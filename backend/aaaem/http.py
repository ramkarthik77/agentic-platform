"""Bounded HTTPS transport. Endpoints come exclusively from reviewed server configuration."""
import json
import os
import httpx


class ConnectionProblem(Exception):
    def __init__(self, code='unavailable'):
        self.code = code
        super().__init__(code)


class Http:
    def __init__(self, transport=None):
        self.transport = transport

    def request(self, method, url, *, headers=None, timeout=20, limit=2_000_000, **kwargs):
        try:
            with httpx.Client(transport=self.transport, timeout=httpx.Timeout(timeout, connect=5),
                              follow_redirects=False, verify=os.getenv('AAAEM_CA_BUNDLE') or True,
                              trust_env=False) as client:
                with client.stream(method, url, headers=headers, **kwargs) as response:
                    if response.status_code in {401, 403}:
                        raise ConnectionProblem('credentials_or_scope_rejected')
                    if response.status_code == 429:
                        raise ConnectionProblem('rate_limited')
                    if not 200 <= response.status_code < 300:
                        raise ConnectionProblem('upstream_http_' + str(response.status_code))
                    chunks, size = [], 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > limit:
                            raise ConnectionProblem('response_limit_exceeded')
                        chunks.append(chunk)
                    return b''.join(chunks)
        except httpx.HTTPError:
            raise ConnectionProblem('network_or_tls_error') from None

    def json(self, method, url, **kwargs):
        try:
            return json.loads(self.request(method, url, **kwargs))
        except (ValueError, UnicodeError):
            raise ConnectionProblem('invalid_json_response') from None
