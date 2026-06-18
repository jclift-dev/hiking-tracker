# Architecture

## Data flow

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

**How the API was found:** The site is fully JS-rendered. Used Playwright to intercept network requests on `schweizmobil.ch/en/hiking-in-switzerland/route-01`, which revealed `api/4/route_or_segment/hike/1/0`. The `land=hike` value was found in the JS bundle. The route geometry map API (`map.schweizmobil.ch/api/4/query/featuresmultilayers`) does **not** contain stage data — route-level geometry only.

## Supabase schema

**`routes`** — shared read-only route data. Primary key: `(id, land)` — hiking and cycling both have routes numbered 1–7, so the composite key is required. The `land` column has a CHECK constraint (see CLAUDE.md). Adding a new land value requires updating that constraint first via the Supabase SQL editor.

**`stages`** — per-stage data. Unique on `(route_id, land, stage_nr)`. `sbb_times` stored as `jsonb`. `country` (text, nullable) and `admin1` (text, nullable) store ISO 3166-2 region codes populated by `enrich_regions.py` — used by the Europe dashboard map. `osm_id` (integer, nullable) is the Waymarked Trails OSM relation ID for the day stage — used for the 🗺 Map preview button and for dynamic cross-route linking (see Stage linking below).

**`user_state`** — per-user completions/ratings/notes. Keyed by `(user_id, stage_key)` where `stage_key` is `"land_routeId_stageNr"` (e.g. `"ch-hike_1_3"`). Fields: `stage_key, completed_on, rating, note, wishlist, updated_at`.

**`user_preferences`** — per-user settings (selected home station). Fields: `selected_station, updated_at`.

RLS policies ensure each user can only read/write their own rows. Routes and stages are public-read (no auth required). The scraper uses the `service_role` key (bypasses RLS) for imports.

**`withTimeout(promise, ms)`** — all Supabase queries in `loadData()` and `loadUserState()` are wrapped with this helper (10 s timeout). Any new queries added to these functions should follow the same pattern; unwrapped queries will hang indefinitely if the network is unavailable after PC wake.

## hikes.json schema

`hikes.json` is the local scraper output — same data imported to Supabase. The web app reads from Supabase, not this file.

`route_type: "continental"` is reserved for the official ERA E-paths (OSM tag `ref=E1`..`E12`, `network=iwn`) — currently E1, E9, E11. Generic multi-country routes that just happen to cross 2-3 borders (Via Alpina, Via Gebennensis, etc.) stay `"international"`. Neither value has dedicated filter UI yet — only national/regional/local have tabs in `index.html`.

```json
[{
  "route_id": 1,
  "route_type": "local" | "regional" | "national" | "international" | "continental",
  "land": "ch-hike" | "ch-cycle" | "uk" | "fr-hike" | "it-hike" | "de-hike" | "es-hike" | "pt-hike" | "eu-hike" | "at-hike" | "se-hike" | "no-hike" | "hr-hike" | "sk-hike" | ...,
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
    },
    "country": "ch",
    "admin1": "ch-sg",
    "_osm_id": 12359031
  }]
}]
```

`_osm_id` is the Waymarked Trails OSM relation ID for the day stage. Present on OSM-scraped routes and ch-hike routes 1–7 (backfilled via `--backfill-ch-osm-ids`). Imported to Supabase as `osm_id`. Enables the 🗺 Map button and dynamic cross-route linking.

`country` and `admin1` are populated by `enrich_regions.py` for European lands (`eu-hike`, `fr-hike`, `de-hike`, `it-hike`, `es-hike`, `ie-hike`, `uk`). Swiss stages use the separate `cantons` field instead.

`sbb_times` values: `null` = scraper tried, no connection found; integer = minutes; missing/`undefined` = never looked up.

`difficulty` values from the Swiss API: `"hiking trail"`, `"mountain hiking trail"`, `"demanding mountain hiking trail"`, `"alpine hiking trail"`. `index.html` normalises via `DIFF_CANON` / `canonDiff()` to T1–T4 labels.

For `land="uk"` stages, difficulty is `"easy"`, `"moderate"`, or `"challenging"` — from the primary-grade image filename on each walksdb page. `duration_hrs` is `null` for SWCP stages (not published by the site).

`_walk_id` in hikes.json is an internal scraper field (not imported to Supabase). `index.html` has a static `SWCP_WALK_IDS` array (53 entries) mapping `stage_nr → walksdb ID` for the "View on SWCP ↗" link.

## Cross-route stage linking

`buildLinkedStageMap()` runs at boot (after `loadData()`) and builds a `Map<stageKey, stageKey>` of linked pairs. Two stages are linked if they share the same `osm_id` value in Supabase — meaning they cover identical geography on different named routes (e.g. a Swiss Via Alpina stage and the international Via Alpina stage for the same day). A linked stage badge appears on the card, and completing one stage shows the other as progress on both routes.

A small hardcoded fallback `E1_STAGE_PAIRS` covers 17 E1 ↔ national-route links where E1 has no `osm_id` (scraped from hiking-europe.eu, not OSM). `SWISS_EU_STAGE_PAIRS` is now empty — Swiss ch-hike stages have OSM IDs backfilled, so linking is automatic.

## Map preview

Stages with an `osm_id` show a 🗺 Map button. Clicking it lazy-loads Leaflet.js (once per session), fetches the route GeoJSON from `https://hiking.waymarkedtrails.org/api/details/relation/{osm_id}/geometry`, and renders a 200px inline map with an OSM tile layer. Geometry is cached in `stageGeomCache` (keyed by `osm_id`) so re-opens are instant. Live map instances are tracked in `stageMaps` and torn down on close.

## Assets

`assets/` contains five terrain icons for the elevation profile display on stage cards:

- `icon-1-meadow.svg` — total elevation < 300 m
- `icon-2-rolling-hills.svg` — 300–600 m
- `icon-3-foothills.svg` — 600–1200 m
- `icon-4-alpine.svg` — 1200–2000 m
- `icon-5-summit.svg` — 2000 m+

Each card shows `↑ Xm [icon] ↓ Xm`. Icons are referenced via `<img src="assets/...">` (not inlined) to avoid SVG `id` clashes when multiple cards render on the same page.

A bed icon is shown next to a stage start or end name when `sbb_times[station].start === null` or `.end === null` — indicating no train connection (remote hut, pass, etc.).

Canton badges (`.canton-badge`) on Swiss stage cards. Flag images from `https://schweizmobil.ch/img/footer/{code.toLowerCase()}.svg` — external URL, `onerror` hides the img if it fails.

## Web app state

All user state stored in Supabase, synced in real time:

In-memory: `completed`, `ratings`, `notes`, `wishlist`, `selectedStation` — loaded from Supabase on login, written back via `persistStage(key)` / `persistStation(val)` on every change. `wishlist` is a ♡/♥ toggle (boolean in `user_state.wishlist`); wishlisted stages appear in the "Wishlist" filter tab.

On first login, any existing localStorage data (`hikes_done`, `hikes_ratings`, `hikes_notes`) is migrated to Supabase automatically and removed from localStorage.

## Auth

- Email + password via Supabase Auth (`signInWithPassword`)
- Sign-ups disabled — users must be invited via **Supabase > Authentication > Users > Invite user**
- Password reset emails use `resetPasswordForEmail` — `PROD_URL` / `APP_URL` constants in `index.html` set the redirect target
- Sessions persist for 1 week with auto-refresh; expiry shows "Your session has expired" message
- **Escape hatch**: `/?reset` clears `localStorage` + `sessionStorage` and reloads. Linked in the login form as "Stuck? Clear session & reload".
- **Sleep/wake recovery**: `_recoverIfStuck()` listens on `visibilitychange` and `online` events — if `_booting` has been true for >20 s when the page becomes visible again, forces a clean reload. Boot sequence guard flags: `_booting`, `_bootStartedAt`, `_loggingOut`, `_inPasswordRecovery`.

## Route numbering

- National routes: IDs 1–7 (displayed with ★) — only 7 exist as of 2026
- Regional routes: IDs 10–99 (not all numbers exist — scraper skips 404s gracefully)
- Local routes (100+) are intentionally excluded (too many)
