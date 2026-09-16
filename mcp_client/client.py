from typing import Any
from mcp import StdioServerParameters, ClientSession
from configuration.settings import settings
import shlex
from mcp.client.stdio import stdio_client
from datetime import timedelta
import json
import sys
import asyncio
from schemas.review import TestResult, StaticAnalysisResult, ReviewResult


class MCPToolError(RuntimeError):
    """Raised when the MCP server reports a tool-level error."""


def _unwrap_exception(exc: BaseException, depth:int= 0) ->str:
    indent = "  " * depth
    lines = [f"{indent}{type(exc).__name__}: {exc}"]
    sub_excs = getattr(exc, "exceptions", None)  # ExceptionGroup / BaseExceptionGroup
    if sub_excs:
        for sub in sub_excs:
            lines.append(_unwrap_exception(sub, depth + 1))
    elif exc.__cause__ is not None:
        lines.append(f"{indent}caused by:")
        lines.append(_unwrap_exception(exc.__cause__, depth + 1))
    return "\n".join(lines)


async def _call(tool_name: str, arguments:list[str, Any]) ->str:
    # tells mcp client how to start your mcp server
    server_params= StdioServerParameters(
        command= settings.mcp_server_cmd,
        args= shlex.split(settings.mcp_server_args)
    )

    try:
        #start the MCP server through stdio. MCP client communicates with the MCP server through standard input/output, commonly called stdio
        async with stdio_client(server_params) as (read, write):
            #stablish the MCP client session over the read and write communication streams
            async with ClientSession(read, write) as session:
                #before using the MCP server, the client needs to perform the MCP initialization handshake
                await session.initialize()

                result= await session.call_tool(
                    tool_name,
                    arguments,
                    read_timeout_seconds= timedelta(seconds=settings.mcp_call_timeout_seconds)
                )
                #extract text from the mcp response
                text_parts= [c.text for c in result.content if hasattr(c, "text")]

                if not text_parts:
                    raise MCPToolError(f"Tool '{tool_name}' returned no content.")

                payload= text_parts[0]
                parsed= json.loads(payload)

                #checks for a very specific error format
                if isinstance(parsed, dict) and "error" in parsed and len(parsed) == 1:
                    raise MCPToolError(f"Tool '{tool_name}' failed: {parsed['error']}")
                return payload
    except MCPToolError:
        raise
    except BaseException as e:  # noqa: BLE001 - deliberately broad: unwrap and re-raise with detail
        detail = _unwrap_exception(e)
        # Always visible on stderr regardless of log level, since this is exactly
        # the information needed to diagnose a transport-level failure.
        print(f"[mcp_client] '{tool_name}' transport failure, unwrapped:\n{detail}", file=sys.stderr)
        raise MCPToolError(f"Tool '{tool_name}' transport failure:\n{detail}") from e


def _run(coro):
    """Run an async coroutine from sync LangGraph node code.
    synchronous langgraph node -> _run() -> asynchronous mcp code -> _call"""
    try:
        loop= asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Rare (e.g. inside Streamlit's own event loop) - use a fresh loop in a thread.
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            return ex.submit(lambda: asyncio.run(coro)).result()
    return asyncio.run(coro)


class OrchestratorMCPClient:

    def call_run_tests(self, solution_code:str, test_code: str) -> TestResult:
        payload= _run(_call("run_tests", {"solution_code": solution_code, "test_code": test_code}))

        return TestResult.model_validate_json(payload)


    def call_run_static_analysis(self, solution_code: str) -> StaticAnalysisResult:
        payload= _run(_call("run_static_analysis", {"solution_code": solution_code}))

        return StaticAnalysisResult.model_validate_json(payload)


    def call_review_code(
        self,
        code: str,
        task: str,
        iteration: int,
        test_result: TestResult,
        static_result: StaticAnalysisResult,
        history_summary: str,
    ) -> tuple[ReviewResult, dict]:
        payload = _run(_call("review_code", {
            "code": code,
            "task": task,
            "iteration": iteration,
            "test_result_json": test_result.model_dump_json(),
            "static_result_json": static_result.model_dump_json(),
            "history_summary": history_summary,
        }))

        data= json.loads(payload)
        return ReviewResult.model_validate(data["review"]), data.get("token_usage", {})



mcp_client = OrchestratorMCPClient()