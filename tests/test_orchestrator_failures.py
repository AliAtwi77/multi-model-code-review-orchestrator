"""
Exercises the orchestrator's failure paths without hitting any real LLM
provider or spawning the real MCP server subprocess - everything is
monkeypatched so these tests run offline and fast.
"""
from __future__ import annotations

from unittest.mock import patch

from schemas.review import TestResult, StaticAnalysisResult, ReviewResult, Verdict
from agent.state import OrchestratorState
from agent import nodes
from mcp_client.client import MCPToolError
from mcp_server.tools.review_tool import _fallback_review


def _base_state(**overrides) -> OrchestratorState:
    state: OrchestratorState = {
        "task": "write a function",
        "test_code": "",
        "current_code": "def f(): return 1",
        "iteration": 1,
        "max_iterations": 5,
        "history": [],
        "finding_ledger": {},
        "token_usage_total": {},
        "mcp_call_log": [],
    }
    state.update(overrides)
    return state


def test_generate_node_handles_generator_exception_without_crashing():
    state = _base_state(iteration=0)
    with patch("agent.nodes.generate_initial", side_effect=RuntimeError("provider down")):
        update = nodes.generate_node(state)
    assert "stop_reason" in update
    assert "provider down" in update["stop_reason"]


def test_test_node_handles_mcp_tool_error_without_crashing():
    state = _base_state()
    with patch("agent.nodes.mcp_client") as mock_client:
        mock_client.call_run_tests.side_effect = MCPToolError("server unreachable")
        update = nodes.test_node(state)
    result = TestResult.model_validate(update["test_result"])
    assert result.crashed is True
    assert "server unreachable" in (result.error_message or "")


def test_test_node_surfaces_sandbox_timeout_as_data_not_exception():
    state = _base_state()
    timed_out_result = TestResult(ran=True, timed_out=True, error_message="exceeded sandbox timeout")
    with patch("agent.nodes.mcp_client") as mock_client:
        mock_client.call_run_tests.return_value = timed_out_result
        update = nodes.test_node(state)
    result = TestResult.model_validate(update["test_result"])
    assert result.timed_out is True
    assert result.all_passed is False  # a hang must never be reported as passing


def test_static_analysis_node_handles_transport_failure():
    state = _base_state()
    with patch("agent.nodes.mcp_client") as mock_client:
        mock_client.call_run_static_analysis.side_effect = RuntimeError("broken pipe")
        update = nodes.static_analysis_node(state)
    result = StaticAnalysisResult.model_validate(update["static_result"])
    assert result.ran is False
    assert "broken pipe" in (result.error_message or "")


def test_review_node_falls_back_to_non_blocking_review_on_reviewer_failure():
    state = _base_state(
        test_result=TestResult(ran=True, passed=1, failed=0).model_dump(),
        static_result=StaticAnalysisResult(ran=True, issues=[]).model_dump(),
    )
    with patch("agent.nodes.mcp_client") as mock_client:
        mock_client.call_review_code.side_effect = RuntimeError("rate limited")
        update = nodes.review_node(state)
    review = ReviewResult.model_validate(update["review"])
    assert review.verdict == Verdict.APPROVE  # never blocks the loop on a broken reviewer
    assert review.findings == []


def test_fallback_review_never_blocks():
    review = _fallback_review("malformed JSON after retries")
    assert review.verdict == Verdict.APPROVE
    assert review.blocking == []


def test_convergence_node_stops_at_max_iterations_as_timeout_not_success():
    state = _base_state(
        iteration=5, max_iterations=5,
        test_result=TestResult(ran=True, passed=0, failed=1).model_dump(),
        static_result=StaticAnalysisResult(ran=True, issues=[]).model_dump(),
        review=ReviewResult(verdict=Verdict.REQUEST_CHANGES, summary="still broken", findings=[]).model_dump(),
        dispositions=[],
    )
    update = nodes.convergence_node(state)
    assert update["converged"] is False
    assert update["stop_reason"] == "max_iterations"
    assert "timeout" in update["convergence_reason"].lower()


def test_generate_node_stops_downstream_nodes_once_stop_reason_set():
    state = _base_state(stop_reason="Generator model failed on iteration 1: boom")
    assert nodes.test_node(state) == {}
    assert nodes.static_analysis_node(state) == {}
    assert nodes.review_node(state) == {}
