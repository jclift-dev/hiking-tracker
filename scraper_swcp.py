#!/usr/bin/env python3
"""
South West Coast Path (UK) Stage Scraper
=========================================
Fetches the 52 day-stages of the South West Coast Path from
southwestcoastpath.org.uk's "walksdb" pages and merges them into hikes.json
with land="uk-hike", route_id=1, route_type="national".

Output is the same hikes.json the Swiss scraper writes to. Existing Swiss
routes are preserved (entries are keyed by (land, route_type, route_id)).

Usage:
    pip3 install requests beautifulsoup4
    python3 scraper_swcp.py             # fetch all 52 stages
    python3 scraper_swcp.py --refresh   # re-fetch even if already cached
    python3 scraper_swcp.py --limit 3   # smoke test (first N stages only)

Push to Supabase via the shared importer (no UK-specific code needed):
    python3 scraper.py --import

Notes
-----
- Source: https://www.southwestcoastpath.org.uk/walk-coast-path/trip-planning/SWCP-itinerary/
  Each linked /walksdb/{id}/ page is one day-stage.
- Distances are converted miles → km on scrape (rounded to nearest int) so
  the existing schema (`dist_km`) stays consistent.
- elev_up / elev_down are left null for now — walksdb pages don't reliably
  publish per-stage ascent. The web app's elevProfile() already silently
  hides the terrain icon when both are null.
- sbb_times = {}, cantons = [], arrival_stations = [] — all gracefully
  ignored by the existing UI for UK rows.
"""

import argparse
import json
import re
import sys
import time

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Missing dependency. Run:  pip3 install requests beautifulsoup4")
    sys.exit(1)

# Reuse persistence helpers from scraper.py — keeps the on-disk format
# in lockstep with the Swiss scraper.
from scraper import save, load_existing  # noqa: E402

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE          = "https://www.southwestcoastpath.org.uk"
ITINERARY_URL = f"{BASE}/walk-coast-path/trip-planning/SWCP-itinerary/"
DELAY         = 1.0   # seconds between requests — small site, be polite

ROUTE_ID      = 1
LAND          = "uk-hike"
ROUTE_TYPE    = "national"
ROUTE_NAME    = "South West Coast Path"
ROUTE_DESC    = (
    "England's longest waymarked footpath: 630 miles (1,014 km) along the "
    "coastline of South West England from Minehead in Somerset to South "
    "Haven Point near Poole in Dorset. Officially divided into 52 day-stages "
    "passing through Exmoor, North Devon, Cornwall, South Devon and the "
    "Jurassic Coast."
)

MILES_TO_KM = 1.60934

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": f"{BASE}/",
})

GRADES = ("severe", "strenuous", "moderate", "easy")  # checked in order — most-specific first


# ---------------------------------------------------------------------------
# Fetch + parse
# ---------------------------------------------------------------------------

def fetch(url, label):
    """GET with one retry on transient errors. Returns text, or None on 404 / give-up."""
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
        except requests.RequestException as e:
            if attempt == 0:
                print(f"  [warn] error for {label}: {e}, retrying in 5s")
                time.sleep(5)
                continue
            print(f"  [error] giving up on {label}: {e}")
            return None
    return None


def discover_walk_ids(html):
    """
    Find ordered /walksdb/{id}/ links on the SWCP-itinerary page.
    Returns first-seen-order list of int IDs.
    """
    soup = BeautifulSoup(html, "html.parser")
    seen, ids = set(), []
    for a in soup.select('a[href*="/walksdb/"]'):
        m = re.search(r"/walksdb/(\d+)/?", a.get("href", ""))
        if not m:
            continue
        wid = int(m.group(1))
        if wid in seen:
            continue
        seen.add(wid)
        ids.append(wid)
    return ids


_TITLE_TAIL_RE = re.compile(r"\s*[|·\-–—]\s*(South West Coast Path|SWCP).*$", re.I)


def parse_walk(html, walk_id):
    """Parse a /walksdb/{id}/ page into a stage dict (without stage_nr)."""
    soup = BeautifulSoup(html, "html.parser")

    # --- Title ---
    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else ""
    if not title:
        t = soup.find("title")
        title = t.get_text(strip=True) if t else f"SWCP walk {walk_id}"
    title = _TITLE_TAIL_RE.sub("", title).strip()

    # "Foo to Bar" → start / end
    if " to " in title:
        start_name, end_name = (s.strip() for s in title.split(" to ", 1))
    else:
        start_name = end_name = title

    # --- Body text for regex extraction ---
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text(" ", strip=True)

    # --- Distance: miles → km ---
    miles = None
    m = re.search(r"(\d+(?:\.\d+)?)\s*mile", text, re.I)
    if m:
        try:
            miles = float(m.group(1))
        except ValueError:
            pass
    dist_km = round(miles * MILES_TO_KM) if miles else None

    # --- Walking time ---
    duration_hrs = None
    # "5h 30m" / "5 hours 30 minutes" / "5 hr 30 min"
    m = re.search(r"(\d+)\s*h(?:ou)?r?s?\s*(?:and\s*)?(\d+)\s*m(?:in)?", text, re.I)
    if m:
        duration_hrs = int(m.group(1)) + int(m.group(2)) / 60
    else:
        # "5.5 hours" / "5 hrs" / "5h"
        m = re.search(r"(\d+(?:\.\d+)?)\s*h(?:ou)?r?s?\b", text, re.I)
        if m:
            try:
                duration_hrs = float(m.group(1))
            except ValueError:
                pass
    if duration_hrs is not None:
        duration_hrs = round(duration_hrs, 1)

    # --- Difficulty grade (first match of severe > strenuous > moderate > easy) ---
    difficulty = None
    lower = text.lower()
    for grade in GRADES:
        if re.search(rf"\b{grade}\b", lower):
            difficulty = grade
            break

    # --- Description: first few substantive paragraphs ---
    paras = []
    for p in main.find_all("p"):
        s = p.get_text(" ", strip=True)
        if len(s) > 60:
            paras.append(s)
        if len(paras) >= 3:
            break
    description = "\n\n".join(paras)

    return {
        "stage_nr":         None,           # filled by caller
        "start_name":       start_name,
        "end_name":         end_name,
        "via":              None,
        "dist_km":          dist_km,
        "elev_up":          None,
        "elev_down":        None,
        "duration_hrs":     duration_hrs,
        "difficulty":       difficulty,
        "description":      description,
        "cantons":          [],
        "arrival_stations": [],
        "sbb_times":        {},
        "_walk_id":         walk_id,        # internal, for resume — ignored by importer
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
        "start":       "Minehead",
        "end":         "South Haven Point",
        "total_km":    None,
        "stages":      [],
    }
    existing[key] = route
    existing_by_walk = {s.get("_walk_id"): s for s in route.get("stages", []) if s.get("_walk_id")}

    print(f"Fetching {ITINERARY_URL}")
    html = fetch(ITINERARY_URL, "itinerary index")
    if not html:
        print("Could not fetch itinerary page. Aborting.")
        sys.exit(1)

    walk_ids = discover_walk_ids(html)
    if not walk_ids:
        print("No /walksdb/ links found on itinerary page. Aborting.")
        print("(The page layout may have changed — inspect the HTML and update discover_walk_ids().)")
        sys.exit(1)

    print(f"Found {len(walk_ids)} walk IDs"
          + (f" (expected ~52)" if len(walk_ids) != 52 else ""))
    if args.limit:
        walk_ids = walk_ids[:args.limit]
        print(f"  (limited to first {len(walk_ids)})")

    new_stages = []
    try:
        for i, wid in enumerate(walk_ids, start=1):
            if not args.refresh and wid in existing_by_walk:
                stage = existing_by_walk[wid]
                stage["stage_nr"] = i
                new_stages.append(stage)
                print(f"  [{i:2d}/{len(walk_ids)}] walk {wid}: cached")
                continue

            time.sleep(DELAY)
            print(f"  [{i:2d}/{len(walk_ids)}] walk {wid}: fetching...", end=" ", flush=True)
            page = fetch(f"{BASE}/walksdb/{wid}/", f"walk {wid}")
            if not page:
                # Preserve any existing data we already had
                if wid in existing_by_walk:
                    stage = existing_by_walk[wid]
                    stage["stage_nr"] = i
                    new_stages.append(stage)
                    print("kept cached data")
                else:
                    print("skipped")
                continue

            stage = parse_walk(page, wid)
            stage["stage_nr"] = i
            new_stages.append(stage)
            print(
                f"{stage['start_name']} → {stage['end_name']} "
                f"({stage['dist_km']} km, "
                f"{stage['duration_hrs']}h, "
                f"{stage['difficulty'] or '?'})"
            )
    except KeyboardInterrupt:
        print("\nInterrupted. Saving progress...")

    # Update route metadata from harvested stages
    route["stages"] = new_stages
    if new_stages:
        route["start"] = new_stages[0]["start_name"]
        route["end"]   = new_stages[-1]["end_name"]
        total = sum(s["dist_km"] for s in new_stages if s.get("dist_km"))
        route["total_km"] = total or None

    save(list(existing.values()))

    parsed_dist = sum(1 for s in new_stages if s.get("dist_km"))
    parsed_time = sum(1 for s in new_stages if s.get("duration_hrs"))
    parsed_diff = sum(1 for s in new_stages if s.get("difficulty"))
    print(
        f"\nDone. {len(new_stages)} UK stages — "
        f"{parsed_dist} with distance, {parsed_time} with walking time, "
        f"{parsed_diff} with difficulty."
    )


if __name__ == "__main__":
    main()
