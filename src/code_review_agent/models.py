"""Typed review contract shared by the LLM layer, the validator and the publishers."""

from enum import StrEnum

from pydantic import BaseModel, Field


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @property
    def rank(self) -> int:
        return list(Severity).index(self)


class Category(StrEnum):
    BUG = "bug"
    SECURITY = "security"
    PERFORMANCE = "performance"
    ERROR_HANDLING = "error-handling"
    MAINTAINABILITY = "maintainability"
    TESTING = "testing"


class Finding(BaseModel):
    path: str = Field(description="File path exactly as shown in the diff header")
    line: int = Field(description="Line number in the NEW file version; must be an added or context line")
    severity: Severity
    category: Category
    title: str = Field(description="One-line summary of the problem")
    explanation: str = Field(description="Why this is a problem and what could go wrong")
    suggestion: str | None = Field(default=None, description="Concrete fix, optionally as replacement code")


class ReviewResult(BaseModel):
    summary: str = Field(description="2-4 sentence overview of the change and its overall quality")
    findings: list[Finding]
