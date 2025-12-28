"""Safety and policy enforcement helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable


class PolicyViolation(Exception):
    """Raised when a policy or safety rule is violated."""


def resolve_path(project_root: Path, path_str: str) -> Path:
    candidate = Path(path_str)
    if not candidate.is_absolute():
        candidate = project_root / candidate
    return candidate.resolve()


def assert_no_forbidden_changes(
    files_changed: Iterable[str],
    *,
    project_root: Path,
    design_dir: Path,
    state_dir: Path,
) -> None:
    forbidden: list[str] = []
    design_root = design_dir.resolve()
    state_root = state_dir.resolve()
    project_root = project_root.resolve()

    for entry in files_changed:
        if not isinstance(entry, str):
            raise PolicyViolation("files_changed entries must be strings.")
        resolved = resolve_path(project_root, entry)
        if _is_within(resolved, design_root) or _is_within(resolved, state_root):
            forbidden.append(entry)
        elif not _is_within(resolved, project_root):
            forbidden.append(entry)

    if forbidden:
        joined = ", ".join(sorted(forbidden))
        raise PolicyViolation(f"Forbidden files modified: {joined}")


def _is_within(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
    except ValueError:
        return False
    return True
