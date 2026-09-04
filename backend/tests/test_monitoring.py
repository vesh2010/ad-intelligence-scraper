from pathlib import Path

from app.monitoring import MonitorStore, build_alerts, create_monitor_target, dedupe_alerts


def test_create_monitor_target_validates_and_normalizes():
    target = create_monitor_target(url="https://Example.com/news", device="both", interval_minutes=120, trace=True)
    assert target["target"] == "https://Example.com/news"
    assert target["device"] == "both"
    assert target["interval_minutes"] == 120
    assert target["crawl_options"]["trace"] is True
    assert len(target["monitor_id"]) == 32


def test_create_monitor_target_rejects_invalid_schedule_and_scheme():
    try:
        create_monitor_target(url="ftp://example.com")
        assert False
    except ValueError as exc:
        assert "http or https" in str(exc)
    try:
        create_monitor_target(url="https://example.com", interval_minutes=30)
        assert False
    except ValueError as exc:
        assert "at least 60" in str(exc)


def test_monitor_store_round_trip(tmp_path: Path):
    store = MonitorStore(tmp_path)
    target = create_monitor_target(url="https://example.com")
    store.upsert(target)
    assert store.get(target["monitor_id"]) == target
    assert store.list_targets() == [target]
    assert store.delete(target["monitor_id"]) is True
    assert store.list_targets() == []


def test_build_alerts_omits_continued_and_classifies_changes():
    previous = [{"campaign_key": "c1", "device": "desktop", "ad_unit_code": "top"}]
    current = [{"campaign_key": "c1", "device": "mobile", "ad_unit_code": "top"}, {"campaign_key": "c2", "device": "mobile", "ad_unit_code": "mrec"}]
    alerts = build_alerts(monitor_id="m1", target="https://example.com", previous=previous, current=current, observed_at="2026-09-04T10:00:00Z")
    assert {x["change_type"] for x in alerts} == {"device_targeting_changed", "new_campaign"}
    assert all(x["observed_at"] == "2026-09-04T10:00:00Z" for x in alerts)
    assert all(x["severity"] == "high" for x in alerts)


def test_dedupe_alerts_suppresses_duplicate_details():
    candidate = {"monitor_id": "m1", "campaign_key": "c1", "change_type": "placement_changed", "details": {"added": ["mrec"]}}
    assert dedupe_alerts([], [candidate]) == [candidate]
    assert dedupe_alerts([candidate], [candidate]) == []
