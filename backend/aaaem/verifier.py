"""Optional Playwright read-only verification service. Run separately from the UI/API."""
import asyncio
import ipaddress
import os
import secrets
import socket
from urllib.parse import urlsplit, urljoin, unquote
from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .db import now


class VerifySite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: int = Field(gt=0)
    url: str = Field(max_length=2048)
    pages: list[str] = Field(min_length=1, max_length=10)
    revision_header: str = Field(default='', pattern=r'^[A-Za-z0-9-]{0,80}$')

    @field_validator('pages')
    @classmethod
    def paths(cls, values):
        if any(len(p) > 2048 or not p.startswith('/') or p.startswith('//') or '..' in unquote(p).split('/') or '\\' in unquote(p) or '?' in p or '#' in p for p in values):
            raise ValueError('Invalid page path')
        return values


class VerifyRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    contract_version: int
    environment: str = Field(pattern=r'^(dev|stage|production)$')
    execution_id: str = Field(max_length=80)
    revision: str | None = Field(default=None, max_length=100)
    sites: list[VerifySite] = Field(min_length=1, max_length=4)


def permitted_url(url, hosts):
    try:
        p = urlsplit(url)
        return p.scheme == 'https' and p.hostname in hosts and not p.username and not p.password and p.port in {None, 443}
    except ValueError:
        return False


async def public_host(host):
    try:
        entries = await asyncio.to_thread(socket.getaddrinfo, host, 443, type=socket.SOCK_STREAM)
        return bool(entries) and all(ipaddress.ip_address(e[4][0]).is_global for e in entries)
    except (socket.gaierror, ValueError):
        return False


async def scan_site(browser, site, hosts, revision=None):
    context = await browser.new_context(viewport={'width': 1440, 'height': 900}, service_workers='block', accept_downloads=False)
    blocked = set()
    dns = {}
    async def route_handler(route):
        url = route.request.url
        if route.request.method not in {'GET', 'HEAD'}:
            return await route.abort()
        host = urlsplit(url).hostname
        if host not in dns: dns[host] = await public_host(host) if host else False
        if not permitted_url(url, hosts) or not dns[host]:
            if len(blocked) < 50: blocked.add(host or 'unsupported-protocol')
            return await route.abort()
        await route.continue_()
    await context.route('**/*', route_handler)
    async def block_socket(ws):
        await ws.close()
    await context.route_web_socket('**/*', block_socket)
    rows, checks, observed = [], [], []
    try:
        for path in site.pages:
            page = await context.new_page()
            url = urljoin(site.url.rstrip('/') + '/', path)
            page_checks = []
            try:
                if not permitted_url(url, hosts): raise ValueError('URL is outside allowed hosts')
                response = await page.goto(url, wait_until='domcontentloaded', timeout=8000)
                served = await response.header_value(site.revision_header) if response and site.revision_header else None
                observed.append(served)
                await page.wait_for_timeout(150)
                facts = await page.evaluate('''() => ({
                    title: !!document.title.trim(), lang: !!document.documentElement.lang,
                    canonical: !!document.querySelector('link[rel="canonical"][href]'),
                    heading: document.querySelectorAll('h1').length === 1,
                    imageAlt: [...document.images].every(i => i.hasAttribute('alt')),
                    buttonNames: [...document.querySelectorAll('button')].every(b => !!(b.innerText.trim() || b.getAttribute('aria-label') || b.getAttribute('aria-labelledby'))),
                    overflow: document.documentElement.scrollWidth <= innerWidth + 2,
                    links: [...new Set([...document.querySelectorAll('a[href]')].map(a=>a.href))].filter(u=>u.startsWith('https://')).slice(0,5)
                })''')
                page_checks = [{'name': 'HTTP response', 'passed': bool(response and response.status < 400)}]
                names = {'title': 'Page title', 'lang': 'Document language', 'canonical': 'Canonical link present',
                         'heading': 'One primary heading', 'imageAlt': 'Images declare alt text',
                         'buttonNames': 'Buttons declare an accessible name', 'overflow': 'No horizontal overflow at desktop viewport'}
                page_checks += [{'name': name, 'passed': bool(facts[key])} for key, name in names.items()]
                for link in facts['links']:
                    if urlsplit(link).hostname != urlsplit(site.url).hostname or not permitted_url(link, hosts): continue
                    # Browser navigation keeps request interception in force for redirects and subrequests.
                    probe = await context.new_page()
                    try:
                        response = await probe.goto(link, wait_until='commit', timeout=3000)
                        page_checks.append({'name': 'Sampled link ' + urlsplit(link).path[:160], 'passed': bool(response and response.status < 400)})
                    except Exception:
                        page_checks.append({'name': 'Sampled link ' + urlsplit(link).path[:160], 'passed': False})
                    finally: await probe.close()
            except Exception:
                page_checks = [{'name': 'Page navigation completed', 'passed': False}]
                observed.append(None)
            checks.extend(page_checks)
            rows.append({'path': path, 'checks': page_checks})
            await page.close()
        return {'id': site.id, 'passed': sum(c['passed'] for c in checks), 'total': len(checks), 'pages': rows,
                'observed_revisions': observed, 'revision_verified': bool(revision) and len(observed) == len(site.pages) and all(v == revision for v in observed),
                'blocked_hosts': sorted(blocked), 'complete': not blocked}
    finally:
        await context.close()


def create_verifier():
    token = os.environ.get('AAAEM_VERIFIER_TOKEN', '')
    hosts = set(filter(None, os.environ.get('AAAEM_VERIFIER_ALLOWED_HOSTS', '').split(',')))
    if len(token) < 32 or not hosts:
        raise ValueError('Configure a 32+ character AAAEM_VERIFIER_TOKEN and exact AAAEM_VERIFIER_ALLOWED_HOSTS')
    lock = asyncio.Lock()
    app = FastAPI(title='AAAEM verification worker', docs_url=None, redoc_url=None, openapi_url=None)
    def authorize(value):
        if not secrets.compare_digest(value, 'Bearer ' + token): raise HTTPException(401, 'Unauthorized')
    @app.get('/healthz')
    def health(authorization: str = Header(default='')):
        authorize(authorization)
        return {'status': 'ok', 'contract_version': 1}
    @app.post('/v1/verify')
    async def verify(body: VerifyRequest, authorization: str = Header(default='')):
        authorize(authorization)
        if body.contract_version != 1 or len({s.id for s in body.sites}) != len(body.sites):
            raise HTTPException(422, 'Invalid verification contract')
        for site in body.sites:
            if not permitted_url(site.url, hosts) or not await public_host(urlsplit(site.url).hostname):
                raise HTTPException(403, 'Only configured public HTTPS hosts may be scanned')
        if lock.locked(): raise HTTPException(429, 'Verification worker is busy; retry later')
        async with lock:
            from playwright.async_api import async_playwright
            results = []
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch()
                tasks = [asyncio.create_task(scan_site(browser, site, hosts, body.revision)) for site in body.sites]
                done, pending = await asyncio.wait(tasks, timeout=45)
                for task in done:
                    if not task.cancelled() and task.exception() is None: results.append(task.result())
                for task in pending: task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                await browser.close()
            return {'contract_version': 1, 'input_mode': 'live', 'environment': body.environment,
                'execution_id': body.execution_id, 'revision': body.revision, 'captured_at': now(),
                'sites': sorted(results, key=lambda s: s['id']),
                'complete': len(results) == len(body.sites) and all(s['complete'] for s in results),
                'revision_verified': len(results) == len(body.sites) and all(s['revision_verified'] for s in results),
                'note': 'Desktop Chromium; configured pages, basic SEO/accessibility, and at most five links per page. No form submissions.'}
    return app
