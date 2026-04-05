# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

A personal Swiss hiking tracker with two components:

1. **`scraper.py`** — fetches route and stage data from the SchweizMobil map API, scrapes stage names from the website, and enriches each stage with SBB travel time from Basel SBB via transport.opendata.ch. Outputs `hikes.json`.
2. **`index.html`** — a single-file vanilla JS web app that reads `hikes.json` and lets you track completed stages, filter/search routes, and sort by travel time from Basel.

## Running the scraper

```bash
pip3 install requests
python3 scraper.py
```

The scraper is resumable — re-running skips routes already in `hikes.json` that have stages (matched by `route_type` + `route_id`). SBB lookups are also skipped if `sbb_mins` is already populated on a stage. Safe to interrupt and restart.

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
  GET /v1/connections?from=Basel+SBB&to={station}&limit=1
```

**How the API was found:** The site is fully JS-rendered. Used Playwright to intercept network requests on `schweizmobil.ch/en/hiking-in-switzerland/route-01`, which revealed the call to `api/4/route_or_segment/hike/1/0`. The `land=hike` value was found by searching the JS bundle for short lowercase strings in the segment component. The route geometry map API (`map.schweizmobil.ch/api/4/query/featuresmultilayers`) does **not** contain stage data — it only has route-level geometry.

### hikes.json schema

```json
[{
  "route_id": 1,
  "route_type": "national" | "regional",
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
    "sbb_station": "Vaduz",
    "sbb_mins": 187
  }]
}]
```

`difficulty` values from the API are English text: `"hiking trail"`, `"mountain hiking trail"`, `"demanding mountain hiking trail"`, `"alpine hiking trail"`. `index.html`'s `diffClass()` maps these to colour badges.

### Web app state

Completion state is stored in `localStorage` under the key `hikes_done` as `{ "routeId_stageNr": "date string" }`. There is no backend — everything is local to the browser.

### Route numbering

- National routes: IDs 1–7 (displayed with ★) — only 7 exist as of 2026
- Regional routes: IDs 10–99 (not all numbers exist — scraper skips 404s gracefully)
- Local routes (100+) are intentionally excluded (too many)

### Scraper rate limiting

`DELAY = 0.35` seconds between requests. The `SESSION` object reuses HTTP connections and sends a `Referer: https://www.schweizmobil.ch/` header (required to avoid 403s on some endpoints).

### Scraper cost per full run

Each route fetches 1 overview call + N individual segment calls (one per stage). National routes average ~20 stages, regional ~6–10. Plus 1 SBB call per stage. A full run is roughly 600–800 HTTP requests.
