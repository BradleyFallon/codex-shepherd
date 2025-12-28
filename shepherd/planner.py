"""Deterministic planner that selects tasks from the plan."""

from __future__ import annotations

from typing import Any, Optional

from .state import StateStore


class PlannerError(Exception):
    """Raised when planner encounters ambiguous or invalid planning state."""


class Planner:
    def __init__(self, store: StateStore) -> None:
        self.store = store

    def ensure_plan(self) -> dict[str, Any]:
        if not self.store.plan_path.exists():
            plan = {"version": 1, "objectives": [], "tasks": []}
            self.store.write_plan(plan)
            return plan
        return self.store.load_plan()

    def select_next_task(self, plan: dict[str, Any]) -> Optional[dict[str, Any]]:
        tasks = plan.get("tasks", [])
        task_map = self._task_map(tasks)
        for task in tasks:
            status = task.get("status")
            if status == "active":
                raise PlannerError("Plan contains an active task without execution context.")
            if status != "pending":
                continue
            depends_on = task.get("depends_on", [])
            if not self._dependencies_satisfied(depends_on, task_map):
                continue
            return task
        return None

    def activate_task(self, plan: dict[str, Any], task_id: str, timeout_seconds: int) -> dict[str, Any]:
        task = self._find_task(plan, task_id)
        task["status"] = "active"
        self._refresh_objective_statuses(plan)
        active_task = dict(task)
        active_task["timeout_seconds"] = timeout_seconds
        return active_task

    def finalize_task(self, plan: dict[str, Any], task_id: str, status: str) -> None:
        task = self._find_task(plan, task_id)
        task["status"] = status
        self._refresh_objective_statuses(plan)

    def reset_task_for_retry(self, plan: dict[str, Any], task_id: str) -> None:
        task = self._find_task(plan, task_id)
        task["status"] = "pending"
        self._refresh_objective_statuses(plan)

    def write_progress(self, plan: dict[str, Any]) -> None:
        objectives = {obj["id"]: obj["status"] for obj in plan.get("objectives", [])}
        tasks = {task["id"]: task["status"] for task in plan.get("tasks", [])}
        progress = {"objectives": objectives, "tasks": tasks}
        self.store.write_progress(_json_dump(progress))

    def append_summary(self, entry: str) -> None:
        if not entry.endswith("\n"):
            entry = entry + "\n"
        if not self.store.summary_path.exists():
            content = "# Execution Summary\n\n(No execution has occurred yet.)\n\n" + entry
        else:
            existing = self.store.load_summary()
            if not existing.strip():
                content = "# Execution Summary\n\n(No execution has occurred yet.)\n\n" + entry
            else:
                content = existing.rstrip() + "\n\n" + entry
        self.store.write_summary(content)

    def _task_map(self, tasks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        task_map: dict[str, dict[str, Any]] = {}
        for task in tasks:
            task_id = task.get("id")
            if not isinstance(task_id, str) or not task_id:
                raise PlannerError("Task id must be a non-empty string.")
            if task_id in task_map:
                raise PlannerError(f"Duplicate task id: {task_id}")
            task_map[task_id] = task
        return task_map

    def _dependencies_satisfied(self, depends_on: list[Any], task_map: dict[str, dict[str, Any]]) -> bool:
        if not isinstance(depends_on, list):
            raise PlannerError("depends_on must be a list.")
        for dep in depends_on:
            if not isinstance(dep, str):
                raise PlannerError("depends_on entries must be strings.")
            if dep not in task_map:
                raise PlannerError(f"Dependency not found: {dep}")
            if task_map[dep].get("status") != "done":
                return False
        return True

    def _find_task(self, plan: dict[str, Any], task_id: str) -> dict[str, Any]:
        for task in plan.get("tasks", []):
            if task.get("id") == task_id:
                return task
        raise PlannerError(f"Task not found: {task_id}")

    def _refresh_objective_statuses(self, plan: dict[str, Any]) -> None:
        objectives = plan.get("objectives", [])
        tasks = plan.get("tasks", [])
        tasks_by_objective: dict[str, list[dict[str, Any]]] = {}
        for task in tasks:
            objective_id = task.get("objective")
            if isinstance(objective_id, str):
                tasks_by_objective.setdefault(objective_id, []).append(task)

        for obj in objectives:
            obj_id = obj.get("id")
            if not isinstance(obj_id, str):
                continue
            related = tasks_by_objective.get(obj_id, [])
            if not related:
                continue
            statuses = {task.get("status") for task in related}
            if statuses <= {"done"}:
                obj["status"] = "complete"
            elif statuses & {"active", "done", "failed", "blocked"}:
                obj["status"] = "in_progress"
            else:
                obj["status"] = "pending"


def _json_dump(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, indent=2) + "\n"
