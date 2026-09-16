import os
from dataclasses import dataclass
from pathlib import Path
from configuration.settings import settings
import time
import subprocess
import sys
import tempfile

_SECRET_MARKERS = ("KEY", "SECRET", "TOKEN", "PASSWORD", "CREDENTIAL")


def _sandboxed_env() ->dict[str,str]:
    env = dict(os.environ)
    for key in list(env.keys()):
        if any(marker in key.upper() for marker in _SECRET_MARKERS):
            env.pop(key, None)
    return env



@dataclass
class SandboxRunResult:
    returncode: int #0 means success, non-zero means something went wrong
    stdout: str #stores normal output from the generated program
    stderr: str #stores error output
    timed_out: bool #records whether the process exceeded its allowed execution time
    duration_seconds: float #how long the subprocess ran


def run_python_subprocess(
        args: list[str],
        cwd: Path,
        timeout: int | None = None
) -> SandboxRunResult:
    timeout= timeout or settings.sandbox_timeout_seconds

    start= time.monotonic()
    try:
        proc= subprocess.run(
            [sys.executable, *args],
            cwd= str(cwd),
            env= _sandboxed_env(),
            capture_output= True,
            text= True,
            timeout= timeout,
            stdin= subprocess.DEVNULL
        )

        duration= time.monotonic() - start

        return SandboxRunResult(
            returncode= proc.returncode,
            stdout= proc.stdout[-8000:],
            stderr= proc.stderr[-8000:],
            timed_out= False,
            duration_seconds= duration
        )
    except subprocess.TimeoutExpired as e:
        duration = time.monotonic() - start
        return SandboxRunResult(
            returncode=-1,
            stdout=(e.stdout or "")[-8000:] if isinstance(e.stdout, str) else "",
            stderr=(e.stderr or "")[-8000:] if isinstance(e.stderr, str) else "",
            timed_out=True,
            duration_seconds=duration,
        )


def make_scratch_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="orch_sandbox_"))