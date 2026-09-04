# Ad Intelligence Scraper

A browser-based web ad intelligence collector. The pipeline is built incrementally so every stage leaves inspectable evidence for later analysis rather than guessing advertiser identity.

## Current scope

The current pipeline covers collection, evidence, comparison, monitoring and reporting:

- Playwright Chromium crawl with desktop/mobile device profiles
- rendered HTML and full-page screenshot
- redirect, frame, image, script and link inventory
- browser network request/response inventory
- console and page-error capture
- Playwright trace
- conservative DOM ad-candidate detection
- Google Publisher Tag runtime extraction
- Prebid.js runtime extraction
- explicit ad-server/exchange request resolution to GPT/Prebid slots when IDs match
- normalized ad records with advertiser/brand/bid metadata when the publisher exposes it
- DOM candidate screenshots, geometry and visual evidence
- bounded local OCR and visual classification
- discoverable image, video and audio creative asset capture with SSRF/size limits
- public `ads.txt` retrieval and parsing
- landing-page enrichment with SSRF protections and bounded destinations
- stable campaign identity and creative fingerprints
- historical change detection for campaigns, creative additions/removals/changes, placements, devices, networks and normalized CPM
- desktop/mobile campaign comparison
- campaign and competitor/brand frequency intelligence
- bounded same-site crawling
- SQLite-backed history, monitor targets and alerts with legacy JSON migration
- scheduled monitor execution with per-monitor isolation and failure status
- FastAPI API plus a built-in inspection UI
- self-contained HTML and vector PDF intelligence reports

### Evidence-first identity

The scraper does **not** treat OCR text, visual similarity, an ad-tech vendor name, or a URL alone as proof of advertiser identity. Identity is derived from observable evidence such as publisher/runtime metadata, explicit advertiser/brand metadata, destination URLs, landing-page metadata, matched ad requests, bid metadata and creative assets. When the publisher does not expose enough evidence, fields remain unknown.

Competitor frequency is reported as a share of **observed ad records**, not market share.

## Monitoring

Create a monitor with `POST /api/monitors`. Supported devices are `desktop`, `mobile`, and `both`; the minimum interval is 60 minutes. The scheduler is disabled by default for local development and enabled in the production Docker configuration with `AD_SCRAPER_ENABLE_MONITOR_SCHEDULER=1`.

Monitor observations are tagged with their `monitor_id`, so two monitors watching the same URL do not contaminate one another's historical comparison. Alerts are generated for new/disappeared campaigns, creative changes, placement changes, device targeting changes, network changes and CPM changes.

## API

### Crawl

- `GET /api/health` — health check
- `POST /api/crawl` — crawl one URL using a selected device profile
- `POST /api/crawl/both-devices` — crawl desktop and mobile and compare campaign presence/placements
- `POST /api/site-crawl` — bounded same-site crawl

### Monitoring and history

- `POST /api/monitors` — create a monitor
- `GET /api/monitors` — list monitors including status and next-run metadata
- `GET /api/monitors/{monitor_id}` — retrieve a monitor
- `PATCH /api/monitors/{monitor_id}` — update enabled/device/interval settings
- `DELETE /api/monitors/{monitor_id}` — delete a monitor and its alerts
- `POST /api/monitors/{monitor_id}/run` — run a monitor immediately
- `GET /api/monitors/{monitor_id}/alerts` — retrieve monitor alerts
- `POST /api/history/changes` — detect changes between supplied observations
- `GET /api/history?target=...` — retrieve persisted observations
- `POST /api/history?target=...` — append observations
- `GET /api/history/intelligence?target=...` — historical intelligence JSON
- `GET /api/history/report?target=...` — historical HTML report
- `GET /api/history/report.pdf?target=...` — historical PDF report

### Reports

- `POST /api/report/intelligence` — campaign, competitor, device and history intelligence JSON
- `POST /api/report/html` — self-contained HTML intelligence report
- `POST /api/report/pdf` — PDF intelligence report
- `GET /api/runs/{run_id}/report.html` — report for one stored crawl
- `GET /api/runs/{run_id}/report.pdf` — PDF report for one stored crawl
- `GET /api/runs/{run_id}/intelligence` — intelligence JSON for one stored crawl
- `GET /api/runs/{run_id}` — retrieve a stored crawl result
- `GET /api/runs/{run_id}/artifact/{artifact_name}` — retrieve a stored crawl artifact

## Example intelligence request

```json
{
  "observations": [
    {
      "campaign_key": "campaign-1",
      "brand_name": "Example Brand",
      "advertiser_name": "Example Advertiser",
      "device": "desktop",
      "ad_unit_code": "top-banner",
      "observed_at": "2026-09-03T10:00:00Z"
    }
  ]
}
```

## Persistence

Runtime monitoring data is stored under `data/` using SQLite. `data/history/history.sqlite3` stores observations and `data/monitoring/monitoring.sqlite3` stores monitor targets and alerts. Existing JSON history/monitor files are imported once automatically; JSON paths remain exposed for compatibility, but new writes use SQLite.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python -m playwright install chromium
uvicorn app.main:app --app-dir backend --reload
```

Open `http://127.0.0.1:8000/` for the inspection UI or `http://127.0.0.1:8000/docs` for the API documentation.

The default UI target is NDTV Profit. Enter another HTTP(S) URL to test a different page.

## Crawl artifacts

Each run is written beneath `data/runs/<run_id>/` and can contain:

```text
page.html
screenshot.png
ads.json
runtime_ads.json
visual_evidence.json
creative_assets.json
ad_records.json
ad_request_resolution.json
ads.txt.json
landing_enrichment.json
trace.zip
result.json
ad_candidates/*.png
creative_assets/*
```

## Media note

The collector can preserve discoverable image/video/audio URLs and bounded copies of public media assets. It does not claim that every video contains a separately extractable song/audio track. Full audio-track extraction from containerized video requires a media decoder pipeline and is intentionally a separate capability.

## Tests

```bash
cd backend
pytest -q
```

CI installs Chromium and Tesseract and executes the browser regression tests plus the pure Python tests. Recent persistence, scheduler, report, historical-change and request-resolution changes are gated by the same GitHub Actions suite.

## Current testing limitation

This ChatGPT execution environment has a Chromium binary available for synthetic local browser tests, but DNS access to external sites is unavailable. Consequently, an NDTV Profit crawl itself cannot be honestly marked as live-tested from this environment. The repository's CI is configured to install Chromium so browser tests run in GitHub Actions.