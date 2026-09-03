from __future__ import annotations

from pathlib import Path

import pytest

from app import creative_assets


@pytest.mark.asyncio
async def test_video_mp4_asset_is_downloaded(tmp_path: Path, monkeypatch) -> None:
    class FakeResponse:
        status_code = 200
        is_success = True
        headers = {"content-type": "video/mp4", "content-length": "9"}
        content = b"MP4DATA!!"

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url):
            return FakeResponse()

    monkeypatch.setattr(creative_assets, "_safe_asset_url", lambda url: _async_true())
    monkeypatch.setattr(creative_assets.httpx, "AsyncClient", FakeClient)

    assets = await creative_assets.capture_creative_assets(
        ["https://cdn.example.test/ad-video.mp4"], tmp_path
    )

    assert len(assets) == 1
    assert assets[0]["asset_kind"] == "video"
    assert assets[0]["mime_type"] == "video/mp4"
    assert str(assets[0]["path"]).endswith(".mp4")
    assert Path(str(assets[0]["path"])).read_bytes() == b"MP4DATA!!"


async def _async_true() -> bool:
    return True
