from pathlib import Path
from io import BytesIO

from app.report_pdf import render_pdf_report


def _observations():
    return [
        {"observed_at": "2026-09-03T10:00:00Z", "campaign_key": "campaign-a", "brand_name": "Brand A", "advertiser_name": "Advertiser A", "device": "desktop", "ad_unit_code": "top", "format": "display", "network": "Google Ad Manager"},
        {"observed_at": "2026-09-03T11:00:00Z", "campaign_key": "campaign-a", "brand_name": "Brand A", "advertiser_name": "Advertiser A", "device": "mobile", "ad_unit_code": "mrec", "format": "video", "network": "Google Ad Manager"},
        {"observed_at": "2026-09-03T12:00:00Z", "campaign_key": "campaign-b", "brand_name": "Brand B", "advertiser_name": "Advertiser B", "device": "desktop", "ad_unit_code": "sidebar", "format": "display", "network": "Prebid"},
    ]


def test_render_pdf_report_returns_valid_pdf_bytes(tmp_path: Path):
    pdf = render_pdf_report(_observations(), title="Evidence Report")
    assert pdf.startswith(b"%PDF")
    assert b"%EOF" in pdf
    assert len(pdf) > 1000
    output = tmp_path / "report.pdf"
    output.write_bytes(pdf)
    assert output.stat().st_size == len(pdf)


def test_render_pdf_report_contains_expected_visible_text_and_competitors():
    from pypdf import PdfReader
    reader = PdfReader(BytesIO(render_pdf_report(_observations())))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Ad Intelligence Report" in text
    assert "Campaign intelligence" in text
    assert "Competitor / brand frequency" in text
    assert "Observed brand share" in text
    assert "Brand A" in text
    assert "Brand B" in text
    assert "Advertiser A" in text
    assert "Device intelligence" in text
    assert "Campaign device distribution" in text
    assert "Historical changes" in text
    assert "Advertiser and creative evidence" in text
    assert "observation share is the share of observed records, not market share" in text.lower()


def test_render_pdf_report_validates_inputs():
    try:
        render_pdf_report(["invalid"])
    except ValueError as exc:
        assert "observations" in str(exc)
    else:
        raise AssertionError("expected ValueError")
    try:
        render_pdf_report([], title=" ")
    except ValueError as exc:
        assert "title" in str(exc)
    else:
        raise AssertionError("expected ValueError")
