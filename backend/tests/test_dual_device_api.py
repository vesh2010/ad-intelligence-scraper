from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_dual_device_endpoint_exists() -> None:
    paths = {route.path for route in app.routes}
    assert "/api/crawl/both-devices" in paths


def test_crawl_request_defaults_to_desktop() -> None:
    from app.crawler.models import CrawlRequest

    request = CrawlRequest(url="https://example.com")
    assert request.device == "desktop"
