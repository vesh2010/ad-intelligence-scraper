from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

MAX_OCR_CHARS = 2000
MAX_OCR_TIMEOUT_S = 8
_CTA_TERMS = re.compile(
    r"\b(?:buy now|shop now|learn more|sign up|get started|download|subscribe|apply now|book now|order now|try now|discover|read more|watch now)\b",
    re.IGNORECASE,
)


def _clean_text(text: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)[:MAX_OCR_CHARS]


def ocr_image(path: str | Path, timeout_s: float = MAX_OCR_TIMEOUT_S) -> dict[str, Any]:
    """Run bounded local Tesseract OCR; missing OCR is a non-fatal condition."""
    image = Path(path)
    if not image.is_file():
        return {"available": False, "text": "", "confidence": None, "error": "image not found"}
    executable = shutil.which("tesseract")
    if not executable:
        return {"available": False, "text": "", "confidence": None, "error": "tesseract not installed"}
    try:
        result = subprocess.run(
            [executable, str(image), "stdout", "--psm", "11", "-l", "eng"],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        if result.returncode != 0:
            return {
                "available": True,
                "text": "",
                "confidence": None,
                "error": result.stderr.strip()[:500] or f"tesseract exit {result.returncode}",
            }
        text = _clean_text(result.stdout)
        return {"available": True, "text": text, "confidence": None, "error": None}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": True, "text": "", "confidence": None, "error": str(exc)[:500]}


def classify_visual_evidence(
    screenshot: str | Path,
    bbox: dict[str, Any] | None = None,
    creative_assets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Produce explainable visual signals without guessing advertiser identity."""
    ocr = ocr_image(screenshot)
    text = str(ocr.get("text") or "")
    words = re.findall(r"\b[\w$%&+.-]+\b", text)
    cta_count = len(_CTA_TERMS.findall(text))
    assets = creative_assets or []
    has_video = any(str(item.get("mime_type", "")).startswith("video/") for item in assets)
    has_image = any(str(item.get("mime_type", "")).startswith("image/") for item in assets)

    width = int((bbox or {}).get("width") or 0)
    height = int((bbox or {}).get("height") or 0)
    aspect = round(width / height, 3) if height else None
    if has_video:
        creative_kind = "video"
    elif has_image:
        creative_kind = "image"
    elif text:
        creative_kind = "text"
    else:
        creative_kind = "unknown"

    if cta_count and len(words) >= 4:
        composition = "text_with_cta"
    elif len(words) >= 8:
        composition = "text_heavy"
    elif has_image and text:
        composition = "image_with_text"
    elif has_image:
        composition = "image_only"
    elif has_video:
        composition = "video_only"
    else:
        composition = "unknown"

    return {
        "ocr": ocr,
        "visual_classification": {
            "creative_kind": creative_kind,
            "composition": composition,
            "word_count": len(words),
            "cta_count": cta_count,
            "aspect_ratio": aspect,
            "has_image_asset": has_image,
            "has_video_asset": has_video,
        },
    }
