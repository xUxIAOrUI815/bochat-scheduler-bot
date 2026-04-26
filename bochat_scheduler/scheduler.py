from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .config import AppConfig, TaskConfig, WEEKDAYS, parse_hhmm
from .state import SchedulerState


def now_for_config(config: AppConfig) -> datetime:
    return datetime.now(ZoneInfo(config.timezone))


def due_tasks(
    config: AppConfig,
    state: SchedulerState,
    now: datetime | None = None,
) -> list[TaskConfig]:
    current = now or now_for_config(config)
    return [task for task in config.enabled_tasks() if is_due(task, state, current)]


def is_due(task: TaskConfig, state: SchedulerState, now: datetime) -> bool:
    task_state = state.task(task.id)
    last_run_at = _parse_dt(task_state.last_run_at)

    if task.schedule == "interval":
        if last_run_at is None:
            return True
        assert task.interval_secs is not None
        return now - last_run_at >= timedelta(seconds=task.interval_secs)

    assert task.time is not None
    hour, minute = parse_hhmm(task.time)
    scheduled_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now < scheduled_at:
        return False

    if task.schedule == "daily":
        return last_run_at is None or last_run_at.date() < now.date()

    if task.schedule == "weekly":
        assert task.weekday is not None
        if now.weekday() != WEEKDAYS[task.weekday]:
            return False
        week_start = (now - timedelta(days=now.weekday())).date()
        return last_run_at is None or last_run_at.date() < week_start

    return False


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
