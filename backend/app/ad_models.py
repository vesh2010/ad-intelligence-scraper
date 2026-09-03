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
    tag: str | None = None
    id: str | None = None
    class_name: str | None = None
    aria_label: str | None = None
    role: str | None = None
    title: str | None = None
    text: str | None = None
    width: int | None = None
    height: int | None = None
    x: int | None = None
    y: int | None = None
    viewport_x: int | None = None
    viewport_y: int | None = None
    iframe_src: str | None = None
    hrefs: list[str] = Field(default_factory=list)
    image_urls: list[str] = Field(default_factory=list)
    video_urls: list[str] = Field(default_factory=list)
    position_mode: str | None = None
    z_index: str | None = None
    dataset: dict[str, str] = Field(default_factory=dict)
    frame_index: int = 0
    frame_url: str | None = None


class AdDetectionResult(BaseModel):
    signals: list[AdSignal] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    network_signal_count: int = 0
    dom_signal_count: int = 0
