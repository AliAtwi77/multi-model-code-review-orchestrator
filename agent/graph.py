from langgraph.graph import StateGraph, START, END
from agent.state import OrchestratorState
from agent.nodes import (
    generate_node,
    test_node,
    static_analysis_node,
    review_node,
    disposition_node,
    convergence_node,
    route_after_convergence,
)

def build_graph():
    graph= StateGraph(OrchestratorState)

    graph.add_node("generate", generate_node)
    graph.add_node("test", test_node)
    graph.add_node("static_analysis", static_analysis_node)
    graph.add_node("review", review_node)
    graph.add_node("disposition", disposition_node)
    graph.add_node("convergence_check", convergence_node)

    graph.add_edge(START, "generate")
    graph.add_edge("generate", "test")
    graph.add_edge("test", "static_analysis")
    graph.add_edge("static_analysis", "review")
    graph.add_edge("review", "disposition")
    graph.add_edge("disposition", "convergence_check")

    graph.add_conditional_edges(
        "convergence_check",
        route_after_convergence,
        {"generate": "generate", "end": END},
    )

    return graph.compile()


def run_orchestrator(task: str, test_code: str = "", max_iterations: int | None = None) -> OrchestratorState:
    from configuration.settings import settings

    app = build_graph()
    
    initial_state: OrchestratorState = {
        "task": task,
        "test_code": test_code,
        "iteration": 0,
        "max_iterations": max_iterations or settings.max_iterations,
        "history": [],
        "finding_ledger": {},
        "token_usage_total": {},
        "mcp_call_log": [],
        "converged": False,
    }
    # recursion_limit accounts for ~6 nodes per iteration
    final_state = app.invoke(initial_state, config={"recursion_limit": (initial_state["max_iterations"] + 1) * 8})
    return final_state