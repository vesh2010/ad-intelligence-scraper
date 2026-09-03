from __future__ import annotations

SENSITIVE_HEADERS = {
    "authorization",
    "proxy-authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
}


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    """Remove credential/session-bearing headers before persisting crawl data."""
    return {
        key: "[REDACTED]" if key.lower() in SENSITIVE_HEADERS else value
        for key, value in headers.items()
    }
