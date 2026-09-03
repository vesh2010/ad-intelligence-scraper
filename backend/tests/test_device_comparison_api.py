from app.device_comparison import compare_devices, DESKTOP, MOBILE

def test_public_api():
    assert DESKTOP.is_mobile is False
    assert MOBILE.is_mobile is True
    assert compare_devices([{'campaign_key':'x','device':'desktop'},{'campaign_key':'x','device':'mobile'}])['both_device_campaigns']==1
