# LangGraph Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an isolated LangGraph experiment mode to Youbestar without changing the existing `/chat` behavior.

**Architecture:** A new `LangGraphBridge` owns a compiled `StateGraph` with an `InMemorySaver`. The graph reuses Youbestar's prompt, parser, skill registry, skill toggle checks, and approved-skill runner. A separate `/langgraph/chat` endpoint and UI toggle route selected conversations through the graph and display graph node traces.

**Tech Stack:** Python 3.10+, FastAPI, LangGraph 1.2.x, unittest, HTML/CSS/JavaScript

---

### Task 1: Add LangGraph bridge tests

**Files:**
- Create: `tests/test_langgraph_bridge.py`

- [ ] Write a failing test for the no-action graph path and per-thread turn count.
- [ ] Write a failing test for the approved-skill graph path.
- [ ] Run `.\.venv\Scripts\python.exe -m unittest tests.test_langgraph_bridge -v` and confirm failure because `core.langgraph_bridge` does not exist.

### Task 2: Implement the backend bridge

**Files:**
- Create: `core/langgraph_bridge.py`
- Modify: `server.py`
- Modify: `requirements.txt`
- Modify: `start.bat`

- [ ] Add `langgraph>=1.2,<1.3` to requirements.
- [ ] Implement `LangGraphBridge` with `plan`, `no_action`, `execute_skill`, and `finish` nodes.
- [ ] Compile the graph with `InMemorySaver` and require a `thread_id` for invocation.
- [ ] Add `POST /langgraph/chat` while leaving `POST /chat` unchanged.
- [ ] Make `start.bat` install requirements when LangGraph is missing from an existing virtual environment.
- [ ] Run the bridge unit tests and confirm both graph paths pass.

### Task 3: Add the UI experiment switch

**Files:**
- Modify: `index.html`
- Create: `tests/test_langgraph_ui.py`

- [ ] Write a failing static UI test for the LangGraph endpoint, toggle, thread ID, and graph trace fields.
- [ ] Add a “LangGraph 实验” switch beside the existing chat-mode switch.
- [ ] Route messages to `/langgraph/chat` only when the switch is enabled.
- [ ] Send the active conversation ID as `threadId`.
- [ ] Display the returned graph node trace and turn count in the existing process-information area.
- [ ] Run the UI test and confirm it passes.

### Task 4: Verify and document

**Files:**
- Modify: `README.md`
- Modify: `开发交接文档.md`

- [ ] Document how to enable LangGraph experiment mode and what it demonstrates.
- [ ] Run `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`.
- [ ] Start the server and verify `/health` plus one `/langgraph/chat` request with a fake-model-independent unit test path.
- [ ] Inspect `git diff` to ensure existing unrelated UI scrolling changes remain intact.
