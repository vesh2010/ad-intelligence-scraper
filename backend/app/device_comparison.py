from __future__ import annotations

from collections import defaultdict
from typing import Any

from .device_profiles import DESKTOP, MOBILE, DeviceProfile


def _norm(value: Any) -> str:
    return str(value or "").strip().lower().rstrip("/")


def compare_devices(observations: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare observed campaign presence and placements across desktop/mobile."""
    groups: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: {"desktop": [], "mobile": []}
    )
    for row in observations:
        key = _norm(row.get("campaign_key")) or _norm(row.get("ad_id"))
        device = _norm(row.get("device"))
        if key and device in {"desktop", "mobile"}:
            groups[key][device].append(row)

    campaigns: list[dict[str, Any]] = []
    for key, group in groups.items():
        desktop = group["desktop"]
        mobile = group["mobile"]
        desktop_placements = sorted(
            {_norm(row.get("ad_unit_code")) for row in desktop if _norm(row.get("ad_unit_code"))}
        )
        mobile_placements = sorted(
            {_norm(row.get("ad_unit_code")) for row in mobile if _norm(row.get("ad_unit_code"))}
        )
        campaigns.append(
            {
                "campaign_key": key,
                "desktop_observations": len(desktop),
                "mobile_observations": len(mobile),
                "desktop_only": bool(desktop) and not mobile,
                "mobile_only": bool(mobile) and not desktop,
                "both_devices": bool(desktop) and bool(mobile),
                "desktop_placements": desktop_placements,
                "mobile_placements": mobile_placements,
                "shared_placements": sorted(set(desktop_placements) & set(mobile_placements)),
            }
        )

    campaigns.sort(
        key=lambda row: (
            -int(row["both_devices"]),
            -(row["desktop_observations"] + row["mobile_observations"]),
            row["campaign_key"],
        )
    )
    return {
        "campaigns": campaigns,
        "campaign_count": len(campaigns),
        "both_device_campaigns": sum(row["both_devices"] for row in campaigns),
        "desktop_only_campaigns": sum(row["desktop_only"] for row in campaigns),
        "mobile_only_campaigns": sum(row["mobile_only"] for row in campaigns),
    }


__all__ = ["compare_devices", "DESKTOP", "MOBILE", "DeviceProfile"]
