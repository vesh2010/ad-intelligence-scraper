# Ad Intelligence Scraper

M1: rendered-page crawler foundation for ad intelligence research.

## M1 scope

- Playwright Chromium crawl
- final URL and redirect information
- page title and metadata
- images, scripts, links, iframes and frames
- network request/response inventory
- console and page errors
- viewport/full-page screenshots
- raw rendered HTML
- optional Playwright trace
- JSON run manifest
- FastAPI API
- unit tests for validation and redaction

Ad classification, advertiser identification and bid/auction extraction are intentionally deferred to M2.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python -m playwright install chromium
uvicorn app.main:app --app-dir backend --reload
```

Open `http://127.0.0.1:8000/docs` and POST to `/api/crawl` with:

```json
{"url":"https://www.ndtvprofit.com/"}
```

## Tests

```bash
pytest -q
```

## Browser note

The repository is designed to run Chromium through Playwright. A browser executable must be installed in the runtime. The current development environment could install the Python package but could not download Chromium because its network/DNS access to the Playwright CDN is unavailable; therefore a live browser crawl is not represented as passing CI here.
