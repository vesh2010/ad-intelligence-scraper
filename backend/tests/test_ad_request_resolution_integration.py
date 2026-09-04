from app.ad_models import AdDetectionResult
from app.ad_reconcile import reconcile_ad_records


def test_reconcile_attaches_explicit_network_request_resolution():
    runtime = [{
        "stage": "post_scroll",
        "data": {
            "gpt": {"slots": [{
                "element_id": "slot-2",
                "ad_unit_path": "/1234/news",
                "sizes": [{"width": 970, "height": 90}],
            }]},
            "prebid": {"bids": [], "winners": []},
        },
    }]
    network = [{
        "url": "https://securepubads.g.doubleclick.net/gampad/ads?iu=%2F1234%2Fnews&slot=slot-2&sz=970x90",
        "method": "GET",
        "resource_type": "document",
        "status": 200,
        "ad_technology": "Google Ad Manager/DoubleClick",
    }]

    records = reconcile_ad_records(AdDetectionResult(), runtime, [], network=network)

    assert len(records) == 1
    resolution = records[0].request_resolution
    assert resolution is not None
    assert resolution["match_method"] == "explicit_slot_id_or_ad_unit_path"
    assert resolution["match_score"] == 190
    assert resolution["matched_requests"][0]["ad_unit_path"] == "/1234/news"
    assert "network.ad_request" in records[0].evidence


def test_reconcile_without_network_preserves_unknown_resolution():
    runtime = [{
        "stage": "post_scroll",
        "data": {"gpt": {"slots": [{"element_id": "slot-unknown", "ad_unit_path": "/1234/unknown"}]}, "prebid": {}}
    }]

    records = reconcile_ad_records(AdDetectionResult(), runtime, [])

    assert len(records) == 1
    assert records[0].request_resolution is None
    assert "network.ad_request" not in records[0].evidence
