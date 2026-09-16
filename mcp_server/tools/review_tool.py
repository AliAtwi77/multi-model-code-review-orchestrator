from schemas.review import TestResult, StaticAnalysisResult, ReviewResult
from configuration.settings import settings
from mcp_server.tools.standards_retrieval import retrieve_relevant_sections
from typing import Optional
import json
from pydantic import ValidationError


_MAX_PARSE_RETRIES = 2

_SYSTEM_PROMPT = """You are a senior code reviewer. You review Python code written by \
another AI model. You are NOT the author and must judge the code on its merits, not \
defer to it.

Rules you must follow:
1. Respond with ONLY a single JSON object matching this schema, no prose, no markdown fences:
   {{
     "verdict": "approve" | "request_changes",
     "summary": "<one paragraph>",
     "findings": [
       {{
         "id": "F1",
         "severity": "blocking" | "advisory",
         "category": "correctness|security|performance|style|resource-leak|testing",
         "location": "function name or file:line",
         "rationale": "<why this is a problem>",
         "suggested_fix": "<optional>",
         "evidence": "<a failing test name, a lint rule id, or a concrete reproducing input - or null if none>"
       }}
     ],
     "standard_refs": ["<short quote or title of the standard section you relied on>"]
   }}
2. A finding with no concrete evidence and no clear correctness/security impact MUST be "advisory", never "blocking".
3. If test results are provided and all tests pass, do not invent correctness findings that contradict passing tests.
4. If you approved a piece of code in a prior iteration, do not raise a new blocking finding against the *same*
   unchanged location without new evidence. Consistency across iterations matters.
5. Ground your review in the coding standard excerpts provided below; cite the section you used in standard_refs.
"""

_USER_TEMPLATE = """## Task
{task}

## Coding standard (retrieved excerpts)
{standard_excerpts}

## Candidate code (iteration {iteration})
```python
{code}
```

## Test results
{test_summary}

## Static analysis results
{static_summary}

## Prior review history (for consistency checking)
{history_summary}

Return the JSON review now.
"""


def _summarize_tests(t: TestResult) -> str:
    """converts the structured TestResult into a concise string for the LLM"""

    if not t.ran:
        return f"Tests did not run. {t.error_message or ''}"
    if t.timed_out:
        return "Tests timed out - possible infinite loop or unbounded blocking call."
    if t.crashed:
        return f"Test process crashed before running: {t.error_message}"
    
    lines = [f"{t.passed} passed, {t.failed} failed, {t.errored} errored (duration {t.duration_seconds:.2f}s)."]

    for c in t.cases:
        if c.outcome != "passed":
            lines.append(f"- FAILED {c.name}: {(c.message or '')[:300]}")

    return "\n".join(lines)
    

def _summarize_static(s: StaticAnalysisResult) -> str:
    """converts the structured Result of Ruff, Mypy, and Bandi into a concise string for the LLM"""

    if not s.ran:
        return f"Static analysis did not run. {s.error_message or ''}"
    if not s.issues:
        return "No issues reported by ruff/mypy/bandit."
    
    lines = [f"{len(s.issues)} issue(s) found:"]

    for i in s.issues[:25]:
        lines.append(f"- [{i.tool}:{i.rule_id}] {i.severity} at {i.location}: {i.message}")

    return "\n".join(lines)


def _get_reviewer_llm():
    """Instantiate the reviewer model. Provider is intentionally distinct from the generator's"""
    provider = settings.reviewer_provider.lower()
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=settings.reviewer_model,
            api_key=settings.anthropic_api_key,
            temperature=0,
            max_tokens=2000,
        )
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.reviewer_model,
            api_key=settings.openai_api_key,
            temperature=0,
        )
    else:
        raise ValueError(f"Unsupported reviewer_provider: {provider}")


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    return text.strip()


def _fallback_review(reason: str) -> ReviewResult:
    """Used when the reviewer provider is unavailable or keeps returning
    malformed JSON. Never blocks convergence - a broken reviewer must notbe able to wedge the loop indefinitely."""
    return ReviewResult(
        verdict="approve",
        summary=f"Reviewer unavailable or returned malformed output after retries: {reason}. "
                f"Proceeding without blocking findings; flag this run for manual inspection.",
        findings=[],
        standard_refs=[],
    )


def run_review(
        code:str,
        task: str,
        iteration: int,
        test_result: TestResult,
        static_result: StaticAnalysisResult,
        history_summary: str = "(no prior iterations)",
) -> tuple[ReviewResult, dict]:
    """Returns (ReviewResult, token_usage_dict)."""
    excerpts= retrieve_relevant_sections(code= code, task= task, top_k= 3)
    standard_excerpts= "\n\n".join(excerpts) if excerpts else "(no relevant sections retrieved)"

    user_msg= _USER_TEMPLATE.format(
        task=task,
        standard_excerpts= standard_excerpts,
        iteration= iteration,
        code= code,
        test_summary= _summarize_tests(test_result),
        static_summary= _summarize_static(static_result),
        history_summary= history_summary
    )

    try:
        llm= _get_reviewer_llm()
    except Exception as e:
        return _fallback_review(f"could not initialize reviewer LLM: {e}"), {"prompt_tokens": 0, "completion_tokens": 0}

    last_error: Optional[str] = None
    total_usage= {"prompt_tokens":0, "completion_tokens": 0}

    for attempt in range(_MAX_PARSE_RETRIES + 1):
        messages= [
            ("system", _SYSTEM_PROMPT),
            ("user", user_msg if attempt ==0 else
            f"{user_msg}\n\nYour previous response failed to parse as valid JSON matching the schema: "
            f"{last_error}\nReturn ONLY corrected JSON, nothing else."
            )
        ]

        try:
            response= llm.invoke(messages)
        except Exception as e:
            last_error = f"LLM call failed: {e}"
            continue

        usage = getattr(response, "usage_metadata", None) or {}

        total_usage["prompt_tokens"] += usage.get("input_tokens", 0)

        total_usage["completion_tokens"] += usage.get("output_tokens", 0)

        raw= _strip_fences(response.content if isinstance(response.content, str) else str(response.content))
        try:
            data= json.loads(raw)
            review= ReviewResult.model_validate(data)

            return review, total_usage
        except (json.JSONDecodeError, ValidationError) as e:
            last_error = str(e)
            continue

    return _fallback_review(last_error or "unknown parse failure"), total_usage