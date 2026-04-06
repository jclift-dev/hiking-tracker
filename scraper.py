#!/usr/bin/env python3
"""
Swiss Hiking & Cycling Tracker — Data Scraper
===============================================
Fetches hiking (land=hike) and cycling (land=cycle) routes + stages from
SchweizMobil, then enriches each stage with SBB travel time from a chosen
home station.

Output: hikes.json  (load this into the web app)

Usage:
    pip3 install requests
    python3 scraper.py                        # default: Basel SBB
    python3 scraper.py --origin "Zürich HB"  # add times from Zürich
    python3 scraper.py --origin "Bern"       # add times from Bern

Re-running is safe:
  - Routes already in hikes.json are skipped (matched by land+type+id)
  - SBB lookups for a given origin are skipped if already present in sbb_times

API:
    Route listing:  GET schweizmobil.ch/api/4/routes/{land}/{category}?lang=en
    Route overview: GET schweizmobil.ch/api/4/route_or_segment/{land}/{route_nr}/0?lang=en
    Segment detail: GET schweizmobil.ch/api/4/route_or_segment/{land}/{route_nr}/{seg_nr}?lang=en

    land:     hike | cycle
    category: national | regional | local
"""

import json
import os
import time
import sys
import argparse
from datetime import datetime

try:
    import requests
except ImportError:
    print("Missing dependency. Run:  pip3 install requests")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SM_BASE        = "https://schweizmobil.ch/api/4"
SBB_API        = "https://transport.opendata.ch/v1"
DEFAULT_ORIGIN = "Basel SBB"
ORIGIN         = DEFAULT_ORIGIN   # overridden by --origin in main()
OUTPUT         = "hikes.json"
DELAY          = 0.35   # seconds between SchweizMobil requests — be polite
SBB_DELAY      = 2.0    # transport.opendata.ch rate limits hard (~50 req/min)

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


def sm_get(url, label):
    """
    GET a SchweizMobil URL with one retry on transient failures (network error or 5xx).
    Returns the Response on success, None on 404, raises on unrecoverable errors.
    """
    for attempt in range(2):
        try:
            r = SESSION.get(url, timeout=15)
            if r.status_code == 404:
                return None
            if r.status_code >= 500 and attempt == 0:
                print(f"    [warn] SM API {r.status_code} for {label}, retrying in 5s...")
                time.sleep(5)
                continue
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            if attempt == 0:
                print(f"    [warn] transient error for {label}, retrying in 5s: {e}")
                time.sleep(5)
                continue
            raise
    return None


def fetch_route(route_nr, land):
    """
    Fetch route overview (segmentNumber=0) which includes all segment summaries.
    Returns parsed dict or None if route doesn't exist or has no useful data.
    """
    url = f"{SM_BASE}/route_or_segment/{land}/{route_nr}/0?lang=en"
    try:
        r = sm_get(url, f"{land} route {route_nr}")
        if r is None:
            return None
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
        r = sm_get(url, f"{land} route {route_nr} seg {segment_nr}")
        if r is None:
            return None
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


_arrival_cache = {}  # arrival_id → stationName (or None)


def fetch_arrival_station_names(arrival_ids):
    """Resolve SchweizMobil arrivalIds to canonical SBB station names."""
    names = []
    for aid in arrival_ids:
        if aid in _arrival_cache:
            if _arrival_cache[aid]:
                names.append(_arrival_cache[aid])
            continue
        try:
            r = SESSION.get(
                f"https://schweizmobil.ch/api/4/goodtoknow/arrivals/{aid}",
                params={"lang": "en"}, timeout=10,
            )
            data = r.json() if r.ok else []
            name = data[0].get("stationName") if data else None
            _arrival_cache[aid] = name
            if name:
                names.append(name)
            time.sleep(DELAY)
        except Exception as e:
            print(f"    [warn] arrival lookup failed for id {aid}: {e}")
            _arrival_cache[aid] = None
    return names


def enrich_arrival_stations(routes):
    """
    For each stage, resolve arrivalIds from the SchweizMobil API to get
    canonical SBB stop names. Stored as arrival_stations list on each stage.
    Skips stages that already have arrival_stations set.
    """
    all_stages = [(r, s) for r in routes for s in r["stages"]]
    total = len(all_stages)
    needs_work = sum(1 for _, s in all_stages if "arrival_stations" not in s)
    if not needs_work:
        return

    SAVE_EVERY = 25
    print(f"\n── Arrival stations ({needs_work} stages to enrich) ────────────")
    enriched = 0
    try:
        for i, (route, stage) in enumerate(all_stages, 1):
            if "arrival_stations" in stage:
                continue
            route_id = route["route_id"]
            land     = route["land"]
            stage_nr = stage["stage_nr"]
            single   = len(route["stages"]) == 1
            try:
                data = fetch_route(route_id, land) if single else fetch_segment(route_id, stage_nr, land)
                time.sleep(DELAY)
                arrival_ids = (data or {}).get("arrivalIds", [])
                names = fetch_arrival_station_names(arrival_ids)
                stage["arrival_stations"] = names
                label = ", ".join(names) if names else "(none)"
                print(f"  [{i}/{total}] Route {route_id} stage {stage_nr}: {label}")
            except Exception as e:
                print(f"  [warn] Route {route_id} stage {stage_nr}: {e}")
                stage["arrival_stations"] = []
            enriched += 1
            if enriched % SAVE_EVERY == 0:
                save(routes)
    except KeyboardInterrupt:
        print(f"\n  [interrupted] Saving progress ({enriched} stages enriched)...")
        save(routes)
        raise
    save(routes)


def best_arrival_station(name, candidates):
    """
    Pick the candidate station name that best matches a place name,
    using word overlap. Returns None if no candidate shares any word.
    """
    if not candidates:
        return None
    words = set(name.lower().replace("(", " ").replace(")", " ")
                             .replace(",", " ").replace("-", " ").split())
    words.discard("fl")  # Fürstentum Liechtenstein suffix, not useful
    for cand in candidates:
        cand_words = set(cand.lower().replace(",", " ").replace("-", " ").split())
        if words & cand_words:
            return cand
    return None


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
            "sbb_times":   {},
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
                "sbb_times":   {},
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

class SbbDailyLimitError(Exception):
    pass


def sbb_canonical_station(name):
    """
    Query the SBB locations API to find the canonical station name for a place.
    Returns the top result's name, or None if not found.
    """
    try:
        r = SESSION.get(f"{SBB_API}/locations", params={"query": name}, timeout=10)
        r.raise_for_status()
        body = r.json()
        if body.get("errors"):
            msg = (body["errors"][0].get("message") or "").lower()
            if "too many requests" in msg or "rate limit" in msg:
                raise SbbDailyLimitError(body["errors"][0]["message"])
            return None
        stations = body.get("stations", [])
        if stations and stations[0].get("name"):
            return stations[0]["name"]
    except SbbDailyLimitError:
        raise
    except Exception:
        pass
    return None


def sbb_travel_minutes(destination):
    """
    Get travel time in minutes from origin to destination.
    Returns int (minutes) or None on failure/bad match.
    Retries once after 30s on 429 rate-limit.
    Raises SbbDailyLimitError if the daily quota is exhausted.
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
            body = r.json()
            # Check for daily quota error returned as JSON body (not a 429)
            errors = body.get("errors", [])
            if errors:
                msg = (errors[0].get("message") or "").lower()
                if "too many requests" in msg or "rate limit" in msg:
                    raise SbbDailyLimitError(errors[0]["message"])
                print(f"    [warn] SBB API error for '{destination}': {errors[0].get('message')}")
                return None
            conns = body.get("connections", [])
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
                (matched_lower.startswith("binningen") and not dest_lower.startswith("binning"))
            )
            if bad_match:
                print(f"    [skip] '{destination}' → '{matched}' — wrong station, discarding")
                return None
            return int((arr - dep) / 60)
        except SbbDailyLimitError:
            raise
        except Exception as e:
            print(f"    [warn] SBB lookup failed for '{destination}': {e}")
            return None
    return None


def enrich_sbb(routes, origin):
    """
    For each stage look up SBB travel time from `origin` for start and end points.
    Skips stages already populated for this origin (safe to re-run).
    """
    all_stages = [(r, s) for r in routes for s in r["stages"]]
    total = len(all_stages)

    # Build reuse lookup: place name → minutes (for this origin run)
    lookup = {}
    for _, s in all_stages:
        times = s.get("sbb_times", {}).get(origin, {})
        if times.get("start") is not None:
            lookup[s.get("start_name", "")] = times["start"]
        if times.get("end") is not None:
            lookup[s.get("end_name", "")] = times["end"]

    SAVE_EVERY = 25
    stages_since_save = 0

    def stop_sbb(reason, i, routes):
        print(f"\n  [{reason}] Stopped at stage {i}/{total}. Saving progress and exiting.")
        save(routes)

    try:
      for i, (route, stage) in enumerate(all_stages, 1):
        times = stage.setdefault("sbb_times", {}).setdefault(origin, {})

        arrivals = stage.get("arrival_stations", [])

        def lookup_sbb(name):
            """Try name, then arrival-station match, then parenthesis-strip, then locations API."""
            mins = sbb_travel_minutes(name)
            if mins is not None:
                return mins
            time.sleep(SBB_DELAY)
            # Try the best-matching canonical arrival station
            canon = best_arrival_station(name, arrivals)
            if canon and canon.lower() != name.lower():
                mins = sbb_travel_minutes(canon)
                if mins is not None:
                    return mins
                time.sleep(SBB_DELAY)
            # Strip parenthesised suffix
            if "(" in name:
                stripped = name[:name.index("(")].strip()
                mins = sbb_travel_minutes(stripped)
                if mins is not None:
                    return mins
                time.sleep(SBB_DELAY)
            # Last resort: SBB locations API
            loc = sbb_canonical_station(name)
            time.sleep(SBB_DELAY)
            if loc and loc.lower() != name.lower():
                mins = sbb_travel_minutes(loc)
                if mins is not None:
                    return mins
                time.sleep(SBB_DELAY)
            return None

        # --- Start point ---
        if times.get("start") is None:
            dest = stage.get("start_name", "")
            print(f"  [{i}/{total}] {origin} → {dest or '?'} (start)...", end=" ", flush=True)
            try:
                mins = lookup_sbb(dest)
            except SbbDailyLimitError as e:
                print(f"\n\n  [DAILY LIMIT] {e}")
                stop_sbb("DAILY LIMIT", i, routes)
                return
            times["start"] = mins
            if mins is not None:
                lookup[dest] = mins
            print(f"{mins} min" if mins is not None else "not found")
        else:
            print(f"  [{i}/{total}] {stage['start_name']} start — cached ({times['start']} min)")

        # --- End point ---
        if times.get("end") is None:
            end = stage.get("end_name", "")
            if end in lookup:
                times["end"] = lookup[end]
                print(f"  [{i}/{total}] {end} end — reused ({times['end']} min)")
            else:
                print(f"  [{i}/{total}] {origin} → {end or '?'} (end)...", end=" ", flush=True)
                try:
                    mins = lookup_sbb(end)
                except SbbDailyLimitError as e:
                    print(f"\n\n  [DAILY LIMIT] {e}")
                    stop_sbb("DAILY LIMIT", i, routes)
                    return
                times["end"] = mins
                if mins is not None:
                    lookup[end] = mins
                print(f"{mins} min" if mins is not None else "not found")
        else:
            print(f"  [{i}/{total}] {stage['end_name']} end — cached ({times['end']} min)")

        stages_since_save += 1
        if stages_since_save >= SAVE_EVERY:
            save(routes)
            stages_since_save = 0

    except KeyboardInterrupt:
        print(f"\n  [interrupted] Saving progress...")
        save(routes)
        raise

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
    except (json.JSONDecodeError, ValueError) as e:
        import shutil
        bak = OUTPUT + ".bak"
        shutil.copy(OUTPUT, bak)
        print(f"  [warn] {OUTPUT} is corrupted ({e}). Backed up to {bak}, starting fresh.\n")
        return {}

# ---------------------------------------------------------------------------
# Supabase import
# ---------------------------------------------------------------------------

def import_to_supabase(routes):
    """Import all routes and stages from hikes.json into Supabase via REST API."""
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not url:
        print("Error: SUPABASE_URL environment variable is not set.")
        sys.exit(1)
    if not key:
        print("Error: SUPABASE_SERVICE_KEY environment variable is not set.")
        sys.exit(1)

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }

    BATCH = 100

    # --- Routes ---
    route_rows = [
        {
            "id":          r["route_id"],
            "land":        r["land"],
            "route_type":  r["route_type"],
            "name":        r["name"],
            "description": r.get("description", ""),
            "start_name":  r.get("start", ""),
            "end_name":    r.get("end", ""),
            "total_km":    r.get("total_km"),
        }
        for r in routes
    ]
    print(f"Uploading {len(route_rows)} routes in batches of {BATCH}...")
    for i in range(0, len(route_rows), BATCH):
        batch = route_rows[i:i + BATCH]
        resp = SESSION.post(
            f"{url}/rest/v1/routes",
            headers=headers, json=batch, timeout=30,
            params={"on_conflict": "id,land"},
        )
        if not resp.ok:
            print(f"  [error] routes batch {i//BATCH + 1}: {resp.status_code} {resp.text[:200]}")
        else:
            print(f"  Uploaded routes {i+1}–{min(i+BATCH, len(route_rows))}")

    # --- Stages ---
    stage_rows = [
        {
            "route_id":        r["route_id"],
            "land":            r["land"],
            "stage_nr":        s["stage_nr"],
            "start_name":      s.get("start_name", ""),
            "end_name":        s.get("end_name", ""),
            "via":             s.get("via"),
            "dist_km":         s.get("dist_km"),
            "elev_up":         s.get("elev_up"),
            "elev_down":       s.get("elev_down"),
            "duration_hrs":    s.get("duration_hrs") or s.get("hiking_hrs"),
            "km_asphalt":      s.get("km_asphalt"),
            "difficulty":      s.get("difficulty"),
            "description":     s.get("description", ""),
            "cantons":         s.get("cantons", []),
            "arrival_stations":s.get("arrival_stations", []),
            "sbb_times":       s.get("sbb_times", {}),
        }
        for r in routes for s in r["stages"]
    ]
    print(f"Uploading {len(stage_rows)} stages in batches of {BATCH}...")
    for i in range(0, len(stage_rows), BATCH):
        batch = stage_rows[i:i + BATCH]
        resp = SESSION.post(
            f"{url}/rest/v1/stages",
            headers=headers, json=batch, timeout=30,
            params={"on_conflict": "route_id,land,stage_nr"},
        )
        if not resp.ok:
            print(f"  [error] stages batch {i//BATCH + 1}: {resp.status_code} {resp.text[:200]}")
        else:
            print(f"  Uploaded stages {i+1}–{min(i+BATCH, len(stage_rows))}")

    print("\n" + "=" * 60)
    print(f"Import complete: {len(route_rows)} routes, {len(stage_rows)} stages")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global ORIGIN
    parser = argparse.ArgumentParser(
        description="Swiss Hiking & Cycling Tracker — Data Scraper"
    )
    parser.add_argument(
        "--origin", default=DEFAULT_ORIGIN,
        help=f"SBB departure station (default: {DEFAULT_ORIGIN!r})"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--routes-only", action="store_true",
        help="Scrape route/stage data only — skip SBB enrichment"
    )
    mode.add_argument(
        "--sbb-only", action="store_true",
        help="Run SBB enrichment only — skip route scraping"
    )
    mode.add_argument(
        '--import', dest='import_mode', action='store_true',
        help='Import hikes.json into Supabase (requires SUPABASE_URL and SUPABASE_SERVICE_KEY env vars)'
    )
    args = parser.parse_args()
    ORIGIN = args.origin

    if args.import_mode:
        routes = list(load_existing().values())
        print(f"Importing {len(routes)} routes to Supabase...")
        import_to_supabase(routes)
        return

    print("=" * 60)
    print("Swiss Hiking & Cycling Tracker — Data Scraper")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Origin:  {ORIGIN}")
    print("=" * 60)

    existing = load_existing()
    routes = []

    # --- Route scraping ---
    if not args.sbb_only:
        try:
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
        except KeyboardInterrupt:
            print(f"\n  [interrupted] Saving {len(routes)} routes and exiting.")
            save(routes)
            sys.exit(0)

        # --- Arrival station enrichment ---
        try:
            enrich_arrival_stations(routes)
        except KeyboardInterrupt:
            sys.exit(0)

        if args.routes_only:
            print(f"\nRoutes-only run complete — skipping SBB enrichment.")
            save(routes)
            return
    else:
        # sbb-only: load all existing routes into the working list
        routes = list(existing.values())
        print(f"SBB-only mode — {len(routes)} routes loaded, skipping route scraping.")

    # --- SBB enrichment ---
    print(f"\n── SBB travel times from {ORIGIN} ─────────────────")
    try:
        enrich_sbb(routes, ORIGIN)
    except KeyboardInterrupt:
        sys.exit(0)
    save(routes)

    # --- Summary ---
    total_stages = sum(len(r["stages"]) for r in routes)
    sbb_found = sum(
        1 for r in routes for s in r["stages"]
        if any(v.get("start") is not None or v.get("end") is not None
               for v in s.get("sbb_times", {}).values())
    )
    by_land = {}
    for r in routes:
        key = r.get("land", "unknown")
        by_land[key] = by_land.get(key, 0) + 1
    print("\n" + "=" * 60)
    print(f"Done!  {len(routes)} routes · {total_stages} stages")
    for land, count in by_land.items():
        print(f"  {land}: {count} routes")
    print(f"SBB times found: {sbb_found}/{total_stages}")
    print(f"Output: {OUTPUT}")
    print("=" * 60)


if __name__ == "__main__":
    main()
