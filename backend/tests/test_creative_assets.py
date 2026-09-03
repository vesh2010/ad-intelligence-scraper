from __future__ import annotations

from pathlib import Path

import pytest

from app import creative_assets


class _FakeResponse:
    status_code = 200
    is_success = True
    headers = {"content-type": "image/png", "content-length": "4"}
    content = b"PNG!"


class _FakeClient:
    def __init__(self, *args, **kwargs):
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url):
        self.calls.append(url)
        return _FakeResponse()


@pytest.mark.asyncio
async def test_creative_asset_is_hashed_and_saved(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(creative_assets, "_safe_asset_url", lambda url: _async_true())
    monkeypatch.setattr(creative_assets.httpx, "AsyncClient", _FakeClient)

    assets = await creative_assets.capture_creative_assets(
        ["https://cdn.example.test/creative.png"], tmp_path
    )

    assert len(assets) == 1
    assert assets[0]["mime_type"] == "image/png"
    assert assets[0]["asset_kind"] == "image"
    assert assets[0]["bytes"] == 4
    assert len(assets[0]["sha256"]) == 64
    saved = Path(str(assets[0]["path"]))
    assert saved.is_file()
    assert saved.read_bytes() == b"PNG!"


@pytest.mark.asyncio
async def test_audio_creative_is_saved_with_audio_metadata(tmp_path: Path, monkeypatch) -> None:
    class _AudioResponse:
        status_code = 200
        is_success = True
        headers = {"content-type": "audio/mpeg", "content-length": "8"}
        content = b"MP3DATA!"

    class _AudioClient(_FakeClient):
        async def get(self, url):
            self.calls.append(url)
            return _AudioResponse()

    monkeypatch.setattr(creative_assets, "_safe_asset_url", lambda url: _async_true())
    monkeypatch.setattr(creative_assets.httpx, "AsyncClient", _AudioClient)

    assets = await creative_assets.capture_creative_assets(
        ["https://cdn.example.test/spot.mp3"], tmp_path
    )

    assert len(assets) == 1
    assert assets[0]["mime_type"] == "audio/mpeg"
    assert assets[0]["asset_kind"] == "audio"
    assert str(assets[0]["path"]).endswith(".mp3")
    assert Path(str(assets[0]["path"])).read_bytes() == b"MP3DATA!"


@pytest.mark.asyncio
async def test_creative_asset_rejects_non_public_url(tmp_path: Path) -> None:
    assets = await creative_assets.capture_creative_assets(
        ["http://127.0.0.1/secret.png", "file:///etc/passwd"], tmp_path
    )
    assert assets == []


async def _async_true() -> bool:
    return True
