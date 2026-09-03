from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, HttpUrl

from ..ad_models import AdDetectionResult
from ..ad_records import AdRecord


class CrawlRequest(BaseModel):
    url: HttpUrl
    wait_ms: int = Field(default=2000, ge=0, le=30000)
    timeout_ms: int = Field(default=30000, ge=1000, le=120000)
    trace: bool = True


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
