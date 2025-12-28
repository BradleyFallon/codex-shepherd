# Codex Shepherd - System Overview

Codex Shepherd is a document-driven orchestration system for autonomous software development.

It coordinates:
- a persistent planning agent (LLM-based)
- Codex (via MCP) as a code execution worker
- a deterministic shepherd daemon that enforces rules and safety

The system is designed to:
- derive work from authoritative documents
- execute tasks one at a time
- track progress mechanically
- stop safely on ambiguity or failure

Codex Shepherd is NOT:
- a self-directed AI
- a creative coding assistant
- a system that invents requirements

All work performed by the system must be traceable to input documents.
