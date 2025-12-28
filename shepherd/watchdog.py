"""Execution watchdog utilities."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RetryTracker:
    max_retries_per_task: int
    max_consecutive_failures: int
    attempts: dict[str, int] = field(default_factory=dict)
    consecutive_failures: int = 0

    def record_success(self, task_id: str) -> None:
        self.consecutive_failures = 0
        self.attempts.pop(task_id, None)

    def record_failure(self, task_id: str) -> None:
        self.consecutive_failures += 1
        self.attempts[task_id] = self.attempts.get(task_id, 0) + 1

    def can_retry(self, task_id: str) -> bool:
        return self.attempts.get(task_id, 0) <= self.max_retries_per_task

    def too_many_consecutive_failures(self) -> bool:
        return self.consecutive_failures >= self.max_consecutive_failures
