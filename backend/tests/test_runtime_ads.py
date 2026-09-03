from app.runtime_ads import RUNTIME_ADS_SCRIPT


def test_runtime_script_contains_supported_public_apis():
    assert "getSlots" in RUNTIME_ADS_SCRIPT
    assert "getResponseInformation" in RUNTIME_ADS_SCRIPT
    assert "getBidResponses" in RUNTIME_ADS_SCRIPT
    assert "getAllWinningBids" in RUNTIME_ADS_SCRIPT


def test_runtime_script_does_not_request_credentials():
    lowered = RUNTIME_ADS_SCRIPT.lower()
    assert "document.cookie" not in lowered
    assert "authorization" not in lowered
