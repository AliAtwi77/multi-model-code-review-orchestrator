from pydantic import BaseModel, Field, field_validator
from typing import Optional
from enum import Enum

class TestCaseResult(BaseModel):
    name:str
    outcome:str #"passed" | "failed" | "error"
    message: Optional[str]= None

class TestResult(BaseModel):
    ran: bool
    passed: int = 0
    failed: int = 0
    errored: int = 0
    duration_seconds: float = 0.0
    cases: list[TestCaseResult]= Field(default_factory=list)
    stdout_tail: str = ""
    timed_out: bool = False
    crashed: bool = False
    error_message: Optional[str] = None

    @property
    def all_passed(self) ->bool:
        return self.ran and not self.timed_out and not self.crashed and self.failed == 0 and self.errored ==0


class StaticIssue(BaseModel):
    tool: str
    rule_id: str
    severity: str
    location: str
    message: str

class StaticAnalysisResult(BaseModel):
    ran: bool
    issues: list[StaticIssue] = Field(default_factory=list)
    tool_versions: dict[str, str] = Field(default_factory=dict)
    error_message: Optional[str] = None

    @property
    def high_severity_count(self) -> int:
        return sum(1 for i in self.issues if i.severity.lower() in {"error", "high"})


class Severity(str, Enum):
    BLOCKING = "blocking" # must be fixed before the loop can converge
    ADVISORY = "advisory" # worth noting, never blocks convergence

class Verdict(str, Enum):
    APPROVE= "approve"
    REQUEST_CHANGES = "request_changes"

class Finding(BaseModel):
    id: str = Field(description="Stable short id, e.g. F1, F2 - used to track a finding across iterations")
    severity: Severity
    category: str = Field(description="e.g. correctness, security, performance, style, resource-leak")
    location: str = Field(description="file:line or function name the finding refers to")
    rationale: str = Field(description="Why this is a problem, grounded in evidence when possible")
    suggested_fix: Optional[str] = None
    evidence: Optional[str] = Field(
        default=None,
        description= "Concrete evidence backing the finding: a failing test name, a static-analysis rule idd, a repoducing input. Findings with no evidence are weighted lower by the disagreement resolver."
    )

    @field_validator("id")
    @classmethod
    def _id_not_empty(cls, v:str) -> str:
        if not v.strip():
            raise ValueError("finfing id must not be empty")
        return v

class ReviewResult(BaseModel):
    verdict: Verdict
    summary: str
    findings: list[Finding]= Field(default_factory= list)
    standard_refs: list[str]= Field(
        default_factory= list,
        description= "Sections of the coding standard retrieved and cited in this review"
    )

    @property
    def blocking(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == Severity.BLOCKING]

    @property
    def advisory(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == Severity.ADVISORY]


class Disposition(BaseModel):
    """What the orchestrator decided to do about one finding."""
    finding_id: str
    accepted: bool
    reason: str