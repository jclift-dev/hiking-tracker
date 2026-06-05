# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Git workflow

- **Straight to `main`**: one-file changes, new route scrapes, CSS tweaks, documentation
- **Feature branch**: anything that touches auth flow, `persistStage`/`loadData`, state management, or spans multiple sessions

  ```bash
  git checkout -b feature/<short-description>
  # work, commit
  git push -u origin feature/<short-description>
  gh pr create
  ```

Always push and create a PR for feature branches — don't merge locally.

## What this project is

A hiking tracker for a small group of users, with components:

1. **`scraper.py`** — fetches route and stage data from the SchweizMobil map API and enriches each stage with SBB travel times from multiple Swiss cities via transport.opendata.ch. Outputs `hikes.json` locally and can import to Supabase.
2. **`scraper_swcp.py`** — fetches the 53 day-stages of the UK South West Coast Path from `southwestcoastpath.org.uk` with elevation via OpenTopoData.
3. **`scraper_whw.py`** — fetches the 8 stages of the West Highland Way from `walkshighlands.co.uk`.
4. **`scraper_odd.py`** — fetches the 12 stages of Offa's Dyke Path from `nationaltrail.co.uk`.
5. **`scraper_gr20.py`** — fetches the 16 stages of the GR20 (Corsica) from `le-gr20.fr`.
6. **`scraper_av1.py`** — fetches the 11 stages of the Alta Via 1 (Dolomites) from `altavia1dolomites.com`.
7. **`scraper_malerweg.py`** — fetches the 8 stages of the Malerweg (Saxon Switzerland) from `saechsische-schweiz.de`.
8. **`scraper_nationaltrail.py`** — fetches day-stage data for UK National Trails from `nationaltrail.co.uk`. Covers South Downs Way (route_id=5), Cotswold Way (6), Hadrian's Wall Path (7), and Pembrokeshire Coast Path (8). All `land="uk"`. Includes GPX-based elevation splitting.
9. **`scraper_gr.py`** — fetches French GR trails: GR65 Via Podiensis (32 stages) and GR70 Chemin de Stevenson (13 stages) from podiensis.com and chamina-voyages.com. Also backfills GR20 distances from thepostrace.com.
10. **`scraper_osm.py`** — fetches long-distance trails from OpenStreetMap via the Waymarked Trails API (`hiking.waymarkedtrails.org`). Covers trails in UK, France, Germany, Spain, and Ireland. Data is © OpenStreetMap contributors, ODbL 1.0.
11. **`index.html`** — a single-file vanilla JS web app. Authenticates via Supabase email+password, loads route data from Supabase, and lets users track completed stages, filter/search routes, and switch between countries and activities (hiking/cycling).
12. **`test_sbb.py`** — sanity-checks the transport.opendata.ch API for all planned SBB origins. Run with `python3 test_sbb.py`.
13. **`discover_local.py`** — Playwright script used to intercept SchweizMobil network traffic and discover API endpoints for local routes. One-off research tool.
14. **Supabase** — hosted Postgres DB for route data and per-user state (completions, ratings, notes). Auth via email + password.

## Land value naming convention

The `land` field combines country code and activity: `{country}-{activity}` (e.g. `ch-hike`, `fr-hike`). Exception: UK trails all share `land="uk"` regardless of sub-trail.

| `land`     | Country     | Activity | Routes |
|------------|-------------|----------|--------|
| `ch-hike`  | Switzerland | Hiking   | SchweizMobil national/regional hiking routes (1-7, 10-99) |
| `ch-cycle` | Switzerland | Cycling  | SchweizMobil national/regional cycling routes (1-7, 10-99) |
| `uk`       | UK          | Hiking   | SWCP (53 stages), WHW (8), ODP (12), South Downs Way (9), Cotswold Way (15), Hadrian's Wall Path (6), Pembrokeshire Coast Path (15), Cape Wrath (1), Pennine Way (OSM fallback) |
| `fr-hike`  | France      | Hiking   | GR20 (16 stages, Corsica), GR65 Via Podiensis (32), GR70 Chemin de Stevenson (13), HRP Haute Randonnée Pyrénéenne (1), GR11 (OSM), Camino Primitivo (OSM), GR221 (OSM) |
| `it-hike`  | Italy       | Hiking   | Alta Via 1 (11 stages, Dolomites) |
| `de-hike`  | Germany     | Hiking   | Malerweg (8), Westweg (OSM), Goldsteig Nord+Süd (OSM), Heidschnuckenweg (OSM) |
| `es-hike`  | Spain       | Hiking   | GR11 Senda Pirenaica (OSM), Camino Primitivo (OSM), GR221 Ruta de Pedra en Sec (OSM) |
| `ie-hike`  | Ireland     | Hiking   | Wicklow Way (OSM), Kerry Way (OSM), Dingle Way (OSM), Causeway Coast Way (OSM), Beara Way (OSM), Western Way (OSM) |
| `eu-hike`  | Europe (multi-country) | Hiking | Via Alpina (116 stages, Monaco → Trieste, OSM 20014200) |

## Running the scraper

### Prerequisites

```bash
# Install all dependencies (recommended)
pip3 install -r requirements.txt

# Or install individually as needed:
pip3 install requests
```

### Basic Usage

```bash
python3 scraper.py                        # default origin: Basel SBB
python3 scraper.py --origin "Zürich HB"  # add times from any SBB station

# Separated modes (recommended workflow):
python3 scraper.py --routes-only          # fetch new/updated route data only, no SBB calls
python3 scraper.py --sbb-only             # enrich SBB times only, skip route scraping
python3 scraper.py --sbb-only --origin "Bern"

# Push to Supabase (after scraping):
python3 scraper.py --import               # requires SUPABASE_URL + SUPABASE_SERVICE_KEY in .env
```

### UK South West Coast Path

```bash
pip3 install cloudscraper beautifulsoup4 requests
python3 scraper_swcp.py                 # fetch all 53 stages + elevation
python3 scraper_swcp.py --refresh       # re-fetch everything, including elevation
python3 scraper_swcp.py --limit 3       # smoke test: first N stages only
python3 scraper_swcp.py --skip-elevation  # skip elevation calls (faster)
python3 scraper.py --import             # push everything (Swiss + UK) to Supabase
```

The SWCP scraper writes a single route entry (`route_id=1`, `land="uk"`, `route_type="national"`, `name="South West Coast Path"`) with 53 stages (the itinerary has one non-sequential walk ID — 189 — between stages 5 and 6). It's resumable: re-running skips walks already in `hikes.json` (matched by an internal `_walk_id`). It does no travel-time enrichment — `sbb_times` is `{}` for all UK stages, and the web app's station picker / sort-by-time degrade gracefully. Distances are taken directly from the `(X km)` figure on each page.

**Elevation** (`elev_up` / `elev_down`) is computed per stage via two extra requests:
1. `GET /walksdb/{id}/data/` — returns a GeoJSON `LineString` with the route geometry
2. Sample up to 80 points (ceiling division to stay under the 100-point API cap) and query [OpenTopoData](https://www.opentopodata.org/) SRTM 30m: `GET api.opentopodata.org/v1/srtm30m?locations=lat,lng|...`
3. Cumulative ascent/descent computed with a 2 m noise threshold

OpenTopoData is free with a **1000 req/day quota** (one request per stage = 53 calls per full run). Cached stages with `elev_up=null` are backfilled automatically on the next run without re-scraping the pages.

The site is behind Cloudflare — `cloudscraper` handles the JS challenge automatically. No cookies or tokens needed.

**Workflow:** Run `--routes-only` to pick up newly added routes. Run `--sbb-only` overnight to avoid burning the daily API quota. Run `--import` to push updated data to Supabase.

### West Highland Way

```bash
pip3 install requests beautifulsoup4
python3 scraper_whw.py                # fetch all 8 stages
python3 scraper_whw.py --refresh      # re-fetch everything
python3 scraper_whw.py --limit 3      # smoke test: first N stages only
python3 scraper.py --import           # push everything to Supabase
```

The WHW scraper writes a single route entry (`route_id=2`, `land="uk"`, `route_type="national"`, `name="West Highland Way"`) with 8 stages. Resumable via internal `_slug` field. No elevation (site has no GPX/GeoJSON API). Distances parsed from "X Miles (Y km)" format.

### Offa's Dyke Path

```bash
pip3 install cloudscraper beautifulsoup4
python3 scraper_odd.py               # fetch all 12 stages
python3 scraper_odd.py --refresh     # re-fetch everything
python3 scraper.py --import          # push everything to Supabase
```

The ODP scraper writes a single route entry (`route_id=3`, `land="uk"`, `route_type="national"`, `name="Offa's Dyke Path"`) with 12 stages scraped from a single page on nationaltrail.co.uk. The site is behind Cloudflare; `cloudscraper` handles this. Elevation and duration are `null`.

### GR20 (Corsica, France)

```bash
pip3 install requests beautifulsoup4
python3 scraper_gr20.py              # fetch all 16 stages
python3 scraper_gr20.py --refresh    # re-fetch even if cached
python3 scraper_gr20.py --limit 3    # smoke test
python3 scraper.py --import
```

Source: `https://www.le-gr20.fr/en/pages/profile-stages/` — overview page with links to 16 individual stage pages. The scraper writes `route_id=1`, `land="fr-hike"`. Data per stage: `elev_up`, `elev_down`, `duration_hrs` (elevation/time format varies by page — colon optional). `dist_km` is null (not published per stage). Stages 9–10 (L'Onda→Vizzavona, Vizzavona→Capanelle) have no elevation data on the source pages. Resumable via internal `_url` field. Difficulty hardcoded to `"difficult"` (GR20 is uniformly demanding).

### GR trails (France)

```bash
pip3 install requests beautifulsoup4
python3 scraper_gr.py              # all trails (GR65, GR70, GR20 backfill)
python3 scraper_gr.py --only gr65  # one trail only
python3 scraper_gr.py --only gr70
python3 scraper_gr.py --only gr20  # GR20 distance backfill only
python3 scraper_gr.py --refresh-trail gr65  # re-fetch even if cached (repeatable)
python3 scraper_gr.py --limit 3    # smoke test: first N stages only
python3 scraper.py --import
```

Handles three French GR trails plus a distance backfill:

| Slug  | Trail | route_id | land | Stages | Source |
|-------|-------|----------|------|--------|--------|
| `gr65` | GR65 Via Podiensis (Le Puy-en-Velay → St-Jean-Pied-de-Port) | 2 | `fr-hike` | 32 | podiensis.com |
| `gr70` | GR70 Chemin de Stevenson (Le Puy-en-Velay → Alès) | 3 | `fr-hike` | 13 | chamina-voyages.com |
| `gr20` | GR20 — distance backfill only (existing route_id=1) | 1 | `fr-hike` | 16 | thepostrace.com |

**GR65** (podiensis.com): index table at `/les-etapes` gives stage_nr, start, end, distance; per-stage pages give duration, elev_up, elev_down, and difficulty. Resumable via internal `_url` field on each stage. Difficulty mapped from French ("Facile"→easy, "Moyenne"→moderate, "Difficile"→difficult).

**GR70** (chamina-voyages.com): single-page table with all 13 stages — start/end parsed from "A > B" format, distance, D+, D−. No per-stage subpages; no duration data. Single fetch, no resume needed.

**GR20 distance backfill**: thepostrace.com has a 15-stage table with per-stage distances (le-gr20.fr, the primary source, doesn't publish per-stage distances). Stages 1–10 align cleanly; stages 11–15 are approximate (thepostrace uses different intermediate waypoints in the southern section). Stage 16 (Bavella→Conca) has no match and remains `dist_km=null`.

**To add a new GR trail**: add an entry to `GR_TRAILS` in `scraper_gr.py` with `slug`, `land`, `route_id`, `route_type`, `name`, `description`, `start`, `end`, `total_km`, then add a scrape function and dispatch it in `main()`. All French trails use `land="fr-hike"`. Cross-border or foreign trails (GR5 FR/CH, GR11 ES) need a Supabase CHECK constraint update first — see deferred comment block in the scraper.

**Deferred trails** (cross-border, require Supabase schema change): GR5 Grande Traversée des Alpes (FR/CH), GR11 Pyrenean Traverse (ES). Listed in a comment block at the top of `scraper_gr.py`.

### Alta Via 1 (Dolomites, Italy)

```bash
pip3 install requests beautifulsoup4
python3 scraper_av1.py              # fetch all 11 stages
python3 scraper_av1.py --refresh    # re-fetch even if already cached
python3 scraper.py --import
```

Source: `https://altavia1dolomites.com/alta-via-1-stages/` — single page with all 11 stages in `wp-block-ugb-columns` Gutenberg blocks. The scraper writes `route_id=1`, `land="it-hike"`. Full data per stage: `dist_km`, `elev_up`, `elev_down`, `duration_hrs`.

### Malerweg (Saxon Switzerland, Germany)

```bash
pip3 install requests beautifulsoup4
python3 scraper_malerweg.py              # fetch all 8 stages
python3 scraper_malerweg.py --refresh    # re-fetch even if cached
python3 scraper_malerweg.py --limit 3    # smoke test
python3 scraper.py --import
```

Source: `https://www.saechsische-schweiz.de/malerweg/en/plan-your-trip/stages-of-the-malerweg-trail/stage-{n}` — sequential per-stage URLs. The scraper writes `route_id=1`, `land="de-hike"`. Data parsed from `.fact__item` CSS structure (`fact__number`, `fact__unit`, `fact__text`). Stage start/end names are hardcoded (transport info on pages is inconsistent). Full data per stage: `dist_km`, `elev_up`, `elev_down`. `duration_hrs` is null (published as prose only).

The scraper is resumable — re-running skips routes already in `hikes.json` and SBB lookups already populated for that origin. Safe to interrupt (Ctrl+C saves progress immediately) and restart.

transport.opendata.ch enforces a **daily request quota**. When hit, the scraper detects the JSON error body, saves progress, and exits cleanly. Re-run the next day to continue. The quota resets at midnight Swiss time.

Progress is also saved every 25 stages during both SBB enrichment and arrival-station enrichment.

### UK National Trails (nationaltrail.co.uk)

```bash
pip3 install requests beautifulsoup4 cloudscraper
python3 scraper_nationaltrail.py              # all 4 trails
python3 scraper_nationaltrail.py --only sdw   # South Downs Way
python3 scraper_nationaltrail.py --only cw    # Cotswold Way
python3 scraper_nationaltrail.py --only hwp   # Hadrian's Wall Path
python3 scraper_nationaltrail.py --only pcp   # Pembrokeshire Coast Path
python3 scraper_nationaltrail.py --refresh    # re-fetch even if cached
python3 scraper.py --import
```

Covers `land="uk"` route_ids 5–8. All stages on a single route page per trail — no individual stage URLs exist, so `smUrl` links to the trail's route description page. The site is behind Cloudflare; `cloudscraper` handles this.

| route_id | Trail | Stages | Source |
|---|---|---|---|
| 5 | South Downs Way (Winchester → Eastbourne) | 9 | nationaltrail.co.uk |
| 6 | Cotswold Way (Chipping Campden → Bath) | 15 | nationaltrail.co.uk |
| 7 | Hadrian's Wall Path (Wallsend → Bowness-on-Solway) | 6 | nationaltrail.co.uk |
| 8 | Pembrokeshire Coast Path (St Dogmaels → Amroth) | 15 | nationaltrail.co.uk |

**Heading formats vary:** South Downs Way and Cotswold Way use `"Start to End – X miles (Y km)"` with the distance in the parent element; Pembrokeshire uses `"Start to End X miles (Y km)"` (no dash before miles); Hadrian's Wall has no per-section distances (dist_km is null for all 6 stages). The parser handles all three automatically. `elev_up`/`elev_down` and `duration_hrs` are null (not published by the site).

### OSM trails (via Waymarked Trails)

```bash
pip3 install requests
python3 scraper_osm.py                          # full run (all trails in catalog)
python3 scraper_osm.py --limit 2               # smoke test: first 2 trails only
python3 scraper_osm.py --only 4080347          # one trail by OSM relation ID
python3 scraper_osm.py --refresh-trail 4080347 # re-fetch a specific trail (repeatable)
python3 scraper_osm.py --skip-elevation        # skip OpenTopoData calls (faster)
python3 scraper.py --import
```

Source: `https://hiking.waymarkedtrails.org/api/v1/details/relation/{osm_id}` — the Waymarked Trails API exposes one-level subroutes as day stages. Trail data is © OpenStreetMap contributors, ODbL 1.0 (attribution link in `index.html` footer).

**Trail catalog** (defined in `TRAILS` list in `scraper_osm.py`):

| OSM ID    | `land`    | route_id | Trail                          |
|-----------|-----------|----------|-------------------------------|
| 4080347   | `uk`      | 4        | Pennine Way                   |
| 77976     | `uk`      | 5        | South Downs Way — OSM fallback (superseded by scraper_nationaltrail.py) |
| 65239     | `uk`      | 6        | Cotswold Way — OSM fallback (superseded by scraper_nationaltrail.py) |
| 38791     | `uk`      | 7        | Hadrian's Wall Path — OSM fallback (superseded by scraper_nationaltrail.py) |
| 77964     | `uk`      | 8        | Pembrokeshire Coast Path — OSM fallback (superseded by scraper_nationaltrail.py) |
| 9327615   | `uk`      | 9        | Cape Wrath Trail (single stage) |
| 8386002   | `fr-hike` | 4        | Haute Randonnée Pyrénéenne    |
| 62900     | `de-hike` | 2        | Westweg                       |
| 61185     | `de-hike` | 3        | Goldsteig-Südroute             |
| 3300718   | `de-hike` | 4        | Goldsteig-Nordroute            |
| 19995501  | `de-hike` | 5        | Heidschnuckenweg               |
| 8865914   | `es-hike` | 1        | Senda Pirenaica (GR11)         |
| 19298101  | `es-hike` | 2        | Camino Primitivo               |
| 16358020  | `es-hike` | 3        | GR 221 Ruta de Pedra en Sec    |
| 2740      | `ie-hike` | 1        | Wicklow Way (single stage)     |
| 183744    | `ie-hike` | 2        | The Kerry Way (single stage)   |
| 21664     | `ie-hike` | 3        | The Dingle Way (single stage)  |
| 1085994   | `ie-hike` | 4        | Causeway Coast Way (single stage) |
| 2989585   | `ie-hike` | 5        | Beara Way (single stage)       |
| 14702338  | `ie-hike` | 6        | Western Way (single stage)     |

**Resumable:** re-running skips fully-cached trails (matched by `_osm_id` on each stage). `--refresh-trail <id>` re-fetches even if cached.

**Elevation:** OpenTopoData SRTM30m, 1000 req/day quota (~1 call per stage). Detects quota exhaustion and saves progress. Stage variants (OSM names containing "Variante") and micro-stages (< 1 km by parent-reported length) are filtered automatically.

**Adding a new trail:** look up the OSM relation ID on `hiking.waymarkedtrails.org`, check it has subroutes at one level (`/api/v1/details/relation/{id}` → `.route.main[].route_type == "route"`), add to `TRAILS` in `scraper_osm.py`, and add the new `smUrl` / `sourceLabel` entries in `index.html` if needed.

**Deferred** (no viable day-stage subroutes at one level): GR34 Chemin des Douaniers (23×~90 km), GR5 Grande Traversée des Alpes (15×~300 km), Rennsteig, Cleveland Way, Alta Via 2, GR54, Camino del Norte (5×~180 km).

**Future candidates** (not yet probed — check OSM relation before adding):

| Trail | Country | Notes |
|---|---|---|
| Offa's Dyke (OSM) | `uk` | Already have ODP from nationaltrail.co.uk; skip unless replacing |
| GR10 Pyrenean Traverse | `fr-hike` | French side of the Pyrenees; no clean parent relation identified yet |
| Tour du Mont Blanc | `fr-hike` / `it-hike` | Circular; may not have day-stage subroutes |
| Via Francigena | `it-hike` | Canterbury → Rome; check if Italian section has subroutes |
| Lycian Way | (new `tr-hike`) | Turkey; needs new land value |
| Camino Portugués | `es-hike` | Likely has subroutes; worth checking |
| Camino Francés | `es-hike` | Most popular Camino; parent relation not yet identified |
| E1 / E4 / E8 (European paths) | varies | Long multi-country paths; likely too coarse |
| Rothaarsteig | `de-hike` | Sauerland ridge trail; check for subroutes |
| Rheinsteig | `de-hike` | Rhine gorge trail; check for subroutes |
| Rennsteig | `de-hike` | Currently deferred (flat relation — 0 subroutes) |

To check a candidate: `curl "https://hiking.waymarkedtrails.org/api/v1/details/relation/{id}" | python3 -m json.tool | grep -E '"route_type"|"length"'` — look for 10–40 children each 5–40 km.

### Supabase credentials

Stored in `.env` (gitignored — never commit this):

```
SUPABASE_URL=https://mpgkkmkvzgqkvtoearxp.supabase.co
SUPABASE_SERVICE_KEY=<service_role key>
```

Load with: `export $(cat .env | xargs) && python3 scraper.py --import`

### Supabase land CHECK constraint

The `routes` and `stages` tables have a CHECK constraint on the `land` column. After adding new land values, update both constraints before importing:

```sql
ALTER TABLE routes DROP CONSTRAINT routes_land_check;
ALTER TABLE routes ADD CONSTRAINT routes_land_check
  CHECK (land IN ('ch-hike','ch-cycle','uk','fr-hike','de-hike','it-hike','es-hike','ie-hike'));
ALTER TABLE stages DROP CONSTRAINT stages_land_check;
ALTER TABLE stages ADD CONSTRAINT stages_land_check
  CHECK (land IN ('ch-hike','ch-cycle','uk','fr-hike','de-hike','it-hike','es-hike','ie-hike'));
```

**One-time migration (Swiss land rename):** In 2026-05 the Swiss land values were renamed from `hike`/`cycle` to `ch-hike`/`ch-cycle`. The Supabase migration SQL is:
```sql
UPDATE routes SET land = 'ch-hike'  WHERE land = 'hike';
UPDATE routes SET land = 'ch-cycle' WHERE land = 'cycle';
UPDATE stages SET land = 'ch-hike'  WHERE land = 'hike';
UPDATE stages SET land = 'ch-cycle' WHERE land = 'cycle';
```
Run this before updating the CHECK constraint and importing the renamed data.

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

**`routes`** — shared read-only route data. Primary key: `(id, land)` — both hiking and cycling have routes numbered 1–7, so the composite key is required. The `land` column has a CHECK constraint (see above). Adding a new land value requires updating that constraint first via the Supabase SQL editor.

**`stages`** — per-stage data. Unique on `(route_id, land, stage_nr)`. `sbb_times` stored as `jsonb` to preserve the existing dict structure. The `land` column has the same CHECK constraint as `routes`.

**`user_state`** — per-user completions/ratings/notes. Keyed by `(user_id, stage_key)` where `stage_key` is `"land_routeId_stageNr"` (e.g. `"ch-hike_1_3"`).

**`user_preferences`** — per-user settings (selected home station).

RLS policies ensure each user can only read/write their own rows. Routes and stages are public-read (no auth required to query). The scraper uses the `service_role` key (bypasses RLS) for imports.

**`withTimeout(promise, ms)`** — all Supabase queries in `loadData()` and `loadUserState()` are wrapped with this helper (10 s timeout). Any new queries added to these functions should follow the same pattern; unwrapped queries will hang indefinitely if the network is unavailable after PC wake.

### hikes.json schema

`hikes.json` is the local scraper output — same data that gets imported to Supabase. The web app reads from Supabase, not this file.

```json
[{
  "route_id": 1,
  "route_type": "national" | "regional",
  "land": "ch-hike" | "ch-cycle" | "uk" | "fr-hike" | "it-hike" | "de-hike",
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
    "duration_hrs": 7.5,
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

`difficulty` values from the Swiss API are English text: `"hiking trail"`, `"mountain hiking trail"`, `"demanding mountain hiking trail"`, `"alpine hiking trail"`. `index.html` normalises these via `DIFF_CANON` and `canonDiff()` to clean T1–T4 labels.

For `land="uk"` stages, difficulty is `"easy"`, `"moderate"`, or `"challenging"` — read from the primary-grade image filename on each walksdb page (e.g. `challenging-walk.png`). Walking time is not published by the SWCP site, so `duration_hrs` is `null` for all UK stages.

`_walk_id` in hikes.json is an internal scraper field (not imported to Supabase). `index.html` contains a static `SWCP_WALK_IDS` array (53 entries) that maps `stage_nr → walksdb ID` so the "View on SWCP ↗" link can go directly to the stage page. If the SWCP ever renumbers stages, update this array alongside a re-scrape.

### Assets

`assets/` contains five terrain icons used in stage cards for the elevation profile display:

- `icon-1-meadow.svg` — total elevation < 300 m
- `icon-2-rolling-hills.svg` — 300–600 m
- `icon-3-foothills.svg` — 600–1200 m
- `icon-4-alpine.svg` — 1200–2000 m
- `icon-5-summit.svg` — 2000 m+

Each card shows `↑ Xm [icon] ↓ Xm`. Icons are referenced via `<img src="assets/...">` (not inlined) to avoid SVG `id` clashes when multiple cards render on the same page.

A 🛏 icon is shown next to a stage start or end name when `sbb_times[station].start === null` or `.end === null` — indicating no train connection (remote hut, pass, etc.).

Canton badges (`.canton-badge`) are shown on Swiss stage cards. Flag images are loaded from `https://schweizmobil.ch/img/footer/{code.toLowerCase()}.svg` — an external URL with no SLA. The `onerror` handler hides the `<img>` if it fails, so badge text still shows. Only present on `ch-hike` / `ch-cycle` stages (`cantons` field is empty for non-Swiss routes).

### Web app state

All user state is stored in Supabase and synced in real time:

- `user_state` table: `{ stage_key, completed_on, rating, note, wishlist, updated_at }` per user
- `user_preferences` table: `{ selected_station, updated_at }` per user

In-memory: `completed`, `ratings`, `notes`, `wishlist`, `selectedStation` — loaded from Supabase on login and written back via `persistStage(key)` / `persistStation(val)` on every change. `wishlist` is a ♡/♥ toggle on each stage (stored as a boolean in `user_state.wishlist`); wishlisted stages appear in the "Wishlist" filter tab.

On first login, any existing localStorage data (`hikes_done`, `hikes_ratings`, `hikes_notes`) is migrated to Supabase automatically and removed from localStorage.

### Auth

- Email + password via Supabase Auth (`signInWithPassword`)
- Sign-ups disabled — users must be invited via **Supabase > Authentication > Users > Invite user**
- Password reset emails use `resetPasswordForEmail` — `PROD_URL` / `APP_URL` constants in `index.html` set the redirect target (GitHub Pages URL in prod, `localhost` in dev)
- Sessions persist for 1 week with auto-refresh; expiry shows "Your session has expired" message rather than silently redirecting
- **Escape hatch**: `/?reset` clears `localStorage` + `sessionStorage` and reloads to a clean login screen. Linked in the login form as "Stuck? Clear session & reload".
- **Sleep/wake recovery**: After a PC lock or sleep, the Supabase token auto-refresh can hang if the network isn't immediately up, blocking all queued DB queries indefinitely. `_recoverIfStuck()` listens on `visibilitychange` and `online` events — if `_booting` has been true for >20 s when the page becomes visible again, it forces a clean reload. Boot sequence guard flags: `_booting` (prevents concurrent boots), `_bootStartedAt` (tracks when boot started, for stale-boot detection), `_loggingOut` (blocks auth events during logout), `_inPasswordRecovery`.

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
- **SBB fuzzy-prefix guard**: the transport.opendata.ch API does prefix-style fuzzy matching on destination names. The scraper rejects results where the matched station's first word *extends* the query's first word (e.g. query `"Binn"` → matched `"Binningen Oberdorf"` is rejected; `"Binn, Dorf"` is accepted). This prevents short village names from resolving to nearby city suburbs.

### Scraper cost per origin

All routes are cached after the first `--routes-only` run. Each subsequent `--sbb-only` pass makes ~1–2 SBB API calls per stage (start + end, with reuse when names repeat), so roughly 600–1200 requests per origin. With the daily quota this typically takes 1–2 nights per origin.

### SBB Travel Time Completion Status

Use `python3 scraper.py --sbb-all` to process all origins in sequence (run in `tmux` so it survives laptop sleep). It skips complete origins and processes incomplete ones shortest-first.

**Complete (1179 Swiss stages each):**
Basel SBB, Bern, Biel/Bienne, Chur, Genève, Interlaken Ost, Lausanne, Lugano, Luzern, St. Gallen, Zürich HB

**Incomplete:**
- Thun — 701/1179 stages (as of 2026-06-04)

> **Note:** Basel SBB shows 1332 stages due to counting methodology; all 11 planned Swiss origins plus Thun are effectively complete for the 1179 Swiss hiking/cycling stages. Thun is the only origin with remaining work.

### Dev servers

`.claude/launch.json` defines two runnable configurations:
- **Web App** — `python3 -m http.server 8000` — serves the app at http://localhost:8000
- **Scraper** — `python3 scraper.py` — run manually with flags as needed
