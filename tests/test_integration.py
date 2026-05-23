"""Integration tests for bochat-scheduler-bot against live BoChat server.

Requires a running BoChat instance with a test bot already in the target group.

Environment:
  BOCHAT_BASE_URL, BOCHAT_BOT_TOKEN, BOCHAT_GROUP_ID
  (set via environment variables)
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from bochat_scheduler.config import AppConfig, TaskConfig
from bochat_scheduler.runner import check_due, find_task, run_once
from bochat_scheduler.scheduler import due_tasks, now_for_config
from bochat_scheduler.sender import BoChatSender, DryRunSender
from bochat_scheduler.state import SchedulerState
from bochat_scheduler.tasks import TaskRunResult, execute_task
from bochat_scheduler.website import fetch_website_snapshot, parse_website_content

# ── Test environment constants ───────────────────────────────────────────────
# These must be set via environment variables before running integration tests:
#   BOCHAT_BASE_URL, BOCHAT_BOT_TOKEN, BOCHAT_GROUP_ID

BASE_URL = os.environ.get("BOCHAT_BASE_URL", "http://127.0.0.1:8080")
BOT_TOKEN = os.environ.get("BOCHAT_BOT_TOKEN", "")
GROUP_ID = os.environ.get("BOCHAT_GROUP_ID", "")
TZ = ZoneInfo("Asia/Shanghai")


def make_integration_config(tmp_path: Path, tasks: list[TaskConfig] | None = None) -> AppConfig:
    return AppConfig(
        base_url=BASE_URL,
        bot_token=BOT_TOKEN,
        state_path=tmp_path / "integration_state.json",
        timezone="Asia/Shanghai",
        tasks=tasks or [],
    )


# ── Real BoChat sender integration ───────────────────────────────────────────

def test_real_sender_send_text_to_group():
    """Send a real message to the BoChat group using the BoChatSender."""
    async def _test():
        cfg = make_integration_config(Path("/tmp"))
        sender = BoChatSender(cfg)
        try:
            result = await sender.send_text(GROUP_ID, "【集成测试】Scheduler Bot 测试消息发送功能正常。")
            assert result.msg_id is not None
            assert result.dry_run is False
        finally:
            await sender.close()

    asyncio.run(_test())


# ── send_message task integration ────────────────────────────────────────────

def test_execute_send_message_integration(tmp_path: Path):
    """Execute a send_message task against the real BoChat server."""
    task = TaskConfig(
        id="integration-send",
        type="send_message",
        enabled=True,
        group_id=GROUP_ID,
        schedule="daily",
        time="09:00",
        message="【集成测试】Scheduler Bot send_message 任务执行成功！",
    )
    cfg = make_integration_config(tmp_path, [task])
    state = SchedulerState.load(cfg.state_path)
    sender = BoChatSender(cfg)

    async def _test():
        try:
            now = datetime(2026, 5, 22, 21, 0, tzinfo=TZ)
            result = await execute_task(task, state, sender, now)
            assert result.executed is True
            assert result.sent is True
            assert result.message == "message sent"
            # Verify state was persisted
            loaded = SchedulerState.load(cfg.state_path)
            assert loaded.task("integration-send").last_run_at is not None
        finally:
            await sender.close()

    asyncio.run(_test())


def test_run_once_send_message_integration(tmp_path: Path):
    """Test the run_once function (same as CLI 'run-once' command)."""
    task = TaskConfig(
        id="run-once-test",
        type="send_message",
        enabled=True,
        group_id=GROUP_ID,
        schedule="daily",
        time="09:00",
        message="【集成测试】Scheduler Bot run-once 命令测试通过！",
    )
    cfg = make_integration_config(tmp_path, [task])
    result = asyncio.run(run_once(cfg, "run-once-test", dry_run=False))
    assert result.task_id == "run-once-test"
    assert result.sent is True
    assert result.executed is True


# ── check_url task integration ───────────────────────────────────────────────

def test_check_url_first_run_integration(tmp_path: Path):
    """First check_url run should record hash without sending."""
    task = TaskConfig(
        id="site-check",
        type="check_url",
        enabled=True,
        group_id=GROUP_ID,
        schedule="daily",
        time="09:00",
        url="https://example.com/",
        title="Example Site",
    )
    cfg = make_integration_config(tmp_path, [task])
    result = asyncio.run(run_once(cfg, "site-check", dry_run=False))
    assert result.task_id == "site-check"
    assert result.executed is True
    # First run: should record hash, not send
    assert "initial" in result.message.lower() or result.sent is False


def test_check_url_second_run_detects_no_change(tmp_path: Path):
    """Second check_url run with unchanged content should not send."""
    task = TaskConfig(
        id="site-check-2",
        type="check_url",
        enabled=True,
        group_id=GROUP_ID,
        schedule="daily",
        time="09:00",
        url="https://example.com/",
        title="Example Site",
    )
    cfg = make_integration_config(tmp_path, [task])

    # First run records hash
    result1 = asyncio.run(run_once(cfg, "site-check-2", dry_run=False))
    assert result1.executed is True

    # Second run should detect no change
    result2 = asyncio.run(run_once(cfg, "site-check-2", dry_run=False))
    assert result2.executed is True
    assert result2.sent is False
    assert "no content change" in result2.message


# ── Dry-run integration ──────────────────────────────────────────────────────

def test_dry_run_send_message(tmp_path: Path):
    """Dry-run should execute but not persist state."""
    task = TaskConfig(
        id="dry-send",
        type="send_message",
        enabled=True,
        group_id=GROUP_ID,
        schedule="daily",
        time="09:00",
        message="这条消息不应实际发送",
    )
    cfg = make_integration_config(tmp_path, [task])
    result = asyncio.run(run_once(cfg, "dry-send", dry_run=True))
    assert result.task_id == "dry-send"
    assert result.sent is True
    # State should NOT have been updated
    loaded = SchedulerState.load(cfg.state_path)
    assert loaded.task("dry-send").last_run_at is None


def test_dry_run_check_url(tmp_path: Path):
    """Dry-run check_url first run should not persist hash."""
    task = TaskConfig(
        id="dry-url",
        type="check_url",
        enabled=True,
        group_id=GROUP_ID,
        schedule="daily",
        time="09:00",
        url="https://example.com/",
        title="Example Site",
    )
    cfg = make_integration_config(tmp_path, [task])
    result = asyncio.run(run_once(cfg, "dry-url", dry_run=True))
    assert result.executed is True
    # State should NOT have been persisted
    loaded = SchedulerState.load(cfg.state_path)
    assert loaded.task("dry-url").last_content_hash is None


# ── Website snapshot integration ─────────────────────────────────────────────

def test_fetch_real_website_snapshot():
    """Fetch a real public website and verify snapshot structure."""
    async def _test():
        snapshot = await fetch_website_snapshot("https://example.com/", timeout_secs=15)
        assert snapshot.url == "https://example.com/"
        assert len(snapshot.title) > 0
        assert len(snapshot.content_hash) == 64
        assert isinstance(snapshot.summary, str)

    asyncio.run(_test())


def test_website_snapshot_hash_stable():
    """Same content should produce the same hash."""
    snapshot1 = parse_website_content("https://example.com", "<html><head><title>T</title></head><body>B</body></html>")
    snapshot2 = parse_website_content("https://example.com", "<html><head><title>T</title></head><body>B</body></html>")
    assert snapshot1.content_hash == snapshot2.content_hash


def test_website_snapshot_hash_differs():
    """Different content should produce different hashes."""
    snapshot1 = parse_website_content("https://example.com", "<html><body>A</body></html>")
    snapshot2 = parse_website_content("https://example.com", "<html><body>B</body></html>")
    assert snapshot1.content_hash != snapshot2.content_hash


# ── Scheduler integration with real server ───────────────────────────────────

def test_check_due_with_real_config(tmp_path: Path):
    """check_due should return currently due tasks."""
    tasks = [
        TaskConfig(
            id="due-send",
            type="send_message",
            enabled=True,
            group_id=GROUP_ID,
            schedule="daily",
            time="09:00",
            message="【集成测试】到期任务检查测试。",
        ),
        TaskConfig(
            id="future-task",
            type="send_message",
            enabled=True,
            group_id=GROUP_ID,
            schedule="daily",
            time="23:59",
            message="这条消息不应在到期任务中",
        ),
    ]
    cfg = make_integration_config(tmp_path, tasks)
    state = SchedulerState.load(cfg.state_path)
    now = datetime(2026, 5, 22, 21, 0, tzinfo=TZ)
    due = due_tasks(cfg, state, now)
    # Only the 09:00 task should be due (now is 21:00)
    due_ids = {t.id for t in due}
    assert "due-send" in due_ids
    assert "future-task" not in due_ids


def test_execute_check_url_with_real_site(tmp_path: Path):
    """Integration: check_url against a real site via run_once."""
    task = TaskConfig(
        id="real-url-check",
        type="check_url",
        enabled=True,
        group_id=GROUP_ID,
        schedule="daily",
        time="09:00",
        url="https://example.com/",
        title="Example Site",
    )
    cfg = make_integration_config(tmp_path, [task])
    result = asyncio.run(run_once(cfg, "real-url-check", dry_run=False))
    assert result.executed is True


# ── Error handling integration ───────────────────────────────────────────────

def test_invalid_bot_token_raises_error(tmp_path: Path):
    """Invalid bot token should result in a clear error."""
    bad_cfg = AppConfig(
        base_url=BASE_URL,
        bot_token="b_fake:0:badtoken",
        state_path=tmp_path / "state.json",
        timezone="Asia/Shanghai",
        tasks=[
            TaskConfig(
                id="should-fail",
                type="send_message",
                enabled=True,
                group_id=GROUP_ID,
                schedule="daily",
                time="09:00",
                message="should not send",
            ),
        ],
    )
    with pytest.raises(Exception):
        asyncio.run(run_once(bad_cfg, "should-fail", dry_run=False))
