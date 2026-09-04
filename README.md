# Ad Intelligence Scraper

A browser-based web ad intelligence collector. The pipeline is built incrementally so every stage leaves inspectable evidence for later analysis rather than guessing advertiser identity.

## v1.0.0 status

The v1.0.0 implementation is complete for the defined evidence-first scope. GitHub Actions gates both the Python/browser regression suite and a Docker build/runtime smoke test. The system is production-oriented, but live publisher behavior remains inherently variable and must be interpreted from evidence.

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

### Option A — Docker (recommended)

From the repository root:

```bash
docker compose up -d --build
```

Open:

- `http://127.0.0.1:8000/` — visual operator UI
- `http://127.0.0.1:8000/docs` — interactive API documentation

The compose file binds port 8000 to localhost only by default. This prevents an unauthenticated scraper API from being exposed directly to the LAN or internet.

To stop it:

```bash
docker compose down
```

Your `./data` directory remains persistent across container restarts.

### Option B — Python

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python -m playwright install chromium
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

On Windows PowerShell, activate the environment with `.venv\\Scripts\\Activate.ps1`.

## Operator workflow

### 1. One-page investigation

Open the UI, enter the publisher URL, leave **Site crawl** off, and press **Start crawl**.

Use this when you want a detailed snapshot of one page. Review:

- network and DOM ad signals
- detected ad technologies
- normalized ad records
- advertiser/brand evidence
- visual candidates and OCR
- ads.txt
- raw crawl JSON

If you need stronger advertiser evidence, enable **Enrich landing pages**. This follows bounded destinations and collects additional landing-page metadata.

### 2. Desktop vs mobile

For API users, call `POST /api/crawl/both-devices`. The result contains the desktop crawl, mobile crawl and a comparison showing campaigns present on desktop only, mobile only, or both, plus placement differences.

This is the best mode for investigating responsive ad targeting.

### 3. Site investigation

Enable **Site crawl** in the UI and choose a bounded page/depth limit. Use this for a small publisher section rather than trying to crawl an entire large site.

For API users, call `POST /api/site-crawl` and then one of the `/api/site-crawl/report.*` endpoints with the returned payload.

### 4. Repeated monitoring

In the UI's **Monitoring** section:

1. enter the target URL above;
2. choose Desktop, Mobile, or Desktop + Mobile;
3. choose an interval of at least 60 minutes;
4. click **Create monitor**.

The production Docker configuration runs the scheduler automatically. You can also click **Run** for an immediate check.

The monitor compares the new observation with that monitor's own history and creates alerts for campaign appearance/disappearance, creative changes, placement/device/network changes and CPM changes.

Use **Alerts** to inspect stored alert events. Delete a monitor when you no longer need it; its alerts are removed with it.

### 5. Reports

For a stored single crawl, use:

- `/api/runs/{run_id}/report.html`
- `/api/runs/{run_id}/report.pdf`
- `/api/runs/{run_id}/intelligence`

For historical monitoring data, use:

- `/api/history/report`
- `/api/history/report.pdf`
- `/api/history/intelligence`

Reports include campaign intelligence, competitor/brand frequency, device intelligence, historical changes and advertiser/creative evidence. Competitor frequency is the share of **observed ad records**, not market share.

## Evidence rules

The scraper does **not** treat OCR text, visual similarity, an ad-tech vendor name, or a URL alone as proof of advertiser identity. Identity is derived from observable evidence such as publisher/runtime metadata, explicit advertiser/brand metadata, destination URLs, landing-page metadata, matched ad requests, bid metadata and creative assets. When the publisher does not expose enough evidence, fields remain unknown.

## Data and backups

Persistent data is under `data/`:

- `data/history/history.sqlite3` — observations
- `data/monitoring/monitoring.sqlite3` — monitor targets and alerts
- `data/runs/` — crawl artifacts

Create a consistent backup with:

```bash
python scripts/backup.py
```

This creates a timestamped ZIP under `data/backups/`, using SQLite's backup API for the databases and preserving crawl artifacts plus legacy JSON compatibility files.

For important production data, copy the generated ZIP to a separate machine/storage location. A Docker container restart is not a backup.

## Security / deployment guidance

The default compose deployment is deliberately localhost-only because the API has no built-in user authentication. **Do not expose port 8000 directly to the public internet.**

If you need remote access, put the service behind an authenticated reverse proxy/VPN/SSH tunnel and keep the container's application port private. For a personal workstation, an SSH tunnel or VPN is preferable to opening the port publicly.

The crawler includes SSRF protections and bounded downloads/crawls, but the service should still be treated as an operator-controlled network tool rather than an anonymous public endpoint.

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
- optional FFprobe media metadata inspection in production containers
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
- Docker build/runtime health and API smoke testing

## API reference

Open `/docs` while the service is running for the interactive Swagger UI. The core endpoints are:

- `GET /api/health`
- `POST /api/crawl`
- `POST /api/crawl/both-devices`
- `POST /api/site-crawl`
- `POST /api/monitors`
- `GET /api/monitors`
- `PATCH /api/monitors/{monitor_id}`
- `DELETE /api/monitors/{monitor_id}`
- `POST /api/monitors/{monitor_id}/run`
- `GET /api/monitors/{monitor_id}/alerts`
- `GET /api/history?target=...`
- `GET /api/history/intelligence?target=...`
- `GET /api/history/report?target=...`
- `GET /api/history/report.pdf?target=...`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/artifact/{artifact_name}`
- `GET /api/runs/{run_id}/report.html`
- `GET /api/runs/{run_id}/report.pdf`
- `GET /api/runs/{run_id}/intelligence`

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

The collector can preserve discoverable image/video/audio URLs and bounded copies of public media assets. FFprobe metadata is collected for downloaded video/audio files when available. The system does not claim that every video contains a separately extractable song/audio track; that requires an explicit media-decoder extraction pipeline and is outside the v1.0.0 evidence contract.

## Testing

```bash
cd backend
pytest -q
```

CI installs Chromium and Tesseract and executes the browser regression tests plus the pure Python tests. A second GitHub Actions workflow builds the production Docker image, starts it, waits for `/api/health`, verifies `/docs`, and captures diagnostics on failure.

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
- Automated regression CI: green on the latest validated release commits

## Live-site limitation

External publisher pages can change their ad stack, inventory and consent behavior at any time. This environment cannot honestly guarantee a live NDTV Profit crawl from ChatGPT because external DNS access is unavailable here. The repository therefore treats synthetic browser regression, deterministic report tests, and Docker runtime checks as automated acceptance gates rather than fabricating live-site results. When a live publisher crawl is performed in an environment with network access, advertiser identity should still be reported as unknown whenever the publisher does not expose sufficient evidence.
