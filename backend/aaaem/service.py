import threading
import time
from collections import Counter
from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError
from . import db
from .contracts import RunRequest
from .policy import ExecutionContext, ToolGateway
from .providers import make_provider
from .http import ConnectionProblem


class Conflict(Exception):
    pass


class NotFound(Exception):
    pass


class LeaseLost(Exception):
    pass


TITLES = {"release": "Release verification dossier", "incident": "Incident investigation brief",
          "reporting": "Platform status brief", 'core': 'Agent team mission brief',
          'security': 'Security and quality review', 'factory': 'Site configuration proposal',
          'governance': 'Content governance report'}
TERMINAL = {'awaiting_review', 'draft_ready', 'reviewed', 'failed', 'blocked', 'cancelled'}


class Platform:
    def __init__(self, engine, settings):
        self.engine, self.settings = engine, settings
        self.gateway = ToolGateway(settings)
        self.provider = make_provider(settings)
        self.stop_event = threading.Event()
        self.thread = None
        self.last_schedule_check = 0

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
                self.heartbeat()
                if not self.tick():
                    self.stop_event.wait(0.5)
            except Exception:
                # Do not log provider responses or credentials. Records retain a bounded error code.
                import logging
                logging.getLogger("aaaem").error("Worker polling failed; retrying after backoff")
                self.stop_event.wait(2)

    @staticmethod
    def heartbeat():
        import os
        from pathlib import Path
        if path := os.getenv('AAAEM_WORKER_HEARTBEAT'):
            Path(path).touch()

    def submit(self, request: RunRequest, key: str, actor='local-operator'):
        data = request.model_dump()
        fingerprint = db.digest(data)
        with self.engine.begin() as conn:
            existing = conn.execute(select(db.runs).where(db.runs.c.key == key)).mappings().first()
            if existing:
                if existing["request_hash"] != fingerprint:
                    raise Conflict("Idempotency key is already bound to different input")
                return existing["id"], False
            active = conn.execute(select(func.count()).select_from(db.runs).where(
                db.runs.c.status.in_(["queued", "running", "waiting_children"]))).scalar_one()
            if active >= 50:
                raise Conflict("Local queue is full; wait for existing runs")
            run_id = db.uid("RUN")
            try:
                conn.execute(db.runs.insert().values(id=run_id, key=key, request_hash=fingerprint,
                    request=data, kind=data["kind"], status="queued", stage="Queued for worker",
                    created_at=db.now(), updated_at=db.now(), attempts=0))
                conn.execute(db.owners.insert().values(run_id=run_id, actor=actor))
                db.emit(conn, run_id, "core", "Work accepted", TITLES[data["kind"]])
                db.record_audit(conn, "run.created", actor, run_id, data)
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
        self.heartbeat()
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
        self.advance_missions()
        self.schedule_due()
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
        if run['kind'] == 'core':
            return self.execute_mission(run)
        request = dict(run["request"])
        context = ExecutionContext(run["kind"], request["environment"], run["id"])
        with self.engine.connect() as conn:
            sites = [r["data"] for r in db.rows(conn, select(db.sites))]
            history = db.rows(conn, select(db.runs.c.id, db.runs.c.kind, db.runs.c.status,
                db.runs.c.created_at).where(db.runs.c.id != run["id"],
                    db.runs.c.request["environment"].as_string() == request["environment"]
                ).order_by(db.runs.c.created_at.desc()).limit(100))
        collected = []
        def checkpoint():
            with self.engine.begin() as conn:
                self.guarded(conn, run, 'Collecting bounded verification batch')
        request['_checkpoint'] = checkpoint

        def tool(name, selected=None):
            with self.engine.begin() as conn:
                self.guarded(conn, run, name)
            if self.stop_event.wait(self.settings.step_delay):
                raise LeaseLost()
            try:
                if name == 'verification.results' and not selected:
                    raise ConnectionProblem('site_registry_empty')
                result = self.gateway.call(context, name, request, sites, history, selected)
            except ConnectionProblem as exc:
                result = {'source': 'unavailable', 'available': False, 'reason': exc.code, 'operation': name}
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
            request['_revision'] = release.get('revision')
            request['execution_id'] = release.get('execution_id', request.get('execution_id', ''))
            impacted = tool("registry.impact")
            scope = impacted["site_ids"]
            checks = tool("verification.results", scope)
            telemetry = tool("monitoring.metrics")
            revision = release.get('revision')
            assessment = self.assess_checks(request, release, checks, scope)
            details = {"site_ids": scope, "site_results": checks.get('sites', []), "impact_reason": impacted["reason"],
                       "coverage_uncertain": impacted["coverage_uncertain"], "telemetry": telemetry,
                       "revision_verified": checks.get('revision_verified', self.settings.integration_mode == 'fixture'),
                       "coverage_note": checks.get('note', 'Bounded checks on configured pages. Not a full-site audit.')}
        elif run["kind"] == "incident":
            telemetry = tool("monitoring.metrics")
            logs = tool("splunk.summary")
            release = tool("cloud_manager.execution")
            revision = release.get('revision')
            assessment = "unconfirmed"
            details = {"root_cause": "unconfirmed", "telemetry": telemetry,
                       "patterns": logs.get('patterns', []), "correlation_is_causation": False}
        elif run['kind'] == 'security':
            sources = [tool(name) for name in ['snyk.findings', 'sonar.findings', 'github.review']]
            findings = [f for source in sources for f in source.get('findings', [])]
            assessment = 'inconclusive' if not all(s.get('complete') for s in sources) else 'needs_attention' if findings else 'no_findings'
            details = {'findings': sorted(findings, key=lambda x: {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}.get(x.get('severity'), 4)),
                       'by_severity': dict(Counter(f.get('severity', 'unknown') for f in findings)),
                       'source_coverage': [{k: s.get(k) for k in ['source', 'complete', 'coverage_note', 'quality_gate', 'reviewed_paths']} for s in sources],
                       'remediation': 'Review each finding, reproduce it, implement the smallest fix, and run project checks. No automatic source-code patch was made.'}
        elif run['kind'] == 'factory':
            bundle = tool('factory.render')
            assessment = 'proposal_ready' if bundle.get('files') else 'blocked'
            details = bundle
        elif run['kind'] == 'governance':
            impacted = tool('registry.impact')
            scope = impacted['site_ids']
            checks = tool('verification.results', scope) if scope else {'available': False, 'reason': 'site_registry_empty'}
            inheritance = tool('aem.governance', scope)
            findings = inheritance.get('findings', [])
            site_results = checks.get('sites', [])
            covered = {s.get('id') for s in site_results} == set(scope) and bool(scope) and all(
                type(s.get('total')) is int and s['total'] > 0 and type(s.get('passed')) is int and 0 <= s['passed'] <= s['total'] for s in site_results)
            complete = covered and len(site_results) == len(scope) and inheritance.get('complete', False) and set(inheritance.get('site_ids', [])) == set(scope)
            if self.settings.integration_mode == 'live':
                from datetime import datetime, timezone
                try:
                    age = (datetime.now(timezone.utc) - datetime.fromisoformat(checks['captured_at'])).total_seconds()
                    metadata_age = (datetime.now(timezone.utc) - datetime.fromisoformat(inheritance['captured_at'])).total_seconds()
                    complete = complete and -60 <= age <= 7200 and -60 <= metadata_age <= 7200 and checks.get('complete') is True and checks.get('environment') == request['environment']
                except (KeyError, ValueError, TypeError):
                    complete = False
            assessment = 'inconclusive' if not complete else 'needs_attention' if findings or any(s['passed'] != s['total'] for s in site_results) else 'no_findings'
            details = {'site_ids': scope, 'site_results': site_results, 'findings': findings, 'inheritance': inheritance,
                       'coverage_note': checks.get('note', 'Only configured pages and supported metadata are checked. Automated accessibility checks require human follow-up.')}
        else:
            data = tool("history.summary")
            details = {"run_count": len(data["runs"]), "by_status": dict(Counter(r["status"] for r in data["runs"])),
                       "source_run_ids": [r["id"] for r in data["runs"]], "window": data["window"]}
        missing = [{'tool': e['tool'], 'reason': e['data'].get('reason')} for e in collected if e['data'].get('available') is False]
        if missing:
            assessment = 'blocked' if all(e['data'].get('available') is False or e['source'] == 'registry' for e in collected) else 'inconclusive'
        details['missing_connections'] = missing
        with self.engine.begin() as conn:
            self.guarded(conn, run, "Preparing evidence-linked draft")
        narrative = self.provider.summarize(run["kind"], collected, assessment)
        result = {"assessment": assessment, "revision": revision, "environment": request["environment"],
                  "details": details, "narrative": narrative.model_dump(), "provider": self.provider.name,
                  "input_mode": self.settings.integration_mode, "evidence_ids": [e["id"] for e in collected]}
        return self.finish(run, result, collected, scope)

    def finish(self, run, result, collected, scope=None):
        scope = scope or []
        revision, request = result['revision'], run['request']
        markdown = self.make_report(run, result, collected)
        if run['kind'] in {'reporting', 'security'}:
            result['details']['files'] = [{'path': f'docs/agent-reports/{run["id"]}.md', 'content': markdown}]
        with self.engine.begin() as conn:
            self.guarded(conn, run, "Draft ready")
            status = 'blocked' if result['assessment'] == 'blocked' else "awaiting_review" if run["kind"] in {'release', 'factory'} else "draft_ready"
            conn.execute(update(db.runs).where(db.runs.c.id == run["id"]).values(
                status=status, result=result, owner=None, lease_until=None, updated_at=db.now()))
            conn.execute(db.reports.insert().values(id=db.uid("DOC"), run_id=run["id"],
                title=TITLES[run["kind"]], markdown=markdown, created_at=db.now()))
            if status == 'awaiting_review':
                payload = {"action": "accept_draft_only", "run_id": run["id"], "revision": revision,
                           "environment": request["environment"], "site_ids": scope,
                           "evidence_ids": result["evidence_ids"], "result_hash": db.digest(result)}
                conn.execute(db.approvals.insert().values(id=db.uid("APR"), run_id=run["id"],
                    title='Review ' + run['kind'] + ' dossier', payload=payload, digest=db.digest(payload), status="pending",
                    created_at=db.now(), expires_at=db.now(86400)))
            db.emit(conn, run["id"], run["kind"], "Draft ready for review", result['assessment'])

    def assess_checks(self, request, release, checks, scope):
        entries = checks.get('sites', [])
        valid = bool(scope) and len(entries) == len(scope) and {s.get('id') for s in entries} == set(scope)
        valid = valid and all(type(s.get('total')) is int and s['total'] > 0 and type(s.get('passed')) is int
                              and 0 <= s['passed'] <= s['total'] for s in entries)
        bound = bool(release.get('revision')) and checks.get('revision') == release.get('revision') and checks.get('environment') == request['environment'] and checks.get('execution_id') == release.get('execution_id')
        if self.settings.integration_mode == 'live':
            valid = valid and checks.get('complete') is True and release.get('deployment_completed') is True and checks.get('revision_verified') is True
            try:
                from datetime import datetime, timezone
                captured = datetime.fromisoformat(checks['captured_at'])
                age = (datetime.now(timezone.utc) - captured).total_seconds()
                deployed = datetime.fromisoformat(release['deployment_time'])
                valid = valid and -60 <= age <= 7200 and captured >= deployed
            except (KeyError, ValueError, TypeError):
                valid = False
        if not valid or not bound: return 'inconclusive'
        return 'failed' if any(s['passed'] != s['total'] for s in entries) else 'verified'

    def advance_missions(self):
        with self.engine.begin() as conn:
            waiting = db.rows(conn, select(db.runs).where(db.runs.c.status == 'waiting_children'))
            for parent in waiting:
                latest = conn.execute(select(db.runs.c.status).join(db.handoffs, db.handoffs.c.child_id == db.runs.c.id)
                    .where(db.handoffs.c.parent_id == parent['id']).order_by(db.handoffs.c.position.desc()).limit(1)).scalar_one_or_none()
                if latest in TERMINAL:
                    conn.execute(update(db.runs).where(db.runs.c.id == parent['id'], db.runs.c.status == 'waiting_children')
                        .values(status='queued', stage='Coordinating next specialist', updated_at=db.now()))

    def execute_mission(self, run):
        with self.engine.begin() as conn:
            self.guarded(conn, run, 'Coordinating specialist handoffs')
            children = db.rows(conn, select(db.runs).join(db.handoffs, db.handoffs.c.child_id == db.runs.c.id)
                .where(db.handoffs.c.parent_id == run['id']).order_by(db.handoffs.c.position))
            objective = run['request']['objective']
            plan = {'release-readiness': ['release', 'incident', 'reporting'], 'incident-investigation': ['incident', 'reporting'],
                    'site-onboarding': ['factory', 'reporting'], 'platform-health': ['security', 'governance', 'reporting']}[objective]
            if objective == 'release-readiness' and children and (children[0].get('result') or {}).get('assessment') == 'verified':
                plan.remove('incident')
            next_kind = next((k for k in plan if k not in [c['kind'] for c in children]), None)
            if next_kind:
                owner = conn.execute(select(db.owners.c.actor).where(db.owners.c.run_id == run['id'])).scalar_one_or_none() or 'local-operator'
                data = RunRequest.model_validate(run['request'] | {'kind': next_kind}).model_dump()
                child_id, position = db.uid('RUN'), len(children)
                conn.execute(db.runs.insert().values(id=child_id, key=f'mission:{run["id"]}:{position}', request_hash=db.digest(data), request=data,
                    kind=next_kind, status='queued', stage='Assigned by orchestrator', created_at=db.now(), updated_at=db.now(), attempts=0))
                conn.execute(db.owners.insert().values(run_id=child_id, actor=owner, parent_id=run['id']))
                conn.execute(db.handoffs.insert().values(id=f'{run["id"]}:{position}', parent_id=run['id'], position=position, child_id=child_id))
                conn.execute(update(db.runs).where(db.runs.c.id == run['id']).values(status='waiting_children', attempts=0,
                    stage='Waiting for ' + next_kind, owner=None, lease_until=None, updated_at=db.now()))
                db.emit(conn, run['id'], 'core', 'Specialist assigned', next_kind + ' → ' + child_id)
                db.record_audit(conn, 'handoff.created', 'agent:core', run['id'], {'child': child_id, 'kind': next_kind})
                return
            summary = [{'id': c['id'], 'kind': c['kind'], 'status': c['status'], 'assessment': (c.get('result') or {}).get('assessment'),
                        'result_hash': db.digest(c['result']) if c.get('result') else None} for c in children]
            evidence = {'id': db.uid('EV'), 'run_id': run['id'], 'tool': 'handoff.summary', 'source': 'local_database',
                        'captured_at': db.now(), 'digest': db.digest(summary), 'data': {'source': 'local_database', 'runs': summary}}
            evidence['digest'] = db.digest(evidence['data'])
            conn.execute(db.evidence.insert().values(**evidence))
        assessment = 'needs_attention' if any(c['status'] in {'failed', 'blocked', 'cancelled'} or c['assessment'] in {'failed', 'inconclusive', 'needs_attention'} for c in summary) else 'review_required'
        narrative = self.provider.summarize('core', [evidence], assessment)
        result = {'assessment': assessment, 'revision': None, 'environment': run['request']['environment'],
                  'details': {'objective': objective, 'handoffs': summary, 'missing_connections': []},
                  'narrative': narrative.model_dump(), 'provider': self.provider.name,
                  'input_mode': self.settings.integration_mode, 'evidence_ids': [evidence['id']]}
        self.finish(run, result, [evidence])

    def schedule_due(self):
        if time.monotonic() - self.last_schedule_check < 30:
            return
        self.last_schedule_check = time.monotonic()
        for schedule in self.settings.workspace.schedules:
            if not schedule.enabled:
                continue
            bucket = int(time.time()) // (schedule.interval_minutes * 60)
            try:
                self.submit(RunRequest(kind=schedule.kind, environment=schedule.environment, scope='shared', objective=schedule.objective),
                            f'schedule:{schedule.id}:{bucket}', 'schedule:' + schedule.id)
            except (Conflict, ValueError):
                continue

    @staticmethod
    def make_report(run, result, collected):
        lines = ["# " + TITLES[run["kind"]], "", "Run: " + run["id"],
                 "Environment: " + result["environment"], "Input data: " + ('synthetic fixtures' if result['input_mode'] == 'fixture' else 'configured live sources; unavailable sources are explicit'),
                 "Summary provider: " + result["provider"], "Assessment: " + result["assessment"],
                 "", "## Draft summary", result["narrative"]["summary"], "", "## Coverage and findings"]
        import json
        lines += ["```json", json.dumps(result["details"], indent=2), "```", "", "## Limitations"]
        lines += ["- " + x for x in result["narrative"]["limitations"]]
        if result["narrative"]["hypotheses"]:
            lines += ["", "## Hypotheses (unconfirmed)"] + ["- " + x for x in result["narrative"]["hypotheses"]]
        lines += ["", "## Evidence"]
        lines += [f"- {e['id']} | {e['tool']} | {e['source']} | {e['captured_at']} | SHA-256 {e['digest']}" for e in collected]
        lines += ["", "Accepting this draft does not deploy, publish, or change an external system. A pull request requires a separate exact-file proposal and approval."]
        return "\n".join(lines)

    def control(self, run_id, action, actor='local-operator'):
        with self.engine.begin() as conn:
            run = conn.execute(select(db.runs).where(db.runs.c.id == run_id)).mappings().first()
            if not run:
                raise NotFound()
            if action == "cancel":
                valid, status = ["queued", "running", 'waiting_children'], "cancelled"
            else:
                if run["attempts"] >= self.settings.max_attempts:
                    raise Conflict("Attempt limit reached; start a new run after addressing the failure")
                valid, status = ["failed", 'blocked'], "queued"
            changed = conn.execute(update(db.runs).where(db.runs.c.id == run_id,
                db.runs.c.status.in_(valid)).values(status=status, stage=status.replace("_", " "),
                owner=None, lease_until=None, error=None, updated_at=db.now())).rowcount
            if not changed:
                raise Conflict("The run has moved on; refresh its status")
            if action == 'retry':
                conn.execute(db.reports.delete().where(db.reports.c.run_id == run_id))
                conn.execute(db.approvals.delete().where(db.approvals.c.run_id == run_id))
                conn.execute(update(db.runs).where(db.runs.c.id == run_id).values(result=None))
            if action == 'cancel' and run['kind'] == 'core':
                child_ids = select(db.handoffs.c.child_id).where(db.handoffs.c.parent_id == run_id)
                conn.execute(update(db.runs).where(db.runs.c.id.in_(child_ids), db.runs.c.status.in_(['queued', 'running', 'waiting_children']))
                    .values(status='cancelled', owner=None, lease_until=None, stage='Mission cancelled', updated_at=db.now()))
            db.emit(conn, run_id, "core", "Run " + status)
            db.record_audit(conn, "run." + action, actor, run_id, {})

    def decide(self, approval_id, decision, actor='local-operator'):
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
                status=decision.decision, actor=actor, reason=decision.reason,
                decided_at=db.now())).rowcount
            if not changed:
                raise Conflict("A concurrent decision was recorded; refresh the page")
            conn.execute(update(db.runs).where(db.runs.c.id == proposal["run_id"]).values(
                status="reviewed", stage="Draft " + decision.decision, updated_at=db.now()))
            db.emit(conn, proposal["run_id"], "core", "Draft " + decision.decision, "Local review recorded; no deployment or publication triggered")
            db.record_audit(conn, "draft." + decision.decision, actor, approval_id,
                            {"digest": decision.digest, "reason": decision.reason})
        return {"status": decision.decision}
