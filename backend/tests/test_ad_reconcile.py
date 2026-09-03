from app.ad_detection import classify_dom_candidates
from app.ad_models import AdDetectionResult, AdSignal
from app.ad_reconcile import reconcile_ad_records


def test_reconcile_prebid_bid_with_gpt_and_dom_evidence():
    dom = classify_dom_candidates([{
        "tag": "div", "id": "slot-1", "class_name": "ad-slot", "aria_label": None,
        "role": None, "title": None, "text": "Sponsored", "width": 300, "height": 250,
        "x": 10, "y": 100, "viewport_x": 10, "viewport_y": 100, "selector": "#slot-1",
        "iframe_src": None, "hrefs": ["https://example.com/product"],
        "image_urls": ["https://example.com/ad.png"], "video_urls": [],
        "position_mode": "static", "z_index": "auto", "dataset": {},
    }])
    detection = AdDetectionResult(signals=[AdSignal.model_validate(dom[0])], dom_signal_count=1)
    bid = {
        "ad_unit_code": "slot-1", "bidder": "rubicon", "ad_id": "bid-1", "creative_id": "creative-1",
        "width": 300, "height": 250, "cpm": 4.2, "currency": "USD",
        "advertiser_name": "Example Advertiser", "advertiser_id": "adv-1", "brand_name": "Example",
        "network_name": "Example SSP", "deal_id": None, "adserver_targeting": {"hb_bidder": "rubicon"},
    }
    runtime = [{"stage": "post_scroll", "data": {
        "gpt": {"slots": [{"element_id": "slot-1", "ad_unit_path": "/1234/news",
            "sizes": [{"width": 300, "height": 250}], "targeting": {"pos": ["top"]},
            "response_information": {"advertiser_id": "42"}}]},
        "prebid": {"bids": [bid], "winners": [bid]},
    }}]
    visual = [{"id": "slot-1", "screenshot": "data/runs/x/ad_candidates/candidate.png"}]

    records = reconcile_ad_records(detection, runtime, visual)

    assert len(records) == 1
    record = records[0]
    assert record.ad_type == "display"
    assert record.ad_format == "medium_rectangle"
    assert record.advertiser_name == "Example Advertiser"
    assert record.brand_name == "Example"
    assert record.bidder == "rubicon"
    assert len(record.bids) == 1
    assert record.winning_bid is not None
    assert record.winning_bid.bidder == "rubicon"
    assert record.adserver_targeting == {"pos": ["top"]}
    assert record.destination_urls == ["https://example.com/product"]
    assert record.creative_image_urls == ["https://example.com/ad.png"]
    assert "runtime.gpt" in record.evidence
    assert "runtime.prebid" in record.evidence
    assert "dom" in record.evidence
    assert "visual" in record.evidence


def test_dom_only_candidate_is_preserved():
    signal = AdSignal(signal_type="dom", confidence="medium", id="dom-only", selector="#dom-only",
                       width=320, height=50, hrefs=["https://example.com/offer"],
                       image_urls=["https://example.com/banner.png"])
    detection = AdDetectionResult(signals=[signal], dom_signal_count=1)
    records = reconcile_ad_records(detection, [], [])
    assert len(records) == 1
    assert records[0].ad_type == "display"
    assert records[0].ad_format == "mobile_banner"
    assert records[0].destination_urls == ["https://example.com/offer"]
