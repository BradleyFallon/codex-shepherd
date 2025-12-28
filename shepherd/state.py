"""Canonical interface for persistent state files."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Optional


AI_DIRNAME = "ai"
DESIGN_DIRNAME = "design"

CONFIG_FILENAME = "config.json"
GOALS_FILENAME = "GOALS.md"
SOURCES_FILENAME = "SOURCES.yaml"
PLAN_FILENAME = "PLAN.yaml"
ACTIVE_TASK_FILENAME = "ACTIVE_TASK.yaml"
SUMMARY_FILENAME = "SUMMARY.md"
LAST_RESULT_FILENAME = "LAST_RESULT.json"
PROGRESS_FILENAME = "PROGRESS.yaml"

DEFAULT_SUMMARY = ""
DEFAULT_PROGRESS = "objectives: {}\n"

OBJECTIVE_STATUSES = {"pending", "in_progress", "complete"}
TASK_STATUSES = {"pending", "active", "done", "failed", "blocked"}
CODEX_RESULT_STATUSES = {"success", "failed", "blocked"}


@dataclass(frozen=True)
class Config:
    mcp_command: str
    startup_timeout_seconds: int
    task_timeout_seconds: int
    max_retries_per_task: int
    max_consecutive_failures: int
    one_task_at_a_time: bool
    design_dir: str
    state_dir: str
    strict_schema_validation: bool
    json_subset_only: bool
    log_level: str
    log_file: str


class StateError(Exception):
    """Base class for state access errors."""


class ReadOnlyStateError(StateError):
    """Raised when attempting to write a read-only path."""


class StateValidationError(StateError):
    """Raised when a state file fails validation."""


class MissingStateError(StateError):
    """Raised when a required state file is missing."""


class StateStore:
    """File-backed state access rooted at a target project."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        state_dir: str = AI_DIRNAME,
        design_dir: str = DESIGN_DIRNAME,
        config_path: Optional[Path] = None,
        strict_schema_validation: bool = True,
        json_subset_only: bool = True,
    ) -> None:
        root = Path(project_root).resolve()
        if not root.exists():
            raise MissingStateError(f"Project root does not exist: {root}")
        self.project_root = root
        self.ai_dir = root / state_dir
        self.design_dir = root / design_dir

        self.config_path = config_path or (root / AI_DIRNAME / CONFIG_FILENAME)
        self.goals_path = self.ai_dir / GOALS_FILENAME
        self.sources_path = self.ai_dir / SOURCES_FILENAME
        self.plan_path = self.ai_dir / PLAN_FILENAME
        self.active_task_path = self.ai_dir / ACTIVE_TASK_FILENAME
        self.summary_path = self.ai_dir / SUMMARY_FILENAME
        self.last_result_path = self.ai_dir / LAST_RESULT_FILENAME
        self.progress_path = self.ai_dir / PROGRESS_FILENAME

        self.strict_schema_validation = strict_schema_validation
        self.json_subset_only = json_subset_only

        self._read_only_paths = {
            self.config_path.resolve(),
            self.goals_path.resolve(),
            self.sources_path.resolve(),
        }
        self._writable_paths = {
            self.plan_path.resolve(),
            self.active_task_path.resolve(),
            self.summary_path.resolve(),
            self.last_result_path.resolve(),
            self.progress_path.resolve(),
        }
        self._design_resolved = self.design_dir.resolve()

    def is_read_only_path(self, path: Path) -> bool:
        resolved = path.resolve()
        if resolved in self._read_only_paths:
            return True
        return _is_within(resolved, self._design_resolved)

    def is_writable_path(self, path: Path) -> bool:
        return path.resolve() in self._writable_paths

    def load_config(self) -> Config:
        """Load ai/config.json and validate it."""
        config_data = _read_json_object(self.config_path)
        return _parse_config(config_data)

    def load_goals(self) -> str:
        """Load ai/GOALS.md (read-only)."""
        return _read_text(self.goals_path)

    def load_sources(self) -> dict[str, Any]:
        """Load ai/SOURCES.yaml (read-only, JSON subset)."""
        return _read_json_object(self.sources_path)

    def load_plan(self) -> dict[str, Any]:
        """Load and validate ai/PLAN.yaml."""
        plan = _read_json_object(self.plan_path)
        if self.strict_schema_validation:
            _validate_plan(plan)
        return plan

    def load_active_task(self) -> dict[str, Any]:
        """Load and validate ai/ACTIVE_TASK.yaml."""
        task = _read_json_object(self.active_task_path)
        if self.strict_schema_validation:
            _validate_active_task(task)
        return task

    def load_summary(self) -> str:
        """Load ai/SUMMARY.md or return a safe default if missing."""
        if not self.summary_path.exists():
            return DEFAULT_SUMMARY
        return _read_text(self.summary_path)

    def load_last_result(self) -> Optional[dict[str, Any]]:
        """Load and validate ai/LAST_RESULT.json, or return None if missing."""
        if not self.last_result_path.exists():
            return None
        result = _read_json_object(self.last_result_path)
        if self.strict_schema_validation:
            _validate_codex_result(result)
        return result

    def load_progress(self) -> str:
        """Load ai/PROGRESS.yaml or return a safe default if missing."""
        if not self.progress_path.exists():
            return DEFAULT_PROGRESS
        return _read_text(self.progress_path)

    def write_plan(self, plan: dict[str, Any]) -> None:
        """Atomically write ai/PLAN.yaml after validation."""
        if self.strict_schema_validation:
            _validate_plan(plan)
        _atomic_write_json(self.plan_path, plan, self)

    def write_active_task(self, task: dict[str, Any]) -> None:
        """Atomically write ai/ACTIVE_TASK.yaml after validation."""
        if self.strict_schema_validation:
            _validate_active_task(task)
        _atomic_write_json(self.active_task_path, task, self)

    def write_summary(self, content: str) -> None:
        """Atomically write ai/SUMMARY.md."""
        _atomic_write_text(self.summary_path, content, self)

    def write_last_result(self, result: dict[str, Any]) -> None:
        """Atomically write ai/LAST_RESULT.json after validation."""
        if self.strict_schema_validation:
            _validate_codex_result(result)
        _atomic_write_json(self.last_result_path, result, self)

    def write_progress(self, content: str) -> None:
        """Atomically write ai/PROGRESS.yaml."""
        _atomic_write_text(self.progress_path, content, self)

    def clear_active_task(self) -> None:
        """Remove ai/ACTIVE_TASK.yaml if present."""
        if self.active_task_path.exists():
            _ensure_writable_path(self.active_task_path, self)
            self.active_task_path.unlink()


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise MissingStateError(f"Missing required state file: {path}") from exc


def _read_json_object(path: Path) -> dict[str, Any]:
    text = _read_text(path)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise StateValidationError(
            f"{path} must contain JSON (YAML-compatible) object data: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise StateValidationError(f"{path} must contain a JSON object.")
    return data


def _atomic_write_text(path: Path, content: str, store: StateStore) -> None:
    if not isinstance(content, str):
        raise TypeError(f"Content for {path} must be a string.")
    _ensure_writable_path(path, store)
    _ensure_parent_dir(path)
    _atomic_write_bytes(path, content.encode("utf-8"))


def _atomic_write_json(path: Path, data: dict[str, Any], store: StateStore) -> None:
    if not isinstance(data, dict):
        raise TypeError(f"JSON content for {path} must be a dict.")
    _ensure_writable_path(path, store)
    _ensure_parent_dir(path)
    try:
        text = json.dumps(data, indent=2) + "\n"
    except TypeError as exc:
        raise StateValidationError(f"JSON content for {path} is not serializable.") from exc
    _atomic_write_bytes(path, text.encode("utf-8"))


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    directory = path.parent
    fd, tmp_path = tempfile.mkstemp(prefix=f".{path.name}.", dir=directory)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def _ensure_writable_path(path: Path, store: StateStore) -> None:
    resolved = path.resolve()
    if resolved in store._read_only_paths:
        raise ReadOnlyStateError(f"{path} is read-only.")
    if _is_within(resolved, store._design_resolved):
        raise ReadOnlyStateError(f"{path} is under design/ and immutable.")
    if resolved not in store._writable_paths:
        raise StateError(f"Refusing to write unknown state file: {path}")


def _ensure_parent_dir(path: Path) -> None:
    if not path.parent.exists():
        raise MissingStateError(f"Missing parent directory for {path}")


def _is_within(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
    except ValueError:
        return False
    return True


def _validate_plan(plan: dict[str, Any]) -> None:
    _require_mapping(plan, "plan")
    _require_keys(plan, {"version", "objectives", "tasks"}, "plan")
    _reject_extra_keys(plan, {"version", "objectives", "tasks"}, "plan")
    _require_int(plan["version"], "plan.version")

    objectives = plan["objectives"]
    _require_list(objectives, "plan.objectives")
    for index, item in enumerate(objectives):
        _validate_objective(item, f"plan.objectives[{index}]")

    tasks = plan["tasks"]
    _require_list(tasks, "plan.tasks")
    for index, item in enumerate(tasks):
        _validate_task(item, f"plan.tasks[{index}]")


def _validate_objective(obj: dict[str, Any], context: str) -> None:
    _require_mapping(obj, context)
    _require_keys(obj, {"id", "source", "status"}, context)
    _reject_extra_keys(obj, {"id", "source", "status"}, context)
    _require_string(obj["id"], f"{context}.id")
    _require_string(obj["source"], f"{context}.source")
    _require_enum(obj["status"], OBJECTIVE_STATUSES, f"{context}.status")


def _validate_task(task: dict[str, Any], context: str) -> None:
    _require_mapping(task, context)
    required = {"id", "objective", "derived_from", "status"}
    optional = {"depends_on", "scope", "success_criteria"}
    allowed = required | optional
    _require_keys(task, required, context)
    _reject_extra_keys(task, allowed, context)
    _require_string(task["id"], f"{context}.id")
    _require_string(task["objective"], f"{context}.objective")
    _require_string(task["derived_from"], f"{context}.derived_from")
    _require_enum(task["status"], TASK_STATUSES, f"{context}.status")

    if "depends_on" in task:
        _require_string_list(task["depends_on"], f"{context}.depends_on")
    if "scope" in task:
        _require_string_list(task["scope"], f"{context}.scope")
    if "success_criteria" in task:
        _require_string_list(task["success_criteria"], f"{context}.success_criteria")


def _validate_active_task(task: dict[str, Any]) -> None:
    context = "active_task"
    _require_mapping(task, context)
    required = {"id", "objective", "derived_from", "status", "timeout_seconds"}
    optional = {"depends_on", "scope", "success_criteria"}
    allowed = required | optional
    _require_keys(task, required, context)
    _reject_extra_keys(task, allowed, context)
    _require_string(task["id"], f"{context}.id")
    _require_string(task["objective"], f"{context}.objective")
    _require_string(task["derived_from"], f"{context}.derived_from")
    _require_enum(task["status"], TASK_STATUSES, f"{context}.status")
    _require_int(task["timeout_seconds"], f"{context}.timeout_seconds")

    if "depends_on" in task:
        _require_string_list(task["depends_on"], f"{context}.depends_on")
    if "scope" in task:
        _require_string_list(task["scope"], f"{context}.scope")
    if "success_criteria" in task:
        _require_string_list(task["success_criteria"], f"{context}.success_criteria")


def _validate_codex_result(result: dict[str, Any]) -> None:
    _require_mapping(result, "codex_result")
    _require_keys(result, {"status", "files_changed", "tests_run", "notes"}, "codex_result")
    _reject_extra_keys(result, {"status", "files_changed", "tests_run", "notes"}, "codex_result")
    _require_enum(result["status"], CODEX_RESULT_STATUSES, "codex_result.status")
    _require_string_list(result["files_changed"], "codex_result.files_changed")
    _require_string_list(result["tests_run"], "codex_result.tests_run")
    _require_string(result["notes"], "codex_result.notes")


def _require_mapping(value: Any, context: str) -> None:
    if not isinstance(value, dict):
        raise StateValidationError(f"{context} must be an object.")


def _require_list(value: Any, context: str) -> None:
    if not isinstance(value, list):
        raise StateValidationError(f"{context} must be an array.")


def _require_keys(mapping: dict[str, Any], required: set[str], context: str) -> None:
    missing = required - set(mapping.keys())
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise StateValidationError(f"{context} is missing required keys: {missing_list}")


def _reject_extra_keys(mapping: dict[str, Any], allowed: set[str], context: str) -> None:
    extra = set(mapping.keys()) - allowed
    if extra:
        extra_list = ", ".join(sorted(extra))
        raise StateValidationError(f"{context} has unexpected keys: {extra_list}")


def _require_int(value: Any, context: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise StateValidationError(f"{context} must be an integer.")


def _require_string(value: Any, context: str) -> None:
    if not isinstance(value, str):
        raise StateValidationError(f"{context} must be a string.")


def _require_string_list(value: Any, context: str) -> None:
    _require_list(value, context)
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise StateValidationError(f"{context}[{index}] must be a string.")


def _require_enum(value: Any, allowed: set[str], context: str) -> None:
    _require_string(value, context)
    if value not in allowed:
        allowed_list = ", ".join(sorted(allowed))
        raise StateValidationError(f"{context} must be one of: {allowed_list}")


def _parse_config(config: dict[str, Any]) -> Config:
    _require_mapping(config, "config")
    _require_keys(config, {"mcp", "execution", "paths", "validation", "logging"}, "config")
    _reject_extra_keys(config, {"mcp", "execution", "paths", "validation", "logging"}, "config")

    mcp = _require_section(config, "mcp")
    _require_keys(mcp, {"command", "startup_timeout_seconds"}, "config.mcp")
    _reject_extra_keys(mcp, {"command", "startup_timeout_seconds"}, "config.mcp")
    _require_string(mcp["command"], "config.mcp.command")
    _require_int(mcp["startup_timeout_seconds"], "config.mcp.startup_timeout_seconds")
    _require_non_negative(mcp["startup_timeout_seconds"], "config.mcp.startup_timeout_seconds")

    execution = _require_section(config, "execution")
    _require_keys(
        execution,
        {
            "task_timeout_seconds",
            "max_retries_per_task",
            "max_consecutive_failures",
            "one_task_at_a_time",
        },
        "config.execution",
    )
    _reject_extra_keys(
        execution,
        {
            "task_timeout_seconds",
            "max_retries_per_task",
            "max_consecutive_failures",
            "one_task_at_a_time",
        },
        "config.execution",
    )
    _require_int(execution["task_timeout_seconds"], "config.execution.task_timeout_seconds")
    _require_positive(
        execution["task_timeout_seconds"], "config.execution.task_timeout_seconds"
    )
    _require_int(execution["max_retries_per_task"], "config.execution.max_retries_per_task")
    _require_non_negative(
        execution["max_retries_per_task"], "config.execution.max_retries_per_task"
    )
    _require_int(
        execution["max_consecutive_failures"], "config.execution.max_consecutive_failures"
    )
    _require_positive(
        execution["max_consecutive_failures"], "config.execution.max_consecutive_failures"
    )
    _require_bool(execution["one_task_at_a_time"], "config.execution.one_task_at_a_time")
    if execution["one_task_at_a_time"] is not True:
        raise StateValidationError("config.execution.one_task_at_a_time must be true.")

    paths = _require_section(config, "paths")
    _require_keys(paths, {"design_dir", "state_dir"}, "config.paths")
    _reject_extra_keys(paths, {"design_dir", "state_dir"}, "config.paths")
    _require_string(paths["design_dir"], "config.paths.design_dir")
    _require_string(paths["state_dir"], "config.paths.state_dir")
    _require_non_empty(paths["design_dir"], "config.paths.design_dir")
    _require_non_empty(paths["state_dir"], "config.paths.state_dir")

    validation = _require_section(config, "validation")
    _require_keys(validation, {"strict_schema_validation", "json_subset_only"}, "config.validation")
    _reject_extra_keys(
        validation, {"strict_schema_validation", "json_subset_only"}, "config.validation"
    )
    _require_bool(validation["strict_schema_validation"], "config.validation.strict_schema_validation")
    _require_bool(validation["json_subset_only"], "config.validation.json_subset_only")
    if validation["json_subset_only"] is not True:
        raise StateValidationError("config.validation.json_subset_only must be true.")

    logging_cfg = _require_section(config, "logging")
    _require_keys(logging_cfg, {"level", "log_file"}, "config.logging")
    _reject_extra_keys(logging_cfg, {"level", "log_file"}, "config.logging")
    _require_string(logging_cfg["level"], "config.logging.level")
    _require_string(logging_cfg["log_file"], "config.logging.log_file")
    _require_non_empty(logging_cfg["level"], "config.logging.level")
    _require_non_empty(logging_cfg["log_file"], "config.logging.log_file")
    _require_log_level(logging_cfg["level"])

    return Config(
        mcp_command=mcp["command"],
        startup_timeout_seconds=mcp["startup_timeout_seconds"],
        task_timeout_seconds=execution["task_timeout_seconds"],
        max_retries_per_task=execution["max_retries_per_task"],
        max_consecutive_failures=execution["max_consecutive_failures"],
        one_task_at_a_time=execution["one_task_at_a_time"],
        design_dir=paths["design_dir"],
        state_dir=paths["state_dir"],
        strict_schema_validation=validation["strict_schema_validation"],
        json_subset_only=validation["json_subset_only"],
        log_level=logging_cfg["level"],
        log_file=logging_cfg["log_file"],
    )


def _require_section(config: dict[str, Any], name: str) -> dict[str, Any]:
    section = config.get(name)
    if not isinstance(section, dict):
        raise StateValidationError(f"config.{name} must be an object.")
    return section


def _require_bool(value: Any, context: str) -> None:
    if not isinstance(value, bool):
        raise StateValidationError(f"{context} must be a boolean.")


def _require_positive(value: int, context: str) -> None:
    if value <= 0:
        raise StateValidationError(f"{context} must be greater than zero.")


def _require_non_negative(value: int, context: str) -> None:
    if value < 0:
        raise StateValidationError(f"{context} must be non-negative.")


def _require_non_empty(value: str, context: str) -> None:
    if not value.strip():
        raise StateValidationError(f"{context} must be non-empty.")


def _require_log_level(value: str) -> None:
    allowed = {"debug", "info", "warning", "error", "critical"}
    if value.lower() not in allowed:
        allowed_list = ", ".join(sorted(allowed))
        raise StateValidationError(f"config.logging.level must be one of: {allowed_list}")
