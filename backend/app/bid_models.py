from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class BidEvidence(BaseModel):
    bidder: str | None = None
    ad_id: str | None = None
    creative_id: str | None = None
    width: int | None = None
    height: int | None = None
    size: str | None = None
    cpm: float | None = None
    currency: str | None = None
    deal_id: str | None = None
    media_type: str | None = None
    rendered: bool = False
    advertiser_domains: list[str] = Field(default_factory=list)
    advertiser_id: str | None = None
    advertiser_name: str | None = None
    brand_id: str | None = None
    brand_name: str | None = None
    network_id: str | None = None
    network_name: str | None = None
    demand_source: str | None = None
    adserver_targeting: dict[str, Any] | None = None

    @field_validator(
        "ad_id", "creative_id", "deal_id", "advertiser_id", "brand_id", "network_id",
        mode="before",
    )
    @classmethod
    def _coerce_identifiers(cls, value: object) -> object:
        if value is None or isinstance(value, str):
            return value
        return str(value)
