# Safety and Stop Conditions

Execution must stop immediately if any of the following occur:

## Planner Conditions
- Conflicting requirements detected
- Objective cannot be mapped to code
- Required clarification is missing

## Execution Conditions
- Codex reports "blocked"
- A task fails more than once
- Forbidden files are modified
- Execution exceeds time limits

## System Conditions
- State files become invalid
- Document invariants are violated

Stopping is a correct outcome.
Human intervention is required after a stop.
