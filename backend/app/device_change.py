from __future__ import annotations

from collections import defaultdict
from typing import Any


def _text(value: Any) -> str:
    return str(value or "").strip()


def _norm(value: Any) -> str:
    return _text(value).lower().rstrip("/")


def _campaign_key(row: dict[str, Any]) -> str:
    return _norm(row.get("campaign_key")) or _norm(row.get("ad_id"))


def _set(rows: list[dict[str, Any]], field: str) -> set[str]:
    return {_text(row.get(field)) for row in rows if _text(row.get(field))}


def _creative_set(rows: list[dict[str, Any]]) -> set[str]:
    values: set[str] = set()
    for row in rows:
        for field in ("creative_image_urls", "creative_video_urls"):
            value = row.get(field) or []
            if isinstance(value, list):
                values.update(_norm(item) for item in value if _norm(item))
    return values


def detect_changes(previous: list[dict[str, Any]], current: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare two observation snapshots and report only evidence-backed changes."""
    old: dict[str, list[dict[str, Any]]] = defaultdict(list)
    new: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in previous:
        key = _campaign_key(row)
        if key:
            old[key].append(row)
    for row in current:
        key = _campaign_key(row)
        if key:
            new[key].append(row)

    changes: list[dict[str, Any]] = []
    for key in sorted(set(old) | set(new)):
        before, after = old.get(key, []), new.get(key, [])
        if not before:
            changes.append({"campaign_key": key, "change": "new_campaign"})
            continue
        if not after:
            changes.append({"campaign_key": key, "change": "campaign_disappeared"})
            continue

        before_devices = _set(before, "device")
        after_devices = _set(after, "device")
        before_places = _set(before, "ad_unit_code")
        after_places = _set(after, "ad_unit_code")
        before_creatives = _creative_set(before)
        after_creatives = _creative_set(after)

        if before_creatives and after_creatives and before_creatives != after_creatives:
            changes.append({"campaign_key": key, "change": "creative_changed", "added": sorted(after_creatives - before_creatives), "removed": sorted(before_creatives - after_creatives)})
        if before_places != after_places:
            changes.append({"campaign_key": key, "change": "placement_changed", "added": sorted(after_places - before_places), "removed": sorted(before_places - after_places)})
        if before_devices != after_devices:
            changes.append({"campaign_key": key, "change": "device_targeting_changed", "added": sorted(after_devices - before_devices), "removed": sorted(before_devices - after_devices)})

    return {
        "changes": changes,
        "change_count": len(changes),
        "new_campaigns": sum(c["change"] == "new_campaign" for c in changes),
        "disappeared_campaigns": sum(c["change"] == "campaign_disappeared" for c in changes),
        "creative_changes": sum(c["change"] == "creative_changed" for c in changes),
        "placement_changes": sum(c["change"] == "placement_changed" for c in changes),
        "device_targeting_changes": sum(c["change"] == "device_targeting_changed" for c in changes),
    }
