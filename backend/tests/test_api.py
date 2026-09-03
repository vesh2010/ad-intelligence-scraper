from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_invalid_scheme_is_rejected_by_model():
    response = client.post("/api/crawl", json={"url": "ftp://example.com"})
    assert response.status_code == 422
