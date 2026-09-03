from __future__ import annotations

from collections import defaultdict
from typing import Any


def _norm(value: Any) -> str:
    return str(value or "").strip().lower().rstrip("/")


def compare_devices(observations: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: {"desktop": [], "mobile": []})
    for row in observations:
        key = _norm(row.get("campaign_key")) or _norm(row.get("ad_id"))
        device = _norm(row.get("device"))
        if key and device in {"desktop", "mobile"}:
            groups[key][device].append(row)
    campaigns = []
    for key, group in groups.items():
        desktop, mobile = group["desktop"], group["mobile"]
        dp = sorted({_norm(r.get("ad_unit_code")) for r in desktop if _norm(r.get("ad_unit_code"))})
        mp = sorted({_norm(r.get("ad_unit_code")) for r in mobile if _norm(r.get("ad_unit_code"))})
        campaigns.append({"campaign_key": key, "desktop_observations": len(desktop), "mobile_observations": len(mobile), "desktop_only": bool(desktop) and not mobile, "mobile_only": bool(mobile) and not desktop, "both_devices": bool(desktop) and bool(mobile), "desktop_placements": dp, "mobile_placements": mp, "shared_placements": sorted(set(dp) & set(mp))})
    campaigns.sort(key=lambda r: (-int(r["both_devices"]), -(r["desktop_observations"] + r["mobile_observations"]), r["campaign_key"]))
    return {"campaigns": campaigns, "campaign_count": len(campaigns), "both_device_campaigns": sum(r["both_devices"] for r in campaigns), "desktop_only_campaigns": sum(r["desktop_only"] for r in campaigns), "mobile_only_campaigns": sum(r["mobile_only"] for r in campaigns)}
