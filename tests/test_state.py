from pathlib import Path

from bochat_scheduler.state import SchedulerState


def test_state_read_write(tmp_path: Path):
    path = tmp_path / "state.json"
    state = SchedulerState.load(path)

    task = state.task("daily")
    task.last_run_at = "2026-04-26T09:00:00+08:00"
    task.last_content_hash = "abc"
    state.save()

    loaded = SchedulerState.load(path)
    assert loaded.task("daily").last_run_at == "2026-04-26T09:00:00+08:00"
    assert loaded.task("daily").last_content_hash == "abc"
