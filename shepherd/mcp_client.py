"""Minimal MCP client for Codex task execution."""

from __future__ import annotations

import json
import shlex
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


class MCPError(Exception):
    """Base class for MCP execution errors."""


class MCPTimeoutError(MCPError):
    """Raised when MCP execution exceeds time limits."""


class MCPProtocolError(MCPError):
    """Raised when MCP output is invalid or unexpected."""


class MCPProcessError(MCPError):
    """Raised when MCP process fails to start or exits unexpectedly."""


@dataclass
class MCPResult:
    payload: dict[str, Any]
    stderr: str


class MCPClient:
    """Executes a single task by spawning the configured MCP command."""

    def __init__(
        self,
        command: str,
        startup_timeout_seconds: int,
        task_timeout_seconds: int,
        *,
        cwd: Optional[Path] = None,
    ) -> None:
        if not isinstance(command, str) or not command.strip():
            raise MCPProcessError("MCP command must be a non-empty string.")
        self.command = command
        self.startup_timeout_seconds = startup_timeout_seconds
        self.task_timeout_seconds = task_timeout_seconds
        self.cwd = cwd

    def run_task(self, payload: dict[str, Any]) -> MCPResult:
        if not isinstance(payload, dict):
            raise MCPProtocolError("Task payload must be a JSON object.")
        process = self._start_process()
        try:
            self._ensure_started(process)
            request = json.dumps(payload)
            response_line = self._send_and_read(process, request, self.task_timeout_seconds)
            if response_line is None:
                raise MCPTimeoutError("Timed out waiting for MCP response.")
            response = self._parse_response(response_line)
            self._terminate(process)
            stderr = self._drain_stream(process.stderr)
            return MCPResult(payload=response, stderr=stderr)
        finally:
            if process.poll() is None:
                self._terminate(process)

    def _start_process(self) -> subprocess.Popen[str]:
        args = shlex.split(self.command)
        try:
            return subprocess.Popen(
                args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=str(self.cwd) if self.cwd is not None else None,
            )
        except OSError as exc:
            raise MCPProcessError(f"Failed to start MCP command: {exc}") from exc

    def _ensure_started(self, process: subprocess.Popen[str]) -> None:
        if process.poll() is not None:
            raise MCPProcessError("MCP process exited during startup.")
        if self.startup_timeout_seconds < 0:
            raise MCPProcessError("startup_timeout_seconds must be non-negative.")
        # No protocol-level readiness signal is assumed; process liveness is treated as ready.
        return

    def _send_and_read(
        self, process: subprocess.Popen[str], request: str, timeout_seconds: int
    ) -> Optional[str]:
        if process.stdin is None or process.stdout is None:
            raise MCPProcessError("MCP process stdio is not available.")
        process.stdin.write(request + "\n")
        process.stdin.flush()

        result: dict[str, Optional[str]] = {"line": None}

        def _reader() -> None:
            result["line"] = process.stdout.readline()

        thread = threading.Thread(target=_reader, daemon=True)
        thread.start()
        thread.join(timeout_seconds)
        if thread.is_alive():
            return None
        return result["line"]

    def _parse_response(self, line: str) -> dict[str, Any]:
        if not line:
            raise MCPProtocolError("MCP response was empty.")
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise MCPProtocolError(f"MCP response is not valid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise MCPProtocolError("MCP response must be a JSON object.")
        return data

    def _terminate(self, process: subprocess.Popen[str]) -> None:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)

    def _drain_stream(self, stream: Optional[Any]) -> str:
        if stream is None:
            return ""
        return stream.read() or ""
