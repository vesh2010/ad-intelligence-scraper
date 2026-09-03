from __future__ import annotations

from typing import Any

from .campaign_intelligence import build_campaign_intelligence
from .device_change import detect_history_changes
from .device_comparison import compare_devices


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
        "observation_count": len(observations),
    }
