import json
from pathlib import Path

from app.history_store import HistoryStore
from app.monitoring import MonitorStore, create_monitor_target


def test_history_uses_sqlite_and_preserves_rows(tmp_path: Path):
    store = HistoryStore(tmp_path / "history")
    target = "https://example.com/news"
    rows = [{"observed_at": "2026-09-04T10:00:00Z", "campaign_key": "c1", "monitor_id": "m1"}]
    assert store.append(target, rows)["history_size"] == 1
    assert store.load(target) == rows
    assert (tmp_path / "history" / "history.sqlite3").is_file()


def test_history_imports_legacy_json_once(tmp_path: Path):
    root = tmp_path / "history"
    root.mkdir()
    legacy = [{"observed_at": "2026-09-04T10:00:00Z", "campaign_key": "legacy"}]
    (root / "abc123.json").write_text(json.dumps(legacy), encoding="utf-8")
    store = HistoryStore(root)
    with store.db.transaction() as db:
        assert db.execute("SELECT COUNT(*) FROM observations WHERE target_key=?", ("abc123",)).fetchone()[0] == 1
    store._migrate_legacy_json()
    with store.db.transaction() as db:
        assert db.execute("SELECT COUNT(*) FROM observations WHERE target_key=?", ("abc123",)).fetchone()[0] == 1


def test_monitor_sqlite_round_trip_and_alerts(tmp_path: Path):
    store = MonitorStore(tmp_path / "monitoring")
    target = create_monitor_target(url="https://example.com")
    store.upsert(target)
    alert = {"alert_id": "a1", "monitor_id": target["monitor_id"], "target": target["target"], "observed_at": "2026-09-04T10:00:00Z",
             "severity": "high", "change_type": "new_campaign", "campaign_key": "c1", "details": {"change": "new_campaign"}}
    store.append_alerts([alert])
    assert store.get(target["monitor_id"]) == target
    assert store.alerts(target["monitor_id"]) == [alert]
    assert (tmp_path / "monitoring" / "monitoring.sqlite3").is_file()
    assert store.delete(target["monitor_id"]) is True
    assert store.alerts(target["monitor_id"]) == []
