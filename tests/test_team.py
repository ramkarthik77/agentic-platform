import io
import json
import hmac
import hashlib
import time
import zipfile
from dataclasses import replace
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from aaaem.api import create_app
from aaaem.config import Settings
from aaaem.contracts import RunRequest
from aaaem import db
from aaaem.auth import Principal

SPEC={'slug':'demo-brand','brand':'Demo Brand','market':'US','locale':'en-US','domain':'demo-brand.example','theme':'standard'}
@pytest.fixture
def settings(tmp_path):
    return Settings(database_url=f'sqlite:///{tmp_path}/team.db',allowed_hosts=('testserver',),worker_enabled=False,step_delay=0)
@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as c: yield c

def headers(c,key='team-request-0001'):
    return {'X-AAAEM-CSRF':c.get('/api/bootstrap').json()['csrf'],'Idempotency-Key':key}
def run(c,kind,**kwargs):
    response=c.post('/api/runs',headers=headers(c,'team-'+str(time.time_ns())),json={'kind':kind,**kwargs})
    assert response.status_code==202,response.text
    rid=response.json()['id']
    for _ in range(20):
        c.app.state.platform.tick()
        detail=c.get('/api/runs/'+rid).json()
        if detail['run']['status'] not in {'queued','running','waiting_children'}:return detail
    pytest.fail('Workflow did not reach a terminal state')

@pytest.mark.parametrize('kind',['security','governance','factory','reporting'])
def test_all_specialists_produce_evidence_and_reports(client,kind):
    detail=run(client,kind,**({'site_spec':SPEC} if kind=='factory' else {}))
    assert detail['run']['status'] in {'draft_ready','awaiting_review'}
    assert detail['evidence'] and all(db.digest(e['data'])==e['digest'] for e in detail['evidence'])
    assert client.get('/api/workspace').json()['reports']

def test_factory_requires_explicit_safe_site_specification(client):
    bad=SPEC|{'slug':'../../secrets'}
    assert client.post('/api/runs',headers=headers(client),json={'kind':'factory','site_spec':bad}).status_code==422
    detail=run(client,'factory',site_spec=SPEC)
    response=client.get('/api/runs/'+detail['run']['id']+'/artifacts')
    archive=zipfile.ZipFile(io.BytesIO(response.content))
    assert len(archive.namelist())==6
    assert 'docs/sites/demo-brand/provisioning.json' in archive.namelist()
    plan=json.loads(archive.read('docs/sites/demo-brand/provisioning.json'))
    assert not plan['aem_write_executed'] and not plan['publishing_executed']

def test_release_mission_handoffs_depend_on_evidence(client):
    detail=run(client,'core',scenario='degraded')
    handoffs=detail['handoffs']
    children=[client.get('/api/runs/'+h['child_id']).json()['run'] for h in handoffs]
    assert [c['kind'] for c in children]==['release','incident','reporting']
    assert all(c['status'] in {'awaiting_review','draft_ready'} for c in children)
    assert detail['run']['result']['assessment']=='needs_attention'
    assert len({h['child_id'] for h in handoffs})==3

def test_healthy_release_mission_skips_unnecessary_investigation(client):
    detail=run(client,'core')
    assert [client.get('/api/runs/'+h['child_id']).json()['run']['kind'] for h in detail['handoffs']]==['release','reporting']

def test_mission_handoff_survives_restart(settings):
    with TestClient(create_app(settings)) as first:
        response=first.post('/api/runs',headers=headers(first),json={'kind':'core'})
        rid=response.json()['id'];first.app.state.platform.tick()
        assert first.get('/api/runs/'+rid).json()['run']['status']=='waiting_children'
    with TestClient(create_app(settings)) as second:
        for _ in range(10):second.app.state.platform.tick()
        detail=second.get('/api/runs/'+rid).json()
        assert detail['run']['status']=='draft_ready' and len(detail['handoffs'])==2

def test_cancel_mission_cancels_pending_child(client):
    rid=client.post('/api/runs',headers=headers(client),json={'kind':'core'}).json()['id']
    client.app.state.platform.tick()
    child=client.get('/api/runs/'+rid).json()['handoffs'][0]['child_id']
    assert client.post('/api/runs/'+rid+'/cancel',headers=headers(client),json={}).status_code==200
    assert client.get('/api/runs/'+child).json()['run']['status']=='cancelled'
    assert not client.app.state.platform.tick()

def test_pr_requires_separate_exact_file_approval(client):
    detail=run(client,'factory',site_spec=SPEC);rid=detail['run']['id']
    proposal=client.post('/api/runs/'+rid+'/propose-pr',headers=headers(client),json={}).json()
    base='/api/changes/'+proposal['id']
    assert client.post(base+'/execute',headers=headers(client),json={}).status_code==409
    assert client.post(base+'/decision',headers=headers(client),json={'decision':'approved','digest':'0'*64}).status_code==409
    assert client.post(base+'/decision',headers=headers(client),json={'decision':'approved','digest':proposal['digest']}).status_code==200
    done=client.post(base+'/execute',headers=headers(client),json={})
    assert done.status_code==200 and done.json()['status']=='simulated'
    replay=client.post(base+'/execute',headers=headers(client),json={})
    assert replay.json()['status']=='simulated'
    audits=client.get('/api/audit').json()
    assert len([a for a in audits if a['action']=='change.simulated'])==1

def test_stale_or_expired_change_cannot_execute(client):
    detail=run(client,'reporting');rid=detail['run']['id']
    proposal=client.post('/api/runs/'+rid+'/propose-pr',headers=headers(client),json={}).json()
    base='/api/changes/'+proposal['id']
    client.post(base+'/decision',headers=headers(client),json={'decision':'approved','digest':proposal['digest']})
    with client.app.state.engine.begin() as conn:conn.execute(update(db.changes).values(expires_at=db.now(-1)))
    assert client.post(base+'/execute',headers=headers(client),json={}).status_code==409

def test_missing_live_connections_never_fall_back_to_fixtures(settings):
    with TestClient(create_app(replace(settings,integration_mode='live'))) as c:
        detail=run(c,'release',scope='shared')
        assert detail['run']['status']=='blocked'
        assert detail['run']['result']['input_mode']=='live'
        assert all(e['source']!='fixture' for e in detail['evidence'])
        assert not c.get('/api/bootstrap').json()['sites']
        setup=c.get('/api/setup').json()
        assert all(x['status']=='not_configured' for x in setup['connections'])

def test_cannot_mix_live_and_fixture_database(settings):
    with TestClient(create_app(settings)):pass
    with pytest.raises(ValueError,match='separate database'):
        with TestClient(create_app(replace(settings,integration_mode='live'))):pass

def test_roles_and_environments_cannot_escalate(client):
    stage=run(client,'incident')['run']['id']
    prod=run(client,'incident',environment='production')['run']['id']
    actor=Principal('reader','Reader',({'roles':['reader'],'environments':['stage']},),'scoped-csrf')
    client.app.state.auth.principal=lambda request:actor
    bootstrap=client.get('/api/bootstrap').json()
    assert {r['id'] for r in bootstrap['runs']}=={stage}
    assert client.get('/api/runs/'+prod).status_code==403
    assert client.post('/api/runs',headers={'X-AAAEM-CSRF':actor.csrf,'Idempotency-Key':'readonly-run'},json={'kind':'incident'}).status_code==403
    assert client.get('/api/audit').status_code==403
    assert client.post('/api/connections/github/check',headers={'X-AAAEM-CSRF':actor.csrf},json={}).status_code==403

def test_group_roles_do_not_cross_environment_grants():
    actor=Principal('mixed','Mixed',({'roles':['admin'],'environments':['stage']},{'roles':['reader'],'environments':['production']}),'x')
    assert actor.allows('reader','production') and not actor.allows('operator','production')

def test_signed_intake_is_scoped_idempotent_and_replay_bounded(client,monkeypatch):
    key='x'*40;monkeypatch.setenv('AAAEM_INTAKE_SECRET',key)
    event={'event_id':'provider-123','source':'cloud_manager','request':{'kind':'core','environment':'stage'}}
    raw=json.dumps(event).encode();stamp=str(int(time.time()))
    signature=hmac.new(key.encode(),stamp.encode()+b'.'+raw,hashlib.sha256).hexdigest()
    hdr={'Content-Type':'application/json','X-AAAEM-Timestamp':stamp,'X-AAAEM-Signature':signature}
    first=client.post('/api/intake',content=raw,headers=hdr)
    second=client.post('/api/intake',content=raw,headers=hdr)
    assert first.status_code==202 and second.status_code==200 and first.json()['id']==second.json()['id']
    assert client.post('/api/intake',content=raw+b' ',headers=hdr).status_code==401
    assert client.post('/api/intake',content=raw,headers=hdr|{'X-AAAEM-Timestamp':'0'}).status_code==401

def test_schedule_bucket_is_idempotent(settings,tmp_path):
    config=tmp_path/'workspace.json'
    config.write_text(json.dumps({'schedules':[{'id':'brief','kind':'reporting','environment':'stage','interval_minutes':60,'enabled':True}]}))
    with TestClient(create_app(replace(settings,config_file=str(config)))) as c:
        p=c.app.state.platform;p.schedule_due();p.last_schedule_check=0;p.schedule_due()
        assert len(c.get('/api/workspace').json()['runs'])==1

def test_zero_checks_do_not_count_as_verification(client):
    p=client.app.state.platform
    request={'environment':'stage'}
    release={'revision':'abc','execution_id':'1'}
    checks={'revision':'abc','execution_id':'1','environment':'stage','sites':[{'id':1,'passed':0,'total':0}]}
    assert p.assess_checks(request,release,checks,[1])=='inconclusive'
