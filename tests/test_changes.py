import json
from types import SimpleNamespace
import httpx
import pytest
from aaaem import db
from aaaem.changes import ChangeService
from aaaem.config import Settings
from aaaem.connections import Connections
from aaaem.http import Http, ConnectionProblem
from aaaem.setup import WorkspaceConfig


@pytest.fixture
def github(monkeypatch,tmp_path):
    monkeypatch.setenv('TEST_TOKEN','test-token')
    config=tmp_path/'workspace.json'
    config.write_text(json.dumps({'environments':{'stage':{'connections':{'github':{
        'driver':'github','base_url':'https://api.github.com','token_env':'TEST_TOKEN','parameters':{'repository':'example/platform'}}},
        'pull_requests':{'repository':'example/platform','allowed_prefixes':['docs/agent-reports/'],'enabled':True}}}}))
    settings=Settings(config_file=str(config),integration_mode='live')
    connections=Connections(settings)
    service=ChangeService(SimpleNamespace(engine=None,settings=settings,gateway=SimpleNamespace(connections=connections)))
    payload={'environment':'stage','repository':'example/platform','base_branch':'main','base_sha':'base',
             'title':'Test report','run_id':'RUN-test','files':[{'path':'docs/agent-reports/test.md','content':'# Reviewed report'}]}
    item={'id':'CHG-test','environment':'stage','payload':payload,'digest':db.digest(payload)}
    state={'base':'base','ref':None,'pr':None,'commit':None,'writes':[],'fail_pr_response':False}
    def handle(r):
        assert r.headers['Authorization']=='Bearer test-token'
        path=r.url.path.removeprefix('/repos/example/platform')
        data=json.loads(r.content) if r.method=='POST' else None
        if r.method=='GET':
            if path=='/pulls':return httpx.Response(200,json=[state['pr']] if state['pr'] else [])
            if path=='/git/ref/heads/main':return httpx.Response(200,json={'object':{'sha':state['base']}})
            if path=='/git/commits/base':return httpx.Response(200,json={'tree':{'sha':'base-tree'}})
            if path.startswith('/git/ref/heads/aaaem/'):
                return httpx.Response(200,json={'object':{'sha':'approved-commit'}}) if state['ref'] else httpx.Response(404)
            if path=='/git/commits/approved-commit':return httpx.Response(200,json=state['commit'])
        else:
            state['writes'].append(path)
            if path=='/git/trees':
                assert data['base_tree']=='base-tree' and data['tree'][0]['content']=='# Reviewed report'
                return httpx.Response(201,json={'sha':'approved-tree'})
            if path=='/git/commits':
                state['commit']={'tree':{'sha':data['tree']},'message':data['message'],'parents':[{'sha':p} for p in data['parents']]}
                return httpx.Response(201,json={'sha':'approved-commit'})
            if path=='/git/refs':state['ref']=data['ref'];return httpx.Response(201,json={})
            if path=='/pulls':
                assert data['draft'] is True
                state['pr']={'number':1,'html_url':'https://github.com/example/platform/pull/1','body':data['body'],
                             'head':{'ref':data['head'],'sha':'approved-commit'},'base':{'ref':'main'}}
                if state['fail_pr_response']:raise httpx.ReadTimeout('test response lost')
                return httpx.Response(201,json=state['pr'])
        raise AssertionError(f'Unexpected request {r.method} {path}')
    connections.http=Http(httpx.MockTransport(handle))
    return service,item,state


def test_exact_file_draft_pr_is_reconciled_after_response_loss(github):
    service,item,state=github;state['fail_pr_response']=True
    with pytest.raises(ConnectionProblem):service.publish(item)
    result=service.publish(item)
    assert result['reconciled'] and state['writes'].count('/pulls')==1 and state['writes'].count('/git/refs')==1


def test_existing_pr_with_edited_tree_cannot_reuse_approval(github):
    service,item,state=github;service.publish(item)
    state['commit']['tree']['sha']='unapproved-tree'
    with pytest.raises(ConnectionProblem,match='does_not_match'):service.publish(item)


def test_existing_pr_with_other_parent_cannot_reuse_approval(github):
    service,item,state=github;service.publish(item)
    state['commit']['parents']=[{'sha':'unapproved-parent'}]
    with pytest.raises(ConnectionProblem,match='does_not_match'):service.publish(item)


def test_changed_base_requires_fresh_proposal(github):
    service,item,state=github;state['base']='changed'
    with pytest.raises(ConnectionProblem,match='base_revision_changed'):service.publish(item)
    assert '/git/refs' not in state['writes'] and '/pulls' not in state['writes']
