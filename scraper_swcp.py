#!/usr/bin/env python3
"""
South West Coast Path (UK) Stage Scraper
=========================================
Fetches the 53 day-stages of the South West Coast Path from
southwestcoastpath.org.uk's "walksdb" pages and merges them into hikes.json
with land="uk-hike", route_id=1, route_type="national".

Output is the same hikes.json the Swiss scraper writes to. Existing Swiss
routes are preserved (entries are keyed by (land, route_type, route_id)).

Usage:
    pip3 install cloudscraper beautifulsoup4 requests
    python3 scraper_swcp.py               # fetch all 53 stages + elevation
    python3 scraper_swcp.py --refresh     # re-fetch even if already cached
    python3 scraper_swcp.py --limit 3     # smoke test (first N stages only)
    python3 scraper_swcp.py --skip-elevation  # skip elevation enrichment

Push to Supabase via the shared importer (no UK-specific code needed):
    python3 scraper.py --import

Notes
-----
- Source: https://www.southwestcoastpath.org.uk/walk-coast-path/trip-planning/SWCP-itinerary/
  Each linked /walksdb/{id}/ page is one day-stage.
- The site is behind Cloudflare; cloudscraper handles the JS challenge.
- Distances are read directly from the "(X km)" figure on each page.
- Elevation (elev_up / elev_down) is computed from the route geometry returned
  by /walksdb/{id}/data/ (GeoJSON LineString), sampled and looked up via the
  free OpenTopoData SRTM 30m API (1000 req/day quota, 1 req/sec limit).
- sbb_times = {}, cantons = [], arrival_stations = [] — all gracefully
  ignored by the existing UI for UK rows.
"""

import argparse
import json
import re
import sys
import time

import requests as std_requests  # plain requests for OpenTopoData (no Cloudflare)

try:
    import cloudscraper
    from bs4 import BeautifulSoup
except ImportError:
    print("Missing dependency. Run:  pip3 install cloudscraper beautifulsoup4")
    sys.exit(1)

# Reuse persistence helpers from scraper.py — keeps the on-disk format
# in lockstep with the Swiss scraper.
from scraper import save, load_existing  # noqa: E402

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE          = "https://www.southwestcoastpath.org.uk"
ITINERARY_URL = f"{BASE}/walk-coast-path/trip-planning/SWCP-itinerary/"
DELAY         = 1.0   # seconds between SWCP requests — be polite

ROUTE_ID   = 1
LAND       = "uk"
ROUTE_TYPE = "national"
ROUTE_NAME = "South West Coast Path"
ROUTE_DESC = (
    "England's longest waymarked footpath: 630 miles (1,014 km) along the "
    "coastline of South West England from Minehead in Somerset to South "
    "Haven Point near Poole in Dorset. Officially divided into 53 day-stages "
    "passing through Exmoor, North Devon, Cornwall, South Devon and the "
    "Jurassic Coast."
)

MILES_TO_KM = 1.60934

# cloudscraper handles Cloudflare JS-challenge (site returns 403 to plain requests)
SESSION = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "darwin", "mobile": False}
)
SESSION.headers.update({
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": f"{BASE}/",
})

# Elevation enrichment via OpenTopoData (SRTM 30m — good UK coverage)
ELEV_SESSION    = std_requests.Session()
ELEV_DELAY      = 1.5   # OpenTopoData rate limit: 1 req/sec, so 1.5s is safe
ELEV_MAX_POINTS = 80    # points to sample per stage (API accepts up to 100)
ELEV_NOISE_M    = 2     # ignore elevation changes smaller than this (GPS noise)
OPENTOPODATA    = "https://api.opentopodata.org/v1/srtm30m"


# ---------------------------------------------------------------------------
# Fetch helpers
# ---------------------------------------------------------------------------

def fetch(url, label):
    """GET via SESSION (cloudscraper). Returns text, or None on 404 / give-up."""
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
# Elevation
# ---------------------------------------------------------------------------

def fetch_elevation(walk_id):
    """
    Fetch route geometry from /walksdb/{id}/data/ then compute cumulative
    ascent/descent via OpenTopoData SRTM 30m.
    Returns (elev_up, elev_down) as int metres, or (None, None) on failure.
    """
    # 1. Route coordinates from the SWCP data endpoint
    try:
        r = SESSION.get(f"{BASE}/walksdb/{walk_id}/data/", timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f" [warn] route data fetch failed for walk {walk_id}: {e}")
        return None, None

    all_coords = []  # [[lng, lat], ...]
    for poly_str in data.get("route_polys", []):
        try:
            ls = json.loads(poly_str)
            all_coords.extend(ls.get("coordinates", []))
        except (json.JSONDecodeError, KeyError):
            pass

    if len(all_coords) < 2:
        return None, None

    # 2. Sample to ELEV_MAX_POINTS, always keeping the last point.
    # Use ceil division so we never exceed the cap even for short polylines.
    n       = len(all_coords)
    step    = max(1, -(-n // ELEV_MAX_POINTS))  # ceiling division
    sampled = all_coords[::step][:ELEV_MAX_POINTS]
    if sampled[-1] != all_coords[-1]:
        sampled.append(all_coords[-1])

    # 3. Query OpenTopoData
    time.sleep(ELEV_DELAY)
    loc_str = "|".join(f"{c[1]:.6f},{c[0]:.6f}" for c in sampled)
    try:
        resp = ELEV_SESSION.get(f"{OPENTOPODATA}?locations={loc_str}", timeout=30)
        if resp.status_code == 429:
            print(" [warn] OpenTopoData rate limited — elevation skipped")
            return None, None
        resp.raise_for_status()
        elevations = [
            pt["elevation"] for pt in resp.json().get("results", [])
            if pt.get("elevation") is not None
        ]
    except Exception as e:
        print(f" [warn] OpenTopoData error for walk {walk_id}: {e}")
        return None, None

    if len(elevations) < 2:
        return None, None

    # 4. Cumulative ascent / descent with noise threshold
    asc = desc = 0.0
    for i in range(1, len(elevations)):
        diff = elevations[i] - elevations[i - 1]
        if diff > ELEV_NOISE_M:
            asc += diff
        elif diff < -ELEV_NOISE_M:
            desc += abs(diff)

    return round(asc), round(desc)


# ---------------------------------------------------------------------------
# Page parsers
# ---------------------------------------------------------------------------

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


def parse_walk(html, walk_id):
    """Parse a /walksdb/{id}/ page into a stage dict (without stage_nr)."""
    soup = BeautifulSoup(html, "html.parser")

    # --- Title: h1 is '<span>Walk</span> - Foo to Bar', strip the "Walk - " prefix ---
    h1 = soup.find("h1")
    title = re.sub(r"^Walk\s*[-–—]\s*", "", h1.get_text(" ", strip=True), flags=re.I).strip() if h1 else ""
    if not title:
        t = soup.find("title")
        # "<title>Foo to Bar - Walk - South West Coast Path</title>"
        raw = t.get_text(strip=True) if t else ""
        title = re.sub(r"\s*[-–—]\s*(Walk|South West Coast Path|SWCP).*$", "", raw, flags=re.I).strip()
    title = title or f"SWCP walk {walk_id}"

    # "Foo to Bar" → start / end
    if " to " in title:
        start_name, end_name = (s.strip() for s in title.split(" to ", 1))
    else:
        start_name = end_name = title

    # --- Distance: use km from h2.mainTitle to avoid unit-conversion rounding ---
    dist_km = None
    h2 = soup.find("h2", class_="mainTitle")
    if h2:
        h2_text = h2.get_text()
        m = re.search(r"\((\d+(?:\.\d+)?)\s*km\)", h2_text)
        if m:
            dist_km = round(float(m.group(1)))
        else:
            m = re.search(r"(\d+(?:\.\d+)?)\s*mile", h2_text, re.I)
            if m:
                dist_km = round(float(m.group(1)) * MILES_TO_KM)

    # --- Walking time: not published by the SWCP site for these stages ---
    duration_hrs = None

    # --- Difficulty: from <p class="difficulty"> image filename (most reliable) ---
    # Site uses: easy / moderate / challenging  (e.g. "challenging-walk.png")
    difficulty = None
    diff_p = soup.find("p", class_="difficulty")
    if diff_p:
        img = diff_p.find("img")
        if img and img.get("src"):
            m = re.search(r"/(easy|moderate|challenging|strenuous|severe)-walk", img["src"], re.I)
            if m:
                difficulty = m.group(1).lower()
        if not difficulty:
            diff_text = diff_p.get_text(" ", strip=True).lower()
            for grade in ("challenging", "strenuous", "severe", "moderate", "easy"):
                if re.search(rf"\b{grade}\b", diff_text):
                    difficulty = grade
                    break

    # --- Description: substantive paragraphs from the walkDetails div ---
    walk_div = soup.find(id="walkDetails")
    paras = []
    if walk_div:
        for p in walk_div.find_all("p"):
            if p.get("class"):   # skip location / difficulty paragraphs (have CSS classes)
                continue
            s = p.get_text(" ", strip=True)
            if len(s) > 60:
                paras.append(s)
            if len(paras) >= 3:
                break
    if not paras:
        main = soup.find("main") or soup.find("article") or soup.body or soup
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
        "elev_up":          None,           # filled by fetch_elevation()
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
    p.add_argument("--skip-elevation", action="store_true",
                   help="Skip elevation enrichment (faster; elev_up/down stay null)")
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
          + ("" if len(walk_ids) == 53 else f" (expected 53)"))
    if args.limit:
        walk_ids = walk_ids[:args.limit]
        print(f"  (limited to first {len(walk_ids)})")

    new_stages = []
    try:
        for i, wid in enumerate(walk_ids, start=1):
            cached = existing_by_walk.get(wid)

            # ---- Use cached stage if we have one and aren't refreshing ----
            if cached and not args.refresh:
                stage = cached
                stage["stage_nr"] = i

                # Fill in elevation if it's missing and not skipped
                needs_elev = (
                    not args.skip_elevation
                    and stage.get("elev_up") is None
                )
                if needs_elev:
                    print(f"  [{i:2d}/{len(walk_ids)}] walk {wid}: cached, fetching elevation...",
                          end=" ", flush=True)
                    elev_up, elev_down = fetch_elevation(wid)
                    stage["elev_up"]   = elev_up
                    stage["elev_down"] = elev_down
                    if elev_up is not None:
                        print(f"↑{elev_up}m ↓{elev_down}m")
                    else:
                        print("elevation unavailable")
                else:
                    elev_str = f"↑{stage['elev_up']}m" if stage.get("elev_up") else "no elev"
                    print(f"  [{i:2d}/{len(walk_ids)}] walk {wid}: cached ({elev_str})")

                new_stages.append(stage)
                continue

            # ---- Fetch the walk page ----
            time.sleep(DELAY)
            print(f"  [{i:2d}/{len(walk_ids)}] walk {wid}: fetching...", end=" ", flush=True)
            page = fetch(f"{BASE}/walksdb/{wid}/", f"walk {wid}")
            if not page:
                if cached:
                    cached["stage_nr"] = i
                    new_stages.append(cached)
                    print("kept cached data")
                else:
                    print("skipped")
                continue

            stage = parse_walk(page, wid)
            stage["stage_nr"] = i

            # ---- Elevation ----
            if not args.skip_elevation:
                elev_up, elev_down = fetch_elevation(wid)
                stage["elev_up"]   = elev_up
                stage["elev_down"] = elev_down
            else:
                elev_up = elev_down = None

            new_stages.append(stage)
            hrs      = f"{stage['duration_hrs']}h" if stage["duration_hrs"] else "-"
            elev_str = f"↑{elev_up}m ↓{elev_down}m" if elev_up is not None else "no elev"
            print(
                f"{stage['start_name']} → {stage['end_name']} "
                f"({stage['dist_km']} km, {hrs}, {stage['difficulty'] or '?'}, {elev_str})"
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
    parsed_elev = sum(1 for s in new_stages if s.get("elev_up") is not None)
    parsed_diff = sum(1 for s in new_stages if s.get("difficulty"))
    print(
        f"\nDone. {len(new_stages)} UK stages — "
        f"{parsed_dist} with distance, {parsed_elev} with elevation, "
        f"{parsed_diff} with difficulty."
    )


if __name__ == "__main__":
    main()
