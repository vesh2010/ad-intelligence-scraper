from app.intelligence_report import build_intelligence_report


def test_report_aggregates_competitors_campaigns_and_devices() -> None:
    observations = [
        {
            "campaign_key": "c1",
            "ad_id": "a1",
            "brand_name": "Acme",
            "advertiser_name": "Acme Inc",
            "observed_at": "2026-09-03T10:00:00Z",
            "ad_unit_code": "top",
            "ad_format": "banner",
            "network_name": "gpt",
            "device": "desktop",
        },
        {
            "campaign_key": "c1",
            "ad_id": "a1",
            "brand_name": "Acme",
            "advertiser_name": "Acme Inc",
            "observed_at": "2026-09-03T11:00:00Z",
            "ad_unit_code": "mrec",
            "ad_format": "banner",
            "network_name": "gpt",
            "device": "mobile",
        },
    ]

    report = build_intelligence_report(observations, {"both_device_campaigns": 1})

    assert report["schema_version"] == "1.0"
    assert report["campaign_count"] == 1
    assert report["competitors"] == [{"name": "Acme", "observations": 2}]
    assert report["campaigns"][0]["placements"] == ["mrec", "top"]
    assert report["campaigns"][0]["devices"] == ["desktop", "mobile"]
    assert report["device_comparison"]["both_device_campaigns"] == 1
