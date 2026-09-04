from io import BytesIO

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.site_reports import build_site_report_router


def _payload() -> dict:
    return {
        "root_url": "https://example.com",
        "pages_crawled": 1,
        "pages_failed": 0,
        "pages": [
            {
                "run_id": "a" * 32,
                "final_url": "https://example.com/news",
                "device": "desktop",
                "ad_records": [
                    {
                        "ad_type": "gpt",
                        "advertiser_name": "Acme Advertiser",
                        "brand_name": "Acme",
                        "landing_page_url": "https://acme.example/",
                        "evidence": ["gpt.advertiser_name"],
                    }
                ],
            }
        ],
    }


def test_site_report_endpoints():
    app = FastAPI()
    app.include_router(build_site_report_router())
    client = TestClient(app)
    payload = _payload()

    html = client.post("/api/site-crawl/report.html", json=payload)
    assert html.status_code == 200
    assert "Competitor / brand frequency" in html.text
    assert "Acme Advertiser" in html.text
    assert "Acme" in html.text

    pdf = client.post("/api/site-crawl/report.pdf", json=payload)
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")
    pdf_text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf.content)).pages)
    assert "Acme Advertiser" in pdf_text
    assert "Acme" in pdf_text

    intelligence = client.post("/api/site-crawl/intelligence", json=payload)
    assert intelligence.status_code == 200
    body = intelligence.json()
    assert body["observation_count"] == 1
    assert body["campaigns"]["campaigns"][0]["brand_name"] == "Acme"
    assert body["campaigns"]["campaigns"][0]["advertiser_name"] == "Acme Advertiser"
    assert body["campaigns"]["competitors"][0]["brand_name"] == "Acme"


def test_site_report_rejects_invalid_pages():
    app = FastAPI()
    app.include_router(build_site_report_router())
    response = TestClient(app).post("/api/site-crawl/intelligence", json={"pages": "bad"})
    assert response.status_code == 422
