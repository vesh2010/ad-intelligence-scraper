from __future__ import annotations

import pytest

import app.landing_page as landing_page


@pytest.mark.asyncio
async def test_private_dns_resolution_is_rejected(monkeypatch):
    def fake_getaddrinfo(*args, **kwargs):
        return [(0, 0, 0, "", ("10.0.0.10", 443))]

    monkeypatch.setattr(landing_page.socket, "getaddrinfo", fake_getaddrinfo)
    assert await landing_page._safe_public_destination("https://example.com/") is False


@pytest.mark.asyncio
async def test_public_dns_resolution_is_allowed(monkeypatch):
    def fake_getaddrinfo(*args, **kwargs):
        return [(0, 0, 0, "", ("93.184.216.34", 443))]

    monkeypatch.setattr(landing_page.socket, "getaddrinfo", fake_getaddrinfo)
    assert await landing_page._safe_public_destination("https://example.com/") is True
