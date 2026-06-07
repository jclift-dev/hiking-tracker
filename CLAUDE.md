# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Detailed docs

Read these when working on the relevant area — don't load them all upfront:
- **[docs/scrapers.md](docs/scrapers.md)** — CLI flags, prerequisites, per-scraper format notes, rate limits, resumability
- **[docs/architecture.md](docs/architecture.md)** — Supabase schema, hikes.json format, web app state, auth, assets, route numbering
- **[docs/trails.md](docs/trails.md)** — full route lists per land value, OSM trail IDs, deferred & future candidates

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

A hiking tracker for a small group of users. Scraper scripts build `hikes.json` → imported to Supabase → served by `index.html`.

1. **`scraper.py`** — Swiss routes (SchweizMobil API) + SBB travel times (transport.opendata.ch). Outputs `hikes.json`.
2. **`scraper_swcp.py`** — UK South West Coast Path (53 stages) from southwestcoastpath.org.uk with OpenTopoData elevation.
3. **`scraper_whw.py`** — West Highland Way (8 stages) from walkshighlands.co.uk.
4. **`scraper_odd.py`** — Offa's Dyke Path (12 stages) from nationaltrail.co.uk.
5. **`scraper_gr20.py`** — GR20 Corsica (16 stages) from le-gr20.fr.
6. **`scraper_av1.py`** — Alta Via 1 Dolomites (11 stages) from altavia1dolomites.com.
7. **`scraper_malerweg.py`** — Malerweg Saxon Switzerland (8 stages) from saechsische-schweiz.de.
8. **`scraper_nationaltrail.py`** — UK National Trails (South Downs Way, Cotswold Way, Hadrian's Wall, Pembrokeshire Coast Path) from nationaltrail.co.uk.
9. **`scraper_gr.py`** — French GR trails: GR65 Via Podiensis (32 stages) and GR70 Chemin de Stevenson (13 stages).
10. **`scraper_osm.py`** — Long-distance trails via Waymarked Trails API (19+ countries). Data © OpenStreetMap contributors, ODbL 1.0.
11. **`scraper_schwarzwaldverein.py`** — 22 Fernwanderwege from schwarzwaldverein.de (`de-hike`, route_ids 10–31). See docs/scrapers.md for elevation backfill notes.
12. **`index.html`** — Single-file vanilla JS web app: Supabase auth, stage tracking, route filtering/searching.
13. **`test_sbb.py`** — Sanity-checks transport.opendata.ch API for all SBB origins.
14. **`discover_local.py`** — Playwright script to intercept SchweizMobil network traffic. One-off research tool.
15. **`discover_trails.py`** — Builds/maintains `trails_catalog.json` (56k+ entries) of European hiking trail candidates via Overpass + Waymarked Trails APIs. See docs/scrapers.md for CLI and filter_status values.
16. **`enrich_regions.py`** — Adds `country`/`admin1` ISO codes to hikes.json stages for the Europe map. Run after adding European routes, then `--import`.
17. **`make_europe_svg.py`** — One-off: generates `europePaths` JS constant for `index.html` from Natural Earth GeoJSON. Re-run only if SVG region shapes need updating.

## Land values

`{country}-{activity}` (e.g. `ch-hike`). Exception: all UK trails share `land="uk"`. For full route lists and OSM IDs, see **[docs/trails.md](docs/trails.md)**.

| `land`     | Country        | Activity |
|------------|----------------|----------|
| `ch-hike`  | Switzerland    | Hiking   |
| `ch-cycle` | Switzerland    | Cycling  |
| `uk`       | UK             | Hiking   |
| `fr-hike`  | France         | Hiking   |
| `it-hike`  | Italy          | Hiking   |
| `de-hike`  | Germany        | Hiking   |
| `es-hike`  | Spain          | Hiking   |
| `ie-hike`  | Ireland        | Hiking   |
| `pt-hike`  | Portugal       | Hiking   |
| `at-hike`  | Austria        | Hiking   |
| `hu-hike`  | Hungary        | Hiking   |
| `cz-hike`  | Czech Republic | Hiking   |
| `si-hike`  | Slovenia       | Hiking   |
| `nl-hike`  | Netherlands    | Hiking   |
| `be-hike`  | Belgium        | Hiking   |
| `se-hike`  | Sweden         | Hiking   |
| `no-hike`  | Norway         | Hiking   |
| `ee-hike`  | Estonia        | Hiking   |
| `eu-hike`  | Europe (multi) | Hiking   |

## Supabase credentials

Stored in `.env` (gitignored — never commit):

```
SUPABASE_URL=https://mpgkkmkvzgqkvtoearxp.supabase.co
SUPABASE_SERVICE_KEY=<service_role key>
```

Load with: `source .env && python3 scraper.py --import`

## Supabase land CHECK constraint

Update both tables' constraints before importing any new land value:

```sql
ALTER TABLE routes DROP CONSTRAINT routes_land_check;
ALTER TABLE routes ADD CONSTRAINT routes_land_check
  CHECK (land IN ('ch-hike','ch-cycle','uk','fr-hike','de-hike','it-hike','es-hike','ie-hike','pt-hike','eu-hike','at-hike','hu-hike','cz-hike','si-hike','nl-hike','be-hike','se-hike','no-hike','ee-hike'));
ALTER TABLE stages DROP CONSTRAINT stages_land_check;
ALTER TABLE stages ADD CONSTRAINT stages_land_check
  CHECK (land IN ('ch-hike','ch-cycle','uk','fr-hike','de-hike','it-hike','es-hike','ie-hike','pt-hike','eu-hike','at-hike','hu-hike','cz-hike','si-hike','nl-hike','be-hike','se-hike','no-hike','ee-hike'));
```

## Viewing the web app

Requires a local HTTP server (not `file://`). Start via `.claude/launch.json` → "Web App", or:

```bash
python3 -m http.server 8000
# then open http://localhost:8000
```

Production: **https://jclift-dev.github.io/hiking-tracker/** — auto-deploys on push to `main`.

## Dev servers

`.claude/launch.json` defines two runnable configurations:
- **Web App** — `python3 -m http.server 8000` — serves the app at http://localhost:8000
- **Scraper** — `python3 scraper.py` — run manually with flags as needed
