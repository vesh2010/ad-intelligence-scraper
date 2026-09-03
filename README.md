# Ad Intelligence Scraper

A browser-based web ad intelligence collector. The pipeline is built incrementally so every stage leaves inspectable evidence for later analysis rather than guessing advertiser identity.

## Current scope

The current pipeline covers the core collection, evidence, comparison and reporting layers:

- Playwright Chromium crawl with desktop/mobile device profiles
- rendered HTML and full-page screenshot
- redirect, frame, image, script and link inventory
- browser network request/response inventory
- console and page-error capture
- Playwright trace
- conservative DOM ad-candidate detection
- Google Publisher Tag runtime extraction
- Prebid.js runtime extraction
- normalized ad records with advertiser/brand/bid metadata when the publisher exposes it
- DOM candidate screenshots, geometry and visual evidence
- bounded local OCR and visual classification
- public `ads.txt` retrieval and parsing
- landing-page enrichment with SSRF protections and bounded destinations
- stable campaign identity and creative fingerprints
- historical change detection for campaigns, creatives, placements, devices, networks and CPM
- desktop/mobile campaign comparison
- campaign and competitor/brand frequency intelligence
- bounded same-site crawling
- FastAPI API plus a built-in inspection UI
- self-contained HTML intelligence reports

### Evidence-first identity

The scraper does **not** treat OCR text or visual similarity as proof of advertiser identity. Identity is derived from observable evidence such as publisher/runtime metadata, destination URLs, landing-page metadata, ad-tech signals and creative assets. When the publisher does not expose enough evidence, fields can remain unknown.

Competitor frequency is reported as a share of **observed ad records**, not market share.

## API

- `GET /api/health` — health check
- `POST /api/crawl` — crawl one URL using a selected device profile
- `POST /api/crawl/both-devices` — crawl desktop and mobile and compare campaign presence/placements
- `POST /api/site-crawl` — bounded same-site crawl
- `POST /api/history/changes` — detect changes between persisted observations
- `POST /api/report/intelligence` — return campaign, competitor, device and history intelligence as JSON
- `POST /api/report/html` — return a self-contained HTML intelligence report
- `GET /api/runs/{run_id}` — retrieve a stored crawl result
- `GET /api/runs/{run_id}/artifact/{artifact_name}` — retrieve a stored crawl artifact

Example intelligence request:

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
ads.txt.json
landing_enrichment.json
trace.zip
result.json
ad_candidates/*.png
```

## Tests

```bash
cd backend
pytest -q
```

CI installs Chromium and Tesseract and executes the browser regression tests as well as the pure Python tests.

## Current testing limitation

This ChatGPT execution environment has a Chromium binary available for synthetic local browser tests, but DNS access to external sites is unavailable. Consequently, the NDTV Profit crawl itself cannot be honestly marked as live-tested from this environment. The repository's CI is configured to install Chromium so the browser tests run in GitHub Actions.
