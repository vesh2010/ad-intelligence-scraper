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
        fingerprint = _text(row.get("creative_fingerprint"))
        if fingerprint:
            values.add(fingerprint)
            continue
        for field in ("creative_image_urls", "creative_video_urls"):
            value = row.get(field) or []
            if isinstance(value, list):
                values.update(_norm(item) for item in value if _norm(item))
    return values


def _compare_campaign(key: str, before: list[dict[str, Any]], after: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not before:
        return [{"campaign_key": key, "change": "new_campaign"}]
    if not after:
        return [{"campaign_key": key, "change": "campaign_disappeared"}]

    changes: list[dict[str, Any]] = []
    before_devices, after_devices = _set(before, "device"), _set(after, "device")
    before_places, after_places = _set(before, "ad_unit_code"), _set(after, "ad_unit_code")
    before_creatives, after_creatives = _creative_set(before), _creative_set(after)
    before_networks, after_networks = _set(before, "network_name"), _set(after, "network_name")
    before_cpms, after_cpms = _set(before, "cpm"), _set(after, "cpm")

    if before_creatives and after_creatives and before_creatives != after_creatives:
        changes.append({"campaign_key": key, "change": "creative_changed", "added": sorted(after_creatives - before_creatives), "removed": sorted(before_creatives - after_creatives)})
    if before_places != after_places:
        changes.append({"campaign_key": key, "change": "placement_changed", "added": sorted(after_places - before_places), "removed": sorted(before_places - after_places)})
    if before_devices != after_devices:
        changes.append({"campaign_key": key, "change": "device_targeting_changed", "added": sorted(after_devices - before_devices), "removed": sorted(before_devices - after_devices)})
    if before_networks != after_networks:
        changes.append({"campaign_key": key, "change": "network_changed", "added": sorted(after_networks - before_networks), "removed": sorted(before_networks - after_networks)})
    if before_cpms != after_cpms:
        changes.append({"campaign_key": key, "change": "cpm_changed", "previous": sorted(before_cpms), "current": sorted(after_cpms)})
    if not changes:
        changes.append({"campaign_key": key, "change": "continued"})
    return changes


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
    changes = [change for key in sorted(set(old) | set(new)) for change in _compare_campaign(key, old.get(key, []), new.get(key, []))]
    return _summary(changes)


def detect_history_changes(observations: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare every adjacent observation timestamp in a persisted history."""
    snapshots: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in observations:
        timestamp = _text(row.get("observed_at"))
        if timestamp:
            snapshots[timestamp].append(row)

    timestamps = sorted(snapshots)
    events: list[dict[str, Any]] = []
    for previous_at, current_at in zip(timestamps, timestamps[1:]):
        pair_changes = detect_changes(snapshots[previous_at], snapshots[current_at])["changes"]
        for change in pair_changes:
            events.append({"from_observed_at": previous_at, "to_observed_at": current_at, **change})
    result = _summary(events)
    result["snapshot_count"] = len(timestamps)
    result["observed_at"] = timestamps
    return result


def _summary(changes: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "changes": changes,
        "change_count": len(changes),
        "new_campaigns": sum(c["change"] == "new_campaign" for c in changes),
        "disappeared_campaigns": sum(c["change"] == "campaign_disappeared" for c in changes),
        "continued_campaigns": sum(c["change"] == "continued" for c in changes),
        "creative_changes": sum(c["change"] == "creative_changed" for c in changes),
        "placement_changes": sum(c["change"] == "placement_changed" for c in changes),
        "device_targeting_changes": sum(c["change"] == "device_targeting_changed" for c in changes),
        "network_changes": sum(c["change"] == "network_changed" for c in changes),
        "cpm_changes": sum(c["change"] == "cpm_changed" for c in changes),
    }
