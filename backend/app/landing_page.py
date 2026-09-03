from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

import httpx


class _MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.in_title = False
        self.meta: dict[tuple[str, str], str] = {}
        self.canonical: str | None = None
        self.json_ld: list[str] = []
        self.in_json_ld = False
        self.json_ld_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {k.lower(): v or "" for k, v in attrs}
        lower = tag.lower()
        if lower == "title":
            self.in_title = True
        elif lower == "meta":
            name = attrs_dict.get("name", "").strip().lower()
            prop = attrs_dict.get("property", "").strip().lower()
            content = attrs_dict.get("content", "").strip()
            if content and (name or prop):
                self.meta[("name" if name else "property", name or prop)] = content
        elif lower == "link" and attrs_dict.get("rel", "").lower() == "canonical":
            self.canonical = attrs_dict.get("href") or None
        elif lower == "script" and attrs_dict.get("type", "").lower() == "application/ld+json":
            self.in_json_ld = True
            self.json_ld_parts = []

    def handle_endtag(self, tag: str) -> None:
        lower = tag.lower()
        if lower == "title":
            self.in_title = False
        elif lower == "script" and self.in_json_ld:
            text = "".join(self.json_ld_parts).strip()
            if text:
                self.json_ld.append(text)
            self.in_json_ld = False
            self.json_ld_parts = []

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)
        if self.in_json_ld:
            self.json_ld_parts.append(data)


def _meta(parser: _MetadataParser, key: str) -> str | None:
    return parser.meta.get(("name", key)) or parser.meta.get(("property", key))


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return [value] if value is not None else []


def _find_products(value: Any) -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    for node in _as_list(value):
        if isinstance(node, dict):
            node_type = node.get("@type") or node.get("type")
            types = {str(t).lower() for t in _as_list(node_type)}
            if "product" in types:
                products.append(node)
            products.extend(_find_products(node.get("@graph")))
            products.extend(_find_products(node.get("item")))
            products.extend(_find_products(node.get("mainEntity")))
            products.extend(_find_products(node.get("mainEntityOfPage")))
        elif isinstance(node, list):
            products.extend(_find_products(node))
    return products


def _brand_name(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        name = value.get("name")
        return str(name).strip() if name else None
    return None


def _first_product(json_ld: list[str]) -> dict[str, Any] | None:
    for raw in json_ld:
        try:
            parsed = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        products = _find_products(parsed)
        if products:
            return products[0]
    return None


async def enrich_landing_page(url: str, timeout_s: float = 8.0, max_bytes: int = 2_000_000) -> dict[str, Any]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return {"found": False, "requested_url": url, "error": "unsupported URL"}

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout_s,
            headers={"User-Agent": "AdIntelligenceScraper/0.1 (+landing metadata research)"},
        ) as client:
            async with client.stream("GET", url) as response:
                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > max_bytes:
                        remaining = max_bytes - (total - len(chunk))
                        if remaining > 0:
                            chunks.append(chunk[:remaining])
                        break
                    chunks.append(chunk)
                body = b"".join(chunks)
                content_type = response.headers.get("content-type", "")
                if "html" not in content_type.lower():
                    return {
                        "found": False,
                        "requested_url": url,
                        "final_url": str(response.url),
                        "status": response.status_code,
                        "error": f"non-HTML content: {content_type or 'unknown'}",
                    }
                encoding = response.encoding or "utf-8"
                text = body.decode(encoding, errors="replace")

        parser = _MetadataParser()
        parser.feed(text)
        product = _first_product(parser.json_ld)
        title = re.sub(r"\s+", " ", "".join(parser.title_parts)).strip() or None
        result: dict[str, Any] = {
            "found": response.is_success,
            "requested_url": url,
            "final_url": str(response.url),
            "status": response.status_code,
            "title": title,
            "canonical": parser.canonical,
            "description": _meta(parser, "description"),
            "og_title": _meta(parser, "og:title"),
            "og_description": _meta(parser, "og:description"),
            "og_image": _meta(parser, "og:image"),
            "product": None,
            "source": "landing_page",
        }
        if product:
            offers = _as_list(product.get("offers"))
            offer = offers[0] if offers and isinstance(offers[0], dict) else {}
            result["product"] = {
                "name": product.get("name"),
                "brand": _brand_name(product.get("brand")),
                "category": product.get("category"),
                "sku": product.get("sku") or product.get("mpn") or product.get("gtin"),
                "price": offer.get("price") if isinstance(offer, dict) else None,
                "currency": offer.get("priceCurrency") if isinstance(offer, dict) else None,
                "availability": offer.get("availability") if isinstance(offer, dict) else None,
                "image": _as_list(product.get("image"))[0] if product.get("image") else None,
                "description": product.get("description"),
            }
        return result
    except (httpx.HTTPError, UnicodeError) as exc:
        return {"found": False, "requested_url": url, "error": str(exc)}
