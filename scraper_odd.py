#!/usr/bin/env python3
"""
Offa's Dyke Path Scraper
========================
Fetches the 12 day-stages of Offa's Dyke Path from nationaltrail.co.uk
and merges them into hikes.json with land="uk", route_id=3,
route_type="national".

Output is the same hikes.json the Swiss scraper writes to. Existing routes
(Swiss, SWCP, WHW) are preserved — entries are keyed by (land, route_type, route_id).

Usage:
    pip3 install requests beautifulsoup4
    python3 scraper_odd.py               # fetch all 12 stages
    python3 scraper_odd.py --refresh     # re-fetch even if already cached

Push to Supabase via the shared importer (no ODP-specific code needed):
    python3 scraper.py --import

Notes
-----
- Source: https://www.nationaltrail.co.uk/en_GB/trails/offas-dyke-path/route/
  All 12 stages are on a single page — no individual stage URLs exist.
- Stage headings are bold text: "Start to End – X miles (Y Km)"
- Distances are taken from the parenthetical km figure.
- No GeoJSON/GPX API is exposed, so elev_up/elev_down are null.
- duration_hrs is null (not published by the site).
- difficulty: inferred from description text where standard keywords appear.
- sbb_times = {}, cantons = [], arrival_stations = [] — ignored by the UI
  for UK rows.
"""

import argparse
import re
import sys
import time

from bs4 import BeautifulSoup

try:
    import cloudscraper
    _SESSION_FACTORY = lambda: cloudscraper.create_scraper()
except ImportError:
    import requests
    _SESSION_FACTORY = lambda: requests.Session()

try:
    from scraper import save, load_existing
except ImportError:
    print("scraper.py not found. Run from the project root.")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ROUTE_URL = "https://www.nationaltrail.co.uk/en_GB/trails/offas-dyke-path/route/"
DELAY     = 1.0

ROUTE_ID   = 3
LAND       = "uk"
ROUTE_TYPE = "national"
ROUTE_NAME = "Offa's Dyke Path"
ROUTE_DESC = (
    "177 miles (285 km) from Sedbury Cliffs near Chepstow on the banks of the "
    "Severn estuary to Prestatyn on the shores of the Irish Sea. The route "
    "follows the spectacular dyke King Offa ordered to be constructed in the "
    "8th century and crosses the England–Wales border more than 20 times, "
    "passing through the Black Mountains, the Shropshire Hills, and the "
    "Clwydian Range."
)

SESSION = _SESSION_FACTORY()
SESSION.headers.update({
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": "https://www.nationaltrail.co.uk/",
})

# Heading patterns:
#   "Sedbury Cliffs to Monmouth – 17.5 miles (28 Km)"  (most stages)
#   "Bodfari – Prestatyn – 12 miles (19 Km)"            (final stage uses em-dash instead of "to")
_HEADING_RE = re.compile(
    r"^(.+?)\s+(?:to|[–—])\s+(.+?)\s*[–—]\s*[\d.]+\s+miles?\s*\((\d+(?:\.\d+)?)\s*[Kk]m\)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Fetch helper
# ---------------------------------------------------------------------------

def fetch(url, label):
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
# Page parser
# ---------------------------------------------------------------------------

def parse_stages(html):
    """
    Parse all stages from the single route-description page.
    Returns a list of stage dicts (without stage_nr — caller assigns).
    """
    soup = BeautifulSoup(html, "html.parser")

    # Collect all text nodes that are direct children of <strong> or <b> tags,
    # then walk the DOM to find adjacent paragraph text for descriptions.
    stages = []

    # Find every element whose direct text matches the heading pattern.
    # The site wraps headings in <strong> inside <p>.
    for strong in soup.find_all(["strong", "b"]):
        text = strong.get_text(" ", strip=True)
        m = _HEADING_RE.match(text)
        if not m:
            continue

        start_name = m.group(1).strip()
        end_name   = m.group(2).strip()
        dist_km    = round(float(m.group(3)))

        # Infer difficulty from nearby paragraph text
        difficulty = None
        desc_paras = []
        el = strong.parent  # typically <p> containing the <strong>
        sibling = el.find_next_sibling()
        while sibling:
            tag = sibling.name
            if tag in ("p", "div", "ul", "li"):
                sibling_text = sibling.get_text(" ", strip=True)
                if len(sibling_text) < 30:
                    sibling = sibling.find_next_sibling()
                    continue
                # Stop when we hit the next stage heading
                if _HEADING_RE.match(sibling_text):
                    break
                # Also stop if we encounter another <strong> heading inside
                inner_strong = sibling.find(["strong", "b"])
                if inner_strong and _HEADING_RE.match(inner_strong.get_text(" ", strip=True)):
                    break
                if not re.search(r"cookie|privacy|copyright|javascript|newsletter", sibling_text, re.I):
                    desc_paras.append(sibling_text)
                    if difficulty is None:
                        lower = sibling_text.lower()
                        for grade in ("strenuous", "challenging", "demanding", "moderate", "easy"):
                            if re.search(rf"\b{grade}\b", lower):
                                difficulty = grade
                                break
            elif tag in ("h1", "h2", "h3", "h4", "h5"):
                # Next section heading — stop
                break
            sibling = sibling.find_next_sibling()
            if len(desc_paras) >= 3:
                break

        stages.append({
            "stage_nr":         None,
            "start_name":       start_name,
            "end_name":         end_name,
            "via":              None,
            "dist_km":          dist_km,
            "elev_up":          None,
            "elev_down":        None,
            "duration_hrs":     None,
            "difficulty":       difficulty,
            "description":      "\n\n".join(desc_paras),
            "cantons":          [],
            "arrival_stations": [],
            "sbb_times":        {},
        })

    return stages


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="Scrape Offa's Dyke Path stages")
    p.add_argument("--refresh", action="store_true",
                   help="Re-fetch the route page even if stages are already cached")
    args = p.parse_args()

    existing = load_existing()
    key = (LAND, ROUTE_TYPE, ROUTE_ID)
    route = existing.get(key) or {
        "route_id":    ROUTE_ID,
        "route_type":  ROUTE_TYPE,
        "land":        LAND,
        "name":        ROUTE_NAME,
        "description": ROUTE_DESC,
        "start":       "Sedbury Cliffs",
        "end":         "Prestatyn",
        "total_km":    285,
        "stages":      [],
    }
    existing[key] = route

    cached_stages = route.get("stages", [])
    if cached_stages and not args.refresh:
        print(f"Already have {len(cached_stages)} cached stages. Use --refresh to re-fetch.")
        save(list(existing.values()))
        return

    print(f"Fetching {ROUTE_URL}")
    time.sleep(DELAY)
    html = fetch(ROUTE_URL, "route page")
    if not html:
        print("Could not fetch route page. Aborting.")
        sys.exit(1)

    stages = parse_stages(html)
    if not stages:
        print("No stages parsed from the page. The layout may have changed.")
        print("Inspect the HTML and update parse_stages() accordingly.")
        sys.exit(1)

    expected = 12
    if len(stages) != expected:
        print(f"  [warn] expected {expected} stages, got {len(stages)}")

    for i, s in enumerate(stages, start=1):
        s["stage_nr"] = i
        print(
            f"  [{i:2d}/{len(stages)}] {s['start_name']} → {s['end_name']} "
            f"({s['dist_km']} km, {s['difficulty'] or '?'})"
        )

    route["stages"]   = stages
    route["start"]    = stages[0]["start_name"]
    route["end"]      = stages[-1]["end_name"]
    route["total_km"] = sum(s["dist_km"] for s in stages if s.get("dist_km")) or 285

    save(list(existing.values()))
    parsed_diff = sum(1 for s in stages if s.get("difficulty"))
    print(f"\nDone. {len(stages)} stages — {parsed_diff} with difficulty inferred.")


if __name__ == "__main__":
    main()
