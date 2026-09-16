<div align="center">

<h1>Multi-Model Code Review Orchestrator</h1>

[![LangGraph](https://img.shields.io/badge/LangGraph-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white)](https://www.langchain.com/langgraph)
[![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white)](https://www.langchain.com/)
[![Model Context Protocol](https://img.shields.io/badge/MCP-000000?style=for-the-badge&logo=anthropic&logoColor=white)](https://modelcontextprotocol.io/)
[![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white)](https://openai.com/)
[![Anthropic Claude](https://img.shields.io/badge/Anthropic_Claude-D97706?style=for-the-badge&logo=anthropic&logoColor=white)](https://www.anthropic.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Pydantic](https://img.shields.io/badge/Pydantic-E92063?style=for-the-badge&logo=pydantic&logoColor=white)](https://docs.pydantic.dev/)
[![pytest](https://img.shields.io/badge/pytest-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white)](https://docs.pytest.org/)
[![Ruff](https://img.shields.io/badge/Ruff-D7FF64?style=for-the-badge&logo=ruff&logoColor=black)](https://docs.astral.sh/ruff/)
[![mypy](https://img.shields.io/badge/mypy-2A629A?style=for-the-badge&logo=python&logoColor=white)](https://mypy-lang.org/)
[![Bandit](https://img.shields.io/badge/Bandit-FF6B6B?style=for-the-badge&logo=python&logoColor=white)](https://github.com/PyCQA/bandit)

</div>



# Generator ↔ Reviewer Orchestration Loop

## MCP + LangGraph + FastAPI + Streamlit

A code-generation and review system where **two models from different providers** work together in an iterative generator ↔ reviewer loop.

Code written by a model and reviewed by the same model can inherit the same blind spots. The premise of this assignment is that a **second model, from a different provider, reviewing the first model's output, can identify issues that the original model may not see**.

The goal of this project is to build an **orchestrator that implements this loop, connects its components through the Model Context Protocol (MCP), and produces evidence that the loop actually improves the code rather than merely generating additional conversation about it**.

The system uses:

* **LangGraph** for orchestration and state management
* **MCP** for communication between the orchestrator and code-review/testing tools
* **OpenAI** as the generator model by default
* **Anthropic** as the reviewer model by default
* **FastAPI** as the backend API
* **Streamlit** as the frontend
* **pytest** for executing reference tests
* **Ruff, mypy, and Bandit** for static analysis

---

## Table of Contents

- [1. Project Objective](#1-project-objective)
- [2. High-Level Architecture](#2-high-level-architecture)
- [3. Project Structure](#3-project-structure)
- [4. Core Application Components & Files](#4-core-application-components--files)
  - [`main.py` (Application Entry Point)](#mainpy-application-entry-point)
  - [`api/main.py` (FastAPI Backend)](#apimainpy-fastapi-backend)
  - [`frontend/app.py` (Streamlit Frontend)](#frontendapppy-streamlit-frontend)
  - [`configuration/settings.py` (Configuration)](#configurationsettingspy-configuration)
  - [`schemas/review.py` (Schemas)](#schemasreviewpy-schemas)
  - [`mcp_server/server.py` (MCP Server)](#mcp_serverserverpy-mcp-server)
  - [`mcp_server/sandbox.py` (Sandbox)](#mcp_serversandboxpy-sandbox)
  - [`mcp_server/tools/review_tool.py` (Review Tool)](#mcp_servertoolsreview_toolpy-review-tool)
  - [`mcp_server/tools/test_tool.py` (Test Tool)](#mcp_servertoolstest_toolpy-test-tool)
  - [`mcp_server/tools/static_analysis_tool.py` (Static Analysis Tool)](#mcp_servertoolsstatic_analysis_toolpy-static-analysis-tool)
  - [`mcp_server/tools/standards_retrieval.py` (Standards Retrieval)](#mcp_servertoolsstandards_retrievalpy-standards-retrieval)
  - [`mcp_client/client.py` (MCP Client)](#mcp_clientclientpy-mcp-client)
  - [`agent/state.py` (Agent State)](#agentstatepy-agent-state)
  - [`agent/generator.py` (Generator Model Wrapper)](#agentgeneratorpy-generator-model-wrapper)
  - [`agent/disagreement.py` (Disagreement Resolution)](#agentdisagreementpy-disagreement-resolution)
  - [`agent/convergence.py` (Convergence Check)](#agentconvergencepy-convergence-check)
  - [`agent/nodes.py` (LangGraph Nodes)](#agentnodespy-langgraph-nodes)
  - [`agent/graph.py` (LangGraph Graph)](#agentgraphpy-langgraph-graph)
  - [`standards/coding_standard.md` (Coding Standards)](#standardscoding_standardmd-coding-standards)
  - [`benchmark/task.py` (Benchmark Tasks)](#benchmarktaskpy-benchmark-tasks)
- [5. Complete Orchestration Loop](#5-complete-orchestration-loop)
- [6. Frontend → API → Agent Flow](#6-frontend--api--agent-flow)
- [7. Setup and Execution Guide](#7-setup-and-execution-guide)
  - [Environment Setup](#environment-setup)
  - [Running the Application](#running-the-application)
  - [Manual Development Mode](#manual-development-mode)
  - [Running the MCP Server](#running-the-mcp-server)
- [8. Testing the Project](#8-testing-the-project)
- [9. Robustness](#9-robustness)
- [10. Design Decisions](#10-design-decisions)
- [11. Important Limitation](#11-important-limitation)
- [12. Quick Start](#12-quick-start)
- [13. Summary](#13-summary)

---

# 1. Project Objective

The project implements a loop in which:

1. A generator model receives a coding task.
2. The generator produces an initial solution.
3. The generated code is executed against reference tests.
4. Static analysis is performed.
5. A second model from a different provider reviews the generated code.
6. The orchestrator evaluates the reviewer's findings against the actual tool evidence.
7. Supported findings are sent back to the generator.
8. The generator revises the code.
9. The process repeats until the solution converges or the maximum number of iterations is reached.
10. Benchmark results can be used to compare the orchestrated approach with a generator-only baseline.

The important design principle is:

> **The reviewer does not automatically decide what should change. The orchestrator evaluates reviewer findings against executable evidence.**

The project therefore combines:

```text
Generator
    +
Reviewer
    +
Tests
    +
Static Analysis
    +
Disagreement Resolution
    +
Convergence
```

to create an iterative code-improvement system.

# 2. High-Level Architecture

The complete application is organized into four main layers:

Plaintext

```
┌──────────────────────┐
│        USER          │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Streamlit Frontend  │
│    frontend/app.py   │
└──────────┬───────────┘
           │ HTTP
           ▼
┌──────────────────────┐
│    FastAPI Backend   │
│      api/main.py     │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│   LangGraph Agent    │
│       agent/         │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│      MCP Client      │
│   mcp_client/        │
└──────────┬───────────┘
           │ MCP / stdio
           ▼
┌──────────────────────┐
│      MCP Server      │
│    mcp_server/       │
└──────────┬───────────┘
           │
      ┌─────┼─────────────┐
      │     │             │
      ▼     ▼             ▼
   Review  Tests    Static Analysis
    Tool    Tool          Tool
```

The root `main.py` starts the FastAPI backend first, waits for it to become healthy, and then starts the Streamlit frontend.

The MCP server is started separately before launching the application.

# 3. Project Structure

Plaintext

```
project-root/
│
├── main.py
│
├── api/
│   └── main.py
│
├── configuration/
│   └── settings.py
│
├── schemas/
│   ├── __init__.py
│   └── review.py
│
├── mcp_server/
│   ├── server.py
│   ├── sandbox.py
│
│   └── tools/
│       ├── review_tool.py
│       ├── test_tool.py
│       ├── static_analysis_tool.py
│       └── standards_retrieval.py
│
├── mcp_client/
│   └── client.py
│
├── agent/
│   ├── state.py
│   ├── generator.py
│   ├── disagreement.py
│   ├── convergence.py
│   ├── nodes.py
│   └── graph.py
│
├── standards/
│   └── coding_standard.md
│
├── benchmark/
│   └── task.py
│
├── frontend/
│   └── app.py
│
├── tests/
│   ├── test_disagreement.py
│   ├── test_convergence.py
│   └── test_orchestrator_failures.py
│
├── requirements.txt
├── .env.example
└── README.md
```

# 4. Core Application Components & Files

### `main.py` (Application Entry Point)

`main.py` is the **main entry point for the complete application**.

It starts:

- FastAPI backend
- Streamlit frontend

The startup sequence is:

Plaintext

```
python main.py
     │
     ▼
Start FastAPI
     │
     ▼
Wait for /health
     │
     ▼
FastAPI ready
     │
     ▼
Start Streamlit
     │
     ▼
Application ready
```

The launcher uses Python's `subprocess` module to start both processes.

It also monitors both processes.

If either process stops, the launcher shuts down the remaining process.

When the user presses:

Plaintext

```
Ctrl+C
```

the launcher terminates both FastAPI and Streamlit.

### `api/main.py` (FastAPI Backend)

`api/main.py` contains the FastAPI application.

FastAPI acts as the backend between the Streamlit frontend and the LangGraph agent.

The request flow is:

Plaintext

```
Streamlit
    │
    │ HTTP request
    ▼
FastAPI
    │
    ▼
LangGraph Agent
    │
    ▼
Result
    │
    ▼
FastAPI response
    │
    ▼
Streamlit
```

The backend exposes the API endpoints required by the frontend, including the health endpoint used by the root launcher.

The health endpoint allows `main.py` to verify that FastAPI is ready before starting Streamlit.

FastAPI also provides automatically generated API documentation.

Once the application is running:

Plaintext

```
[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
```

can be used to inspect and test the API.

### `frontend/app.py` (Streamlit Frontend)

`frontend/app.py` contains the Streamlit user interface.

The frontend is responsible for:

- Receiving the user's coding task
- Selecting benchmark tasks
- Sending requests to FastAPI
- Displaying orchestration results
- Showing generated code
- Showing iterations
- Showing code changes
- Showing reviewer findings
- Showing finding dispositions
- Showing test results
- Showing static-analysis results
- Showing MCP activity
- Showing the final generated solution

The frontend does **not** directly run the LangGraph orchestration.

Instead:

Plaintext

```
Streamlit
    │
    │ HTTP
    ▼
FastAPI
    │
    ▼
Agent
```

This keeps the user interface separate from the backend and orchestration logic.

### `configuration/settings.py` (Configuration)

This file contains the application's configuration.

Settings are loaded from environment variables and `.env`.

The configuration includes settings for:

- Generator provider
- Generator model
- Reviewer provider
- Reviewer model
- API keys
- Maximum iterations
- MCP timeout
- Sandbox timeout
- Other runtime settings

A key requirement is that the generator and reviewer must use **different providers**.

For example:

Plaintext

```
Generator → OpenAI
Reviewer  → Anthropic
```

The application validates this requirement.

This ensures that the review is performed by a different model/provider rather than the same model reviewing its own output.

### `schemas/review.py` (Schemas)

This module defines the structured Pydantic models used by the project.

Important schemas include:

Plaintext

```
Finding
ReviewResult
TestResult
StaticAnalysisResult
Disposition
```

These schemas provide structured communication between:

- Reviewer
- MCP tools
- MCP server
- MCP client
- LangGraph agent

For example, a reviewer finding can contain:

Plaintext

```
severity
category
location
rationale
suggested_fix
evidence
```

Using structured schemas makes the system more reliable than passing unstructured text between components.

### `mcp_server/server.py` (MCP Server)

This is the project's MCP server.

It exposes the main tools used by the orchestrator:

Plaintext

```
review_code
run_tests
run_static_analysis
```

The server uses **FastMCP** and stdio transport.

The MCP tools are implemented as Python functions and exposed through MCP.

The function signatures and type hints define the tool input contracts.

The MCP server is a required component of the application architecture.

### `mcp_server/sandbox.py` (Sandbox)

Generated code is treated as untrusted code.

Therefore, generated code is not executed directly inside the main application process.

Instead, the sandbox runs generated code in a separate subprocess.

The sandbox provides protections such as:

- Separate process execution
- Timeout protection
- Restricted environment
- Captured stdout/stderr

For example, if a generated solution contains:

Python

```
while True:
    pass
```

the timeout prevents the entire orchestrator from hanging indefinitely.

The sandbox therefore provides a controlled environment for executing model-generated code.

### `mcp_server/tools/review_tool.py` (Review Tool)

This tool handles communication with the reviewer model.

The reviewer receives:

- Coding task
- Generated code
- Test results
- Static-analysis results
- Relevant coding-standard sections

The reviewer produces structured findings.

The output is validated against the project's Pydantic schemas.

Malformed reviewer responses are retried.

If the reviewer continues returning invalid output, the system falls back to a safe non-blocking review.

This prevents malformed model output from breaking the entire orchestration loop.

### `mcp_server/tools/test_tool.py` (Test Tool)

This tool executes the reference tests against the generated solution.

Conceptually:

Plaintext

```
Generated Code
      │
      ▼
solution.py
      │
      +
      │
Reference Tests
      │
      ▼
pytest
      │
      ▼
TestResult
```

The test results are then provided to the orchestrator and reviewer.

This gives the system executable evidence about whether the generated code actually satisfies the required behavior.

### `mcp_server/tools/static_analysis_tool.py` (Static Analysis Tool)

This tool performs static analysis on the generated code.

The project uses:

Plaintext

```
ruff
mypy
bandit
```

The results are converted into a structured `StaticAnalysisResult`.

These results can then be used as evidence when evaluating reviewer findings.

### `mcp_server/tools/standards_retrieval.py` (Standards Retrieval)

This module retrieves relevant sections from:

Plaintext

```
standards/coding_standard.md
```

The entire coding standard is not unnecessarily inserted into every reviewer prompt.

Instead, relevant sections are retrieved based on the current task and code.

The retrieved sections are then provided to the reviewer as additional grounding.

### `mcp_client/client.py` (MCP Client)

The MCP client is the communication layer between the LangGraph agent and the MCP server.

It communicates with the MCP server through:

Plaintext

```
ClientSession
stdio_client
```

The agent uses the client to call:

Plaintext

```
review_code
run_tests
run_static_analysis
```

The architecture is therefore:

Plaintext

```
LangGraph Agent
      │
      ▼
MCP Client
      │
      │ MCP / stdio
      ▼
MCP Server
      │
      ├── review_code
      ├── run_tests
      └── run_static_analysis
```

### `agent/state.py` (Agent State)

Defines the `OrchestratorState`.

This is the central state object used throughout the LangGraph workflow.

It contains information such as:

- Current task
- Generated code
- Previous code
- Test results
- Static-analysis results
- Reviewer findings
- Finding dispositions
- Current iteration
- Token usage
- Stop reason
- Final status

Each LangGraph node reads from and updates this shared state.

### `agent/generator.py` (Generator Model Wrapper)

Contains the generator model wrapper.

The generator has two main responsibilities.

#### Initial generation

It creates the first solution for the user's coding task.

#### Code revision

If supported reviewer findings require changes, the generator receives the relevant feedback and produces a revised solution.

The generator therefore participates in every iteration of the improvement loop.

### `agent/disagreement.py` (Disagreement Resolution)

This module implements the project's disagreement-resolution logic.

A reviewer finding is **not automatically accepted**.

The orchestrator checks the finding against available evidence.

The logic considers:

Plaintext

```
Reviewer finding
       +
Test results
       +
Static-analysis results
       +
Reviewer evidence
       +
Previous review decisions
```

Examples of the decision process include:

Plaintext

```
Finding matches a failing test
        ↓
Accepted

Finding matches a static-analysis issue
        ↓
Accepted

Blocking finding has no evidence
and tests/static analysis are clean
        ↓
Downgraded / not acted on

Reviewer reverses an earlier decision
without new evidence
        ↓
Rejected

Advisory finding
        ↓
Logged but does not block convergence
```

This is one of the central ideas of the project:

> **The orchestrator does not blindly obey the reviewer.**

### `agent/convergence.py` (Convergence Check)

This module determines whether the orchestration loop has converged.

Convergence is not simply defined as reaching the maximum number of iterations.

For example:

Plaintext

```
Tests pass
+
Static analysis is clean
+
No supported blocking findings remain
        ↓
Converged
```

If the maximum number of iterations is reached without convergence:

Plaintext

```
Maximum iterations reached
        ↓
Stopped
```

This is recorded separately as:

Plaintext

```
max_iterations
```

Therefore:

Plaintext

```
Converged ≠ Maximum iterations reached
```

An iteration limit is a safety mechanism, not evidence that the code is correct.

### `agent/nodes.py` (LangGraph Nodes)

Contains the individual nodes used by the LangGraph workflow.

The nodes implement the main stages:

Plaintext

```
Generate
   ↓
Test
   ↓
Static Analysis
   ↓
Review
   ↓
Disposition
   ↓
Convergence Check
```

If the solution has not converged, the workflow returns to the generator.

Each node operates using the shared `OrchestratorState`.

### `agent/graph.py` (LangGraph Graph)

Builds the LangGraph `StateGraph` and connects the nodes together.

The workflow is:

Plaintext

```
             ┌───────────┐
             │  Generate │
             └─────┬─────┘
                   │
                   ▼
             ┌───────────┐
             │   Tests   │
             └─────┬─────┘
                   │
                   ▼
             ┌───────────────┐
             │Static Analysis│
             └───────┬───────┘
                     │
                     ▼
              ┌────────────┐
              │   Review   │
              └──────┬─────┘
                     │
                     ▼
              ┌───────────────┐
              │  Disposition  │
              └───────┬───────┘
                     │
                     ▼
              ┌───────────────┐
              │  Convergence  │
              │     Check     │
              └───────┬───────┘
                     │
                 ┌────┴────┐
                 │         │
                 ▼         ▼
             Converged   Not Converged
                 │         │
                 ▼         │
                END ◄──────┘
```

### `standards/coding_standard.md` (Coding Standards)

Contains the coding standards used to ground the reviewer.

The standards are retrieved dynamically rather than always providing the entire document to the model.

The retrieval flow is:

Plaintext

```
Task + Generated Code
        │
        ▼
Standards Retrieval
        │
        ▼
Relevant Sections
        │
        ▼
Reviewer Model
```

This provides task-specific guidance while keeping the reviewer context focused.

### `benchmark/task.py` (Benchmark Tasks)

The benchmark currently contains the benchmark task definitions in:

Plaintext

```
benchmark/task.py
```

The benchmark is used to evaluate whether the orchestration process provides an improvement compared with generating code without the reviewer loop.

The benchmark tasks represent different coding scenarios and seeded defect categories.

The evaluation concept is:

Plaintext

```
Generator-only
     VS
Generator + Reviewer
```

The purpose is not simply to show that the reviewer produces comments.

The goal is to obtain evidence about whether the complete orchestration process improves the resulting code.

# 5. Complete Orchestration Loop

The overall loop can be summarized as:

Plaintext

```
Generate
   ↓
Run Tests
   ↓
Run Static Analysis
   ↓
Reviewer Model
   ↓
Evaluate Reviewer Findings
   ↓
Accept / Downgrade / Reject Findings
   ↓
Convergence Check
   │
   ├── Converged → END
   │
   └── Not Converged → Generate Revision
                           │
                           └── repeat
```

The reviewer is therefore one component in the decision-making process rather than the final authority.

# 6. Frontend → API → Agent Flow

When the user submits a task through the Streamlit interface, the request follows this path:

Plaintext

```
                 USER
                  │
                  ▼
         ┌──────────────────┐
         │ Streamlit        │
         │ frontend/app.py  │
         └────────┬─────────┘
                  │
                  │ HTTP
                  ▼
         ┌──────────────────┐
         │ FastAPI          │
         │ api/main.py      │
         └────────┬─────────┘
                  │
                  ▼
         ┌──────────────────┐
         │ LangGraph Agent  │
         │ agent/           │
         └────────┬─────────┘
                  │
                  ▼
         ┌──────────────────┐
         │ MCP Client       │
         │ mcp_client/      │
         └────────┬─────────┘
                  │
                  │ MCP / stdio
                  ▼
         ┌──────────────────┐
         │ MCP Server       │
         │ mcp_server/      │
         └────────┬─────────┘
                  │
         ┌────────┼──────────┐
         ▼        ▼          ▼
       Review   Tests    Static Analysis
        Tool     Tool         Tool
         │        │           │
         ▼        ▼           ▼
      Reviewer   pytest    ruff/mypy/bandit
         │        │           │
         └────────┼───────────┘
                  │
                  ▼
         Disagreement Resolver
                  │
                  ▼
         Convergence Check
                  │
            ┌──────┴──────┐
            │             │
            ▼             ▼
        Converged     Not Converged
            │             │
            ▼             │
           END ◄──────────┘
```

# 7. Setup and Execution Guide

### Environment Setup

Create a virtual environment:

Bash

```
python -m venv .venv
```

Activate it on Windows:

Bash

```
.venv\Scripts\activate
```

On Linux/macOS:

Bash

```
source .venv/bin/activate
```

Install the project dependencies:

Bash

```
pip install -r requirements.txt
```

Create the environment file.

Windows:

Bash

```
copy .env.example .env
```

Linux/macOS:

Bash

```
cp .env.example .env
```

Then configure the required API keys and model settings in `.env`.

For example:

Plaintext

```
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...

GENERATOR_PROVIDER=openai
REVIEWER_PROVIDER=anthropic
```

The generator and reviewer providers must be different.

### Running the Application

#### Startup Order

The application should be started in the following order:

Plaintext

```
1. Start MCP Server
        ↓
2. Start FastAPI + Streamlit
        ↓
3. Open Streamlit
```

##### Step 1 — Start the MCP Server

From the project root, run:

Bash

```
python -m mcp_server.server
```

The MCP server uses stdio transport and provides the tools required by the orchestrator.

Keep this process running.

##### Step 2 — Start the Application

Open a **second terminal** in the project root.

Activate the virtual environment if necessary, then run:

Bash

```
python main.py
```

The root launcher will:

1. Start FastAPI.
2. Wait for FastAPI's `/health` endpoint.
3. Confirm that FastAPI is ready.
4. Start Streamlit.
5. Monitor both processes.
6. Shut down both processes when `Ctrl+C` is pressed.

The expected startup sequence is:

Plaintext

```
Starting FastAPI backend...
Waiting for FastAPI to become available...
FastAPI is ready.
Starting Streamlit frontend...

FastAPI: [http://127.0.0.1:8000](http://127.0.0.1:8000)
API Docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
Streamlit: http://localhost:8501

Press Ctrl+C to stop the application.
```

##### Step 3 — Open Streamlit

Open:

Plaintext

```
http://localhost:8501
```

The Streamlit interface is now ready to accept coding tasks.

##### FastAPI Documentation

The FastAPI Swagger documentation is available at:

Plaintext

```
[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
```

##### Stopping the Application

To stop the application, press:

Plaintext

```
Ctrl+C
```

The root `main.py` launcher will terminate both the Streamlit and FastAPI processes.

The MCP server should also be stopped separately with `Ctrl+C` in its terminal.

### Manual Development Mode

For development and debugging, FastAPI and Streamlit can also be started separately.

First start the MCP server:

Bash

```
python -m mcp_server.server
```

Then start FastAPI in another terminal:

Bash

```
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Then start Streamlit in another terminal:

Bash

```
streamlit run frontend/app.py
```

This method is useful when debugging the frontend and backend independently.

For normal usage, the recommended method is:

Plaintext

```
Terminal 1:
python -m mcp_server.server

Terminal 2:
python main.py
```

### Running the MCP Server

The MCP server can be started directly with:

Bash

```
python -m mcp_server.server
```

The server provides the tools required by the orchestrator:

Plaintext

```
review_code
run_tests
run_static_analysis
```

It uses stdio transport.

The MCP server should be running before starting the main application.

The normal startup arrangement is:

Plaintext

```
┌──────────────────────────┐
│ Terminal 1               │
│                          │
│ python -m                │
│ mcp_server.server        │
└────────────┬─────────────┘
             │
             │ MCP / stdio
             │
             ▼
┌──────────────────────────┐
│ Terminal 2               │
│                          │
│ python main.py           │
│                          │
│ ├── FastAPI              │
│ └── Streamlit            │
└──────────────────────────┘
```

# 8. Testing the Project

The project includes offline tests for the orchestration logic.

Run:

Bash

```
pytest tests/ -v
```

The tests cover areas such as:

### `test_disagreement.py`

Tests the disagreement-resolution behavior, including:

- Evidence-supported findings
- Unsupported blocking findings
- Advisory findings
- Reviewer inconsistency
- Declining unsupported reviewer findings

### `test_convergence.py`

Tests:

- Successful convergence
- Convergence over unsupported reviewer objections
- Maximum iteration handling
- Difference between convergence and timeout

### `test_orchestrator_failures.py`

Tests failure scenarios such as:

- Generator failure
- MCP transport failure
- Sandbox timeout
- Reviewer failure
- Reviewer fallback
- Maximum iteration timeout

These tests are designed to test the orchestrator's behavior without requiring external model API calls.

# 9. Robustness

The project includes several mechanisms for handling failures.

## Reviewer Failure

Malformed reviewer output is retried.

If the reviewer continues to return malformed output, a safe fallback review is used.

## Generator Failure

If the generator model call fails, the workflow stops cleanly rather than entering an infinite loop.

## MCP Failure

MCP tool failures are returned as structured data that can be inspected by the orchestrator.

## Sandbox Timeout

Generated code runs in a separate subprocess with timeout protection.

## Maximum Iterations

The maximum iteration limit prevents an endless generation/review loop.

Reaching this limit is recorded as:

Plaintext

```
max_iterations
```

rather than being considered successful convergence.

# 10. Design Decisions

## Different Providers

The generator and reviewer intentionally use different providers.

Example:

Plaintext

```
Generator → OpenAI
Reviewer  → Anthropic
```

This supports the project's central premise of introducing a second model/provider perspective.

## Evidence-Based Review

The orchestrator does not blindly accept reviewer findings.

Reviewer findings are evaluated using:

Plaintext

```
Tests
Static Analysis
Reviewer Evidence
Previous Decisions
```

This allows the system to decline unsupported review feedback.

## MCP

MCP provides a clean interface between the orchestration layer and the tools used to evaluate generated code.

The agent does not need to directly implement testing, static analysis, or review execution.

## LangGraph

LangGraph provides explicit state and control flow for the iterative process.

The workflow can therefore represent:

Plaintext

```
Generate
→ Test
→ Analyze
→ Review
→ Resolve
→ Converge
→ Repeat
```

## FastAPI

FastAPI separates the backend orchestration from the Streamlit interface.

This makes the system easier to expose as an API and keeps the frontend independent from the internal agent implementation.

## Streamlit

Streamlit provides a simple interface for interacting with the system and inspecting the generated results and individual iterations.

# 11. Important Limitation

The reviewer is not guaranteed to be correct.

The disagreement resolver helps identify unsupported findings by checking them against executable evidence, but a reviewer can still produce a plausible-looking finding that is based on an incorrect interpretation of the available evidence.

The benchmark therefore evaluates the actual outcome of the orchestration rather than assuming that every reviewer intervention improves the code.

The project's goal is to **measure the effect of the orchestration loop**, not to assume that adding a reviewer always makes the solution better.

# 12. Quick Start

After installing the dependencies and configuring `.env`, open **two terminals**.

### Terminal 1 — MCP Server

Bash

```
python -m mcp_server.server
```

Keep it running.

### Terminal 2 — Application

Bash

```
python main.py
```

Then open:

Plaintext

```
http://localhost:8501
```

FastAPI API documentation:

Plaintext

```
[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
```

Run the project's tests separately with:

Bash

```
pytest tests/ -v
```

# 13. Summary

The project implements a complete **generator ↔ reviewer code-improvement loop** using two models from different providers.

The main architecture is:

Plaintext

```
User
 │
 ▼
Streamlit
 │
 ▼
FastAPI
 │
 ▼
LangGraph
 │
 ├── Generator Model
 │
 └── MCP Client
        │
        ▼
     MCP Server
        │
        ├── Reviewer
        ├── Tests
        └── Static Analysis
                │
                ▼
         Disagreement Resolution
                │
                ▼
           Convergence Check
              /        \
             /          \
      Converged        Not Converged
         │                 │
         ▼                 ▼
        END           Generate Revision
                           │
                           └──────► repeat
```

The application is started using two processes:

Plaintext

```
Terminal 1
    │
    └── python -m mcp_server.server

Terminal 2
    │
    └── python main.py
            │
            ├── FastAPI
            │
            └── Streamlit
```

The central objective is to determine whether a **second model from a different provider**, combined with MCP tools, executable evidence, disagreement resolution, and iterative orchestration, can actually improve generated code rather than simply produce additional review conversation.
