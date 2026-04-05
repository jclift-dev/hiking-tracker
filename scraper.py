#!/usr/bin/env python3
"""
Swiss Hiking & Cycling Tracker — Data Scraper
===============================================
Fetches hiking (land=hike) and cycling (land=cycle) routes + stages from
SchweizMobil, then enriches each stage with SBB travel time from Basel SBB.

Output: hikes.json  (load this into the web app)

Usage:
    pip3 install requests
    python3 scraper.py

The script is polite: it sleeps briefly between requests.
Re-running is safe — it skips routes and SBB lookups already cached in hikes.json.

API:
    Route listing:  GET schweizmobil.ch/api/4/routes/{land}/{category}?lang=en
    Route overview: GET schweizmobil.ch/api/4/route_or_segment/{land}/{route_nr}/0?lang=en
    Segment detail: GET schweizmobil.ch/api/4/route_or_segment/{land}/{route_nr}/{seg_nr}?lang=en

    land:     hike | cycle
    category: national | regional | local
"""

import json
import time
import sys
from datetime import datetime

try:
    import requests
except ImportError:
    print("Missing dependency. Run:  pip3 install requests")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SM_BASE   = "https://schweizmobil.ch/api/4"
SBB_API   = "https://transport.opendata.ch/v1"
ORIGIN    = "Basel SBB"
OUTPUT    = "hikes.json"
DELAY     = 0.35   # seconds between SchweizMobil requests — be polite
SBB_DELAY = 2.0    # transport.opendata.ch rate limits hard (~50 req/min)

LANDS      = ["hike", "cycle"]
CATEGORIES = ["national", "regional", "local"]

# SchweizMobil canton ID → abbreviation (discovered empirically via stage geography)
CANTON_MAP = {
    1:  "FL",  # Liechtenstein (foreign territory, appears on Via Alpina stage 1)
    2:  "GR",  # Graubünden
    3:  "ZH",  # Zürich
    4:  "UR",  # Uri
    5:  "FR",  # Fribourg
    6:  "TG",  # Thurgau
    7:  "VS",  # Valais
    8:  "BS",  # Basel-Stadt
    9:  "BL",  # Basel-Landschaft
    10: "NW",  # Nidwalden
    11: "SZ",  # Schwyz
    12: "BE",  # Bern
    13: "AG",  # Aargau
    14: "GL",  # Glarus
    15: "LU",  # Luzern
    16: "SO",  # Solothurn
    17: "AI",  # Appenzell Innerrhoden
    18: "OW",  # Obwalden
    19: "TI",  # Ticino
    20: "SH",  # Schaffhausen
    21: "ZG",  # Zug
    22: "GE",  # Geneva
    23: "SG",  # St. Gallen
    24: "JU",  # Jura
    25: "NE",  # Neuchâtel
    26: "AR",  # Appenzell Ausserrhoden
    27: "VD",  # Vaud
    28: "FL",  # Liechtenstein (secondary code, treat same as 1)
}

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "SwissHikingTracker/1.0 (personal use)",
    "Accept": "application/json",
    "Accept-Language": "en",
    "Referer": "https://www.schweizmobil.ch/",
})

# ---------------------------------------------------------------------------
# SchweizMobil API
# ---------------------------------------------------------------------------

def fetch_route_ids(land, category):
    """
    Fetch all route numbers for a given land + category from the listing API.
    Returns a sorted list of ints, or [] on failure.
    """
    url = f"{SM_BASE}/routes/{land}/{category}?lang=en"
    try:
        r = SESSION.get(url, timeout=15)
        r.raise_for_status()
        ids = sorted(item["routeNumber"] for item in r.json() if "routeNumber" in item)
        print(f"  Found {len(ids)} {category} {land} routes.")
        return ids
    except Exception as e:
        print(f"  [warn] Could not fetch {land}/{category} route list: {e}")
        return []


def fetch_route(route_nr, land):
    """
    Fetch route overview (segmentNumber=0) which includes all segment summaries.
    Returns parsed dict or None if route doesn't exist or has no useful data.
    """
    url = f"{SM_BASE}/route_or_segment/{land}/{route_nr}/0?lang=en"
    try:
        r = SESSION.get(url, timeout=15)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        data = r.json()
        # Must have at least a start/end to be useful
        if not data.get("start") and not data.get("length"):
            return None
        return data
    except Exception as e:
        print(f"    [warn] SM API failed for {land} route {route_nr}: {e}")
        return None


def fetch_segment(route_nr, segment_nr, land):
    """
    Fetch a single segment for its detail (hikingTime, gradeText, cantons, etc.).
    Returns parsed dict or None on failure.
    """
    url = f"{SM_BASE}/route_or_segment/{land}/{route_nr}/{segment_nr}?lang=en"
    try:
        r = SESSION.get(url, timeout=15)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"    [warn] SM API failed for {land} route {route_nr} seg {segment_nr}: {e}")
        return None


def map_cantons(raw_cantons):
    """Map canton IDs to abbreviations, deduplicating and preserving order."""
    seen, result = set(), []
    for cid in (raw_cantons or []):
        abbr = CANTON_MAP.get(cid)
        if abbr and abbr not in seen:
            result.append(abbr)
            seen.add(abbr)
    return result


def extract_stage_detail(detail, land):
    """Pull time, difficulty, description, cantons, surface from a detail dict."""
    if not detail:
        return None, None, "", [], None
    if land == "hike":
        ht = detail.get("hikingTime")
        duration_hrs = round(ht, 2) if ht is not None else None
        difficulty = detail.get("gradeText") or detail.get("fitness")
    else:  # cycle
        duration_hrs = None   # cycling routes don't expose riding time
        difficulty = detail.get("fitness")
    description = detail.get("abstract") or ""
    cantons = map_cantons(detail.get("cantons"))
    km_asphalt = detail.get("lengthAsphalt")  # cycling only, None for hike
    return duration_hrs, difficulty, description, cantons, km_asphalt


def build_route(route_nr, land):
    """
    Build a complete route dict with stages for one route/land combination.
    Returns None if the route doesn't exist or is not useful.
    """
    overview = fetch_route(route_nr, land)
    time.sleep(DELAY)
    if not overview:
        return None

    category = overview.get("category", "")
    if category not in CATEGORIES:
        return None

    print(f"    [{land}/{category}] {overview.get('title', f'Route {route_nr}')} "
          f"— {overview.get('stages', 0)} stage(s)")

    stages = []
    segs = overview.get("segments", [])

    if not segs:
        # Single-stage route: overview IS the stage
        duration_hrs, difficulty, description, cantons, km_asphalt = \
            extract_stage_detail(overview, land)
        stages.append({
            "stage_nr":    1,
            "start_name":  overview.get("start", ""),
            "end_name":    overview.get("end", ""),
            "via":         overview.get("via"),
            "dist_km":     overview.get("length"),
            "elev_up":     overview.get("ascent"),
            "elev_down":   overview.get("descent"),
            "duration_hrs": duration_hrs,
            "km_asphalt":  km_asphalt,
            "difficulty":  difficulty,
            "description": description,
            "cantons":     cantons,
            "sbb_station": None,
            "sbb_mins":    None,
            "sbb_mins_end": None,
        })
    else:
        for seg in segs:
            seg_nr = seg["segmentNumber"]
            detail = fetch_segment(route_nr, seg_nr, land)
            time.sleep(DELAY)
            duration_hrs, difficulty, description, cantons, km_asphalt = \
                extract_stage_detail(detail, land)
            stages.append({
                "stage_nr":    seg_nr,
                "start_name":  seg.get("start", ""),
                "end_name":    seg.get("end", ""),
                "via":         seg.get("via"),
                "dist_km":     seg.get("length"),
                "elev_up":     seg.get("ascent"),
                "elev_down":   seg.get("descent"),
                "duration_hrs": duration_hrs,
                "km_asphalt":  km_asphalt,
                "difficulty":  difficulty,
                "description": description,
                "cantons":     cantons,
                "sbb_station": None,
                "sbb_mins":    None,
                "sbb_mins_end": None,
            })

    stages.sort(key=lambda s: s["stage_nr"])

    return {
        "route_id":    route_nr,
        "land":        land,
        "route_type":  category,
        "name":        overview.get("title", f"Route {route_nr}"),
        "description": overview.get("description", ""),
        "start":       overview.get("start", ""),
        "end":         overview.get("end", ""),
        "total_km":    overview.get("length"),
        "stages":      stages,
    }

# ---------------------------------------------------------------------------
# SBB travel time lookup
# ---------------------------------------------------------------------------

def sbb_travel_minutes(destination):
    """
    Get travel time in minutes from Basel SBB to destination.
    Returns int (minutes) or None on failure/bad match.
    Retries once after 30s on 429 rate-limit.
    """
    if not destination:
        return None
    for attempt in range(2):
        try:
            r = SESSION.get(
                f"{SBB_API}/connections",
                params={"from": ORIGIN, "to": destination, "limit": 1},
                timeout=15,
            )
            if r.status_code == 429:
                if attempt == 0:
                    print(f"\n    [rate-limited] waiting 30s...", end=" ", flush=True)
                    time.sleep(30)
                    continue
                return None
            r.raise_for_status()
            conns = r.json().get("connections", [])
            if not conns:
                return None
            c = conns[0]
            dep = c["from"]["departureTimestamp"]
            arr = c["to"]["arrivalTimestamp"]
            if not (dep and arr):
                return None
            # Reject if matched to a Basel-area stop for a non-Basel destination
            matched = (c["to"]["station"] or {}).get("name", "")
            dest_lower = destination.lower()
            matched_lower = matched.lower()
            dest_mentions_basel = "basel" in dest_lower
            bad_match = (
                (matched_lower.startswith("basel") and not dest_mentions_basel) or
                (matched_lower.startswith("binningen") and not dest_lower.startswith("binn"))
            )
            if bad_match:
                print(f"    [skip] '{destination}' → '{matched}' — wrong station, discarding")
                return None
            return int((arr - dep) / 60)
        except Exception as e:
            print(f"    [warn] SBB lookup failed for '{destination}': {e}")
            return None
    return None


def enrich_sbb(routes):
    """
    For each stage look up SBB travel time for start and end points.
    Skips stages with sbb_mins already populated (safe to re-run).
    """
    all_stages = [(r, s) for r in routes for s in r["stages"]]
    total = len(all_stages)

    # Build lookup from previously resolved start names → minutes
    start_lookup = {}
    for _, s in all_stages:
        if s.get("sbb_mins") is not None and s.get("sbb_station"):
            start_lookup[s["sbb_station"]] = s["sbb_mins"]
            start_lookup[s["start_name"]] = s["sbb_mins"]

    for i, (route, stage) in enumerate(all_stages, 1):
        # --- Start point ---
        if stage.get("sbb_mins") is None:
            dest = stage.get("start_name", "")
            print(f"  [{i}/{total}] Basel → {dest or '?'} (start)...", end=" ", flush=True)
            mins = sbb_travel_minutes(dest)
            time.sleep(SBB_DELAY)
            if mins is None and "(" in dest:
                stripped = dest[:dest.index("(")].strip()
                mins = sbb_travel_minutes(stripped)
                time.sleep(SBB_DELAY)
                if mins is not None:
                    dest = stripped
            stage["sbb_station"] = dest if mins is not None else None
            stage["sbb_mins"] = mins
            if mins is not None:
                start_lookup[dest] = mins
                start_lookup[stage["start_name"]] = mins
            print(f"{mins} min" if mins is not None else "not found")
        else:
            print(f"  [{i}/{total}] {stage['start_name']} start — cached ({stage['sbb_mins']} min)")

        # --- End point ---
        if stage.get("sbb_mins_end") is None:
            end = stage.get("end_name", "")
            # Try to reuse a previously resolved time for the same place name
            if end in start_lookup:
                stage["sbb_mins_end"] = start_lookup[end]
                print(f"  [{i}/{total}] {end} end — reused ({stage['sbb_mins_end']} min)")
            else:
                print(f"  [{i}/{total}] Basel → {end or '?'} (end)...", end=" ", flush=True)
                mins = sbb_travel_minutes(end)
                time.sleep(SBB_DELAY)
                if mins is None and "(" in end:
                    stripped = end[:end.index("(")].strip()
                    mins = sbb_travel_minutes(stripped)
                    time.sleep(SBB_DELAY)
                stage["sbb_mins_end"] = mins
                if mins is not None:
                    start_lookup[end] = mins
                print(f"{mins} min" if mins is not None else "not found")
        else:
            print(f"  [{i}/{total}] {stage['end_name']} end — cached ({stage['sbb_mins_end']} min)")

# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save(routes):
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(routes, f, ensure_ascii=False, indent=2)
    print(f"  → Saved {len(routes)} routes to {OUTPUT}")


def load_existing():
    try:
        with open(OUTPUT) as f:
            old = json.load(f)
        existing = {}
        for r in old:
            if not r.get("stages"):
                continue  # skip stale/empty
            land = r.get("land", "hike")  # default hike for pre-cycling data
            existing[(land, r["route_type"], r["route_id"])] = r
        stale = len(old) - len(existing)
        print(f"Loaded {len(existing)} routes from {OUTPUT}"
              + (f" ({stale} stale/empty skipped)" if stale else "") + "\n")
        return existing
    except FileNotFoundError:
        print(f"No existing {OUTPUT} — starting fresh\n")
        return {}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Swiss Hiking & Cycling Tracker — Data Scraper")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    existing = load_existing()
    routes = []

    for land in LANDS:
        label = "Hiking" if land == "hike" else "Cycling"
        print(f"\n{'='*60}")
        print(f"── {label} routes ──")

        for category in CATEGORIES:
            print(f"\n  ── {category} ──")
            ids = fetch_route_ids(land, category)
            for rid in ids:
                key = (land, category, rid)
                if key in existing:
                    print(f"    Route {rid} already cached, skipping.")
                    routes.append(existing[key])
                    continue
                route = build_route(rid, land)
                if route:
                    routes.append(route)
                    save(routes)
                time.sleep(DELAY)

    # --- SBB enrichment ---
    print(f"\n── SBB travel times from {ORIGIN} ─────────────────")
    enrich_sbb(routes)
    save(routes)

    # --- Summary ---
    total_stages = sum(len(r["stages"]) for r in routes)
    sbb_found = sum(1 for r in routes for s in r["stages"] if s.get("sbb_mins") is not None)
    by_land = {}
    for r in routes:
        by_land[r["land"]] = by_land.get(r["land"], 0) + 1
    print("\n" + "=" * 60)
    print(f"Done!  {len(routes)} routes · {total_stages} stages")
    for land, count in by_land.items():
        print(f"  {land}: {count} routes")
    print(f"SBB times found: {sbb_found}/{total_stages}")
    print(f"Output: {OUTPUT}")
    print("=" * 60)


if __name__ == "__main__":
    main()
