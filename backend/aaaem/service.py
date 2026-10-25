import threading
import time
from collections import Counter
from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError
from . import db
from .contracts import RunRequest
from .policy import ExecutionContext, ToolGateway
from .providers import make_provider


class Conflict(Exception):
    pass


class NotFound(Exception):
    pass


class LeaseLost(Exception):
    pass


TITLES = {"release": "Release verification dossier", "incident": "Incident investigation brief",
          "reporting": "Platform status brief"}


class Platform:
    def __init__(self, engine, settings):
        self.engine, self.settings = engine, settings
        self.gateway = ToolGateway()
        self.provider = make_provider(settings)
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        self.thread = threading.Thread(target=self.loop, name="aaaem-local-worker", daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=55)

    def loop(self):
        while not self.stop_event.is_set():
            try:
                if not self.tick():
                    self.stop_event.wait(0.5)
            except Exception:
                # Do not log provider responses or credentials. Records retain a bounded error code.
                import logging
                logging.getLogger("aaaem").error("Worker polling failed; retrying after backoff")
                self.stop_event.wait(2)

    def submit(self, request: RunRequest, key: str):
        data = request.model_dump()
        fingerprint = db.digest(data)
        with self.engine.begin() as conn:
            existing = conn.execute(select(db.runs).where(db.runs.c.key == key)).mappings().first()
            if existing:
                if existing["request_hash"] != fingerprint:
                    raise Conflict("Idempotency key is already bound to different input")
                return existing["id"], False
            active = conn.execute(select(func.count()).select_from(db.runs).where(
                db.runs.c.status.in_(["queued", "running"]))).scalar_one()
            if active >= 50:
                raise Conflict("Local queue is full; wait for existing runs")
            run_id = db.uid("RUN")
            try:
                conn.execute(db.runs.insert().values(id=run_id, key=key, request_hash=fingerprint,
                    request=data, kind=data["kind"], status="queued", stage="Queued for worker",
                    created_at=db.now(), updated_at=db.now(), attempts=0))
                db.emit(conn, run_id, "core", "Work accepted", TITLES[data["kind"]])
                db.record_audit(conn, "run.created", "local-operator", run_id, data)
            except IntegrityError:
                # The outer transaction rolls back; the caller can replay the same key.
                raise Conflict("Concurrent request with the same key; retry the request") from None
        return run_id, True

    def recover(self):
        with self.engine.begin() as conn:
            stale = db.rows(conn, select(db.runs).where(db.runs.c.status == "running", db.runs.c.lease_until < db.now()))
            for run in stale:
                status = "failed" if run["attempts"] >= self.settings.max_attempts else "queued"
                changed = conn.execute(update(db.runs).where(db.runs.c.id == run["id"],
                    db.runs.c.status == "running", db.runs.c.owner == run["owner"],
                    db.runs.c.lease_until < db.now()).values(status=status, owner=None,
                    lease_until=None, stage="Recovering interrupted work", updated_at=db.now(),
                    error="Attempt limit reached" if status == "failed" else None)).rowcount
                if changed:
                    db.emit(conn, run["id"], "core", "Expired worker lease recovered", status)

    def claim(self):
        with self.engine.begin() as conn:
            candidate = conn.execute(select(db.runs).where(db.runs.c.status == "queued").order_by(
                db.runs.c.created_at).limit(1)).mappings().first()
            if not candidate:
                return None
            owner = db.uid("lease")
            changed = conn.execute(update(db.runs).where(db.runs.c.id == candidate["id"],
                db.runs.c.status == "queued").values(status="running", owner=owner,
                lease_until=db.now(self.settings.lease_seconds), attempts=db.runs.c.attempts + 1,
                updated_at=db.now(), stage="Collecting evidence", error=None)).rowcount
            if not changed:
                return None
            db.emit(conn, candidate["id"], candidate["kind"], "Agent started", "Read-only tool policy applied")
            return dict(candidate, owner=owner)

    def guarded(self, conn, run, stage):
        if self.stop_event.is_set():
            raise LeaseLost()
        changed = conn.execute(update(db.runs).where(db.runs.c.id == run["id"],
            db.runs.c.status == "running", db.runs.c.owner == run["owner"],
            db.runs.c.lease_until >= db.now()).values(stage=stage, updated_at=db.now(),
            lease_until=db.now(self.settings.lease_seconds))).rowcount
        if not changed:
            raise LeaseLost()

    def tick(self):
        self.recover()
        run = self.claim()
        if not run:
            return False
        try:
            self.execute(run)
        except LeaseLost:
            pass
        except Exception as exc:
            with self.engine.begin() as conn:
                changed = conn.execute(update(db.runs).where(db.runs.c.id == run["id"],
                    db.runs.c.owner == run["owner"], db.runs.c.status == "running").values(
                    status="failed", stage="Needs attention", error=type(exc).__name__ + ": agent step failed",
                    updated_at=db.now(), owner=None, lease_until=None)).rowcount
                if changed:
                    db.emit(conn, run["id"], run["kind"], "Run failed", "Inspect configuration and retry. No external write occurred.")
        return True

    def execute(self, run):
        request = run["request"]
        context = ExecutionContext(run["kind"], request["environment"], run["id"])
        with self.engine.connect() as conn:
            sites = [r["data"] for r in db.rows(conn, select(db.sites))]
            history = db.rows(conn, select(db.runs.c.id, db.runs.c.kind, db.runs.c.status,
                db.runs.c.created_at).where(db.runs.c.id != run["id"],
                    db.runs.c.request["environment"].as_string() == request["environment"]
                ).order_by(db.runs.c.created_at.desc()).limit(100))
        collected = []

        def tool(name, selected=None):
            with self.engine.begin() as conn:
                self.guarded(conn, run, name)
            if self.stop_event.wait(self.settings.step_delay):
                raise LeaseLost()
            result = self.gateway.call(context, name, request, sites, history, selected)
            item = {"id": db.uid("EV"), "run_id": run["id"], "tool": name,
                    "source": result["source"], "captured_at": db.now(), "digest": db.digest(result), "data": result}
            with self.engine.begin() as conn:
                self.guarded(conn, run, name)
                conn.execute(db.evidence.insert().values(**item))
                db.emit(conn, run["id"], run["kind"], "Evidence collected", name)
                db.record_audit(conn, "tool.read", "agent:" + context.agent, run["id"],
                                {"tool": name, "environment": context.environment, "evidence": item["id"]})
            collected.append(item)
            return result

        assessment, revision, scope = "draft", None, []
        details = {}
        if run["kind"] == "release":
            release = tool("cloud_manager.execution")
            impacted = tool("registry.impact")
            scope = impacted["site_ids"]
            checks = tool("verification.results", scope)
            telemetry = tool("monitoring.metrics")
            revision = release["revision"]
            expected = set(scope)
            observed = {s["id"] for s in checks["sites"]}
            bound = (checks["revision"] == revision and checks["environment"] == request["environment"]
                     and checks["execution_id"] == release["execution_id"])
            assessment = "inconclusive" if expected != observed or not bound else (
                "failed" if any(s["passed"] != s["total"] for s in checks["sites"]) else "verified")
            details = {"site_ids": scope, "site_results": checks["sites"], "impact_reason": impacted["reason"],
                       "coverage_uncertain": impacted["coverage_uncertain"], "pages_per_site": 4,
                       "checks_per_site": 28, "telemetry": telemetry,
                       "coverage_note": "Four representative pages per selected fixture site. Not a full-site audit."}
        elif run["kind"] == "incident":
            telemetry = tool("monitoring.metrics")
            logs = tool("splunk.summary")
            release = tool("cloud_manager.execution")
            revision = release["revision"]
            assessment = "unconfirmed"
            details = {"root_cause": "unconfirmed", "telemetry": telemetry,
                       "patterns": logs["patterns"], "correlation_is_causation": False}
        else:
            data = tool("history.summary")
            details = {"run_count": len(data["runs"]), "by_status": dict(Counter(r["status"] for r in data["runs"])),
                       "source_run_ids": [r["id"] for r in data["runs"]], "window": data["window"]}
        with self.engine.begin() as conn:
            self.guarded(conn, run, "Preparing evidence-linked draft")
        narrative = self.provider.summarize(run["kind"], collected, assessment)
        result = {"assessment": assessment, "revision": revision, "environment": request["environment"],
                  "details": details, "narrative": narrative.model_dump(), "provider": self.provider.name,
                  "input_mode": "fixture", "evidence_ids": [e["id"] for e in collected]}
        markdown = self.make_report(run, result, collected)
        with self.engine.begin() as conn:
            self.guarded(conn, run, "Draft ready")
            status = "awaiting_review" if run["kind"] == "release" else "draft_ready"
            conn.execute(update(db.runs).where(db.runs.c.id == run["id"]).values(
                status=status, result=result, owner=None, lease_until=None, updated_at=db.now()))
            conn.execute(db.reports.insert().values(id=db.uid("DOC"), run_id=run["id"],
                title=TITLES[run["kind"]], markdown=markdown, created_at=db.now()))
            if run["kind"] == "release":
                payload = {"action": "accept_draft_only", "run_id": run["id"], "revision": revision,
                           "environment": request["environment"], "site_ids": scope,
                           "evidence_ids": result["evidence_ids"], "result_hash": db.digest(result)}
                conn.execute(db.approvals.insert().values(id=db.uid("APR"), run_id=run["id"],
                    title="Review release dossier", payload=payload, digest=db.digest(payload), status="pending",
                    created_at=db.now(), expires_at=db.now(86400)))
            db.emit(conn, run["id"], run["kind"], "Draft ready for review", assessment)

    @staticmethod
    def make_report(run, result, collected):
        lines = ["# " + TITLES[run["kind"]], "", "Run: " + run["id"],
                 "Environment: " + result["environment"], "Input data: synthetic fixtures",
                 "Summary provider: " + result["provider"], "Assessment: " + result["assessment"],
                 "", "## Draft summary", result["narrative"]["summary"], "", "## Coverage and findings"]
        import json
        lines += ["```json", json.dumps(result["details"], indent=2), "```", "", "## Limitations"]
        lines += ["- " + x for x in result["narrative"]["limitations"]]
        if result["narrative"]["hypotheses"]:
            lines += ["", "## Hypotheses (unconfirmed)"] + ["- " + x for x in result["narrative"]["hypotheses"]]
        lines += ["", "## Evidence"]
        lines += [f"- {e['id']} | {e['tool']} | {e['source']} | {e['captured_at']} | SHA-256 {e['digest']}" for e in collected]
        lines += ["", "Phase 1 produces read-only drafts. Accepting this draft does not deploy, publish, or change an external system."]
        return "\n".join(lines)

    def control(self, run_id, action):
        with self.engine.begin() as conn:
            run = conn.execute(select(db.runs).where(db.runs.c.id == run_id)).mappings().first()
            if not run:
                raise NotFound()
            if action == "cancel":
                valid, status = ["queued", "running"], "cancelled"
            else:
                if run["attempts"] >= self.settings.max_attempts:
                    raise Conflict("Attempt limit reached; start a new run after addressing the failure")
                valid, status = ["failed"], "queued"
            changed = conn.execute(update(db.runs).where(db.runs.c.id == run_id,
                db.runs.c.status.in_(valid)).values(status=status, stage=status.replace("_", " "),
                owner=None, lease_until=None, error=None, updated_at=db.now())).rowcount
            if not changed:
                raise Conflict("The run has moved on; refresh its status")
            db.emit(conn, run_id, "core", "Run " + status)
            db.record_audit(conn, "run." + action, "local-operator", run_id, {})

    def decide(self, approval_id, decision):
        with self.engine.begin() as conn:
            proposal = conn.execute(select(db.approvals).where(db.approvals.c.id == approval_id)).mappings().first()
            if not proposal:
                raise NotFound()
            if decision.digest != proposal["digest"] or db.digest(proposal["payload"]) != proposal["digest"]:
                raise Conflict("Proposal changed; review the current evidence")
            if proposal["status"] != "pending":
                if proposal["status"] == decision.decision:
                    return dict(proposal)  # Harmless replay; no second audit/action.
                raise Conflict("A different decision has already been recorded")
            if proposal["expires_at"] < db.now():
                raise Conflict("Proposal expired; run verification again")
            run = conn.execute(select(db.runs).where(db.runs.c.id == proposal["run_id"])).mappings().one()
            if (run["status"] != "awaiting_review" or not run["result"] or
                    db.digest(run["result"]) != proposal["payload"]["result_hash"]):
                raise Conflict("Run evidence changed; review a fresh dossier")
            changed = conn.execute(update(db.approvals).where(db.approvals.c.id == approval_id,
                db.approvals.c.status == "pending", db.approvals.c.digest == decision.digest).values(
                status=decision.decision, actor="local-operator", reason=decision.reason,
                decided_at=db.now())).rowcount
            if not changed:
                raise Conflict("A concurrent decision was recorded; refresh the page")
            conn.execute(update(db.runs).where(db.runs.c.id == proposal["run_id"]).values(
                status="reviewed", stage="Draft " + decision.decision, updated_at=db.now()))
            db.emit(conn, proposal["run_id"], "core", "Draft " + decision.decision, "Local review recorded; no deployment or publication triggered")
            db.record_audit(conn, "draft." + decision.decision, "local-operator", approval_id,
                            {"digest": decision.digest, "reason": decision.reason})
        return {"status": decision.decision}
