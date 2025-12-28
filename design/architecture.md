# Architecture

The system consists of three distinct roles:

## Planner Agent
- Persistent across tasks
- Performs reasoning only
- Reads documents and state files
- Writes planning artifacts only
- Never edits application code
- Never runs shell commands

## Codex Executor
- Invoked via MCP
- Executes exactly one task per invocation
- Edits code and runs tests
- Has no authority to plan or reprioritize work
- Is stateless across tasks

## Shepherd Daemon
- Deterministic control loop
- Dispatches Codex tasks
- Blocks until execution completes
- Enforces retries, timeouts, and stop conditions
- Owns system safety

No component may assume the responsibilities of another.
