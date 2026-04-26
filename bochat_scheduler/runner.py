from __future__ import annotations

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from .config import AppConfig, TaskConfig
from .scheduler import due_tasks, now_for_config
from .sender import BoChatSender, DryRunSender
from .state import SchedulerState
from .tasks import TaskRunResult, execute_task


def find_task(config: AppConfig, task_id: str) -> TaskConfig:
    for task in config.tasks:
        if task.id == task_id:
            return task
    raise ValueError(f"未找到任务: {task_id}")


async def run_once(
    config: AppConfig,
    task_id: str,
    dry_run: bool = False,
) -> TaskRunResult:
    state = SchedulerState.load(config.state_path)
    task = find_task(config, task_id)
    sender = DryRunSender() if dry_run else BoChatSender(config)
    try:
        return await execute_task(
            task=task,
            state=state,
            sender=sender,
            now=now_for_config(config),
            dry_run=dry_run,
        )
    finally:
        await sender.close()


async def check_due(config: AppConfig, dry_run: bool = False) -> list[TaskRunResult]:
    state = SchedulerState.load(config.state_path)
    current = now_for_config(config)
    tasks = due_tasks(config, state, current)
    sender = DryRunSender() if dry_run else BoChatSender(config)
    results: list[TaskRunResult] = []
    try:
        for task in tasks:
            results.append(
                await execute_task(
                    task=task,
                    state=state,
                    sender=sender,
                    now=current,
                    dry_run=dry_run,
                )
            )
        return results
    finally:
        await sender.close()


async def run_forever(config: AppConfig, dry_run: bool = False) -> None:
    sender = DryRunSender() if dry_run else BoChatSender(config)
    state = SchedulerState.load(config.state_path)
    try:
        while True:
            current = now_for_config(config)
            for task in due_tasks(config, state, current):
                try:
                    result = await execute_task(
                        task=task,
                        state=state,
                        sender=sender,
                        now=current,
                        dry_run=dry_run,
                    )
                    print(
                        f"[{task.id}] executed={result.executed} "
                        f"sent={result.sent} message={result.message}"
                    )
                except Exception as exc:
                    print(f"[{task.id}] failed: {exc}")
            await asyncio.sleep(5)
    except KeyboardInterrupt:
        print("收到退出信号，停止 BoChat 定时任务 Bot")
    finally:
        await sender.close()
