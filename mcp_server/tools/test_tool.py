from schemas.review import TestResult, TestCaseResult
from mcp_server.sandbox import run_python_subprocess, make_scratch_dir
import json
import shutil


def run_tests(solution_code:str, test_code:str) ->TestResult:
    if not test_code or not test_code.strip():
        return TestResult(
            ran= False,
            error_message="No tests were provided for this task.",
        )
    
    #Create a temporary sandbox
    scratch= make_scratch_dir()
    try:
        #Write the generated solution
        (scratch / "solution.py").write_text(solution_code, encoding="utf-8")
        #Write the tests
        (scratch / "test_solution.py").write_text(test_code,encoding="utf-8",)
        #define pytest report location
        report_path = scratch / "report.json"

        #run pytest
        result= run_python_subprocess(
            args=[
                "-m",
                "pytest",
                "test_solution.py",
                "-q",
                "--json-report",
                f"--json-report-file={report_path}",
                "--timeout=8",
            ],
            cwd= scratch,
            timeout= 20
        )

        #if thesandbox's outer 20-second timeout was reached
        if result.timed_out:
            return TestResult(
                ran= True,
                timed_out= True,
                stdout_tail= (result.stdout + result.stderr)[-2000:],
                error_message=(
                    "Test execution exceeded the sandbox timeout "
                    "(possible infinite loop or unbounded blocking call)."
                ),
            )

        #Check whether pytest produced a report
        if not report_path.exists():
            return TestResult(
                ran=True,
                crashed=True,
                stdout_tail=(result.stdout + result.stderr)[-2000:],
                error_message=(
                    f"pytest produced no report. "
                    f"returncode={result.returncode}; "
                    f"stderr={result.stderr[-1000:]}"
                ),
            )

        #read json report
        report= json.loads(report_path.read_text(encoding="utf-8"))
        #extract summary
        summary= report.get("summary", {})

        cases= []
        #prcoess every individual test
        for test in report.get("tests", []):
            outcome= test.get("outcome", "unknown")
            message = None

            if outcome != "passed":
                message= ((test.get("call", {}) or {}).get("longrepr"))
            cases.append(
                TestCaseResult(
                    name= test.get("nodeid", "unknown"),
                    outcome= outcome,
                    message= message
                )
            )

        return TestResult(
            ran=True,
            passed=summary.get("passed", 0),
            failed=summary.get("failed", 0),
            errored=summary.get("error", 0),
            duration_seconds=report.get("duration", 0.0),
            cases=cases,
            stdout_tail=result.stdout[-2000:],
        )
    
    except json.JSONDecodeError as e:
        return TestResult(
            ran=True,
            crashed=True,
            error_message=f"Invalid pytest JSON report: {e}",
        )

    except Exception as e:
        return TestResult(
            ran=False,
            crashed=True,
            error_message=f"{type(e).__name__}: {e}",
        )

    finally:
        shutil.rmtree(scratch, ignore_errors=True)