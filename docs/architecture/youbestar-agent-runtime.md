# Youbestar Agent Runtime Architecture

## Positioning

Youbestar is not a LangGraph application.

Youbestar is a local, self-owned agent runtime. LangGraph is useful as a reference implementation and experiment bench, but the production agent core must remain inside Youbestar.

The rule is:

```text
Borrow the ideas. Do not depend on the framework as the core.
```

LangGraph concepts we will borrow:

- Explicit state
- Node-based execution
- Conditional routing
- Reflection after execution
- Checkpoints
- Human approval interrupts

Youbestar-owned equivalents:

```text
LangGraph StateGraph   -> Youbestar AgentRuntime
LangGraph State        -> Youbestar AgentState
LangGraph Node         -> Youbestar AgentNode
LangGraph Edges        -> Youbestar AgentRouter
LangGraph Checkpointer -> Youbestar AgentCheckpoint
LangGraph Interrupt    -> Youbestar AgentPolicy / Approval
```

## Runtime Layers

The runtime is split into six layers.

```text
AgentState
AgentNode
AgentRouter
AgentRuntime
AgentCheckpoint
AgentPolicy
```

### AgentState

`AgentState` is the single workbench for one agent run. Every node reads and writes this state.

Required fields:

```text
thread_id
user_input
allow_chat
model_reply
thought
intent
plan
action
params
observation
reflection
response
reply
errors
runtime_nodes
step_count
history
```

Design rule: do not pass loose tuples between nodes. Add state fields deliberately when the agent needs a new kind of memory or decision surface.

### AgentNode

A node is a small deterministic unit:

```text
node(state, context) -> state
```

Initial core nodes:

```text
prepare
execute
reflect
finalize
```

Future nodes:

```text
classify_intent
plan
observe
repair
approval_interrupt
checkpoint
summarize_memory
```

### AgentRouter

The router decides the next node from state.

The first runtime can use a fixed route:

```text
prepare -> execute -> reflect -> finalize
```

Later versions can route dynamically:

```text
prepare -> classify_intent -> plan -> execute -> reflect
reflect -> execute | approval_interrupt | finalize
```

### AgentRuntime

`AgentRuntime` owns execution order, node limits, checkpoint hooks, and final result conversion.

It should expose:

```python
runtime.run(llm, memory, user_input, allow_chat=True, thread_id="default")
```

It returns a structured result compatible with the existing `/chat` response:

```text
reply
model_reply
thought
action
params
action_result
response
runtime_nodes
```

### AgentCheckpoint

The checkpoint layer records node-by-node state snapshots.

First useful local format:

```json
{
  "thread_id": "chat-123",
  "run_id": "2026-06-04T23:20:00Z",
  "step": 2,
  "node": "reflect",
  "state": {}
}
```

Initial implementation can be in-memory for tests. The production local implementation should use JSONL or SQLite.

### AgentPolicy

Policy decides whether execution may continue.

Examples:

```text
Can call this skill?
Does this action need approval?
Should this file write be blocked?
Should the runtime interrupt and wait for the user?
```

The first runtime can keep policy implicit by reusing the existing skill registry and enable checks. Later we move approval and interrupt into this layer.

## First Runtime Flow

The first self-owned runtime is deliberately small:

```text
prepare -> execute -> reflect -> finalize
```

### prepare

Responsibilities:

- Build the prompt using the existing prompt builder.
- Call the model.
- Parse `Thought / Action / Params / Response`.
- Normalize the action name.
- Store model output in state.

### execute

Responsibilities:

- If `action == none`, set observation to `无操作`.
- If action is unknown, set observation to `未知工具：...`.
- If action is disabled, set observation to `技能已关闭：...`.
- Otherwise call the registered skill.

### reflect

Responsibilities:

- Preserve an existing natural `response`.
- If tool execution failed, turn the failure into a user-facing explanation.
- If tool execution succeeded and response is empty, use the observation as response.
- If there is no action and no response, provide a warm fallback.

### finalize

Responsibilities:

- Set `reply` to the final user-visible answer.
- Keep debug fields separate.
- Write short memory.
- Return a result compatible with the existing API.

## Relationship To Existing Paths

### `/chat`

Current stable path. It now uses the self-owned `AgentRuntime` by default.

Fallback:

```text
/chat -> AgentRuntime
fallback -> agent_loop
```

### `/langgraph/chat`

Experiment path only. It remains useful for comparing design ideas, but it should not become the main architecture.

### `core/loop.py`

Compatibility layer. The new runtime may reuse its prompt builder, parser-adjacent helpers, and response bridge while the project migrates.

## Implementation Phases

### Phase 1: Skeleton

- Add `core/agent_state.py`
- Add `core/agent_nodes.py`
- Add `core/agent_runtime.py`
- Add framework tests
- Do not switch `/chat` yet

### Phase 2: Runtime Parity

- Make AgentRuntime match current `agent_loop` behavior
- Keep `/chat` response shape unchanged
- Add tests for chat, tool, unknown tool, disabled tool, natural reply

### Phase 3: Switch `/chat`

- Route `/chat` through AgentRuntime
- Keep `agent_loop` as compatibility fallback
- Update docs and UI labels

### Phase 4: Checkpoint

- Add local JSONL or SQLite checkpoint store
- Record every node state
- Add debug endpoint to inspect a run

### Phase 5: Policy / Interrupt

- Move approvals into AgentPolicy
- Add interrupt-style pending approval states
- Resume runs by `thread_id`

### Phase 6: Loops And Repair

- Add bounded `reflect -> execute` loops
- Add repair node for failed skill creation or bad params
- Limit iterations to prevent runaway behavior

## Non-Goals

- Do not replace the whole system with LangGraph.
- Do not add multi-agent orchestration before the single-agent runtime is stable.
- Do not hide state transitions in ad hoc helper functions.
- Do not make `/chat` depend on experimental graph code.
