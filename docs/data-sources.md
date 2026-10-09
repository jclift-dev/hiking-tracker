# Data sources and terms

Where each part of `hikes.json` comes from, and what is (and isn't) known about
reuse terms. This is a private, non-commercial project for a small group; it is
**not** legal advice, and the "terms status" column only records what has been
checked in this repo, not what the sites actually permit.

| Source | Used for | Scraper | Terms status |
|---|---|---|---|
| SchweizMobil (schweizmobil.ch) | Swiss hiking/cycling routes, stages | `scraper.py` | Non-commercial permission recorded in `LICENSE` |
| OpenStreetMap via Waymarked Trails (hiking/cycling.waymarkedtrails.org) | Most European long-distance trails, geometry, `osm_id` links | `scraper_osm.py`, `scraper_via_francigena.py` | ODbL 1.0 — attribution required; shown in the app footer |
| transport.opendata.ch (SBB) | Travel times | `scraper.py` | Public API; rate limited |
| OpenTopoData | Elevation | `scraper_osm.py`, `scraper_swcp.py`, `scraper_nationaltrail.py` | Public API; rate limited |
| nationaltrail.co.uk, southwestcoastpath.org.uk | UK national trail stages | `scraper_nationaltrail.py`, `scraper_swcp.py`, `scraper_odd.py` | "Permission for personal use" per `LICENSE` (not independently verified here) |
| walkhighlands.co.uk | West Highland Way | `scraper_whw.py` | Not reviewed |
| le-gr20.fr, GR65/GR70 sites | GR20, GR65, GR70 | `scraper_gr20.py`, `scraper_gr.py` | Not reviewed |
| altavia1dolomites.com | Alta Via 1 | `scraper_av1.py` | Not reviewed |
| saechsische-schweiz.de | Malerweg | `scraper_malerweg.py` | Not reviewed |
| schwarzwaldverein.de, wege.albverein.net | German Fernwanderwege | `scraper_schwarzwaldverein.py`, `scraper_albverein.py` | Not reviewed |
| hiking-europe.eu | E1 stages | `scraper_e1.py` | Not reviewed |
| viefrancigene.org | Via Francigena | `scraper_via_francigena.py` | Not reviewed |
| Geotrek instances (Vanoise, Mercantour), gronze.com, and ~25 regional tourism/trail sites | Assorted routes | `scraper_websites.py` (see `docs/scrapers.md`) | Not reviewed |

## What is covered by which licence

- The **application code** — see `LICENSE` (note: `README.md` currently calls
  the code "proprietary" while `LICENSE` is MIT; that mismatch is for the owner
  to resolve).
- **OSM-derived data** — ODbL 1.0; keep the "© OpenStreetMap contributors"
  attribution.
- **Everything else in `hikes.json`** (names, descriptions, distances scraped
  from the sites above) belongs to its respective publishers. It is kept here
  for personal use and is not relicensed by the code licence.

## If a publisher objects

Remove that scraper's routes (they are identified by `land` + `route_id` in
`docs/trails.md`), re-run `python3 validate_hikes.py`, then re-import and prune
the matching rows in Supabase (see issue #52 for the prune gap).

## Open follow-ups

- Add a per-route `source` field so the app can show where each route came from.
- Review the terms of the "Not reviewed" sources, and drop or reduce routes
  (e.g. keep only names and distances) for any that don't allow reuse.
