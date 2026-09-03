from app.device_compare_v3 import compare_devices

def test_device_comparison():
    result=compare_devices([{'campaign_key':'c1','device':'desktop','ad_unit_code':'top'},{'campaign_key':'c1','device':'mobile','ad_unit_code':'mrec'},{'campaign_key':'c2','device':'desktop'}])
    assert result['campaign_count']==2
    assert result['both_device_campaigns']==1
    assert result['desktop_only_campaigns']==1

def test_device_fallback():
    assert compare_devices([{'ad_id':'a','device':'desktop'},{'ad_id':'a','device':'mobile'}])['both_device_campaigns']==1
