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
10. **`scraper_osm.py`** — Long-distance trails via Waymarked Trails API (19+ countries). Data © OpenStreetMap contributors, ODbL 1.0. CLI: `--only <osm_id>`, `--refresh-trail <osm_id>`, `--skip-elevation`, `--backfill-elevation`, `--backfill-names`, `--backfill-ch-osm-ids` (assigns `_osm_id` to ch-hike routes 1–7 from OSM parent superroutes).
11. **`scraper_schwarzwaldverein.py`** — 22 Fernwanderwege from schwarzwaldverein.de (`de-hike`, route_ids 10–31). See docs/scrapers.md for elevation backfill notes.
12. **`scraper_websites.py`** — Website-only routes (no OSM day-stage hierarchy): Eifelsteig (de-hike 49), Italia Coast to Coast (it-hike 13), Sauerland-Waldroute (de-hike 44, overwrites OSM), Linksrheinischer Jakobsweg (de-hike 50), WestfalenWanderWeg (de-hike 51), Stormarnweg (53), Oberlausitzer Bergweg (54), Werra-Burgen-Steig (55), König-Ludwig-Weg (56), X27 (57), Camino de la Frontera (es-hike 11), Grande Rota Peneda-Gerês (pt-hike 2), Camino Portugués (pt-hike 3, pilgrim.es, Lisboa→Santiago), SNP Trail (sk-hike 1, snptrail.com, hardcoded). CLI: `--only <slug>`, `--refresh`. See docs/scrapers.md for details.
13. **`scraper_e1.py`** — E1 European Long Distance Path (eu-hike, route_id=5, 425 stages, North Cape→Sicily) from hiking-europe.eu. CLI: `--refresh`, `--clear-cache`. Uses `.e1_cache.json` to avoid re-fetching.
14. **`scraper_albverein.py`** — Albverein Hauptwanderwege (de-hike, route_ids 33–41, 52) from wege.albverein.net. CLI: `--only <slug>`, `--refresh`.
15. **`index.html`** — Single-file vanilla JS web app: Supabase auth, stage tracking, route filtering/searching.
16. **`test_sbb.py`** — Sanity-checks transport.opendata.ch API for all SBB origins.
17. **`discover_local.py`** — Playwright script to intercept SchweizMobil network traffic. One-off research tool.
18. **`discover_trails.py`** — Builds/maintains `trails_catalog.json` (56k+ entries) of European hiking trail candidates via Overpass + Waymarked Trails APIs. See docs/scrapers.md for CLI and filter_status values.
19. **`discover_trail_websites.py`** — Three-source pipeline that checks which catalog candidates have day-stage pages on their official websites. Outputs `trail_websites.json` (status="found" = viable; 68 confirmed hits across 896 processed). One-off research tool; re-run to refresh.
20. **`enrich_regions.py`** — Adds `country`/`admin1` ISO codes to hikes.json stages for the Europe map. Run after adding European routes, then `--import`.
21. **`make_europe_svg.py`** — One-off: generates `europePaths` JS constant for `index.html` from Natural Earth GeoJSON. Re-run only if SVG region shapes need updating.

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
| `hr-hike`  | Croatia        | Hiking   |
| `ee-hike`  | Estonia        | Hiking   |
| `sk-hike`  | Slovakia       | Hiking   |
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
  CHECK (land IN ('ch-hike','ch-cycle','uk','fr-hike','de-hike','it-hike','es-hike','ie-hike','pt-hike','eu-hike','at-hike','hu-hike','cz-hike','si-hike','nl-hike','be-hike','se-hike','no-hike','ee-hike','hr-hike','sk-hike'));
ALTER TABLE stages DROP CONSTRAINT stages_land_check;
ALTER TABLE stages ADD CONSTRAINT stages_land_check
  CHECK (land IN ('ch-hike','ch-cycle','uk','fr-hike','de-hike','it-hike','es-hike','ie-hike','pt-hike','eu-hike','at-hike','hu-hike','cz-hike','si-hike','nl-hike','be-hike','se-hike','no-hike','ee-hike','hr-hike','sk-hike'));
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
