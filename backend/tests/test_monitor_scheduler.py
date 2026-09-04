from datetime import datetime, timezone

import pytest

from app.monitor_scheduler import MonitorScheduler, is_due, parse_timestamp
from app.monitoring import MonitorStore, create_monitor_target


def test_parse_timestamp_handles_z_and_invalid():
    assert parse_timestamp("2026-09-04T10:00:00Z") == datetime(2026, 9, 4, 10, tzinfo=timezone.utc)
    assert parse_timestamp("bad") is None


def test_is_due_respects_interval_and_disabled():
    now = datetime(2026, 9, 4, 12, tzinfo=timezone.utc)
    target = create_monitor_target(url="https://example.com", interval_minutes=120)
    assert is_due(target, now=now)
    target["last_run_at"] = "2026-09-04T11:00:00Z"
    assert not is_due(target, now=now)
    target["last_run_at"] = "2026-09-04T10:00:00Z"
    assert is_due(target, now=now)
    target["enabled"] = False
    assert not is_due(target, now=now)


@pytest.mark.asyncio
async def test_scheduler_runs_due_target_and_records_status(tmp_path):
    store = MonitorStore(tmp_path)
    target = create_monitor_target(url="https://example.com", interval_minutes=60)
    store.upsert(target)
    now = datetime(2026, 9, 4, 12, tzinfo=timezone.utc)
    calls = []

    async def runner(value):
        calls.append(value["monitor_id"])
        return {"alerts": 2}

    scheduler = MonitorScheduler(store, runner, clock=lambda: now)
    results = await scheduler.run_due_once()
    assert results[0]["status"] == "success"
    assert calls == [target["monitor_id"]]
    saved = store.get(target["monitor_id"])
    assert saved["last_run_status"] == "success"
    assert saved["last_run_at"] == "2026-09-04T12:00:00Z"
    assert scheduler.due_targets() == []


@pytest.mark.asyncio
async def test_scheduler_records_errors_without_stopping_other_targets(tmp_path):
    store = MonitorStore(tmp_path)
    first = create_monitor_target(url="https://one.example")
    second = create_monitor_target(url="https://two.example")
    store.upsert(first)
    store.upsert(second)

    async def runner(value):
        if value["monitor_id"] == first["monitor_id"]:
            raise RuntimeError("crawl failed")
        return "ok"

    now = datetime(2026, 9, 4, 12, tzinfo=timezone.utc)
    results = await MonitorScheduler(store, runner, clock=lambda: now).run_due_once()
    assert [x["status"] for x in results] == ["error", "success"]
    assert store.get(first["monitor_id"])["last_error"] == "crawl failed"
    assert store.get(second["monitor_id"])["last_run_status"] == "success"
