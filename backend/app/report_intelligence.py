from __future__ import annotations

from collections import defaultdict
from typing import Any

from .campaign_intelligence import build_campaign_intelligence
from .device_change import detect_history_changes
from .device_comparison import compare_devices
from .evidence_confidence import advertiser_evidence_confidence


def _campaign_key(row: dict[str, Any]) -> str:
    return str(row.get("campaign_key") or row.get("ad_id") or "").strip()


def _confidence_summary(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in observations:
        key = _campaign_key(row)
        if key:
            grouped[key].append(advertiser_evidence_confidence(row))

    summary: list[dict[str, Any]] = []
    rank = {"unverified": 0, "low": 1, "medium": 2, "high": 3, "verified": 4}
    for key, items in grouped.items():
        best = max(items, key=lambda item: (rank[item["level"]], item["score"]))
        summary.append({
            "campaign_key": key,
            "level": best["level"],
            "score": best["score"],
            "signals": best["signals"],
            "observation_count": len(items),
        })
    summary.sort(key=lambda row: (-int(row["score"]), row["campaign_key"]))
    return summary


def build_report_intelligence(observations: list[dict[str, Any]]) -> dict[str, Any]:
    """Build one report-ready, evidence-backed intelligence payload."""
    if not all(isinstance(row, dict) for row in observations):
        raise ValueError("observations must be a list of objects")

    campaigns = build_campaign_intelligence(observations)
    devices = compare_devices(observations)
    history = detect_history_changes(observations)
    return {
        "campaigns": campaigns,
        "devices": devices,
        "history": history,
        "advertiser_confidence": _confidence_summary(observations),
        "observation_count": len(observations),
    }
