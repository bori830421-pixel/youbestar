# Agent System

This folder implements a controlled skill evolution system.

## Flow

```text
model writes code -> sandbox/
model writes tests -> tests/
tests pass -> approval request
operator approves -> skills/local/
registry.json records the skill
agent can call registered skill
```

## Skill Registry

Registered skills live under:

```text
skills/
  official/      # maintained first-party skills
  community/     # shared skills from other authors
  local/         # local user skills approved on this machine
  registry.json  # namespace -> path/version/source metadata
```

Skill names use namespaces:

```text
official.open_browser
community.user123.parse_order
local.my_parse_order
```

## Permission Boundary

The model can write only sandbox skill files and test files through controlled API endpoints. It cannot write directly into `skills/`.

The model can read ordinary project files only through the controlled read policy. By default this allows text/code files under `D:\codex_project` and blocks secrets, tokens, auth files, virtual environments, caches, databases, browser profiles, and runtime data directories.

Approved local skills are promoted by the operator through:

```text
POST /skills/approve
```

Rejected skills stay out of the approved runtime.
