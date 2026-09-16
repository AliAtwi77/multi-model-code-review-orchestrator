from schemas.review import TestResult, StaticAnalysisResult, Finding, ReviewResult, Disposition, Severity


def _location_has_tool_evidence(location: str, test_result: TestResult, static_result: StaticAnalysisResult) -> bool:
    """Checks if a finding's location matches any failing test case names or static analysis issue locations."""
    loc_lower = location.lower()
    for case in test_result.cases:
        if case.outcome != "passed" and loc_lower in case.name.lower():
            return True
    for issue in static_result.issues:
        if loc_lower in issue.location.lower():
            return True
    return False

def _has_concrete_evidence(finding: Finding) -> bool:
    """Checks if a finding includes non-trivial string text inside its evidence field."""
    if not finding.evidence:
        return False
    ev = finding.evidence.strip().lower()
    if not ev or ev in {"none", "n/a", "null"}:
        return False
    return True


def resolve(
    review: ReviewResult,
    test_result: TestResult,
    static_result: StaticAnalysisResult,
    finding_ledger: dict[str, dict],
    iteration: int,
) -> tuple[list[Disposition], dict[str, dict]]:
    """Evaluates code review findings against automated tool outputs to determine dispositions."""

    dispositions: list[Disposition] = []
    updated_ledger = dict(finding_ledger)
    code_is_clean = test_result.all_passed and static_result.high_severity_count == 0

    for finding in review.findings:
        location_key= finding.location.strip().lower()
        #Retrieves any historical ledger record that exists for this specific location key
        prior = updated_ledger.get(location_key)
        #Checks if the finding is marked only as an informational/non-blocking recommendation
        if finding.severity == Severity.ADVISORY:
            #Appends a rejected disposition (accepted=False) explaining that advisory findings do not block code approval
            dispositions.append(Disposition(
                finding_id=finding.id, accepted=False,
                reason="Advisory finding - logged but does not block or force a revision."
            ))
            updated_ledger[location_key] = {
                "iteration": iteration, "severity": "advisory", "rationale": finding.rationale,
            }
            continue

        # Rule 4: reviewer reversing its own prior approval at an unchanged location.
        # A location counts as "previously approved" either because it individually was
        # marked resolved_ok, or because the whole module was approved clean in an earlier
        # iteration and this location was never flagged before now.
        whole_module_prior = updated_ledger.get("__whole_module__")
        previously_approved = (prior and prior.get("severity") == "resolved_ok") or (
            prior is None and whole_module_prior and whole_module_prior.get("severity") == "resolved_ok"
            and whole_module_prior.get("iteration", -1) < iteration
        )
        if previously_approved and not _has_concrete_evidence(finding) \
                and not _location_has_tool_evidence(finding.location, test_result, static_result):
            reversal_iteration = prior["iteration"] if prior else whole_module_prior["iteration"]
            dispositions.append(Disposition(
                finding_id=finding.id, accepted=False,
                reason=(
                    f"Rejected: reviewer accepted this location as OK in iteration {reversal_iteration} and "
                    f"the code there has not changed; this blocking finding cites no new evidence "
                    f"(no failing test, no lint hit). Treated as reviewer inconsistency, not acted on."
                ),
            ))
            updated_ledger[location_key] = {"iteration": iteration, "severity": "blocking_disputed",
                                             "rationale": finding.rationale}
            continue

        # Rule 1/2: corroborated by tool evidence -> accept.
        if _location_has_tool_evidence(finding.location, test_result, static_result) or _has_concrete_evidence(finding):
            dispositions.append(Disposition(
                finding_id=finding.id, accepted=True,
                reason="Accepted: corroborated by failing test / lint result or concrete cited evidence."
            ))
            updated_ledger[location_key] = {"iteration": iteration, "severity": "blocking_accepted",
                                             "rationale": finding.rationale}
            continue

        # Rule 3: blocking, no evidence, code otherwise clean -> downgrade, don't act.
        if code_is_clean:
            dispositions.append(Disposition(
                finding_id=finding.id, accepted=False,
                reason=(
                    "Downgraded from blocking: no failing test, no lint hit, and no concrete evidence cited, "
                    "while all tests and static analysis are clean. Treated as unsupported opinion; not acted on."
                ),
            ))
            updated_ledger[location_key] = {"iteration": iteration, "severity": "blocking_unsupported",
                                             "rationale": finding.rationale}
            continue

        # Otherwise: blocking, no direct evidence, but the code is NOT clean overall - give it the benefit
        # of the doubt and accept, since something is demonstrably wrong nearby.
        dispositions.append(Disposition(
            finding_id=finding.id, accepted=True,
            reason="Accepted cautiously: no direct location-level evidence, but the code is not currently clean overall."
        ))
        updated_ledger[location_key] = {"iteration": iteration, "severity": "blocking_accepted",
                                         "rationale": finding.rationale}

    # Any location that appeared clean (no findings at all this round, code clean) is recorded as resolved_ok
    # so future spurious reversals can be caught by Rule 4.
    if code_is_clean and review.verdict.value == "approve":
        updated_ledger.setdefault("__whole_module__", {})
        updated_ledger["__whole_module__"] = {"iteration": iteration, "severity": "resolved_ok",
                                               "rationale": "All tests + static analysis clean; reviewer approved."}

    return dispositions, updated_ledger