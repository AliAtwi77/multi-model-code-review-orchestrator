from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from agent.graph import run_orchestrator


app = FastAPI(
    title="Multi-Model Code Review Orchestrator API",
    description=(
        "FastAPI backend for the LangGraph generator/reviewer "
        "code review orchestration system."
    ),
    version="1.0.0",
)


class OrchestratorRequest(BaseModel):
    task: str = Field(..., min_length=1, description="Coding task in natural language")
    test_code: str = Field(
        default="",
        description="Optional pytest reference tests",
    )
    max_iterations: Optional[int] = Field(
        default=None,
        ge=1,
        le=8,
        description="Maximum number of orchestration iterations",
    )


class OrchestratorResponse(BaseModel):
    success: bool
    state: dict


@app.get("/")
def root():
    return {
        "name": "Multi-Model Code Review Orchestrator API",
        "status": "running",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
    }


@app.post("/run", response_model=OrchestratorResponse)
def run_orchestrator_api(request: OrchestratorRequest):
    try:
        if not request.task.strip():
            raise HTTPException(
                status_code=400,
                detail="Task cannot be empty.",
            )
        final_state = run_orchestrator(
            task=request.task,
            test_code=request.test_code,
            max_iterations=request.max_iterations,
        )

        return {
            "success": True,
            "state": final_state,
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Orchestrator execution failed: {str(exc)}",
        ) from exc