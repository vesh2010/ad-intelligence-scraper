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
