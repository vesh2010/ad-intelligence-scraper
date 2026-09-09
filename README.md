# Ad Intelligence Scraper

A browser-based web ad intelligence collector. The pipeline is evidence-first: every stage leaves inspectable evidence for later analysis rather than guessing advertiser identity.

## Site-wide crawl architecture

Site crawl now uses a bounded **discover → classify → crawl → capture → reconcile → report** pipeline.

Default production controls:

```text
MAX_DEPTH=5
MAX_PAGES=200
MAX_DISCOVERED_URLS=5000
MAX_RUNTIME_MINUTES=25
BOTH_DEVICES=true
WAIT_MS=2500
TIMEOUT_MS=60000
ENRICH_LANDING_PAGES=true
MAX_LANDING_DESTINATIONS=25
DISCOVER_SITEMAP=true
HANDLE_CONSENT=true
KEEP_EVIDENCE=true
SCROLL_PAGE=true
CAPTURE_RUNTIME_SNAPSHOTS=true
```

Discovery checks `robots.txt`, sitemap indexes, `sitemap.xml`, rendered page links, canonical/next/prev links, iframes and JSON-LD URLs. Discovered URLs are normalized, deduplicated, bounded and classified into homepage, section/category/topic, article, video, gallery, author, tag, search, pagination or other.

Every crawl writes a manifest with URL, source, discovery method, depth, section, page type, status, HTTP status, device coverage, ad signal count and normalized ad count. The report distinguishes pages that had no observed ad from pages that were never crawled or failed.

Ad capture is multi-stage: DOMContentLoaded, post-wait, network-idle/timeout, consent handling, 25/50/75/100% scroll checkpoints and final state. Runtime, network, DOM, iframe and visual evidence are reconciled into normalized records. Public landing destinations can be enriched with bounded redirect validation and metadata extraction.

Evidence retention is enabled for site investigations. This includes page HTML, screenshots, network/runtime JSON, visual evidence, candidate captures, creative assets, trace data and landing-page metadata when available.

## Automatic 13-site reports

GitHub Actions runs the configured publisher set automatically on push, daily, or manually. The automatic job uses a bounded 50-page-per-device CI profile, depth 5, up to 5,000 discovered URLs and desktop + mobile coverage. Each site produces HTML + PDF plus its crawl manifest and retained evidence package. A second job builds the 13-site comparison HTML + PDF table.

The configured publishers are NDTV, News18, The Indian Express, Times of India, Zee News, Economic Times, Moneycontrol, Business Standard, Navbharat Times, Dainik Jagran, Aaj Tak, News18 Hindi and ABP News.

## What you use it for

Use the scraper when you want to answer questions such as:

- Which advertisers/brands are visibly exposed on a publisher page?
- Which campaigns and creatives appeared across repeated observations?
- How does ad delivery differ between desktop and mobile?
- Which campaigns are new, gone, changed, or moved?
- Which brands occur most often in the ads you actually observed?
- What ad-tech, supply-chain, landing-page and creative evidence supports an identity claim?
- Can I preserve the raw browser evidence behind a report?

The system reports **observed evidence**, not a claim of total market inventory or spend.

## Fastest way to start

### Option A — Windows portable app (recommended for sharing)

The repository's `windows-desktop` GitHub Actions workflow builds a single `AdIntelligenceScraper.exe` for Windows. The executable bundles the Python application, Chromium, OCR and media tooling, so the recipient does **not** need Docker, Python, Node.js, Playwright or a separate Chromium installation.

To create a downloadable build, use the successful Windows workflow artifact from GitHub Actions, or push a version tag to publish the EXE as a GitHub Release asset. Copy the single `AdIntelligenceScraper.exe` to the Windows computer and double-click it.

What happens:

1. the EXE starts the local backend on `127.0.0.1:8765`;
2. it opens the default browser automatically;
3. the user operates the normal web UI;
4. crawl data is stored in a `data` folder next to the EXE;
5. the monitoring scheduler runs while the EXE remains open;
6. the background application can be stopped from Windows Task Manager when finished.

The EXE is intentionally localhost-only; it does not publish the scraper API to the LAN or internet.

### Option B — Docker

From the repository root:

```bash
docker compose up -d --build
```

Open `http://127.0.0.1:8000/` for the UI. Docker remains the better option for an always-on server.

### Option C — Python

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python -m playwright install chromium
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

## Operator workflow

### 1. One-page investigation

Open the UI, enter the publisher URL, leave **Site crawl** off, and press **Start crawl**.

Use this when you want a detailed snapshot of one page. Review network/DOM signals, normalized ad records, advertiser/brand evidence, visual candidates/OCR, ads.txt and raw JSON.

If you need stronger advertiser evidence, enable **Enrich landing pages**.

### 2. Desktop vs mobile

For API users, call `POST /api/crawl/both-devices`. The result contains desktop/mobile crawls and a comparison showing campaigns present on desktop only, mobile only, or both, plus placement differences.

### 3. Site investigation

Enable **Site crawl** and choose a bounded page/depth limit. Site reports include crawl coverage, section/page-type coverage, the complete manifest, ad inventory, missing-data analysis and errors.

### 4. Repeated monitoring

In **Monitoring**:

1. enter the target URL;
2. choose Desktop, Mobile, or Desktop + Mobile;
3. choose at least 60 minutes;
4. click **Create monitor**.

Docker and the Windows portable application enable the scheduler automatically. Python development mode leaves it disabled unless explicitly enabled. Click **Run** for an immediate check.

Alerts can cover campaign appearance/disappearance, creative changes, placement/device/network changes and CPM changes. Use **Alerts** to inspect stored events.

### 5. Reports

Use run reports for a single crawl, historical reports for repeated monitoring data, and site reports for bounded multi-page investigations. Reports include campaign intelligence, competitor/brand frequency, device intelligence, historical changes, crawl coverage and advertiser/creative evidence.

Competitor frequency is the share of **observed ad records**, not market share.

## Evidence rules

The scraper does **not** treat OCR text, visual similarity, an ad-tech vendor name, or a URL alone as proof of advertiser identity. Identity is derived from observable evidence such as publisher/runtime metadata, explicit advertiser/brand metadata, destination URLs, landing-page metadata, matched ad requests, bid metadata and creative assets. When the publisher does not expose enough evidence, fields remain unknown.

## Data and backups

Persistent data is under `data/` (or beside the Windows EXE):

- `history/history.sqlite3` — observations
- `monitoring/monitoring.sqlite3` — monitor targets and alerts
- `runs/` — crawl artifacts

Create a consistent backup with:

```bash
python scripts/backup.py
```

For the Windows portable build, run the same script only when using a Python checkout; the portable EXE stores its data next to itself and should be backed up by copying its `data` folder while the application is stopped.

## Security / deployment guidance

The scraper keeps publisher pages and third-party ad destinations separate. External domains are recorded as ad destinations, ad servers, landing pages or network evidence; they are not promoted to normal site pages unless the crawl configuration explicitly permits them.
