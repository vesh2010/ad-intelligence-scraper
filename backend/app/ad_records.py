from __future__ import annotations

from pydantic import BaseModel, Field


class AdRecord(BaseModel):
    ad_id: str
    ad_type: str
    advertiser_name: str | None = None
    advertiser_id: str | None = None
    brand_name: str | None = None
    product_name: str | None = None
    ad_unit_code: str | None = None
    ad_unit_path: str | None = None
    element_id: str | None = None
    sizes: list[dict[str, int]] = Field(default_factory=list)
    bidder: str | None = None
    network_name: str | None = None
    ad_server: str | None = None
    cpm: float | None = None
    currency: str | None = None
    deal_id: str | None = None
    placement: dict[str, object] | None = None
    evidence: list[str] = Field(default_factory=list)
    confidence: float = 0.0
