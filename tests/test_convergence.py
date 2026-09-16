from __future__ import annotations

from schemas.review import ReviewResult, Verdict, TestResult, StaticAnalysisResult, Disposition
from agent.convergence import check_convergence


def _passed_tests() -> TestResult:
    return TestResult(ran=True, passed=3, failed=0, errored=0)


def _failed_tests() -> TestResult:
    return TestResult(ran=True, passed=2, failed=1, errored=0)


def _clean_static() -> StaticAnalysisResult:
    return StaticAnalysisResult(ran=True, issues=[])


def test_converges_when_clean_and_approved_with_no_accepted_findings():
    review = ReviewResult(verdict=Verdict.APPROVE, summary="ok", findings=[])
    converged, reason = check_convergence(review, _passed_tests(), _clean_static(), [])
    assert converged is True


def test_does_not_converge_with_failing_tests():
    review = ReviewResult(verdict=Verdict.APPROVE, summary="ok", findings=[])
    converged, reason = check_convergence(review, _failed_tests(), _clean_static(), [])
    assert converged is False


def test_does_not_converge_with_accepted_blocking_finding_pending():
    review = ReviewResult(verdict=Verdict.REQUEST_CHANGES, summary="fix it", findings=[])
    dispositions = [Disposition(finding_id="F1", accepted=True, reason="corroborated")]
    converged, reason = check_convergence(review, _passed_tests(), _clean_static(), dispositions)
    assert converged is False


def test_converges_over_reviewer_objection_when_all_findings_rejected_and_code_clean():
    review = ReviewResult(verdict=Verdict.REQUEST_CHANGES, summary="objection", findings=[])
    dispositions = [Disposition(finding_id="F1", accepted=False, reason="unsupported - downgraded")]
    converged, reason = check_convergence(review, _passed_tests(), _clean_static(), dispositions)
    assert converged is True
    assert "over the reviewer's objection" in reason
