"""
Unit tests for agent/disagreement.py - no network calls, no MCP, no LLMs.
Pure logic tests over pydantic models.
"""
from __future__ import annotations

from schemas.review import (
    ReviewResult, Finding, Severity, Verdict,
    TestResult, TestCaseResult, StaticAnalysisResult, StaticIssue,
)
from agent.disagreement import resolve


def _clean_test_result() -> TestResult:
    return TestResult(ran=True, passed=5, failed=0, errored=0, duration_seconds=0.1, cases=[
        TestCaseResult(name="test_a", outcome="passed"),
        TestCaseResult(name="test_b", outcome="passed"),
    ])


def _clean_static_result() -> StaticAnalysisResult:
    return StaticAnalysisResult(ran=True, issues=[])


def test_blocking_finding_with_failing_test_evidence_is_accepted():
    test_result = TestResult(ran=True, passed=1, failed=1, errored=0, cases=[
        TestCaseResult(name="test_off_by_one", outcome="failed", message="assert 4 == 5"),
    ])
    review = ReviewResult(
        verdict=Verdict.REQUEST_CHANGES,
        summary="off by one",
        findings=[Finding(
            id="F1", severity=Severity.BLOCKING, category="correctness",
            location="test_off_by_one", rationale="loop bound is wrong",
        )],
    )
    dispositions, ledger = resolve(review, test_result, _clean_static_result(), {}, iteration=1)
    assert dispositions[0].accepted is True
    assert "corroborated" in dispositions[0].reason.lower()


def test_unsupported_blocking_finding_on_clean_code_is_declined():
    """The required 'system correctly declines to act on a review finding' case:
    reviewer raises a blocking finding with no evidence, on code where all tests
    pass and static analysis is clean. The orchestrator must not act on it."""
    review = ReviewResult(
        verdict=Verdict.REQUEST_CHANGES,
        summary="stylistic objection dressed up as blocking",
        findings=[Finding(
            id="F1", severity=Severity.BLOCKING, category="style",
            location="format_name", rationale="I would have named this differently",
            evidence=None,
        )],
    )
    dispositions, ledger = resolve(review, _clean_test_result(), _clean_static_result(), {}, iteration=1)
    assert dispositions[0].accepted is False
    assert "unsupported" in dispositions[0].reason.lower()


def test_reviewer_reversal_without_new_evidence_is_rejected():
    """Iteration 1: reviewer approves everything clean. Iteration 2: reviewer
    raises a new blocking finding at the same (unchanged) location with no
    new evidence. This must be rejected as inconsistency, not acted on."""
    review_1 = ReviewResult(verdict=Verdict.APPROVE, summary="looks good", findings=[])
    _, ledger = resolve(review_1, _clean_test_result(), _clean_static_result(), {}, iteration=1)

    review_2 = ReviewResult(
        verdict=Verdict.REQUEST_CHANGES,
        summary="actually I object now",
        findings=[Finding(
            id="F1", severity=Severity.BLOCKING, category="style",
            location="helper_function", rationale="reconsidered, don't like this pattern",
            evidence=None,
        )],
    )
    dispositions, _ = resolve(review_2, _clean_test_result(), _clean_static_result(), ledger, iteration=2)
    assert dispositions[0].accepted is False
    assert "inconsistency" in dispositions[0].reason.lower()


def test_finding_corroborated_by_static_analysis_location_is_accepted():
    static_result = StaticAnalysisResult(ran=True, issues=[
        StaticIssue(tool="bandit", rule_id="B608", severity="high", location="solution.py:12", message="sql injection"),
    ])
    review = ReviewResult(
        verdict=Verdict.REQUEST_CHANGES,
        summary="security issue",
        findings=[Finding(
            id="F1", severity=Severity.BLOCKING, category="security",
            location="solution.py:12", rationale="string-built SQL",
        )],
    )
    dispositions, _ = resolve(review, _clean_test_result(), static_result, {}, iteration=1)
    assert dispositions[0].accepted is True


def test_advisory_findings_never_block():
    review = ReviewResult(
        verdict=Verdict.APPROVE,
        summary="minor nit",
        findings=[Finding(
            id="F1", severity=Severity.ADVISORY, category="style",
            location="solution.py:1", rationale="could use a docstring",
        )],
    )
    dispositions, _ = resolve(review, _clean_test_result(), _clean_static_result(), {}, iteration=1)
    assert dispositions[0].accepted is False
