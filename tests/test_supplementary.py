"""Supplementary unit tests for bochat-scheduler-bot.

Covers gaps identified in the test plan:
- config edge cases
- scheduler edge cases
- tasks edge cases
- website edge cases
- state edge cases
- runner edge cases
"""

from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import asyncio

import pytest

from bochat_scheduler.config import ConfigError, parse_config, AppConfig, TaskConfig
from bochat_scheduler.scheduler import due_tasks, is_due, now_for_config
from bochat_scheduler.state import SchedulerState, StateError
from bochat_scheduler.tasks import (
    TaskRunResult,
    execute_task,
    format_website_change_message,
)
from bochat_scheduler.website import (
    WebsiteSnapshot,
    WebsiteError,
    parse_website_content,
)
from bochat_scheduler.runner import find_task, check_due, run_once


TZ = ZoneInfo("Asia/Shanghai")
NOW = datetime(2026, 4, 26, 10, 0, tzinfo=TZ)


# ── helpers ──────────────────────────────────────────────────────────────────

def base_config_dict():
    return {
        "base_url": "http://127.0.0.1:8080",
        "bot_token": "b_token",
        "state_path": "scheduler_state.json",
        "timezone": "Asia/Shanghai",
        "tasks": [
            {
                "id": "daily",
                "type": "send_message",
                "enabled": True,
                "group_id": "g_1",
                "schedule": "daily",
                "time": "09:00",
                "message": "hello",
            }
        ],
    }


def make_app_config(tmp_path: Path, tasks: list[TaskConfig] | None = None) -> AppConfig:
    return AppConfig(
        base_url="http://127.0.0.1:8080",
        bot_token="b_token",
        state_path=tmp_path / "state.json",
        timezone="Asia/Shanghai",
        tasks=tasks or [],
    )


class FakeSender:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.messages: list[tuple[str, str]] = []

    async def send_text(self, group_id: str, text: str):
        if self.fail:
            raise RuntimeError("send failed")
        self.messages.append((group_id, text))


async def fake_snapshot(url: str, title: str = "Site", content_hash: str = "hash-v1") -> WebsiteSnapshot:
    return WebsiteSnapshot(url=url, title=title, summary="hello", content_hash=content_hash)


# ── config ───────────────────────────────────────────────────────────────────

def test_daily_missing_time_rejected(tmp_path: Path):
    raw = base_config_dict()
    raw["tasks"][0] = {
        "id": "daily",
        "type": "send_message",
        "group_id": "g_1",
        "schedule": "daily",
        "message": "hello",
    }
    with pytest.raises(ConfigError, match="time"):
        parse_config(raw, base_dir=tmp_path)


def test_weekly_invalid_weekday_rejected(tmp_path: Path):
    raw = base_config_dict()
    raw["tasks"][0] = {
        "id": "weekly",
        "type": "send_message",
        "group_id": "g_1",
        "schedule": "weekly",
        "weekday": "notaday",
        "time": "09:00",
        "message": "hello",
    }
    with pytest.raises(ConfigError, match="weekday"):
        parse_config(raw, base_dir=tmp_path)


def test_invalid_timezone_rejected(tmp_path: Path):
    raw = base_config_dict()
    raw["timezone"] = "Mars/Unknown"
    with pytest.raises(ConfigError, match="timezone"):
        parse_config(raw, base_dir=tmp_path)


def test_send_message_missing_message_rejected(tmp_path: Path):
    raw = base_config_dict()
    raw["tasks"][0] = {
        "id": "daily",
        "type": "send_message",
        "group_id": "g_1",
        "schedule": "daily",
        "time": "09:00",
    }
    with pytest.raises(ConfigError, match="message"):
        parse_config(raw, base_dir=tmp_path)


def test_weekly_missing_time_rejected(tmp_path: Path):
    raw = base_config_dict()
    raw["tasks"][0] = {
        "id": "weekly",
        "type": "send_message",
        "group_id": "g_1",
        "schedule": "weekly",
        "weekday": "monday",
        "message": "hello",
    }
    with pytest.raises(ConfigError, match="time"):
        parse_config(raw, base_dir=tmp_path)


def test_check_url_invalid_url_scheme_rejected(tmp_path: Path):
    raw = base_config_dict()
    raw["tasks"][0] = {
        "id": "site",
        "type": "check_url",
        "group_id": "g_1",
        "schedule": "daily",
        "time": "09:00",
        "url": "ftp://example.com",
    }
    with pytest.raises(ConfigError, match="url 必须是 http:// 或 https://"):
        parse_config(raw, base_dir=tmp_path)


# ── scheduler ────────────────────────────────────────────────────────────────

def test_due_tasks_filters_disabled(tmp_path: Path):
    tasks = [
        TaskConfig("t1", "send_message", False, "g_1", "daily", time="09:00", message="hello"),
        TaskConfig("t2", "send_message", True, "g_1", "daily", time="09:00", message="world"),
    ]
    cfg = make_app_config(tmp_path, tasks)
    state = SchedulerState.load(cfg.state_path)
    now = datetime(2026, 4, 26, 10, 0, tzinfo=TZ)
    due = due_tasks(cfg, state, now)
    assert len(due) == 1
    assert due[0].id == "t2"


def test_due_tasks_not_yet_time(tmp_path: Path):
    tasks = [
        TaskConfig("t1", "send_message", True, "g_1", "daily", time="18:00", message="hello"),
    ]
    cfg = make_app_config(tmp_path, tasks)
    state = SchedulerState.load(cfg.state_path)
    now = datetime(2026, 4, 26, 10, 0, tzinfo=TZ)
    due = due_tasks(cfg, state, now)
    assert len(due) == 0


def test_daily_not_due_before_time(tmp_path: Path):
    task = TaskConfig("d", "send_message", True, "g_1", "daily", time="09:00", message="hi")
    state = SchedulerState.load(Path("/tmp/sched.json"))
    now = datetime(2026, 4, 26, 8, 59, tzinfo=TZ)
    assert not is_due(task, state, now)


def test_weekly_not_due_on_wrong_day(tmp_path: Path):
    task = TaskConfig("w", "send_message", True, "g_1", "weekly", weekday="monday", time="10:00", message="hi")
    state = SchedulerState.load(Path("/tmp/sched2.json"))
    # 2026-04-28 is Tuesday
    assert not is_due(task, state, datetime(2026, 4, 28, 10, 1, tzinfo=TZ))


# ── tasks ────────────────────────────────────────────────────────────────────

def test_check_url_no_change_sends_nothing(tmp_path: Path):
    task = TaskConfig("site", "check_url", True, "g_1", "daily", time="09:00", url="https://x.com", title="X")
    state = SchedulerState.load(tmp_path / "s.json")
    state.task("site").last_content_hash = "hash-v1"
    state.save()
    sender = FakeSender()

    async def fetcher(url):
        return await fake_snapshot(url, content_hash="hash-v1")

    result = asyncio.run(execute_task(task, state, sender, NOW, website_fetcher=fetcher))
    assert result.sent is False
    assert "no content change" in result.message
    assert len(sender.messages) == 0


def test_check_url_dry_run_first_run(tmp_path: Path):
    task = TaskConfig("site", "check_url", True, "g_1", "daily", time="09:00", url="https://x.com", title="X")
    state = SchedulerState.load(tmp_path / "s.json")
    sender = FakeSender()

    async def fetcher(url):
        return await fake_snapshot(url, content_hash="hash-v1")

    result = asyncio.run(execute_task(task, state, sender, NOW, dry_run=True, website_fetcher=fetcher))
    assert result.sent is False
    assert "initial content hash" in result.message
    # dry_run: state must NOT be persisted
    loaded = SchedulerState.load(state.path)
    assert loaded.task("site").last_content_hash is None


def test_format_website_change_message_includes_title_and_summary():
    snapshot = WebsiteSnapshot(
        url="https://example.com",
        title="Example Page",
        summary="Summary of changes",
        content_hash="abc123",
    )
    message = format_website_change_message("Custom Title", snapshot)
    assert "【网站更新】Custom Title" in message
    assert "https://example.com" in message
    assert "Summary of changes" in message


def test_execute_task_invalid_type_raises(tmp_path: Path):
    task = TaskConfig("bad", "invalid_type", True, "g_1", "daily", time="09:00", message="x")  # type: ignore[arg-type]
    state = SchedulerState.load(tmp_path / "s.json")
    with pytest.raises(ValueError, match="unsupported task type"):
        asyncio.run(execute_task(task, state, FakeSender(), NOW))


# ── website ──────────────────────────────────────────────────────────────────

def test_parse_website_content_no_title():
    snapshot = parse_website_content("https://example.com", "<html><body>Just body</body></html>")
    assert snapshot.url in snapshot.title  # fallback to URL
    assert len(snapshot.content_hash) == 64


def test_parse_website_content_empty_body():
    snapshot = parse_website_content("https://example.com", "<html><head><title>T</title></head><body></body></html>")
    assert snapshot.title == "T"
    assert len(snapshot.summary) >= 0


def test_parse_website_content_strips_scripts():
    snapshot = parse_website_content(
        "https://x.com",
        "<html><head><title>T</title><script>alert('xss')</script></head><body>Content</body></html>",
    )
    assert "alert" not in snapshot.summary
    assert "Content" in snapshot.summary


# ── state ────────────────────────────────────────────────────────────────────

def test_state_handles_corrupted_json(tmp_path: Path):
    path = tmp_path / "corrupt.json"
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(StateError):
        SchedulerState.load(path)


def test_state_atomic_write(tmp_path: Path):
    path = tmp_path / "atomic.json"
    state = SchedulerState.load(path)
    state.task("t1").last_run_at = "2026-01-01T00:00:00+00:00"
    state.task("t1").last_content_hash = "abc"
    state.save()

    loaded = SchedulerState.load(path)
    assert loaded.task("t1").last_run_at == "2026-01-01T00:00:00+00:00"
    assert loaded.task("t1").last_content_hash == "abc"


# ── runner ───────────────────────────────────────────────────────────────────

def test_find_task_raises_for_unknown(tmp_path: Path):
    cfg = make_app_config(tmp_path)
    with pytest.raises(ValueError, match="未找到任务"):
        find_task(cfg, "nonexistent")


def test_check_due_returns_only_due_tasks(tmp_path: Path):
    tasks = [
        TaskConfig("t1", "send_message", True, "g_1", "daily", time="09:00", message="m1"),
        TaskConfig("t2", "send_message", True, "g_1", "daily", time="18:00", message="m2"),
    ]
    cfg = make_app_config(tmp_path, tasks)
    state = SchedulerState.load(cfg.state_path)
    # Patch now_for_config indirectly: pass now through due_tasks
    from bochat_scheduler.scheduler import due_tasks
    now = datetime(2026, 4, 26, 10, 0, tzinfo=TZ)
    due = due_tasks(cfg, state, now)
    assert len(due) == 1
    assert due[0].id == "t1"


def test_run_once_send_message(tmp_path: Path):
    task = TaskConfig("t1", "send_message", True, "g_1", "daily", time="09:00", message="hello")
    cfg = make_app_config(tmp_path, [task])
    state = SchedulerState.load(cfg.state_path)
    sender = FakeSender()

    # Use lower-level call
    from bochat_scheduler.tasks import execute_task
    result = asyncio.run(execute_task(task, state, sender, NOW))
    assert result.sent is True
    assert sender.messages == [("g_1", "hello")]
