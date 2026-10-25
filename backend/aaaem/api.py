import json
import secrets
from contextlib import asynccontextmanager
from urllib.parse import urlparse
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import select
from . import db, fixtures
from .config import ROOT, Settings
from .contracts import DecisionRequest, RunRequest
from .service import Conflict, NotFound, Platform


def create_app(settings=None):
    settings = settings or Settings()
    settings.validate()
    engine = db.make_engine(settings.database_url)
    platform = Platform(engine, settings)
    csrf = secrets.token_urlsafe(32)

    @asynccontextmanager
    async def lifespan(app):
        db.initialize(engine, fixtures.registry())
        if settings.worker_enabled:
            platform.start()
        yield
        platform.stop()
        engine.dispose()

    app = FastAPI(title="AAAEM Platform", version="0.1.0", lifespan=lifespan,
                  docs_url=None, openapi_url="/api/openapi.json", redoc_url=None)
    app.state.platform, app.state.engine = platform, engine
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.allowed_hosts))

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            # Local app, same-origin only. A bearer token fetched through same-origin bootstrap
            # protects writes from cross-site form/fetch attacks; this is not enterprise auth.
            if origin and urlparse(origin).netloc != request.headers.get("host"):
                return JSONResponse({"detail": "Cross-origin writes are not allowed"}, status_code=403)
            if not secrets.compare_digest(request.headers.get("x-aaaem-csrf", ""), csrf):
                return JSONResponse({"detail": "Refresh the workspace session before writing"}, status_code=403)
            length = request.headers.get("content-length", "0")
            if not length.isdigit() or int(length) > 16384:
                return JSONResponse({"detail": "Request is too large"}, status_code=413)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api") else "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = ("default-src 'self'; script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; "
            "object-src 'none'; base-uri 'none'; frame-ancestors 'self'")
        return response

    @app.exception_handler(Conflict)
    async def conflict(_, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(NotFound)
    async def missing(_, exc):
        return JSONResponse({"detail": "Record not found"}, status_code=404)

    @app.get("/healthz")
    def health():
        with engine.connect() as conn:
            conn.execute(select(db.schema.c.version)).scalar_one()
        return {"status": "ok", "mode": "local", "integrations": "fixture"}

    def snapshot():
        with engine.connect() as conn:
            run_rows = db.rows(conn, select(db.runs).order_by(db.runs.c.created_at.desc()).limit(100))
            for r in run_rows:
                for field in ("key", "request_hash", "owner", "lease_until"):
                    r.pop(field)
            proposals = db.rows(conn, select(db.approvals).order_by(db.approvals.c.created_at.desc()).limit(100))
            for a in proposals:
                if a["status"] == "pending" and a["expires_at"] < db.now():
                    a["status"] = "expired"
            return {"runs": run_rows, "approvals": proposals,
                    "events": db.rows(conn, select(db.events).order_by(db.events.c.id.desc()).limit(40)),
                    "reports": db.rows(conn, select(db.reports.c.id, db.reports.c.run_id,
                        db.reports.c.title, db.reports.c.created_at).order_by(db.reports.c.created_at.desc()).limit(100))}

    @app.get("/api/bootstrap")
    def bootstrap():
        with engine.connect() as conn:
            site_rows = [r["data"] for r in db.rows(conn, select(db.sites).order_by(db.sites.c.id))]
        return {**snapshot(), "csrf": csrf, "mode": "local", "integration_mode": "fixture",
                "provider": settings.provider, "actor": "local-operator", "sites": site_rows,
                "agents": json.loads((ROOT / "agents" / "catalog.json").read_text())}

    @app.get("/api/workspace")
    def workspace():
        return {**snapshot(), "csrf": csrf}

    @app.post("/api/runs")
    def submit(body: RunRequest, idempotency_key: str = Header(min_length=8, max_length=120)):
        run_id, created = platform.submit(body, idempotency_key)
        return JSONResponse({"id": run_id, "created": created}, status_code=202 if created else 200)

    @app.get("/api/runs/{run_id}")
    def detail(run_id: str):
        with engine.connect() as conn:
            run = conn.execute(select(db.runs).where(db.runs.c.id == run_id)).mappings().first()
            if not run:
                raise NotFound()
            safe = {k: v for k, v in run.items() if k not in {"key", "request_hash", "owner", "lease_until"}}
            return {"run": safe, "evidence": db.rows(conn, select(db.evidence).where(db.evidence.c.run_id == run_id)),
                    "events": db.rows(conn, select(db.events).where(db.events.c.run_id == run_id).order_by(db.events.c.id))}

    @app.post("/api/runs/{run_id}/{action}")
    def control(run_id: str, action: str):
        if action not in {"cancel", "retry"}:
            raise HTTPException(404, "Unknown run action")
        platform.control(run_id, action)
        return {"status": "recorded"}

    @app.post("/api/approvals/{approval_id}/decision")
    def decision(approval_id: str, body: DecisionRequest):
        return platform.decide(approval_id, body)

    @app.get("/api/reports/{report_id}")
    def report(report_id: str, download: bool = False):
        with engine.connect() as conn:
            row = conn.execute(select(db.reports).where(db.reports.c.id == report_id)).mappings().first()
            if not row:
                raise NotFound()
        return PlainTextResponse(row["markdown"], media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="AAAEM-{row["id"]}.md"'} if download else None)

    @app.get("/api/audit")
    def audit():
        with engine.connect() as conn:
            return db.rows(conn, select(db.audit).order_by(db.audit.c.id.desc()).limit(200))

    app.mount("/assets", StaticFiles(directory=ROOT / "web" / "assets"), name="assets")

    @app.get("/")
    def index():
        return FileResponse(ROOT / "web" / "index.html")

    return app
