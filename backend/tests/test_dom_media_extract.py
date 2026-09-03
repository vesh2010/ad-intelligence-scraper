from __future__ import annotations

from app.dom_extract import DOM_SCRIPT


def test_dom_script_collects_video_audio_and_poster_sources() -> None:
    assert "audio_urls" in DOM_SCRIPT
    assert "video_posters" in DOM_SCRIPT
    assert "audio[src]" in DOM_SCRIPT
    assert "audio source[src]" in DOM_SCRIPT
    assert "video[poster]" in DOM_SCRIPT
    assert "video_urls" in DOM_SCRIPT
