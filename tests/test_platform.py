import json
from dataclasses import replace
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update, func
from aaaem.api import create_app
from aaaem.config import Settings
from aaaem import db
from aaaem.policy import ExecutionContext, PolicyDenied
from aaaem.service import LeaseLost
from aaaem.providers import BedrockProvider


@pytest.fixture
def settings(tmp_path):
    return Settings(database_url=f"sqlite:///{tmp_path / 'platform.db'}", allowed_hosts=("testserver",),
                    worker_enabled=False, step_delay=0)


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as client:
        yield client


def headers(client, key="request-0001"):
    return {"X-AAAEM-CSRF": client.get('/api/bootstrap').json()['csrf'], "Idempotency-Key": key}


def submit(client, **kwargs):
    response = client.post('/api/runs', json={"kind": "release", **kwargs}, headers=headers(client))
    assert response.status_code == 202, response.text
    return response.json()['id']


def complete(client, **kwargs):
    run_id = submit(client, **kwargs)
    assert client.app.state.platform.tick()
    detail = client.get('/api/runs/' + run_id).json()
    assert detail['run']['status'] != 'failed', detail
    return detail


def proposal(client):
    return client.get('/api/workspace').json()['approvals'][0]


def decide(client, item, **changes):
    return client.post('/api/approvals/' + item['id'] + '/decision',
                       headers=headers(client), json={"decision": "approved", "digest": item['digest'], **changes})


def test_local_boundary_and_validation(client):
    assert client.get('/healthz').status_code == 200
    assert client.post('/api/runs', json={"kind": "release"}).status_code == 403
    assert client.post('/api/runs', headers={**headers(client), "Origin": "https://evil.example"},
                       json={"kind": "release"}).status_code == 403
    assert client.post('/api/runs', headers=headers(client), json={"kind": "factory"}).status_code == 422
    assert client.post('/api/runs', headers=headers(client), json={"kind": "release", "role": "admin"}).status_code == 422
    assert client.get('/api/workspace', headers={"Host": "evil.example"}).status_code == 400


def test_idempotency_is_bound_to_exact_request(client):
    run_id = submit(client)
    replay = client.post('/api/runs', headers=headers(client), json={"kind": "release"})
    assert replay.status_code == 200 and replay.json()['id'] == run_id
    conflict = client.post('/api/runs', headers=headers(client), json={"kind": "incident"})
    assert conflict.status_code == 409
    assert len(client.get('/api/workspace').json()['runs']) == 1


def test_release_scope_evidence_and_report_are_persisted(client):
    detail = complete(client)
    result = detail['run']['result']
    assert result['assessment'] == 'verified'
    assert len(result['details']['site_ids']) == 14
    assert len(detail['evidence']) == 4
    assert all(db.digest(e['data']) == e['digest'] for e in detail['evidence'])
    assert set(result['narrative']['evidence_ids']) <= {e['id'] for e in detail['evidence']}
    report_id = client.get('/api/workspace').json()['reports'][0]['id']
    report = client.get('/api/reports/' + report_id + '?download=true')
    assert 'attachment;' in report.headers['content-disposition']
    assert 'Input data: synthetic fixtures' in report.text
    assert detail['evidence'][0]['id'] in report.text


@pytest.mark.parametrize('scenario,expected', [('degraded','failed'), ('incomplete','inconclusive')])
def test_missing_or_failing_checks_never_pass(client, scenario, expected):
    detail = complete(client, scenario=scenario)
    assert detail['run']['result']['assessment'] == expected


def test_wrong_revision_never_verifies(client):
    gateway = client.app.state.platform.gateway
    original = gateway.call
    def altered(context, tool, *args, **kwargs):
        data = original(context, tool, *args, **kwargs)
        if tool == 'verification.results': data['revision'] = 'stale-revision'
        return data
    gateway.call = altered
    assert complete(client)['run']['result']['assessment'] == 'inconclusive'


def test_unknown_dependencies_expand_coverage(client):
    result = complete(client, scope='unknown')['run']['result']
    assert len(result['details']['site_ids']) == 108
    assert result['details']['coverage_uncertain']


def test_incident_keeps_root_cause_unconfirmed(client):
    detail = complete(client, kind='incident', scenario='degraded')
    assert detail['run']['status'] == 'draft_ready'
    assert detail['run']['result']['details']['root_cause'] == 'unconfirmed'
    assert detail['run']['result']['details']['telemetry']['current_5xx_rate'] > 0.002
    assert not client.get('/api/workspace').json()['approvals']


def test_report_counts_actual_history(client):
    complete(client, kind='incident')
    response = client.post('/api/runs', headers=headers(client, 'request-0002'), json={"kind": "reporting"})
    client.app.state.platform.tick()
    result = client.get('/api/runs/' + response.json()['id']).json()['run']['result']
    assert result['details']['run_count'] == 1
    assert result['details']['by_status'] == {'draft_ready': 1}


def test_draft_review_is_idempotent_and_cannot_change_decision(client):
    complete(client)
    item = proposal(client)
    assert decide(client, item, digest='0'*64).status_code == 409
    assert decide(client, item, reason='Scope reviewed').status_code == 200
    assert decide(client, item).status_code == 200
    assert decide(client, item, decision='declined').status_code == 409
    entries = [e for e in client.get('/api/audit').json() if e['action'] == 'draft.approved']
    assert len(entries) == 1
    assert entries[0]['detail']['reason'] == 'Scope reviewed'
    assert item['payload']['action'] == 'accept_draft_only'


def test_expired_approval_is_rejected(client):
    complete(client)
    item = proposal(client)
    with client.app.state.engine.begin() as conn:
        conn.execute(update(db.approvals).values(expires_at=db.now(-10)))
    assert decide(client, item).status_code == 409
    assert proposal(client)['status'] == 'expired'


def test_changed_result_invalidates_approval(client):
    detail = complete(client)
    item = proposal(client)
    result = detail['run']['result']; result['revision'] = 'new-revision'
    with client.app.state.engine.begin() as conn:
        conn.execute(update(db.runs).values(result=result))
    assert decide(client, item).status_code == 409


def test_cancel_fences_running_worker(client):
    run_id = submit(client)
    platform = client.app.state.platform
    claimed = platform.claim()
    assert client.post('/api/runs/' + run_id + '/cancel', headers=headers(client), json={}).status_code == 200
    with pytest.raises(LeaseLost): platform.execute(claimed)
    detail = client.get('/api/runs/' + run_id).json()
    assert detail['run']['status'] == 'cancelled'
    assert not detail['evidence']
    assert not client.get('/api/workspace').json()['reports']


def test_expired_lease_recovery_and_stale_owner(client):
    run_id = submit(client)
    platform = client.app.state.platform
    old = platform.claim()
    with client.app.state.engine.begin() as conn:
        conn.execute(update(db.runs).values(lease_until=db.now(-10)))
    platform.recover()
    new = platform.claim()
    assert new['owner'] != old['owner']
    with pytest.raises(LeaseLost): platform.execute(old)
    platform.execute(new)
    assert client.get('/api/runs/' + run_id).json()['run']['attempts'] == 2
    assert len(client.get('/api/workspace').json()['reports']) == 1


def test_worker_failure_has_no_completed_artifacts_and_can_retry(client):
    run_id = submit(client)
    platform = client.app.state.platform
    original = platform.provider.summarize
    def fail(*args): raise ValueError('provider failure with private details')
    platform.provider.summarize = fail
    platform.tick()
    detail = client.get('/api/runs/' + run_id).json()
    assert detail['run']['status'] == 'failed'
    assert 'private details' not in detail['run']['error']
    assert not client.get('/api/workspace').json()['reports']
    platform.provider.summarize = original
    assert client.post('/api/runs/' + run_id + '/retry', headers=headers(client), json={}).status_code == 200
    platform.tick()
    assert client.get('/api/runs/' + run_id).json()['run']['status'] == 'awaiting_review'


def test_records_and_decisions_survive_application_restart(settings):
    with TestClient(create_app(settings)) as first:
        run_id = complete(first)['run']['id']
        item = proposal(first)
        assert decide(first, item, decision='declined', reason='More evidence required').status_code == 200
    with TestClient(create_app(settings)) as second:
        assert second.get('/api/runs/' + run_id).json()['run']['status'] == 'reviewed'
        assert proposal(second)['reason'] == 'More evidence required'
        assert len(second.get('/api/bootstrap').json()['sites']) == 108


def test_tools_cannot_escalate_agent_or_environment_scope(client):
    platform = client.app.state.platform
    with pytest.raises(PolicyDenied):
        platform.gateway.call(ExecutionContext('reporting','stage','test'), 'cloud_manager.execution',
                              {'environment':'stage'}, [])
    with pytest.raises(PolicyDenied):
        platform.gateway.call(ExecutionContext('release','stage','test'), 'cloud_manager.deploy',
                              {'environment':'stage'}, [])
    with pytest.raises(PolicyDenied):
        platform.gateway.call(ExecutionContext('release','stage','test'), 'cloud_manager.execution',
                              {'environment':'production'}, [])


def test_production_mode_fails_closed(settings):
    with pytest.raises(ValueError, match='Enterprise authentication'):
        create_app(replace(settings, mode='production'))


def test_bedrock_adapter_validates_evidence_citations():
    provider = BedrockProvider.__new__(BedrockProvider)
    provider.model_id = 'test-model'
    class FakeBedrock:
        def converse(self, **kwargs):
            return {'output': {'message': {'content': [{'text': json.dumps({
                'summary':'Draft', 'evidence_ids':['invented'], 'hypotheses':[], 'limitations':['Draft only']})}]}}}
    provider.client = FakeBedrock()
    with pytest.raises(ValueError, match='unknown evidence'):
        provider.summarize('incident', [{'id':'known'}], 'unconfirmed')


def test_reporting_does_not_cross_environment_scope(client):
    complete(client, kind='incident', environment='production')
    response = client.post('/api/runs', headers=headers(client, 'report-stage'),
                           json={'kind':'reporting','environment':'stage'})
    client.app.state.platform.tick()
    result = client.get('/api/runs/' + response.json()['id']).json()['run']['result']
    assert result['details']['run_count'] == 0
    assert result['details']['source_run_ids'] == []


def test_concurrent_workers_only_claim_one_owner(client):
    from concurrent.futures import ThreadPoolExecutor
    submit(client)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: client.app.state.platform.claim(), range(2)))
    assert len([r for r in results if r]) == 1


def test_attempt_limit_stops_recovery_loop(client):
    run_id = submit(client)
    platform = client.app.state.platform
    platform.claim()
    with client.app.state.engine.begin() as conn:
        conn.execute(update(db.runs).values(attempts=3, lease_until=db.now(-10)))
    platform.recover()
    assert platform.claim() is None
    assert client.get('/api/runs/' + run_id).json()['run']['status'] == 'failed'
    assert client.post('/api/runs/' + run_id + '/retry', headers=headers(client), json={}).status_code == 409


def test_background_worker_completes_an_api_submitted_run(settings):
    import time
    with TestClient(create_app(replace(settings, worker_enabled=True))) as client:
        run_id = submit(client, kind='incident')
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            result = client.get('/api/runs/' + run_id).json()['run']
            if result['status'] == 'draft_ready': break
            time.sleep(0.02)
        assert result['status'] == 'draft_ready'
        assert result['result']['evidence_ids']
