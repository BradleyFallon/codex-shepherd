"""Deterministic shepherd control loop."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .mcp_client import MCPClient, MCPError, MCPTimeoutError
from .planner import Planner, PlannerError
from .policies import PolicyViolation, assert_no_forbidden_changes
from .state import Config, MissingStateError, StateError, StateStore
from .watchdog import RetryTracker


class StopExecution(Exception):
    """Raised when execution must stop immediately."""


def main() -> None:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()

    bootstrap_store = StateStore(project_root)
    config = bootstrap_store.load_config()
    store = StateStore(
        project_root,
        state_dir=config.state_dir,
        design_dir=config.design_dir,
        config_path=bootstrap_store.config_path,
        strict_schema_validation=config.strict_schema_validation,
        json_subset_only=config.json_subset_only,
    )

    logger = _setup_logging(config, project_root)
    logger.info("Shepherd starting.")

    _validate_state_directories(store)
    store.load_goals()
    store.load_sources()

    planner = Planner(store)
    max_retries_per_task = min(config.max_retries_per_task, 1)
    if config.max_retries_per_task > max_retries_per_task:
        logger.warning(
            "max_retries_per_task=%s exceeds safety limit; clamped to %s.",
            config.max_retries_per_task,
            max_retries_per_task,
        )
    retry_tracker = RetryTracker(
        max_retries_per_task=max_retries_per_task,
        max_consecutive_failures=config.max_consecutive_failures,
    )

    try:
        _run_loop(store, planner, config, retry_tracker, logger, project_root)
    except StopExecution as exc:
        logger.error("Execution stopped: %s", exc)
    except (MissingStateError, StateError, PlannerError, PolicyViolation) as exc:
        logger.error("Execution halted: %s", exc)
    except MCPError as exc:
        logger.error("MCP error: %s", exc)
    finally:
        logger.info("Shepherd exiting.")


def _run_loop(
    store: StateStore,
    planner: Planner,
    config: Config,
    retry_tracker: RetryTracker,
    logger: logging.Logger,
    project_root: Path,
) -> None:
    while True:
        if store.active_task_path.exists():
            raise StopExecution("ACTIVE_TASK.yaml exists; manual intervention required.")

        plan = planner.ensure_plan()
        task = planner.select_next_task(plan)
        if task is None:
            logger.info("No pending tasks available. Stopping.")
            return

        active_task = planner.activate_task(plan, task["id"], config.task_timeout_seconds)
        store.write_plan(plan)
        planner.write_progress(plan)
        store.write_active_task(active_task)

        executor = MCPClient(
            config.mcp_command,
            config.startup_timeout_seconds,
            config.task_timeout_seconds,
        )
        payload = {"task": active_task}

        try:
            result = executor.run_task(payload)
        except MCPTimeoutError as exc:
            raise StopExecution(str(exc)) from exc

        store.clear_active_task()
        if result.stderr.strip():
            logger.warning("MCP stderr: %s", result.stderr.strip())
        store.write_last_result(result.payload)

        assert_no_forbidden_changes(
            result.payload.get("files_changed", []),
            project_root=project_root,
            design_dir=store.design_dir,
            state_dir=store.ai_dir,
        )

        status = result.payload.get("status")
        if status == "success":
            planner.finalize_task(plan, task["id"], "done")
            retry_tracker.record_success(task["id"])
            _append_summary(planner, task["id"], status, result.payload)
            store.write_plan(plan)
            planner.write_progress(plan)
            continue

        if status == "blocked":
            planner.finalize_task(plan, task["id"], "blocked")
            store.write_plan(plan)
            planner.write_progress(plan)
            _append_summary(planner, task["id"], status, result.payload)
            raise StopExecution("Codex reported blocked.")

        if status == "failed":
            retry_tracker.record_failure(task["id"])
            if retry_tracker.too_many_consecutive_failures():
                raise StopExecution("Max consecutive failures reached.")
            if retry_tracker.can_retry(task["id"]):
                planner.reset_task_for_retry(plan, task["id"])
                store.write_plan(plan)
                planner.write_progress(plan)
                _append_summary(planner, task["id"], status, result.payload)
                continue
            planner.finalize_task(plan, task["id"], "failed")
            store.write_plan(plan)
            planner.write_progress(plan)
            _append_summary(planner, task["id"], status, result.payload)
            raise StopExecution("Task failed more than once.")

        raise StopExecution(f"Unexpected Codex status: {status}")


def _append_summary(
    planner: Planner, task_id: str, status: str, payload: dict[str, object]
) -> None:
    entry_lines = [
        f"Task {task_id}: {status}",
        f"Files changed: {len(payload.get('files_changed', []))}",
        f"Tests run: {len(payload.get('tests_run', []))}",
        f"Notes: {payload.get('notes', '')}",
    ]
    planner.append_summary("\n".join(entry_lines))


def _validate_state_directories(store: StateStore) -> None:
    if not store.ai_dir.exists():
        raise MissingStateError(f"State directory missing: {store.ai_dir}")
    if not store.design_dir.exists():
        raise MissingStateError(f"Design directory missing: {store.design_dir}")


def _setup_logging(config: Config, project_root: Path) -> logging.Logger:
    logger = logging.getLogger("shepherd")
    logger.setLevel(config.log_level.upper())
    logger.handlers.clear()
    log_path = Path(config.log_file)
    if not log_path.is_absolute():
        log_path = project_root / log_path
    if not log_path.parent.exists():
        raise MissingStateError(f"Log directory missing: {log_path.parent}")
    handler = logging.FileHandler(log_path, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Codex Shepherd daemon")
    parser.add_argument("--project-root", required=True, help="Path to target project root")
    return parser.parse_args()


if __name__ == "__main__":
    main()
