from pathlib import Path

from app.report_pdf import render_pdf_report


def _observations():
    return [
        {
            "observed_at": "2026-09-03T10:00:00Z",
            "campaign_key": "campaign-a",
            "brand_name": "Brand A",
            "advertiser_name": "Advertiser A",
            "device": "desktop",
            "ad_unit_code": "top",
            "format": "display",
            "network": "Google Ad Manager",
        },
        {
            "observed_at": "2026-09-03T11:00:00Z",
            "campaign_key": "campaign-a",
            "brand_name": "Brand A",
            "advertiser_name": "Advertiser A",
            "device": "mobile",
            "ad_unit_code": "mrec",
            "format": "video",
            "network": "Google Ad Manager",
        },
    ]


def test_render_pdf_report_returns_valid_pdf_bytes(tmp_path: Path):
    pdf = render_pdf_report(_observations(), title="Evidence Report")
    assert pdf.startswith(b"%PDF")
    assert b"%EOF" in pdf
    assert len(pdf) > 1000
    output = tmp_path / "report.pdf"
    output.write_bytes(pdf)
    assert output.stat().st_size == len(pdf)


def test_render_pdf_report_includes_intelligence_labels():
    pdf = render_pdf_report(_observations())
    assert b"Ad Intelligence Report" in pdf
    assert b"Campaign intelligence" in pdf
    assert b"Competitor / brand frequency" in pdf
    assert b"Device intelligence" in pdf
    assert b"Historical changes" in pdf


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
