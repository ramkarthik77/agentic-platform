"""Optional integration smoke test against a dedicated disposable aaaem_test database."""
import os
import pytest
from sqlalchemy.engine import make_url
from fastapi.testclient import TestClient
from aaaem.api import create_app
from aaaem.config import Settings
from aaaem import db


@pytest.mark.skipif(not os.getenv('AAAEM_TEST_POSTGRES_URL'), reason='PostgreSQL service not configured')
def test_postgres_workflow():
    url = os.environ['AAAEM_TEST_POSTGRES_URL']
    assert make_url(url).database == 'aaaem_test', 'Use the dedicated disposable test database'
    engine = db.make_engine(url)
    db.metadata.drop_all(engine)
    try:
        settings = Settings(database_url=url, allowed_hosts=('testserver',), worker_enabled=False, step_delay=0)
        with TestClient(create_app(settings)) as client:
            csrf = client.get('/api/bootstrap').json()['csrf']
            headers = {'X-AAAEM-CSRF':csrf,'Idempotency-Key':'postgres-test-run'}
            response = client.post('/api/runs', headers=headers, json={'kind':'release'})
            assert response.status_code == 202
            client.app.state.platform.tick()
            data = client.get('/api/runs/' + response.json()['id']).json()
            assert data['run']['result']['assessment'] == 'verified'
            a = client.get('/api/workspace').json()['approvals'][0]
            assert client.post('/api/approvals/'+a['id']+'/decision', headers=headers,
                               json={'digest':a['digest'],'decision':'approved'}).status_code == 200
    finally:
        db.metadata.drop_all(engine)
        engine.dispose()
