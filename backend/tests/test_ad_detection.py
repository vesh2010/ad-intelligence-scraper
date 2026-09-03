from app.ad_detection import classify_dom_candidates, classify_network_requests


def test_network_ad_tech_signal():
    result = classify_network_requests([
        {"url": "https://securepubads.g.doubleclick.net/gampad/ads", "method": "GET", "resource_type": "script", "status": 200}
    ])
    assert len(result) == 1
    assert result[0]["ad_technology"] == "Google Ad Manager/DoubleClick"


def test_non_ad_network_request_is_ignored():
    result = classify_network_requests([
        {"url": "https://www.ndtvprofit.com/markets", "method": "GET", "resource_type": "document", "status": 200}
    ])
    assert result == []


def test_dom_candidate_signal():
    result = classify_dom_candidates([
        {"id": "top-ad", "class_name": "leaderboard", "aria_label": None, "text": ""}
    ])
    assert len(result) == 1
    assert result[0]["signal_type"] == "dom"
