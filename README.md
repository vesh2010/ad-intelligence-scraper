# Ad Intelligence Scraper

A browser-based web ad intelligence collector. The pipeline is being built incrementally so every stage leaves inspectable evidence for later analysis.

## Current scope: M1 + M2 + supply-chain foundation

- Playwright Chromium crawl
- rendered HTML and full-page screenshot
- redirect, frame, image, script and link inventory
- browser network request/response inventory
- console and page-error capture
- Playwright trace
- DOM ad-candidate detection with conservative markers
- Google Publisher Tag runtime extraction
- Prebid.js runtime extraction
- normalized ad records with advertiser/brand/bid metadata when the publisher exposes it
- DOM candidate screenshots and geometry
- public `ads.txt` retrieval and parsing
- raw JSON artifacts for every crawl
- FastAPI API plus a built-in inspection UI

Product identity is intentionally not guessed yet. Landing-page enrichment, stronger visual classification, deduplication/history, broader supply-chain resolution and GPT analysis are later stages.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python -m playwright install chromium
uvicorn app.main:app --app-dir backend --reload
```

Open:

`http://127.0.0.1:8000/`

The default UI target is NDTV Profit. Enter another HTTP(S) URL to test a different page.

The API remains available at:

`http://127.0.0.1:8000/docs`

Example request:

```json
{"url":"https://www.ndtvprofit.com/"}
```

## Crawl artifacts

Each run is written beneath `data/runs/<run_id>/` and can contain:

```text
page.html
screenshot.png
ads.json
runtime_ads.json
visual_evidence.json
ad_records.json
ads.txt.json
trace.zip
result.json
ad_candidates/*.png
```

## Tests

```bash
cd backend
pytest -q
```

CI installs Chromium and executes the browser regression tests as well as the pure Python tests.

## Current testing limitation

This ChatGPT execution environment has a Chromium binary available for synthetic local browser tests, but DNS access to external sites is unavailable. Consequently, the NDTV Profit crawl itself cannot be honestly marked as live-tested from this environment. The repository's CI is configured to install Chromium so the browser tests run in GitHub Actions.
