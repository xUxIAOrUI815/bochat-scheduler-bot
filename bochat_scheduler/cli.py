from __future__ import annotations

import asyncio
from pathlib import Path

import typer

from .config import ConfigError, load_config
from .runner import check_due, find_task, run_forever, run_once
from .scheduler import due_tasks, now_for_config
from .state import SchedulerState

app = typer.Typer(help="BoChat config-driven scheduler bot")


@app.command("init-config")
def init_config(path: Path) -> None:
    """Generate an example config file."""
    if path.exists():
        raise typer.BadParameter(f"文件已存在: {path}")
    example = Path(__file__).resolve().parents[1] / "examples" / "config.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
    typer.echo(f"已生成配置文件: {path}")


@app.command("list")
def list_tasks(config: Path = typer.Option(..., "--config", "-c")) -> None:
    cfg = _load_or_exit(config)
    for task in cfg.tasks:
        status = "enabled" if task.enabled else "disabled"
        schedule = _schedule_label(task)
        typer.echo(
            f"{task.id}\t{status}\t{task.type}\t{schedule}\tgroup={task.group_id}"
        )


@app.command("due")
def due(config: Path = typer.Option(..., "--config", "-c")) -> None:
    cfg = _load_or_exit(config)
    state = SchedulerState.load(cfg.state_path)
    tasks = due_tasks(cfg, state, now_for_config(cfg))
    for task in tasks:
        typer.echo(task.id)


@app.command("run-once")
def run_once_command(
    task_id: str,
    config: Path = typer.Option(..., "--config", "-c"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    cfg = _load_or_exit(config)
    result = asyncio.run(run_once(cfg, task_id, dry_run=dry_run))
    typer.echo(f"{result.task_id}: sent={result.sent}, {result.message}")


@app.command("check")
def check(
    config: Path = typer.Option(..., "--config", "-c"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    cfg = _load_or_exit(config)
    results = asyncio.run(check_due(cfg, dry_run=dry_run))
    if not results:
        typer.echo("当前没有到期任务")
        return
    for result in results:
        typer.echo(f"{result.task_id}: sent={result.sent}, {result.message}")


@app.command("run")
def run(
    config: Path = typer.Option(..., "--config", "-c"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    cfg = _load_or_exit(config)
    asyncio.run(run_forever(cfg, dry_run=dry_run))


def _load_or_exit(path: Path):
    try:
        return load_config(path)
    except ConfigError as exc:
        typer.echo(f"配置错误: {exc}", err=True)
        raise typer.Exit(code=2) from exc


def _schedule_label(task) -> str:
    if task.schedule == "interval":
        return f"interval:{task.interval_secs}s"
    if task.schedule == "weekly":
        return f"weekly:{task.weekday}@{task.time}"
    return f"daily@{task.time}"
