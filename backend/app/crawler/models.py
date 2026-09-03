from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl


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
