from __future__ import annotations

from collections import defaultdict
from typing import Any


def _norm(value: Any) -> str:
    return str(value or "").strip().lower().rstrip("/")


def _campaign_id(observation: dict[str, Any]) -> str:
    return _norm(observation.get("campaign_key")) or _norm(observation.get("ad_id"))


def compare_devices(observations: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare desktop/mobile observations without inventing missing ads."""
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: {"desktop": [], "mobile": []})
    for observation in observations:
        campaign = _campaign_id(observation)
        device = _norm(observation.get("device"))
        if not campaign or device not in {"desktop", "mobile"}:
            continue
        grouped[campaign][device].append(observation)

    rows: list[dict[str, Any]] = []
    for campaign, devices in grouped.items():
        desktop = devices["desktop"]
        mobile = devices["mobile"]
        if not desktop and not mobile:
            continue
        desktop_places = sorted({_norm(r.get("ad_unit_code")) for r in desktop if _norm(r.get("ad_unit_code"))})
        mobile_places = sorted({_norm(r.get("ad_unit_code")) for r in mobile if _norm(r.get("ad_unit_code"))})
        rows.append({
            "campaign_key": campaign,
            "desktop_observations": len(desktop),
            "mobile_observations": len(mobile),
            "desktop_present": bool(desktop),
            "mobile_present": bool(mobile),
            "desktop_only": bool(desktop) and not mobile,
            "mobile_only": bool(mobile) and not desktop,
            "both_devices": bool(desktop) and bool(mobile),
            "desktop_placements": desktop_places,
            "mobile_placements": mobile_places,
            "shared_placements": sorted(set(desktop_places) & set(mobile_places)),
        })

    rows.sort(key=lambda row: (-int(row["both_devices"]), -row["desktop_observations"] - row["mobile_observations"], row["campaign_key"]))
    return {
        "campaigns": rows,
        "campaign_count": len(rows),
        "both_device_campaigns": sum(row["both_devices"] for row in rows),
        "desktop_only_campaigns": sum(row["desktop_only"] for row in rows),
        "mobile_only_campaigns": sum(row["mobile_only"] for row in rows),
    }
