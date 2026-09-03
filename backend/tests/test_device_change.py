from app.device_change import detect_changes


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
    assert result["change_count"] == 6


def test_ignores_missing_creative_evidence():
    result = detect_changes(
        [{"campaign_key": "c1", "device": "desktop"}],
        [{"campaign_key": "c1", "device": "desktop"}],
    )
    assert result["change_count"] == 0
