from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, Response

from .report_html import render_html_report
from .report_intelligence import build_report_intelligence
from .report_pdf import render_pdf_report


def _observations(payload: dict[str, Any]) -> list[dict[str, Any]]:
    pages = payload.get("pages")
    if not isinstance(pages, list):
        raise HTTPException(status_code=422, detail="pages must be a list")
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
