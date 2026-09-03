from __future__ import annotations

from pathlib import Path

from app import visual_analysis


def test_visual_classification_uses_ocr_and_asset_signals(tmp_path: Path, monkeypatch) -> None:
    image = tmp_path / "creative.png"
    image.write_bytes(b"not-a-real-png")
    monkeypatch.setattr(
        visual_analysis,
        "ocr_image",
        lambda path: {"available": True, "text": "Amazing offer Buy Now", "confidence": None, "error": None},
    )

    result = visual_analysis.classify_visual_evidence(
        image,
        {"width": 300, "height": 250},
        [{"mime_type": "image/png"}],
    )

    classification = result["visual_classification"]
    assert classification["creative_kind"] == "image"
    assert classification["composition"] == "text_with_cta"
    assert classification["cta_count"] == 1
    assert classification["aspect_ratio"] == 1.2


def test_ocr_is_non_fatal_when_tesseract_missing(tmp_path: Path, monkeypatch) -> None:
    image = tmp_path / "creative.png"
    image.write_bytes(b"x")
    monkeypatch.setattr(visual_analysis.shutil, "which", lambda name: None)

    result = visual_analysis.ocr_image(image)

    assert result["available"] is False
    assert result["text"] == ""
    assert result["error"] == "tesseract not installed"
