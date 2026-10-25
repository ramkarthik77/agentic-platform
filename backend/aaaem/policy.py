from dataclasses import dataclass
from . import fixtures

ALLOWED = {
    "release": {"cloud_manager.execution", "registry.impact", "verification.results", "monitoring.metrics"},
    "incident": {"cloud_manager.execution", "monitoring.metrics", "splunk.summary"},
    "reporting": {"history.summary"},
}


class PolicyDenied(Exception):
    pass


@dataclass(frozen=True)
class ExecutionContext:
    """Constructed by the worker from persisted validated input, never from a model reply."""
    agent: str
    environment: str
    run_id: str


class ToolGateway:
    def call(self, context, tool, request, sites, history=None, selected=None):
        if tool not in ALLOWED.get(context.agent, set()):
            raise PolicyDenied("Tool is outside this agent's Phase 1 read scope")
        if request["environment"] != context.environment:
            raise PolicyDenied("Environment does not match the trusted execution context")
        if tool == "cloud_manager.execution":
            return fixtures.execution(request)
        if tool == "registry.impact":
            return fixtures.impact(request, sites)
        if tool == "verification.results":
            known = {s["id"] for s in sites}
            if not selected or not set(selected).issubset(known):
                raise PolicyDenied("Verification scope is not registered")
            return fixtures.verification(request, selected)
        if tool == "monitoring.metrics":
            return fixtures.metrics(request)
        if tool == "splunk.summary":
            return fixtures.logs(request)
        return {"source": "local_database", "runs": history or [], "window": "Last 100 runs"}
