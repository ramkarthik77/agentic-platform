from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class SiteSpec(BaseModel):
    model_config = ConfigDict(extra='forbid')
    slug: str = Field(pattern=r'^[a-z][a-z0-9-]{1,39}$')
    brand: str = Field(min_length=1, max_length=80, pattern=r'^[A-Za-z0-9 _-]+$')
    market: str = Field(pattern=r'^[A-Z]{2}$')
    locale: str = Field(pattern=r'^[a-z]{2}(?:-[A-Z]{2})?$')
    domain: str = Field(pattern=r'^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$')
    theme: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,50}$')


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["core", "release", "incident", "security", "factory", "governance", "reporting"]
    environment: Literal["dev", "stage", "production"] = "stage"
    scenario: Literal["healthy", "degraded", "incomplete"] = "healthy"
    scope: Literal["theme-04", "shared", "unknown", "selected"] = "theme-04"
    site_ids: list[int] = Field(default_factory=list, max_length=250)
    execution_id: str = Field(default='', pattern=r'^[A-Za-z0-9_-]{0,80}$')
    objective: Literal['release-readiness', 'incident-investigation', 'site-onboarding', 'platform-health'] = 'release-readiness'
    site_spec: SiteSpec | None = None

    @model_validator(mode='after')
    def valid_scope(self):
        if self.scope == 'selected' and not self.site_ids:
            raise ValueError('Selected scope requires site IDs')
        if len(set(self.site_ids)) != len(self.site_ids) or any(x < 1 for x in self.site_ids):
            raise ValueError('Site IDs must be unique positive integers')
        if (self.kind == 'factory' or self.kind == 'core' and self.objective == 'site-onboarding') and not self.site_spec:
            raise ValueError('Site Factory requires a site specification')
        return self


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approved", "declined"]
    digest: str = Field(min_length=64, max_length=64, pattern="^[a-f0-9]+$")
    reason: str = Field(default="", max_length=1000)


class Narrative(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=1, max_length=4000)
    evidence_ids: list[str] = Field(min_length=1, max_length=20)
    hypotheses: list[str] = Field(default_factory=list, max_length=5)
    limitations: list[str] = Field(min_length=1, max_length=10)
