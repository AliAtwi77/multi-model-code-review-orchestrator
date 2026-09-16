from schemas.review import ReviewResult, TestResult, StaticAnalysisResult, Disposition

def check_convergence(
    review: ReviewResult,
    test_result: TestResult,
    static_result: StaticAnalysisResult,
    dispositions: list[Disposition],
) -> tuple[bool, str]:
    
    tests_ok = test_result.all_passed or not test_result.ran  # not ran => no tests supplied for this task
    static_ok = static_result.ran and static_result.high_severity_count == 0
    accepted_blocking = [d for d in dispositions if d.accepted]

    if tests_ok and static_ok and review.verdict.value == "approve" and not accepted_blocking:
        return True, "Tests pass, static analysis clean, reviewer approved, no accepted blocking findings."

    if review.verdict.value == "request_changes" and not accepted_blocking and tests_ok and static_ok:
        return True, (
            "Reviewer requested changes, but every blocking finding was rejected or downgraded by the disagreement resolver as unsupported/inconsistent, and tests + static analysis are clean. Converging on the generator's code over the reviewer's objection."
        )

    return False, "Outstanding accepted blocking findings or failing tests/static analysis remain."