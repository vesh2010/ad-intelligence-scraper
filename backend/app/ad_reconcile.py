from __future__ import annotations

import hashlib
from typing import Any

from .ad_records import AdRecord


def _ad_id(parts: list[object]) -> str:
    raw = "|".join(str(p or "") for p in parts)
    return "ad_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _latest_runtime(runtime_snapshots: list[dict[str, object]]) -> dict[str, Any]:
    if not runtime_snapshots:
        return {"gpt": {}, "prebid": {}}
    data = runtime_snapshots[-1].get("data", {})
    return data if isinstance(data, dict) else {"gpt": {}, "prebid": {}}


def _placement(slot_dom: Any, evidence: dict[str, object] | None) -> dict[str, object]:
    if slot_dom is None and evidence is None:
        return {}
    return {
        "selector": getattr(slot_dom, "selector", None),
        "x": getattr(slot_dom, "x", None),
        "y": getattr(slot_dom, "y", None),
        "width": getattr(slot_dom, "width", None),
        "height": getattr(slot_dom, "height", None),
        "position_mode": getattr(slot_dom, "position_mode", None),
        "screenshot": evidence.get("screenshot") if evidence else None,
    }


def _dom_urls(slot_dom: Any) -> tuple[list[str], list[str], list[str]]:
    if slot_dom is None:
        return [], [], []
    return (
        list(getattr(slot_dom, "hrefs", []) or []),
        list(getattr(slot_dom, "image_urls", []) or []),
        list(getattr(slot_dom, "video_urls", []) or []),
    )


def reconcile_ad_records(
    ad_detection: Any,
    runtime_snapshots: list[dict[str, object]],
    visual_evidence: list[dict[str, object]],
) -> list[AdRecord]:
    """Merge publisher-runtime and DOM evidence into normalized ad records.

    No LLM inference occurs here. Product identity is deliberately left nullable
    until landing-page/creative enrichment is added in a later stage.
    """
    runtime = _latest_runtime(runtime_snapshots)
    gpt = runtime.get("gpt", {}) if isinstance(runtime, dict) else {}
    prebid = runtime.get("prebid", {}) if isinstance(runtime, dict) else {}
    slots = gpt.get("slots", []) if isinstance(gpt, dict) else []
    bids = prebid.get("bids", []) if isinstance(prebid, dict) else []

    dom_by_id = {
        str(signal.id): signal
        for signal in getattr(ad_detection, "signals", [])
        if signal.signal_type == "dom" and signal.id
    }
    evidence_by_id = {
        str(item.get("id")): item
        for item in visual_evidence
        if item.get("id")
    }

    records: dict[str, AdRecord] = {}

    for slot in slots if isinstance(slots, list) else []:
        if not isinstance(slot, dict):
            continue
        element_id = slot.get("element_id")
        slot_dom = dom_by_id.get(str(element_id)) if element_id else None
        placement = evidence_by_id.get(str(element_id)) if element_id else None
        response_info = slot.get("response_information") or {}
        hrefs, image_urls, video_urls = _dom_urls(slot_dom)
        record = AdRecord(
            ad_id=_ad_id(["gpt", element_id, slot.get("ad_unit_path")]),
            ad_type="gpt_slot",
            advertiser_id=response_info.get("advertiser_id"),
            ad_unit_path=slot.get("ad_unit_path"),
            element_id=element_id,
            sizes=slot.get("sizes") or [],
            ad_server="Google Ad Manager/Google Publisher Tag",
            adserver_targeting=slot.get("targeting") or None,
            destination_urls=hrefs,
            creative_image_urls=image_urls,
            creative_video_urls=video_urls,
            placement=_placement(slot_dom, placement),
            evidence=["runtime.gpt"] + (["dom"] if slot_dom else []) + (["visual"] if placement else []),
            confidence=0.80 + (0.10 if slot_dom else 0.0) + (0.05 if response_info else 0.0),
        )
        records[record.ad_id] = record

    for bid in bids if isinstance(bids, list) else []:
        if not isinstance(bid, dict):
            continue
        element_id = bid.get("ad_unit_code")
        slot = next(
            (s for s in slots if isinstance(s, dict) and s.get("element_id") == element_id),
            None,
        )
        slot_dom = dom_by_id.get(str(element_id)) if element_id else None
        placement = evidence_by_id.get(str(element_id)) if element_id else None
        hrefs, image_urls, video_urls = _dom_urls(slot_dom)
        record = AdRecord(
            ad_id=_ad_id(
                ["prebid", bid.get("ad_unit_code"), bid.get("bidder"), bid.get("ad_id"), bid.get("creative_id")]
            ),
            ad_type="prebid_bid",
            advertiser_name=bid.get("advertiser_name"),
            advertiser_id=bid.get("advertiser_id"),
            brand_name=bid.get("brand_name"),
            ad_unit_code=bid.get("ad_unit_code"),
            ad_unit_path=slot.get("ad_unit_path") if slot else None,
            element_id=element_id if slot_dom else None,
            sizes=[{"width": bid["width"], "height": bid["height"]}]
            if bid.get("width") and bid.get("height")
            else [],
            bidder=bid.get("bidder"),
            network_name=bid.get("network_name"),
            cpm=bid.get("cpm"),
            currency=bid.get("currency"),
            deal_id=bid.get("deal_id"),
            ad_server="Google Ad Manager/Prebid" if slot else None,
            adserver_targeting=bid.get("adserver_targeting") or None,
            destination_urls=hrefs,
            creative_image_urls=image_urls,
            creative_video_urls=video_urls,
            placement=_placement(slot_dom, placement),
            evidence=["runtime.prebid"]
            + (["runtime.gpt"] if slot else [])
            + (["dom"] if slot_dom else [])
            + (["visual"] if placement else []),
            confidence=0.85 + (0.05 if slot else 0.0) + (0.05 if slot_dom else 0.0),
        )
        records[record.ad_id] = record

    return list(records.values())
