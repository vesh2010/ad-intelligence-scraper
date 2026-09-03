from app.device_comparison import DESKTOP, MOBILE, compare_devices

def test_exported_symbols():
    assert DESKTOP.name == 'desktop'
    assert MOBILE.name == 'mobile'
    assert compare_devices([])['campaign_count'] == 0
