from app.device_compare import compare_devices


def test_compare_devices_matches_campaign_across_devices():
    result = compare_devices([
        {"campaign_key": "c1", "device": "desktop", "ad_unit_code": "top"},
        {"campaign_key": "c1", "device": "mobile", "ad_unit_code": "mrec"},
        {"campaign_key": "c2", "device": "desktop", "ad_unit_code": "top"},
        {"campaign_key": "c3", "device": "mobile", "ad_unit_code": "mrec"},
    ])
    assert result["campaign_count"] == 3
    assert result["both_device_campaigns"] == 1
    assert result["desktop_only_campaigns"] == 1
    assert result["mobile_only_campaigns"] == 1
    c1 = next(row for row in result["campaigns"] if row["campaign_key"] == "c1")
    assert c1["both_devices"] is True
    assert c1["desktop_placements"] == ["top"]
    assert c1["mobile_placements"] == ["mrec"]
    assert c1["shared_placements"] == []


def test_compare_devices_ignores_unknown_device_and_empty_input():
    result = compare_devices([
        {"campaign_key": "c1", "device": "tablet"},
        {"campaign_key": "c2", "device": "desktop", "ad_unit_code": "top"},
    ])
    assert result["campaign_count"] == 1
    assert result["campaigns"][0]["campaign_key"] == "c2"
    assert compare_devices([])["campaign_count"] == 0


def test_compare_devices_uses_ad_id_when_campaign_key_missing():
    result = compare_devices([
        {"ad_id": "ad1", "device": "desktop"},
        {"ad_id": "ad1", "device": "mobile"},
    ])
    assert result["both_device_campaigns"] == 1
