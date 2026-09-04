from app.device_change import detect_changes, detect_history_changes


def test_detects_new_disappeared_and_field_changes():
    previous = [
        {"campaign_key": "c1", "device": "desktop", "ad_unit_code": "top", "creative_image_urls": ["https://x/a.png"]},
        {"campaign_key": "c2", "device": "mobile", "ad_unit_code": "mrec"},
    ]
    current = [
        {"campaign_key": "c1", "device": "mobile", "ad_unit_code": "mrec", "creative_image_urls": ["https://x/b.png"]},
        {"campaign_key": "c3", "device": "desktop", "ad_unit_code": "top"},
    ]
    result = detect_changes(previous, current)
    changes = {(item["campaign_key"], item["change"]) for item in result["changes"]}
    assert ("c1", "creative_changed") in changes
    assert ("c1", "placement_changed") in changes
    assert ("c1", "device_targeting_changed") in changes
    assert ("c2", "campaign_disappeared") in changes
    assert ("c3", "new_campaign") in changes
    assert result["change_count"] == 5


def test_detects_network_cpm_and_continuation():
    result = detect_changes(
        [{"campaign_key": "c1", "network_name": "net-a", "cpm": 1.2}],
        [{"campaign_key": "c1", "network_name": "net-b", "cpm": 2.4}],
    )
    changes = {item["change"] for item in result["changes"]}
    assert "network_changed" in changes
    assert "cpm_changed" in changes

    unchanged = detect_changes(
        [{"campaign_key": "c1", "network_name": "net-a", "cpm": 1.2}],
        [{"campaign_key": "c1", "network_name": "net-a", "cpm": 1.2}],
    )
    assert unchanged["continued_campaigns"] == 1


def test_cpm_string_and_numeric_values_are_equivalent():
    result = detect_changes(
        [{"campaign_key": "c1", "cpm": "1.20"}],
        [{"campaign_key": "c1", "cpm": 1.2}],
    )
    assert result["continued_campaigns"] == 1
    assert result["cpm_changes"] == 0


def test_detects_creative_added_and_removed():
    added = detect_changes(
        [{"campaign_key": "c1"}],
        [{"campaign_key": "c1", "creative_fingerprint": "new"}],
    )
    assert added["creative_added"] == 1
    assert added["creative_changes"] == 1

    removed = detect_changes(
        [{"campaign_key": "c1", "creative_fingerprint": "old"}],
        [{"campaign_key": "c1"}],
    )
    assert removed["creative_removed"] == 1
    assert removed["creative_changes"] == 1


def test_detects_adjacent_persisted_snapshots():
    result = detect_history_changes([
        {"observed_at": "2026-09-03T10:00:00Z", "campaign_key": "c1", "ad_unit_code": "top"},
        {"observed_at": "2026-09-03T11:00:00Z", "campaign_key": "c1", "ad_unit_code": "mrec"},
        {"observed_at": "2026-09-03T11:00:00Z", "campaign_key": "c2"},
    ])
    assert result["snapshot_count"] == 2
    assert result["observed_at"] == ["2026-09-03T10:00:00Z", "2026-09-03T11:00:00Z"]
    assert result["placement_changes"] == 1
    assert result["new_campaigns"] == 1


def test_ignores_missing_creative_evidence():
    result = detect_changes(
        [{"campaign_key": "c1", "device": "desktop"}],
        [{"campaign_key": "c1", "device": "desktop"}],
    )
    assert result["change_count"] == 1
    assert result["continued_campaigns"] == 1
