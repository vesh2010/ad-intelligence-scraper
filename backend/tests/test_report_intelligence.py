from app.report_intelligence import build_report_intelligence


def test_report_intelligence_combines_campaign_device_and_history_views():
    observations = [
        {
            "observed_at": "2026-09-03T10:00:00Z",
            "campaign_key": "c1",
            "brand_name": "Brand A",
            "device": "desktop",
            "ad_unit_code": "top",
            "creative_fingerprint": "old",
        },
        {
            "observed_at": "2026-09-03T11:00:00Z",
            "campaign_key": "c1",
            "brand_name": "Brand A",
            "device": "mobile",
            "ad_unit_code": "mrec",
            "creative_fingerprint": "new",
        },
    ]

    result = build_report_intelligence(observations)

    assert result["observation_count"] == 2
    assert result["campaigns"]["campaign_count"] == 1
    assert result["campaigns"]["competitors"] == [
        {"brand_name": "Brand A", "observations": 2, "observation_share_pct": 100.0}
    ]
    assert result["devices"]["both_device_campaigns"] == 1
    assert result["history"]["creative_changes"] == 1
    assert result["history"]["placement_changes"] == 1
    assert result["history"]["device_targeting_changes"] == 1


def test_report_intelligence_rejects_non_object_rows():
    try:
        build_report_intelligence([{"campaign_key": "c1"}, "invalid"])
    except ValueError as exc:
        assert str(exc) == "observations must be a list of objects"
    else:
        raise AssertionError("expected ValueError")


def test_report_includes_best_advertiser_confidence_per_campaign():
    result = build_report_intelligence([
        {"campaign_key": "campaign-1", "brand_name": "Acme", "evidence": ["ocr: ACME"]},
        {
            "campaign_key": "campaign-1",
            "advertiser_name": "Acme Corp",
            "brand_name": "Acme",
            "landing_page_url": "https://acme.example/",
            "network": "Google Ad Manager",
        },
    ])
    assert result["advertiser_confidence"] == [{
        "campaign_key": "campaign-1",
        "level": "verified",
        "score": 90,
        "signals": ["advertiser_metadata", "brand_metadata", "landing_destination", "ad_tech_signal"],
        "observation_count": 2,
    }]


def test_report_resolves_explicit_ad_requests_to_gpt_slots():
    result = build_report_intelligence([{
        "campaign_key": "campaign-2",
        "network": [{
            "url": "https://securepubads.g.doubleclick.net/gampad/ads?iu=%2F1234%2Fnews&slot=slot-2&sz=970x90",
            "status": 200,
            "ad_technology": "Google Ad Manager/DoubleClick",
        }],
        "runtime_ads": {"snapshots": [{"data": {"gpt": {"slots": [{
            "element_id": "slot-2", "ad_unit_path": "/1234/news"
        }]}}}]},
    }])
    resolution = result["ad_request_resolution"]
    assert resolution["request_count"] == 1
    assert resolution["resolved_slot_count"] == 1
    assert resolution["resolved_slots"][0]["matches"][0]["match_score"] == 190
