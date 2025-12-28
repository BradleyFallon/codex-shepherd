# Execution Model

Execution is performed exclusively by Codex via MCP.

## Execution Rules
- One task per Codex invocation
- New conversation per task
- No persistent Codex memory
- Codex must not modify planning files

## Execution Lifecycle
1. Task dispatched
2. Codex runs code changes and tests
3. Codex emits a structured result
4. Shepherd evaluates result

Codex may report:
- success
- failed
- blocked

Codex must not decide what happens next.
