import os
from dataclasses import dataclass, field
from pathlib import Path
from functools import cached_property
from .setup import load_config

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=lambda: os.getenv(
        "DATABASE_URL", f"sqlite:///{ROOT / '.data' / 'aaaem.db'}"))
    mode: str = field(default_factory=lambda: os.getenv("AAAEM_MODE", "local"))
    provider: str = field(default_factory=lambda: os.getenv("AAAEM_MODEL_PROVIDER", "fixture"))
    model_id: str = field(default_factory=lambda: os.getenv('AAAEM_MODEL_ID') or os.getenv("AAAEM_BEDROCK_MODEL_ID", ""))
    region: str = field(default_factory=lambda: os.getenv("AWS_REGION", "us-east-1"))
    integration_mode: str = field(default_factory=lambda: os.getenv('AAAEM_INTEGRATION_MODE', 'fixture'))
    config_file: str = field(default_factory=lambda: os.getenv('AAAEM_CONFIG_FILE', ''))
    public_origin: str = field(default_factory=lambda: os.getenv('AAAEM_PUBLIC_ORIGIN', ''))
    model_endpoint: str = field(default_factory=lambda: os.getenv('AAAEM_MODEL_ENDPOINT', ''))
    model_token_env: str = 'AAAEM_MODEL_API_KEY'
    allowed_hosts: tuple = field(default_factory=lambda: tuple(os.getenv(
        "AAAEM_ALLOWED_HOSTS", "127.0.0.1,localhost,[::1]").split(",")))
    worker_enabled: bool = field(default_factory=lambda: os.getenv('AAAEM_WORKER_ENABLED', 'true').lower() == 'true')
    step_delay: float = 0.35
    lease_seconds: int = 120
    max_attempts: int = 3

    @cached_property
    def workspace(self):
        return load_config(self.config_file)

    def validate(self):
        if self.mode not in {'local', 'production'}:
            raise ValueError('AAAEM_MODE must be local or production')
        if self.integration_mode not in {'fixture', 'live'}:
            raise ValueError('AAAEM_INTEGRATION_MODE must be fixture or live')
        if self.mode == 'production':
            from .setup import endpoint, secret
            auth = self.workspace.auth
            if not all([auth.issuer, auth.authorization_endpoint, auth.token_endpoint, auth.jwks_endpoint,
                        auth.client_id, secret(auth.client_secret_env), auth.group_grants, self.public_origin]):
                raise ValueError('Enterprise authentication requires complete OIDC configuration and credentials')
            if endpoint(self.public_origin) != self.public_origin or '/' in self.public_origin.split('://')[1]:
                raise ValueError('AAAEM_PUBLIC_ORIGIN must be an HTTPS origin without a path')
            if not self.database_url.startswith('postgresql'):
                raise ValueError('Hosted mode requires PostgreSQL')
            if self.integration_mode != 'live':
                raise ValueError('Hosted mode requires explicit live integration mode')
        if self.provider not in {"fixture", "bedrock", "openai_compatible"}:
            raise ValueError("AAAEM_MODEL_PROVIDER must be fixture, bedrock, or openai_compatible")
        if self.provider == "bedrock" and not self.model_id:
            raise ValueError("AAAEM_BEDROCK_MODEL_ID is required for Bedrock")
        if "*" in self.allowed_hosts:
            raise ValueError("Unrestricted wildcard hosts are not allowed")
        if self.provider == 'openai_compatible':
            from .setup import endpoint, secret
            endpoint(self.model_endpoint)
            if not self.model_id or not secret(self.model_token_env):
                raise ValueError('Configure the model ID and AAAEM_MODEL_API_KEY')
        self.workspace
