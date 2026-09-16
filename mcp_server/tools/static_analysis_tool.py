from pathlib import Path
import subprocess
from schemas.review import StaticIssue
import sys
import json
from schemas.review import StaticAnalysisResult, StaticIssue
from tempfile import mkdtemp
import shutil

_TIMEOUT = 20


def _run(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    try:
        p= subprocess.run(
            cmd, #command to execute
            cwd=str(cwd), #directory where the command runs
            capture_output=True, #capture stdout and stderr
            text=True, 
            timeout=_TIMEOUT
        )
        return p.returncode, p.stdout, p.stderr
    
    except subprocess.TimeoutExpired:
        return -1, "", f"{cmd[0]} timed out after {_TIMEOUT}s"
    except FileNotFoundError:
        return -2, "", f"{cmd[0]} is not installed"


def _run_ruff(cwd: Path) -> list[StaticIssue]:
    """Ruff is used for linting and code-quality correctness check"""

    rc, out, err= _run([sys.executable, "-m", "ruff", "check", "solution.py", "--output-format=json"], cwd)
    issues=[]
    if out.strip():
        try:
            for item in json.loads(out):
                issues.append(
                    StaticIssue(
                        tool="ruff",
                        rule_id=item.get("code") or "unknown",
                        severity="error" if (item.get("code") or "").startswith(("E", "F")) else "warning", location=f"solution.py:{item.get('location', {}).get('row', '?')}",
                        message= item.get("message", "")
                    )
                )
        except json.JSONDecodeError:
            pass
    return issues


def _run_bandit(cwd: Path) -> list[StaticIssue]:
    """Bandit detects potentially dangerous code patters(weak_encruption, passwords,...) checks security oversights"""

    rc, out, err = _run([sys.executable, "-m", "bandit", "-f", "json", "-q", "solution.py"], cwd)
    issues = []
    if out.strip():
        try:
            data = json.loads(out)
            for item in data.get("results", []):
                issues.append(
                    StaticIssue(
                        tool="bandit",
                        rule_id=item.get("test_id", "unknown"),
                        severity=item.get("issue_severity", "low").lower(),
                        location=f"solution.py:{item.get('line_number', '?')}",
                        message=item.get("issue_text", ""),
                    )
                )
        except json.JSONDecodeError:
            pass
    return issues


def _run_mypy(cwd: Path) -> list[StaticIssue]:
    """Mypy performs static type checking"""

    rc, out, err = _run([sys.executable, "-m", "mypy", "solution.py", "--no-error-summary", "--no-color-output"], cwd)
    issues = []
    for line in out.splitlines():
        # format: solution.py:12: error: message  [code]
        parts = line.split(":", 3)
        if len(parts) >= 4 and parts[1].strip().isdigit():
            severity = "error" if "error" in parts[2] else "warning"
            issues.append(
                StaticIssue(
                    tool="mypy",
                    rule_id="type-check",
                    severity=severity,
                    location=f"solution.py:{parts[1].strip()}",
                    message=parts[3].strip(),
                )
            )
    return issues


def run_static_analysis(solution_code:str) -> StaticAnalysisResult:
    scratch= Path(mkdtemp(prefix="orch_lint_"))
    try:
        (scratch / "solution.py").write_text(solution_code, encoding="utf-8")
        issues: list[StaticIssue] = []
        errors = []
        for fn in (_run_ruff, _run_bandit, _run_mypy):
            try:
                issues.extend(fn(scratch))
            except Exception as e:
                errors.append(f"{fn.__name__}: {e}")

        return StaticAnalysisResult(
            ran=True,
            issues=issues,
            error_message="; ".join(errors) if errors else None,
        )
    finally:
        shutil.rmtree(scratch, ignore_errors=True)  