from __future__ import annotations

import hashlib
import ipaddress
import socket
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .media_intelligence import inspect_media


MAX_ASSET_BYTES = 4_000_000
MAX_TOTAL_BYTES = 20_000_000
DEFAULT_MAX_ASSETS = 30
_ALLOWED_PREFIXES = ("image/", "video/", "audio/")


def _public_destination(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return False
    host = parsed.hostname.lower().rstrip(".")
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return True
    return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved)


async def _resolves_public(url: str) -> bool:
    parsed = urlparse(url)
    if not parsed.hostname:
        return False
    try:
        infos = await __import__("asyncio").to_thread(
            socket.getaddrinfo,
            parsed.hostname,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except OSError:
        return False
    addresses = {info[4][0] for info in infos if info and info[4]}
    if not addresses:
        return False
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            return False
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            return False
    return True


async def _safe_asset_url(url: str) -> bool:
    return _public_destination(url) and await _resolves_public(url)


def _extension(content_type: str, url: str) -> str:
    mapping = {
        "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif", "image/avif": ".avif", "image/svg+xml": ".svg",
        "video/mp4": ".mp4", "video/webm": ".webm", "video/ogg": ".ogv",
        "audio/mpeg": ".mp3", "audio/mp3": ".mp3", "audio/mp4": ".m4a", "audio/aac": ".aac", "audio/ogg": ".ogg", "audio/wav": ".wav", "audio/x-wav": ".wav", "audio/webm": ".weba",
    }
    mime = content_type.split(";", 1)[0].strip().lower()
    if mime in mapping:
        return mapping[mime]
    suffix = Path(urlparse(url).path).suffix.lower()
    return suffix if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".svg", ".mp4", ".webm", ".ogv", ".mp3", ".m4a", ".aac", ".ogg", ".wav", ".weba"} else ".bin"


async def capture_creative_assets(
    asset_urls: list[str],
    output_dir: str | Path,
    max_assets: int = DEFAULT_MAX_ASSETS,
    max_asset_bytes: int = MAX_ASSET_BYTES,
    max_total_bytes: int = MAX_TOTAL_BYTES,
    timeout_s: float = 8.0,
) -> list[dict[str, object]]:
    """Download bounded public image/video/audio creative assets and inspect media streams."""
    unique: list[str] = []
    seen: set[str] = set()
    for url in asset_urls:
        if not isinstance(url, str) or url in seen:
            continue
        if await _safe_asset_url(url):
            seen.add(url)
            unique.append(url)
        if len(unique) >= max_assets:
            break

    asset_dir = Path(output_dir) / "creative_assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []
    total = 0

    async with httpx.AsyncClient(
        follow_redirects=False,
        timeout=timeout_s,
        headers={"User-Agent": "AdIntelligenceScraper/0.1 (+creative asset research)"},
    ) as client:
        for url in unique:
            try:
                current = url
                response: httpx.Response | None = None
                for _ in range(5):
                    if not await _safe_asset_url(current):
                        raise ValueError("redirected to a non-public destination")
                    response = await client.get(current)
                    if response.status_code not in {301, 302, 303, 307, 308}:
                        break
                    location = response.headers.get("location")
                    if not location:
                        break
                    current = str(httpx.URL(current).join(location))
                if response is None:
                    raise ValueError("no response")
                if not response.is_success:
                    raise ValueError(f"HTTP {response.status_code}")

                content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                if not any(content_type.startswith(prefix) for prefix in _ALLOWED_PREFIXES):
                    raise ValueError(f"unsupported content type: {content_type or 'unknown'}")
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > max_asset_bytes:
                    raise ValueError("asset exceeds size limit")
                body = response.content
                if len(body) > max_asset_bytes:
                    raise ValueError("asset exceeds size limit")
                if total + len(body) > max_total_bytes:
                    results.append({"url": url, "error": "total asset budget exhausted"})
                    break

                digest = hashlib.sha256(body).hexdigest()
                filename = f"{digest[:20]}{_extension(content_type, current)}"
                path = asset_dir / filename
                if not path.exists():
                    path.write_bytes(body)
                total += len(body)
                item: dict[str, object] = {
                    "url": url, "final_url": current, "mime_type": content_type,
                    "asset_kind": content_type.split("/", 1)[0], "bytes": len(body),
                    "sha256": digest, "path": str(path),
                }
                if content_type.startswith(("video/", "audio/")):
                    item["media"] = inspect_media(path)
                results.append(item)
            except (httpx.HTTPError, ValueError, OSError) as exc:
                results.append({"url": url, "error": str(exc)})

    return results
