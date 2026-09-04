from app.evidence_confidence import advertiser_evidence_confidence


def test_metadata_and_destination_can_verify_identity():
    result = advertiser_evidence_confidence({
        "advertiser_name": "Acme", "brand_name": "Acme", "landing_page_url": "https://acme.example/",
        "network": "Google Ad Manager",
    })
    assert result["level"] == "verified"
    assert result["score"] >= 80


def test_ocr_only_never_verifies_identity():
    result = advertiser_evidence_confidence({"evidence": ["ocr: ACME", "creative:image"]})
    assert result["level"] == "low"
    assert result["score"] == 10


def test_request_resolution_is_only_corroborating_evidence():
    result = advertiser_evidence_confidence({
        "request_resolution": {"matches": [{"ad_unit_path": "/1234/news"}]}
    })
    assert result["level"] == "low"
    assert result["score"] == 5
    assert result["signals"] == ["request_resolution"]


def test_empty_record_is_unverified():
    assert advertiser_evidence_confidence({}) == {"score": 0, "level": "unverified", "signals": []}
