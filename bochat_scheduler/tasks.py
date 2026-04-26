from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Awaitable, Callable, Protocol

from .config import TaskConfig
from .state import SchedulerState
from .website import WebsiteSnapshot, fetch_website_snapshot


FetchWebsite = Callable[[str], Awaitable[WebsiteSnapshot]]


class Sender(Protocol):
    async def send_text(self, group_id: str, text: str): ...


@dataclass(frozen=True)
class TaskRunResult:
    task_id: str
    executed: bool
    sent: bool
    message: str


async def execute_task(
    task: TaskConfig,
    state: SchedulerState,
    sender: Sender,
    now: datetime,
    dry_run: bool = False,
    website_fetcher: FetchWebsite = fetch_website_snapshot,
) -> TaskRunResult:
    if task.type == "send_message":
        return await _execute_send_message(task, state, sender, now, dry_run)
    if task.type == "check_url":
        return await _execute_check_url(task, state, sender, now, dry_run, website_fetcher)
    raise ValueError(f"unsupported task type: {task.type}")


async def _execute_send_message(
    task: TaskConfig,
    state: SchedulerState,
    sender: Sender,
    now: datetime,
    dry_run: bool,
) -> TaskRunResult:
    assert task.message is not None
    await sender.send_text(task.group_id, task.message)
    if not dry_run:
        state.task(task.id).last_run_at = now.isoformat()
        state.save()
    return TaskRunResult(
        task_id=task.id,
        executed=True,
        sent=True,
        message="message sent",
    )


async def _execute_check_url(
    task: TaskConfig,
    state: SchedulerState,
    sender: Sender,
    now: datetime,
    dry_run: bool,
    website_fetcher: FetchWebsite,
) -> TaskRunResult:
    assert task.url is not None
    snapshot = await website_fetcher(task.url)
    task_state = state.task(task.id)
    title = task.title or snapshot.title

    if task_state.last_content_hash is None:
        if not dry_run:
            task_state.last_content_hash = snapshot.content_hash
            task_state.last_run_at = now.isoformat()
            state.save()
        return TaskRunResult(
            task_id=task.id,
            executed=True,
            sent=False,
            message="initial content hash recorded",
        )

    if task_state.last_content_hash == snapshot.content_hash:
        if not dry_run:
            task_state.last_run_at = now.isoformat()
            state.save()
        return TaskRunResult(
            task_id=task.id,
            executed=True,
            sent=False,
            message="no content change",
        )

    message = format_website_change_message(title, snapshot)
    await sender.send_text(task.group_id, message)
    if not dry_run:
        task_state.last_content_hash = snapshot.content_hash
        task_state.last_run_at = now.isoformat()
        state.save()
    return TaskRunResult(
        task_id=task.id,
        executed=True,
        sent=True,
        message="content change sent",
    )


def format_website_change_message(title: str, snapshot: WebsiteSnapshot) -> str:
    parts = [
        f"【网站更新】{title}",
        f"链接：{snapshot.url}",
        "",
        "检测到页面内容发生变化。",
        f"标题：{snapshot.title}",
    ]
    if snapshot.summary:
        parts.extend(["", f"摘要：{snapshot.summary}"])
    return "\n".join(parts)
