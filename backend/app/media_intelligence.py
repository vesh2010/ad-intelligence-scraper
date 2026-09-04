from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


def inspect_media(path: str | Path, timeout_s: float = 4.0) -> dict[str, Any]:
    """Inspect downloaded media with ffprobe when available.

    This is deliberately optional: the scraper remains functional without FFmpeg.
    Metadata is evidence only; tags such as artist/title are not treated as advertiser identity.
    """
    probe = shutil.which("ffprobe")
    if not probe:
        return {"available": False, "reason": "ffprobe not installed"}
    target = Path(path)
    if not target.is_file():
        return {"available": False, "reason": "media file not found"}
    try:
        completed = subprocess.run(
            [probe, "-v", "error", "-show_entries", "format=duration:format_tags=title,artist,album", "-show_entries", "stream=index,codec_type,codec_name,channels:stream_tags=title,language", "-of", "json", str(target)],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"available": False, "reason": str(exc)}
    if completed.returncode != 0:
        return {"available": False, "reason": completed.stderr.strip()[:500] or "ffprobe failed"}
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        return {"available": False, "reason": "invalid ffprobe output"}

    streams = payload.get("streams") if isinstance(payload.get("streams"), list) else []
    audio = [row for row in streams if isinstance(row, dict) and row.get("codec_type") == "audio"]
    video = [row for row in streams if isinstance(row, dict) and row.get("codec_type") == "video"]
    fmt = payload.get("format") if isinstance(payload.get("format"), dict) else {}
    tags = fmt.get("tags") if isinstance(fmt.get("tags"), dict) else {}
    result: dict[str, Any] = {
        "available": True,
        "duration_seconds": _number(fmt.get("duration")),
        "audio_stream_count": len(audio),
        "video_stream_count": len(video),
        "audio_codecs": sorted({str(row.get("codec_name")) for row in audio if row.get("codec_name")}),
        "video_codecs": sorted({str(row.get("codec_name")) for row in video if row.get("codec_name")}),
    }
    for key in ("title", "artist", "album"):
        if tags.get(key):
            result[key] = str(tags[key])[:300]
    if audio:
        result["audio_streams"] = [
            {key: row[key] for key in ("index", "codec_name", "channels") if key in row}
            for row in audio[:4]
        ]
    return result


def _number(value: Any) -> float | None:
    try:
        return round(float(value), 3)
    except (TypeError, ValueError):
        return None


__all__ = ["inspect_media"]
