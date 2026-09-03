from app.device_compare_final import compare_devices

def test_final_entrypoint():
    r=compare_devices([{'campaign_key':'x','device':'desktop'},{'campaign_key':'x','device':'mobile'}])
    assert r['both_device_campaigns']==1
