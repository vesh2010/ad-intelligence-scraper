from app.ad_detection import classify_dom_candidates
from app.ad_models import AdDetectionResult, AdSignal
from app.ad_reconcile import reconcile_ad_records


def test_reconcile_prebid_bid_with_gpt_and_dom_evidence():
    dom = classify_dom_candidates([
        {
            "tag": "div",
            "id": "slot-1",
            "class_name": "ad-slot",
            "aria_label": None,
            "role": None,
            "title": None,
            "text": "Sponsored",
            "width": 300,
            "height": 250,
            "x": 10,
            "y": 100,
            "selector": "#slot-1",
            "iframe_src": None,
        }
    ])
    detection = AdDetectionResult(signals=[AdSignal.model_validate(dom[0])], dom_signal_count=1)
    runtime = [{
        "stage": "post_scroll",
        "data": {
            "gpt": {"slots": [{
                "element_id": "slot-1",
                "ad_unit_path": "/1234/news",
                "sizes": [{"width": 300, "height": 250}],
                "response_information": {"advertiser_id": "42"},
            }]},
            "prebid": {"bids": [{
                "ad_unit_code": "slot-1",
                "bidder": "rubicon",
                "ad_id": "bid-1",
                "creative_id": "creative-1",
                "width": 300,
                "height": 250,
                "cpm": 4.2,
                "currency": "USD",
                "advertiser_name": "Example Advertiser",
                "advertiser_id": "adv-1",
                "brand_name": "Example",
                "network_name": "Example SSP",
                "deal_id": None,
            }]},
        },
    }]
    visual = [{"id": "slot-1", "screenshot": "data/runs/x/ad_candidates/candidate.png"}]

    records = reconcile_ad_records(detection, runtime, visual)

    assert len(records) == 2
    prebid = next(record for record in records if record.ad_type == "prebid_bid")
    assert prebid.advertiser_name == "Example Advertiser"
    assert prebid.brand_name == "Example"
    assert prebid.bidder == "rubicon"
    assert "runtime.gpt" in prebid.evidence
    assert "dom" in prebid.evidence
    assert "visual" in prebid.evidence
