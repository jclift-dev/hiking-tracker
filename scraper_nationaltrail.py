#!/usr/bin/env python3
"""
National Trail Scraper (UK)
============================
Fetches day-stage data for UK National Trails from nationaltrail.co.uk.
Covers route_ids 5–8 (land="uk"):

  5 — South Downs Way       (Winchester → Eastbourne, 160 km, 9 stages)
  6 — Cotswold Way          (Chipping Campden → Bath, 164 km, 15 stages)
  7 — Hadrian's Wall Path   (Wallsend → Bowness-on-Solway, 135 km, 6 stages)
  8 — Pembrokeshire Coast Path (St Dogmaels → Amroth, 300 km, 15 stages)

ODP (route_id=3) already has its own scraper (scraper_odd.py).
Pennine Way (route_id=4) uses OSM (scraper_osm.py).

Usage:
    pip3 install requests beautifulsoup4 cloudscraper
    python3 scraper_nationaltrail.py              # all 4 trails
    python3 scraper_nationaltrail.py --only sdw   # one trail by short code
    python3 scraper_nationaltrail.py --only cw
    python3 scraper_nationaltrail.py --only hwp
    python3 scraper_nationaltrail.py --only pcp
    python3 scraper_nationaltrail.py --refresh         # re-fetch stages + elevation
    python3 scraper_nationaltrail.py --skip-elevation  # skip elevation (faster)
    python3 scraper.py --import

Elevation
---------
GPX files are downloaded from nationaltrails.s3.eu-west-2.amazonaws.com.
SDW, CW, PCP: elevation embedded in GPX → computed directly (no quota).
HWP: GPX has coordinates but no elevation → enriched via OpenTopoData SRTM30m
     (1000 req/day quota, ~1 req per stage; 6 calls for a full HWP run).

The GPX track is split into per-stage segments using accumulated haversine
distance. Stage distances guide the split; Hadrian's Wall (no per-section
distances) is split equally by total track distance.

Other notes
-----------
- Heading formats vary across trails (see parse_stages docstring).
- Hadrian's Wall headings have no distance — dist_km is null for that trail.
- duration_hrs: null (not published by the site).
- The site is behind Cloudflare — cloudscraper handles the JS challenge.
"""

import argparse
import math
import re
import sys
import time
import xml.etree.ElementTree as ET

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
        "start":    "Winchester",
        "end":      "Eastbourne",
        "total_km": 160,
        "expected": 9,
        "gpx_url":  "https://nationaltrails.s3.eu-west-2.amazonaws.com/uploads/South_Downs_Way_Elev.gpx",
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
        "start":    "Chipping Campden",
        "end":      "Bath",
        "total_km": 164,
        "expected": 15,
        "gpx_url":  "https://nationaltrails.s3.eu-west-2.amazonaws.com/uploads/Cotswold-Way-2019.gpx",
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
        "start":    "Wallsend",
        "end":      "Bowness-on-Solway",
        "total_km": 135,
        "expected": 6,
        "gpx_url":  "https://nationaltrails.s3.eu-west-2.amazonaws.com/uploads/Hadrians_Wall_Path-1.gpx",
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
        "start":    "St Dogmaels",
        "end":      "Amroth",
        "total_km": 300,
        "expected": 15,
        "gpx_url":  "https://nationaltrails.s3.eu-west-2.amazonaws.com/uploads/PCP-elev.gpx",
    },
]

BASE_URL   = "https://www.nationaltrail.co.uk/en_GB/trails/{slug}/route/"
LAND       = "uk"
ROUTE_TYPE = "national"
DELAY      = 1.5

OPENTOPODATA = "https://api.opentopodata.org/v1/srtm30m"
ELEV_DELAY   = 1.5
ELEV_MAX_PTS = 80
ELEV_NOISE_M = 2.0

# "Start to End – X miles (Y km)"  or  "Start – End – X miles (Y km)"
_HEADING_DIST_RE = re.compile(
    r"^(.+?)\s+(?:to|[–—])\s+(.+?)\s*[–—]\s*[\d.]+\s+miles?\s*\((\d+(?:\.\d+)?)\s*[Kk]m\)",
    re.IGNORECASE,
)
# "Start to End X miles (Y km)" — no dash before miles (Pembrokeshire)
_HEADING_DIST2_RE = re.compile(
    r"^(.+?)\s+to\s+(.+?)\s+\d+(?:\.\d+)?\s+miles?\s*\((\d+(?:\.\d+)?)\s*[Kk]m\)",
    re.IGNORECASE,
)
# Name-only fallback: "Place to Place" (Hadrian's Wall — no per-section distances)
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
            r = session.get(url, timeout=30)
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
# GPX helpers
# ---------------------------------------------------------------------------

def parse_gpx_points(xml_text):
    """
    Parse a GPX file and return list of (lat, lng, ele_or_None).
    Handles both <trkpt> (track) and <rtept> (route) formats.
    """
    root = ET.fromstring(xml_text)
    ns = "http://www.topografix.com/GPX/1/1"
    points = []
    for tag in ("trkpt", "rtept"):
        for pt in root.iter(f"{{{ns}}}{tag}"):
            lat = float(pt.get("lat"))
            lng = float(pt.get("lon"))
            ele_el = pt.find(f"{{{ns}}}ele")
            ele = float(ele_el.text) if ele_el is not None else None
            points.append((lat, lng, ele))
    return points


def haversine_km(lat1, lng1, lat2, lng2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlng / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def accumulate_distances(points):
    """Cumulative haversine distance (km) at each point."""
    cum = [0.0]
    for i in range(1, len(points)):
        cum.append(cum[-1] + haversine_km(
            points[i-1][0], points[i-1][1], points[i][0], points[i][1]))
    return cum


def split_by_stage_km(points, cum, stage_km_list):
    """
    Split track into one segment per stage.
    stage_km_list: per-stage distances in km; None entries are distributed equally
                   over the remaining total distance (used for Hadrian's Wall).
    Returns list of point-lists, one per stage.
    """
    total_km    = cum[-1]
    known_km    = sum(d for d in stage_km_list if d is not None)
    none_count  = sum(1 for d in stage_km_list if d is None)
    equal_share = (total_km - known_km) / none_count if none_count else 0.0
    resolved    = [d if d is not None else equal_share for d in stage_km_list]

    segments = []
    boundary = 0.0
    for dist_km in resolved:
        start_d = boundary
        end_d   = boundary + dist_km
        seg = [p for p, c in zip(points, cum) if start_d <= c <= end_d]
        if not seg:
            # Fallback: at least one point
            mid = (start_d + end_d) / 2
            idx = min(range(len(cum)), key=lambda i: abs(cum[i] - mid))
            seg = [points[idx]]
        segments.append(seg)
        boundary = end_d
    return segments


def elev_from_points(points, noise_m=ELEV_NOISE_M):
    """
    Compute cumulative ascent/descent (m) from points with embedded elevation.
    Returns (elev_up, elev_down) or (None, None) if no elevation data.
    """
    vals = [p[2] for p in points if p[2] is not None]
    if len(vals) < 2:
        return None, None
    up = dn = 0.0
    for i in range(1, len(vals)):
        diff = vals[i] - vals[i - 1]
        if diff > noise_m:
            up += diff
        elif diff < -noise_m:
            dn += abs(diff)
    return round(up), round(dn)


def elev_from_opentopodata(points, session):
    """
    Fetch elevation for a set of (lat, lng, *) points via OpenTopoData SRTM30m,
    sample to ELEV_MAX_PTS, and return (elev_up, elev_down).
    Returns (None, None) on quota exhaustion or error.
    """
    if not points:
        return None, None
    step    = max(1, -(-len(points) // ELEV_MAX_PTS))
    sampled = points[::step][:ELEV_MAX_PTS]
    if sampled[-1] != points[-1]:
        sampled.append(points[-1])

    locs = "|".join(f"{p[0]},{p[1]}" for p in sampled)
    time.sleep(ELEV_DELAY)
    try:
        r = session.get(OPENTOPODATA, params={"locations": locs}, timeout=30)
        data = r.json()
        if data.get("status") == "QUOTA_EXCEEDED":
            print("  [warn] OpenTopoData quota exceeded")
            return None, None
        elevations = [res.get("elevation") for res in data.get("results", [])]
        elevations = [e for e in elevations if e is not None]
        if len(elevations) < 2:
            return None, None

        up = dn = 0.0
        for i in range(1, len(elevations)):
            diff = elevations[i] - elevations[i - 1]
            if diff > ELEV_NOISE_M:
                up += diff
            elif diff < -ELEV_NOISE_M:
                dn += abs(diff)
        return round(up), round(dn)
    except Exception as e:
        print(f"  [warn] OpenTopoData error: {e}")
        return None, None


# ---------------------------------------------------------------------------
# Stage parser
# ---------------------------------------------------------------------------

def parse_stages(html):
    """
    Extract stage dicts from a single nationaltrail.co.uk route page.

    Three-pass strategy:
      Pass 1 — "Start to End – X miles (Y km)" in strong OR parent element text
               (handles SDW and CW where distance sits outside the <strong>).
      Pass 2 — "Start to End X miles (Y km)" — no dash before miles (PCP).
      Pass 3 — "Start to End" name-only (HWP — no per-section distances).

    Returns list of stage dicts (stage_nr not yet set, elev_* not yet set).
    """
    soup   = BeautifulSoup(html, "html.parser")
    stages = _parse_with_re(soup, _HEADING_DIST_RE,  has_dist=True)
    if not stages:
        stages = _parse_with_re(soup, _HEADING_DIST2_RE, has_dist=True)
    if not stages:
        stages = _parse_with_re(soup, _HEADING_NAME_RE,  has_dist=False)
    return stages


def _parse_with_re(soup, pattern, has_dist):
    stages = []
    for strong in soup.find_all(["strong", "b"]):
        strong_text = strong.get_text(" ", strip=True)
        parent_text = strong.parent.get_text(" ", strip=True) if strong.parent else ""
        m = pattern.match(strong_text) or pattern.match(parent_text)
        if not m:
            continue

        start_name = m.group(1).strip()
        end_name   = m.group(2).strip()
        dist_km    = round(float(m.group(3)), 1) if has_dist else None

        difficulty = None
        desc_paras = []
        el      = strong.parent
        sibling = el.find_next_sibling()
        while sibling:
            tag = sibling.name
            if tag in ("p", "div", "ul", "li"):
                t = sibling.get_text(" ", strip=True)
                if len(t) < 30:
                    sibling = sibling.find_next_sibling()
                    continue
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
# Elevation enrichment
# ---------------------------------------------------------------------------

def enrich_elevation(stages, trail, session, skip_elevation):
    """
    Download the trail GPX, split by stage distances, and fill in elev_up/elev_down.
    Modifies stages in-place. Returns True if successful, False if skipped/failed.
    """
    if skip_elevation:
        return False

    needs_elev = any(s["elev_up"] is None for s in stages)
    if not needs_elev:
        return True

    gpx_url = trail.get("gpx_url")
    if not gpx_url:
        return False

    print(f"  Fetching GPX…", end=" ", flush=True)
    time.sleep(DELAY)
    gpx_text = fetch(session, gpx_url, "GPX")
    if not gpx_text:
        print("failed")
        return False

    points = parse_gpx_points(gpx_text)
    if len(points) < 2:
        print(f"too few points ({len(points)})")
        return False

    print(f"{len(points)} points")

    cum        = accumulate_distances(points)
    stage_km   = [s["dist_km"] for s in stages]
    segments   = split_by_stage_km(points, cum, stage_km)

    has_embedded = points[0][2] is not None

    quota_hit = False
    for i, (stage, seg) in enumerate(zip(stages, segments), start=1):
        if stage["elev_up"] is not None:
            continue
        if has_embedded:
            up, dn = elev_from_points(seg)
        else:
            if quota_hit:
                break
            print(f"    [{i}/{len(stages)}] OpenTopoData for {stage['start_name']}…",
                  end=" ", flush=True)
            up, dn = elev_from_opentopodata(seg, session)
            if up is None:
                quota_hit = True
                print("failed/quota")
                break
            print(f"↑{up}m ↓{dn}m")
        stage["elev_up"]   = up
        stage["elev_down"] = dn

    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="Scrape UK National Trails from nationaltrail.co.uk")
    p.add_argument("--only",           metavar="SHORT",
                   help="Only scrape one trail (sdw, cw, hwp, pcp)")
    p.add_argument("--refresh",        action="store_true",
                   help="Re-fetch stages and elevation even if cached")
    p.add_argument("--skip-elevation", action="store_true",
                   help="Skip GPX download and elevation computation")
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
        key   = (LAND, ROUTE_TYPE, trail["route_id"])
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
        needs_elev = any(s.get("elev_up") is None for s in cached)

        if cached and not args.refresh and not needs_elev:
            print(f"{trail['name']}: {len(cached)} cached stages (elev ✓) — use --refresh to re-fetch")
            continue

        if cached and not args.refresh and needs_elev:
            print(f"\n{trail['name']} (elevation pass only)")
            enrich_elevation(cached, trail, session, args.skip_elevation)
            route["stages"] = cached
            save(list(existing.values()))
            continue

        # Full re-fetch
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

        enrich_elevation(stages, trail, session, args.skip_elevation)

        for s in stages:
            dist = f"{s['dist_km']} km" if s["dist_km"] else "no dist"
            elev = (f"↑{s['elev_up']}m ↓{s['elev_down']}m"
                    if s["elev_up"] is not None else "no elev")
            print(f"  [{s['stage_nr']:2d}/{len(stages)}] "
                  f"{s['start_name']} → {s['end_name']} ({dist}, {elev})")

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
