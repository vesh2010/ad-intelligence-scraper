from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.main import crawler

client = TestClient(app)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_invalid_scheme_is_rejected_by_model():
    response = client.post("/api/crawl", json={"url": "ftp://example.com"})
    assert response.status_code == 422


def test_unknown_artifact_is_rejected():
    response = client.get("/api/runs/0123456789abcdef0123456789abcdef/artifact/unknown")
    assert response.status_code == 404


def test_history_changes_api():
    response = client.post(
        "/api/history/changes",
        json={
            "observations": [
                {"observed_at": "2026-09-03T10:00:00Z", "campaign_key": "c1", "ad_unit_code": "top"},
                {"observed_at": "2026-09-03T11:00:00Z", "campaign_key": "c1", "ad_unit_code": "mrec"},
            ]
        },
    )
    assert response.status_code == 200
    assert response.json()["placement_changes"] == 1


def test_history_changes_api_validates_observations():
    response = client.post("/api/history/changes", json={"observations": "invalid"})
    assert response.status_code == 422


def test_report_intelligence_api():
    response = client.post(
        "/api/report/intelligence",
        json={
            "observations": [
                {
                    "observed_at": "2026-09-03T10:00:00Z",
                    "campaign_key": "c1",
                    "brand_name": "Brand A",
                    "device": "desktop",
                    "ad_unit_code": "top",
                },
                {
                    "observed_at": "2026-09-03T11:00:00Z",
                    "campaign_key": "c1",
                    "brand_name": "Brand A",
                    "device": "mobile",
                    "ad_unit_code": "mrec",
                },
            ]
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["observation_count"] == 2
    assert body["campaigns"]["campaign_count"] == 1
    assert body["devices"]["both_device_campaigns"] == 1


def test_report_intelligence_api_validates_observations():
    response = client.post("/api/report/intelligence", json={"observations": "invalid"})
    assert response.status_code == 422


def test_artifact_path_cannot_escape_run_directory(tmp_path: Path):
    run_id = "0123456789abcdef0123456789abcdef"
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "screenshot.png").write_bytes(b"image")
    old_root = crawler.data_root
    crawler.data_root = tmp_path
    try:
        assert client.get(f"/api/runs/{run_id}/artifact/screenshot").status_code == 200
    finally:
        crawler.data_root = old_root
