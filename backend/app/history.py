from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .ad_records import AdRecord


def _norm(value: str | None) -> str:
    return (value or "").strip().lower().rstrip("/")


def campaign_key(record: AdRecord) -> str:
    """Stable observable campaign identity; creative evidence is deliberately excluded."""
    parts = [
        _norm(record.brand_name),
        _norm(record.advertiser_name),
        _norm(record.product_name),
        _norm(record.landing_page.get("url") if record.landing_page else None),
        *sorted(_norm(url) for url in record.destination_urls),
    ]
    raw = "|".join(part for part in parts if part)
    if not raw:
        raw = f"{record.ad_type}|{record.ad_format}|{record.ad_unit_code}|{record.element_id}"
    return "campaign_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def creative_fingerprint(record: AdRecord) -> str:
    """Return a stable fingerprint for creative evidence attached to an observation."""
    values = [_norm(url) for url in record.creative_image_urls + record.creative_video_urls]
    values.extend(
        evidence.removeprefix("creative:").strip()
        for evidence in record.evidence
        if evidence.startswith("creative:") and evidence.removeprefix("creative:").strip()
    )
    raw = "|".join(sorted(set(values)))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20] if raw else ""


def build_snapshot(records: list[AdRecord], observed_at: str) -> list[dict[str, Any]]:
    """Create compact historical observations suitable for a later database."""
    snapshot: list[dict[str, Any]] = []
    for record in records:
        snapshot.append(
            {
                "campaign_key": campaign_key(record),
                "observed_at": observed_at,
                "ad_id": record.ad_id,
                "brand_name": record.brand_name,
                "advertiser_name": record.advertiser_name,
                "product_name": record.product_name,
                "ad_type": record.ad_type,
                "ad_format": record.ad_format,
                "ad_unit_code": record.ad_unit_code,
                "device": getattr(record, "device", None),
                "bidder": record.bidder,
                "network_name": record.network_name,
                "cpm": record.cpm,
                "currency": record.currency,
                "destination_urls": record.destination_urls,
                "creative_image_urls": record.creative_image_urls,
                "creative_video_urls": record.creative_video_urls,
                "creative_fingerprint": creative_fingerprint(record),
                "above_fold": record.above_fold,
                "confidence": record.confidence,
            }
        )
    return snapshot


def append_snapshot(history_file: str | Path, records: list[AdRecord], observed_at: str) -> dict[str, int]:
    """Append observations atomically enough for the single-process crawler and return counts."""
    path = Path(history_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict[str, Any]] = []
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                existing = [item for item in loaded if isinstance(item, dict)]
        except (OSError, json.JSONDecodeError):
            existing = []
    additions = build_snapshot(records, observed_at)
    existing.extend(additions)
    path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    return {"observations": len(additions), "history_size": len(existing)}
