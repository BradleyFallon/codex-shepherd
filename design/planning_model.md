# Planning Model

Planning is document-driven.

## Inputs
- Authoritative design documents
- Immutable goals
- Current repository state
- Recorded execution results

## Outputs
- Objectives (what must be true)
- Tasks (actions to satisfy objectives)
- Task dependencies
- Progress state

## Rules
- Tasks must be derived from documents
- Tasks may be decomposed only after failure
- The planner may not invent new objectives
- Ambiguity must halt execution

Planning occurs only between execution steps.
The planner never intervenes during task execution.
