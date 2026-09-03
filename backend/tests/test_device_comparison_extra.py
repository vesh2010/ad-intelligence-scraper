from app.device_comparison import compare_devices

def test_shared_placement():
    r=compare_devices([{'campaign_key':'x','device':'desktop','ad_unit_code':'top'},{'campaign_key':'x','device':'mobile','ad_unit_code':'top'}])
    assert r['campaigns'][0]['shared_placements']==['top']
