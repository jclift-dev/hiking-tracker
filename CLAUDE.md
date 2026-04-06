# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

A personal Swiss hiking tracker with two components:

1. **`scraper.py`** — fetches route and stage data from the SchweizMobil map API and enriches each stage with SBB travel times from multiple Swiss cities via transport.opendata.ch. Outputs `hikes.json`.
2. **`index.html`** — a single-file vanilla JS web app that reads `hikes.json` and lets you track completed stages, filter/search routes, sort by travel time from a selected home station, and switch between hiking and cycling modes.

## Running the scraper

```bash
pip3 install requests
python3 scraper.py                        # default origin: Basel SBB
python3 scraper.py --origin "Zürich HB"  # any other SBB station
```

The scraper is resumable — re-running skips routes already in `hikes.json` and SBB lookups already populated for that origin. Safe to interrupt and restart.

transport.opendata.ch enforces a **daily request quota**. When hit, the scraper detects the JSON error body, saves progress, and exits cleanly. Re-run the next day to continue. The quota resets at midnight Swiss time.

## Viewing the web app

The web app fetches `hikes.json` via `fetch()`, so it requires a local HTTP server (not `file://`):

```bash
python -m http.server 8000
# then open http://localhost:8000
```

## Architecture

### Data flow

```
SchweizMobil API  ──────────────────────────────────────────────────┐
  route overview: GET schweizmobil.ch/api/4/route_or_segment/hike/{id}/0?lang=en
  per-segment:    GET schweizmobil.ch/api/4/route_or_segment/hike/{id}/{seg}?lang=en
                                                                     ├──► scraper.py ──► hikes.json ──► index.html
transport.opendata.ch  ──────────────────────────────────────────────┘
  GET /v1/connections?from={origin}&to={station}&limit=1
```

**How the API was found:** The site is fully JS-rendered. Used Playwright to intercept network requests on `schweizmobil.ch/en/hiking-in-switzerland/route-01`, which revealed the call to `api/4/route_or_segment/hike/1/0`. The `land=hike` value was found by searching the JS bundle for short lowercase strings in the segment component. The route geometry map API (`map.schweizmobil.ch/api/4/query/featuresmultilayers`) does **not** contain stage data — it only has route-level geometry.

### hikes.json schema

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
    "sbb_times": {
      "Basel SBB":  { "start": 187, "end": 45 },
      "Zürich HB":  { "start": 90,  "end": 30 }
    }
  }]
}]
```

`sbb_times` is a dict keyed by origin station name. Each value has `start` (mins from origin to stage start) and `end` (mins to stage end). Either can be `null` if the station wasn't found. Values are added incrementally by running the scraper with different `--origin` flags.

`difficulty` values from the API are English text: `"hiking trail"`, `"mountain hiking trail"`, `"demanding mountain hiking trail"`, `"alpine hiking trail"`. `index.html` normalises these via `DIFF_CANON` and `canonDiff()` to clean T1–T4 labels.

### Web app state

- Completion state: `localStorage` key `hikes_done` → `{ "land_routeId_stageNr": "date string" }`
- Ratings: `localStorage` key `hikes_ratings` → `{ "land_routeId_stageNr": 1–5 }`
- Notes: `localStorage` key `hikes_notes` → `{ "land_routeId_stageNr": "text" }`
- Selected home station: `localStorage` key `hikes_station`

There is no backend — everything is local to the browser.

### Route numbering

- National routes: IDs 1–7 (displayed with ★) — only 7 exist as of 2026
- Regional routes: IDs 10–99 (not all numbers exist — scraper skips 404s gracefully)
- Local routes (100+) are intentionally excluded (too many)

### Scraper rate limiting

- `DELAY = 0.35s` between SchweizMobil requests. `SESSION` sends `Referer: https://www.schweizmobil.ch/` (required to avoid 403s).
- `SBB_DELAY = 2.0s` between transport.opendata.ch requests. The API also has a **daily quota** — the scraper detects this and saves progress before exiting.
- Per-minute 429s are retried once after 30s.

### Scraper cost per origin

All 479 routes are cached after the first run. Each subsequent `--origin` pass makes ~1–2 SBB API calls per stage (start + end, with reuse when names repeat), so roughly 600–1200 requests per origin. With the daily quota this typically takes 1–2 nights per origin.
