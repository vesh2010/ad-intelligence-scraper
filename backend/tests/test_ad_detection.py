from app.ad_detection import classify_dom_candidates, classify_network_requests


def test_network_ad_tech_signal():
    result = classify_network_requests([
        {
            "url": "https://securepubads.g.doubleclick.net/gampad/ads",
            "method": "GET",
            "resource_type": "script",
            "status": 200,
        }
    ])
    assert len(result) == 1
    assert result[0]["ad_technology"] == "Google Ad Manager/DoubleClick"


def test_non_ad_network_request_is_ignored():
    result = classify_network_requests([
        {
            "url": "https://www.ndtvprofit.com/markets",
            "method": "GET",
            "resource_type": "document",
            "status": 200,
        }
    ])
    assert result == []


def test_generic_ad_substring_does_not_create_false_positive():
    result = classify_dom_candidates([
        {"id": "header", "class_name": "site-header", "aria_label": None, "text": "Latest markets"}
    ])
    assert result == []


def test_dom_ad_candidate_signal():
    result = classify_dom_candidates([
        {"id": "top-ad", "class_name": "leaderboard", "aria_label": None, "text": ""}
    ])
    assert len(result) == 1
    assert result[0]["signal_type"] == "dom"


def test_dom_adsbygoogle_signal():
    result = classify_dom_candidates([
        {"id": None, "class_name": "adsbygoogle", "aria_label": None, "text": ""}
    ])
    assert len(result) == 1


def test_dom_sponsored_marker_signal():
    result = classify_dom_candidates([
        {"id": "promo", "class_name": "article-card", "aria_label": "Sponsored", "text": "Brand message"}
    ])
    assert len(result) == 1
