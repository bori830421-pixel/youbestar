# Model Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Youbestar discover and select models from OpenAI-compatible third-party APIs such as NVIDIA and FreeModel.

**Architecture:** A backend-only model discovery service derives `/models` from the configured API base URL, sends the API key in an Authorization header, and normalizes common OpenAI-compatible response shapes. The configuration page calls this service on demand and populates a searchable model list while retaining manual model entry.

**Tech Stack:** Python 3.10+, FastAPI, requests, unittest, HTML/CSS/JavaScript

---

### Task 1: Backend model discovery

**Files:**
- Create: `core/model_discovery.py`
- Create: `tests/test_model_discovery.py`
- Modify: `server.py`

- [ ] Write failing tests for `/models` URL normalization and common response shapes.
- [ ] Write a failing test that confirms the API key is sent only in the Authorization header.
- [ ] Implement the smallest discovery helper and `POST /models/discover` endpoint.
- [ ] Verify backend tests pass.

### Task 2: Configuration UI

**Files:**
- Create: `tests/test_model_discovery_ui.py`
- Modify: `index.html`

- [ ] Write a failing static UI test for the discovery button, model list, and manual fallback.
- [ ] Add the model discovery controls to the existing configuration form.
- [ ] Populate and filter the discovered model list, syncing selection to the existing model input.
- [ ] Show clear success and error states without removing manual model entry.
- [ ] Verify UI tests pass.

### Task 3: Documentation and verification

**Files:**
- Modify: `README.md`
- Modify: `开发交接文档.md`

- [ ] Document compatible `/v1/models` providers and manual fallback.
- [ ] Run the complete test suite and compile check.
- [ ] Verify the running UI in a browser without using a real API key.
