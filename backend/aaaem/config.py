import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=lambda: os.getenv(
        "DATABASE_URL", f"sqlite:///{ROOT / '.data' / 'aaaem.db'}"))
    mode: str = field(default_factory=lambda: os.getenv("AAAEM_MODE", "local"))
    provider: str = field(default_factory=lambda: os.getenv("AAAEM_MODEL_PROVIDER", "fixture"))
    model_id: str = field(default_factory=lambda: os.getenv("AAAEM_BEDROCK_MODEL_ID", ""))
    region: str = field(default_factory=lambda: os.getenv("AWS_REGION", "us-east-1"))
    allowed_hosts: tuple = field(default_factory=lambda: tuple(os.getenv(
        "AAAEM_ALLOWED_HOSTS", "127.0.0.1,localhost,[::1]").split(",")))
    worker_enabled: bool = True
    step_delay: float = 0.35
    lease_seconds: int = 120
    max_attempts: int = 3

    def validate(self):
        if self.mode != "local":
            raise ValueError("Only local mode is implemented. Enterprise authentication is required before hosting.")
        if self.provider not in {"fixture", "bedrock"}:
            raise ValueError("AAAEM_MODEL_PROVIDER must be fixture or bedrock")
        if self.provider == "bedrock" and not self.model_id:
            raise ValueError("AAAEM_BEDROCK_MODEL_ID is required for Bedrock")
        if "*" in self.allowed_hosts:
            raise ValueError("Wildcard hosts are not allowed in local mode")
