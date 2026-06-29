# Roadmap

What to add next, what's blocked, and what needs investigation.

For the full list of what's already live, see [docs/trails.md](trails.md).

---

## Easy wins — ready to scrape now

OSM routes with verified day-stage hierarchies. All can be added with `scraper_osm.py --only <osm_id> --skip-elevation`, then backfill + enrich + import.

| OSM ID | Trail | Land | route_id | Stages | Notes |
|--------|-------|------|----------|--------|-------|
| 8928052 | Transcaucasian Trail | `eu-hike` | 18 | 94 | ✓ Added 2026-06-29. Lake Arpi→Meghri, AM. SVG map extended to LON_MAX=52 to include GE/AM/AZ. |
| 16742541 | Hugenotten und Waldenserweg | `de-hike` | 74 | 23 | ✓ Added 2026-06-28. Baden→Schaffhausen. |
| 4830796 | Camino Natural del Guadiana | `es-hike` | 35 | 44 | ✓ Added 2026-06-28. Laguna Blanca→Ayamonte, ES/PT. |
| 3802149 | La Senda del Duero | `es-hike` | 36 | 42 | ✓ Added 2026-06-28. Fuentes del Duero→Vega Terrón. |

### Catalog entries to investigate

These OSM IDs appeared in `discover_trails.py` with plausible stage counts but haven't been examined in detail:

| OSM ID | Trail | Verdict |
|--------|-------|---------|
| 7029512 | Sentiero Italia — Lombardia (D00), 60 stages | ✓ Added as it-hike:57 (2026-06-29). |
| 7125614 | Sentiero Italia — Calabria (U00), 32 stages | ✓ Added as it-hike:60 (2026-06-29). |
| 7332771 | Sentiero Italia — Friuli Venezia Giulia (A00), 29 stages | ✓ Added as it-hike:59 (2026-06-29). |
| 7029513 | Sentiero Italia — Trentino Alto Adige (C00), 30 stages | ✓ Added as it-hike:58 (2026-06-29). |
| 5576339 | Kuststigen (SE/NO coastal path, Göteborg → Oslo), 39 stages | ✓ Added as eu-hike:17. Scraper split the 42km outlier at level-2. |

---

## UK cycling routes — added 2026-06-28

4 routes added as `uk-cycle` land value using hardcoded stage data in `scraper_websites.py` (UK cycling routes on cycling.waymarkedtrails.org have no day-stage subroutes — only unnamed way fragments).

| Slug | Trail | route_id | Stages | Notes |
|------|-------|----------|--------|-------|
| `sea-to-sea` | C2C Sea to Sea | 1 | 6 | NCN 71, Whitehaven→Sunderland |
| `way-of-the-roses` | Way of the Roses | 2 | 7 | Morecambe→Bridlington |
| `hadrians-cycleway` | Hadrian's Cycleway | 3 | 6 | NCN 72, Ravenglass→South Shields |
| `lon-las-cymru` | Lôn Las Cymru | 4 | 9 | NCN 8, Holyhead→Cardiff |

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

- **SVG map** — ✓ Done (2026-06-29). GE/AM/AZ added to `make_europe_svg.py` and `europePaths` regenerated for Transcaucasian Trail. Viewport extended to LON_MAX=52, SVG_W=1500.
- **Via Alpina overlap links** — ✓ Done. eu-hike:1 shares 14 OSM stage IDs with ch-hike:1 (stages 2–15 on the Swiss section); 170 total cross-route shared `osm_id` pairs across the dataset. `buildLinkedStageMap()` handles these automatically at boot.
- **Swiss OSM superroute linking** — ✓ Done (2026-06-28). 28 multi-stage ch-hike routes and 83 single-stage routes linked to OSM. 390 Swiss stages have `_osm_id`. See `docs/osm-superroute-status.md` for 3 count-mismatch routes and 50 routes with no OSM superroute (both need OSM fixes before they can be linked).
- **Nordkalottruta stage links** — ✓ Done. 18 shared OSM IDs confirmed: 14 with Nordland (no-hike:2, stages 24–37) and 4 with Kungsleden (se-hike:5, stages 1–4). All auto-linked via `buildLinkedStageMap()`.
- **Ireland OSM** — all 6 ie-hike routes are currently single-stage flat OSM; re-check periodically if day stages are added.
- **discover_trails --recheck-large-stages** — ✓ Done (2026-06-29). Found 12 new viable candidates; all added.
- **Sentiero Italia missing regions** — 12 regional superroutes exist in OSM out of Italy's 20 regions. 11 are in the app (it-hike:10/29/30/57–67); Puglia (R00, OSM 9290765) was scraped 2026-06-29 and is it-hike:66. Missing regions have only individual Tappa stage relations, no assembled superroute: Piemonte (E00), Valle d'Aosta (F00), Emilia-Romagna (H00), Toscana, Umbria, Marche, Campania, Basilicata, Sicilia. Add when OSM mappers create the regional superroutes.
- **OSM stage splits needed** — several added routes have stages longer than ideal (~30–44km) that would benefit from a mapper splitting them in OSM: Limeswanderweg de-hike:75 (max 44km), Camino Lituano lt-hike:2 (max 34km), Via Matildica del Volto Santo it-hike:63 (max 35km), Svatojakubská cesta cz-hike:4 (max 33km). Re-scrape once splits appear in OSM.
- **Dutch "alle varianten" superroutes** — several nl-hike routes have an OSM "alle varianten" superroute wrapping the main trail plus side variants (e.g. Trekvogelpad 532494 → superroute 10879005, Maarten van Rossumpad 8435936 → 11141874, Marskramerpad 2801085 → 13506168, Pieterpad 312993+156951 → 7973533). We intentionally use the main sub-route IDs in `ROUTE_OSM_IDS` — the superroutes include unmapped variant branches and would show more than what's in the app.

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
