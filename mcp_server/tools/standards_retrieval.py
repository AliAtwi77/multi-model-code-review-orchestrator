import re
from pathlib import Path
from configuration.settings import settings


_SECTION_RE = re.compile(r"^##\s+(.*)$", re.MULTILINE)

def _load_sections() -> list[tuple[str, str]]:
    text = Path(settings.coding_standard_path).read_text(encoding="utf-8")
    headers = [(m.group(1).strip(), m.start()) for m in _SECTION_RE.finditer(text)]
    sections = []

    for i, (title, start) in enumerate(headers):
        end = headers[i + 1][1] if i + 1 < len(headers) else len(text)
        sections.append((title, text[start:end].strip()))

    return sections


def retrieve_relevant_sections(code: str, task: str, top_k: int = 3) -> list[str]:
    """Keyword-overlap retrieval: score each standard section against the task description + code, return the top_k section bodies."""
    query_terms = set(re.findall(r"[a-zA-Z_]{4,}", (task + " " + code).lower()))

    scored = []

    for title, body in _load_sections():
        body_terms = set(re.findall(r"[a-zA-Z_]{4,}", body.lower()))
        overlap = len(query_terms & body_terms)
        scored.append((overlap, title, body))

    scored.sort(key=lambda x: x[0], reverse=True)
    
    return [body for _, _, body in scored[:top_k] if body]