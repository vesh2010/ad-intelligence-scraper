from app.ads_txt import parse_ads_txt


def test_parse_ads_txt_entries_and_variables():
    parsed = parse_ads_txt(
        """
        # comment
        google.com, pub-123, DIRECT, f08c47fec0942fa0
        example-ssp.com, 456, RESELLER
        OWNERDOMAIN=ndtv.com
        MANAGERDOMAIN=example.com
        malformed
        """
    )

    assert parsed["entry_count"] == 2
    assert parsed["entries"][0]["ad_system"] == "google.com"
    assert parsed["entries"][0]["relationship"] == "direct"
    assert parsed["entries"][1]["relationship"] == "reseller"
    assert parsed["variables"]["OWNERDOMAIN"] == "ndtv.com"
    assert parsed["variables"]["MANAGERDOMAIN"] == "example.com"
