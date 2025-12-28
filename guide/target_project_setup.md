# Target Project Setup for Codex Shepherd

This document defines the **required and optional files**, **directory layout**, and
**authority rules** for any project that will be operated on by Codex Shepherd.

Codex Shepherd will refuse to run if these rules are violated.

This document is authoritative for all target-project setup.

---

## 1. Conceptual Model

Codex Shepherd operates on a **target project**.

A target project is:
- a normal source repository
- containing authoritative design documentation
- plus a dedicated `ai/` directory owned by Codex Shepherd

Codex Shepherd itself lives in a **separate repository** and must never be
checked into the target project.

---

## 2. Required Directory Layout (Target Project)

At the root of the target project repository:

```

target-project/
├─ ai/                # Shepherd-owned state and configuration
├─ design/ OR docs/   # Authoritative design documentation
├─ <application code>
└─ README.md

```

Notes:
- The project may use either `design/` or `docs/` for design documents.
- The location of authoritative documents is defined explicitly in `ai/SOURCES.yaml`.
- Codex Shepherd does not infer document locations.

---

## 3. The `ai/` Directory (Mandatory)

The `ai/` directory is **required** and **owned exclusively by Codex Shepherd**.

No application code may depend on files in `ai/`.

### Required files in `ai/`

```

ai/
├─ config.json
├─ GOALS.md
└─ SOURCES.yaml

```

### Optional / generated files

These files are created and maintained by Codex Shepherd at runtime:

```

ai/
├─ PLAN.yaml
├─ ACTIVE_TASK.yaml
├─ PROGRESS.yaml
├─ SUMMARY.md
├─ LAST_RESULT.json
└─ shepherd.log

````

---

## 4. `ai/config.json` (Required)

Defines runtime configuration for Codex Shepherd.

- Must exist before the shepherd starts.
- Must be valid JSON.
- Must not be modified during execution.

### Minimal example

```json
{
  "mcp": {
    "command": "codex mcp-server --sandbox workspace --approval-policy never",
    "startup_timeout_seconds": 10
  },
  "execution": {
    "task_timeout_seconds": 1800,
    "max_retries_per_task": 2,
    "max_consecutive_failures": 3,
    "one_task_at_a_time": true
  },
  "paths": {
    "design_dir": "design",
    "state_dir": "ai"
  },
  "validation": {
    "strict_schema_validation": true,
    "json_subset_only": true
  },
  "logging": {
    "level": "info",
    "log_file": "ai/shepherd.log"
  }
}
````

---

## 5. `ai/GOALS.md` (Required, Immutable)

Defines **completion criteria** for the target project.

Rules:

* Written by humans only.
* Must not contain tasks.
* Must not contain implementation detail.
* Must not be modified by Codex or the planner.

### Example

```md
# Project Goals

The project is complete when:

- All requirements defined in authoritative design documents are satisfied
- All documented constraints are enforced
- No unresolved design ambiguities remain
```

---

## 6. `ai/SOURCES.yaml` (Required, Immutable)

Defines **which documents are authoritative** and how they are treated.

This is the **only file** that grants authority to documents.

Rules:

* Must be valid JSON-subset YAML (i.e., valid JSON).
* Paths are relative to the project root.
* Documents not listed here are ignored by the planner.

### Example (using docs/)

```json
{
  "sources": [
    {
      "path": "docs/architecture.md",
      "role": "primary"
    },
    {
      "path": "docs/api.md",
      "role": "authoritative"
    },
    {
      "path": "docs/invariants.md",
      "role": "constraints"
    }
  ]
}
```

### Roles

| Role          | Meaning                                   |
| ------------- | ----------------------------------------- |
| primary       | Defines intended structure and behavior   |
| authoritative | Defines binding requirements              |
| constraints   | Defines rules that must never be violated |
| optional      | Informational only; never enforced        |

---

## 7. Authoritative Design Documents

Design documents may live anywhere (`design/`, `docs/`, etc.), but:

* Only files listed in `ai/SOURCES.yaml` are authoritative.
* Authoritative documents may reference other documents for context.
* Referenced documents do not gain authority automatically.

### Recommended disclaimer inside design docs

```md
## Authority

This document is listed in ai/SOURCES.yaml and defines binding requirements
for automated execution. Referenced documents are informational only unless
explicitly promoted to authoritative sources.
```

---

## 8. Worker Context vs Authority

Codex Shepherd distinguishes between:

### Authority (planner uses)

* Only documents listed in `ai/SOURCES.yaml`
* Used to derive objectives and tasks

### Context (Codex workers may read)

* Any files allowed by the worker context rules
* Used to implement tasks correctly
* Never used to derive new requirements

Context documents must never override authoritative inputs.

---

## 9. Runtime-Generated State Files

The following files are created and maintained automatically:

* `ai/PLAN.yaml` – derived objectives and tasks
* `ai/ACTIVE_TASK.yaml` – currently executing task
* `ai/PROGRESS.yaml` – objective-level progress tracking
* `ai/SUMMARY.md` – append-only execution log
* `ai/LAST_RESULT.json` – last Codex execution result

Humans should not edit these files while the shepherd is running.

---

## 10. JSON-Subset YAML Rule

All `.yaml` files used by Codex Shepherd must be:

* valid JSON
* parseable by the Python standard library `json` module

This forbids:

* comments
* anchors
* multiline YAML-only features

Violations cause immediate termination.

---

## 11. Stop Conditions

Codex Shepherd will halt execution if:

* Required files are missing or malformed
* Design documents contradict each other
* An authoritative requirement is ambiguous
* Codex reports a blocked task
* Retry or failure limits are exceeded

Stopping is a correct and expected outcome.

---

## 12. What Codex Shepherd Will Never Do

Codex Shepherd will never:

* invent requirements
* modify design documents
* modify `ai/config.json`, `ai/GOALS.md`, or `ai/SOURCES.yaml`
* guess intent in ambiguous situations
* continue execution after a STOP condition

---

## 13. Summary

A target project is ready for Codex Shepherd when:

* `ai/config.json`, `ai/GOALS.md`, and `ai/SOURCES.yaml` exist
* Authoritative design docs are listed explicitly
* All rules in this document are satisfied

If these conditions are met, Codex Shepherd may operate autonomously.

