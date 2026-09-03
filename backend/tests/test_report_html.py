from fastapi.testclient import TestClient

from app.main import app
from app.report_html import render_html_report

client = TestClient(app)

OBSERVATIONS = [
    {
        "observed_at": "2026-09-03T10:00:00Z",
        "campaign_key": "c1",
        "brand_name": "Brand <A>",
        "advertiser_name": "Advertiser A",
        "device": "desktop",
        "ad_unit_code": "top",
    },
    {
        "observed_at": "2026-09-03T11:00:00Z",
        "campaign_key": "c1",
        "brand_name": "Brand <A>",
        "advertiser_name": "Advertiser A",
        "device": "mobile",
        "ad_unit_code": "mrec",
    },
]


def test_render_html_report_is_self_contained_and_escaped():
    body = render_html_report(OBSERVATIONS, title="Test <Report>")
    assert "<!doctype html>" in body
    assert "Test &lt;Report&gt;" in body
    assert "Brand &lt;A&gt;" in body
    assert "Observations" in body
    assert "Machine-readable intelligence" in body


def test_report_html_api():
    response = client.post(
        "/api/report/html",
        json={"title": "Test Report", "observations": OBSERVATIONS},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Both devices" in response.text
    assert "Brand &lt;A&gt;" in response.text


def test_report_html_api_validates_observations_and_title():
    assert client.post("/api/report/html", json={"observations": "invalid"}).status_code == 422
    assert client.post("/api/report/html", json={"observations": [], "title": ""}).status_code == 422
    assert client.post("/api/report/html", json={"observations": [], "title": 123}).status_code == 422
