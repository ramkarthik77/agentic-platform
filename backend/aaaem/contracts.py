from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["release", "incident", "reporting"]
    environment: Literal["dev", "stage", "production"] = "stage"
    scenario: Literal["healthy", "degraded", "incomplete"] = "healthy"
    scope: Literal["theme-04", "shared", "unknown"] = "theme-04"


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
