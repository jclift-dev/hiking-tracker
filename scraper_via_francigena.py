#!/usr/bin/env python3
"""
scraper_via_francigena.py — fetches the full official Via Francigena from
viefrancigene.org (EAVF, European Association of the Via Francigena Ways).

Replaces eu-hike route_id=16 (previously a 51-stage Lausanne→Roma gronze.com
scrape) with the complete London(Southwark)→Santa Maria di Leuca route:

  VFEB  1–7    England   Southwark → Canterbury  ("Francigena Britannica")
  VFE   1–2    England   Canterbury → Dover
  VFF   3–49   France    Calais → Jougne
  VFS   50–59  Switzerland  Jougne → Colle del Gran San Bernardo
  VFI   60–149 Italy     Gran San Bernardo → Roma → Santa Maria di Leuca

Total: 156 stages.

Data source: the site's Angular app calls a JSON API for its interactive map.
  Bulk track list (GeoJSON, all sections incl. variants):
    GET /api/website/map/tracks?trackType=1
  Per-track detail (distance, difficulty, slug, description):
    GET /api/website/map/tracks/{trackId}

Variant/alternate tracks (Val di Susa entrance, Monte Sant'Angelo loop,
Litoranea coastal variant, Bradanica inland variant, and per-stage "_N"
sub-variants) are excluded — only the single canonical numbered path is kept.

Country/admin1 are computed directly from each track's own coordinates
(Natural Earth point-in-polygon lookup, reusing enrich_regions.py's spatial
index) rather than via ROUTE_DEFAULTS — there's no need to hand-write region
ranges across 4 countries when we already have precise per-stage geometry.

Cache: .via_francigena_cache.json (bulk tracks GeoJSON + per-track details)

Usage:
    python3 scraper_via_francigena.py              # build from cache or fetch
    python3 scraper_via_francigena.py --refresh     # re-fetch everything
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from enrich_regions import load_ne_geojson, build_spatial_index, find_region

HIKES_FILE  = Path("hikes.json")
CACHE_FILE  = Path(".via_francigena_cache.json")
DELAY       = 0.6
BASE        = "https://www.viefrancigene.org"
ROUTE_ID    = 16
LAND        = "eu-hike"

# Existing link_keys from the gronze-sourced version (Lausanne -> Gd St-Bernard),
# shared with ch-hike:70 (SchweizMobil ViaFrancigena). Re-applied by VFS number.
LINK_KEYS_BY_VFS_NUM = {
    53: "via-francigena-ch-1",  # Lausanne -> Vevey
    54: "via-francigena-ch-2",  # Vevey -> Aigle
    55: "via-francigena-ch-3",  # Aigle -> Saint-Maurice
    56: "via-francigena-ch-4",  # Saint-Maurice -> Martigny
    57: "via-francigena-ch-5",  # Martigny -> Orsieres
    58: "via-francigena-ch-6",  # Orsieres -> Bourg-Saint-Pierre
    59: "via-francigena-ch-7",  # Bourg-Saint-Pierre -> Gd St-Bernard
}

# (prefix, country_iso2) in final stage order
PREFIX_ORDER = ["VFEB", "VFE", "VFF", "VFS", "VFI"]
PREFIX_COUNTRY = {"VFEB": "gb", "VFE": "gb", "VFF": "fr", "VFS": "ch", "VFI": "it"}

TRACK_NAME_RE = re.compile(r'([A-Z]+)\s*-?\s*(\d+)(_\d+)?\s*-\s*(.+)')
# detail["startInformation"]/["endInformation"] contain typos on the source
# (e.g. "Venery" for "Vevey") - the "From X to Y" in the name field is clean.
START_END_RE = re.compile(r'[A-Z]+\s*-\s*\d+(?:_\d+)?\s*-\s*(?:[Ff]rom\s+)?(.+?)\s+(?:to|ad)\s+(.+)$')
MAIN_SECTION_ORDERS = {0, 1, 2, 3, 4}

SESSION = requests.Session()
SESSION.headers["User-Agent"] = "Mozilla/5.0 (compatible; HikingTracker/1.0)"


def fetch_json(url):
    time.sleep(DELAY)
    r = SESSION.get(url, timeout=30)
    r.raise_for_status()
    return r.json()


def load_cache():
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text())
    return {"bulk": None, "details": {}}


def save_cache(cache):
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False))


def elevation_gain_loss(coords):
    """coords: list of [lon, lat, elev_m]. Returns (gain, loss) in metres."""
    gain = loss = 0.0
    for i in range(1, len(coords)):
        prev_z = coords[i - 1][2] if len(coords[i - 1]) > 2 else None
        cur_z  = coords[i][2] if len(coords[i]) > 2 else None
        if prev_z is None or cur_z is None:
            continue
        delta = cur_z - prev_z
        if delta > 0:
            gain += delta
        else:
            loss += -delta
    return round(gain), round(loss)


def midpoint(coords):
    if not coords:
        return None
    lon, lat = coords[len(coords) // 2][0], coords[len(coords) // 2][1]
    return lat, lon


def main():
    p = argparse.ArgumentParser(description="Scrape the official Via Francigena from viefrancigene.org")
    p.add_argument("--refresh", action="store_true", help="re-fetch bulk track list + all details")
    args = p.parse_args()

    cache = {"bulk": None, "details": {}} if args.refresh else load_cache()

    if cache["bulk"] is None:
        print("Fetching bulk track list (GeoJSON)...")
        cache["bulk"] = fetch_json(f"{BASE}/api/website/map/tracks?trackType=1")
        save_cache(cache)

    features = cache["bulk"]["features"]
    print(f"Total tracks in bulk list: {len(features)}")

    # Filter to canonical (non-variant) tracks in the main sections
    canon = []
    for f in features:
        props = f["properties"]
        if props["sectionOrder"] not in MAIN_SECTION_ORDERS:
            continue
        name = props["trackName"]
        m = TRACK_NAME_RE.match(name)
        if not m:
            print(f"  [warn] unmatched track name: {name}")
            continue
        prefix, num, variant_suffix, rest = m.groups()
        if variant_suffix or "variant" in rest.lower() or "winter" in rest.lower():
            continue
        if prefix not in PREFIX_COUNTRY:
            print(f"  [warn] unknown prefix {prefix}: {name}")
            continue
        canon.append({
            "prefix": prefix,
            "num": int(num),
            "name": name,
            "trackId": props["trackId"],
            "coords": f["geometry"]["coordinates"],
        })

    print(f"Canonical stages: {len(canon)}")

    # Order: VFEB asc, VFE asc, VFF asc, VFS asc, VFI asc
    order_key = {p: i for i, p in enumerate(PREFIX_ORDER)}
    canon.sort(key=lambda t: (order_key[t["prefix"]], t["num"]))

    print("Loading Natural Earth admin-1 boundaries...")
    ne_data = load_ne_geojson()
    spatial_index = build_spatial_index(ne_data["features"])

    stages = []
    for i, t in enumerate(canon, 1):
        track_id = t["trackId"]
        if track_id not in cache["details"]:
            print(f"  [{i}/{len(canon)}] fetching detail {t['prefix']}-{t['num']:02d}...", end=" ", flush=True)
            try:
                cache["details"][track_id] = fetch_json(f"{BASE}/api/website/map/tracks/{track_id}")
            except Exception as e:
                print(f"FAILED: {e}")
                continue
            if i % 20 == 0:
                save_cache(cache)
            print("ok")

        detail = cache["details"][track_id]
        coords = t["coords"]
        gain, loss = elevation_gain_loss(coords)
        mid = midpoint(coords)
        country, admin1 = (None, None)
        if mid:
            country, admin1 = find_region(mid[0], mid[1], spatial_index)
        if not country:
            country = PREFIX_COUNTRY[t["prefix"]]

        link_key = LINK_KEYS_BY_VFS_NUM.get(t["num"]) if t["prefix"] == "VFS" else None

        m = START_END_RE.match(t["name"])
        start_name, end_name = (m.group(1), m.group(2)) if m else (
            detail.get("startInformation") or "?", detail.get("endInformation") or "?"
        )
        description = re.sub(r'<[^>]+>', '', detail.get("description") or "").strip() or None

        stages.append({
            "stage_nr":         i,
            "start_name":       start_name,
            "end_name":         end_name,
            "via":              None,
            "dist_km":          round(detail["lengthInMeters"] / 1000, 1) if detail.get("lengthInMeters") else None,
            "elev_up":          gain,
            "elev_down":        loss,
            "duration_hrs":     None,
            "difficulty":       None,
            "description":      description,
            "arrival_stations": [],
            "sbb_times":        {},
            "_source_url":      f"{BASE}/en/itineraries/{detail.get('slug', track_id)}",
            "country":          country,
            "admin1":           admin1,
            "_link_key":        link_key,
        })

    save_cache(cache)

    valid_km = [s["dist_km"] for s in stages if s["dist_km"]]
    total_km = round(sum(valid_km), 1)
    print(f"\n{len(stages)} stages, {total_km} km total")
    print(f"Start: {stages[0]['start_name']} -> End: {stages[-1]['end_name']}")

    route = {
        "route_id":   ROUTE_ID,
        "route_type": "international",
        "land":       LAND,
        "name":       "Via Francígena",
        "description": None,
        "start":      stages[0]["start_name"],
        "end":        stages[-1]["end_name"],
        "total_km":   total_km,
        "stages":     stages,
    }

    routes = json.loads(HIKES_FILE.read_text()) if HIKES_FILE.exists() else []
    index = {(r["land"], r["route_id"]): idx for idx, r in enumerate(routes)}
    key = (LAND, ROUTE_ID)
    if key in index:
        routes[index[key]] = route
        print(f"Replaced existing route_id={ROUTE_ID}")
    else:
        routes.append(route)
        print(f"Added new route_id={ROUTE_ID}")

    HIKES_FILE.write_text(json.dumps(routes, ensure_ascii=False, separators=(",", ":")))
    print(f"Saved {HIKES_FILE}")


if __name__ == "__main__":
    main()
