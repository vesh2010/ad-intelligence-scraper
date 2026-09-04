from __future__ import annotations

from collections import defaultdict
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse


AD_REQUEST_HOST_MARKERS = (
    "doubleclick.net",
    "googlesyndication.com",
    "googleadservices.com",
    "adnxs.com",
    "amazon-adsystem.com",
    "pubmatic.com",
    "rubiconproject.com",
    "criteo.com",
    "openx.net",
    "indexexchange.com",
    "33across.com",
    "sovrn.com",
    "sharethrough.com",
    "triplelift.com",
)

PARAM_ALIASES = {
    "ad_unit_path": ("iu", "ad_unit_path", "adunit", "ad_unit", "slotname"),
    "element_id": ("element_id", "slot", "slot_id", "div_id"),
    "creative_id": ("creative_id", "creativeid", "crid"),
    "line_item_id": ("line_item_id", "lineitem", "li"),
    "campaign_id": ("campaign_id", "campaignid", "cid"),
    "advertiser_id": ("advertiser_id", "advertiserid", "aid"),
    "advertiser_domain": ("adomain", "advertiser_domain", "advertiser"),
}


def _first(query: dict[str, list[str]], names: tuple[str, ...]) -> str | None:
    for name in names:
        values = query.get(name)
        if values and values[0].strip():
            return unquote(values[0].strip())
    return None


def _is_ad_request(item: dict[str, object]) -> bool:
    url = str(item.get("url") or "")
    parsed = urlparse(url)
    host = parsed.netloc.lower().split(":", 1)[0]
    path = parsed.path.lower()
    return any(host == marker or host.endswith("." + marker) for marker in AD_REQUEST_HOST_MARKERS) or any(
        marker in path for marker in ("/gampad/", "/pagead/", "/adservice", "/adserver", "/ads/")
    )


def resolve_ad_requests(network: list[dict[str, object]]) -> list[dict[str, Any]]:
    """Normalize ad-server/exchange requests into evidence usable for slot resolution.

    This identifies the request and any identifiers explicitly exposed in its URL;
    it never infers an advertiser from a URL alone.
    """
    resolved: list[dict[str, Any]] = []
    for item in network:
        if not _is_ad_request(item):
            continue
        url = str(item.get("url") or "")
        parsed = urlparse(url)
        query = parse_qs(parsed.query, keep_blank_values=False)
        row: dict[str, Any] = {
            "url": url,
            "host": parsed.netloc,
            "method": item.get("method"),
            "resource_type": item.get("resource_type"),
            "status": item.get("status"),
            "ad_technology": item.get("ad_technology"),
        }
        for field, aliases in PARAM_ALIASES.items():
            value = _first(query, aliases)
            if value:
                row[field] = value
        sizes = _first(query, ("sz", "size"))
        if sizes:
            row["size"] = sizes
        row["request_kind"] = "ad_request"
        resolved.append(row)
    return resolved


def match_ad_requests(
    slot: dict[str, Any], requests: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Match captured ad requests to a GPT slot using explicit observable IDs."""
    element_id = str(slot.get("element_id") or "").strip()
    ad_unit_path = str(slot.get("ad_unit_path") or "").strip()
    matches: list[dict[str, Any]] = []
    for request in requests:
        score = 0
        if element_id and request.get("element_id") == element_id:
            score += 100
        if ad_unit_path and request.get("ad_unit_path") == ad_unit_path:
            score += 90
        if score:
            matches.append({**request, "match_score": score})
    matches.sort(key=lambda row: (-int(row["match_score"]), str(row.get("url") or "")))
    return matches


def index_ad_requests(requests: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Build a deterministic index for request evidence keyed by explicit IDs."""
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for request in requests:
        for key in (request.get("element_id"), request.get("ad_unit_path")):
            if key:
                index[str(key)].append(request)
    return dict(index)


__all__ = ["resolve_ad_requests", "match_ad_requests", "index_ad_requests"]
