# Roadmap

What to add next, what's blocked, and what needs investigation.

For the full list of what's already live, see [docs/trails.md](trails.md).

---

## Easy wins — ready to scrape now

OSM routes with verified day-stage hierarchies. All can be added with `scraper_osm.py --only <osm_id> --skip-elevation`, then backfill + enrich + import.

| OSM ID | Trail | Land | route_id | Stages | Notes |
|--------|-------|------|----------|--------|-------|
| 8928052 | Transcaucasian Trail | `eu-hike` | 17 | ~94 | GE/AM/AZ — needs GE/AM/AZ added to SVG map (re-run `make_europe_svg.py` with updated Natural Earth data or add polygons manually) |
| 16742541 | Hugenotten und Waldenserweg | `de-hike` | 74 | ~23 | Basel/Geneva → Schaffhausen/Mosbach; max ~14km per stage |
| 4830796 | Camino Natural del Guadiana | `es-hike` | 35 | ~44 | PT/ES cross-border; max ~39km per stage |
| 3802149 | La Senda del Duero | `es-hike` | 36 | ~42 | PT/ES; max ~46km per stage |

### Catalog entries to investigate

These OSM IDs appeared in `discover_trails.py` with plausible stage counts but haven't been examined in detail:

| OSM ID | Next step |
|--------|-----------|
| 7029512 | Check `https://hiking.waymarkedtrails.org/#route?id=7029512` for stage count and max stage length |
| 5576339 | Check Waymarked Trails |
| 7125614 | Check Waymarked Trails |
| 7332771 | Check Waymarked Trails |
| 7029513 | Check Waymarked Trails |

---

## Website scrapers — no viable OSM day-stage data

These trails have day-stage pages on an official website but the OSM data is too coarse to use.

| Trail | Land | route_id | Source | Notes |
|-------|------|----------|--------|-------|
| Sauerland-Waldroute (full) | `de-hike` | 44 | sauerland-waldroute.de | 19 stages published but only 7 in static HTML; remaining 12 are JS-rendered — consider Playwright scrape |
| GR10 Pyrenean Traverse | `fr-hike` | TBD | None found | Paywall-only (FFRandonnée topoguide); all ~15 candidate free sources are 404 or overview-only. Permanently deferred until a free per-stage source appears |
| E11 Germany section | `de-hike` | TBD | TBD | 8 flat OSM state-level relations, no subroutes; would need website scraper |
| E11 Poland section | `eu-hike` | TBD | TBD | 1 flat OSM relation; would need website scraper |
| Pyrénées NP Geotrek | `fr-hike` | TBD | geotrek.fr (PNRNP instance?) | Geotrek API endpoint not yet found — investigate `https://geotrek.pyrenees-parcnational.fr/` |
| Cévennes NP Geotrek | `fr-hike` | TBD | geotrek.cevennes-parcnational.net | Geotrek API endpoint not yet found |
| Serbian/Bulgarian/Greek/Turkish E-paths | `eu-hike` | TBD | TBD | OSM is flat (sections, no day stages); would need national trail websites |

---

## Infrastructure / one-off tasks

- **SVG map** — if adding routes in GE/AM/AZ (Transcaucasian Trail), run `make_europe_svg.py` with updated Natural Earth GeoJSON (currently those 3 countries have no SVG polygon) and update the `europePaths` JS constant in `index.html`.
- **ee-hike:4 ROUTE_OSM_IDS** — already populated (`11346181`) and route is live. No action needed.
- **Via Alpina overlap links** — ✓ Done. eu-hike:1 shares 14 OSM stage IDs with ch-hike:1 (stages 2–15 on the Swiss section); 170 total cross-route shared `osm_id` pairs across the dataset. `buildLinkedStageMap()` handles these automatically at boot.
- **Nordkalottruta stage links** — eu-hike:6 likely overlaps with Kungsleden (se-hike:5) and Nordland (no-hike:2); check OSM IDs or add link_keys.
- **Ireland OSM** — all 6 ie-hike routes are currently single-stage flat OSM; re-check periodically if day stages are added.
- **discover_trails --recheck-large-stages** — run to get accurate day-stage counts for multi-section candidates in `trails_catalog.json`.

---

## Deferred / blocked

| Trail | Reason |
|-------|--------|
| Via Alpina Purple (OSM 271352) | Abandoned by via-alpina.org 2024 — do not scrape |
| Via Alpina Blue (OSM 2389235) | Abandoned by via-alpina.org 2024 — do not scrape |
| Via Alpina Yellow (OSM 2122176) | Abandoned by via-alpina.org 2024 — do not scrape |
| GR10 Pyrenean Traverse | No free per-stage source (see above) |
| GR34 Chemin des Douaniers | OSM 7790332, 23 coarse unnamed sections ~90km each |
| GR5 Grande Traversée des Alpes | OSM 18308154, coarse sections only |
| Zentralalpenweg 02 | 8 OSM coarse sections ~143km each |
| Kaiserweg (Harz) | Official site dead/parked 2026-06-16; Harz portal presents it as one 110km tour, no stages |
| Via Dinarica (White Trail) | OSM 4690755 flat, no day-stage subroutes |
| E4 Serbia/Bulgaria/Greece | OSM flat (sections only) |
| Lycian Way (Turkey) | OSM 51855 flat; cultureroutesinturkey.com has no per-stage pages |
| St. Paul's Trail (Turkey) | OSM 569620 flat; no per-stage pages found |
| Querweg Freiburg-Bodensee | OSM 10180 has 68 "stages" at max 3km — these are trail segments, not day stages |
| South West Coast Path | OSM 2376086 (52 stages) would duplicate uk:1 already scraped from southwestcoastpath.org.uk |
