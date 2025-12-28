import json
import sys


def main() -> int:
    line = sys.stdin.readline()
    if not line:
        return 1
    try:
        payload = json.loads(line)
    except json.JSONDecodeError as exc:
        sys.stdout.write(json.dumps({
            "status": "failed",
            "files_changed": [],
            "tests_run": [],
            "notes": f"invalid json input: {exc}"
        }) + "\n")
        return 0

    task = payload.get("task", {})
    task_id = task.get("id", "unknown")
    response = {
        "status": "success",
        "files_changed": [],
        "tests_run": [],
        "notes": f"stub executed task {task_id}"
    }
    sys.stdout.write(json.dumps(response) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
