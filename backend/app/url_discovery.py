from __future__ import annotations

from collections import deque
from urllib.parse import urldefrag, urljoin, urlparse, urlunparse


IGNORED_EXTENSIONS = {
    ".7z", ".avi", ".bin", ".css", ".csv", ".doc", ".docx", ".gif", ".gz",
    ".ico", ".jpeg", ".jpg", ".js", ".json", ".mp3", ".mp4", ".mpeg", ".pdf",
    ".png", ".rar", ".svg", ".tar", ".tgz", ".txt", ".webm", ".webp", ".woff",
    ".woff2", ".xls", ".xlsx", ".xml", ".zip",
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


def same_site(url: str, root: str) -> bool:
    left = (urlparse(url).hostname or "").lower().removeprefix("www.")
    right = (urlparse(root).hostname or "").lower().removeprefix("www.")
    return bool(left and right and (left == right or left.endswith("." + right)))


def extract_links(page_url: str, hrefs: list[str], root_url: str) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []
    for href in hrefs:
        absolute = normalize_url(urljoin(page_url, href))
        if not absolute or not same_site(absolute, root_url) or absolute in seen:
            continue
        seen.add(absolute)
        results.append(absolute)
    return results


def prioritize_urls(urls: list[str]) -> list[str]:
    """Prefer pages likely to contain publisher inventory before low-value URLs."""
    def score(url: str) -> tuple[int, str]:
        path = urlparse(url).path.lower()
        if path in {"", "/"}:
            return (100, url)
        high_terms = ("news", "business", "market", "markets", "finance", "economy", "article", "story")
        medium_terms = ("category", "topic", "section", "latest")
        if any(term in path for term in high_terms):
            return (90, url)
        if any(term in path for term in medium_terms):
            return (60, url)
        return (30, url)

    return [url for _, url in sorted((score(url) for url in urls), reverse=True)]


class URLQueue:
    def __init__(self, root_url: str, max_pages: int = 100) -> None:
        normalized = normalize_url(root_url)
        if not normalized:
            raise ValueError("Invalid root URL")
        self.root_url = normalized
        self.max_pages = max_pages
        self._queue: deque[tuple[int, str]] = deque([(0, normalized)])
        self._seen = {normalized}

    def add_links(self, page_url: str, hrefs: list[str], depth: int) -> int:
        if len(self._seen) >= self.max_pages:
            return 0
        candidates = prioritize_urls(extract_links(page_url, hrefs, self.root_url))
        added = 0
        for url in candidates:
            if len(self._seen) >= self.max_pages:
                break
            if url in self._seen:
                continue
            self._seen.add(url)
            self._queue.append((depth + 1, url))
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
