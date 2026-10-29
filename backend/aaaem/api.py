import io
import json
import secrets
import hashlib
import hmac
import time
import zipfile
from contextlib import asynccontextmanager
from urllib.parse import urlparse
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from . import db, fixtures
from .config import ROOT, Settings
from .contracts import DecisionRequest, RunRequest
from .service import Conflict, NotFound, Platform
from .setup import read_registry, secret
from .auth import Authentication, AccessDenied, SESSION_COOKIE, FLOW_COOKIE
from .changes import ChangeService
from .http import ConnectionProblem


class WorkspaceHostMiddleware(TrustedHostMiddleware):
    async def __call__(self, scope, receive, send):
        # Load balancer health probes use the task's private IP as Host.
        if scope.get('path') == '/healthz':
            return await self.app(scope, receive, send)
        return await super().__call__(scope, receive, send)


def create_app(settings=None):
    settings = settings or Settings()
    settings.validate()
    engine = db.make_engine(settings.database_url)
    platform = Platform(engine, settings)
    auth, changes = Authentication(engine, settings), ChangeService(platform)

    @asynccontextmanager
    async def lifespan(app):
        registry = fixtures.registry() if settings.integration_mode == 'fixture' else read_registry(settings.workspace)
        db.initialize(engine, registry, settings.integration_mode)
        if settings.worker_enabled: platform.start()
        try: yield
        finally:
            platform.stop()
            engine.dispose()

    app = FastAPI(title='AAAEM Platform', version='0.2.0', lifespan=lifespan,
                  docs_url=None, openapi_url='/api/openapi.json', redoc_url=None)
    app.state.platform, app.state.engine, app.state.auth, app.state.changes = platform, engine, auth, changes
    app.add_middleware(WorkspaceHostMiddleware, allowed_hosts=list(settings.allowed_hosts))

    @app.middleware('http')
    async def boundary(request: Request, call_next):
        actor = auth.principal(request)
        request.state.principal = actor
        intake = request.url.path == '/api/intake'
        if request.url.path.startswith('/api/') and not intake and not actor:
            return JSONResponse({'detail': 'Sign in to the AAAEM workspace', 'login_url': '/auth/login'}, status_code=401)
        if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            length = request.headers.get('content-length', '0')
            if not length.isdigit() or int(length) > 65536:
                return JSONResponse({'detail': 'Request is too large'}, status_code=413)
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 65536: return JSONResponse({'detail': 'Request is too large'}, status_code=413)
            request._body = bytes(body)
            if not intake:
                origin = request.headers.get('origin')
                expected = settings.public_origin if settings.mode == 'production' else str(request.base_url).rstrip('/')
                if origin and (urlparse(origin).scheme != urlparse(expected).scheme or urlparse(origin).netloc != urlparse(expected).netloc):
                    return JSONResponse({'detail': 'Cross-origin writes are not allowed'}, status_code=403)
                if not actor or not secrets.compare_digest(request.headers.get('x-aaaem-csrf', ''), actor.csrf):
                    return JSONResponse({'detail': 'Refresh the workspace session before writing'}, status_code=403)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store' if request.url.path.startswith(('/api', '/auth')) else 'no-cache'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'self'; form-action 'self'")
        if settings.mode == 'production': response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        return response

    @app.exception_handler(Conflict)
    async def conflict(_, exc): return JSONResponse({'detail': str(exc)}, status_code=409)
    @app.exception_handler(IntegrityError)
    async def concurrent(_, exc): return JSONResponse({'detail': 'Concurrent update; refresh and retry'}, status_code=409)
    @app.exception_handler(NotFound)
    async def missing(_, exc): return JSONResponse({'detail': 'Record not found'}, status_code=404)
    @app.exception_handler(AccessDenied)
    async def denied(_, exc): return JSONResponse({'detail': str(exc)}, status_code=403)
    @app.exception_handler(ConnectionProblem)
    async def unavailable(_, exc): return JSONResponse({'detail': exc.code}, status_code=502)

    def principal(request, role='reader', environment=None):
        actor = request.state.principal
        if not actor: raise HTTPException(401, 'Sign in first')
        actor.require(role, environment)
        return actor

    def scoped_run(request, run_id, role='reader'):
        with engine.connect() as conn:
            row = conn.execute(select(db.runs).where(db.runs.c.id == run_id)).mappings().first()
        if not row: raise NotFound()
        principal(request, role, row['request']['environment'])
        return row

    def scoped_change(request, change_id, role):
        with engine.connect() as conn:
            row = conn.execute(select(db.changes).where(db.changes.c.id == change_id)).mappings().first()
        if not row: raise NotFound()
        principal(request, role, row['environment'])
        return row

    @app.get('/auth/login')
    def login():
        if settings.mode == 'local': return RedirectResponse('/')
        url, binding = auth.begin()
        response = RedirectResponse(url, status_code=303)
        response.set_cookie(FLOW_COOKIE, binding, max_age=300, secure=True, httponly=True, samesite='lax', path='/')
        return response

    @app.get('/auth/callback')
    def callback(request: Request, code: str = '', state: str = ''):
        if settings.mode != 'production': raise HTTPException(404)
        session_id, age = auth.finish(code, state, request.cookies.get(FLOW_COOKIE, ''))
        response = RedirectResponse('/', status_code=303)
        response.delete_cookie(FLOW_COOKIE, secure=True, httponly=True, samesite='lax', path='/')
        response.set_cookie(SESSION_COOKIE, session_id, max_age=age, secure=True, httponly=True, samesite='lax', path='/')
        return response

    @app.post('/api/logout')
    def logout(request: Request):
        auth.logout(request.cookies.get(SESSION_COOKIE), principal(request))
        response = JSONResponse({'status': 'signed_out'})
        response.delete_cookie(SESSION_COOKIE, secure=True, httponly=True, samesite='lax', path='/')
        return response

    @app.get('/healthz')
    def health():
        with engine.connect() as conn: conn.execute(select(db.schema.c.version)).scalar_one()
        return {'status': 'ok', 'mode': settings.mode, 'integrations': settings.integration_mode}

    def snapshot(actor):
        with engine.connect() as conn:
            scope = db.runs.c.request['environment'].as_string().in_(actor.environments)
            run_rows = db.rows(conn, select(db.runs).where(scope).order_by(db.runs.c.created_at.desc()).limit(100))
            ids = [r['id'] for r in run_rows]
            for r in run_rows:
                for field in ('key', 'request_hash', 'owner', 'lease_until'): r.pop(field)
            proposals = db.rows(conn, select(db.approvals).where(db.approvals.c.run_id.in_(ids)).order_by(db.approvals.c.created_at.desc()))
            change_rows = db.rows(conn, select(db.changes).where(db.changes.c.environment.in_(actor.environments)).order_by(db.changes.c.created_at.desc()).limit(100))
            for a in proposals + change_rows:
                if a['status'] in {'pending', 'approved'} and a['expires_at'] < db.now(): a['status'] = 'expired'
                a.pop('owner', None); a.pop('lease_until', None)
            return {'runs': run_rows, 'approvals': proposals, 'changes': change_rows,
                'events': db.rows(conn, select(db.events).where(db.events.c.run_id.in_(ids)).order_by(db.events.c.id.desc()).limit(40)),
                'reports': db.rows(conn, select(db.reports.c.id, db.reports.c.run_id, db.reports.c.title, db.reports.c.created_at)
                    .where(db.reports.c.run_id.in_(ids)).order_by(db.reports.c.created_at.desc()).limit(100)),
                'handoffs': db.rows(conn, select(db.handoffs).where(db.handoffs.c.parent_id.in_(ids)))}

    @app.get('/api/bootstrap')
    def bootstrap(request: Request):
        actor = principal(request)
        with engine.connect() as conn: sites = [r['data'] for r in db.rows(conn, select(db.sites).order_by(db.sites.c.id))]
        if settings.integration_mode == 'live':
            sites = [{**s, 'urls': {e: u for e, u in s.get('urls', {}).items() if e in actor.environments}}
                     for s in sites if any(e in actor.environments for e in s.get('urls', {}))]
        return {**snapshot(actor), 'csrf': actor.csrf, 'mode': settings.mode, 'integration_mode': settings.integration_mode,
            'provider': settings.provider, 'actor': actor.name,
            'permissions': {e: {r: actor.allows(r, e) for r in ['reader', 'operator', 'reviewer', 'admin']} for e in actor.environments},
            'environments': actor.environments, 'sites': sites, 'agents': json.loads((ROOT / 'agents/catalog.json').read_text())}

    @app.get('/api/workspace')
    def workspace(request: Request):
        actor = principal(request)
        return {**snapshot(actor), 'csrf': actor.csrf}

    @app.post('/api/runs')
    def submit(request: Request, body: RunRequest, idempotency_key: str = Header(min_length=8, max_length=120)):
        actor = principal(request, 'operator', body.environment)
        key = idempotency_key if settings.mode == 'local' else db.digest([actor.actor, body.environment, idempotency_key])
        run_id, created = platform.submit(body, key, actor.actor)
        return JSONResponse({'id': run_id, 'created': created}, status_code=202 if created else 200)

    @app.get('/api/runs/{run_id}')
    def detail(request: Request, run_id: str):
        run = scoped_run(request, run_id)
        with engine.connect() as conn:
            return {'run': {k: v for k, v in run.items() if k not in {'key', 'request_hash', 'owner', 'lease_until'}},
                'evidence': db.rows(conn, select(db.evidence).where(db.evidence.c.run_id == run_id)),
                'events': db.rows(conn, select(db.events).where(db.events.c.run_id == run_id).order_by(db.events.c.id)),
                'handoffs': db.rows(conn, select(db.handoffs).where(db.handoffs.c.parent_id == run_id).order_by(db.handoffs.c.position))}

    @app.get('/api/runs/{run_id}/artifacts')
    def artifacts(request: Request, run_id: str):
        run = scoped_run(request, run_id)
        files = (run['result'] or {}).get('details', {}).get('files', [])
        if not files: raise NotFound()
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
            for f in files: archive.writestr(f['path'], f['content'])
        return Response(stream.getvalue(), media_type='application/zip', headers={'Content-Disposition': f'attachment; filename="AAAEM-{run_id}.zip"'})

    @app.post('/api/runs/{run_id}/propose-pr')
    def propose(request: Request, run_id: str):
        scoped_run(request, run_id, 'operator')
        return changes.propose(run_id, principal(request).actor)

    @app.post('/api/runs/{run_id}/{action}')
    def control(request: Request, run_id: str, action: str):
        if action not in {'cancel', 'retry'}: raise HTTPException(404, 'Unknown run action')
        scoped_run(request, run_id, 'operator')
        platform.control(run_id, action, principal(request).actor)
        return {'status': 'recorded'}

    @app.post('/api/approvals/{approval_id}/decision')
    def decision(request: Request, approval_id: str, body: DecisionRequest):
        with engine.connect() as conn:
            run_id = conn.execute(select(db.approvals.c.run_id).where(db.approvals.c.id == approval_id)).scalar_one_or_none()
        if not run_id: raise NotFound()
        scoped_run(request, run_id, 'reviewer')
        return platform.decide(approval_id, body, principal(request).actor)

    @app.post('/api/changes/{change_id}/decision')
    def change_decision(request: Request, change_id: str, body: DecisionRequest):
        scoped_change(request, change_id, 'reviewer')
        return changes.decision(change_id, body, principal(request).actor)

    @app.post('/api/changes/{change_id}/execute')
    def execute_change(request: Request, change_id: str):
        scoped_change(request, change_id, 'operator')
        return changes.execute(change_id, principal(request).actor)

    @app.get('/api/reports/{report_id}')
    def report(request: Request, report_id: str, download: bool = False):
        with engine.connect() as conn: row = conn.execute(select(db.reports).where(db.reports.c.id == report_id)).mappings().first()
        if not row: raise NotFound()
        scoped_run(request, row['run_id'])
        return PlainTextResponse(row['markdown'], media_type='text/markdown',
            headers={'Content-Disposition': f'attachment; filename="AAAEM-{row["id"]}.md"'} if download else None)

    @app.get('/api/audit')
    def audit(request: Request):
        actor = principal(request, 'admin')
        admin_envs = [e for e in actor.environments if actor.allows('admin', e)]
        with engine.connect() as conn:
            rows = db.rows(conn, select(db.audit).order_by(db.audit.c.id.desc()).limit(500))
            allowed_runs = set(conn.execute(select(db.runs.c.id).where(db.runs.c.request['environment'].as_string().in_(admin_envs))).scalars())
            allowed_reviews = set(conn.execute(select(db.approvals.c.id).where(db.approvals.c.run_id.in_(allowed_runs))).scalars())
        return [r for r in rows if r['resource'] in allowed_runs | allowed_reviews or r['resource'] == 'session' and r['actor'] == actor.actor
                or r['detail'].get('environment') in admin_envs][:200]

    @app.get('/api/setup')
    def setup(request: Request, environment: str = 'stage'):
        principal(request, 'reader', environment)
        rows = platform.gateway.connections.readiness(environment)
        with engine.connect() as conn:
            checks = {r['key']: r['value'] for r in db.rows(conn, select(db.workspace).where(db.workspace.c.key.like('connection:%')))}
            count = len([r for r in db.rows(conn, select(db.sites)) if settings.integration_mode == 'fixture' or environment in r['data'].get('urls', {})])
        for row in rows: row['last_check'] = checks.get('connection:' + environment + ':' + row['id'])
        target = changes.target(environment)
        return {'environment': environment, 'integration_mode': settings.integration_mode, 'connections': rows,
            'registry_count': count, 'identity': 'local operator' if settings.mode == 'local' else 'OIDC',
            'model_provider': settings.provider, 'templates_approved': settings.workspace.templates_approved,
            'pr_enabled': bool(target and target.enabled),
            'schedules': [s.model_dump() for s in settings.workspace.schedules if s.environment == environment],
            'configuration_guide': '/guide'}

    @app.post('/api/connections/{name}/check')
    def check_connection(request: Request, name: str, environment: str = 'stage'):
        actor = principal(request, 'admin', environment)
        result = platform.gateway.connections.check(environment, name)
        key = 'connection:' + environment + ':' + name
        with engine.begin() as conn:
            changed = conn.execute(db.workspace.update().where(db.workspace.c.key == key).values(value=result)).rowcount
            if not changed: conn.execute(db.workspace.insert().values(key=key, value=result))
            db.record_audit(conn, 'connection.checked', actor.actor, name, {'environment': environment, 'status': result['status']})
        return result

    @app.post('/api/intake')
    async def intake(request: Request):
        key = secret(settings.workspace.intake_secret_env)
        if len(key) < 32: raise HTTPException(503, 'Signed event intake is not configured')
        timestamp, signature = request.headers.get('x-aaaem-timestamp', ''), request.headers.get('x-aaaem-signature', '')
        try:
            if abs(time.time() - int(timestamp)) > 300: raise ValueError()
        except ValueError: raise HTTPException(401, 'Expired event signature') from None
        raw = await request.body()
        expected = hmac.new(key.encode(), timestamp.encode() + b'.' + raw, hashlib.sha256).hexdigest()
        if not secrets.compare_digest(expected, signature): raise HTTPException(401, 'Invalid event signature')
        try:
            event = json.loads(raw)
            if set(event) != {'event_id', 'source', 'request'} or event['source'] not in {'cloud_manager', 'monitoring', 'teams', 'scheduler'}: raise ValueError()
            if not isinstance(event['event_id'], str) or not 1 <= len(event['event_id']) <= 160: raise ValueError()
            body = RunRequest.model_validate(event['request'])
        except (ValueError, KeyError, TypeError): raise HTTPException(422, 'Invalid normalized event contract') from None
        if body.environment not in settings.workspace.intake_environments: raise HTTPException(403, 'Event intake is not enabled for this environment')
        run_id, created = platform.submit(body, 'event:' + db.digest([event['source'], event['event_id']]), 'intake:' + event['source'])
        return JSONResponse({'id': run_id, 'created': created}, status_code=202 if created else 200)

    app.mount('/assets', StaticFiles(directory=ROOT / 'web/assets'), name='assets')
    @app.get('/guide')
    def guide(request: Request):
        if settings.mode == 'production' and not request.state.principal: return RedirectResponse('/auth/login')
        return FileResponse(ROOT / 'docs/SETUP.md', media_type='text/plain')
    @app.get('/')
    def index(): return FileResponse(ROOT / 'web/index.html')
    return app
