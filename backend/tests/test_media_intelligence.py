from pathlib import Path

from app import media_intelligence


def test_inspect_media_is_optional_without_ffprobe(tmp_path: Path, monkeypatch):
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"data")
    monkeypatch.setattr(media_intelligence.shutil, "which", lambda name: None)
    assert media_intelligence.inspect_media(media) == {"available": False, "reason": "ffprobe not installed"}


def test_inspect_media_extracts_streams_and_tags(tmp_path: Path, monkeypatch):
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"data")
    monkeypatch.setattr(media_intelligence.shutil, "which", lambda name: "/usr/bin/ffprobe")

    class Completed:
        returncode = 0
        stderr = ""
        stdout = '{"format":{"duration":"12.75","tags":{"title":"Spot","artist":"Artist"}},"streams":[{"index":0,"codec_type":"video","codec_name":"h264"},{"index":1,"codec_type":"audio","codec_name":"aac","channels":2}]}'

    monkeypatch.setattr(media_intelligence.subprocess, "run", lambda *args, **kwargs: Completed())
    result = media_intelligence.inspect_media(media)
    assert result["available"] is True
    assert result["duration_seconds"] == 12.75
    assert result["audio_stream_count"] == 1
    assert result["video_stream_count"] == 1
    assert result["audio_codecs"] == ["aac"]
    assert result["video_codecs"] == ["h264"]
    assert result["title"] == "Spot"
    assert result["artist"] == "Artist"
