from app.device_compare import compare_devices


def test_entrypoint():
    assert compare_devices([
        {"campaign_key": "x", "device": "desktop"},
        {"campaign_key": "x", "device": "mobile"},
    ])["both_device_campaigns"] == 1
