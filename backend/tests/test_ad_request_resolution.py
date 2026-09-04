from app.ad_request_resolution import match_ad_requests, resolve_ad_requests


def test_resolve_gam_request_extracts_explicit_slot_identifiers():
    network = [{
        "url": "https://securepubads.g.doubleclick.net/gampad/ads?iu=%2F1234%2Fnews%2Fhome&sz=970x90&ad_unit_code=top",
        "method": "GET",
        "resource_type": "document",
        "status": 200,
        "ad_technology": "Google Ad Manager/DoubleClick",
    }]
    result = resolve_ad_requests(network)
    assert len(result) == 1
    assert result[0]["ad_unit_path"] == "/1234/news/home"
    assert result[0]["size"] == "970x90"
    assert result[0]["request_kind"] == "ad_request"


def test_resolver_does_not_invent_advertiser_identity():
    result = resolve_ad_requests([{
        "url": "https://securepubads.g.doubleclick.net/gampad/ads?iu=%2F1234%2Fnews",
        "status": 200,
    }])
    assert "advertiser_name" not in result[0]
    assert "advertiser_id" not in result[0]


def test_match_prefers_explicit_element_and_ad_unit_matches():
    requests = resolve_ad_requests([
        {"url": "https://securepubads.g.doubleclick.net/gampad/ads?iu=%2F1234%2Fnews&slot=slot-1", "status": 200},
        {"url": "https://securepubads.g.doubleclick.net/gampad/ads?iu=%2Fother", "status": 200},
    ])
    matches = match_ad_requests({"element_id": "slot-1", "ad_unit_path": "/1234/news"}, requests)
    assert len(matches) == 1
    assert matches[0]["match_score"] == 190
