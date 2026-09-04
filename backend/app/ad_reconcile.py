from __future__ import annotations

import hashlib
from typing import Any

from .ad_records import AdRecord
from .ad_request_resolution import match_ad_requests, resolve_ad_requests
from .ad_type import classify_ad_type, is_above_fold
from .bid_models import BidEvidence


def _ad_id(parts: list[object]) -> str:
    raw = "|".join(str(p or "") for p in parts)
    return "ad_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _string_id(value: object) -> str | None:
    if value is None:
        return None
    return value if isinstance(value, str) else str(value)


def _latest_runtime(runtime_snapshots: list[dict[str, object]]) -> dict[str, Any]:
    if not runtime_snapshots:
        return {"gpt": {}, "prebid": {}}
    data = runtime_snapshots[-1].get("data", {})
    return data if isinstance(data, dict) else {"gpt": {}, "prebid": {}}


def _placement(slot_dom: Any, evidence: dict[str, object] | None) -> dict[str, object]:
    if slot_dom is None and evidence is None:
        return {}
    return {
        "frame_index": getattr(slot_dom, "frame_index", 0) if slot_dom else evidence.get("frame_index", 0),
        "frame_url": getattr(slot_dom, "frame_url", None) if slot_dom else evidence.get("frame_url"),
        "selector": getattr(slot_dom, "selector", None),
        "x": getattr(slot_dom, "x", None),
        "y": getattr(slot_dom, "y", None),
        "viewport_x": getattr(slot_dom, "viewport_x", None),
        "viewport_y": getattr(slot_dom, "viewport_y", None),
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


def _bid_evidence(raw: dict[str, Any]) -> BidEvidence:
    return BidEvidence(
        bidder=_string_id(raw.get("bidder")), ad_id=_string_id(raw.get("ad_id")), creative_id=_string_id(raw.get("creative_id")),
        width=raw.get("width"), height=raw.get("height"), size=raw.get("size"), cpm=raw.get("cpm"),
        currency=raw.get("currency"), deal_id=_string_id(raw.get("deal_id")), media_type=raw.get("media_type"),
        rendered=bool(raw.get("rendered")), advertiser_domains=[str(v) for v in (raw.get("advertiser_domains") or [])],
        advertiser_id=_string_id(raw.get("advertiser_id")), advertiser_name=_string_id(raw.get("advertiser_name")),
        brand_id=_string_id(raw.get("brand_id")), brand_name=_string_id(raw.get("brand_name")), network_id=_string_id(raw.get("network_id")),
        network_name=_string_id(raw.get("network_name")), demand_source=_string_id(raw.get("demand_source")),
        adserver_targeting=raw.get("adserver_targeting") if isinstance(raw.get("adserver_targeting"), dict) else None,
    )


def _signal_key(signal: Any) -> str:
    return f"{getattr(signal, 'frame_index', 0)}:{getattr(signal, 'id', None) or getattr(signal, 'selector', None)}"


def _evidence_key(item: dict[str, object]) -> str:
    return f"{int(item.get('frame_index', 0))}:{item.get('id') or item.get('selector')}"


def _resolution(slot: dict[str, Any], requests: list[dict[str, Any]]) -> dict[str, Any] | None:
    matches = match_ad_requests(slot, requests)
    if not matches:
        return None
    return {
        "request_kind": "ad_request",
        "match_method": "explicit_slot_id_or_ad_unit_path",
        "match_score": matches[0]["match_score"],
        "matched_requests": matches,
    }


def reconcile_ad_records(
    ad_detection: Any,
    runtime_snapshots: list[dict[str, object]],
    visual_evidence: list[dict[str, object]],
    network: list[dict[str, object]] | None = None,
) -> list[AdRecord]:
    """Create observable ad records and attach explicit ad-request evidence when available."""
    runtime = _latest_runtime(runtime_snapshots)
    gpt = runtime.get("gpt", {}) if isinstance(runtime, dict) else {}
    prebid = runtime.get("prebid", {}) if isinstance(runtime, dict) else {}
    slots = gpt.get("slots", []) if isinstance(gpt, dict) else []
    bids = prebid.get("bids", []) if isinstance(prebid, dict) else []
    winners = prebid.get("winners", []) if isinstance(prebid, dict) else []
    resolved_requests = resolve_ad_requests(network or [])

    dom_signals = [signal for signal in getattr(ad_detection, "signals", []) if signal.signal_type == "dom"]
    dom_by_key = {_signal_key(signal): signal for signal in dom_signals}
    evidence_by_key = {_evidence_key(item): item for item in visual_evidence if item.get("id") or item.get("selector")}

    records: list[AdRecord] = []
    covered_keys: set[str] = set()

    for slot in slots if isinstance(slots, list) else []:
        if not isinstance(slot, dict):
            continue
        element_id = _string_id(slot.get("element_id"))
        dom_key = f"0:{element_id}"
        slot_dom = dom_by_key.get(dom_key) if element_id else None
        placement = evidence_by_key.get(dom_key) if element_id else None
        response_info = slot.get("response_information") or {}
        slot_bids = [_bid_evidence(b) for b in bids if isinstance(b, dict) and _string_id(b.get("ad_unit_code")) == element_id]
        slot_winners = [_bid_evidence(b) for b in winners if isinstance(b, dict) and _string_id(b.get("ad_unit_code")) == element_id]
        winning = next((b for b in slot_winners if b.rendered), None) or (slot_winners[0] if slot_winners else None)
        hrefs, image_urls, video_urls = _dom_urls(slot_dom)
        ad_type, ad_format = classify_ad_type(
            width=getattr(slot_dom, "width", None) or (winning.width if winning else None),
            height=getattr(slot_dom, "height", None) or (winning.height if winning else None),
            position_mode=getattr(slot_dom, "position_mode", None), text=getattr(slot_dom, "text", None),
            has_video=bool(video_urls) or any(b.media_type in {"video", "outstream"} for b in slot_bids),
            ad_type_hint=winning.media_type if winning else None,
        )
        request_resolution = _resolution(slot, resolved_requests)
        evidence = ["runtime.gpt"] + (["runtime.prebid"] if slot_bids else []) + (["dom"] if slot_dom else []) + (["visual"] if placement else [])
        if request_resolution:
            evidence.append("network.ad_request")
        records.append(AdRecord(
            ad_id=_ad_id(["slot", element_id, slot.get("ad_unit_path")]),
            ad_type=ad_type if ad_type != "unknown" else "gpt_slot", ad_format=ad_format,
            advertiser_name=winning.advertiser_name if winning else None,
            advertiser_id=_string_id(response_info.get("advertiser_id")) or (winning.advertiser_id if winning else None),
            brand_name=winning.brand_name if winning else None, ad_unit_code=element_id,
            ad_unit_path=_string_id(slot.get("ad_unit_path")), element_id=element_id, sizes=slot.get("sizes") or [],
            bidder=winning.bidder if winning else None, network_name=winning.network_name if winning else None,
            ad_server="Google Ad Manager/Google Publisher Tag", cpm=winning.cpm if winning else None,
            currency=winning.currency if winning else None, deal_id=winning.deal_id if winning else None,
            adserver_targeting=slot.get("targeting") or (winning.adserver_targeting if winning else None),
            destination_urls=hrefs, creative_image_urls=image_urls, creative_video_urls=video_urls,
            bids=slot_bids, winning_bid=winning, placement=_placement(slot_dom, placement),
            above_fold=is_above_fold(y=getattr(slot_dom, "y", None), height=getattr(slot_dom, "height", None)) if slot_dom else None,
            evidence=evidence, request_resolution=request_resolution,
            confidence=min(0.98, 0.80 + (0.08 if slot_dom else 0.0) + (0.05 if response_info else 0.0) + (0.05 if winning else 0.0)),
        ))
        if element_id:
            covered_keys.add(dom_key)

    covered_bid_keys = {(record.ad_unit_code, record.winning_bid.ad_id if record.winning_bid else None) for record in records}
    for raw in winners if isinstance(winners, list) else []:
        if not isinstance(raw, dict):
            continue
        bid = _bid_evidence(raw)
        key = (_string_id(raw.get("ad_unit_code")), _string_id(raw.get("ad_id")))
        if key in covered_bid_keys:
            continue
        ad_type, ad_format = classify_ad_type(width=bid.width, height=bid.height, has_video=bid.media_type in {"video", "outstream"}, ad_type_hint=bid.media_type)
        request_resolution = _resolution(raw, resolved_requests)
        evidence = ["runtime.prebid"] + (["network.ad_request"] if request_resolution else [])
        records.append(AdRecord(
            ad_id=_ad_id(["winner", raw.get("ad_unit_code"), raw.get("bidder"), raw.get("ad_id"), raw.get("creative_id")]),
            ad_type=ad_type if ad_type != "unknown" else "prebid_winner", ad_format=ad_format,
            advertiser_name=bid.advertiser_name, advertiser_id=bid.advertiser_id, brand_name=bid.brand_name,
            ad_unit_code=_string_id(raw.get("ad_unit_code")), ad_unit_path=_string_id(raw.get("ad_unit_path")), element_id=_string_id(raw.get("element_id")),
            sizes=[{"width": bid.width, "height": bid.height}] if bid.width and bid.height else [], bidder=bid.bidder,
            network_name=bid.network_name, cpm=bid.cpm, currency=bid.currency, deal_id=bid.deal_id,
            adserver_targeting=bid.adserver_targeting, bids=[bid], winning_bid=bid, evidence=evidence,
            request_resolution=request_resolution, confidence=0.86 + (0.05 if request_resolution else 0.0),
        ))

    seen_dom_keys: set[str] = set()
    for signal in dom_signals:
        key = _signal_key(signal)
        if key in seen_dom_keys or key in covered_keys:
            continue
        seen_dom_keys.add(key)
        hrefs, image_urls, video_urls = _dom_urls(signal)
        evidence = evidence_by_key.get(key)
        ad_type, ad_format = classify_ad_type(width=signal.width, height=signal.height, position_mode=signal.position_mode,
                                               text=signal.text, has_video=bool(video_urls))
        records.append(AdRecord(
            ad_id=_ad_id(["dom", key, signal.selector]), ad_type="dom_candidate" if ad_type == "unknown" else ad_type,
            ad_format=ad_format, element_id=_string_id(signal.id),
            sizes=[{"width": signal.width, "height": signal.height}] if signal.width and signal.height else [],
            destination_urls=hrefs, creative_image_urls=image_urls, creative_video_urls=video_urls,
            placement=_placement(signal, evidence), above_fold=is_above_fold(y=signal.y, height=signal.height),
            evidence=["dom"] + (["visual"] if evidence else []), confidence=0.62 + (0.10 if evidence else 0.0),
        ))

    return records
