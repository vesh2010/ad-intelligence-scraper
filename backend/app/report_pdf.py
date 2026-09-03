from __future__ import annotations

import io
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .report_intelligence import build_report_intelligence


def _value(value: Any, fallback: str = "—") -> str:
    text = str(value or "").strip()
    return text or fallback


def _pct(value: Any) -> str:
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return "0.0%"


def _paragraph(text: Any, style: ParagraphStyle) -> Paragraph:
    return Paragraph(_value(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), style)


def _table(data: list[list[Any]], widths: list[float], styles: list[tuple[str, Any, Any, Any, Any]] | None = None) -> Table:
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    base = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEADING", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d1d5db")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if styles:
        base.extend(styles)
    table.setStyle(TableStyle(base))
    return table


def _header_footer(canvas, doc) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#6b7280"))
    canvas.drawString(18 * mm, 10 * mm, "Ad Intelligence Scraper — evidence-backed report")
    canvas.drawRightString(width - 18 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def render_pdf_report(observations: list[dict[str, Any]], title: str = "Ad Intelligence Report") -> bytes:
    """Generate a self-contained PDF from the same intelligence payload as the HTML report."""
    if not all(isinstance(row, dict) for row in observations):
        raise ValueError("observations must be a list of objects")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("title must be a non-empty string")

    intelligence = build_report_intelligence(observations)
    campaigns = intelligence["campaigns"]["campaigns"]
    competitors = intelligence["campaigns"]["competitors"]
    devices = intelligence["devices"]
    history = intelligence["history"]

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("ReportTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=22, leading=26, spaceAfter=8, alignment=TA_LEFT)
    h2 = ParagraphStyle("ReportH2", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=14, leading=17, spaceBefore=12, spaceAfter=7)
    body = ParagraphStyle("ReportBody", parent=styles["BodyText"], fontName="Helvetica", fontSize=9, leading=13, spaceAfter=5)
    small = ParagraphStyle("ReportSmall", parent=body, fontSize=7.5, leading=10)
    card = ParagraphStyle("ReportCard", parent=body, fontName="Helvetica-Bold", fontSize=12, leading=14, spaceAfter=0)

    story: list[Any] = [
        Paragraph(title.strip(), title_style),
        Paragraph(
            f"Generated from {len(observations)} observed ad records. "
            "Observation share is the share of observed records, not market share.",
            body,
        ),
        Spacer(1, 4 * mm),
    ]

    summary = [
        [Paragraph("Observations", small), Paragraph("Campaigns", small), Paragraph("Both devices", small), Paragraph("History changes", small)],
        [Paragraph(str(intelligence["observation_count"]), card), Paragraph(str(intelligence["campaigns"]["campaign_count"]), card), Paragraph(str(devices["both_device_campaigns"]), card), Paragraph(str(history.get("change_count", 0)), card)],
    ]
    summary_table = Table(summary, colWidths=[43 * mm] * 4, hAlign="LEFT")
    summary_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#e5e7eb")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story += [summary_table, Spacer(1, 5 * mm)]

    story.append(Paragraph("Executive summary", h2))
    if campaigns:
        top = campaigns[0]
        story.append(Paragraph(
            f"Most observed campaign records were associated with {_value(top.get('brand_name'))}. "
            f"It accounted for {_pct(top.get('observation_share_pct'))} of observed records. "
            f"{devices['both_device_campaigns']} campaign(s) were observed on both desktop and mobile.", body))
    else:
        story.append(Paragraph("No campaign records were observed in the supplied dataset.", body))

    story.append(Paragraph("Campaign intelligence", h2))
    campaign_data = [["Brand", "Advertiser", "Obs.", "Share", "First seen", "Last seen"]]
    for row in campaigns:
        campaign_data.append([
            _paragraph(row.get("brand_name"), small), _paragraph(row.get("advertiser_name"), small),
            str(row.get("observations", 0)), _pct(row.get("observation_share_pct")),
            _paragraph(row.get("first_seen"), small), _paragraph(row.get("last_seen"), small),
        ])
    if len(campaign_data) == 1:
        campaign_data.append(["No campaigns observed.", "—", "0", "0.0%", "—", "—"])
    story.append(_table(campaign_data, [34 * mm, 34 * mm, 14 * mm, 16 * mm, 35 * mm, 35 * mm]))

    story.append(Paragraph("Competitor / brand frequency", h2))
    competitor_data = [["Brand", "Observations", "Share"]]
    for row in competitors:
        competitor_data.append([_paragraph(row.get("brand_name"), small), str(row.get("observations", 0)), _pct(row.get("observation_share_pct"))])
    if len(competitor_data) == 1:
        competitor_data.append(["No competitor/brand observations.", "0", "0.0%"])
    story.append(_table(competitor_data, [110 * mm, 35 * mm, 35 * mm]))

    story.append(PageBreak())
    story.append(Paragraph("Device intelligence", h2))
    device_data = [["Metric", "Count"],
                   ["Desktop-only campaigns", str(devices["desktop_only_campaigns"])],
                   ["Mobile-only campaigns", str(devices["mobile_only_campaigns"])],
                   ["Campaigns on both devices", str(devices["both_device_campaigns"])]]
    story.append(_table(device_data, [120 * mm, 60 * mm]))
    both = [row for row in devices.get("campaigns", []) if row.get("both_devices")]
    if both:
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph("Cross-device placements", h2))
        placement_data = [["Campaign", "Desktop placements", "Mobile placements", "Shared"]]
        for row in both:
            placement_data.append([
                _paragraph(row.get("campaign_key"), small),
                _paragraph(", ".join(row.get("desktop_placements") or []) or "—", small),
                _paragraph(", ".join(row.get("mobile_placements") or []) or "—", small),
                _paragraph(", ".join(row.get("shared_placements") or []) or "—", small),
            ])
        story.append(_table(placement_data, [42 * mm, 46 * mm, 46 * mm, 46 * mm]))

    story.append(Paragraph("Historical changes", h2))
    change_data = [["Change type", "Count"]]
    for key in ("new_campaigns", "disappeared_campaigns", "creative_changes", "placement_changes", "device_targeting_changes", "network_changes", "cpm_changes"):
        change_data.append([key.replace("_", " ").title(), str(history.get(key, 0))])
    story.append(_table(change_data, [120 * mm, 60 * mm]))

    story.append(Paragraph("Advertiser and creative evidence", h2))
    evidence_rows = [["Campaign", "Advertiser / brand", "Formats", "Networks", "Above fold"]]
    for row in campaigns:
        evidence_rows.append([
            _paragraph(row.get("campaign_key"), small),
            _paragraph(f"{_value(row.get('advertiser_name'))} / {_value(row.get('brand_name'))}", small),
            _paragraph(", ".join(row.get("formats") or []) or "—", small),
            _paragraph(", ".join(row.get("networks") or []) or "—", small),
            str(row.get("above_fold_observations", 0)),
        ])
    if len(evidence_rows) == 1:
        evidence_rows.append(["No campaigns.", "—", "—", "—", "0"])
    story.append(_table(evidence_rows, [42 * mm, 50 * mm, 35 * mm, 35 * mm, 18 * mm]))

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "Identity is based on observable evidence such as advertiser/brand metadata, landing destinations, creative assets, placements, and ad-tech signals. "
        "OCR or visual signals alone do not prove advertiser identity. Missing evidence is reported as missing rather than inferred.", small))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=15 * mm, leftMargin=15 * mm, topMargin=15 * mm, bottomMargin=16 * mm,
        title=title.strip(), author="Ad Intelligence Scraper",
    )
    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buffer.getvalue()


__all__ = ["render_pdf_report"]
