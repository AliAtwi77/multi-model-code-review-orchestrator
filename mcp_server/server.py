from mcp.server.fastmcp import FastMCP
from mcp_server.tools.test_tool import run_tests as _run_tests
import json
from mcp_server.tools.static_analysis_tool import run_static_analysis as _run_static_analysis
from schemas.review import TestResult, StaticAnalysisResult
from mcp_server.tools.review_tool import run_review as _run_review

mcp= FastMCP(
    "code-review-orchestrator",
    instructions=(
        "Tools supporting a generator/reviewer code-improvement loop: run generated code against tests, run static analysis on it, and get a structured, evidence-grounded review from an LLM belonging to a different provider than the code's author."
    ),
)

@mcp.tool(name="run_tests")
def run_tests_tool(solution_code: str, test_code: str) -> str:
    """Run pytest for `solution_code` (written to solution.py) against `test_code` (written to test_solution.py) inside a sandboxed, timeout-bound subprocess. Returns the JSON-serialized TestResult schema: pass/fail counts, per-case outcomes, and flags for timeout/crash so a hang never blocks the caller."""

    try:
        result= _run_tests(solution_code=solution_code, test_code= test_code)
        return result.model_dump_json()
    except Exception as e:
        return json.dumps({"error": f"{type(e).__name__}: {e}"})


@mcp.tool(name= "run_static_analysis")
def run_static_analysis_tool(solution_code: str) -> str:
    """Run ruff (lint/correctness), mypy (types) and bandit (security) against `solution_code`. Returns the JSON-serialized StaticAnalysisResult schema: a merged, tool-tagged list of issues with severity and location."""

    try:
        result= _run_static_analysis(solution_code=solution_code)
        return result.model_dump_json()
    except Exception as e:
        return json.dumps({"error": f"{type(e).__name__}: {e}"})


@mcp.tool(name="review_code")
def review_code_tool(
    code: str, # generated code
    task: str, # original task code suppose to solve
    iteration: int, #improvement iteration
    test_result_json: str, #result from test_tool
    static_result_json: str,# results from static_analysis tool
    history_summary: str = "(no prior iterations)",# information about previous iterations
) -> str:
    """Get a structured code review from an LLM belonging to a different
    provider than the generator. `test_result_json` and `static_result_json` must be the JSON output of run_tests/run_static_analysis so the reviewer is grounded in tool evidence rather than the code alone. Returns a JSON object `{"review": <ReviewResult>, "token_usage": {...}}`."""

    try:
        test_result= TestResult.model_validate_json(test_result_json)
        static_result= StaticAnalysisResult.model_validate_json(static_result_json)
        review, usage= _run_review(
            code= code,
            task= task,
            iteration= iteration,
            test_result=test_result,
            static_result=static_result,
            history_summary=history_summary
        )
        return json.dumps({"review": review.model_dump(), "token_usage": usage})
    except Exception as e: 
        return json.dumps({"error": f"{type(e).__name__}: {e}"})


if __name__ == "__main__":
    #start the server
    mcp.run(transport="stdio")