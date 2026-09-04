from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.main import crawler, history_store, monitor_store

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
    response = client.post("/api/history/changes", json={"observations": [
        {"observed_at": "2026-09-03T10:00:00Z", "campaign_key": "c1", "ad_unit_code": "top"},
        {"observed_at": "2026-09-03T11:00:00Z", "campaign_key": "c1", "ad_unit_code": "mrec"},
    ]})
    assert response.status_code == 200
    assert response.json()["placement_changes"] == 1


def test_history_changes_api_validates_observations():
    response = client.post("/api/history/changes", json={"observations": "invalid"})
    assert response.status_code == 422


def test_report_intelligence_api():
    response = client.post("/api/report/intelligence", json={"observations": [
        {"observed_at": "2026-09-03T10:00:00Z", "campaign_key": "c1", "brand_name": "Brand A", "device": "desktop", "ad_unit_code": "top"},
        {"observed_at": "2026-09-03T11:00:00Z", "campaign_key": "c1", "brand_name": "Brand A", "device": "mobile", "ad_unit_code": "mrec"},
    ]})
    assert response.status_code == 200
    body = response.json()
    assert body["observation_count"] == 2
    assert body["campaigns"]["campaign_count"] == 1
    assert body["devices"]["both_device_campaigns"] == 1


def test_report_intelligence_api_validates_observations():
    response = client.post("/api/report/intelligence", json={"observations": "invalid"})
    assert response.status_code == 422


def test_report_pdf_api():
    response = client.post("/api/report/pdf", json={"title": "PDF Regression", "observations": [
        {"observed_at": "2026-09-03T10:00:00Z", "campaign_key": "c1", "brand_name": "Brand A", "device": "desktop", "ad_unit_code": "top"},
        {"observed_at": "2026-09-03T11:00:00Z", "campaign_key": "c1", "brand_name": "Brand A", "device": "mobile", "ad_unit_code": "mrec"},
    ]})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("inline;")
    assert response.content.startswith(b"%PDF")
    assert b"%EOF" in response.content


def test_report_pdf_api_validates_observations_and_title():
    assert client.post("/api/report/pdf", json={"observations": "invalid"}).status_code == 422
    assert client.post("/api/report/pdf", json={"observations": [], "title": " "}).status_code == 422


def test_persistent_history_api(tmp_path: Path):
    old_root = history_store.root
    history_store.root = tmp_path
    target = "https://example.com/news"
    observations = [{"observed_at": "2026-09-03T10:00:00Z", "campaign_key": "c1"}]
    try:
        write = client.post("/api/history", params={"target": target}, json={"observations": observations})
        assert write.status_code == 200
        assert write.json()["history_size"] == 1
        read = client.get("/api/history", params={"target": target})
        assert read.status_code == 200
        assert read.json()["observations"] == observations
        intelligence = client.get("/api/history/intelligence", params={"target": target})
        assert intelligence.status_code == 200
        assert intelligence.json()["observation_count"] == 1
        report = client.get("/api/history/report", params={"target": target})
        assert report.status_code == 200
        assert "Ad Intelligence" in report.text
        pdf = client.get("/api/history/report.pdf", params={"target": target})
        assert pdf.status_code == 200
        assert pdf.headers["content-type"] == "application/pdf"
        assert pdf.content.startswith(b"%PDF")
    finally:
        history_store.root = old_root


def test_persistent_history_api_validates_observations():
    response = client.post("/api/history", params={"target": "example.com"}, json={"observations": "invalid"})
    assert response.status_code == 422


def test_monitor_api_lifecycle(tmp_path: Path):
    old_root = monitor_store.root
    monitor_store.root = tmp_path
    try:
        created = client.post("/api/monitors", json={"url": "https://example.com/news", "device": "both", "interval_minutes": 120})
        assert created.status_code == 200
        monitor = created.json()
        assert monitor["device"] == "both"
        monitor_id = monitor["monitor_id"]
        listed = client.get("/api/monitors")
        assert listed.status_code == 200
        assert listed.json()["count"] == 1
        updated = client.patch(f"/api/monitors/{monitor_id}", json={"enabled": False})
        assert updated.status_code == 200
        assert updated.json()["enabled"] is False
        alerts = client.get(f"/api/monitors/{monitor_id}/alerts")
        assert alerts.status_code == 200
        assert alerts.json()["count"] == 0
        deleted = client.delete(f"/api/monitors/{monitor_id}")
        assert deleted.status_code == 200
        assert client.get(f"/api/monitors/{monitor_id}").status_code == 404
    finally:
        monitor_store.root = old_root


def test_monitor_api_validates_interval_and_device(tmp_path: Path):
    old_root = monitor_store.root
    monitor_store.root = tmp_path
    try:
        assert client.post("/api/monitors", json={"url": "https://example.com", "interval_minutes": 30}).status_code == 422
        assert client.post("/api/monitors", json={"url": "https://example.com", "device": "tablet"}).status_code == 422
    finally:
        monitor_store.root = old_root


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
