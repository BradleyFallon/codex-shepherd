# codex-shepherd

Python scaffolding for a persistent planner that coordinates Codex workers via MCP.
No orchestration logic is implemented yet; this repo only defines the structure and
interfaces to be filled in.

## Purpose

`codex-shepherd` is intended to host a long-lived planner that delegates work to
Codex through MCP. The planner and the shepherd daemon are separate from Codex
itself: Codex remains an external worker accessed via MCP.

## Architecture (scaffolding)

- `shepherd/daemon.py`: placeholder for a long-running process that coordinates
  planning and execution.
- `shepherd/planner.py`: placeholder for a planner agent that emits plans/steps.
- `shepherd/mcp_client.py`: placeholder for a client that exchanges messages with
  Codex over MCP.
- `shepherd/state.py` and `shepherd/policies.py`: placeholders for state and
  policy definitions used by the daemon and planner.
- `shepherd/watchdog.py`: placeholder for supervision and liveness checks.

Prompt and schema placeholders live in:

- `prompts/`: text templates for planner and Codex worker interactions.
- `schemas/`: JSON schema files for plan and result payloads.
- `examples/`: minimal sample artifacts for future validation.

## Separation of responsibilities

- Planner: decides *what* to do and produces a structured plan.
- Shepherd (daemon): decides *when* and *how* to run steps, and coordinates state.
- Codex: executes a requested step and returns results via MCP.

## Codex MCP usage (high level)

The shepherd will use an MCP client to open a session with a Codex MCP server,
send prompt payloads (from `prompts/`) and receive structured results that can be
validated against `schemas/`. No MCP configuration or wiring is implemented in
this scaffolding.

## Status

v0 scaffolding only. Files are placeholders; no runtime behavior exists yet.

## Next Steps

- Implement shepherd daemon
- Implement MCP client
- Implement planner agent
