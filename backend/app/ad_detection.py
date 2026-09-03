from __future__ import annotations

import re
from urllib.parse import urlparse


# Keep generic DOM markers token-aware. A raw substring check for "ad" produces
# unacceptable false positives (for example, "header").
DOM_MARKER_RE = re.compile(
    r"(?:^|[\s_:\-/])(ads?|advert(?:isement|ising)?|sponsored|promoted|adsbygoogle)(?:$|[\s_:\-/])",
    re.IGNORECASE,
)

KNOWN_AD_TECH = {
    "googlesyndication": "Google AdSense/Publisher",
    "doubleclick": "Google Ad Manager/DoubleClick",
    "prebid": "Prebid.js",
    "amazon-adsystem": "Amazon Publisher Services",
    "adnxs": "Microsoft/Xandr",
    "criteo": "Criteo",
    "rubiconproject": "Magnite/Rubicon",
    "pubmatic": "PubMatic",
    "openx": "OpenX",
    "33across": "33Across",
    "indexexchange": "Index Exchange",
    "sovrn": "Sovrn",
    "sharethrough": "Sharethrough",
    "triplelift": "TripleLift",
}

NETWORK_PATH_MARKERS = (
    "/ads/",
    "/ad/",
    "/gampad/",
    "/pagead/",
    "/adserver",
    "/adservice",
    "/adsystem/",
    "advertising",
)


def _is_dom_ad_related(value: str) -> bool:
    return bool(DOM_MARKER_RE.search(value.strip()))


def _technology(value: str) -> str | None:
    lower = value.lower()
    for marker, name in KNOWN_AD_TECH.items():
        if marker in lower:
            return name
    return None


def _is_network_ad_related(url: str) -> bool:
    if _technology(url):
        return True
    lower = url.lower()
    return any(marker in lower for marker in NETWORK_PATH_MARKERS)


def classify_network_requests(network: list[dict[str, object]]) -> list[dict[str, object]]:
    """Create conservative ad-tech signals from captured network metadata.

    A signal means that a request looks ad-related. It does not prove that the
    request resulted in a paid impression or identify the final advertiser.
    """
    records: list[dict[str, object]] = []
    for item in network:
        url = str(item.get("url", ""))
        if not _is_network_ad_related(url):
            continue
        records.append(
            {
                "signal_type": "network",
                "url": url,
                "host": urlparse(url).netloc,
                "method": item.get("method"),
                "resource_type": item.get("resource_type"),
                "status": item.get("status"),
                "ad_technology": _technology(url),
                "confidence": "medium",
            }
        )
    return records


def classify_dom_candidates(candidates: list[dict[str, object]]) -> list[dict[str, object]]:
    """Score browser-supplied DOM elements using conservative ad markers."""
    results: list[dict[str, object]] = []
    for candidate in candidates:
        values = [candidate.get(k) for k in ("id", "class_name", "aria_label", "role", "title", "text")]
        if not any(_is_dom_ad_related(str(value or "")) for value in values):
            continue
        results.append({**candidate, "signal_type": "dom", "confidence": "medium"})
    return results
