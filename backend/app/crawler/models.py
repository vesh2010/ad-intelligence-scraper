from __future__ import annotations

from typing import Any, Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, Field, HttpUrl, field_validator

from ..ad_models import AdDetectionResult
from ..ad_records import AdRecord


def _prefer_https(value: object) -> object:
    """Prefer HTTPS for public hostnames when callers supply an HTTP URL.

    Some CDN/WAF front doors reject plain HTTP before issuing their normal
    redirect. This makes a crawl fail with an empty page even though the same
    public site is reachable over HTTPS. Local/private HTTP targets remain
    untouched so development and internal test fixtures continue to work.
    """
    if not isinstance(value, str):
        return value
    parsed = urlsplit(value)
    host = (parsed.hostname or "").lower()
    if parsed.scheme == "http" and host not in {"localhost", "127.0.0.1", "0.0.0.0", "::1"} and not host.endswith(".local"):
        return urlunsplit(("https", parsed.netloc, parsed.path, parsed.query, parsed.fragment))
    return value


class CrawlRequest(BaseModel):
    url: HttpUrl
    wait_ms: int = Field(default=2000, ge=0, le=30000)
    timeout_ms: int = Field(default=30000, ge=1000, le=120000)
    trace: bool = True
    include_ads_txt: bool = True
    enrich_landing_pages: bool = False
    max_landing_destinations: int = Field(default=10, ge=1, le=25)
    device: Literal["desktop", "mobile"] = "desktop"

    @field_validator("url", mode="before")
    @classmethod
    def prefer_https(cls, value: object) -> object:
        return _prefer_https(value)


class CrawlResult(BaseModel):
    run_id: str
    requested_url: str
    final_url: str
    status: int | None
    title: str
    elapsed_ms: int
    dimensions: dict[str, int]
    counts: dict[str, int]
    metadata: dict[str, str | None]
    redirects: list[dict[str, str | int | None]]
    network: list[dict[str, object]]
    console_errors: list[str]
    page_errors: list[str]
    frames: list[str]
    artifacts: dict[str, str]
    ad_detection: AdDetectionResult | None = None
    runtime_ads: dict[str, object] | None = None
    visual_evidence: list[dict[str, object]] = Field(default_factory=list)
    ad_records: list[AdRecord] = Field(default_factory=list)
    ads_txt: dict[str, Any] | None = None
    device: Literal["desktop", "mobile"] = "desktop"


class SiteCrawlRequest(BaseModel):
    url: HttpUrl
    max_pages: int = Field(default=10, ge=1, le=100)
    max_depth: int = Field(default=2, ge=0, le=10)
    wait_ms: int = Field(default=1500, ge=0, le=30000)
    timeout_ms: int = Field(default=30000, ge=1000, le=120000)
    enrich_landing_pages: bool = False
    max_landing_destinations: int = Field(default=10, ge=1, le=25)

    @field_validator("url", mode="before")
    @classmethod
    def prefer_https(cls, value: object) -> object:
        return _prefer_https(value)


class SiteCrawlResult(BaseModel):
    root_url: str
    max_pages: int
    max_depth: int
    pages_crawled: int
    pages_failed: int
    pages_discovered: int
    ads_detected: int
    normalized_ad_records: int
    pages: list[CrawlResult]
    failures: list[dict[str, str]]
