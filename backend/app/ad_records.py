from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .bid_models import BidEvidence


class AdRecord(BaseModel):
    """One observable ad/slot record, with auction bids retained as evidence."""

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
    adserver_targeting: dict[str, object] | None = None
    destination_urls: list[str] = Field(default_factory=list)
    creative_image_urls: list[str] = Field(default_factory=list)
    creative_video_urls: list[str] = Field(default_factory=list)
    landing_page: dict[str, Any] | None = None
    bids: list[BidEvidence] = Field(default_factory=list)
    winning_bid: BidEvidence | None = None
    placement: dict[str, object] | None = None
    evidence: list[str] = Field(default_factory=list)
    confidence: float = 0.0
