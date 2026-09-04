from __future__ import annotations

from typing import Any


_LEVELS = ("unverified", "low", "medium", "high", "verified")


def _present(value: Any) -> bool:
    return bool(str(value or "").strip())


def advertiser_evidence_confidence(record: dict[str, Any]) -> dict[str, Any]:
    """Score advertiser identity from corroborating observable evidence.

    OCR/visual text is supporting evidence only and can never produce a
    verified identity by itself. Request-resolution evidence is also treated
    as corroboration unless it explicitly exposes advertiser metadata.
    """
    evidence = {str(item).strip().lower() for item in (record.get("evidence") or []) if str(item).strip()}
    signals: list[str] = []
    score = 0

    if _present(record.get("advertiser_name")) or _present(record.get("advertiser_id")):
        score += 45
        signals.append("advertiser_metadata")
    if _present(record.get("brand_name")):
        score += 15
        signals.append("brand_metadata")
    if _present(record.get("landing_page_url")) or record.get("destination_urls"):
        score += 20
        signals.append("landing_destination")
    if _present(record.get("bidder")) or _present(record.get("network")):
        score += 10
        signals.append("ad_tech_signal")
    resolution = record.get("request_resolution")
    if isinstance(resolution, dict) and resolution.get("matches"):
        score += 5
        signals.append("request_resolution")
    if any("creative" in item or "ocr" in item or "visual" in item for item in evidence):
        score += 10
        signals.append("creative_visual_support")

    if not signals:
        level = "unverified"
    elif score >= 80 and ("advertiser_metadata" in signals or "landing_destination" in signals):
        level = "verified"
    elif score >= 60:
        level = "high"
    elif score >= 35:
        level = "medium"
    else:
        level = "low"

    return {"score": min(score, 100), "level": level, "signals": signals}


def add_advertiser_confidence(record: dict[str, Any]) -> dict[str, Any]:
    result = dict(record)
    result["advertiser_confidence"] = advertiser_evidence_confidence(result)
    return result


__all__ = ["advertiser_evidence_confidence", "add_advertiser_confidence"]
