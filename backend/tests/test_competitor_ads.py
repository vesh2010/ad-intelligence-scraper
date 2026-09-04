from app.campaign_intelligence import build_campaign_intelligence
from app.report_html import render_html_report


def test_external_destination_is_reported_as_competitor_candidate() -> None:
    observations = [
        {
            "campaign_key": "ad-1",
            "brand_name": "Acme",
            "advertiser_name": "Acme Inc",
            "publisher_domain": "example.com",
            "destination_urls": ["https://acme.example/offer"],
            "target_url": "https://example.com/news",
        },
        {
            "campaign_key": "ad-2",
            "publisher_domain": "example.com",
            "destination_urls": ["https://competitor.test/product"],
            "target_url": "https://example.com/news",
        },
    ]
    result = build_campaign_intelligence(observations)
    labels = {row["competitor"] for row in result["competitor_ads"]}
    assert "Acme Inc" in labels
    assert "competitor.test" in labels
    assert result["competitor_count"] == 2


def test_competitor_analysis_is_present_in_html_report() -> None:
    html = render_html_report([
        {
            "campaign_key": "ad-1",
            "advertiser_name": "Competitor Co",
            "publisher_domain": "example.com",
            "destination_urls": ["https://competitor.example/offer"],
        }
    ])
    assert "Competitor advertising analysis" in html
    assert "Competitor Co" in html
    assert "Competitor ads" in html
