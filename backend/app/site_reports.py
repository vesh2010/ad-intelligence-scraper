from __future__ import annotations

import hashlib
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, Response

from .report_html import render_html_report
from .report_intelligence import build_report_intelligence
from .report_pdf import render_pdf_report


def _campaign_key(record: dict[str, Any]) -> str:
    """Create the same kind of stable observable identity used by persisted snapshots."""
    values = [
        record.get("brand_name"),
        record.get("advertiser_name"),
        record.get("product_name"),
        record.get("landing_page_url"),
        *(record.get("destination_urls") or []),
    ]
    normalized = [str(value).strip().lower().rstrip("/") for value in values if value]
    if not normalized:
        normalized = [
            str(record.get("ad_type") or ""),
            str(record.get("ad_format") or ""),
            str(record.get("ad_unit_code") or ""),
            str(record.get("element_id") or ""),
        ]
    raw = "|".join(value for value in normalized if value)
    return "campaign_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20] if raw else ""


def _publisher_domain(root_url: Any) -> str:
    try:
        return (urlparse(str(root_url or "")).hostname or "").lower().removeprefix("www.")
    except ValueError:
        return ""


def _observations(payload: dict[str, Any]) -> list[dict[str, Any]]:
    pages = payload.get("pages")
    if not isinstance(pages, list):
        raise HTTPException(status_code=422, detail="pages must be a list")
    publisher_domain = _publisher_domain(payload.get("root_url"))
    rows: list[dict[str, Any]] = []
    for page in pages:
        if not isinstance(page, dict):
            raise HTTPException(status_code=422, detail="each page must be an object")
        records = page.get("ad_records", [])
        if not isinstance(records, list) or not all(isinstance(record, dict) for record in records):
            raise HTTPException(status_code=422, detail="page ad_records must be a list of objects")
        for record in records:
            row = dict(record)
            row.setdefault("device", page.get("device", "desktop"))
            row.setdefault("target_url", page.get("final_url") or page.get("url"))
            row.setdefault("run_id", page.get("run_id"))
            row.setdefault("publisher_domain", publisher_domain)
            if not row.get("campaign_key") and not row.get("ad_id"):
                row["campaign_key"] = _campaign_key(row)
            rows.append(row)
    return rows


def _title(payload: dict[str, Any], title: Any) -> str:
    if title is None:
        title = f"Ad Intelligence — {payload.get('root_url') or 'Site crawl'}"
    if not isinstance(title, str) or not title.strip():
        raise HTTPException(status_code=422, detail="title must be a non-empty string")
    return title.strip()


def build_site_report_router() -> APIRouter:
    router = APIRouter(prefix="/api/site-crawl", tags=["reports"])

    @router.post("/report.html", response_class=HTMLResponse)
    async def site_report_html(payload: dict[str, Any]) -> HTMLResponse:
        return HTMLResponse(render_html_report(_observations(payload), title=_title(payload, payload.get("title"))))

    @router.post("/report.pdf")
    async def site_report_pdf(payload: dict[str, Any]) -> Response:
        pdf = render_pdf_report(_observations(payload), title=_title(payload, payload.get("title")))
        return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": 'inline; filename="ad-intelligence-site-report.pdf"'})

    @router.post("/intelligence")
    async def site_intelligence(payload: dict[str, Any]) -> dict[str, Any]:
        return build_report_intelligence(_observations(payload))

    return router


__all__ = ["build_site_report_router"]
