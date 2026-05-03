#!/usr/bin/env python3
"""
West Highland Way Scraper
=========================
Fetches the 8 day-stages of the West Highland Way from westhighlandway.org
and merges them into hikes.json with land="uk-whw", route_id=1,
route_type="national".

Output is the same hikes.json the Swiss scraper writes to. Existing routes
(Swiss and SWCP) are preserved — entries are keyed by (land, route_type, route_id).

Usage:
    pip3 install requests beautifulsoup4
    python3 scraper_whw.py               # fetch all 8 stages
    python3 scraper_whw.py --refresh     # re-fetch even if already cached
    python3 scraper_whw.py --limit 3     # smoke test: first N stages only

Push to Supabase via the shared importer (no WHW-specific code needed):
    python3 scraper.py --import

IMPORTANT — before the first import, ensure 'uk' is in the land CHECK constraint:
    ALTER TABLE routes DROP CONSTRAINT routes_land_check;
    ALTER TABLE routes ADD CONSTRAINT routes_land_check
      CHECK (land IN ('hike','cycle','uk'));
    -- repeat for stages table:
    ALTER TABLE stages DROP CONSTRAINT stages_land_check;
    ALTER TABLE stages ADD CONSTRAINT stages_land_check
      CHECK (land IN ('hike','cycle','uk'));

Notes
-----
- Source: https://www.westhighlandway.org/the-route/
  Each linked /the-route/{slug}/ page is one day-stage.
- The site is WordPress-based with Cloudflare CDN but no JS challenge;
  plain requests work fine.
- Distances are parsed from the "X Miles (Y km)" figure on each stage page.
- No GeoJSON/GPX API is exposed by the site, so elev_up/elev_down are null.
  The web app's elevation icon and sort fall back gracefully for null values.
- duration_hrs is null (not published by the WHW site).
- sbb_times = {}, cantons = [], arrival_stations = [] — all ignored by the UI
  for UK rows.
"""

import argparse
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

# Reuse persistence helpers from scraper.py — keeps the on-disk format
# in lockstep with the Swiss scraper.
try:
    from scraper import save, load_existing
except ImportError:
    print("scraper.py not found. Run from the project root.")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE      = "https://www.westhighlandway.org"
ROUTE_URL = f"{BASE}/the-route/"
DELAY     = 1.0  # seconds between requests — be polite

ROUTE_ID   = 2
LAND       = "uk"
ROUTE_TYPE = "national"
ROUTE_NAME = "West Highland Way"
ROUTE_DESC = (
    "Scotland's most popular long-distance route: 96 miles (154 km) from "
    "Milngavie on the outskirts of Glasgow to Fort William at the foot of "
    "Ben Nevis. The route passes through some of Scotland's most dramatic "
    "scenery — the eastern shore of Loch Lomond, the expanse of Rannoch "
    "Moor, and the grandeur of Glencoe."
)

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": f"{BASE}/",
})


# ---------------------------------------------------------------------------
# Fetch helper
# ---------------------------------------------------------------------------

def fetch(url, label):
    """GET via SESSION. Returns text, or None on 404 / give-up."""
    for attempt in range(2):
        try:
            r = SESSION.get(url, timeout=15)
            if r.status_code == 404:
                print(f"  [warn] 404 for {label}")
                return None
            if r.status_code >= 500 and attempt == 0:
                print(f"  [warn] {r.status_code} for {label}, retrying in 5s...")
                time.sleep(5)
                continue
            r.raise_for_status()
            return r.text
        except Exception as e:
            if attempt == 0:
                print(f"  [warn] error for {label}: {e}, retrying in 5s")
                time.sleep(5)
                continue
            print(f"  [error] giving up on {label}: {e}")
            return None
    return None


# ---------------------------------------------------------------------------
# Page parsers
# ---------------------------------------------------------------------------

def discover_stage_slugs(html):
    """
    Find ordered /the-route/{slug}/ stage links on the route index page.
    Only slugs containing '-to-' are treated as stage pages (e.g.
    'milngavie-to-drymen'); other /the-route/ sub-pages (maps, guides, etc.)
    are skipped.
    """
    soup = BeautifulSoup(html, "html.parser")
    seen, slugs = set(), []
    for a in soup.select('a[href*="/the-route/"]'):
        href = a.get("href", "")
        m = re.search(r"/the-route/([^/]+-to-[^/]+?)/?$", href)
        if not m:
            continue
        slug = m.group(1)
        if slug in seen:
            continue
        seen.add(slug)
        slugs.append(slug)
    return slugs


def parse_stage(html, slug):
    """Parse a /the-route/{slug}/ page into a stage dict (without stage_nr)."""
    soup = BeautifulSoup(html, "html.parser")

    # --- Title: prefer <h1>, fall back to <title> tag ---
    h1 = soup.find("h1")
    title = h1.get_text(" ", strip=True) if h1 else ""
    if not title:
        t = soup.find("title")
        raw = t.get_text(strip=True) if t else ""
        title = re.sub(r"\s*[-–|]\s*(West Highland Way|WHW).*$", "", raw, flags=re.I).strip()
    title = title or slug.replace("-", " ").title()

    # "Foo to Bar" → start_name / end_name
    if " to " in title:
        start_name, end_name = (s.strip() for s in title.split(" to ", 1))
    else:
        start_name = end_name = title

    # --- Distance: "12 Miles (19 km)" → prefer km figure directly ---
    dist_km = None
    for tag in soup.find_all(["p", "td", "li", "span", "div"]):
        text = tag.get_text(" ", strip=True)
        # Preferred: explicit km in parentheses
        m = re.search(r"\d+(?:\.\d+)?\s+[Mm]iles?\s*\((\d+(?:\.\d+)?)\s*km\)", text)
        if m:
            dist_km = round(float(m.group(1)))
            break
        # Fallback: bare miles figure → convert
        m = re.search(r"^(\d+(?:\.\d+)?)\s+[Mm]iles?$", text.strip())
        if m:
            dist_km = round(float(m.group(1)) * 1.60934)
            break

    # --- Difficulty: infer from "Be aware" or terrain section text ---
    difficulty = None
    for h3 in soup.find_all(["h3", "h4"]):
        heading = h3.get_text(" ", strip=True).lower()
        if "be aware" in heading or "terrain" in heading or "difficulty" in heading:
            sibling = h3.find_next_sibling(["p", "div", "ul"])
            if sibling:
                content = sibling.get_text(" ", strip=True).lower()
                for grade in ("strenuous", "challenging", "demanding", "moderate", "easy"):
                    if re.search(rf"\b{grade}\b", content):
                        difficulty = grade
                        break
            if difficulty:
                break

    # --- Description: first substantive paragraphs from article/main content ---
    paras = []
    root = soup.find("article") or soup.find("main") or soup.body or soup
    for p in root.find_all("p"):
        text = p.get_text(" ", strip=True)
        if len(text) < 60:
            continue
        # Skip boilerplate
        if re.search(r"cookie|privacy|copyright|javascript|subscribe|newsletter", text, re.I):
            continue
        paras.append(text)
        if len(paras) >= 3:
            break
    description = "\n\n".join(paras)

    return {
        "stage_nr":         None,       # filled by caller
        "start_name":       start_name,
        "end_name":         end_name,
        "via":              None,
        "dist_km":          dist_km,
        "elev_up":          None,       # not available from this source
        "elev_down":        None,
        "duration_hrs":     None,       # not published by the WHW site
        "difficulty":       difficulty,
        "description":      description,
        "cantons":          [],
        "arrival_stations": [],
        "sbb_times":        {},
        "_slug":            slug,       # internal resume key — not imported to Supabase
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    p.add_argument("--refresh", action="store_true",
                   help="Re-fetch every stage even if cached in hikes.json")
    p.add_argument("--limit", type=int, default=None,
                   help="Only fetch the first N stages (smoke test)")
    args = p.parse_args()

    existing = load_existing()
    key = (LAND, ROUTE_TYPE, ROUTE_ID)
    route = existing.get(key) or {
        "route_id":    ROUTE_ID,
        "route_type":  ROUTE_TYPE,
        "land":        LAND,
        "name":        ROUTE_NAME,
        "description": ROUTE_DESC,
        "start":       "Milngavie",
        "end":         "Fort William",
        "total_km":    None,
        "stages":      [],
    }
    existing[key] = route
    existing_by_slug = {
        s.get("_slug"): s
        for s in route.get("stages", [])
        if s.get("_slug")
    }

    print(f"Fetching {ROUTE_URL}")
    html = fetch(ROUTE_URL, "route index")
    if not html:
        print("Could not fetch route index page. Aborting.")
        sys.exit(1)

    slugs = discover_stage_slugs(html)
    if not slugs:
        print("No stage links found on route index page. Aborting.")
        print("(The page layout may have changed — inspect the HTML and update discover_stage_slugs().)")
        sys.exit(1)

    print(f"Found {len(slugs)} stage{'s' if len(slugs) != 1 else ''}"
          + ("" if len(slugs) == 8 else f" (expected 8)"))
    if args.limit:
        slugs = slugs[:args.limit]
        print(f"  (limited to first {len(slugs)})")

    new_stages = []
    try:
        for i, slug in enumerate(slugs, start=1):
            cached = existing_by_slug.get(slug)

            if cached and not args.refresh:
                cached["stage_nr"] = i
                new_stages.append(cached)
                print(f"  [{i:2d}/{len(slugs)}] {slug}: cached")
                continue

            time.sleep(DELAY)
            print(f"  [{i:2d}/{len(slugs)}] {slug}: fetching...", end=" ", flush=True)
            page = fetch(f"{BASE}/the-route/{slug}/", slug)
            if not page:
                if cached:
                    cached["stage_nr"] = i
                    new_stages.append(cached)
                    print("kept cached data")
                else:
                    print("skipped")
                continue

            stage = parse_stage(page, slug)
            stage["stage_nr"] = i
            new_stages.append(stage)
            print(
                f"{stage['start_name']} → {stage['end_name']} "
                f"({stage['dist_km']} km, {stage['difficulty'] or '?'})"
            )

    except KeyboardInterrupt:
        print("\nInterrupted. Saving progress...")

    route["stages"] = new_stages
    if new_stages:
        route["start"] = new_stages[0]["start_name"]
        route["end"]   = new_stages[-1]["end_name"]
        total = sum(s["dist_km"] for s in new_stages if s.get("dist_km"))
        route["total_km"] = total or None

    save(list(existing.values()))

    parsed_dist = sum(1 for s in new_stages if s.get("dist_km"))
    parsed_diff = sum(1 for s in new_stages if s.get("difficulty"))
    print(
        f"\nDone. {len(new_stages)} stages — "
        f"{parsed_dist} with distance, {parsed_diff} with difficulty."
    )


if __name__ == "__main__":
    main()
