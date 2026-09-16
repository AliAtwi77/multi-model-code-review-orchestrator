# import sys
# from pathlib import Path
# import streamlit as st

# sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# from benchmark.tasks import TASKS
# from agent.graph import run_orchestrator

# st.set_page_config(page_title="Generator/Reviewer Orchestrator", layout="wide")
# st.title("Generator ↔ Reviewer Orchestration Loop (MCP)")
# st.caption(
#     "One model writes code. A different-provider model reviews it through an MCP server "
#     "(review, test-execution, static-analysis tools). The orchestrator decides which findings "
#     "to act on - it does not blindly comply."
# )

# with st.sidebar:
#     st.header("Run configuration")
#     example_ids = ["(free-form task)"] + [t.id for t in TASKS]
#     choice = st.selectbox("Load a benchmark task", example_ids)
#     max_iter = st.slider("Max iterations (timeout cap, not convergence)", 1, 8, 5)
#     run_button = st.button("Run orchestrator", type="primary")

# if choice != "(free-form task)":
#     selected = next(t for t in TASKS if t.id == choice)
#     default_task, default_tests = selected.prompt, selected.test_code
# else:
#     default_task, default_tests = "", ""

# task_text = st.text_area("Task (natural language)", value=default_task, height=120)
# tests_text = st.text_area("Reference tests (pytest, optional)", value=default_tests, height=180)

# if run_button:
#     if not task_text.strip():
#         st.error("Please provide a task.")
#         st.stop()

#     with st.spinner("Running the generate → test → lint → review → disposition loop..."):
#         final_state = run_orchestrator(task=task_text, test_code=tests_text, max_iterations=max_iter)

#     st.session_state["final_state"] = final_state

# state = st.session_state.get("final_state")

# if state:
#     st.divider()
#     col1, col2, col3, col4 = st.columns(4)
#     col1.metric("Converged", "Yes" if state.get("converged") else "No")
#     col2.metric("Iterations", state.get("iteration"))
#     col3.metric("Stop reason", state.get("stop_reason") or "—")
#     total_tokens = sum(
#         v.get("prompt_tokens", 0) + v.get("completion_tokens", 0)
#         for v in state.get("token_usage_total", {}).values()
#     )
#     col4.metric("Total tokens", total_tokens)

#     st.info(f"**Convergence reason:** {state.get('convergence_reason')}")

#     tab_iters, tab_final, tab_mcp, tab_tokens = st.tabs(
#         ["Iterations", "Final result", "MCP call log", "Token usage"]
#     )

#     with tab_iters:
#         history = state.get("history", [])
#         if not history:
#             st.write("No iterations recorded.")
#         for record in history:
#             with st.expander(f"Iteration {record['iteration']}", expanded=(record is history[-1])):
#                 st.subheader("Diff from previous iteration")
#                 st.code(record["diff"] or "(first iteration - no prior code)", language="diff")

#                 st.subheader("Code")
#                 st.code(record["code"], language="python")

#                 tcol, scol = st.columns(2)
#                 with tcol:
#                     st.subheader("Test results")
#                     tr = record["test_result"]
#                     st.json(tr)
#                 with scol:
#                     st.subheader("Static analysis")
#                     st.json(record["static_result"])

#                 st.subheader("Review")
#                 review = record["review"]
#                 st.write(f"**Verdict:** {review.get('verdict')}")
#                 st.write(review.get("summary", ""))

#                 if review.get("findings"):
#                     disp_by_id = {d["finding_id"]: d for d in record["dispositions"]}
#                     for f in review["findings"]:
#                         d = disp_by_id.get(f["id"], {})
#                         badge = "✅ ACCEPTED - will be fixed" if d.get("accepted") else "🚫 DECLINED - not acted on"
#                         st.markdown(f"**[{f['severity'].upper()}] {f['category']} — `{f['location']}`**  \n{badge}")
#                         st.write(f"- Rationale: {f['rationale']}")
#                         if f.get("evidence"):
#                             st.write(f"- Evidence: {f['evidence']}")
#                         if f.get("suggested_fix"):
#                             st.write(f"- Suggested fix: {f['suggested_fix']}")
#                         st.write(f"- Disposition reason: {d.get('reason', '(none)')}")
#                         st.markdown("---")
#                 else:
#                     st.write("No findings raised this iteration.")

#     with tab_final:
#         st.subheader("Final code")
#         st.code(state.get("final_code") or state.get("current_code") or "(no code produced)", language="python")
#         st.subheader("Task")
#         st.write(state.get("task"))

#     with tab_mcp:
#         st.subheader("MCP tool call log")
#         for entry in state.get("mcp_call_log", []):
#             status = "✅" if entry["ok"] else "❌"
#             st.write(f"{status} `{entry['tool']}`" + (f" — {entry['note']}" if entry.get("note") else ""))

#     with tab_tokens:
#         st.subheader("Token usage by model")
#         st.json(state.get("token_usage_total", {}))
# else:
#     st.write("Configure a task in the sidebar (or load a benchmark example) and click **Run orchestrator**.")

import sys
from pathlib import Path

import requests
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark.tasks import TASKS

FASTAPI_URL = "http://localhost:8000"

st.set_page_config(page_title="Generator/Reviewer Orchestrator", layout="wide")

st.title("Generator ↔ Reviewer Orchestration Loop (MCP)")

st.caption(
    "One model writes code. A different-provider model reviews it through an MCP server "
    "(review, test-execution, static-analysis tools). The orchestrator decides which findings "
    "to act on - it does not blindly comply."
)

with st.sidebar:
    st.header("Run configuration")
    example_ids = ["(free-form task)"] + [t.id for t in TASKS]
    choice = st.selectbox("Load a benchmark task", example_ids)
    max_iter = st.slider("Max iterations (timeout cap, not convergence)", 1, 8, 5)
    run_button = st.button("Run orchestrator", type="primary")

if choice != "(free-form task)":
    selected = next(t for t in TASKS if t.id == choice)
    default_task, default_tests = selected.prompt, selected.test_code
else:
    default_task, default_tests = "", ""

task_text = st.text_area("Task (natural language)", value=default_task, height=120)
tests_text = st.text_area("Reference tests (pytest, optional)", value=default_tests, height=180)

if run_button:
    if not task_text.strip():
        st.error("Please provide a task.")
        st.stop()

    payload = {
        "task": task_text,
        "test_code": tests_text,
        "max_iterations": max_iter,
    }

    try:
        with st.spinner("Sending task to FastAPI → LangGraph orchestrator..."):
            response = requests.post(
                f"{FASTAPI_URL}/run",
                json=payload,
                timeout=600,
            )

        if response.status_code != 200:
            try:
                error_detail = response.json().get("detail", response.text)
            except Exception:
                error_detail = response.text

            st.error(
                f"FastAPI returned HTTP {response.status_code}: {error_detail}"
            )
            st.stop()

        result = response.json()

        if not result.get("success"):
            st.error("The orchestrator failed to complete the request.")
            st.stop()

        st.session_state["final_state"] = result["state"]

    except requests.exceptions.ConnectionError:
        st.error(
            "Could not connect to the FastAPI backend. "
            "Make sure FastAPI is running on http://localhost:8000."
        )
        st.stop()

    except requests.exceptions.Timeout:
        st.error(
            "The FastAPI request timed out. "
            "The orchestrator may still be running or may require more time."
        )
        st.stop()

    except requests.exceptions.RequestException as exc:
        st.error(f"Request to FastAPI failed: {exc}")
        st.stop()

    except Exception as exc:
        st.error(f"Unexpected error: {exc}")
        st.stop()

state = st.session_state.get("final_state")

if state:
    st.divider()

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Converged", "Yes" if state.get("converged") else "No")
    col2.metric("Iterations", state.get("iteration"))
    col3.metric("Stop reason", state.get("stop_reason") or "—")

    total_tokens = sum(
        v.get("prompt_tokens", 0) + v.get("completion_tokens", 0)
        for v in state.get("token_usage_total", {}).values()
    )

    col4.metric("Total tokens", total_tokens)

    st.info(f"**Convergence reason:** {state.get('convergence_reason')}")

    tab_iters, tab_final, tab_mcp, tab_tokens = st.tabs(
        ["Iterations", "Final result", "MCP call log", "Token usage"]
    )

    with tab_iters:
        history = state.get("history", [])

        if not history:
            st.write("No iterations recorded.")

        for record in history:
            with st.expander(
                f"Iteration {record['iteration']}",
                expanded=(record is history[-1]),
            ):
                st.subheader("Diff from previous iteration")
                st.code(
                    record["diff"] or "(first iteration - no prior code)",
                    language="diff",
                )

                st.subheader("Code")
                st.code(record["code"], language="python")

                tcol, scol = st.columns(2)

                with tcol:
                    st.subheader("Test results")
                    st.json(record["test_result"])

                with scol:
                    st.subheader("Static analysis")
                    st.json(record["static_result"])

                st.subheader("Review")
                review = record["review"]

                st.write(f"**Verdict:** {review.get('verdict')}")
                st.write(review.get("summary", ""))

                if review.get("findings"):
                    disp_by_id = {
                        d["finding_id"]: d
                        for d in record["dispositions"]
                    }

                    for finding in review["findings"]:
                        disposition = disp_by_id.get(finding["id"], {})

                        if disposition.get("accepted"):
                            badge = "✅ ACCEPTED - will be fixed"
                        else:
                            badge = "🚫 DECLINED - not acted on"

                        st.markdown(
                            f"**[{finding['severity'].upper()}] "
                            f"{finding['category']} — "
                            f"`{finding['location']}`**  \n{badge}"
                        )

                        st.write(f"- Rationale: {finding['rationale']}")

                        if finding.get("evidence"):
                            st.write(f"- Evidence: {finding['evidence']}")

                        if finding.get("suggested_fix"):
                            st.write(
                                f"- Suggested fix: {finding['suggested_fix']}"
                            )

                        st.write(
                            f"- Disposition reason: "
                            f"{disposition.get('reason', '(none)')}"
                        )
                        st.markdown("---")
                else:
                    st.write("No findings raised this iteration.")

    with tab_final:
        st.subheader("Final code")
        st.code(
            state.get("final_code")
            or state.get("current_code")
            or "(no code produced)",
            language="python",
        )

        st.subheader("Task")
        st.write(state.get("task"))

    with tab_mcp:
        st.subheader("MCP tool call log")

        for entry in state.get("mcp_call_log", []):
            status = "✅" if entry["ok"] else "❌"

            st.write(
                f"{status} `{entry['tool']}`"
                + (f" — {entry['note']}" if entry.get("note") else "")
            )

    with tab_tokens:
        st.subheader("Token usage by model")
        st.json(state.get("token_usage_total", {}))

else:
    st.write(
        "Configure a task in the sidebar (or load a benchmark example) "
        "and click **Run orchestrator**."
    )