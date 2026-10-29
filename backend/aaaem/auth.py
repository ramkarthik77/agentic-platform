"""OIDC authorization-code + PKCE login and database-backed, environment-scoped sessions."""
import base64
import hashlib
import secrets
import time
from dataclasses import dataclass
from urllib.parse import urlencode
import jwt
from sqlalchemy import select, delete
from . import db
from .http import Http, ConnectionProblem
from .setup import secret

SESSION_COOKIE = '__Host-aaaem-session'
FLOW_COOKIE = '__Host-aaaem-flow'


class AccessDenied(Exception):
    pass


@dataclass(frozen=True)
class Principal:
    actor: str
    name: str
    grants: tuple
    csrf: str

    def allows(self, role='reader', environment=None):
        for grant in self.grants:
            roles = grant['roles']
            permitted = role in roles or 'admin' in roles or role == 'reader' and bool(roles)
            if permitted and (environment is None or environment in grant['environments']):
                return True
        return False

    @property
    def environments(self):
        return sorted({e for g in self.grants for e in g['environments']})

    def require(self, role='reader', environment=None):
        if not self.allows(role, environment):
            raise AccessDenied('Your role does not allow this action in this environment')


class Authentication:
    def __init__(self, engine, settings, http=None):
        self.engine, self.settings = engine, settings
        self.config = settings.workspace.auth
        self.http = http or Http()
        self.local = Principal('local-operator', 'Local operator',
            ({'roles': ['admin'], 'environments': ['dev', 'stage', 'production']},), secrets.token_urlsafe(32))
        self._jwks, self._jwks_until = None, 0

    def principal(self, request):
        if self.settings.mode == 'local':
            return self.local
        cookie = request.cookies.get(SESSION_COOKIE)
        if not cookie:
            return None
        with self.engine.connect() as conn:
            row = conn.execute(select(db.sessions).where(db.sessions.c.id_hash == db.digest(cookie),
                db.sessions.c.expires_at > db.now())).mappings().first()
        return Principal(row['actor'], row['display_name'], tuple(row['grants']), row['csrf']) if row else None

    def begin(self):
        state, binding, nonce, verifier = [secrets.token_urlsafe(32) for _ in range(4)]
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
        with self.engine.begin() as conn:
            conn.execute(delete(db.auth_flows).where(db.auth_flows.c.expires_at < db.now()))
            conn.execute(delete(db.sessions).where(db.sessions.c.expires_at < db.now()))
            conn.execute(db.auth_flows.insert().values(state_hash=db.digest(state), binding_hash=db.digest(binding),
                nonce=nonce, verifier=verifier, expires_at=db.now(300)))
        query = urlencode({'response_type': 'code', 'client_id': self.config.client_id,
            'redirect_uri': self.settings.public_origin + '/auth/callback', 'scope': 'openid profile email',
            'state': state, 'nonce': nonce, 'code_challenge': challenge, 'code_challenge_method': 'S256'})
        return self.config.authorization_endpoint + '?' + query, binding

    def validate_token(self, token, nonce):
        try:
            header = jwt.get_unverified_header(token)
            if header.get('alg') != 'RS256' or not header.get('kid'):
                raise AccessDenied('Unsupported identity token')
            if not self._jwks or self._jwks_until < time.time() or not any(k.get('kid') == header['kid'] for k in self._jwks.get('keys', [])):
                self._jwks = self.http.json('GET', self.config.jwks_endpoint, limit=262144)
                self._jwks_until = time.time() + 300
            matches = [k for k in self._jwks.get('keys', []) if k.get('kid') == header['kid']
                       and k.get('use', 'sig') == 'sig' and k.get('kty') == 'RSA' and k.get('alg', 'RS256') == 'RS256']
            if len(matches) != 1:
                raise AccessDenied('Unknown identity signing key')
            claims = jwt.decode(token, jwt.PyJWK.from_dict(matches[0]).key, algorithms=['RS256'],
                audience=self.config.client_id, issuer=self.config.issuer, leeway=30,
                options={'require': ['exp', 'iat', 'iss', 'aud', 'sub', 'nonce']})
            if not secrets.compare_digest(str(claims['nonce']), nonce):
                raise AccessDenied('Identity nonce does not match')
            aud = claims['aud']
            if (isinstance(aud, list) and len(aud) > 1 or 'azp' in claims) and claims.get('azp') != self.config.client_id:
                raise AccessDenied('Identity authorized party does not match')
            if not isinstance(claims['sub'], str) or not claims['sub']:
                raise AccessDenied('Identity subject is missing')
            return claims
        except (jwt.PyJWTError, ValueError, KeyError, TypeError, ConnectionProblem):
            raise AccessDenied('Identity token could not be validated') from None

    def finish(self, code, state, binding):
        if not all([code, state, binding]) or max(map(len, [code, state, binding])) > 4096:
            raise AccessDenied('Invalid sign-in callback')
        with self.engine.begin() as conn:
            flow = conn.execute(select(db.auth_flows).where(db.auth_flows.c.state_hash == db.digest(state),
                db.auth_flows.c.expires_at > db.now())).mappings().first()
            if not flow or not secrets.compare_digest(flow['binding_hash'], db.digest(binding)):
                raise AccessDenied('Sign-in expired or did not begin in this browser')
            consumed = conn.execute(delete(db.auth_flows).where(db.auth_flows.c.state_hash == db.digest(state))).rowcount
            if consumed != 1:
                raise AccessDenied('Sign-in callback has already been used')
        tokens = self.http.json('POST', self.config.token_endpoint, data={'grant_type': 'authorization_code',
            'code': code, 'redirect_uri': self.settings.public_origin + '/auth/callback',
            'client_id': self.config.client_id, 'client_secret': secret(self.config.client_secret_env),
            'code_verifier': flow['verifier']})
        claims = self.validate_token(tokens.get('id_token', ''), flow['nonce'])
        groups = claims.get(self.config.group_claim, [])
        if not isinstance(groups, list) or len(groups) > 1000 or not all(isinstance(x, str) for x in groups):
            raise AccessDenied('Configure a group or app-role list claim in the identity provider')
        grants = [g.model_dump() for k, g in self.config.group_grants.items() if k in groups]
        if not grants:
            raise AccessDenied('No AAAEM role has been assigned to this account')
        session_id = secrets.token_urlsafe(32)
        actor = 'oidc:' + db.digest([claims['iss'], claims['sub']])
        lifetime = min(self.config.session_minutes * 60, int(claims['exp'] - time.time()))
        if lifetime <= 0:
            raise AccessDenied('Identity token has expired')
        with self.engine.begin() as conn:
            conn.execute(db.sessions.insert().values(id_hash=db.digest(session_id), actor=actor,
                display_name=str(claims.get('name', 'Platform user'))[:160], grants=grants,
                csrf=secrets.token_urlsafe(32), expires_at=db.now(lifetime)))
            db.record_audit(conn, 'session.created', actor, 'session', {})
        return session_id, lifetime

    def logout(self, cookie, principal):
        if cookie:
            with self.engine.begin() as conn:
                conn.execute(delete(db.sessions).where(db.sessions.c.id_hash == db.digest(cookie)))
                db.record_audit(conn, 'session.ended', principal.actor, 'session', {})
