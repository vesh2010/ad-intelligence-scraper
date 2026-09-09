from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urldefrag, urljoin, urlparse, urlunparse

import httpx

IGNORED_EXTENSIONS = {
    ".7z", ".avi", ".bin", ".css", ".csv", ".doc", ".docx", ".gif", ".gz",
    ".ico", ".jpeg", ".jpg", ".js", ".json", ".mp3", ".mp4", ".mpeg", ".pdf",
    ".png", ".rar", ".svg", ".tar", ".tgz", ".txt", ".webm", ".webp", ".woff",
    ".woff2", ".xls", ".xlsx", ".zip",
}


def normalize_url(url: str) -> str | None:
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    path = parsed.path or "/"
    if any(path.lower().endswith(ext) for ext in IGNORED_EXTENSIONS):
        return None
    path = path.rstrip("/") or "/"
    clean = parsed._replace(path=path, fragment="")
    return urlunparse(clean)


def same_site(url: str, root: str, allow_subdomains: bool = True) -> bool:
    left = (urlparse(url).hostname or "").lower().removeprefix("www.")
    right = (urlparse(root).hostname or "").lower().removeprefix("www.")
    if not left or not right:
        return False
    return left == right or (allow_subdomains and left.endswith("." + right))


def extract_links(page_url: str, hrefs: list[str], root_url: str, allow_subdomains: bool = True) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []
    for href in hrefs:
        absolute = normalize_url(urljoin(page_url, href))
        if not absolute or not same_site(absolute, root_url, allow_subdomains) or absolute in seen:
            continue
        seen.add(absolute)
        results.append(absolute)
    return results


def prioritize_urls(urls: list[str]) -> list[str]:
    """Prefer high-value publisher pages without excluding lower-priority pages."""
    def score(url: str) -> tuple[int, str]:
        path = urlparse(url).path.lower()
        if path in {"", "/"}:
            return (100, url)
        high_terms = ("news", "business", "market", "markets", "finance", "economy", "article", "story")
        medium_terms = ("category", "topic", "section", "latest", "video", "gallery")
        if any(term in path for term in high_terms):
            return (90, url)
        if any(term in path for term in medium_terms):
            return (60, url)
        return (30, url)
    return [url for _, url in sorted((score(url) for url in urls), reverse=True)]


class _HTMLDiscoveryParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []
        self.jsonld: list[str] = []
        self._in_jsonld = False
        self._jsonld_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value for key, value in attrs}
        tag = tag.lower()
        if tag in {"a", "area", "link"} and values.get("href"):
            self.urls.append(str(values["href"]))
        if tag in {"iframe", "frame", "script", "source"}:
            for key in ("src", "data-src", "data-url", "data-href"):
                if values.get(key):
                    self.urls.append(str(values[key]))
        if tag == "link" and str(values.get("rel") or "").lower() in {"canonical", "next", "prev"}:
            if values.get("href"):
                self.urls.append(str(values["href"]))
        if tag == "script" and str(values.get("type") or "").lower() == "application/ld+json":
            self._in_jsonld = True
            self._jsonld_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_jsonld:
            self._jsonld_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._in_jsonld:
            self.jsonld.append("".join(self._jsonld_parts))
            self._in_jsonld = False
            self._jsonld_parts = []


def _jsonld_urls(value: object) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in {"url", "mainentityofpage", "contenturl", "thumbnailurl", "sameas"}:
                if isinstance(item, str):
                    found.append(item)
                elif isinstance(item, list):
                    found.extend(str(x) for x in item if isinstance(x, str))
            found.extend(_jsonld_urls(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_jsonld_urls(item))
    return found


def extract_discovery_urls(page_url: str, html: str, root_url: str, allow_subdomains: bool = True) -> list[str]:
    parser = _HTMLDiscoveryParser()
    try:
        parser.feed(html)
    except Exception:
        pass
    hrefs = list(parser.urls)
    import json
    for blob in parser.jsonld:
        try:
            hrefs.extend(_jsonld_urls(json.loads(blob)))
        except (TypeError, ValueError):
            continue
    return extract_links(page_url, hrefs, root_url, allow_subdomains)


def classify_page(url: str, title: str = "", breadcrumb: str = "") -> str:
    path = urlparse(url).path.lower().strip("/")
    text = f"{path} {title.lower()} {breadcrumb.lower()}"
    if not path:
        return "homepage"
    if any(token in text for token in ("/video", "/videos", "video", "/watch")):
        return "video"
    if any(token in text for token in ("/gallery", "/photos", "gallery")):
        return "gallery"
    if any(token in text for token in ("/author", "/authors", "author")):
        return "author"
    if any(token in text for token in ("/tag", "/tags", "tag")):
        return "tag"
    if any(token in text for token in ("/search", "?q=", "?query=")):
        return "search"
    if any(token in text for token in ("/category", "/categories", "category")):
        return "category"
    if any(token in text for token in ("/topic", "/topics", "topic")):
        return "topic"
    if any(token in text for token in ("/section", "/sections", "section")):
        return "section"
    if any(token in text for token in ("/article", "/story", "article", "story")):
        return "article"
    if any(token in text for token in ("page=", "/page/", "?p=")):
        return "pagination"
    return "other"


def infer_section(url: str, root_url: str) -> str:
    path = urlparse(url).path.strip("/")
    if not path:
        return "home"
    return path.split("/", 1)[0] or "home"


@dataclass
class ManifestEntry:
    url: str
    normalized_url: str
    source_url: str | None
    discovery_method: str
    depth: int
    section: str
    page_type: str
    status: str = "discovered"
    last_error: str | None = None
    desktop_checked: bool = False
    mobile_checked: bool = False
    http_status: int | None = None
    ad_signal_count: int = 0
    normalized_ad_count: int = 0
    run_id: str | None = None

    def as_dict(self) -> dict[str, object]:
        return self.__dict__.copy()


@dataclass
class DiscoveryInventory:
    root_url: str
    max_discovered_urls: int = 5000
    sitemap_urls_discovered: list[str] = field(default_factory=list)
    sitemap_urls_crawled: list[str] = field(default_factory=list)
    sitemap_urls_skipped: list[dict[str, str]] = field(default_factory=list)
    manifest: dict[str, ManifestEntry] = field(default_factory=dict)

    @property
    def urls_found_only_in_sitemap(self) -> list[str]:
        sitemap = set(self.sitemap_urls_discovered)
        page_links = {item.url for item in self.manifest.values() if item.discovery_method not in {"sitemap", "robots"}}
        return sorted(sitemap - page_links)

    @property
    def urls_found_only_through_page_links(self) -> list[str]:
        sitemap = set(self.sitemap_urls_discovered)
        return sorted(item.url for item in self.manifest.values() if item.discovery_method in {"page_link", "canonical", "jsonld", "iframe", "pagination"} and item.url not in sitemap)

    def add(self, url: str, source_url: str | None, method: str, depth: int) -> bool:
        normalized = normalize_url(url)
        if not normalized or not same_site(normalized, self.root_url) or normalized in self.manifest:
            return False
        if len(self.manifest) >= self.max_discovered_urls:
            return False
        self.manifest[normalized] = ManifestEntry(
            url=normalized,
            normalized_url=normalized,
            source_url=source_url,
            discovery_method=method,
            depth=depth,
            section=infer_section(normalized, self.root_url),
            page_type=classify_page(normalized),
        )
        return True

    def to_dict(self) -> dict[str, object]:
        return {
            "root_url": self.root_url,
            "max_discovered_urls": self.max_discovered_urls,
            "sitemap_urls_discovered": self.sitemap_urls_discovered,
            "sitemap_urls_crawled": self.sitemap_urls_crawled,
            "sitemap_urls_skipped": self.sitemap_urls_skipped,
            "urls_found_only_in_sitemap": self.urls_found_only_in_sitemap,
            "urls_found_only_through_page_links": self.urls_found_only_through_page_links,
            "manifest": [item.as_dict() for item in self.manifest.values()],
        }


async def discover_sitemaps(root_url: str, max_urls: int = 5000, timeout_ms: int = 15000) -> tuple[list[str], list[dict[str, str]]]:
    parsed = urlparse(root_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    candidates: list[str] = []
    skipped: list[dict[str, str]] = []
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout_ms / 1000, headers={"User-Agent": "AdIntelligenceScraper/1.0 (+sitemap discovery)"}) as client:
        robots_url = urljoin(origin + "/", "/robots.txt")
        try:
            response = await client.get(robots_url)
            for line in response.text.splitlines():
                if line.lower().startswith("sitemap:"):
                    candidates.append(line.split(":", 1)[1].strip())
        except Exception as exc:
            skipped.append({"url": robots_url, "error": str(exc)})
        candidates.extend([urljoin(origin + "/", "/sitemap.xml"), urljoin(origin + "/", "/sitemap_index.xml")])
        queue = deque(dict.fromkeys(candidates))
        discovered: list[str] = []
        seen_sitemaps: set[str] = set()
        while queue and len(discovered) < max_urls:
            sitemap_url = queue.popleft()
            sitemap_url = urldefrag(sitemap_url).url
            if sitemap_url in seen_sitemaps:
                continue
            seen_sitemaps.add(sitemap_url)
            try:
                response = await client.get(sitemap_url)
                if response.status_code >= 400:
                    skipped.append({"url": sitemap_url, "error": f"HTTP {response.status_code}"})
                    continue
                text = response.text
                import re
                locs = re.findall(r"<loc>\s*(.*?)\s*</loc>", text, flags=re.I | re.S)
                if "<sitemapindex" in text[:1000].lower() or "sitemap" in sitemap_url.lower() and any("sitemap" in loc.lower() for loc in locs):
                    for loc in locs:
                        if loc not in seen_sitemaps:
                            queue.append(loc.strip())
                    continue
                for loc in locs:
                    normalized = normalize_url(loc.strip())
                    if normalized and same_site(normalized, root_url):
                        discovered.append(normalized)
                        if len(discovered) >= max_urls:
                            break
                if sitemap_url not in discovered:
                    pass
            except Exception as exc:
                skipped.append({"url": sitemap_url, "error": str(exc)})
        return list(dict.fromkeys(discovered))[:max_urls], skipped


class URLQueue:
    def __init__(self, root_url: str, max_pages: int = 100, max_discovered_urls: int = 5000) -> None:
        normalized = normalize_url(root_url)
        if not normalized:
            raise ValueError("Invalid root URL")
        self.root_url = normalized
        self.max_pages = max_pages
        self.max_discovered_urls = max_discovered_urls
        self._queue: deque[tuple[int, str]] = deque([(0, normalized)])
        self._seen = {normalized}
        self._manifest: dict[str, dict[str, object]] = {normalized: {"url": normalized, "source_url": None, "discovery_method": "homepage", "depth": 0}}

    def add_links(self, page_url: str, hrefs: list[str], depth: int) -> int:
        if len(self._seen) >= self.max_discovered_urls:
            return 0
        candidates = prioritize_urls(extract_links(page_url, hrefs, self.root_url))
        added = 0
        for url in candidates:
            if len(self._seen) >= self.max_discovered_urls:
                break
            if url in self._seen:
                continue
            self._seen.add(url)
            self._manifest[url] = {"url": url, "source_url": page_url, "discovery_method": "page_link", "depth": depth + 1}
            self._queue.append((depth + 1, url))
            added += 1
        return added

    def seed_sitemap_urls(self, urls: list[str], depth: int = 1) -> int:
        added = 0
        for url in prioritize_urls(urls):
            if len(self._seen) >= self.max_discovered_urls or url in self._seen:
                continue
            normalized = normalize_url(url)
            if not normalized or not same_site(normalized, self.root_url):
                continue
            self._seen.add(normalized)
            self._manifest[normalized] = {"url": normalized, "source_url": self.root_url, "discovery_method": "sitemap", "depth": depth}
            self._queue.append((depth, normalized))
            added += 1
        return added

    def pop(self) -> tuple[int, str] | None:
        if not self._queue:
            return None
        return self._queue.popleft()

    def __len__(self) -> int:
        return len(self._queue)

    @property
    def seen_count(self) -> int:
        return len(self._seen)

    @property
    def manifest(self) -> dict[str, dict[str, object]]:
        return self._manifest
