from configuration.settings import settings
import re


_SYSTEM_PROMPT = """You are a careful Python engineer. Given a task, write a single, complete, \
self-contained Python module named `solution.py` that solves it. Output ONLY the code, no prose, \
no markdown fences. Include type hints and a module docstring. Do not include tests unless asked."""

_REVISE_TEMPLATE = """## Task
{task}

## Current code
```python
{code}
```

## Findings you must address (already vetted - act on all of these)
{accepted_findings}

## Findings you may ignore (rejected by the orchestrator's disagreement resolver - do NOT act on these)
{rejected_findings}

Rewrite the complete module with the accepted findings fixed. Do not regress anything that was
already correct. Output ONLY the corrected code, no prose, no markdown fences.
"""

def _get_generator_llm():
    provider = settings.generator_provider.lower()
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=settings.generator_model, api_key=settings.openai_api_key, temperature=0)
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=settings.generator_model, api_key=settings.anthropic_api_key,
                              temperature=0, max_tokens=3000)
    else:
        raise ValueError(f"Unsupported generator_provider: {provider}")


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(python)?\n", "", text)
    text = re.sub(r"\n```$", "", text)
    return text.strip()


def generate_initial(task: str) -> tuple[str, dict]:
    llm = _get_generator_llm()
    response = llm.invoke([("system", _SYSTEM_PROMPT), ("user", task)])
    usage = getattr(response, "usage_metadata", None) or {}
    code = _strip_fences(response.content if isinstance(response.content, str) else str(response.content))

    return code, {"prompt_tokens": usage.get("input_tokens", 0), "completion_tokens": usage.get("output_tokens", 0)}



def revise(task: str, code: str, accepted_findings: list[dict], rejected_findings: list[dict]) -> tuple[str, dict]:
    llm = _get_generator_llm()

    def _fmt(findings: list[dict]) -> str:
        if not findings:
            return "(none)"
        return "\n".join(
            f"- [{f.get('severity')}] {f.get('category')} at {f.get('location')}: {f.get('rationale')}"
            f" (fix: {f.get('suggested_fix') or 'use your judgement'})"
            for f in findings
        )

    user_msg = _REVISE_TEMPLATE.format(
        task=task,
        code=code,
        accepted_findings=_fmt(accepted_findings),
        rejected_findings=_fmt(rejected_findings),
    )
    response = llm.invoke([("system", _SYSTEM_PROMPT), ("user", user_msg)])
    usage = getattr(response, "usage_metadata", None) or {}
    new_code = _strip_fences(response.content if isinstance(response.content, str) else str(response.content))
    
    return new_code, {"prompt_tokens": usage.get("input_tokens", 0), "completion_tokens": usage.get("output_tokens", 0)}