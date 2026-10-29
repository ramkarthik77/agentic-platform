"""Separate exact-file approval and idempotent draft-PR execution. No merge/deploy tools."""
from urllib.parse import quote
from sqlalchemy import select, update
from . import db
from .http import ConnectionProblem
from .setup import EnvironmentConfig, safe_path
from .service import Conflict, NotFound


class ChangeService:
    def __init__(self, platform):
        self.platform = platform
        self.engine, self.settings = platform.engine, platform.settings
        self.connections = platform.gateway.connections

    def target(self, env):
        return self.settings.workspace.environments.get(env, EnvironmentConfig()).pull_requests

    def propose(self, run_id, actor):
        with self.engine.connect() as conn:
            run = conn.execute(select(db.runs).where(db.runs.c.id == run_id)).mappings().first()
            existing = conn.execute(select(db.changes).where(db.changes.c.run_id == run_id)).mappings().first()
        if not run:
            raise NotFound()
        if existing:
            return dict(existing)
        result = run['result']
        if not result or run['status'] not in {'draft_ready', 'reviewed', 'awaiting_review'}:
            raise Conflict('Complete a workflow with generated files first')
        files = result['details'].get('files', [])
        if not files or len(files) > 30 or sum(len(f['content']) for f in files) > 500_000:
            raise Conflict('No bounded file bundle is available')
        for f in files:
            safe_path(f['path'])
        env, target = run['request']['environment'], self.target(run['request']['environment'])
        if self.settings.integration_mode == 'live':
            if not target or not target.enabled or not self.connections.configured(env, 'github'):
                raise Conflict('Configure and enable the GitHub PR target for this environment')
            if any(not any(f['path'].startswith(p) for p in target.allowed_prefixes) for f in files):
                raise Conflict('Generated files are outside the configured PR paths')
            if run['kind'] == 'factory' and not result['details'].get('templates_approved'):
                raise Conflict('Site templates must be reviewed before proposing a live PR')
            c = self.settings.workspace.connection(env, 'github')
            head = self.connections.get_json(c, '/repos/' + target.repository + '/git/ref/heads/' + quote(target.base_branch, safe=''))
            repository, branch, base_sha = target.repository, target.base_branch, head['object']['sha']
        else:
            repository, branch, base_sha = 'fixture/demo-repository', 'main', 'fixture-base'
        payload = {'action': 'create_draft_pull_request', 'input_mode': self.settings.integration_mode,
            'run_id': run_id, 'result_hash': db.digest(result), 'environment': env,
            'repository': repository, 'base_branch': branch, 'base_sha': base_sha, 'files': files,
            'title': 'AAAEM ' + run['kind'] + ' proposal — ' + run_id}
        item = {'id': db.uid('CHG'), 'run_id': run_id, 'environment': env, 'payload': payload,
            'digest': db.digest(payload), 'status': 'pending', 'created_at': db.now(),
            'expires_at': db.now(86400), 'proposed_by': actor}
        with self.engine.begin() as conn:
            current = conn.execute(select(db.runs.c.result).where(db.runs.c.id == run_id)).scalar_one()
            if db.digest(current) != payload['result_hash']:
                raise Conflict('Run changed while preparing the proposal')
            conn.execute(db.changes.insert().values(**item))
            db.record_audit(conn, 'change.proposed', actor, item['id'], {'digest': item['digest'], 'environment': env})
        return item

    def decision(self, change_id, body, actor):
        with self.engine.begin() as conn:
            item = conn.execute(select(db.changes).where(db.changes.c.id == change_id)).mappings().first()
            if not item: raise NotFound()
            if item['digest'] != body.digest or db.digest(item['payload']) != body.digest:
                raise Conflict('Review the current proposal digest')
            if item['status'] != 'pending':
                if item['status'] == body.decision: return {'status': item['status']}
                raise Conflict('A decision has already been recorded')
            if item['expires_at'] < db.now():
                raise Conflict('Proposal expired; start a fresh run')
            if self.settings.mode == 'production' and item['proposed_by'] == actor:
                raise Conflict('A different authorized reviewer must approve this change')
            current = conn.execute(select(db.runs.c.result).where(db.runs.c.id == item['run_id'])).scalar_one()
            if db.digest(current) != item['payload']['result_hash']:
                raise Conflict('Run evidence changed; create a fresh proposal')
            changed = conn.execute(update(db.changes).where(db.changes.c.id == change_id, db.changes.c.status == 'pending')
                .values(status=body.decision, reviewed_by=actor, reason=body.reason)).rowcount
            if changed != 1: raise Conflict('Concurrent review; refresh the proposal')
            db.record_audit(conn, 'change.' + body.decision, actor, change_id, {'digest': body.digest, 'environment': item['environment']})
        return {'status': body.decision}

    def execute(self, change_id, actor):
        owner = db.uid('write')
        with self.engine.begin() as conn:
            item = conn.execute(select(db.changes).where(db.changes.c.id == change_id)).mappings().first()
            if not item: raise NotFound()
            if item['status'] in {'succeeded', 'simulated'}: return dict(item)
            retryable = item['status'] in {'approved', 'unknown'} or item['status'] == 'executing' and item['lease_until'] < db.now()
            if not retryable or not item['reviewed_by']:
                raise Conflict('Approve the exact file proposal before execution')
            if item['expires_at'] < db.now() or item['digest'] != db.digest(item['payload']):
                raise Conflict('Proposal expired or changed')
            current = conn.execute(select(db.runs.c.result).where(db.runs.c.id == item['run_id'])).scalar_one()
            if db.digest(current) != item['payload']['result_hash']:
                raise Conflict('Run evidence changed')
            changed = conn.execute(update(db.changes).where(db.changes.c.id == change_id, db.changes.c.status == item['status'],
                db.changes.c.owner.is_(None) if item['owner'] is None else db.changes.c.owner == item['owner'])
                .values(status='executing', owner=owner, lease_until=db.now(600), error=None)).rowcount
            if changed != 1: raise Conflict('Another executor owns this proposal')
        try:
            if self.settings.integration_mode == 'fixture':
                result = {'simulated': True, 'message': 'Demo execution only; no GitHub branch or PR was created.'}
                status = 'simulated'
            else:
                result = self.publish(item)
                status = 'succeeded'
        except Exception as exc:
            with self.engine.begin() as conn:
                conn.execute(update(db.changes).where(db.changes.c.id == change_id, db.changes.c.owner == owner)
                    .values(status='unknown', owner=None, lease_until=None, error='Execution interrupted; reconcile before retry. ' + (exc.code if isinstance(exc, ConnectionProblem) else type(exc).__name__)))
                db.record_audit(conn, 'change.uncertain', actor, change_id, {'environment': item['environment']})
            raise Conflict('GitHub execution is uncertain. Retry uses the same branch and reconciles an existing PR.') from None
        with self.engine.begin() as conn:
            conn.execute(update(db.changes).where(db.changes.c.id == change_id, db.changes.c.owner == owner)
                .values(status=status, result=result, owner=None, lease_until=None))
            db.record_audit(conn, 'change.' + status, actor, change_id, {'digest': item['digest'], 'environment': item['environment']})
        return {'status': status, 'result': result}

    def publish(self, item):
        p, env = item['payload'], item['environment']
        c, target = self.settings.workspace.connection(env, 'github'), self.target(env)
        if not target or not target.enabled or target.repository != p['repository'] or target.base_branch != p['base_branch']:
            raise ConnectionProblem('target_configuration_changed')
        if any(not any(f['path'].startswith(prefix) for prefix in target.allowed_prefixes) for f in p['files']):
            raise ConnectionProblem('target_paths_changed')
        root, branch = '/repos/' + p['repository'], 'aaaem/' + item['id'].lower() + '-' + item['digest'][:12]
        owner = p['repository'].split('/')[0]
        def get(path, **kwargs): return self.connections.get_json(c, root + path, **kwargs)
        def post(path, data): return self.connections.http.json('POST', c.base_url + root + path,
                headers=self.connections.headers(c), json=data, timeout=c.timeout_seconds)
        existing = get('/pulls', params={'state': 'all', 'head': owner + ':' + branch, 'base': p['base_branch']})
        commit = get('/git/commits/' + p['base_sha'])
        tree = post('/git/trees', {'base_tree': commit['tree']['sha'],
            'tree': [{'path': f['path'], 'mode': '100644', 'type': 'blob', 'content': f['content']} for f in p['files']]})
        def matches_approval(sha):
            actual = get('/git/commits/' + sha)
            return (actual['tree']['sha'] == tree['sha'] and item['digest'] in actual['message']
                    and [parent['sha'] for parent in actual.get('parents', [])] == [p['base_sha']])
        if existing:
            pr = existing[0]
            if (item['digest'] not in pr.get('body', '') or pr.get('head', {}).get('ref') != branch
                    or pr.get('base', {}).get('ref') != p['base_branch']
                    or not matches_approval(pr['head']['sha'])):
                raise ConnectionProblem('existing_pr_does_not_match_approved_files')
            return {'url': pr['html_url'], 'number': pr['number'], 'branch': branch, 'reconciled': True}
        base = get('/git/ref/heads/' + quote(p['base_branch'], safe=''))
        if base['object']['sha'] != p['base_sha']:
            raise ConnectionProblem('base_revision_changed_new_proposal_required')
        try:
            ref = get('/git/ref/heads/' + quote(branch, safe=''))
            if not matches_approval(ref['object']['sha']):
                raise ConnectionProblem('existing_branch_does_not_match_approved_files')
        except ConnectionProblem as exc:
            if exc.code != 'upstream_http_404': raise
            created = post('/git/commits', {'message': p['title'] + '\n\nAAAEM proposal: ' + item['digest'],
                                          'tree': tree['sha'], 'parents': [p['base_sha']]})
            post('/git/refs', {'ref': 'refs/heads/' + branch, 'sha': created['sha']})
        pr = post('/pulls', {'title': p['title'], 'head': branch, 'base': p['base_branch'], 'draft': True,
            'body': 'Generated files approved in AAAEM.\n\nProposal digest: ' + item['digest'] + '\nRun: ' + p['run_id'] +
                    '\n\nReview and run repository-specific checks before merging. This PR does not provision or deploy the site.'})
        return {'url': pr['html_url'], 'number': pr['number'], 'branch': branch, 'reconciled': False}
