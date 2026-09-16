from agent.state import OrchestratorState
import time
from agent.generator import generate_initial, revise
from configuration.settings import settings
from schemas.review import TestResult, StaticAnalysisResult, ReviewResult, Disposition
from mcp_client.client import mcp_client, MCPToolError
from agent.disagreement import resolve as resolve_disagreement
import difflib
from agent.convergence import check_convergence



def _log_call(state: OrchestratorState, tool: str, ok: bool, note: str = "") -> dict:
    log = list(state.get("mcp_call_log", []))
    log.append({"tool": tool, "ok": ok, "note": note, "ts": time.time()})
    return {"mcp_call_log": log}


def _accumulate_tokens(state: OrchestratorState, model_key: str, usage: dict) -> dict:
    totals = dict(state.get("token_usage_total", {}))

    running = dict(totals.get(model_key, {"prompt_tokens": 0, "completion_tokens": 0}))

    running["prompt_tokens"] = running.get("prompt_tokens", 0) + usage.get("prompt_tokens", 0)

    running["completion_tokens"] = running.get("completion_tokens", 0) + usage.get("completion_tokens", 0)

    totals[model_key] = running
    return {"token_usage_total": totals}


def generate_node(state:OrchestratorState) -> dict:
    """First iteration: write code from scratch. Later iterations: revise based on the accepted dispositions from the previous round."""
    iteration= state.get("iteration",0)+1
    update: dict = {"iteration": iteration, "previous_code": state.get("current_code")}

    try:
        if iteration ==1:
            code, usage= generate_initial(state["task"])
        else:
            dispositions = state.get("dispositions", [])
            review = state.get("review", {})
            findings_by_id = {f["id"]: f for f in review.get("findings", [])}

            accepted= [
                findings_by_id[d["finding_id"]] for d in dispositions 
                if d['accepted'] and d["finding_id"] in findings_by_id
            ]

            rejected= [
                findings_by_id[d["finding_id"]] for d in dispositions 
                if not d['accepted'] and d["finding_id"] in findings_by_id
            ]

            code, usage= revise(state["task"], state["current_code"], accepted, rejected)

    except Exception as e:
        update["stop_reason"] = f"Generator model failed on iteration {iteration}: {e}"
        update["current_code"] = state.get("current_code", "")
        return update

    update["current_code"]=code
    update.update(_accumulate_tokens(state, f"generator:{settings.generator_model}", usage))
    return update


def test_node(state:OrchestratorState) ->dict:
    """Runs the test-execution MCP tool. Never crashes the loop - a hang
    or a crash is captured as data in TestResult and handled downstream."""
    if state.get("stop_reason"):
        return {}
    try:
        result: TestResult= mcp_client.call_run_tests(state["current_code"], state.get("test_code", ""))

        return {"test_result": result.model_dump(), **_log_call(state, "run_tests", True)}
    
    except MCPToolError as e:
        fallback = TestResult(ran=False, crashed=True, error_message=str(e))
        return {"test_result": fallback.model_dump(), **_log_call(state, "run_tests", False, str(e))}
    except Exception as e:
        fallback = TestResult(ran=False, crashed=True, error_message=f"MCP transport error: {e}")
        return {"test_result": fallback.model_dump(), **_log_call(state, "run_tests", False, str(e))}


def static_analysis_node(state: OrchestratorState) -> dict:
    if state.get("stop_reason"):
        return {}
    try:
        result: StaticAnalysisResult = mcp_client.call_run_static_analysis(state["current_code"])

        return {"static_result": result.model_dump(), **_log_call(state, "run_static_analysis", True)}
    
    except Exception as e:  # noqa: BLE001
        fallback = StaticAnalysisResult(ran=False, error_message=f"MCP transport error: {e}")
        return {"static_result": fallback.model_dump(), **_log_call(state, "run_static_analysis", False, str(e))}


def _summarize_history_for_reviewer(state: OrchestratorState) -> str:
    history = state.get("history", [])
    if not history:
        return "(no prior iterations)"
    
    lines = []

    for h in history[-3:]:  # cap context growth
        lines.append(
            f"Iteration {h['iteration']}: verdict={h['review'].get('verdict')}, "
            f"blocking_findings={[f['id'] for f in h['review'].get('findings', []) if f.get('severity') == 'blocking']}, "
            f"dispositions={[(d['finding_id'], d['accepted']) for d in h.get('dispositions', [])]}"
        )

    return "\n".join(lines)


def review_node(state: OrchestratorState) -> dict:
    if state.get("stop_reason"):
        return {}
    try:
        test_result = TestResult.model_validate(state["test_result"])
        static_result = StaticAnalysisResult.model_validate(state["static_result"])
        review, usage = mcp_client.call_review_code(
            code=state["current_code"],
            task=state["task"],
            iteration=state["iteration"],
            test_result=test_result,
            static_result=static_result,
            history_summary=_summarize_history_for_reviewer(state),
        )

        update = {"review": review.model_dump(), **_log_call(state, "review_code", True)}
        update.update(_accumulate_tokens(state, f"reviewer:{settings.reviewer_model}", usage))
        return update
    
    except Exception as e:  # noqa: BLE001 - reviewer provider down/rate-limited: don't crash, don't block
        fallback = ReviewResult(verdict="approve", summary=f"Review step failed: {e}. Not blocking.", findings=[])
        return {"review": fallback.model_dump(), **_log_call(state, "review_code", False, str(e))}


def disposition_node(state: OrchestratorState) -> dict:
    """Applies agent/disagreement.py - decides which findings the generator
    must actually act on. This is where the system can decline a finding."""
    review = ReviewResult.model_validate(state["review"])
    test_result = TestResult.model_validate(state["test_result"])
    static_result = StaticAnalysisResult.model_validate(state["static_result"])
    ledger = state.get("finding_ledger", {})

    dispositions, updated_ledger = resolve_disagreement(
        review=review, test_result=test_result, static_result=static_result,
        finding_ledger=ledger, iteration=state["iteration"],
    )

    diff = "\n".join(
        difflib.unified_diff(
            (state.get("previous_code") or "").splitlines(),
            state["current_code"].splitlines(),
            fromfile="previous", tofile="current", lineterm="",
        )
    )

    record = {
        "iteration": state["iteration"],
        "code": state["current_code"],
        "diff": diff,
        "test_result": state["test_result"],
        "static_result": state["static_result"],
        "review": state["review"],
        "dispositions": [d.model_dump() for d in dispositions],
        "token_usage": state.get("token_usage_total", {}),
    }
    history = list(state.get("history", []))
    history.append(record)

    return {
        "dispositions": [d.model_dump() for d in dispositions],
        "finding_ledger": updated_ledger,
        "history": history,
    }



def convergence_node(state: OrchestratorState) -> dict:
    if state.get("stop_reason"):
        return {"converged": False, "convergence_reason": state["stop_reason"], "final_code": state["current_code"]}

    review = ReviewResult.model_validate(state["review"])
    test_result = TestResult.model_validate(state["test_result"])
    static_result = StaticAnalysisResult.model_validate(state["static_result"])
    dispositions = [Disposition.model_validate(d) for d in state.get("dispositions", [])]

    converged, reason = check_convergence(review, test_result, static_result, dispositions)

    if not converged and state["iteration"] >= state.get("max_iterations", settings.max_iterations):
        return {
            "converged": False,
            "convergence_reason": "max_iterations reached without convergence (timeout, not success)",
            "stop_reason": "max_iterations",
            "final_code": state["current_code"],
        }

    update = {"converged": converged, "convergence_reason": reason}

    if converged:
        update["final_code"] = state["current_code"]

    return update


def route_after_convergence(state: OrchestratorState) -> str:
    """Conditional edge function"""
    if state.get("converged") or state.get("stop_reason"):
        return "end"
    return "generate"