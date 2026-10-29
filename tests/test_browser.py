"""Real Chromium UI flow; enable with AAAEM_BROWSER_TESTS=1 on a clean development/CI host."""
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
import pytest

pytestmark=pytest.mark.skipif(os.getenv('AAAEM_BROWSER_TESTS')!='1',reason='Browser flow is opt-in; CI installs Chromium')
ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def browser_workspace(tmp_path):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    origin=f'http://127.0.0.1:{port}'
    env=os.environ|{'AAAEM_MODE':'local','AAAEM_INTEGRATION_MODE':'fixture','AAAEM_MODEL_PROVIDER':'fixture',
        'AAAEM_WORKER_ENABLED':'true','AAAEM_ALLOWED_HOSTS':'127.0.0.1','AAAEM_CONFIG_FILE':'',
        'DATABASE_URL':f'sqlite:///{tmp_path}/browser.db'}
    logs=open(tmp_path/'server.log','w')
    process=subprocess.Popen([sys.executable,'scripts/serve.py','--port',str(port)],cwd=ROOT,env=env,stdout=logs,stderr=subprocess.STDOUT)
    try:
        for _ in range(100):
            try:
                with urllib.request.urlopen(origin+'/healthz',timeout=1):break
            except OSError:time.sleep(0.1)
        else:pytest.fail('Browser test server failed to start')
        yield origin
    finally:
        process.terminate()
        try:process.wait(timeout=15)
        except subprocess.TimeoutExpired:process.kill();process.wait()
        logs.close()


def test_ui_mission_review_bundle_and_configuration(browser_workspace):
    from playwright.sync_api import sync_playwright, expect
    artifacts=ROOT/'test-results';artifacts.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch()
        context=browser.new_context(viewport={'width':1440,'height':1000},reduced_motion='reduce')
        page=context.new_page();errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        try:
            page.goto(browser_workspace)
            expect(page.get_by_role('heading',name='Mission control',exact=True)).to_be_visible()
            page.get_by_role('button',name='Start an agent run',exact=True).first.click()
            page.get_by_label('Workflow',exact=True).select_option('core')
            page.get_by_label('Demo scenario').select_option('degraded')
            page.get_by_role('button',name='Start run',exact=True).click()
            expect(page.locator('button.data-row').first).to_contain_text('needs_attention',timeout=60000)
            page.locator('button.data-row').first.click()
            expect(page.get_by_role('heading',name='Team handoffs')).to_be_visible()
            expect(page.locator('.handoff-row')).to_have_count(3)
            page.get_by_role('button',name='Close dialog').click()
            page.get_by_role('button',name='Approvals',exact=True).click()
            page.get_by_role('button',name='Accept draft',exact=True).click()
            expect(page.locator('.approval-detail')).to_contain_text('approved by local-operator')
            page.get_by_role('button',name='Site factory',exact=True).click()
            page.get_by_role('button',name='Start site factory',exact=True).click()
            page.get_by_role('button',name='Start run',exact=True).click()
            expect(page.locator('button.data-row').first).to_contain_text('proposal_ready',timeout=20000)
            page.locator('button.data-row').first.click()
            with page.expect_download() as download:page.get_by_role('link',name='Download bundle').click()
            assert download.value.suggested_filename.endswith('.zip')
            page.get_by_role('button',name='Prepare draft PR proposal').click()
            page.get_by_role('button',name='Approve these files').click()
            page.get_by_role('button',name='Simulate PR creation').click()
            expect(page.get_by_role('dialog')).to_contain_text('no GitHub branch or PR was created')
            page.get_by_role('button',name='Close dialog').click()
            page.get_by_role('button',name='Approvals',exact=True).click()
            expect(page.get_by_role('heading',name='File change proposals')).to_be_visible()
            page.reload()
            expect(page.locator('.change-card')).to_contain_text('simulated')
            page.get_by_role('button',name='Integrations',exact=True).click()
            expect(page.locator('.integration-card')).to_have_count(8)
            page.locator('.integration-card').first.get_by_role('button',name='Check connection').click()
            expect(page.locator('.integration-card').first).to_contain_text('no live request was sent')
            assert context.request.get(browser_workspace+'/guide').ok
            page.screenshot(path=str(artifacts/'integrations-desktop.png'),full_page=True)
            page.get_by_role('button',name='Mission control',exact=True).click()
            page.screenshot(path=str(artifacts/'mission-desktop.png'),full_page=True)
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 2')
            page.get_by_role('button',name='Open navigation').click()
            page.get_by_role('button',name='Agent fleet',exact=True).click()
            expect(page.locator('.fleet-card')).to_have_count(7)
            page.screenshot(path=str(artifacts/'agents-mobile.png'),full_page=True)
            assert not errors,errors
        except Exception:
            page.screenshot(path=str(artifacts/'failure.png'),full_page=True)
            raise
        finally:browser.close()
