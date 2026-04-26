from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
import os
import tempfile


class StateError(RuntimeError):
    pass


@dataclass
class TaskState:
    last_run_at: str | None = None
    last_content_hash: str | None = None


class SchedulerState:
    def __init__(self, path: Path, tasks: dict[str, TaskState] | None = None):
        self.path = path
        self.tasks = tasks or {}

    @classmethod
    def load(cls, path: str | Path) -> "SchedulerState":
        state_path = Path(path)
        if not state_path.exists():
            return cls(state_path)
        try:
            raw = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise StateError(f"状态文件 JSON 格式错误: {state_path}") from exc

        tasks_raw = raw.get("tasks", {}) if isinstance(raw, dict) else {}
        tasks: dict[str, TaskState] = {}
        if isinstance(tasks_raw, dict):
            for task_id, task_raw in tasks_raw.items():
                if not isinstance(task_raw, dict):
                    continue
                tasks[str(task_id)] = TaskState(
                    last_run_at=task_raw.get("last_run_at"),
                    last_content_hash=task_raw.get("last_content_hash"),
                )
        return cls(state_path, tasks)

    def task(self, task_id: str) -> TaskState:
        if task_id not in self.tasks:
            self.tasks[task_id] = TaskState()
        return self.tasks[task_id]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "tasks": {
                task_id: {
                    "last_run_at": task.last_run_at,
                    "last_content_hash": task.last_content_hash,
                }
                for task_id, task in sorted(self.tasks.items())
            }
        }
        data = json.dumps(payload, ensure_ascii=False, indent=2)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            delete=False,
            dir=str(self.path.parent),
            prefix=f".{self.path.name}.",
            suffix=".tmp",
        ) as tmp:
            tmp.write(data)
            tmp_path = Path(tmp.name)
        os.replace(tmp_path, self.path)
