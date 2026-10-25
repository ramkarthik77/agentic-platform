import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from sqlalchemy import (JSON, Column, ForeignKey, Integer, MetaData, String,
                        Table, Text, create_engine, event, select)

metadata = MetaData()
schema = Table("schema_version", metadata, Column("version", Integer, primary_key=True))
sites = Table("sites", metadata, Column("id", Integer, primary_key=True), Column("data", JSON, nullable=False))
runs = Table("runs", metadata,
    Column("id", String(40), primary_key=True), Column("key", String(120), unique=True, nullable=False),
    Column("request_hash", String(64), nullable=False), Column("request", JSON, nullable=False),
    Column("kind", String(20), nullable=False), Column("status", String(30), nullable=False),
    Column("stage", String(120), nullable=False), Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False), Column("attempts", Integer, nullable=False, default=0),
    Column("owner", String(40)), Column("lease_until", String(40)), Column("result", JSON), Column("error", Text))
events = Table("events", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True), Column("run_id", String(40), ForeignKey("runs.id")),
    Column("agent", String(20), nullable=False), Column("title", String(160), nullable=False),
    Column("detail", Text, nullable=False), Column("created_at", String(40), nullable=False))
evidence = Table("evidence", metadata,
    Column("id", String(40), primary_key=True), Column("run_id", String(40), ForeignKey("runs.id"), nullable=False),
    Column("tool", String(80), nullable=False), Column("source", String(80), nullable=False),
    Column("captured_at", String(40), nullable=False), Column("digest", String(64), nullable=False),
    Column("data", JSON, nullable=False))
approvals = Table("approvals", metadata,
    Column("id", String(40), primary_key=True), Column("run_id", String(40), ForeignKey("runs.id"), unique=True, nullable=False),
    Column("title", String(200), nullable=False), Column("payload", JSON, nullable=False),
    Column("digest", String(64), nullable=False), Column("status", String(20), nullable=False),
    Column("created_at", String(40), nullable=False), Column("expires_at", String(40), nullable=False),
    Column("decided_at", String(40)), Column("actor", String(80)), Column("reason", Text))
reports = Table("reports", metadata,
    Column("id", String(40), primary_key=True), Column("run_id", String(40), ForeignKey("runs.id"), unique=True, nullable=False),
    Column("title", String(200), nullable=False), Column("markdown", Text, nullable=False),
    Column("created_at", String(40), nullable=False))
audit = Table("audit", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True), Column("action", String(80), nullable=False),
    Column("actor", String(80), nullable=False), Column("resource", String(80), nullable=False),
    Column("detail", JSON, nullable=False), Column("created_at", String(40), nullable=False))


def now(offset=0):
    return (datetime.now(timezone.utc) + timedelta(seconds=offset)).isoformat()


def uid(prefix):
    return prefix + "-" + uuid.uuid4().hex[:16]


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def make_engine(url):
    if url.startswith("sqlite:///") and ":memory:" not in url:
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    args = {"check_same_thread": False, "timeout": 30} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=args, pool_pre_ping=True)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def configure(conn, _):
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA journal_mode=WAL")
    return engine


def initialize(engine, registry):
    metadata.create_all(engine)
    with engine.begin() as conn:
        version = conn.execute(select(schema.c.version)).scalar_one_or_none()
        if version is None:
            conn.execute(schema.insert().values(version=1))
        elif version != 1:
            raise RuntimeError("Unsupported database schema; migration required")
        if conn.execute(select(sites.c.id).limit(1)).first() is None:
            conn.execute(sites.insert(), [{"id": s["id"], "data": s} for s in registry])
            emit(conn, None, "core", "Workspace initialized", "108 fixture sites registered. Phase 1 is ready.")


def emit(conn, run_id, agent, title, detail=""):
    conn.execute(events.insert().values(run_id=run_id, agent=agent, title=title,
                                       detail=detail, created_at=now()))


def record_audit(conn, action, actor, resource, detail):
    conn.execute(audit.insert().values(action=action, actor=actor, resource=resource,
                                      detail=detail, created_at=now()))


def rows(conn, query):
    return [dict(r) for r in conn.execute(query).mappings()]
