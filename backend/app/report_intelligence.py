from __future__ import annotations

from collections import defaultdict
from typing import Any

from .ad_request_resolution import match_ad_requests, resolve_ad_requests
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


def _request_resolution_summary(observations: list[dict[str, Any]]) -> dict[str, Any]:
    resolved: list[dict[str, Any]] = []
    request_count = 0
    for row in observations:
        network = row.get("network")
        if not isinstance(network, list):
            continue
        requests = resolve_ad_requests([item for item in network if isinstance(item, dict)])
        request_count += len(requests)
        runtime = row.get("runtime_ads")
        snapshots = runtime.get("snapshots", []) if isinstance(runtime, dict) else []
        latest = snapshots[-1].get("data", {}) if snapshots and isinstance(snapshots[-1], dict) else {}
        gpt = latest.get("gpt", {}) if isinstance(latest, dict) else {}
        slots = gpt.get("slots", []) if isinstance(gpt, dict) else []
        for slot in slots if isinstance(slots, list) else []:
            if isinstance(slot, dict):
                matches = match_ad_requests(slot, requests)
                if matches:
                    resolved.append({
                        "campaign_key": _campaign_key(row),
                        "element_id": slot.get("element_id"),
                        "ad_unit_path": slot.get("ad_unit_path"),
                        "matches": matches,
                    })
    return {
        "resolved_slots": resolved,
        "resolved_slot_count": len(resolved),
        "request_count": request_count,
    }


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
        "ad_request_resolution": _request_resolution_summary(observations),
        "observation_count": len(observations),
    }
