"""Native read adapters and a versioned bridge contract for organization-specific AEM APIs."""
import json
import re
import time
from datetime import datetime, timezone
from urllib.parse import quote, urlsplit
from . import db
from .http import Http, ConnectionProblem
from .setup import secret

NAMES = {'cloud_manager': 'Cloud Manager', 'new_relic': 'New Relic', 'splunk': 'Splunk',
         'snyk': 'Snyk', 'sonar': 'Sonar', 'github': 'GitHub', 'aem': 'AEM metadata', 'verification': 'Site verification'}
REQUIRED = {'cloud_manager': ['program_id', 'pipeline_id', 'environment_id'], 'new_relic': ['account_id', 'nrql'],
            'splunk': ['search'], 'snyk': ['organization_id', 'api_version'], 'sonar': ['project_key'],
            'github': ['repository'], 'bridge': [], 'verification': []}
TOOL_CONNECTION = {'cloud_manager.execution': 'cloud_manager', 'monitoring.metrics': 'new_relic',
                   'splunk.summary': 'splunk', 'snyk.findings': 'snyk', 'sonar.findings': 'sonar',
                   'github.review': 'github', 'aem.governance': 'aem', 'verification.results': 'verification'}


def redacted(text):
    value = str(text)[:2000]
    value = re.sub(r'(?i)(bearer\s+|(?:token|password|secret|authorization)\s*[:=]\s*)[^\s,;]+', r'\1[redacted]', value)
    value = re.sub(r'[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}', '[email]', value, flags=re.I)
    return value


class Connections:
    def __init__(self, settings, config=None, http=None):
        self.settings, self.config = settings, config or settings.workspace
        self.http = http or Http()
        self._tokens = {}

    def readiness(self, environment):
        rows = []
        for key, label in NAMES.items():
            c = self.config.connection(environment, key)
            missing = []
            if c.driver == 'disabled':
                missing.append('driver')
            if not c.base_url:
                missing.append('base_url')
            refs = [c.token_env] + list(c.header_env.values())
            for ref in refs:
                if ref and not secret(ref):
                    missing.append(ref)
            oauth = c.parameters.get('oauth')
            if oauth:
                for key_name in ['client_id_env', 'client_secret_env']:
                    if not secret(oauth.get(key_name, '')):
                        missing.append(oauth.get(key_name) or 'oauth.' + key_name)
                if not oauth.get('token_endpoint') or not oauth.get('scopes'):
                    missing.append('oauth.token_endpoint/scopes')
            elif c.driver != 'disabled' and not c.token_env:
                missing.append('token_env')
            for param in REQUIRED.get(c.driver, []):
                if not c.parameters.get(param):
                    missing.append('parameters.' + param)
            rows.append({'id': key, 'name': label, 'driver': c.driver, 'environment': environment,
                         'status': 'fixture' if self.settings.integration_mode == 'fixture' else 'configured' if not missing else 'not_configured',
                         'missing': missing, 'host': urlsplit(c.base_url).hostname,
                         'note': 'Configuration present; use Check connection to validate access.' if not missing else 'Complete the server-side setup.'})
        return rows

    def configured(self, env, name):
        return not next(x for x in self.readiness(env) if x['id'] == name)['missing']

    def headers(self, c):
        result = {k: secret(v) for k, v in c.header_env.items()}
        oauth = c.parameters.get('oauth')
        token = secret(c.token_env)
        if oauth:
            from .setup import endpoint
            token_url = endpoint(oauth['token_endpoint'])
            key = db.digest(oauth)
            cached = self._tokens.get(key)
            if cached and cached[1] > time.time():
                token = cached[0]
            else:
                response = self.http.json('POST', token_url, timeout=c.timeout_seconds,
                    data={'grant_type': 'client_credentials', 'client_id': secret(oauth['client_id_env']),
                          'client_secret': secret(oauth['client_secret_env']), 'scope': oauth['scopes']})
                token = response.get('access_token', '')
                if not token:
                    raise ConnectionProblem('oauth_token_missing')
                self._tokens[key] = (token, time.time() + max(1, min(int(response.get('expires_in', 300)), 86400) - 60))
        if not token:
            raise ConnectionProblem('not_configured')
        if c.driver == 'new_relic':
            result['API-Key'] = token
        else:
            prefix = 'token' if c.driver == 'snyk' else 'Bearer'
            result['Authorization'] = prefix + ' ' + token
        result['Accept'] = 'application/json'
        return result

    def get_json(self, c, path, **kwargs):
        if not path.startswith('/') or path.startswith('//') or '..' in path.split('/'):
            raise ConnectionProblem('invalid_adapter_path')
        return self.http.json('GET', c.base_url + path, headers=self.headers(c), timeout=c.timeout_seconds, **kwargs)

    def read(self, tool, request, sites, selected=None):
        name = TOOL_CONNECTION[tool]
        env = request['environment']
        c = self.config.connection(env, name)
        if not self.configured(env, name):
            raise ConnectionProblem('not_configured')
        if c.driver == 'bridge':
            payload = {'contract_version': 1, 'operation': tool, 'environment': env,
                       'execution_id': request.get('execution_id', ''), 'site_ids': selected or request.get('site_ids', []),
                       'sites': [{k: s.get(k) for k in ['id', 'content_root', 'inheritance_exceptions']} for s in sites
                                 if s['id'] in (selected or request.get('site_ids', []))]}
            result = self.http.json('POST', c.base_url + '/v1/read', headers=self.headers(c), json=payload, timeout=c.timeout_seconds)
            if result.get('contract_version') != 1 or result.get('environment') != env or result.get('operation') != tool:
                raise ConnectionProblem('bridge_scope_mismatch')
            data = result.get('data')
            if not isinstance(data, dict):
                raise ConnectionProblem('invalid_bridge_data')
            if data.get('source') == 'fixture' or data.get('input_mode') == 'fixture':
                raise ConnectionProblem('fixture_data_rejected_in_live_mode')
        else:
            method = getattr(self, c.driver, None)
            if method is None:
                raise ConnectionProblem('driver_not_supported')
            data = method(c, request, sites, selected)
        return {**data, 'source': 'live:' + name, 'available': True}

    def cloud_manager(self, c, request, sites, selected):
        p = c.parameters
        program, pipeline = quote(str(p['program_id']), safe=''), quote(str(p['pipeline_id']), safe='')
        execution = request.get('execution_id')
        path = f'/api/program/{program}/pipeline/{pipeline}/execution' + ('/' + quote(execution, safe='') if execution else '')
        raw = self.get_json(c, path)
        if str(raw.get('pipelineId')) != str(p['pipeline_id']) or str(raw.get('programId')) != str(p['program_id']):
            raise ConnectionProblem('execution_scope_mismatch')
        if execution and str(raw.get('id')) != execution:
            raise ConnectionProblem('execution_id_mismatch')
        steps = raw.get('_embedded', {}).get('stepStates', [])
        target = [s for s in steps if str(s.get('environmentId')) == str(p['environment_id'])]
        revisions = set()
        def collect(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k in {'commitId', 'commitHash'} and isinstance(v, str) and re.fullmatch('[a-fA-F0-9]{7,64}', v):
                        revisions.add(v)
                    elif isinstance(v, (dict, list)):
                        collect(v)
            elif isinstance(obj, list):
                for v in obj: collect(v)
        collect(raw)
        revision = next(iter(revisions)) if len(revisions) == 1 else None
        return {'execution_id': str(raw['id']), 'revision': revision, 'environment': request['environment'],
                'pipeline_status': raw.get('status', 'UNKNOWN'), 'deployment_time': raw.get('finishedAt'),
                'environment_verified': bool(target), 'deployment_completed': raw.get('status') == 'FINISHED' and bool(target)
                    and all(s.get('status') == 'FINISHED' for s in target),
                'revision_note': 'Revision is inconclusive unless the API provides one unambiguous commit ID.'}

    def new_relic(self, c, request, sites, selected):
        p = c.parameters
        query = str(p['nrql'])
        if not re.match(r'^\s*(SELECT|FROM)\b', query, re.I) or not re.search(r'\bSINCE\b', query, re.I):
            raise ConnectionProblem('configure_bounded_nrql')
        account = int(p['account_id'])
        graphql = 'query($account: Int!, $nrql: Nrql!) { actor { account(id: $account) { nrql(query: $nrql) { results } } } }'
        raw = self.http.json('POST', c.base_url, headers=self.headers(c), timeout=c.timeout_seconds,
                             json={'query': graphql, 'variables': {'account': account, 'nrql': query}})
        if raw.get('errors'):
            raise ConnectionProblem('nrql_query_rejected')
        rows = raw['data']['actor']['account']['nrql']['results']
        if not rows or len(rows) > 100:
            raise ConnectionProblem('nrql_result_count_invalid')
        # Administrators provide queries with these aliases. Never invent missing measurements.
        result = {k: rows[0].get(k) for k in ['requests', 'baseline_5xx_rate', 'current_5xx_rate', 'p95_ms']}
        if not any(v is not None for v in result.values()):
            raise ConnectionProblem('nrql_aliases_missing')
        return {**result, 'window_minutes': p.get('window_minutes', 30), 'query_configured': True}

    def splunk(self, c, request, sites, selected):
        search = str(c.parameters['search'])
        # This is a configured read search, never model-generated SPL. Deny known write commands as defense in depth.
        if not re.match(r'^\s*search\b', search, re.I) or re.search(r'\|\s*(outputlookup|outputcsv|collect|mcollect|sendemail|script|run|delete|rest)\b', search, re.I):
            raise ConnectionProblem('configure_read_only_splunk_search')
        raw = self.http.request('POST', c.base_url + '/services/search/v2/jobs/export', headers=self.headers(c),
            timeout=c.timeout_seconds, data={'search': search, 'output_mode': 'json', 'earliest_time': '-30m', 'latest_time': 'now'})
        patterns = []
        for line in raw.decode().splitlines():
            item = json.loads(line)
            if item.get('preview'):
                continue
            row = item.get('result')
            if row:
                if 'pattern' not in row or 'count' not in row:
                    raise ConnectionProblem('splunk_summary_aliases_missing')
                patterns.append({'pattern': redacted(row['pattern']), 'count': int(row['count'])})
                if len(patterns) > 100:
                    raise ConnectionProblem('splunk_summary_limit_exceeded')
        return {'patterns': patterns, 'window_minutes': 30, 'redacted': True, 'query': 'configured-summary-query'}

    def snyk(self, c, request, sites, selected):
        p = c.parameters
        path = '/orgs/' + quote(str(p['organization_id']), safe='') + '/issues'
        findings, cursor, complete = [], None, False
        for _ in range(c.max_pages):
            if request.get('_checkpoint'): request['_checkpoint']()
            params = {'version': p['api_version'], 'limit': 100}
            if cursor: params['starting_after'] = cursor
            raw = self.get_json(c, path, params=params)
            if not isinstance(raw.get('data'), list):
                raise ConnectionProblem('invalid_snyk_contract')
            for row in raw.get('data', []):
                a = row.get('attributes', {})
                findings.append({'id': str(row['id']), 'provider': 'snyk',
                    'title': redacted(a.get('title', 'Snyk finding')), 'severity': a.get('effective_severity_level', 'unknown'),
                    'status': a.get('status', 'unknown'), 'fix_available': a.get('resolveable', False)})
            nxt = raw.get('links', {}).get('next')
            if not nxt:
                complete = True; break
            # Follow only the pagination cursor, never an upstream-controlled URL.
            from urllib.parse import parse_qs
            cursor = parse_qs(urlsplit(nxt).query).get('starting_after', [None])[0]
            if not cursor:
                break
        return {'findings': findings, 'complete': complete, 'coverage_note': 'Organization issues; pagination is bounded.'}

    def sonar(self, c, request, sites, selected):
        findings, complete = [], False
        for page in range(1, c.max_pages + 1):
            if request.get('_checkpoint'): request['_checkpoint']()
            raw = self.get_json(c, '/api/issues/search', params={'componentKeys': c.parameters['project_key'],
                'resolved': 'false', 'p': page, 'ps': 100})
            for row in raw.get('issues', []):
                findings.append({'id': row['key'], 'provider': 'sonar', 'title': redacted(row.get('message', 'Sonar issue')),
                    'severity': {'BLOCKER': 'critical', 'CRITICAL': 'high', 'MAJOR': 'medium', 'MINOR': 'low', 'INFO': 'info'}.get(row.get('severity'), 'unknown'), 'rule': row.get('rule'),
                    'component': row.get('component'), 'line': row.get('line'), 'status': row.get('status')})
            total = raw.get('paging', {}).get('total', raw.get('total'))
            if total is not None and len(findings) >= total:
                complete = True; break
            if not raw.get('issues'): break
        gate = self.get_json(c, '/api/qualitygates/project_status', params={'projectKey': c.parameters['project_key']})
        gate_status = gate.get('projectStatus', {}).get('status', 'UNKNOWN')
        if gate_status == 'ERROR':
            findings.append({'id': 'sonar-quality-gate', 'provider': 'sonar', 'title': 'Sonar quality gate failed', 'severity': 'high'})
        return {'findings': findings, 'complete': complete and gate_status in {'OK', 'ERROR'}, 'quality_gate': gate_status}

    def github(self, c, request, sites, selected):
        repository = c.parameters['repository']
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
            raise ConnectionProblem('invalid_repository')
        info = self.get_json(c, '/repos/' + repository)
        branch = str(c.parameters.get('branch') or info['default_branch'])
        head = self.get_json(c, '/repos/' + repository + '/commits/' + quote(branch, safe=''))
        findings, reviewed = [], []
        paths = c.parameters.get('review_paths', [])
        if not isinstance(paths, list) or len(paths) > 20:
            raise ConnectionProblem('review_path_limit_exceeded')
        import base64
        from .setup import safe_path
        for path in paths:
            if request.get('_checkpoint'): request['_checkpoint']()
            safe_path(path)
            raw = self.get_json(c, '/repos/' + repository + '/contents/' + quote(path, safe='/'), params={'ref': head['sha']})
            if raw.get('encoding') != 'base64' or raw.get('size', 0) > 100_000:
                raise ConnectionProblem('review_file_limit_exceeded')
            text = base64.b64decode(raw['content']).decode('utf-8')
            reviewed.append(path)
            checks = [(r'getAdministrativeResourceResolver\s*\(', 'Deprecated administrative resource resolver', 'high'),
                      (r'(?s)/type\s*"allow"[^{}]{0,300}/url\s*"\*"', 'Broad Dispatcher allow rule requires review', 'high'),
                      (r'Access-Control-Allow-Origin[^\n]{0,80}\*', 'Wildcard CORS origin requires review', 'medium')]
            for pattern, title, severity in checks:
                for match in re.finditer(pattern, text):
                    findings.append({'id': db.digest([path, pattern, match.start()])[:20], 'provider': 'aem-baseline',
                                     'title': title, 'severity': severity, 'path': path,
                                     'line': text[:match.start()].count('\n') + 1})
        return {'repository': repository, 'revision': head['sha'], 'findings': findings, 'reviewed_paths': reviewed,
                'complete': bool(paths), 'coverage_note': 'Configured files and three heuristic rules; manual review remains necessary.'}

    def verification(self, c, request, sites, selected):
        scoped = [s for s in sites if s['id'] in (selected or [])]
        payload = {'contract_version': 1, 'environment': request['environment'], 'execution_id': request.get('execution_id', ''),
                   'revision': request.get('_revision'), 'sites': [{'id': s['id'], 'url': s.get('urls', {}).get(request['environment']),
                       'pages': s.get('pages', ['/']), 'revision_header': s.get('revision_header', '')} for s in scoped]}
        if not scoped or any(not s['url'] for s in payload['sites']):
            raise ConnectionProblem('site_environment_url_missing')
        if len(scoped) > 250:
            raise ConnectionProblem('verification_site_limit_exceeded')
        batches, collected = [], []
        for start in range(0, len(scoped), 4):
            if request.get('_checkpoint'): request['_checkpoint']()
            result = self.http.json('POST', c.base_url + '/v1/verify', headers=self.headers(c),
                json=payload | {'sites': payload['sites'][start:start+4]}, timeout=c.timeout_seconds)
            if (result.get('contract_version') != 1 or result.get('input_mode') != 'live'
                    or result.get('environment') != request['environment'] or result.get('execution_id') != payload['execution_id']
                    or result.get('revision') != payload['revision']):
                raise ConnectionProblem('verification_scope_mismatch')
            batches.append(result)
            collected.extend(result.get('sites', []))
        return {'contract_version': 1, 'input_mode': 'live', 'environment': request['environment'],
                'execution_id': payload['execution_id'], 'revision': payload['revision'], 'sites': collected,
                'complete': all(b.get('complete') is True for b in batches),
                'revision_verified': all(b.get('revision_verified') is True for b in batches),
                'captured_at': min(b['captured_at'] for b in batches),
                'note': 'Chromium checks on configured pages. Link checks are sampled. No form submissions or full accessibility certification.'}

    def check(self, environment, name):
        if name not in NAMES:
            raise ConnectionProblem('unknown_connection')
        if self.settings.integration_mode == 'fixture':
            return {'status': 'fixture', 'message': 'Synthetic data mode; no live request was sent.', 'checked_at': db.now()}
        if not self.configured(environment, name):
            return {'status': 'not_configured', 'checked_at': db.now()}
        c = self.config.connection(environment, name)
        try:
            if c.driver in {'bridge', 'verification'}:
                self.get_json(c, '/healthz')
            elif c.driver == 'github':
                self.get_json(c, '/repos/' + c.parameters['repository'])
            elif c.driver == 'cloud_manager':
                self.get_json(c, '/api/program/' + quote(str(c.parameters['program_id']), safe='') + '/pipeline/' + quote(str(c.parameters['pipeline_id']), safe=''))
            elif c.driver == 'sonar':
                if self.get_json(c, '/api/authentication/validate').get('valid') is not True:
                    raise ConnectionProblem('credentials_or_scope_rejected')
            elif c.driver == 'snyk':
                self.get_json(c, '/orgs/' + quote(str(c.parameters['organization_id']), safe='') + '/issues', params={'version': c.parameters['api_version'], 'limit': 1})
            else:
                self.read('monitoring.metrics' if c.driver == 'new_relic' else 'splunk.summary', {'environment': environment}, [])
            return {'status': 'reachable', 'message': 'Read probe succeeded. Validate an actual workflow before enabling schedules.', 'checked_at': db.now()}
        except ConnectionProblem as exc:
            return {'status': 'error', 'message': exc.code, 'checked_at': db.now()}
