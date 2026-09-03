from __future__ import annotations

from .ad_detection import classify_dom_candidates, classify_network_requests
from .ad_models import AdDetectionResult, AdSignal


def detect_ads(network: list[dict[str, object]], dom_candidates: list[dict[str, object]]) -> AdDetectionResult:
    network_signals = classify_network_requests(network)
    dom_signals = classify_dom_candidates(dom_candidates)
    signals = [AdSignal.model_validate(item) for item in [*network_signals, *dom_signals]]
    technologies = sorted({s.ad_technology for s in signals if s.ad_technology})
    return AdDetectionResult(
        signals=signals,
        technologies=technologies,
        network_signal_count=len(network_signals),
        dom_signal_count=len(dom_signals),
    )
