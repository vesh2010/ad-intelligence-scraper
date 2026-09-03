from app.ad_pipeline import detect_ads


def test_pipeline_combines_network_and_dom_signals():
    result = detect_ads(
        [{
            "url": "https://securepubads.g.doubleclick.net/gampad/ads",
            "method": "GET",
            "resource_type": "xhr",
            "status": 200,
        }],
        [{"id": "top-ad", "class_name": "leaderboard", "text": "Advertisement"}],
    )
    assert result.network_signal_count == 1
    assert result.dom_signal_count == 1
    assert "Google Ad Manager/DoubleClick" in result.technologies
