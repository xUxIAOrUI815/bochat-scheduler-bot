from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from bochat_scheduler.config import AppConfig, TaskConfig
from bochat_scheduler.scheduler import is_due
from bochat_scheduler.state import SchedulerState


TZ = ZoneInfo("Asia/Shanghai")


def state(tmp_path: Path) -> SchedulerState:
    return SchedulerState.load(tmp_path / "state.json")


def test_daily_due_after_time_once_per_day(tmp_path: Path):
    task = TaskConfig(
        id="daily",
        type="send_message",
        enabled=True,
        group_id="g_1",
        schedule="daily",
        time="09:00",
        message="hello",
    )
    scheduler_state = state(tmp_path)
    now = datetime(2026, 4, 26, 9, 1, tzinfo=TZ)

    assert is_due(task, scheduler_state, now)
    scheduler_state.task("daily").last_run_at = now.isoformat()
    assert not is_due(task, scheduler_state, now.replace(hour=10))


def test_weekly_due_only_on_configured_weekday(tmp_path: Path):
    task = TaskConfig(
        id="weekly",
        type="send_message",
        enabled=True,
        group_id="g_1",
        schedule="weekly",
        weekday="monday",
        time="10:00",
        message="hello",
    )
    scheduler_state = state(tmp_path)

    assert is_due(task, scheduler_state, datetime(2026, 4, 27, 10, 1, tzinfo=TZ))
    assert not is_due(task, scheduler_state, datetime(2026, 4, 28, 10, 1, tzinfo=TZ))


def test_interval_due_after_elapsed_seconds(tmp_path: Path):
    task = TaskConfig(
        id="interval",
        type="send_message",
        enabled=True,
        group_id="g_1",
        schedule="interval",
        interval_secs=60,
        message="hello",
    )
    scheduler_state = state(tmp_path)
    now = datetime(2026, 4, 26, 10, 0, tzinfo=TZ)

    assert is_due(task, scheduler_state, now)
    scheduler_state.task("interval").last_run_at = (now - timedelta(seconds=30)).isoformat()
    assert not is_due(task, scheduler_state, now)
    scheduler_state.task("interval").last_run_at = (now - timedelta(seconds=61)).isoformat()
    assert is_due(task, scheduler_state, now)
