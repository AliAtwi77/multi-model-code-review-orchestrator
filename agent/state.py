from typing import Any, Optional, TypedDict
from schemas.review import ReviewResult, TestResult, StaticAnalysisResult, Disposition


class IterationRecord(TypedDict):
    iteration:int
    code: str
    diff: str
    test_result: dict
    static_result: dict
    dispositions: list[dict]
    token_usage: dict


class OrchestratorState(TypedDict, total= False):
    # --- inputs ---
    task: str
    test_code:str

    # --- working state ---
    current_code: str
    previous_code: Optional[str]
    iteration: int
    max_iterations: int

    # --- latest tool outputs (validated pydantic models, dumped to dict for state) ---
    test_result: dict
    static_result: dict
    review: dict
    dispositions: list[dict]

    # --- accumulated ---
    history: list[IterationRecord]
    finding_ledger: dict[str, dict]      # location -> last-seen finding + iteration, for disagreement/consistency checks
    token_usage_total: dict[str, dict]   # model_name -> {"prompt_tokens": int, "completion_tokens": int}

    # --- control flow ---
    converged: bool
    convergence_reason: str
    stop_reason: Optional[str]           # set on hard failures (crash loop, provider down) that force a stop

    # --- final output ---
    final_code: str
    mcp_call_log: list[dict[str, Any]]