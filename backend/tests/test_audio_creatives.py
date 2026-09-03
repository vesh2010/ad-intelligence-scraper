from __future__ import annotations

from pathlib import Path

import pytest

from app import creative_assets, visual_analysis


@pytest.mark.asyncio
async def test_audio_mpeg_asset_is_downloaded_and_classified(tmp_path: Path, monkeypatch) -> None:
    class FakeResponse:
        status_code = 200
        is_success = True
        headers = {"content-type": "audio/mpeg", "content-length": "8"}
        content = b"MP3DATA!"

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
        ["https://cdn.example.test/ad-song.mp3"], tmp_path
    )

    assert len(assets) == 1
    assert assets[0]["asset_kind"] == "audio"
    assert assets[0]["mime_type"] == "audio/mpeg"
    assert str(assets[0]["path"]).endswith(".mp3")
    assert Path(str(assets[0]["path"])).read_bytes() == b"MP3DATA!"


def test_audio_asset_is_reported_by_visual_classification(tmp_path: Path, monkeypatch) -> None:
    image = tmp_path / "candidate.png"
    image.write_bytes(b"x")
    monkeypatch.setattr(
        visual_analysis,
        "ocr_image",
        lambda path: {"available": False, "text": "", "confidence": None, "error": None},
    )

    result = visual_analysis.classify_visual_evidence(
        image,
        {"width": 300, "height": 250},
        [{"mime_type": "audio/mpeg", "asset_kind": "audio"}],
    )

    assert result["visual_classification"]["creative_kind"] == "audio"
    assert result["visual_classification"]["composition"] == "audio_only"
    assert result["visual_classification"]["has_audio_asset"] is True


async def _async_true() -> bool:
    return True
