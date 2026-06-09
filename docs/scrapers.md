# Scraper docs

CLI flags, prerequisites, per-scraper format notes, rate limits, resumability.

## Prerequisites

```bash
# Install all dependencies (recommended)
pip3 install -r requirements.txt

# Or install individually as needed:
pip3 install requests
```

## Swiss routes — scraper.py

```bash
python3 scraper.py                        # default origin: Basel SBB
python3 scraper.py --origin "Zürich HB"  # add times from any SBB station

# Separated modes (recommended workflow):
python3 scraper.py --routes-only          # fetch new/updated route data only, no SBB calls
python3 scraper.py --sbb-only             # enrich SBB times only, skip route scraping
python3 scraper.py --sbb-only --origin "Bern"
python3 scraper.py --sbb-all              # process all origins in sequence (run in tmux)

# Push to Supabase (after scraping):
python3 scraper.py --import               # requires SUPABASE_URL + SUPABASE_SERVICE_KEY in .env
```

The scraper is resumable — re-running skips routes already in `hikes.json` and SBB lookups already populated for that origin. Safe to interrupt (Ctrl+C saves progress immediately) and restart.

transport.opendata.ch enforces a **daily request quota**. When hit, the scraper detects the JSON error body, saves progress, and exits cleanly. Re-run the next day. The quota resets at midnight Swiss time. Progress is also saved every 25 stages during both SBB enrichment and arrival-station enrichment.

### Rate limiting & reliability

- `DELAY = 0.35s` between SchweizMobil requests. `SESSION` sends `Referer: https://www.schweizmobil.ch/` (required to avoid 403s).
- `SBB_DELAY = 2.0s` between transport.opendata.ch requests.
- Per-minute 429s are retried once after 30s. SchweizMobil requests retry once after 5s on 5xx or network errors (`sm_get()` helper).
- Corrupted `hikes.json` (e.g. interrupted mid-write) is detected on startup, backed up to `hikes.json.bak`, and the scraper starts fresh.
- **SBB fuzzy-prefix guard**: the transport.opendata.ch API does prefix-style fuzzy matching on destination names. The scraper rejects results where the matched station's first word *extends* the query's first word (e.g. query `"Binn"` → matched `"Binningen Oberdorf"` is rejected; `"Binn, Dorf"` is accepted).

### Cost per origin

All routes are cached after the first `--routes-only` run. Each subsequent `--sbb-only` pass makes ~1–2 SBB API calls per stage (~600–1200 requests per origin). With the daily quota this typically takes 1–2 nights per origin.

### SBB Travel Time Completion Status

**Complete (all 12 origins, all Swiss stages):**
Basel SBB, Bern, Biel/Bienne, Chur, Genève, Interlaken Ost, Lausanne, Lugano, Luzern, St. Gallen, Thun, Zürich HB

## UK South West Coast Path — scraper_swcp.py

```bash
pip3 install cloudscraper beautifulsoup4 requests
python3 scraper_swcp.py                   # fetch all 53 stages + elevation
python3 scraper_swcp.py --refresh         # re-fetch everything, including elevation
python3 scraper_swcp.py --limit 3         # smoke test: first N stages only
python3 scraper_swcp.py --skip-elevation  # skip elevation calls (faster)
python3 scraper.py --import
```

Writes `route_id=1`, `land="uk"`, 53 stages. Resumable via internal `_walk_id`. Walk ID 189 is non-sequential between stages 5 and 6. No SBB enrichment (`sbb_times={}` for all UK stages).

**Elevation** computed per stage:
1. `GET /walksdb/{id}/data/` — GeoJSON LineString geometry
2. Sample up to 80 points → OpenTopoData SRTM30m (`api.opentopodata.org/v1/srtm30m`)
3. Cumulative ascent/descent with 2 m noise threshold

OpenTopoData: **1000 req/day quota** (1 call per stage = 53 calls per full run). Cached stages with `elev_up=null` are backfilled automatically on next run. The site is behind Cloudflare — `cloudscraper` handles this.

## West Highland Way — scraper_whw.py

```bash
pip3 install requests beautifulsoup4
python3 scraper_whw.py                # fetch all 8 stages
python3 scraper_whw.py --refresh      # re-fetch everything
python3 scraper_whw.py --limit 3      # smoke test
python3 scraper.py --import
```

Writes `route_id=2`, `land="uk"`, 8 stages. Resumable via internal `_slug`. No elevation (site has no GPX/GeoJSON API). Distances parsed from "X Miles (Y km)" format.

## Offa's Dyke Path — scraper_odd.py

```bash
pip3 install cloudscraper beautifulsoup4
python3 scraper_odd.py               # fetch all 12 stages
python3 scraper_odd.py --refresh
python3 scraper.py --import
```

Writes `route_id=3`, `land="uk"`, 12 stages from a single nationaltrail.co.uk page. Cloudflare-protected; `cloudscraper` handles it. Elevation and duration are `null`.

## GR20 (Corsica) — scraper_gr20.py

```bash
pip3 install requests beautifulsoup4
python3 scraper_gr20.py              # fetch all 16 stages
python3 scraper_gr20.py --refresh
python3 scraper_gr20.py --limit 3
python3 scraper.py --import
```

Source: `https://www.le-gr20.fr/en/pages/profile-stages/`. Writes `route_id=1`, `land="fr-hike"`. Per stage: `elev_up`, `elev_down`, `duration_hrs` (format varies by page — colon optional). `dist_km` is null (not published per stage). Stages 9–10 have no elevation on the source pages. Resumable via internal `_url`. Difficulty hardcoded to `"difficult"`.

## French GR trails — scraper_gr.py

```bash
pip3 install requests beautifulsoup4
python3 scraper_gr.py                       # all trails (GR65, GR70, GR20 backfill)
python3 scraper_gr.py --only gr65
python3 scraper_gr.py --only gr70
python3 scraper_gr.py --only gr20           # GR20 distance backfill only
python3 scraper_gr.py --refresh-trail gr65  # re-fetch even if cached
python3 scraper_gr.py --limit 3
python3 scraper.py --import
```

| Slug   | Trail                                           | route_id | Stages | Source              |
|--------|-------------------------------------------------|----------|--------|---------------------|
| `gr65` | GR65 Via Podiensis (Le Puy → St-Jean-Pied-de-Port) | 2     | 32     | podiensis.com       |
| `gr70` | GR70 Chemin de Stevenson (Le Puy → Alès)        | 3        | 13     | chamina-voyages.com |
| `gr20` | GR20 — distance backfill only (existing route_id=1) | 1    | 16     | thepostrace.com     |

**GR65**: index table at `/les-etapes` gives stage_nr, start, end, distance; per-stage pages give duration, elevation, difficulty. Resumable via `_url`. Difficulty mapped from French ("Facile"→easy, "Moyenne"→moderate, "Difficile"→difficult).

**GR70**: single-page table, start/end from "A > B" format, distance, D+, D−. No per-stage subpages; no duration. Single fetch, no resume needed.

**GR20 distance backfill**: thepostrace.com has a 15-stage table (stages 1–10 align cleanly; 11–15 approximate; stage 16 Bavella→Conca has no match, stays `dist_km=null`).

**To add a new GR trail**: add an entry to `GR_TRAILS` in `scraper_gr.py`, add a scrape function, dispatch it in `main()`. Cross-border trails need a Supabase CHECK constraint update first — see deferred comment block at the top of the scraper.

## Alta Via 1 (Dolomites) — scraper_av1.py

```bash
pip3 install requests beautifulsoup4
python3 scraper_av1.py              # fetch all 11 stages
python3 scraper_av1.py --refresh
python3 scraper.py --import
```

Source: `https://altavia1dolomites.com/alta-via-1-stages/`. Writes `route_id=1`, `land="it-hike"`. Full per-stage data: `dist_km`, `elev_up`, `elev_down`, `duration_hrs`. Single page with all 11 stages in Gutenberg blocks (`wp-block-ugb-columns`).

## Malerweg (Saxon Switzerland) — scraper_malerweg.py

```bash
pip3 install requests beautifulsoup4
python3 scraper_malerweg.py              # fetch all 8 stages
python3 scraper_malerweg.py --refresh
python3 scraper_malerweg.py --limit 3
python3 scraper.py --import
```

Source: sequential per-stage URLs at `saechsische-schweiz.de`. Writes `route_id=1`, `land="de-hike"`. Data from `.fact__item` CSS structure. Stage start/end names are hardcoded (transport info on pages is inconsistent). Per stage: `dist_km`, `elev_up`, `elev_down`. `duration_hrs` is null.

## UK National Trails — scraper_nationaltrail.py

```bash
pip3 install requests beautifulsoup4 cloudscraper
python3 scraper_nationaltrail.py              # all 4 trails
python3 scraper_nationaltrail.py --only sdw   # South Downs Way
python3 scraper_nationaltrail.py --only cw    # Cotswold Way
python3 scraper_nationaltrail.py --only hwp   # Hadrian's Wall Path
python3 scraper_nationaltrail.py --only pcp   # Pembrokeshire Coast Path
python3 scraper_nationaltrail.py --refresh
python3 scraper.py --import
```

| route_id | Trail                                          | Stages |
|----------|------------------------------------------------|--------|
| 5        | South Downs Way (Winchester → Eastbourne)      | 9      |
| 6        | Cotswold Way (Chipping Campden → Bath)         | 15     |
| 7        | Hadrian's Wall Path (Wallsend → Bowness)       | 6      |
| 8        | Pembrokeshire Coast Path (St Dogmaels → Amroth)| 15     |

All stages on a single route page per trail — `smUrl` links to the trail description page. Cloudflare-protected; `cloudscraper` handles it.

**Heading formats vary:** South Downs/Cotswold use `"Start to End – X miles (Y km)"`; Pembrokeshire uses `"Start to End X miles (Y km)"` (no dash); Hadrian's Wall has no per-section distances (`dist_km=null` for all 6 stages). `elev_up`/`elev_down` and `duration_hrs` are null.

## OSM trails (Waymarked Trails) — scraper_osm.py

```bash
pip3 install requests
python3 scraper_osm.py                          # full run (all trails in catalog)
python3 scraper_osm.py --limit 2               # smoke test: first 2 trails only
python3 scraper_osm.py --only 4080347          # one trail by OSM relation ID
python3 scraper_osm.py --refresh-trail 4080347 # re-fetch a specific trail
python3 scraper_osm.py --skip-elevation        # skip OpenTopoData calls (faster)
python3 scraper_osm.py --backfill-elevation    # fill elev_up/down for stages with _osm_id
python3 scraper_osm.py --backfill-names        # Nominatim reverse-geocoding for code-style names
python3 scraper.py --import
```

Source: `https://hiking.waymarkedtrails.org/api/v1/details/relation/{osm_id}`. Subroutes at one level become day stages.

**Resumable:** re-running skips fully-cached trails (matched by `_osm_id` on each stage). `--refresh-trail <id>` re-fetches even if cached. Never run two scraper_osm.py processes simultaneously against hikes.json.

**Elevation:** OpenTopoData SRTM30m, 1000 req/day quota (~1 call per stage). Detects quota exhaustion and saves progress. Stage variants (OSM names containing "Variante") and micro-stages (< 1 km) are filtered automatically.

**Permanent elevation gap — Scandinavian trails (236 stages):** Subroute geometry not exposed via WT API — elevation stays `null` without a different source:
- Hälsingeleden (22, se-hike), St. Olavsleden (29, se-hike), Kungsleden (31, se-hike)
- Skåneleden SL1–SL6 (94 stages total, se-hike)
- Fjordruta på Nordmøre (14, no-hike), Nordland trekking trail (43, no-hike), Lofoten Long Crossing (11, no-hike)

**Backfilling elevation for website-scraped trails:** `--backfill-elevation` also works on non-OSM stages if `_osm_id` is manually injected. Pattern: search WT by trail name (`/api/v1/list/search?query=NAME`), verify subroute count matches stage count, inject `stage["_osm_id"]` into hikes.json, run `--backfill-elevation`. Used for 4 Schwarzwaldverein trails (Schluchtensteig route_id=14, Kandelhöhenweg 15, ZweiTälerSteig 17, Murgleiter 22).

**`--backfill-names`:** Nominatim reverse-geocoding for stages with OSM code-style names (e.g. "Via Alpina Red R3"). ~1.1 s/call. `is_code_name()` detects "Trail Red RN" patterns only (not "Stage N" — those need manual fix).

**Adding a new trail:** look up the OSM relation ID on `hiking.waymarkedtrails.org`, check it has subroutes (`/api/v1/details/relation/{id}` → `.route.main[].route_type == "route"`), add to `TRAILS` in `scraper_osm.py`, add `smUrl`/`sourceLabel` in `index.html`. Full OSM ID → land → route_id table in docs/trails.md.

To check a candidate: `curl "https://hiking.waymarkedtrails.org/api/v1/details/relation/{id}" | python3 -m json.tool | grep -E '"route_type"|"length"'` — look for 10–40 children each 5–40 km.

## Schwarzwaldverein Fernwanderwege — scraper_schwarzwaldverein.py

```bash
python3 scraper_schwarzwaldverein.py              # all 22 trails
python3 scraper_schwarzwaldverein.py --refresh    # re-fetch even if cached
python3 scraper.py --import
```

Source: schwarzwaldverein.de. All `land="de-hike"`, route_ids 10–31. Stage data parsed from `elementor-icon-list-text` spans. Variant stages (A/B): only first variant used. Route-level totals (total_km, elev_up, elev_down, difficulty) extracted for all. Per-stage elevation available on 4 trails only — backfilled via `scraper_osm.py --backfill-elevation` with manually injected `_osm_id` values.

## Albverein Hauptwanderwege — scraper_albverein.py

```bash
python3 scraper_albverein.py              # all 4 trails
python3 scraper_albverein.py --only hw1   # one trail (hw1, hw2, hw5, hw7)
python3 scraper_albverein.py --refresh    # re-fetch even if cached
python3 scraper.py --import
```

Source: `https://wege.albverein.net/wanderwege/hauptwanderwege/{slug}/etappenbeschreibung-{slug}/`. Stage format: `<strong>Etappe N | Start – End | X,Y Km</strong>` (en-dash is `&#8211;` in raw HTML). Plain requests works (no Playwright needed) — page content is server-rendered at the correct URL.

| route_id | Trail | Stages | Total km |
|----------|-------|--------|----------|
| 33 | Schwäbische Alb-Nordrand-Weg (HW1) | 23 | 356 km |
| 34 | Schwäbische Alb-Südrand-Weg (HW2) | 19 | 288 km |
| 35 | Schwarzwald-Schwäbische-Alb-Allgäu-Weg (HW5) | 19 | 309 km |
| 36 | Schwäbische-Alb-Oberschwaben-Weg (HW7) | 16 | 232 km |

No elevation or duration data (not published per stage). To add more HW trails: add entry to `TRAILS` in `scraper_albverein.py` with slug, route_id, name, start, end. Route_ids continue from 37.

## Website-only routes — scraper_websites.py

```bash
pip3 install requests beautifulsoup4
python3 scraper_websites.py                   # all trails
python3 scraper_websites.py --only eifelsteig # one trail by slug
python3 scraper_websites.py --refresh         # re-fetch even if cached
python3 scraper.py --import
```

For routes with no viable OSM day-stage hierarchy. Each trail has a custom scrape function. `DELAY = 1.5s` between requests.

| Slug | Trail | Land | route_id | Stages | Source |
|------|-------|------|----------|--------|--------|
| `eifelsteig` | Eifelsteig | `de-hike` | 49 | 15 | eifelsteig.de |
| `italiac2c` | Italia Coast to Coast | `it-hike` | 13 | 18 | italiacoast2coast.it |
| `sauerland` | Sauerland-Waldroute | `de-hike` | 44 | 7 (partial) | sauerland-waldroute.de |
| `linksrheinisch` | Linksrheinischer Jakobsweg | `de-hike` | 50 | 12 | linksrheinischer-jakobsweg.info |
| `westfalenww` | WestfalenWanderWeg | `de-hike` | 51 | 11 | wildganz.com |

**Sauerland-Waldroute note:** Overwrites the 3 coarse OSM sections in route_id=44. Only 7 of 19 stages are server-rendered (rest require JS). Use `--only sauerland` to re-fetch.

**Linksrheinischer Jakobsweg:** Fetches 12 individual stage pages at `/index.php/linksrheinischer-jakobsweg/etappenuebersicht/N-etappe`.

**WestfalenWanderWeg:** All 11 stages parsed from the bottom listing on stage 1's page — single fetch only.

**To add a new trail:** add a scrape function and a `TRAILS[slug]` entry. Keys: `land`, `route_id`, `name`, `fetch_fn`. If it's a new `land` value, update the Supabase CHECK constraint before importing (see CLAUDE.md).

## Trail discovery — discover_trails.py

```bash
python3 discover_trails.py                        # full run (Overpass + WT enrichment)
python3 discover_trails.py --enrich-only          # skip Overpass, resume WT enrichment
python3 discover_trails.py --recheck-excluded     # level-2 for flat/no-stage routes
python3 discover_trails.py --recheck-large-stages # level-2 for section-structured trails
python3 discover_trails.py --refresh-id 16127693  # re-fetch one trail
python3 discover_trails.py --smoke-test           # Ireland only, first 5 WT calls
```

Builds/maintains `trails_catalog.json` (56k+ entries, gitignored). Two-phase: Overpass API (all `iwn/nwn/rwn` hiking relations in Europe) → Waymarked Trails API (enriches with length, stage count, bbox).

**`filter_status` values:**
- `candidate` — viable day stages (may have `needs_level2=True` if stages are really sections)
- `needs_level2` — level-1 children are sections, not day stages; run `--recheck-large-stages` to descend
- `section_of_parent` — suppressed: this is a sub-section of a parent trail in the catalog
- `auto_excluded` — too short or no day stages
- `in_app` — already imported
- `pending_enrichment` — WT call not yet made
- `unverified` — rwn below distance threshold, not enriched

**Key functions:**
- `tag_child_sections()` — builds child→parent index from `stages_raw`, sets `parent_osm_id` on section entries
- `apply_section_suppression()` — post-filter: demotes sections to `section_of_parent` (preserves `in_app`, `auto_excluded`)
- `backfill_needs_level2()` — computes `needs_level2` for entries enriched before the field existed
- Auto level-2: during Phase 2, if all children are >40 km the script immediately fetches sections
