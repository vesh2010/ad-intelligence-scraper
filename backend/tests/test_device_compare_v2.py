from app.device_compare_v2 import compare_devices


def test_cross_device_campaigns():
    result = compare_devices([
        {"campaign_key":"c1","device":"desktop","ad_unit_code":"top"},
        {"campaign_key":"c1","device":"mobile","ad_unit_code":"mrec"},
        {"campaign_key":"c2","device":"desktop","ad_unit_code":"top"},
        {"campaign_key":"c3","device":"mobile","ad_unit_code":"mrec"},
        {"campaign_key":"c4","device":"tablet"},
    ])
    assert result["campaign_count"] == 3
    assert result["both_device_campaigns"] == 1
    assert result["desktop_only_campaigns"] == 1
    assert result["mobile_only_campaigns"] == 1


def test_fallback_to_ad_id():
    result = compare_devices([{"ad_id":"a1","device":"desktop"}, {"ad_id":"a1","device":"mobile"}])
    assert result["both_device_campaigns"] == 1
