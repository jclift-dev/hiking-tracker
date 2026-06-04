#!/usr/bin/env python3
"""
OSM Long-Distance Trails Scraper (via Waymarked Trails API)
===========================================================
Fetches long-distance hiking trails from OpenStreetMap via the Waymarked
Trails API (hiking.waymarkedtrails.org) and merges them into hikes.json.

Usage:
    pip3 install requests
    python3 scraper_osm.py                      # full run (may take multiple days: ~1 elevation call/stage)
    python3 scraper_osm.py --limit 2            # smoke test: first 2 trails only
    python3 scraper_osm.py --only 4080347       # one trail by OSM relation ID
    python3 scraper_osm.py --refresh-trail 4080347  # re-fetch a specific trail (repeatable)
    python3 scraper_osm.py --skip-elevation     # skip OpenTopoData calls (faster)

Push to Supabase (after adding es-hike to the land CHECK constraint):
    python3 scraper.py --import

Licensing
---------
Trail data is from OpenStreetMap, © OpenStreetMap contributors, ODbL 1.0.
https://www.openstreetmap.org/copyright
For a produced-work hiking app, only attribution is required (no share-alike).
Attribution is present in index.html footer.

API notes (discovered by probing)
----------------------------------
Base:    https://hiking.waymarkedtrails.org/api/v1/
Search:  GET /list/search?query=<name>&limit=N
Detail:  GET /details/relation/<osm_id>

Detail response fields used here:
  .name                  display name (e.g. "Pennine Way (Edale to Crowden)")
  .tags.from / .tags.to  start/end place names
  .tags.sac_scale        SAC difficulty (T1-T6, Alpine only)
  .official_length       official length in metres (may be None)
  .route.length          actual routed length in metres (most reliable)
  .route.main[]          direct child routes (subroutes = day stages)
    .id                  OSM relation ID of the child stage
    .route_type          "route" (named sub-route) | "linear" (way sequence)
    .length              metres (from parent; same as child .route.length)
  way.geometry           EPSG:3857 LineString coordinates [[x,y], ...]

Coordinate system: EPSG:3857 Web Mercator (metres). Convert to WGS84 before
elevation calls using merc_to_wgs84().

Rate limits
-----------
Waymarked Trails: be polite; 1.5-2 s between requests.
OpenTopoData SRTM30m: 1000 req/day quota (1 req/stage). With ~170 stages
across this catalog, a full run fits in one day. The quota resets at midnight
UTC. The scraper detects quota exhaustion and saves progress.
"""

import argparse
import json
import math
import re
import sys
import time

import requests

try:
    from scraper import save, load_existing
except ImportError:
    print("scraper.py not found. Run from the project root.")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Trail catalog
# ---------------------------------------------------------------------------
# (osm_relation_id, land, route_id, route_type, display_name)
#
# route_id rules — don't collide with existing entries in hikes.json:
#   uk:      4+  (1=SWCP, 2=WHW, 3=ODP already from authoritative scrapers)
#   fr-hike: 4+  (1=GR20, 2=GR65, 3=GR70 already scraped)
#   de-hike: 2+  (1=Malerweg already scraped)
#   es-hike: 1+  (new land value — add to Supabase CHECK before --import)

TRAILS = [
    # UK — day-stage subroutes available
    (4080347,  "uk",      4, "national", "Pennine Way"),
    # UK — flat in OSM; imported as single stage
    (77976,    "uk",      5, "national", "South Downs Way"),
    (65239,    "uk",      6, "national", "Cotswold Way"),
    (38791,    "uk",      7, "national", "Hadrian's Wall Path"),
    (77964,    "uk",      8, "national", "Pembrokeshire Coast Path"),
    (9327615,  "uk",      9, "national", "Cape Wrath Trail"),

    # France
    (8386002,  "fr-hike", 4, "national", "Haute Randonnée Pyrénéenne"),

    # Germany
    (62900,    "de-hike", 2, "national", "Westweg"),
    (61185,    "de-hike", 3, "national", "Goldsteig-Südroute"),
    (3300718,  "de-hike", 4, "national", "Goldsteig-Nordroute"),
    (19995501, "de-hike", 5, "national", "Heidschnuckenweg"),

    # Spain
    (8865914,  "es-hike", 1, "national", "Senda Pirenaica (GR11)"),
    (19298101, "es-hike", 2, "national", "Camino Primitivo"),
    (16358020, "es-hike", 3, "national", "GR 221 Ruta de Pedra en Sec"),

    # Ireland (ie-hike — new land; update Supabase CHECK constraint before --import)
    (2740,     "ie-hike", 1, "national", "Wicklow Way"),
    (183744,   "ie-hike", 2, "national", "The Kerry Way"),
    (21664,    "ie-hike", 3, "national", "The Dingle Way"),
    (1085994,  "ie-hike", 4, "national", "Causeway Coast Way"),
    (2989585,  "ie-hike", 5, "national", "Beara Way"),
    (14702338, "ie-hike", 6, "national", "Western Way"),
]

# Deferred — level-2 descent still too coarse, no viable day stages:
#   GR34 Chemin des Douaniers    (7790332)   — 2 sections × ~1000 km
#   GR5  Grande Traversée Alpes  (18308154)  — 1 section × 293 km
#   Camino del Norte             (19001007)  — 1 section × 69 km (level-2 shows no stages)
#   GR10 Pyrenean Traverse       (France)    — no clean parent relation identified
#   Camino Francés               (2163573)   — flat, 1 child × 163 km
#   Alta Via 2                   (404914)    — 0 subroutes (flat)
#   GR54 Tour de l'Oisans        (2909096)   — flat

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

API_BASE       = "https://hiking.waymarkedtrails.org/api/v1/details/relation"
API_DELAY      = 1.8   # seconds between Waymarked Trails requests
USER_AGENT     = "HikingTracker/1.0 (https://github.com/jclift-dev/hiking-tracker)"
STAGE_MAX_KM   = 40    # route children longer than this trigger level-2 descent

OPENTOPODATA   = "https://api.opentopodata.org/v1/srtm30m"
ELEV_DELAY     = 1.5   # OpenTopoData rate limit: ≤1 req/sec; 1.5 s is safe
ELEV_MAX_PTS   = 80    # sample up to this many points (API cap: 100)
ELEV_NOISE_M   = 2     # ignore elevation changes < this (GPS noise threshold)

SAC_SCALE_MAP = {
    "hiking":                    "hiking trail",
    "mountain_hiking":           "mountain hiking trail",
    "demanding_mountain_hiking": "demanding mountain hiking trail",
    "alpine_hiking":             "alpine hiking trail",
    "demanding_alpine_hiking":   "alpine hiking trail",
    "difficult_alpine_hiking":   "alpine hiking trail",
}

SESSION = requests.Session()
SESSION.headers["User-Agent"] = USER_AGENT

ELEV_SESSION = requests.Session()
ELEV_SESSION.headers["User-Agent"] = USER_AGENT


# ---------------------------------------------------------------------------
# Coordinate helpers
# ---------------------------------------------------------------------------

def merc_to_wgs84(x, y):
    """Convert EPSG:3857 Web Mercator (metres) → (lat_deg, lng_deg)."""
    lng = x / 20037508.34 * 180.0
    lat = math.degrees(
        2 * math.atan(math.exp(math.radians(y / 20037508.34 * 180.0))) - math.pi / 2
    )
    return lat, lng


def extract_coords_merc(route_node):
    """Recursively collect EPSG:3857 [x, y] pairs from a route node's geometry."""
    coords = []
    for child in route_node.get("main", []):
        if "ways" in child:
            for way in child["ways"]:
                geom = way.get("geometry", {})
                if geom.get("type") == "LineString":
                    coords.extend(geom["coordinates"])
        else:
            coords.extend(extract_coords_merc(child))
    return coords


def sample_wgs84(route_node, max_pts=ELEV_MAX_PTS):
    """
    Extract route geometry and return a list of (lat, lng) WGS84 pairs,
    sampled to at most max_pts points (preserving last point).
    """
    merc = extract_coords_merc(route_node)
    if len(merc) < 2:
        return []
    step = max(1, -(-len(merc) // max_pts))   # ceiling division
    sampled = merc[::step][:max_pts]
    if sampled[-1] != merc[-1]:
        sampled.append(merc[-1])
    return [merc_to_wgs84(p[0], p[1]) for p in sampled]


# ---------------------------------------------------------------------------
# Elevation
# ---------------------------------------------------------------------------

def fetch_elevation(wgs84_pts):
    """
    Query OpenTopoData SRTM30m for elevation at the given (lat, lng) points.
    Returns (elev_up_m, elev_down_m) as ints, or (None, None) on failure.

    Raises SystemExit if the daily quota is exhausted.
    """
    if len(wgs84_pts) < 2:
        return None, None

    time.sleep(ELEV_DELAY)
    loc_str = "|".join(f"{lat:.6f},{lng:.6f}" for lat, lng in wgs84_pts)
    try:
        resp = ELEV_SESSION.get(f"{OPENTOPODATA}?locations={loc_str}", timeout=30)
    except Exception as e:
        print(f"   [warn] OpenTopoData request failed: {e}")
        return None, None

    if resp.status_code == 429:
        print("   [warn] OpenTopoData rate-limited; waiting 60 s then retrying once")
        time.sleep(60)
        try:
            resp = ELEV_SESSION.get(f"{OPENTOPODATA}?locations={loc_str}", timeout=30)
        except Exception as e:
            print(f"   [warn] retry failed: {e}")
            return None, None

    if resp.status_code == 403 or resp.status_code == 429:
        print("   [error] OpenTopoData daily quota exhausted — saving and stopping.")
        return "QUOTA_EXHAUSTED", None

    try:
        body = resp.json()
    except Exception:
        print(f"   [warn] OpenTopoData non-JSON response ({resp.status_code})")
        return None, None

    if body.get("status") == "QUOTA_EXCEEDED":
        print("   [error] OpenTopoData daily quota exhausted — saving and stopping.")
        return "QUOTA_EXHAUSTED", None

    elevations = [
        pt["elevation"]
        for pt in body.get("results", [])
        if pt.get("elevation") is not None
    ]
    if len(elevations) < 2:
        return None, None

    asc = desc = 0.0
    for i in range(1, len(elevations)):
        diff = elevations[i] - elevations[i - 1]
        if diff > ELEV_NOISE_M:
            asc += diff
        elif diff < -ELEV_NOISE_M:
            desc += abs(diff)

    return round(asc), round(desc)


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def fetch_relation(osm_id, label=""):
    """GET /details/relation/<id> with retry. Returns parsed JSON or None."""
    url = f"{API_BASE}/{osm_id}"
    for attempt in range(2):
        try:
            time.sleep(API_DELAY)
            r = SESSION.get(url, timeout=20)
            if r.status_code == 404:
                print(f"   [warn] 404 for relation {osm_id}{' (' + label + ')' if label else ''}")
                return None
            if r.status_code >= 500 and attempt == 0:
                print(f"   [warn] {r.status_code} for {osm_id}, retrying in 10 s")
                time.sleep(10)
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == 0:
                print(f"   [warn] error fetching {osm_id}: {e}, retrying in 10 s")
                time.sleep(10)
                continue
            print(f"   [error] giving up on {osm_id}: {e}")
            return None
    return None


# ---------------------------------------------------------------------------
# Stage parsing
# ---------------------------------------------------------------------------

def parse_start_end(data):
    """
    Return (start_name, end_name) for a stage relation.
    Prefers tags.from / tags.to, then parses the name field.
    """
    tags = data.get("tags", {})
    from_place = (tags.get("from") or "").strip()
    to_place   = (tags.get("to")   or "").strip()
    if from_place and to_place:
        return from_place, to_place

    name = (data.get("name") or "").strip()

    # Strip any "<TrailName>: " route-name prefix before a stage keyword
    clean = re.sub(r"^.+?:\s*", "", name, count=1) if re.search(
        r":\s*(?:[ÉéEe]tape|Stage|Etapa|Tappa|Abschnitt|Etappe)\s+\d+", name, re.I
    ) else name
    # Strip leading "Étape N", "Stage N", "Etapa N", "Etappe N" etc.
    clean = re.sub(r"^(?:[ÉéEe]tape|Stage|Etapa|Tappa|Abschnitt|Etappe)\s+\d+\s*[:·\-–—]?\s*",
                   "", clean, flags=re.I).strip()
    # Strip any remaining leading lowercase word(s) — artefacts of bad translation
    clean = re.sub(r"^(?:[a-z]+\s+)+", "", clean).strip()

    # Split on spaced separators: " – ", " — ", " → ", " to ", " - "
    for sep in [" – ", " — ", " → ", " to ", " - "]:
        if sep in clean:
            parts = clean.split(sep, 1)
            return parts[0].strip(), parts[1].strip()

    # Handle bracketed stage format: "[01. Pforzheim→Dobel]" (Westweg pattern)
    m = re.search(r'\[\d+\.\s*(.+?)→(.+?)\]', clean)
    if m:
        return m.group(1).strip(), m.group(2).strip()

    # Handle bare → without spaces (any inline arrow)
    if "→" in clean:
        parts = clean.split("→", 1)
        left  = re.sub(r'[\[\(][^)]*$', "", parts[0]).strip()
        right = re.sub(r'[\]\)][^)]*$', "", parts[1]).strip()
        if left and right:
            return left, right

    # Fallback: split on the last bare hyphen if the right side starts with a capital letter
    # Handles "La Trapa-Coma d'en Vidal" → ("La Trapa", "Coma d'en Vidal")
    m = re.search(r"-([A-ZÁÉÍÓÚÀÈÌÒÙÑÜ])", clean)
    if m:
        idx = clean.rfind("-", 0, m.end())
        left, right = clean[:idx].strip(), clean[idx + 1:].strip()
        if left and right:
            return left, right

    # Last resort: use the cleaned name for both
    fallback = clean or name
    return fallback, fallback


def parse_difficulty(data):
    """Map sac_scale tag to canonical difficulty string, or None."""
    tags = data.get("tags", {})
    sac = (tags.get("sac_scale") or "").strip().lower().replace(" ", "_").replace("-", "_")
    return SAC_SCALE_MAP.get(sac)


def parse_description(data):
    """Extract a short description from OSM tags, or empty string."""
    tags = data.get("tags", {})
    for key in ("description", "description:en", "note"):
        val = (tags.get(key) or "").strip()
        if len(val) > 30:
            return val
    return ""


def build_stage(child_data, stage_nr, skip_elevation=False):
    """
    Build a hikes.json stage dict from a fetched child relation.
    Returns the stage dict, or None if the child has no usable geometry.
    """
    route_node = child_data.get("route", {})

    # Distance from route.length (metres → km)
    length_m = route_node.get("length") or child_data.get("official_length")
    dist_km  = round(length_m / 1000, 1) if length_m else None

    # Start / end names
    start_name, end_name = parse_start_end(child_data)
    if not start_name:
        start_name = end_name = f"Stage {stage_nr}"

    # Elevation
    elev_up = elev_down = None
    quota_hit = False
    if not skip_elevation:
        pts = sample_wgs84(route_node)
        if pts:
            result_up, result_down = fetch_elevation(pts)
            if result_up == "QUOTA_EXHAUSTED":
                quota_hit = True
            else:
                elev_up, elev_down = result_up, result_down

    # Difficulty, description
    difficulty  = parse_difficulty(child_data)
    description = parse_description(child_data)

    stage = {
        "stage_nr":         stage_nr,
        "start_name":       start_name,
        "end_name":         end_name,
        "via":              None,
        "dist_km":          dist_km,
        "elev_up":          elev_up,
        "elev_down":        elev_down,
        "duration_hrs":     None,
        "difficulty":       difficulty,
        "description":      description,
        "cantons":          [],
        "arrival_stations": [],
        "sbb_times":        {},
        "_osm_id":          child_data.get("id"),   # internal resume key
    }
    return stage, quota_hit


# ---------------------------------------------------------------------------
# Trail processing
# ---------------------------------------------------------------------------

def process_trail(osm_id, land, route_id, route_type, display_name,
                  refresh=False, skip_elevation=False):
    """
    Fetch a trail's parent relation and return (route_dict, deferred_reason).

    Stage resolution strategy (Option D):
    1. Collect direct route-type children; filter micro-stages (< 1 km).
    2. For children longer than STAGE_MAX_KM, attempt level-2 descent —
       replace the coarse child with its own subroutes if they exist.
    3. If no route-type children survive, fall back to a single-stage import
       using the parent's total distance and geometry (flat relations like
       most UK National Trails, Irish Way routes, etc.).
    """
    print(f"\n  Fetching parent relation {osm_id}: {display_name} ...")
    parent = fetch_relation(osm_id, display_name)
    if not parent:
        return None, "parent relation fetch failed"

    # Collect direct route-type children; filter micro-stages
    children = [
        c for c in parent.get("route", {}).get("main", [])
        if c.get("route_type") == "route"
    ]
    children = [c for c in children if not (c.get("length") and c.get("length") < 1000)]

    # Level-2 descent: for coarse children attempt to use their subroutes
    if children:
        expanded = []
        for c in children:
            if (c.get("length") or 0) > STAGE_MAX_KM * 1000:
                cid = c.get("id")
                ckm = (c.get("length", 0)) / 1000
                print(f"  ↳ child {cid} is {ckm:.0f} km — trying level-2...", end=" ", flush=True)
                sub = fetch_relation(cid)
                if sub:
                    grandchildren = [
                        gc for gc in sub.get("route", {}).get("main", [])
                        if gc.get("route_type") == "route"
                        and not (gc.get("length") and gc.get("length") < 1000)
                    ]
                    if grandchildren:
                        print(f"{len(grandchildren)} stages found")
                        expanded.extend(grandchildren)
                        continue
                    print("no day stages, keeping as section")
                expanded.append(c)
            else:
                expanded.append(c)
        children = expanded

    single_stage = not children
    if single_stage:
        print(f"  → no subroute children — importing as single stage")
    else:
        print(f"  → {len(children)} candidate stages")

    # Build route skeleton
    tags = parent.get("tags", {})
    total_m = parent.get("official_length") or parent.get("route", {}).get("length") or 0
    route_start = (tags.get("from") or "").strip()
    route_end   = (tags.get("to")   or "").strip()
    route_desc  = ""
    for key in ("description", "description:en"):
        val = (tags.get(key) or "").strip()
        if len(val) > 30:
            route_desc = val
            break

    route = {
        "route_id":    route_id,
        "route_type":  route_type,
        "land":        land,
        "name":        display_name,
        "description": route_desc,
        "start":       route_start,
        "end":         route_end,
        "total_km":    round(total_m / 1000, 1) if total_m else None,
        "stages":      [],
    }

    stages    = []
    quota_hit = False

    if single_stage:
        # Build one stage from the parent's geometry and metadata
        route_node = parent.get("route", {})
        length_m   = parent.get("official_length") or route_node.get("length")
        dist_km    = round(length_m / 1000, 1) if length_m else None
        start_name, end_name = parse_start_end(parent)

        elev_up = elev_down = None
        if not skip_elevation:
            pts = sample_wgs84(route_node)
            if pts:
                result_up, result_down = fetch_elevation(pts)
                if result_up == "QUOTA_EXHAUSTED":
                    quota_hit = True
                else:
                    elev_up, elev_down = result_up, result_down

        elev_str = f"↑{elev_up}m ↓{elev_down}m" if elev_up is not None else "no elev"
        print(f"  [  1] {start_name} → {end_name} ({dist_km} km, {elev_str})")

        stages = [{
            "stage_nr":         1,
            "start_name":       start_name,
            "end_name":         end_name,
            "via":              None,
            "dist_km":          dist_km,
            "elev_up":          elev_up,
            "elev_down":        elev_down,
            "duration_hrs":     None,
            "difficulty":       parse_difficulty(parent),
            "description":      parse_description(parent),
            "cantons":          [],
            "arrival_stations": [],
            "sbb_times":        {},
            "_osm_id":          osm_id,   # parent ID as resume key
        }]

    else:
        stage_nr = 0

        for child_ref in children:
            child_id = child_ref.get("id")
            if not child_id:
                continue

            print(f"  fetching child {child_id}...", end=" ", flush=True)
            child_data = fetch_relation(child_id)
            if not child_data:
                print("fetch failed, skipping")
                continue

            child_name = child_data.get("name", "")

            # Skip route variants — "Variante" standalone or as suffix (e.g. "Höhenvariante")
            if re.search(r'variante', child_name, re.I):
                print(f"skip (route variant: {child_name[:60]})")
                continue

            stage_nr += 1
            stage, hit = build_stage(child_data, stage_nr, skip_elevation=skip_elevation)
            if hit:
                quota_hit = True

            stages.append(stage)
            elev_str = (
                f"↑{stage['elev_up']}m ↓{stage['elev_down']}m"
                if stage.get("elev_up") is not None else "no elev"
            )
            print(
                f"[{stage_nr:3d}] {stage['start_name']} → {stage['end_name']} "
                f"({stage['dist_km']} km, {elev_str})"
            )

            if quota_hit:
                print("   OpenTopoData quota exhausted — stopping elevation calls.")
                skip_elevation = True
                quota_hit = False

    if not stages:
        return None, "all child fetches failed"

    route["stages"] = stages
    if stages:
        route["start"] = stages[0]["start_name"] or route_start
        route["end"]   = stages[-1]["end_name"]  or route_end
    if not route["total_km"]:
        total = sum(s["dist_km"] for s in stages if s.get("dist_km"))
        route["total_km"] = round(total, 1) or None

    return route, None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    p.add_argument("--limit",          type=int,  default=None,
                   help="Only process first N trails (smoke test)")
    p.add_argument("--only",           type=int,  default=None,
                   help="Only process this OSM relation ID")
    p.add_argument("--refresh-trail",  type=int,  action="append", dest="refresh_ids",
                   help="Re-fetch this relation ID even if cached (repeatable)")
    p.add_argument("--skip-elevation", action="store_true",
                   help="Skip OpenTopoData elevation calls")
    args = p.parse_args()

    refresh_ids = set(args.refresh_ids or [])

    existing = load_existing()

    # Index existing stages by (land, route_id, _osm_id) for resume
    def cached_stages(land, route_id):
        key = (land, "national", route_id)
        existing_route = existing.get(key) or {}
        return {s["_osm_id"]: s for s in existing_route.get("stages", []) if s.get("_osm_id")}

    catalog = TRAILS
    if args.only:
        catalog = [t for t in catalog if t[0] == args.only]
        if not catalog:
            print(f"No trail with OSM ID {args.only} in catalog.")
            sys.exit(1)
    if args.limit:
        catalog = catalog[:args.limit]

    deferred = []
    total_stages = 0

    try:
        for osm_id, land, route_id, route_type, display_name in catalog:
            key = (land, route_type, route_id)
            do_refresh = (osm_id in refresh_ids)

            # Check if already fully scraped (all children have _osm_id in cache)
            if not do_refresh:
                existing_route = existing.get(key)
                if existing_route and existing_route.get("stages"):
                    print(f"\nSkipping {display_name} ({osm_id}) — already cached "
                          f"({len(existing_route['stages'])} stages). "
                          f"Use --refresh-trail {osm_id} to re-fetch.")
                    total_stages += len(existing_route["stages"])
                    continue

            route, reason = process_trail(
                osm_id, land, route_id, route_type, display_name,
                refresh=do_refresh,
                skip_elevation=args.skip_elevation,
            )

            if route is None:
                print(f"  DEFERRED: {display_name} — {reason}")
                deferred.append((osm_id, display_name, reason))
                continue

            existing[key] = route
            total_stages += len(route["stages"])
            print(f"  Saved {len(route['stages'])} stages for {display_name}.")

            # Save after every trail
            save(list(existing.values()))

    except KeyboardInterrupt:
        print("\nInterrupted — saving progress...")
        save(list(existing.values()))
        sys.exit(0)

    save(list(existing.values()))

    # Summary
    print(f"\n{'='*60}")
    print(f"OSM scrape complete. {len(catalog) - len(deferred)} trails scraped, "
          f"{total_stages} stages total.")
    if deferred:
        print(f"\nDeferred ({len(deferred)} trails — no viable day-stage subroutes):")
        for did, dname, reason in deferred:
            print(f"  {did}: {dname} — {reason}")
    print("="*60)


if __name__ == "__main__":
    main()
