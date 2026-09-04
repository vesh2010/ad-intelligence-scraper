# Ad Intelligence Scraper

A browser-based web ad intelligence collector. The pipeline is built incrementally so every stage leaves inspectable evidence for later analysis rather than guessing advertiser identity.

## v1.0.0 status

The v1.0.0 implementation is complete for the defined evidence-first scope. GitHub Actions gates the Python/browser regression suite, Docker runtime smoke test, and Windows portable application build. The system is production-oriented, but live publisher behavior remains inherently variable and must be interpreted from evidence.

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

Enable **Site crawl** and choose a bounded page/depth limit. Use this for a small publisher section rather than an entire large site.

### 4. Repeated monitoring

In **Monitoring**:

1. enter the target URL;
2. choose Desktop, Mobile, or Desktop + Mobile;
3. choose at least 60 minutes;
4. click **Create monitor**.

Docker and the Windows portable application enable the scheduler automatically. Python development mode leaves it disabled unless explicitly enabled. Click **Run** for an immediate check.

Alerts can cover campaign appearance/disappearance, creative changes, placement/device/network changes and CPM changes. Use **Alerts** to inspect stored events.

### 5. Reports

Use run reports for a single crawl, historical reports for repeated monitoring data, and site reports for bounded multi-page investigations. Reports include campaign intelligence, competitor/brand frequency, device intelligence, historical changes and advertiser/creative evidence.

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

The default deployments are localhost-only because the API has no built-in user authentication. Do not expose it directly to the public internet. For remote access, use an authenticated reverse proxy/VPN/SSH tunnel.

## Current scope

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
- optional FFprobe media metadata inspection
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
- Docker build/runtime health and smoke testing
- Windows single-file portable executable with bundled browser/runtime dependencies

## API reference

Open `/docs` while the service is running for interactive Swagger documentation. Core endpoints include `/api/crawl`, `/api/crawl/both-devices`, `/api/site-crawl`, `/api/monitors`, `/api/history`, and `/api/runs/{run_id}/...`.

## Testing

```bash
cd backend
pytest -q
```

CI validates Python/browser behavior, Docker startup, and the Windows portable executable's startup, `/api/health` and `/docs` endpoints.

## Acceptance status

- Core crawl and ad evidence: complete
- GPT/Prebid/network resolution: complete
- Evidence-backed advertiser identity: complete
- Creative/OCR/media capture: complete within documented bounds
- Desktop/mobile comparison: complete
- Historical change intelligence: complete
- SQLite persistence and monitor isolation: complete
- Scheduled monitoring and alerts: complete
- HTML/PDF/report intelligence: complete
- Site-crawl reporting: complete
- API and artifact security validation: complete
- Docker production packaging and smoke test: complete
- Backup utility and operator runbook: complete
- Windows single-file portable application: complete, with automated startup smoke test
- Automated regression CI: release gates enabled

## Live-site limitation

External publisher pages can change their ad stack, inventory and consent behavior at any time. This environment cannot honestly guarantee a live publisher crawl from ChatGPT because external DNS access is unavailable here. Automated acceptance therefore relies on browser regression, deterministic report tests, Docker runtime checks and the Windows executable smoke test. When a live publisher crawl is performed in an environment with network access, advertiser identity should still be reported as unknown whenever the publisher does not expose sufficient evidence.
