from __future__ import annotations

from pydantic import BaseModel, Field


class AdSignal(BaseModel):
    signal_type: str
    confidence: str
    url: str | None = None
    host: str | None = None
    method: str | None = None
    resource_type: str | None = None
    status: int | None = None
    ad_technology: str | None = None
    selector: str | None = None
    id: str | None = None
    class_name: str | None = None
    text: str | None = None


class AdDetectionResult(BaseModel):
    signals: list[AdSignal] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    network_signal_count: int = 0
    dom_signal_count: int = 0
