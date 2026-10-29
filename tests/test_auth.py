import json
import time
from urllib.parse import parse_qs, urlsplit
import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from aaaem import db
from aaaem.auth import Authentication, AccessDenied, SESSION_COOKIE
from aaaem.config import Settings
from aaaem.http import Http


@pytest.fixture
def identity(tmp_path,monkeypatch):
    monkeypatch.setenv('TEST_OIDC_SECRET','only-for-this-test')
    config=tmp_path/'workspace.json'
    config.write_text(json.dumps({'auth':{'issuer':'https://id.example/','authorization_endpoint':'https://id.example/authorize',
        'token_endpoint':'https://id.example/token','jwks_endpoint':'https://id.example/keys','client_id':'aaaem-test','client_secret_env':'TEST_OIDC_SECRET',
        'group_grants':{'stage-operators':{'roles':['operator'],'environments':['stage']}}}}))
    settings=Settings(database_url=f'sqlite:///{tmp_path}/auth.db',mode='production',config_file=str(config),public_origin='https://app.example')
    engine=db.make_engine(settings.database_url);db.initialize(engine,[],'live')
    private=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    public=json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))|{'kid':'key1','use':'sig','alg':'RS256'}
    auth=Authentication(engine,settings,Http(httpx.MockTransport(lambda r:httpx.Response(200,json={'keys':[public]}))))
    claims={'iss':'https://id.example/','aud':'aaaem-test','sub':'user1','iat':int(time.time()),'exp':int(time.time())+600,
            'nonce':'nonce1','name':'Test User','groups':['stage-operators']}
    def sign(data):return jwt.encode(data,private,algorithm='RS256',headers={'kid':'key1'})
    yield auth,claims,sign,public
    engine.dispose()


@pytest.mark.parametrize('override',[{'iss':'https://wrong.example/'},{'aud':'other'},{'nonce':'replayed'},
    {'exp':int(time.time())-100},{'aud':['aaaem-test','other']},{'azp':'other'}])
def test_oidc_rejects_claim_confusion(identity,override):
    auth,claims,sign,_=identity
    with pytest.raises(AccessDenied):auth.validate_token(sign(claims|override),'nonce1')


def test_oidc_rejects_algorithm_confusion(identity):
    auth,claims,_,_=identity
    bad=jwt.encode(claims,'random-test-key-with-at-least-32-characters',algorithm='HS256',headers={'kid':'key1'})
    with pytest.raises(AccessDenied):auth.validate_token(bad,'nonce1')


def test_full_pkce_login_scopes_session_and_consumes_callback(identity):
    auth,claims,sign,public=identity
    url,binding=auth.begin();query=parse_qs(urlsplit(url).query)
    assert query['code_challenge_method']==['S256']
    claims['nonce']=query['nonce'][0]
    def handle(r):
        if r.url.path=='/keys':return httpx.Response(200,json={'keys':[public]})
        fields=parse_qs(r.content.decode())
        assert fields['redirect_uri']==['https://app.example/auth/callback'] and len(fields['code_verifier'][0])>40
        return httpx.Response(200,json={'id_token':sign(claims)})
    auth.http=Http(httpx.MockTransport(handle))
    with pytest.raises(AccessDenied):auth.finish('code',query['state'][0],'wrong-browser')
    cookie,age=auth.finish('code',query['state'][0],binding)
    request=type('Request',(),{'cookies':{SESSION_COOKIE:cookie}})()
    principal=auth.principal(request)
    assert principal.allows('operator','stage') and not principal.allows('operator','production')
    assert 0<age<=600 and principal.name=='Test User'
    with pytest.raises(AccessDenied):auth.finish('code',query['state'][0],binding)
    auth.logout(cookie,principal)
    assert auth.principal(request) is None


def test_oidc_rejects_unassigned_account(identity):
    auth,claims,sign,public=identity
    url,binding=auth.begin();query=parse_qs(urlsplit(url).query)
    claims.update(nonce=query['nonce'][0],groups=['unassigned'])
    auth.http=Http(httpx.MockTransport(lambda r:httpx.Response(200,json={'keys':[public]} if r.url.path=='/keys' else {'id_token':sign(claims)})))
    with pytest.raises(AccessDenied,match='No AAAEM role'):auth.finish('code',query['state'][0],binding)
