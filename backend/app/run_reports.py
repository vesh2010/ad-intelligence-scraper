from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, Response

from .crawler.models import CrawlResult
from .history import build_snapshot
from .report_html import render_html_report
from .report_intelligence import build_report_intelligence
from .report_pdf import render_pdf_report


def _observations(result: CrawlResult) -> list[dict[str, Any]]:
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    rows = build_snapshot(result.ad_records, timestamp)
    for row in rows:
        row["device"] = result.device
        row["run_id"] = result.run_id
        row["target_url"] = result.final_url
        row["crawl_session_id"] = result.run_id
    return rows


def generate_run_reports(result: CrawlResult, data_root: str | Path) -> dict[str, str]:
    """Render and persist HTML, PDF, and intelligence immediately after a crawl."""
    run_dir = Path(data_root) / result.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    observations = _observations(result)
    report_html = run_dir / "report.html"
    report_pdf = run_dir / "report.pdf"
    intelligence = run_dir / "intelligence.json"
    report_html.write_text(
        render_html_report(observations, title=f"Ad Intelligence — {result.final_url}"),
        encoding="utf-8",
    )
    report_pdf.write_bytes(
        render_pdf_report(observations, title=f"Ad Intelligence — {result.final_url}")
    )
    intelligence.write_text(
        __import__("json").dumps(build_report_intelligence(observations), indent=2, default=str),
        encoding="utf-8",
    )
    result.artifacts.update(
        {
            "report_html": str(report_html),
            "report_pdf": str(report_pdf),
            "intelligence": str(intelligence),
        }
    )
    (run_dir / "result.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return {
        "report_html": str(report_html),
        "report_pdf": str(report_pdf),
        "intelligence": str(intelligence),
    }


def _load_run(data_root: Path, run_id: str) -> CrawlResult:
    path = data_root / run_id / "result.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Run not found")
    try:
        return CrawlResult.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail="Stored run is invalid") from exc


def build_run_report_router(data_root: str | Path | Callable[[], str | Path]) -> APIRouter:
    router = APIRouter(prefix="/api/runs", tags=["reports"])

    def current_root() -> Path:
        return Path(data_root() if callable(data_root) else data_root)

    @router.get("/{run_id}/report.html", response_class=HTMLResponse)
    async def run_report_html(run_id: str) -> HTMLResponse:
        result = _load_run(current_root(), run_id)
        return HTMLResponse(render_html_report(_observations(result), title=f"Ad Intelligence — {result.final_url}"))

    @router.get("/{run_id}/report.pdf")
    async def run_report_pdf(run_id: str) -> Response:
        result = _load_run(current_root(), run_id)
        pdf = render_pdf_report(_observations(result), title=f"Ad Intelligence — {result.final_url}")
        return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": 'inline; filename="ad-intelligence-run-report.pdf"'})

    @router.get("/{run_id}/intelligence")
    async def run_intelligence(run_id: str) -> dict[str, Any]:
        result = _load_run(current_root(), run_id)
        return build_report_intelligence(_observations(result))

    return router


__all__ = ["build_run_report_router", "generate_run_reports"]
