from app.ad_models import AdDetectionResult
from app.ad_reconcile import reconcile_ad_records


def test_runtime_numeric_advertiser_id_is_serialized_as_string():
    runtime = [{
        "data": {
            "gpt": {
                "slots": [{
                    "element_id": "slot-1",
                    "ad_unit_path": "/1234/news",
                    "sizes": [{"width": 300, "height": 250}],
                    "response_information": {"advertiser_id": 5464097881},
                }]
            },
            "prebid": {"bids": [], "winners": []},
        }
    }]

    records = reconcile_ad_records(AdDetectionResult(), runtime, [])

    assert len(records) == 1
    assert records[0].advertiser_id == "5464097881"


def test_runtime_numeric_prebid_identifiers_are_serialized_as_strings():
    winner = {
        "ad_unit_code": "slot-2",
        "bidder": "rubicon",
        "ad_id": 12345,
        "creative_id": 67890,
        "advertiser_id": 5464097881,
        "brand_id": 42,
        "network_id": 99,
        "deal_id": 777,
        "width": 300,
        "height": 250,
        "cpm": 2.0,
        "currency": "USD",
        "rendered": True,
    }
    runtime = [{"data": {"gpt": {"slots": []}, "prebid": {"bids": [], "winners": [winner]}}}]

    records = reconcile_ad_records(AdDetectionResult(), runtime, [])

    bid = records[0].winning_bid
    assert bid is not None
    assert bid.ad_id == "12345"
    assert bid.creative_id == "67890"
    assert bid.advertiser_id == "5464097881"
    assert bid.brand_id == "42"
    assert bid.network_id == "99"
    assert bid.deal_id == "777"
