"""Versioned, non-secret workspace configuration. Secrets are environment references."""
import json
import os
from pathlib import Path, PurePosixPath
from typing import Literal
from urllib.parse import urlsplit
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Environment = Literal['dev', 'stage', 'production']
Role = Literal['reader', 'operator', 'reviewer', 'admin']


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


def endpoint(value):
    p = urlsplit(value)
    if p.scheme != 'https' or not p.hostname or p.username or p.password or p.fragment or p.query:
        raise ValueError('Configure an HTTPS endpoint without credentials, query, or fragment')
    return value.rstrip('/')


def safe_path(value):
    if not value or '\\' in value or value.startswith('/') or any(p in {'', '.', '..'} for p in value.split('/')):
        raise ValueError('Use a relative repository path without traversal')
    if any(p.startswith('.') for p in PurePosixPath(value).parts):
        raise ValueError('Hidden paths, workflows and Git metadata cannot be generated')
    return value


class Connection(StrictModel):
    driver: Literal['disabled', 'cloud_manager', 'new_relic', 'splunk', 'snyk', 'sonar', 'github', 'bridge', 'verification'] = 'disabled'
    base_url: str = ''
    token_env: str = ''
    header_env: dict[str, str] = Field(default_factory=dict)
    parameters: dict = Field(default_factory=dict)
    timeout_seconds: int = Field(default=20, ge=1, le=60)
    max_pages: int = Field(default=5, ge=1, le=20)

    @field_validator('base_url')
    @classmethod
    def validate_url(cls, value):
        return endpoint(value) if value else value

    @field_validator('token_env')
    @classmethod
    def validate_secret_ref(cls, value):
        import re
        if value and not re.fullmatch(r'[A-Z][A-Z0-9_]{1,99}', value):
            raise ValueError('Use an environment variable name, never a secret value')
        return value

    @field_validator('header_env')
    @classmethod
    def validate_headers(cls, value):
        import re
        for k, v in value.items():
            if k.lower() in {'host', 'content-length', 'cookie', 'authorization'} or not re.fullmatch(r'[A-Za-z0-9-]+', k):
                raise ValueError('Header name is not allowed')
            cls.validate_secret_ref(v)
        return value


class GitTarget(StrictModel):
    repository: str = Field(pattern=r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')
    base_branch: str = Field(default='main', pattern=r'^[A-Za-z0-9_.\-/]+$', max_length=120)
    allowed_prefixes: list[str] = Field(min_length=1, max_length=20)
    enabled: bool = False

    @field_validator('allowed_prefixes')
    @classmethod
    def validate_paths(cls, values):
        return [safe_path(v.rstrip('/')) + '/' for v in values]


class EnvironmentConfig(StrictModel):
    connections: dict[str, Connection] = Field(default_factory=dict)
    pull_requests: GitTarget | None = None

    @field_validator('connections')
    @classmethod
    def known_connections(cls, values):
        if set(values) - {'cloud_manager', 'new_relic', 'splunk', 'snyk', 'sonar', 'github', 'aem', 'verification'}:
            raise ValueError('Unknown connection name')
        for name, connection in values.items():
            allowed = {'disabled', 'bridge'} if name == 'aem' else {'disabled', 'verification'} if name == 'verification' else {'disabled', 'bridge', name}
            if connection.driver not in allowed:
                raise ValueError('Driver does not match the named connection')
        return values


class AccessGrant(StrictModel):
    roles: list[Role] = Field(min_length=1)
    environments: list[Environment] = Field(min_length=1)


class AuthConfig(StrictModel):
    issuer: str = ''
    authorization_endpoint: str = ''
    token_endpoint: str = ''
    jwks_endpoint: str = ''
    client_id: str = ''
    client_secret_env: str = 'AAAEM_OIDC_CLIENT_SECRET'
    group_claim: str = 'groups'
    group_grants: dict[str, AccessGrant] = Field(default_factory=dict)
    session_minutes: int = Field(default=60, ge=5, le=480)

    @field_validator('issuer', 'authorization_endpoint', 'token_endpoint', 'jwks_endpoint')
    @classmethod
    def https_url(cls, v):
        if v: endpoint(v)
        return v

    @field_validator('client_secret_env')
    @classmethod
    def secret_ref(cls, v):
        return Connection.validate_secret_ref(v)


class Site(StrictModel):
    id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=100)
    market: str = Field(min_length=2, max_length=12)
    region: str = Field(default='Configured', max_length=80)
    theme: str = Field(max_length=80)
    template: str = Field(default='Configured', max_length=80)
    urls: dict[Environment, str]
    pages: list[str] = Field(default_factory=lambda: ['/'], min_length=1, max_length=10)
    owner: str = Field(default='', max_length=160)
    content_root: str = Field(default='', max_length=300)
    revision_header: str = Field(default='', pattern=r'^[A-Za-z0-9-]{0,80}$')
    inheritance_exceptions: list[str] = Field(default_factory=list, max_length=100)

    @field_validator('urls')
    @classmethod
    def validate_urls(cls, values):
        return {k: endpoint(v) for k, v in values.items()}

    @field_validator('pages', 'inheritance_exceptions')
    @classmethod
    def validate_pages(cls, values):
        from urllib.parse import unquote
        if any(len(v) > 2048 or not v.startswith('/') or v.startswith('//') or '..' in unquote(v).split('/') or '\\' in unquote(v) or '?' in v or '#' in v for v in values):
            raise ValueError('Use bounded absolute paths on the configured site origin')
        return values


class Schedule(StrictModel):
    id: str = Field(pattern=r'^[a-z0-9-]{1,60}$')
    kind: Literal['core', 'release', 'incident', 'security', 'governance', 'reporting']
    objective: Literal['release-readiness', 'incident-investigation', 'platform-health'] = 'platform-health'
    environment: Environment = 'stage'
    interval_minutes: int = Field(ge=5, le=10080)
    enabled: bool = False


class WorkspaceConfig(StrictModel):
    version: Literal[1] = 1
    registry_file: str = ''
    environments: dict[Environment, EnvironmentConfig] = Field(default_factory=dict)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    templates_directory: str = ''
    templates_approved: bool = False
    schedules: list[Schedule] = Field(default_factory=list, max_length=20)
    intake_secret_env: str = 'AAAEM_INTAKE_SECRET'
    intake_environments: list[Environment] = Field(default_factory=lambda: ['dev', 'stage'])

    @model_validator(mode='after')
    def unique_schedules(self):
        if len({s.id for s in self.schedules}) != len(self.schedules):
            raise ValueError('Schedule IDs must be unique')
        return self

    def connection(self, environment, name):
        return self.environments.get(environment, EnvironmentConfig()).connections.get(name, Connection())


def load_config(path):
    if not path:
        return WorkspaceConfig()
    return WorkspaceConfig.model_validate_json(Path(path).read_text())


def read_registry(config):
    if not config.registry_file:
        return []
    raw = json.loads(Path(config.registry_file).read_text())
    if not isinstance(raw, list) or len(raw) > 1000:
        raise ValueError('The registry must be a list of at most 1000 sites')
    items = [Site.model_validate(s).model_dump() | {'source': 'registry', 'status': 'not_checked', 'checks': None} for s in raw]
    if len({s['id'] for s in items}) != len(items):
        raise ValueError('Site IDs must be unique')
    return items


def secret(name):
    return os.environ.get(name, '') if name else ''
