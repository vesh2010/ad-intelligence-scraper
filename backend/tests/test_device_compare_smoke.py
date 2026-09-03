from app.device_comparison import compare_devices

def test_empty_input():
    assert compare_devices([]) == {'campaigns': [], 'campaign_count': 0, 'both_device_campaigns': 0, 'desktop_only_campaigns': 0, 'mobile_only_campaigns': 0}
