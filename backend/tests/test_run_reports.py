from io import BytesIO
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.crawler.models import CrawlResult
from app.run_reports import build_run_report_router


def _run(root: Path, run_id: str) -> None:
    run_dir = root / run_id
    run_dir.mkdir(parents=True)
    result = CrawlResult(
        run_id=run_id,
        requested_url="https://example.com/news",
        final_url="https://example.com/news",
        status=200,
        title="Example",
        elapsed_ms=10,
        dimensions={"width": 1280, "height": 720},
        counts={}, metadata={}, redirects=[], network=[], console_errors=[], page_errors=[], frames=[], artifacts={},
        ad_records=[
            {
                "ad_type": "gpt",
                "advertiser_name": "Acme Advertiser",
                "brand_name": "Acme",
                "landing_page_url": "https://acme.example/",
                "evidence": ["gpt.advertiser_name"],
            }
        ],
        device="desktop",
    )
    (run_dir / "result.json").write_text(result.model_dump_json(), encoding="utf-8")


def test_run_report_endpoints_read_current_run(tmp_path: Path):
    run_id = "a" * 32
    _run(tmp_path, run_id)
    app = FastAPI()
    app.include_router(build_run_report_router(tmp_path))
    client = TestClient(app)

    html = client.get(f"/api/runs/{run_id}/report.html")
    assert html.status_code == 200
    assert "Ad Intelligence" in html.text
    assert "Acme Advertiser" in html.text

    pdf = client.get(f"/api/runs/{run_id}/report.pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")
    pdf_text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf.content)).pages)
    assert "Acme Advertiser" in pdf_text
    assert "Acme" in pdf_text

    intelligence = client.get(f"/api/runs/{run_id}/intelligence")
    assert intelligence.status_code == 200
    assert intelligence.json()["observation_count"] == 1


def test_run_report_missing_run_is_404(tmp_path: Path):
    app = FastAPI()
    app.include_router(build_run_report_router(tmp_path))
    response = TestClient(app).get(f"/api/runs/{'b' * 32}/report.pdf")
    assert response.status_code == 404
