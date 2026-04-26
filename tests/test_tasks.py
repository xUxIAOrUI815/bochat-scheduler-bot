from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import asyncio

import pytest

from bochat_scheduler.config import TaskConfig
from bochat_scheduler.state import SchedulerState
from bochat_scheduler.tasks import execute_task
from bochat_scheduler.website import WebsiteSnapshot, parse_website_content


TZ = ZoneInfo("Asia/Shanghai")
NOW = datetime(2026, 4, 26, 10, 0, tzinfo=TZ)


class FakeSender:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.messages: list[tuple[str, str]] = []

    async def send_text(self, group_id: str, text: str):
        if self.fail:
            raise RuntimeError("send failed")
        self.messages.append((group_id, text))


async def fake_snapshot_v1(url: str) -> WebsiteSnapshot:
    return WebsiteSnapshot(url=url, title="Site", summary="hello", content_hash="hash-v1")


async def fake_snapshot_v2(url: str) -> WebsiteSnapshot:
    return WebsiteSnapshot(url=url, title="Site", summary="changed", content_hash="hash-v2")


def scheduler_state(tmp_path: Path) -> SchedulerState:
    return SchedulerState.load(tmp_path / "state.json")


def test_send_message_updates_state_after_success(tmp_path: Path):
    task = TaskConfig(
        id="daily",
        type="send_message",
        enabled=True,
        group_id="g_1",
        schedule="daily",
        time="09:00",
        message="hello",
    )
    state = scheduler_state(tmp_path)
    sender = FakeSender()

    result = asyncio.run(execute_task(task, state, sender, NOW))

    assert result.sent is True
    assert sender.messages == [("g_1", "hello")]
    assert SchedulerState.load(state.path).task("daily").last_run_at == NOW.isoformat()


def test_dry_run_does_not_update_state(tmp_path: Path):
    task = TaskConfig(
        id="daily",
        type="send_message",
        enabled=True,
        group_id="g_1",
        schedule="daily",
        time="09:00",
        message="hello",
    )
    state = scheduler_state(tmp_path)
    sender = FakeSender()

    result = asyncio.run(execute_task(task, state, sender, NOW, dry_run=True))

    assert result.sent is True
    assert sender.messages == [("g_1", "hello")]
    assert SchedulerState.load(state.path).task("daily").last_run_at is None


def test_send_failure_does_not_update_state(tmp_path: Path):
    task = TaskConfig(
        id="daily",
        type="send_message",
        enabled=True,
        group_id="g_1",
        schedule="daily",
        time="09:00",
        message="hello",
    )
    state = scheduler_state(tmp_path)

    with pytest.raises(RuntimeError, match="send failed"):
        asyncio.run(execute_task(task, state, FakeSender(fail=True), NOW))

    assert SchedulerState.load(state.path).task("daily").last_run_at is None


def test_check_url_first_run_records_hash_without_sending(tmp_path: Path):
    task = TaskConfig(
        id="site",
        type="check_url",
        enabled=True,
        group_id="g_1",
        schedule="daily",
        time="09:00",
        url="https://example.com",
        title="Example",
    )
    state = scheduler_state(tmp_path)
    sender = FakeSender()

    result = asyncio.run(
        execute_task(task, state, sender, NOW, website_fetcher=fake_snapshot_v1)
    )

    assert result.sent is False
    assert sender.messages == []
    loaded = SchedulerState.load(state.path)
    assert loaded.task("site").last_content_hash == "hash-v1"
    assert loaded.task("site").last_run_at == NOW.isoformat()


def test_check_url_sends_when_content_changes(tmp_path: Path):
    task = TaskConfig(
        id="site",
        type="check_url",
        enabled=True,
        group_id="g_1",
        schedule="daily",
        time="09:00",
        url="https://example.com",
        title="Example",
    )
    state = scheduler_state(tmp_path)
    state.task("site").last_content_hash = "hash-v1"
    state.save()
    sender = FakeSender()

    result = asyncio.run(
        execute_task(task, state, sender, NOW, website_fetcher=fake_snapshot_v2)
    )

    assert result.sent is True
    assert len(sender.messages) == 1
    assert "【网站更新】Example" in sender.messages[0][1]
    assert SchedulerState.load(state.path).task("site").last_content_hash == "hash-v2"


def test_parse_website_content_extracts_title_summary_and_hash():
    snapshot = parse_website_content(
        "https://example.com",
        "<html><head><title>Hello</title><script>x</script></head><body>World</body></html>",
    )

    assert snapshot.title == "Hello"
    assert snapshot.summary == "Hello World"
    assert len(snapshot.content_hash) == 64
