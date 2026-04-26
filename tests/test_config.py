from pathlib import Path

import pytest

from bochat_scheduler.config import ConfigError, parse_config


def base_config():
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


def test_parse_config_defaults(tmp_path: Path):
    cfg = parse_config(base_config(), base_dir=tmp_path)

    assert cfg.base_url == "http://127.0.0.1:8080"
    assert cfg.state_path == tmp_path / "scheduler_state.json"
    assert cfg.timezone == "Asia/Shanghai"
    assert cfg.tasks[0].id == "daily"


def test_duplicate_task_id_rejected(tmp_path: Path):
    raw = base_config()
    raw["tasks"].append(dict(raw["tasks"][0]))

    with pytest.raises(ConfigError, match="task id 重复"):
        parse_config(raw, base_dir=tmp_path)


def test_interval_requires_interval_secs(tmp_path: Path):
    raw = base_config()
    raw["tasks"][0] = {
        "id": "interval",
        "type": "send_message",
        "group_id": "g_1",
        "schedule": "interval",
        "message": "hello",
    }

    with pytest.raises(ConfigError, match="interval_secs"):
        parse_config(raw, base_dir=tmp_path)


def test_check_url_requires_url(tmp_path: Path):
    raw = base_config()
    raw["tasks"][0] = {
        "id": "site",
        "type": "check_url",
        "group_id": "g_1",
        "schedule": "daily",
        "time": "09:00",
    }

    with pytest.raises(ConfigError, match="url"):
        parse_config(raw, base_dir=tmp_path)
