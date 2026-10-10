# Data sources, terms, and what can be published

Reviewed 2026-10-10 for issue #48. **Not legal advice** — this records what each source's own pages say, and what follows for a project that is currently public. Every source was checked by reading its `robots.txt` and legal/terms pages. Two were re-verified verbatim by hand (nationaltrail.co.uk, westhighlandway.org); the rest were read by a research agent through a summarising fetch tool, so quotes can be paraphrased and the *confidence* column matters. "No terms found" means exactly that — it is **not** permission: copyright applies by default.

Route → source mapping lives in `route_sources.py` (tested: every route maps to exactly one source). Run `python3 route_sources.py` for the counts below.

## What is published today

| Channel | What is exposed |
|---|---|
| Public GitHub repo `jclift-dev/hiking-tracker` | `hikes.json` (4.3 MB): all 842 routes / 7,768 stages, including ~1.29 M characters of scraped descriptive text (1.20 M of it from non-OSM sources), in every commit of git history |
| Supabase REST API | `routes` and `stages` have a `public read` RLS policy (`USING (true)`), and the publishable key is in `index.html`, so **anyone can read every row without logging in** |
| GitHub Pages site | the app; data comes from the API above |

So "can we publish this?" is not hypothetical: everything below is already published.

## What "publish" needs

Most sites allow *personal, private, non-commercial* copying. That does not cover putting the content in a public repository or an openly readable API: that is redistribution, which needs an open licence or the owner's consent. Separately, **facts** (a place name, a distance, an ascent) are generally not protected by copyright, but **prose descriptions, photos and curated selections** are, and in the EU/UK a substantial extraction of a *database* can infringe database rights even when each fact is free. Bulk-copying a publisher's whole stage list (E1: 425 stages, Via Francigena: 156) is the riskiest category for that reason.

## Verdicts

**A — publishable, with attribution**

| Source | Routes / stages | What its terms say | Required |
|---|---|---|---|
| OpenStreetMap via Waymarked Trails | 234 / 4,421 | ODbL 1.0: "free to copy, distribute, transmit and adapt our data, as long as you credit OpenStreetMap and its contributors"; derived databases must stay under ODbL | "© OpenStreetMap contributors" (in the app footer); **offer the derived data (hikes.json, the DB tables) under ODbL** — the repo's MIT licence does not cover it |
| transport.opendata.ch / opentransportdata.swiss (SBB times) | `sbb_times` on Swiss stages | data "can be processed, analysed and published"; no fixed per-client limit | cite "Timetable data: opentransportdata.swiss" — **not currently shown in the app** |
| OpenTopoData (elevation, SWCP / OSM / National Trails scrapers) | elevation values | service: max 1 call/s, 1,000/day; code is MIT; **dataset licences (SRTM, EU-DEM, …) not verified** | credit the underlying dataset once confirmed |

Usage policies that bind our *scraping* even though the data is open: OSM Nominatim (≤1 req/s, cache results, identify the app) and the OSM tile server (no bulk download/offline use) — see #47.

**B — terms explicitly forbid scraping or republishing → should not be in the published data**

| Source | Routes / stages (prose chars) | Evidence | Confidence |
|---|---|---|---|
| nationaltrail.co.uk | 6 / 71 (40.8 k) — uk:3, 5, 6, 7, 8, 15 | *"You shall not conduct, facilitate, authorise or permit any text or data mining or web scraping in relation to our site"*; commercial use needs a licence; personal-use extracts only; OS map data licensed for viewing only. (The scrapers also use `cloudscraper` to get past the site's Cloudflare protection.) | high — **verified verbatim** |
| walkhighlands.co.uk (West Highland Way, uk:2) | 1 / 8 (6.6 k) | its pages returned 403 so terms could not be read; search summaries say bulk/automated map-tile download is prohibited and a staff post says route descriptions "cannot be re-published or re-sold". (The official westhighlandway.org terms — verified — also forbid bots/"manual process to monitor or copy" and aggregating its content in another site, but that isn't our source.) | low — re-check in a browser |
| komoot.com | 1 / 9 | "explicitly prohibited to export, distribute or publish tours in other ways than with the offered export function" (§1.4) | medium |
| outdooractive.com | 1 / 16 | API terms: content may not be distributed or made accessible; `robots.txt` blocks GPX/FIT/API and named AI crawlers | medium |

**C — personal/private use permitted only; publishing is outside it**

| Source | Routes / stages | Key sentence | Confidence |
|---|---|---|---|
| gronze.com (30 Camino routes) | 30 / 602 | content "exclusivamente para su uso personal, privado y no lucrativo"; commercial reproduction/distribution prohibited; written consent otherwise | high |
| wege.albverein.net | 10 / 175 | only copies/downloads "für den persönlichen, privaten und nicht kommerziellen Gebrauch"; storing/processing content in databases needs written consent | medium |
| rando.vanoise.com (Parc national de la Vanoise) | 11 / 49 | reproduction allowed only "strictement réservées à un usage personnel"; otherwise prior authorisation | medium (notice is on the park's site) |
| erzgebirge-tourismus.de, vogelsberg-touristik.de, ith-hils-weg.de | 3 routes / 30 stages | "Downloads und Kopien dieser Seite sind nur für den privaten, nicht kommerziellen Gebrauch gestattet"; exploitation needs written consent | medium |
| sauerland-waldroute.de | 1 / 19 | single private copies only; reproducing texts/data needs written consent | medium |
| sustrans.org.uk (Walk Wheel Cycle Trust), visitnorthumberland.com | 3 / 21 | personal copying only; commercial use / storing content on another website not permitted | medium |
| caminoespiritualdelsur.com | 1 / 14 | personal/private copying only; reproduction, distribution, public communication prohibited | medium |
| high-scardus-trail.com | 1 / 20 | private use only; tour geometries are "protected works"; further use needs written consent | medium |

**D — reproduction prohibited, no personal-use carve-out**

| Source | Routes / stages | Key sentence | Confidence |
|---|---|---|---|
| podiensis.com (GR65) | 1 / 32 | "Toute reproduction, distribution, modification… même partielle, est strictement interdite sans l'accord exprès par écrit" | medium |
| pilgrim.es | 1 / 25 | any reproduction/adaptation/public communication of the whole prohibited without express authorisation; `robots.txt` blocks wget/HTTrack by name | medium |
| oberlausitzer-bergweg.de | 1 / 7 | all rights reserved; reproduction/electronic processing needs written permission | medium (quote truncated) |
| grand-tour-ecrins.fr | 1 / 13 | "toute utilisation… doit faire l'objet d'une autorisation express du Parc national des Écrins" | low (notice is on the park's site) |

**E — no usable terms found (default copyright applies; no permission established)**

| Source | Routes / stages (prose chars) | Notes |
|---|---|---|
| **schweizmobil.ch** | **479 / 1,179 (993.6 k)** | legal pages returned no text; `robots.txt` allows everything. `LICENSE` says "used with permission for non-commercial purposes" — **the written permission needs to be located** and checked for whether it covers a public repo/API |
| southwestcoastpath.org.uk | 1 / 53 (46.8 k) | pages returned 403 |
| viefrancigene.org | 1 / 156 (93.1 k) | JS-rendered; no legal page reachable |
| hiking-europe.eu (E1) | 1 / 425 | terms cover user uploads only; `robots.txt` blocks `/gpx/*` |
| le-gr20.fr | 1 / 16 (8.7 k) | legal page is only a © line; `robots.txt` bans several named bots |
| altavia1dolomites.com | 1 / 11 | © line only; /terms pages 404 |
| saechsische-schweiz.de (Malerweg) | 1 / 8 (3.3 k) | impressum has image credits only |
| schwarzwaldverein.de | 23 / 138 | impressum has only credits; the AGB PDFs were not read |
| rando.marittimemercantour.eu (Mercantour) | 14 / 82 | mentions légales has no reuse clause |
| wildganz.com, eifelsteig.de, italiacoast2coast.it, linksrheinischer-jakobsweg.info (TLS cert expired), werra-burgen-steig-hessen.de, caminodelafrontera.es, walkingpenedageres.pt, koenig-ludwig-weg.de, ich-geh-wandern.de (© Wanderatlas Verlag), snptrail.com, wayoftheroses.co.uk | 12 routes / 155 stages | © lines only |
| chamina-voyages.com (GR70) | 1 / 13 | **not researched** |

## Recommendations

Ordered by how much risk they remove per unit of effort. None has been applied; items marked ⚠ need your explicit go-ahead.

1. **Stop serving the data to anonymous callers.** Change the `routes` / `stages` RLS policies from `public read` to `authenticated` (add to the #50 migration). The app already requires login, so users see no difference. ⚠ (changes live policies)
2. **Strip the prose from non-OSM data.** The app shows scraped descriptive text in exactly one place (the dashboard's "hike of the day" blurb); stage descriptions are not displayed anywhere. Dropping `description` for every source except OSM removes ~1.2 M characters — 994 k of it SchweizMobil's — at almost no functional cost, and is the clearest copyright text in the dataset. ⚠ (data change, `hikes.json` + `--import`)
3. **Remove or replace the Tier B routes** (UK National Trails ×6, West Highland Way, Komoot, Outdooractive: 9 routes / 104 stages), and stop using `cloudscraper` to defeat Cloudflare on nationaltrail.co.uk. Where an OSM relation exists, use that instead. ⚠
4. **Take `hikes.json` out of the public repo going forward** and keep it elsewhere (private storage, or load it into Supabase only). Note this does **not** remove it from git history: either make the repo private (GitHub Pages then needs a paid plan) or rewrite history with `git filter-repo` and force-push. ⚠⚠ (destructive / outward-facing)
5. **Settle SchweizMobil.** Find the permission referred to in `LICENSE`; if it can't be shown to cover redistribution, treat the 479 Swiss routes as Tier E: keep names/distances/elevations, drop the prose, and keep the data behind login.
6. **Ask for permission** from the few publishers where it matters most (E1 / hiking-europe.eu, Via Francigena, Gronze, Albverein) or replace their routes with OSM-derived ones.
7. **Fix attribution and licensing** (safe, no data change): footer credits for opentransportdata.swiss, SchweizMobil and the OpenTopoData datasets; state that the OSM-derived data is under ODbL; resolve the README ("proprietary") vs `LICENSE` (MIT) mismatch for the code.
8. **Scraper conduct** (#47): honour `robots.txt` (several of these block named bots), one identifying User-Agent with a contact URL, polite delays, no Cloudflare bypass.

## Gaps in this review

chamina-voyages.com was not researched; southwestcoastpath.org.uk, walkhighlands.co.uk and schweizmobil.ch could not be read (403 / empty); linksrheinischer-jakobsweg.info has an expired TLS certificate; several legal notices belong to a parent organisation (park authorities, albverein.net) and applicability to the sub-site is inferred; terms change, so re-check before relying on any row.
