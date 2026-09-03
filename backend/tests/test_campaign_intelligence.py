from app.campaign_intelligence import build_campaign_intelligence


def test_groups_observations_into_one_campaign_and_tracks_placements() -> None:
    observations = [
        {
            "campaign_key": "campaign_a",
            "brand_name": "Acme",
            "advertiser_name": "Acme Inc",
            "observed_at": "2026-09-01T10:00:00Z",
            "ad_unit_code": "top_300x250",
            "ad_format": "300x250",
            "network_name": "network-a",
            "above_fold": True,
        },
        {
            "campaign_key": "campaign_a",
            "brand_name": "Acme",
            "advertiser_name": "Acme Inc",
            "observed_at": "2026-09-03T10:00:00Z",
            "ad_unit_code": "rail_300x600",
            "ad_format": "300x600",
            "network_name": "network-b",
            "above_fold": False,
        },
        {
            "campaign_key": "campaign_b",
            "brand_name": "Beta",
            "observed_at": "2026-09-02T10:00:00Z",
            "ad_unit_code": "top_728x90",
            "ad_format": "728x90",
            "above_fold": True,
        },
    ]

    result = build_campaign_intelligence(observations)
    acme = next(row for row in result["campaigns"] if row["campaign_key"] == "campaign_a")

    assert result["campaign_count"] == 2
    assert result["total_observations"] == 3
    assert acme["observations"] == 2
    assert acme["placement_count"] == 2
    assert acme["first_seen"] == "2026-09-01T10:00:00Z"
    assert acme["last_seen"] == "2026-09-03T10:00:00Z"
    assert acme["above_fold_observations"] == 1
    assert set(acme["formats"]) == {"300x250", "300x600"}


def test_competitor_frequency_is_ranked_by_observations() -> None:
    observations = [
        {"campaign_key": "a", "brand_name": "Acme"},
        {"campaign_key": "a", "brand_name": "Acme"},
        {"campaign_key": "b", "brand_name": "Beta"},
    ]

    result = build_campaign_intelligence(observations)
    assert result["competitors"] == [
        {"brand_name": "Acme", "observations": 2},
        {"brand_name": "Beta", "observations": 1},
    ]


def test_empty_and_unidentified_observations_are_safe() -> None:
    result = build_campaign_intelligence([{}, {"ad_id": "ad-1"}])
    assert result["campaign_count"] == 1
    assert result["total_observations"] == 2
