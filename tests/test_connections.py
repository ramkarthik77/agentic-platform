import json
from dataclasses import replace
from urllib.parse import parse_qs
import httpx
import pytest
from fastapi.testclient import TestClient
from aaaem import db
from aaaem.api import create_app
from aaaem.config import Settings
from aaaem.connections import Connections
from aaaem.contracts import RunRequest
from aaaem.http import Http, ConnectionProblem
from aaaem.setup import WorkspaceConfig
from aaaem.verifier import VerifySite, permitted_url


def connections(monkeypatch, name, driver=None, parameters=None, pages=2, handler=None):
    monkeypatch.setenv('TEST_TOKEN', 'test-token')
    conf=WorkspaceConfig.model_validate({'environments': {'stage': {'connections': {name: {
        'driver': driver or name, 'base_url': 'https://service.example', 'token_env': 'TEST_TOKEN',
        'parameters': parameters or {}, 'max_pages': pages}}}}})
    return Connections(Settings(integration_mode='live'), conf, Http(httpx.MockTransport(handler)))


def test_cloud_manager_rejects_wrong_execution_scope(monkeypatch):
    raw={'id':'44','programId':'7','pipelineId':'8','status':'FINISHED','commitId':'a'*40,
         'finishedAt':db.now(-60),'_embedded':{'stepStates':[{'environmentId':'9','status':'FINISHED'}]}}
    client=connections(monkeypatch,'cloud_manager',parameters={'program_id':'7','pipeline_id':'8','environment_id':'9'},handler=lambda r:httpx.Response(200,json=raw))
    request={'environment':'stage','execution_id':'44'}
    evidence=client.read('cloud_manager.execution',request,[])
    assert evidence['deployment_completed'] and evidence['revision']=='a'*40
    raw['pipelineId']='wrong'
    with pytest.raises(ConnectionProblem,match='execution_scope_mismatch'):client.read('cloud_manager.execution',request,[])


def test_snyk_paginates_on_trusted_host_and_exposes_truncation(monkeypatch):
    calls=[]
    def handle(r):
        calls.append(r)
        assert r.url.host=='service.example' and r.headers['Authorization']=='token test-token'
        if len(calls)==1:return httpx.Response(200,json={'data':[{'id':'1','attributes':{'title':'First','effective_severity_level':'high'}}], 'links':{'next':'https://untrusted.example/steal?starting_after=cursor-one'}})
        assert r.url.params['starting_after']=='cursor-one'
        return httpx.Response(200,json={'data':[{'id':'2','attributes':{'title':'Second'}}],'links':{}})
    c=connections(monkeypatch,'snyk',parameters={'organization_id':'org','api_version':'2024-10-15'},handler=handle)
    assert len(c.read('snyk.findings',{'environment':'stage'},[])['findings'])==2
    calls.clear()
    c.config.environments['stage'].connections['snyk'].max_pages=1
    assert c.read('snyk.findings',{'environment':'stage'},[])['complete'] is False


def test_sonar_failed_gate_is_a_finding_even_with_zero_issues(monkeypatch):
    c=connections(monkeypatch,'sonar',parameters={'project_key':'test'},handler=lambda r:httpx.Response(200,json=
        {'issues':[],'paging':{'total':0}} if r.url.path.endswith('/search') else {'projectStatus':{'status':'ERROR'}}))
    result=c.read('sonar.findings',{'environment':'stage'},[])
    assert result['complete'] and result['findings'][0]['id']=='sonar-quality-gate'


def test_splunk_read_query_summarizes_and_redacts(monkeypatch):
    def handle(r):
        query=parse_qs(r.content.decode())
        assert query['earliest_time']==['-30m']
        return httpx.Response(200,text=json.dumps({'result':{'pattern':'user=a@example.com token=abc123 failed','count':'8'}}))
    c=connections(monkeypatch,'splunk',parameters={'search':'search index=app | stats count by pattern'},handler=handle)
    result=c.read('splunk.summary',{'environment':'stage'},[])
    assert result['patterns']==[{'pattern':'user=[email] token=[redacted] failed','count':8}]
    c.config.environments['stage'].connections['splunk'].parameters['search']='search index=app | delete'
    with pytest.raises(ConnectionProblem,match='read_only'):c.read('splunk.summary',{'environment':'stage'},[])


def test_new_relic_binds_account_and_configured_query(monkeypatch):
    def handle(r):
        body=json.loads(r.content)
        assert body['variables']['account']==9 and r.headers['API-Key']=='test-token'
        return httpx.Response(200,json={'data':{'actor':{'account':{'nrql':{'results':[{'requests':100,'current_5xx_rate':0.2}]}}}}})
    c=connections(monkeypatch,'new_relic',parameters={'account_id':9,'nrql':'SELECT count(*) AS requests FROM Transaction SINCE 30 minutes ago'},handler=handle)
    assert c.read('monitoring.metrics',{'environment':'stage'},[])['requests']==100


@pytest.mark.parametrize('mutation',[{'environment':'production'},{'operation':'other'},{'data':{'source':'fixture'}}])
def test_bridge_rejects_scope_or_fixture_confusion(monkeypatch,mutation):
    response={'contract_version':1,'environment':'stage','operation':'aem.governance','data':{'findings':[]}}|mutation
    c=connections(monkeypatch,'aem','bridge',handler=lambda r:httpx.Response(200,json=response))
    with pytest.raises(ConnectionProblem):c.read('aem.governance',{'environment':'stage'},[])


def test_verifier_batches_and_renews_leases_without_inventing_revision_proof(monkeypatch):
    batches=[];checkpoints=[]
    def handle(r):
        body=json.loads(r.content);batches.append(body)
        return httpx.Response(200,json={k:body[k] for k in ['contract_version','environment','execution_id','revision']}|
            {'input_mode':'live','captured_at':db.now(),'complete':True,'sites':[{'id':s['id'],'passed':8,'total':8} for s in body['sites']]})
    c=connections(monkeypatch,'verification',handler=handle)
    sites=[{'id':i,'urls':{'stage':'https://brand.example'},'pages':['/']} for i in range(1,10)]
    result=c.read('verification.results',{'environment':'stage','execution_id':'44','_revision':'a'*40,'_checkpoint':lambda:checkpoints.append(1)},sites,list(range(1,10)))
    assert [len(b['sites']) for b in batches]==[4,4,1] and len(checkpoints)==3
    assert result['complete'] and result['revision_verified'] is False


def test_live_release_flow_requires_measured_revision_and_fresh_complete_evidence(tmp_path,monkeypatch):
    monkeypatch.setenv('TEST_TOKEN','test-token')
    registry=tmp_path/'registry.json';registry.write_text(json.dumps([{'id':1,'name':'Test','market':'US','theme':'standard','urls':{'stage':'https://brand.example'},'revision_header':'X-Revision'}]))
    config=tmp_path/'config.json'
    config.write_text(json.dumps({'registry_file':str(registry),'environments':{'stage':{'connections':{
        'cloud_manager':{'driver':'cloud_manager','base_url':'https://cm.example','token_env':'TEST_TOKEN','parameters':{'program_id':'7','pipeline_id':'8','environment_id':'9'}},
        'new_relic':{'driver':'new_relic','base_url':'https://nr.example','token_env':'TEST_TOKEN','parameters':{'account_id':9,'nrql':'SELECT count(*) AS requests FROM Transaction SINCE 30 minutes ago'}},
        'verification':{'driver':'verification','base_url':'https://verify.example','token_env':'TEST_TOKEN'}}}}}))
    settings=Settings(database_url=f'sqlite:///{tmp_path}/live.db',integration_mode='live',config_file=str(config),worker_enabled=False,step_delay=0,allowed_hosts=('testserver',))
    measured=True
    def handle(r):
        if r.url.host=='cm.example':return httpx.Response(200,json={'id':'44','programId':'7','pipelineId':'8','status':'FINISHED','commitId':'a'*40,'finishedAt':db.now(-60),'_embedded':{'stepStates':[{'environmentId':'9','status':'FINISHED'}]}})
        if r.url.host=='nr.example':return httpx.Response(200,json={'data':{'actor':{'account':{'nrql':{'results':[{'requests':100}]}}}}})
        body=json.loads(r.content)
        assert body['sites'][0]['revision_header']=='X-Revision'
        return httpx.Response(200,json={k:body[k] for k in ['contract_version','environment','execution_id','revision']}|
            {'input_mode':'live','complete':True,'revision_verified':measured,'captured_at':db.now(),'sites':[{'id':1,'passed':8,'total':8}]})
    with TestClient(create_app(settings)) as c:
        p=c.app.state.platform;p.gateway.connections.http=Http(httpx.MockTransport(handle))
        for expected in ['verified','inconclusive']:
            rid,_=p.submit(RunRequest(kind='release',scope='shared'),expected);p.tick()
            detail=c.get('/api/runs/'+rid).json()
            assert detail['run']['result']['assessment']==expected
            assert all(e['source']!='fixture' for e in detail['evidence'])
            measured=False


@pytest.mark.parametrize('url',['http://brand.example','https://brand.example:8080','https://brand.example@evil.example','https://brand.example:bad'])
def test_verification_rejects_non_allowed_origins(url):
    assert not permitted_url(url,{'brand.example'})


def test_verification_rejects_encoded_path_traversal():
    with pytest.raises(ValueError):VerifySite(id=1,url='https://brand.example',pages=['/%2e%2e/secrets'])


def test_transport_refuses_redirects_and_oversized_responses():
    redirect=Http(httpx.MockTransport(lambda r:httpx.Response(302,headers={'Location':'https://evil.example'})))
    with pytest.raises(ConnectionProblem,match='302'):redirect.json('GET','https://service.example')
    oversized=Http(httpx.MockTransport(lambda r:httpx.Response(200,content=b'x'*100)))
    with pytest.raises(ConnectionProblem,match='limit'):oversized.request('GET','https://service.example',limit=10)
