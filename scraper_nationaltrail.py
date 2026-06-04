#!/usr/bin/env python3
"""
National Trail Scraper (UK)
============================
Fetches day-stage data for UK National Trails from nationaltrail.co.uk.
Covers route_ids 5–8 (land="uk"):

  5 — South Downs Way       (Winchester → Eastbourne, 160 km, ~9 stages)
  6 — Cotswold Way          (Chipping Campden → Bath, 164 km, 15 stages)
  7 — Hadrian's Wall Path   (Wallsend → Bowness-on-Solway, 135 km, 6 stages)
  8 — Pembrokeshire Coast Path (St Dogmaels → Amroth, 300 km, 14 stages)

ODP (route_id=3) already has its own scraper (scraper_odd.py).
Pennine Way (route_id=4) uses OSM (scraper_osm.py).

Usage:
    pip3 install requests beautifulsoup4 cloudscraper
    python3 scraper_nationaltrail.py              # all 4 trails
    python3 scraper_nationaltrail.py --only sdw   # one trail by short code
    python3 scraper_nationaltrail.py --only cw
    python3 scraper_nationaltrail.py --only hwp
    python3 scraper_nationaltrail.py --only pcp
    python3 scraper_nationaltrail.py --refresh    # re-fetch even if cached
    python3 scraper.py --import

Notes
-----
- Source: https://www.nationaltrail.co.uk/en_GB/trails/{slug}/route/
  All stages are on a single page per trail — no individual stage URLs exist.
- Heading format: "Start to End – X miles (Y km)" inside <strong> tags.
- Hadrian's Wall Path headings have no distance — dist_km is null for that trail.
- elev_up/elev_down: null (no GeoJSON/elevation API exposed by the site).
- duration_hrs: null (not published).
- The site is behind Cloudflare — cloudscraper handles the JS challenge.
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
    print("[warn] cloudscraper not found; falling back to requests (may hit Cloudflare)")
    _SESSION_FACTORY = lambda: requests.Session()

try:
    from scraper import save, load_existing
except ImportError:
    print("scraper.py not found. Run from the project root.")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Trail catalog
# ---------------------------------------------------------------------------

TRAILS = [
    {
        "slug":        "south-downs-way",
        "short":       "sdw",
        "route_id":    5,
        "name":        "South Downs Way",
        "description": (
            "The South Downs Way runs 160 km (100 miles) along the chalk ridge "
            "of the South Downs from Winchester in Hampshire to Eastbourne in East "
            "Sussex. It crosses open downland, ancient hillforts, and river valleys, "
            "ending at the dramatic Seven Sisters chalk cliffs on the English Channel."
        ),
        "start":       "Winchester",
        "end":         "Eastbourne",
        "total_km":    160,
        "expected":    9,
    },
    {
        "slug":        "cotswold-way",
        "short":       "cw",
        "route_id":    6,
        "name":        "Cotswold Way",
        "description": (
            "The Cotswold Way follows 164 km (102 miles) of the limestone Cotswold "
            "escarpment from Chipping Campden in Gloucestershire to the Georgian city "
            "of Bath in Somerset, passing honey-stone villages, ancient drove roads, "
            "and expansive views across the Severn Vale and Welsh hills."
        ),
        "start":       "Chipping Campden",
        "end":         "Bath",
        "total_km":    164,
        "expected":    15,
    },
    {
        "slug":        "hadrians-wall-path",
        "short":       "hwp",
        "route_id":    7,
        "name":        "Hadrian's Wall Path",
        "description": (
            "Hadrian's Wall Path crosses northern England coast to coast over 135 km "
            "(84 miles), from Wallsend on the River Tyne to Bowness-on-Solway on the "
            "Solway Firth. It follows the line of the Roman frontier built from AD 122, "
            "passing forts, milecastles, and the dramatic crags of the Whin Sill."
        ),
        "start":       "Wallsend",
        "end":         "Bowness-on-Solway",
        "total_km":    135,
        "expected":    6,
    },
    {
        "slug":        "pembrokeshire-coast-path",
        "short":       "pcp",
        "route_id":    8,
        "name":        "Pembrokeshire Coast Path",
        "description": (
            "The Pembrokeshire Coast Path follows 300 km (186 miles) of spectacular "
            "coastline from St Dogmaels in the north to Amroth in the south, almost "
            "entirely within the Pembrokeshire Coast National Park. It takes in sea "
            "cliffs, sandy beaches, headlands, and historic harbour towns through one "
            "of the UK's most dramatic coastal landscapes."
        ),
        "start":       "St Dogmaels",
        "end":         "Amroth",
        "total_km":    300,
        "expected":    15,
    },
]

BASE_URL  = "https://www.nationaltrail.co.uk/en_GB/trails/{slug}/route/"
LAND      = "uk"
ROUTE_TYPE = "national"
DELAY     = 1.5

# "Start to End – X miles (Y km)"  or  "Start – End – X miles (Y km)"
# Matches ODP, South Downs Way, Cotswold Way (when full text including distance is checked)
_HEADING_DIST_RE = re.compile(
    r"^(.+?)\s+(?:to|[–—])\s+(.+?)\s*[–—]\s*[\d.]+\s+miles?\s*\((\d+(?:\.\d+)?)\s*[Kk]m\)",
    re.IGNORECASE,
)
# "Start to End X miles (Y km)" — no dash before the miles figure (Pembrokeshire)
_HEADING_DIST2_RE = re.compile(
    r"^(.+?)\s+to\s+(.+?)\s+\d+(?:\.\d+)?\s+miles?\s*\((\d+(?:\.\d+)?)\s*[Kk]m\)",
    re.IGNORECASE,
)
# Name-only fallback: "Place to Place" with no distance (Hadrian's Wall)
_HEADING_NAME_RE = re.compile(
    r"^([A-Z][^–—\n]{3,60}?)\s+to\s+([A-Z][^–—\n]{3,60})$",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------

def make_session():
    s = _SESSION_FACTORY()
    s.headers.update({
        "Accept-Language": "en-GB,en;q=0.9",
        "Referer": "https://www.nationaltrail.co.uk/",
    })
    return s


def fetch(session, url, label):
    for attempt in range(2):
        try:
            r = session.get(url, timeout=20)
            if r.status_code == 404:
                print(f"  [warn] 404 for {label}")
                return None
            if r.status_code >= 500 and attempt == 0:
                print(f"  [warn] {r.status_code} for {label}, retrying in 5s…")
                time.sleep(5)
                continue
            r.raise_for_status()
            return r.text
        except Exception as e:
            if attempt == 0:
                print(f"  [warn] {e}, retrying in 5s")
                time.sleep(5)
                continue
            print(f"  [error] giving up on {label}: {e}")
            return None
    return None


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def parse_stages(html):
    """
    Extract stage dicts from a single nationaltrail.co.uk route page.

    Three-pass strategy:
      Pass 1 — "Start to End – X miles (Y km)" in strong text OR parent element text
               (handles ODP-style, South Downs Way, and Cotswold Way where the
               distance sits outside the <strong> tag in the parent <li>).
      Pass 2 — "Start to End X miles (Y km)" — no dash before miles (Pembrokeshire).
      Pass 3 — "Start to End" name-only (Hadrian's Wall, no per-section distances).

    Returns list of stage dicts (stage_nr not yet set).
    """
    soup = BeautifulSoup(html, "html.parser")
    stages = _parse_with_re(soup, _HEADING_DIST_RE, has_dist=True)
    if not stages:
        stages = _parse_with_re(soup, _HEADING_DIST2_RE, has_dist=True)
    if not stages:
        stages = _parse_with_re(soup, _HEADING_NAME_RE, has_dist=False)
    return stages


def _parse_with_re(soup, pattern, has_dist):
    stages = []
    for strong in soup.find_all(["strong", "b"]):
        # Try matching the strong tag text first; fall back to parent element text.
        # This handles Cotswold Way where the distance sits outside the <strong>.
        strong_text = strong.get_text(" ", strip=True)
        parent_text = strong.parent.get_text(" ", strip=True) if strong.parent else ""
        m = pattern.match(strong_text) or pattern.match(parent_text)
        if not m:
            continue

        start_name = m.group(1).strip()
        end_name   = m.group(2).strip()
        dist_km    = round(float(m.group(3)), 1) if has_dist else None

        # Collect description paragraphs and infer difficulty from nearby text
        difficulty  = None
        desc_paras  = []
        el      = strong.parent
        sibling = el.find_next_sibling()
        while sibling:
            tag = sibling.name
            if tag in ("p", "div", "ul", "li"):
                t = sibling.get_text(" ", strip=True)
                if len(t) < 30:
                    sibling = sibling.find_next_sibling()
                    continue
                # Stop at next stage heading
                if pattern.match(t):
                    break
                inner = sibling.find(["strong", "b"])
                if inner and pattern.match(inner.get_text(" ", strip=True)):
                    break
                if not re.search(r"cookie|privacy|copyright|javascript|newsletter", t, re.I):
                    desc_paras.append(t)
                    if difficulty is None:
                        low = t.lower()
                        for grade in ("strenuous", "challenging", "demanding", "moderate", "easy"):
                            if re.search(rf"\b{grade}\b", low):
                                difficulty = grade
                                break
            elif tag in ("h1", "h2", "h3", "h4", "h5"):
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
    p = argparse.ArgumentParser(description="Scrape UK National Trails from nationaltrail.co.uk")
    p.add_argument("--only",    metavar="SHORT",
                   help="Only scrape one trail by short code (sdw, cw, hwp, pcp)")
    p.add_argument("--refresh", action="store_true",
                   help="Re-fetch even if stages are already cached")
    args = p.parse_args()

    trails = TRAILS
    if args.only:
        trails = [t for t in TRAILS if t["short"] == args.only.lower()]
        if not trails:
            shorts = ", ".join(t["short"] for t in TRAILS)
            print(f"Unknown trail '{args.only}'. Valid codes: {shorts}")
            sys.exit(1)

    existing = load_existing()
    session  = make_session()

    for trail in trails:
        key = (LAND, ROUTE_TYPE, trail["route_id"])
        route = existing.get(key) or {
            "route_id":    trail["route_id"],
            "route_type":  ROUTE_TYPE,
            "land":        LAND,
            "name":        trail["name"],
            "description": trail["description"],
            "start":       trail["start"],
            "end":         trail["end"],
            "total_km":    trail["total_km"],
            "stages":      [],
        }
        existing[key] = route

        cached = route.get("stages", [])
        if cached and not args.refresh:
            print(f"{trail['name']}: {len(cached)} cached stages — use --refresh to re-fetch")
            continue

        url = BASE_URL.format(slug=trail["slug"])
        print(f"\n{trail['name']}")
        print(f"  Fetching {url}")
        time.sleep(DELAY)
        html = fetch(session, url, trail["name"])
        if not html:
            print(f"  [error] Could not fetch — skipping")
            continue

        stages = parse_stages(html)
        if not stages:
            print(f"  [warn] No stages parsed — page layout may have changed")
            continue

        expected = trail["expected"]
        if len(stages) != expected:
            print(f"  [warn] Expected {expected} stages, got {len(stages)}")

        for i, s in enumerate(stages, start=1):
            s["stage_nr"] = i
            dist  = f"{s['dist_km']} km" if s["dist_km"] else "no dist"
            diff  = s["difficulty"] or "?"
            print(f"  [{i:2d}/{len(stages)}] {s['start_name']} → {s['end_name']} ({dist}, {diff})")

        route["stages"]   = stages
        route["start"]    = stages[0]["start_name"]
        route["end"]      = stages[-1]["end_name"]
        route["total_km"] = (
            round(sum(s["dist_km"] for s in stages if s["dist_km"]), 1)
            or trail["total_km"]
        )

    save(list(existing.values()))
    print("\nDone.")


if __name__ == "__main__":
    main()
