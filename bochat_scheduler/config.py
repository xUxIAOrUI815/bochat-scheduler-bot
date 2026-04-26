from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import tomllib


class ConfigError(ValueError):
    pass


TaskType = Literal["send_message", "check_url"]
ScheduleType = Literal["daily", "weekly", "interval"]


@dataclass(frozen=True)
class TaskConfig:
    id: str
    type: TaskType
    enabled: bool
    group_id: str
    schedule: ScheduleType
    time: str | None = None
    weekday: str | None = None
    interval_secs: int | None = None
    message: str | None = None
    url: str | None = None
    title: str | None = None


@dataclass(frozen=True)
class AppConfig:
    base_url: str
    bot_token: str
    state_path: Path
    timezone: str
    tasks: list[TaskConfig]

    def enabled_tasks(self) -> list[TaskConfig]:
        return [task for task in self.tasks if task.enabled]


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    try:
        raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"配置文件不存在: {config_path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"配置文件 TOML 格式错误: {exc}") from exc

    return parse_config(raw, base_dir=config_path.parent)


def parse_config(raw: dict[str, Any], base_dir: Path | None = None) -> AppConfig:
    base_dir = base_dir or Path.cwd()
    base_url = _required_str(raw, "base_url")
    bot_token = _required_str(raw, "bot_token")
    state_path_raw = _str_value(raw.get("state_path", "./scheduler_state.json"), "state_path")
    timezone = _str_value(raw.get("timezone", "Asia/Shanghai"), "timezone")
    _validate_timezone(timezone)

    if not _has_http_scheme(base_url):
        raise ConfigError("base_url 必须是 http:// 或 https:// 地址")

    state_path = Path(state_path_raw)
    if not state_path.is_absolute():
        state_path = base_dir / state_path

    tasks_raw = raw.get("tasks")
    if not isinstance(tasks_raw, list) or not tasks_raw:
        raise ConfigError("至少需要配置一个 [[tasks]]")

    tasks: list[TaskConfig] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(tasks_raw):
        if not isinstance(item, dict):
            raise ConfigError(f"tasks[{index}] 必须是对象")
        task = _parse_task(item, index)
        if task.id in seen_ids:
            raise ConfigError(f"task id 重复: {task.id}")
        seen_ids.add(task.id)
        tasks.append(task)

    return AppConfig(
        base_url=base_url.rstrip("/"),
        bot_token=bot_token,
        state_path=state_path,
        timezone=timezone,
        tasks=tasks,
    )


def _parse_task(raw: dict[str, Any], index: int) -> TaskConfig:
    prefix = f"tasks[{index}]"
    task_id = _required_str(raw, "id", prefix)
    task_type = _required_str(raw, "type", prefix)
    if task_type not in {"send_message", "check_url"}:
        raise ConfigError(f"{prefix}.type 必须是 send_message 或 check_url")

    schedule = _required_str(raw, "schedule", prefix)
    if schedule not in {"daily", "weekly", "interval"}:
        raise ConfigError(f"{prefix}.schedule 必须是 daily、weekly 或 interval")

    enabled = bool(raw.get("enabled", True))
    group_id = _required_str(raw, "group_id", prefix)
    time_value = raw.get("time")
    time_text = _str_value(time_value, f"{prefix}.time") if time_value is not None else None
    weekday = raw.get("weekday")
    weekday_text = _str_value(weekday, f"{prefix}.weekday").lower() if weekday is not None else None
    interval_secs = raw.get("interval_secs")
    interval_value = (
        _positive_int(interval_secs, f"{prefix}.interval_secs")
        if interval_secs is not None
        else None
    )
    message = raw.get("message")
    message_text = _str_value(message, f"{prefix}.message") if message is not None else None
    url = raw.get("url")
    url_text = _str_value(url, f"{prefix}.url") if url is not None else None
    title = raw.get("title")
    title_text = _str_value(title, f"{prefix}.title") if title is not None else None

    _validate_schedule(prefix, schedule, time_text, weekday_text, interval_value)
    if task_type == "send_message" and message_text is None:
        raise ConfigError(f"{prefix}.message 是 send_message 任务的必填项")
    if task_type == "check_url":
        if url_text is None:
            raise ConfigError(f"{prefix}.url 是 check_url 任务的必填项")
        if not _has_http_scheme(url_text):
            raise ConfigError(f"{prefix}.url 必须是 http:// 或 https:// 地址")

    return TaskConfig(
        id=task_id,
        type=task_type,  # type: ignore[arg-type]
        enabled=enabled,
        group_id=group_id,
        schedule=schedule,  # type: ignore[arg-type]
        time=time_text,
        weekday=weekday_text,
        interval_secs=interval_value,
        message=message_text,
        url=url_text,
        title=title_text,
    )


def _validate_schedule(
    prefix: str,
    schedule: str,
    time_text: str | None,
    weekday: str | None,
    interval_secs: int | None,
) -> None:
    if schedule in {"daily", "weekly"}:
        if time_text is None:
            raise ConfigError(f"{prefix}.time 是 {schedule} 调度的必填项")
        _parse_hhmm(time_text, f"{prefix}.time")
    if schedule == "weekly":
        if weekday not in WEEKDAYS:
            raise ConfigError(f"{prefix}.weekday 必须是 {', '.join(WEEKDAYS)} 之一")
    if schedule == "interval" and interval_secs is None:
        raise ConfigError(f"{prefix}.interval_secs 是 interval 调度的必填项")


def parse_hhmm(value: str) -> tuple[int, int]:
    return _parse_hhmm(value, "time")


def _parse_hhmm(value: str, label: str) -> tuple[int, int]:
    parts = value.split(":")
    if len(parts) != 2:
        raise ConfigError(f"{label} 必须是 HH:MM 格式")
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError as exc:
        raise ConfigError(f"{label} 必须是 HH:MM 格式") from exc
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ConfigError(f"{label} 必须是有效的 HH:MM 时间")
    return hour, minute


WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def _required_str(raw: dict[str, Any], key: str, prefix: str | None = None) -> str:
    label = f"{prefix}.{key}" if prefix else key
    if key not in raw:
        raise ConfigError(f"缺少必填配置: {label}")
    return _str_value(raw[key], label)


def _str_value(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{label} 必须是非空字符串")
    return value.strip()


def _positive_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or value <= 0:
        raise ConfigError(f"{label} 必须是正整数")
    return value


def _has_http_scheme(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _validate_timezone(value: str) -> None:
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ConfigError(f"timezone 无效: {value}") from exc
