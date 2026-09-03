from app.device_compare_integration import compare_devices


def test_public_device_comparison_entrypoint():
    result = compare_devices([{"campaign_key":"c1","device":"desktop"},{"campaign_key":"c1","device":"mobile"}])
    assert result["both_device_campaigns"] == 1
