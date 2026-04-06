# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

A Swiss hiking tracker for a small group of users, with three components:

1. **`scraper.py`** — fetches route and stage data from the SchweizMobil map API and enriches each stage with SBB travel times from multiple Swiss cities via transport.opendata.ch. Outputs `hikes.json` locally and can import to Supabase.
2. **`index.html`** — a single-file vanilla JS web app. Authenticates via Supabase magic link, loads route data from Supabase, and lets users track completed stages, filter/search routes, sort by travel time, and switch between hiking and cycling modes.
3. **Supabase** — hosted Postgres DB for route data and per-user state (completions, ratings, notes). Auth via magic link (passwordless email).

## Running the scraper

```bash
pip3 install requests
python3 scraper.py                        # default origin: Basel SBB
python3 scraper.py --origin "Zürich HB"  # add times from any SBB station

# Separated modes (recommended workflow):
python3 scraper.py --routes-only          # fetch new/updated route data only, no SBB calls
python3 scraper.py --sbb-only             # enrich SBB times only, skip route scraping
python3 scraper.py --sbb-only --origin "Bern"

# Push to Supabase (after scraping):
python3 scraper.py --import               # requires SUPABASE_URL + SUPABASE_SERVICE_KEY in .env
```

**Workflow:** Run `--routes-only` to pick up newly added routes. Run `--sbb-only` overnight to avoid burning the daily API quota. Run `--import` to push updated data to Supabase.

The scraper is resumable — re-running skips routes already in `hikes.json` and SBB lookups already populated for that origin. Safe to interrupt (Ctrl+C saves progress immediately) and restart.

transport.opendata.ch enforces a **daily request quota**. When hit, the scraper detects the JSON error body, saves progress, and exits cleanly. Re-run the next day to continue. The quota resets at midnight Swiss time.

Progress is also saved every 25 stages during both SBB enrichment and arrival-station enrichment.

### Supabase credentials

Stored in `.env` (gitignored — never commit this):

```
SUPABASE_URL=https://mpgkkmkvzgqkvtoearxp.supabase.co
SUPABASE_SERVICE_KEY=<service_role key>
```

Load with: `export $(cat .env | xargs) && python3 scraper.py --import`

## Viewing the web app

The app requires a local HTTP server (not `file://`) for local dev. The easiest way is via `.claude/launch.json` — start the "Web App" server from Claude Code. Or manually:

```bash
python3 -m http.server 8000
# then open http://localhost:8000
```

The production app is deployed at **https://jclift-dev.github.io/hiking-tracker/** via GitHub Pages. Pushes to `main` deploy automatically.

## Architecture

### Data flow

```
SchweizMobil API  ──────────────────────────────────────────────────┐
  route listing:  GET schweizmobil.ch/api/4/routes/{land}/{category}?lang=en
  route overview: GET schweizmobil.ch/api/4/route_or_segment/{land}/{id}/0?lang=en
  per-segment:    GET schweizmobil.ch/api/4/route_or_segment/{land}/{id}/{seg}?lang=en
  arrival IDs:    GET schweizmobil.ch/api/4/goodtoknow/arrivals/{id}?lang=en
                                                                     ├──► scraper.py ──► hikes.json
transport.opendata.ch  ──────────────────────────────────────────────┘                      │
  GET /v1/connections?from={origin}&to={station}&limit=1                              --import
                                                                                            │
                                                                                            ▼
                                                                                       Supabase DB ──► index.html
```

**How the API was found:** The site is fully JS-rendered. Used Playwright to intercept network requests on `schweizmobil.ch/en/hiking-in-switzerland/route-01`, which revealed the call to `api/4/route_or_segment/hike/1/0`. The `land=hike` value was found by searching the JS bundle for short lowercase strings in the segment component. The route geometry map API (`map.schweizmobil.ch/api/4/query/featuresmultilayers`) does **not** contain stage data — it only has route-level geometry.

### Supabase schema

**`routes`** — shared read-only route data. Primary key: `(id, land)` — both hiking and cycling have routes numbered 1–7, so the composite key is required.

**`stages`** — per-stage data. Unique on `(route_id, land, stage_nr)`. `sbb_times` stored as `jsonb` to preserve the existing dict structure.

**`user_state`** — per-user completions/ratings/notes. Keyed by `(user_id, stage_key)` where `stage_key` is `"land_routeId_stageNr"` (e.g. `"hike_1_3"`).

**`user_preferences`** — per-user settings (selected home station).

RLS policies ensure each user can only read/write their own rows. Routes and stages are public-read (no auth required to query). The scraper uses the `service_role` key (bypasses RLS) for imports.

### hikes.json schema

`hikes.json` is the local scraper output — same data that gets imported to Supabase. The web app reads from Supabase, not this file.

```json
[{
  "route_id": 1,
  "route_type": "national" | "regional",
  "land": "hike" | "cycle",
  "name": "Via Alpina",
  "description": "...",
  "start": "Vaduz (Gaflei, FL)",
  "end": "Montreux",
  "total_km": 390,
  "stages": [{
    "stage_nr": 1,
    "start_name": "Vaduz (Gaflei, FL)",
    "end_name": "Sargans",
    "via": null,
    "dist_km": 28,
    "elev_up": 480,
    "elev_down": 1600,
    "hiking_hrs": 7.5,
    "difficulty": "hiking trail",
    "description": "...",
    "arrival_stations": ["Sargans"],
    "sbb_times": {
      "Basel SBB":  { "start": 187, "end": 45 },
      "Zürich HB":  { "start": 90,  "end": 30 }
    }
  }]
}]
```

`sbb_times` values are `null` (scraper tried, no connection found) or an integer (minutes). `undefined`/missing means never looked up.

`difficulty` values from the API are English text: `"hiking trail"`, `"mountain hiking trail"`, `"demanding mountain hiking trail"`, `"alpine hiking trail"`. `index.html` normalises these via `DIFF_CANON` and `canonDiff()` to clean T1–T4 labels.

### Assets

`assets/` contains five terrain icons used in stage cards for the elevation profile display:

- `icon-1-meadow.svg` — total elevation < 300 m
- `icon-2-rolling-hills.svg` — 300–600 m
- `icon-3-foothills.svg` — 600–1200 m
- `icon-4-alpine.svg` — 1200–2000 m
- `icon-5-summit.svg` — 2000 m+

Each card shows `↑ Xm [icon] ↓ Xm`. Icons are referenced via `<img src="assets/...">` (not inlined) to avoid SVG `id` clashes when multiple cards render on the same page.

A 🛏 icon is shown next to a stage start or end name when `sbb_times[station].start === null` or `.end === null` — indicating no train connection (remote hut, pass, etc.).

### Web app state

All user state is stored in Supabase and synced in real time:

- `user_state` table: `{ stage_key, completed_on, rating, note }` per user
- `user_preferences` table: `{ selected_station }` per user

In-memory: `completed`, `ratings`, `notes`, `selectedStation` — same structure as before, loaded from Supabase on login and written back via `persistStage(key)` / `persistStation(val)` on every change.

On first login, any existing localStorage data (`hikes_done`, `hikes_ratings`, `hikes_notes`) is migrated to Supabase automatically and removed from localStorage.

### Auth

- Magic link (passwordless email) via Supabase Auth
- Sign-ups disabled — users must be invited via **Supabase > Authentication > Users > Invite user**
- Sessions persist for 1 week with auto-refresh (users rarely need to re-authenticate)
- `PROD_URL` constant in `index.html` hardcodes the GitHub Pages URL for magic link redirects

### Route numbering

- National routes: IDs 1–7 (displayed with ★) — only 7 exist as of 2026
- Regional routes: IDs 10–99 (not all numbers exist — scraper skips 404s gracefully)
- Local routes (100+) are intentionally excluded (too many)

### Scraper rate limiting & reliability

- `DELAY = 0.35s` between SchweizMobil requests. `SESSION` sends `Referer: https://www.schweizmobil.ch/` (required to avoid 403s).
- `SBB_DELAY = 2.0s` between transport.opendata.ch requests. The API also has a **daily quota** — the scraper detects this and saves progress before exiting.
- Per-minute 429s are retried once after 30s.
- SchweizMobil requests retry once after 5s on 5xx or network errors (`sm_get()` helper).
- Ctrl+C is handled gracefully at all stages — always saves before exiting.
- Saves every 25 stages during SBB and arrival-station enrichment (not just at end).
- Corrupted `hikes.json` (e.g. interrupted mid-write) is detected on startup, backed up to `hikes.json.bak`, and the scraper starts fresh.

### Scraper cost per origin

All routes are cached after the first `--routes-only` run. Each subsequent `--sbb-only` pass makes ~1–2 SBB API calls per stage (start + end, with reuse when names repeat), so roughly 600–1200 requests per origin. With the daily quota this typically takes 1–2 nights per origin.

### Planned SBB origins

Basel SBB is done. Remaining cities to scrape (run one per night with `--sbb-only`):

- Zürich HB
- Bern
- Lausanne
- Genève
- Luzern
- St. Gallen
- Winterthur
- Biel/Bienne
- Lugano

### Dev servers

`.claude/launch.json` defines two runnable configurations:
- **Web App** — `python3 -m http.server 8000` — serves the app at http://localhost:8000
- **Scraper** — `python3 scraper.py` — run manually with flags as needed
