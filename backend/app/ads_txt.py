from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx


def parse_ads_txt(text: str) -> dict[str, Any]:
    variables: dict[str, str] = {}
    entries: list[dict[str, str | None]] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line and "," not in line.split("=", 1)[0]:
            key, value = line.split("=", 1)
            variables[key.strip().upper()] = value.strip()
            continue

        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 3:
            continue
        entries.append(
            {
                "ad_system": parts[0] or None,
                "seller_id": parts[1] or None,
                "relationship": parts[2].lower() or None,
                "tag_id": parts[3] if len(parts) > 3 and parts[3] else None,
            }
        )

    return {"variables": variables, "entries": entries, "entry_count": len(entries)}


async def fetch_ads_txt(site_url: str, timeout_s: float = 10.0) -> dict[str, Any]:
    """Fetch and parse a publisher's public ads.txt declaration.

    ads.txt describes authorized sellers; it does not prove that a seller served
    the particular impression observed by the browser.
    """
    parsed = urlparse(site_url)
    if not parsed.hostname:
        return {"found": False, "error": "missing hostname"}

    hosts = [parsed.hostname]
    if parsed.hostname.startswith("www."):
        hosts.append(parsed.hostname.removeprefix("www."))
    else:
        hosts.append(f"www.{parsed.hostname}")

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=timeout_s,
        headers={"User-Agent": "AdIntelligenceScraper/0.1 (+public ads.txt research)"},
    ) as client:
        last_error: str | None = None
        for host in dict.fromkeys(hosts):
            url = f"https://{host}/ads.txt"
            try:
                response = await client.get(url)
            except httpx.HTTPError as exc:
                last_error = str(exc)
                continue

            if response.status_code != 200 or not response.text.strip():
                last_error = f"HTTP {response.status_code} from {response.url}"
                continue

            parsed_ads = parse_ads_txt(response.text)
            return {
                "found": True,
                "requested_url": url,
                "final_url": str(response.url),
                "status": response.status_code,
                **parsed_ads,
                "raw_text": response.text,
            }

    return {"found": False, "error": last_error or "ads.txt not found"}
