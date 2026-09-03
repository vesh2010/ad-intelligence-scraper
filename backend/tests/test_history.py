from __future__ import annotations

from pathlib import Path

from app.ad_records import AdRecord
from app.history import append_snapshot, campaign_key


def _record(**kwargs) -> AdRecord:
    base = {
        "ad_id": "ad_123",
        "ad_type": "display",
        "ad_format": "300x250",
        "brand_name": "Example Brand",
        "destination_urls": ["https://example.com/product/"],
        "evidence": [],
    }
    base.update(kwargs)
    return AdRecord(**base)


def test_campaign_key_is_stable_for_same_observable_identity() -> None:
    left = _record(destination_urls=["https://example.com/product/"])
    right = _record(destination_urls=["https://example.com/product"])
    assert campaign_key(left) == campaign_key(right)


def test_campaign_key_changes_when_brand_or_destination_changes() -> None:
    first = _record()
    second = _record(brand_name="Other Brand")
    third = _record(destination_urls=["https://other.example/product"])
    assert campaign_key(first) != campaign_key(second)
    assert campaign_key(first) != campaign_key(third)


def test_append_snapshot_is_recoverable_and_counts(tmp_path: Path) -> None:
    history = tmp_path / "history.json"
    first = append_snapshot(history, [_record()], "2026-09-03T12:00:00Z")
    second = append_snapshot(history, [_record(ad_id="ad_456")], "2026-09-03T13:00:00Z")
    assert first == {"observations": 1, "history_size": 1}
    assert second == {"observations": 1, "history_size": 2}
