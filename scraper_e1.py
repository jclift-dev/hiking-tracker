#!/usr/bin/env python3
"""
scraper_e1.py — fetches E1 European Long Distance Path stages from hiking-europe.eu
Source: https://www.hiking-europe.eu/en/e1/stages
Trail: E1 (North Cape → Sicily, ~7700 km, ~420 stages)  eu-hike route_id=5

Crawl phases:
  1. Collect leaf stage URLs from all 5 country sections (fast, ~20 pages)
  2. Fetch each individual stage page for title + km (slow, ~420 pages @ 1s delay)

URL cache: .e1_cache.json  (avoids re-fetching on retry)
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HIKES_FILE  = Path("hikes.json")
CACHE_FILE  = Path(".e1_cache.json")
DELAY       = 1.0
BASE        = "https://www.hiking-europe.eu"
ROUTE_ID    = 5
LAND        = "eu-hike"

COUNTRY_SECTIONS = [
    "norway-finland-sweden",
    "denmark",
    "germany",
    "switzerland",
    "italy",
]
# Geographic order index for cross-country sorting
COUNTRY_ORDER = {c: i for i, c in enumerate(COUNTRY_SECTIONS)}

SESSION = requests.Session()
SESSION.headers["User-Agent"] = "Mozilla/5.0 (compatible; HikingTracker/1.0)"


def fetch(url, delay=True):
    if delay:
        time.sleep(DELAY)
    try:
        r = SESSION.get(url, timeout=30)
        return r.text if r.status_code == 200 else None
    except Exception as e:
        print(f"  fetch error {url}: {e}")
        return None


def load_json(path):
    return json.loads(path.read_text()) if path.exists() else {}


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def load_hikes():
    return json.loads(HIKES_FILE.read_text()) if HIKES_FILE.exists() else []


def save_hikes(routes):
    HIKES_FILE.write_text(json.dumps(routes, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# Phase 1: collect leaf URLs
# ---------------------------------------------------------------------------

LEAF_RE = re.compile(
    r'href="(/en/e1/stages/[a-z-]+/[a-z-]+/[a-z-]+)"'
)


def collect_leaf_urls():
    """Return list of (country, url_path) tuples (skipping western variant)."""
    all_leaves = []
    for country in COUNTRY_SECTIONS:
        url = f"{BASE}/en/e1/stages/{country}"
        print(f"  Scanning {country} ...", flush=True)
        html = fetch(url)
        if not html:
            print(f"  ERROR: could not fetch {url}")
            continue
        leaves = sorted(set(LEAF_RE.findall(html)))
        # Skip western variant (alternative route for Schleswig-Holstein)
        leaves = [l for l in leaves if "western-variant" not in l]
        print(f"    {len(leaves)} stages")
        for l in leaves:
            all_leaves.append((country, l))
    return all_leaves


# ---------------------------------------------------------------------------
# Phase 2: fetch individual stage pages
# ---------------------------------------------------------------------------

TITLE_RE = re.compile(r'<h1[^>]*>\s*([^<\n]+?)\s*</h1>')
KM_RE    = re.compile(r'([\d.]+)\s*km')
# Stage key: "NN.NN" (e.g. "08.13", "10.01")
STAGE_KEY_RE = re.compile(r'^(\d+\.\d+)\s+(.+?)\s+-\s+(.+)$')


def fetch_stage(url_path, cache):
    """Fetch stage page and return (sort_key, title, start, end, km_str) or None."""
    if url_path in cache:
        return cache[url_path]
    url = BASE + url_path
    html = fetch(url)
    if not html:
        cache[url_path] = None
        return None
    title_m = TITLE_RE.search(html)
    if not title_m:
        cache[url_path] = None
        return None
    title = title_m.group(1).strip()
    km_m = KM_RE.search(html)
    km_str = km_m.group(1) if km_m else None
    # Parse title: "NN.NN Start - End"
    key_m = STAGE_KEY_RE.match(title)
    if not key_m:
        # Fallback: use URL slug for start/end
        slug = url_path.rstrip('/').split('/')[-1]
        parts = slug.split('-', 1)
        start = parts[0].replace('-', ' ').title()
        end   = parts[1].replace('-', ' ').title() if len(parts) > 1 else ''
        result = ("99.99", title, start, end, km_str)
    else:
        result = (key_m.group(1), title, key_m.group(2), key_m.group(3), km_str)
    cache[url_path] = result
    return result


def parse_km(s):
    if not s:
        return None
    try:
        return round(float(s.replace(",", ".")), 1)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="Scrape E1 trail from hiking-europe.eu")
    p.add_argument("--refresh",        action="store_true", help="re-fetch even if cached in hikes.json")
    p.add_argument("--clear-cache",    action="store_true", help="delete .e1_cache.json and start fresh")
    p.add_argument("--collect-only",   action="store_true", help="only run phase 1 (URL collection)")
    args = p.parse_args()

    if args.clear_cache and CACHE_FILE.exists():
        CACHE_FILE.unlink()
        print("Cache cleared.")

    routes = load_hikes()
    index  = {(r["land"], r["route_id"]): i for i, r in enumerate(routes)}
    key    = (LAND, ROUTE_ID)

    if key in index and not args.refresh:
        existing = routes[index[key]]
        print(f"E1 already cached with {len(existing.get('stages', []))} stages. Use --refresh to re-fetch.")
        sys.exit(0)

    cache = load_json(CACHE_FILE)

    print("=== Phase 1: Collecting leaf stage URLs ===")
    leaf_urls = collect_leaf_urls()
    print(f"  Total: {len(leaf_urls)} stage URLs collected\n")

    if args.collect_only:
        print("--collect-only: stopping after phase 1.")
        sys.exit(0)

    print("=== Phase 2: Fetching individual stage pages ===")
    raw_stages = []
    errors = 0
    for i, (country, url_path) in enumerate(leaf_urls, 1):
        result = fetch_stage(url_path, cache)
        # Save cache every 50 pages
        if i % 50 == 0:
            save_json(CACHE_FILE, cache)
            print(f"  ... {i}/{len(leaf_urls)} fetched, {errors} errors")
        if result is None:
            print(f"  ERROR: {url_path}")
            errors += 1
            continue
        sort_key, title, start, end, km_str = result
        country_idx = COUNTRY_ORDER[country]
        raw_stages.append((country_idx, sort_key, start, end, km_str, BASE + url_path, country))

    save_json(CACHE_FILE, cache)
    print(f"  Done: {len(raw_stages)} stages fetched, {errors} errors")

    # Sort by (country order, section.stage float)
    raw_stages.sort(key=lambda x: (x[0], float(x[1]) if x[1] != "99.99" else 9999))

    stages = []
    for i, (country_idx, sort_key, start, end, km_str, src_url, country) in enumerate(raw_stages, 1):
        stages.append({
            "stage_nr":         i,
            "start_name":       start.strip(),
            "end_name":         end.strip(),
            "via":              None,
            "dist_km":          parse_km(km_str),
            "elev_up":          None,
            "elev_down":        None,
            "duration_hrs":     None,
            "difficulty":       None,
            "description":      None,
            "arrival_stations": [],
            "sbb_times":        {},
            "_source_url":      src_url,
            "_e1_section":      f"{country}/{sort_key}",
        })

    valid_km = [s["dist_km"] for s in stages if s["dist_km"]]
    total_km = round(sum(valid_km), 1)
    print(f"\n  {len(stages)} stages, {total_km} km total")
    print(f"  Start: {stages[0]['start_name']} → End: {stages[-1]['end_name']}")

    route = {
        "route_id":   ROUTE_ID,
        "route_type": "international",
        "land":       LAND,
        "name":       "E1 European Long Distance Path",
        "description": None,
        "start":      stages[0]["start_name"],
        "end":        stages[-1]["end_name"],
        "total_km":   total_km,
        "stages":     stages,
    }

    if key in index:
        routes[index[key]] = route
        print(f"  Updated existing route_id={ROUTE_ID}")
    else:
        routes.append(route)
        print(f"  Added route_id={ROUTE_ID}")

    save_hikes(routes)
    print("\nDone. Run: source .env && python3 scraper.py --import")


if __name__ == "__main__":
    main()
