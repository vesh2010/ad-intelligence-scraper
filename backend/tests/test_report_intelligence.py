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
    assert result["campaigns"]["competitors"] == [{"brand_name": "Brand A", "observations": 2}]
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
