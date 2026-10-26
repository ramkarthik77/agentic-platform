from dataclasses import dataclass
from . import fixtures
from .connections import Connections

ALLOWED = {
    "release": {"cloud_manager.execution", "registry.impact", "verification.results", "monitoring.metrics"},
    "incident": {"cloud_manager.execution", "monitoring.metrics", "splunk.summary"},
    "reporting": {"history.summary"},
    "security": {"snyk.findings", "sonar.findings", "github.review"},
    "governance": {"registry.impact", "verification.results", "aem.governance"},
    "factory": {"factory.render"},
    "core": {"handoff.summary"},
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
    def __init__(self, settings=None):
        from .config import Settings
        self.settings = settings or Settings()
        self.connections = Connections(self.settings)

    def call(self, context, tool, request, sites, history=None, selected=None):
        if tool not in ALLOWED.get(context.agent, set()):
            raise PolicyDenied("Tool is outside this agent's scope")
        if request["environment"] != context.environment:
            raise PolicyDenied("Environment does not match the trusted execution context")
        if tool == 'history.summary' or tool == 'handoff.summary':
            return {'source': 'local_database', 'runs': history or [], 'window': 'Last 100 runs'}
        if tool == 'factory.render':
            from .factory import render_site
            return render_site(request, self.settings)
        if tool == 'registry.impact' and self.settings.integration_mode == 'live':
            available = [s for s in sites if request['environment'] in s.get('urls', {})]
            known = {s['id'] for s in available}
            requested = set(request.get('site_ids', []))
            if requested and not requested.issubset(known):
                raise PolicyDenied('Selected sites are not registered for this environment')
            ids = sorted(requested) if request.get('scope') == 'selected' else sorted(known)
            return {'source': 'registry', 'site_ids': ids, 'coverage_uncertain': True,
                    'reason': 'Explicitly selected sites; impact is not proven' if requested else 'All registered environment sites; dependency mapping is not yet proven'}
        if tool == 'verification.results':
            known = {s['id'] for s in sites}
            if not selected or not set(selected).issubset(known):
                raise PolicyDenied('Verification scope is not registered')
        if self.settings.integration_mode == 'live':
            return self.connections.read(tool, request, sites, selected)
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
        if tool in {'snyk.findings', 'sonar.findings', 'github.review'}:
            return fixtures.findings(request, tool)
        if tool == 'aem.governance':
            return fixtures.governance(request, selected or [])
        raise PolicyDenied('Tool has no implementation')
