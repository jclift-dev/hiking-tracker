#!/usr/bin/env python3
"""
scraper_websites.py — fetches trails whose day-stage data comes from official websites
but have no usable day-stage hierarchy in OpenStreetMap.

Trails:
  Eifelsteig                  (de-hike, route_id=49)  eifelsteig.de
  Italia Coast to Coast        (it-hike, route_id=13)  italiacoast2coast.it
  Sauerland-Waldroute          (de-hike, route_id=44)  sauerland-waldroute.de  [overwrites OSM sections]
  Linksrheinischer Jakobsweg   (de-hike, route_id=50)  linksrheinischer-jakobsweg.info
  WestfalenWanderWeg           (de-hike, route_id=51)  wildganz.com

Usage:
  python3 scraper_websites.py
  python3 scraper_websites.py --only eifelsteig
  python3 scraper_websites.py --refresh     # re-fetch all
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HIKES_FILE = Path("hikes.json")
DELAY = 1.5


SESSION = requests.Session()
SESSION.headers["User-Agent"] = "Mozilla/5.0 (compatible; HikingTracker/1.0)"


def load_hikes():
    return json.loads(HIKES_FILE.read_text()) if HIKES_FILE.exists() else []


def save_hikes(routes):
    HIKES_FILE.write_text(json.dumps(routes, ensure_ascii=False, indent=2))


def fetch(url):
    try:
        r = SESSION.get(url, timeout=20, allow_redirects=True)
        return r.text if r.status_code == 200 else None
    except Exception as e:
        print(f"  fetch error: {e}")
        return None


def parse_km(s):
    if not s:
        return None
    try:
        return round(float(s.replace(",", ".")), 1)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Eifelsteig — eifelsteig.de/eifelsteig-etappen
# ---------------------------------------------------------------------------
# Each article element has heading "Eifelsteig-Etappe NN StartTown"
# and body "Distanz: XX,X km".  End of stage N = start of stage N+1.
# Final stage (15) ends in Trier per description.

EIFELSTEIG_URL = "https://www.eifelsteig.de/eifelsteig-etappen"
EIFELSTEIG_ARTICLE_RE = re.compile(
    r'Eifelsteig-Etappe\s+(\d+)\s+(.+?)\s+Distanz:\s*([\d,]+)\s*km',
    re.DOTALL,
)


def scrape_eifelsteig():
    print(f"Fetching {EIFELSTEIG_URL} ...")
    html = fetch(EIFELSTEIG_URL)
    if not html:
        print("  ERROR: fetch failed")
        return None

    soup = BeautifulSoup(html, "html.parser")
    raw = []
    for article in soup.find_all("article"):
        text = article.get_text(" ", strip=True)
        m = EIFELSTEIG_ARTICLE_RE.search(text)
        if m:
            raw.append((int(m.group(1)), m.group(2).strip(), parse_km(m.group(3))))

    if not raw:
        print("  ERROR: no stages found")
        return None

    raw.sort(key=lambda x: x[0])
    stages = []
    for i, (nr, start, km) in enumerate(raw):
        end = raw[i + 1][1] if i + 1 < len(raw) else "Trier"
        stages.append({
            "stage_nr":         nr,
            "start_name":       start,
            "end_name":         end,
            "via":              None,
            "dist_km":          km,
            "elev_up":          None,
            "elev_down":        None,
            "duration_hrs":     None,
            "difficulty":       None,
            "description":      None,
            "arrival_stations": [],
            "sbb_times":        {},
            "_source_url":      EIFELSTEIG_URL,
        })

    total_km = round(sum(s["dist_km"] for s in stages if s["dist_km"]), 1)
    print(f"  {len(stages)} stages, {total_km} km total")
    return {
        "route_id":   49,
        "route_type": "national",
        "land":       "de-hike",
        "name":       "Eifelsteig",
        "description": None,
        "start":      stages[0]["start_name"],
        "end":        stages[-1]["end_name"],
        "total_km":   total_km,
        "stages":     stages,
    }


# ---------------------------------------------------------------------------
# Italia Coast to Coast — italiacoast2coast.it/tappe-e-tracce-gps/
# ---------------------------------------------------------------------------
# h2/h3 headings in format "Tappa N: Start – End"
# No distance data on the listing page.

ITALIAC2C_URL = "https://www.italiacoast2coast.it/tappe-e-tracce-gps/"
ITALIAC2C_STAGE_RE = re.compile(
    r'(?i)^tappa\s+(\d+):\s*(.+?)\s*[–—-]\s*(.+)$'
)


def scrape_italiac2c():
    print(f"Fetching {ITALIAC2C_URL} ...")
    html = fetch(ITALIAC2C_URL)
    if not html:
        print("  ERROR: fetch failed")
        return None

    soup = BeautifulSoup(html, "html.parser")
    seen = set()
    stages = []
    for tag in soup.find_all(["h2", "h3", "h4"]):
        text = tag.get_text(" ", strip=True)
        m = ITALIAC2C_STAGE_RE.match(text)
        if not m:
            continue
        nr = int(m.group(1))
        if nr in seen:
            continue
        seen.add(nr)
        stages.append({
            "stage_nr":         nr,
            "start_name":       m.group(2).strip(),
            "end_name":         m.group(3).strip(),
            "via":              None,
            "dist_km":          None,
            "elev_up":          None,
            "elev_down":        None,
            "duration_hrs":     None,
            "difficulty":       None,
            "description":      None,
            "arrival_stations": [],
            "sbb_times":        {},
            "_source_url":      ITALIAC2C_URL,
        })

    stages.sort(key=lambda s: s["stage_nr"])
    if not stages:
        print("  ERROR: no stages found")
        return None

    print(f"  {len(stages)} stages")
    return {
        "route_id":   13,
        "route_type": "national",
        "land":       "it-hike",
        "name":       "Italia Coast to Coast",
        "description": None,
        "start":      stages[0]["start_name"],
        "end":        stages[-1]["end_name"],
        "total_km":   None,
        "stages":     stages,
    }


# ---------------------------------------------------------------------------
# Sauerland-Waldroute — sauerland-waldroute.de
# ---------------------------------------------------------------------------
# Stage listing at /de/tourenplanung/wandern-in-etappen
# Format: "Sauerland-Waldroute - Etappe N: Start - End"  (partial km in context)
# Overwrites the 3 coarse OSM sections already in route_id=44.

SAUERLAND_URL = "https://www.sauerland-waldroute.de/de/tourenplanung/wandern-in-etappen"
SAUERLAND_RE = re.compile(
    r'Etappe\s+(\d+):\s*([^-\n]+?)\s+-\s+([^\n]+)',
    re.IGNORECASE,
)


def scrape_sauerland():
    print(f"Fetching {SAUERLAND_URL} ...")
    html = fetch(SAUERLAND_URL)
    if not html:
        print("  ERROR: fetch failed")
        return None

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n")

    seen = set()
    stages = []
    for m in SAUERLAND_RE.finditer(text):
        nr = int(m.group(1))
        if nr in seen:
            continue
        seen.add(nr)
        start = m.group(2).strip()
        end = m.group(3).strip()
        # Look for km near this match
        context = text[m.start():m.start() + 400]
        km_m = re.search(r'(\d+[\.,]\d*)\s*km', context, re.I)
        stages.append({
            "stage_nr":         nr,
            "start_name":       start,
            "end_name":         end,
            "via":              None,
            "dist_km":          parse_km(km_m.group(1)) if km_m else None,
            "elev_up":          None,
            "elev_down":        None,
            "duration_hrs":     None,
            "difficulty":       None,
            "description":      None,
            "arrival_stations": [],
            "sbb_times":        {},
            "_source_url":      SAUERLAND_URL,
        })

    stages.sort(key=lambda s: s["stage_nr"])
    if len(stages) < 5:
        print(f"  WARNING: only {len(stages)} stages found (expected 19) — JS-rendered content missing")
        if not stages:
            return None

    total_km = round(sum(s["dist_km"] for s in stages if s["dist_km"]), 1)
    print(f"  {len(stages)} stages, ~{total_km} km total (partial km data)")
    return {
        "route_id":   44,
        "route_type": "national",
        "land":       "de-hike",
        "name":       "Sauerland-Waldroute",
        "description": None,
        "start":      stages[0]["start_name"],
        "end":        stages[-1]["end_name"],
        "total_km":   244.7,
        "stages":     stages,
    }


# ---------------------------------------------------------------------------
# Linksrheinischer Jakobsweg — linksrheinischer-jakobsweg.info
# ---------------------------------------------------------------------------
# Stage pages at /index.php/linksrheinischer-jakobsweg/etappenuebersicht/N-etappe
# Heading format: "N. Etappe von Start nach End (ca. X km)"

LINKSRH_BASE = "http://www.linksrheinischer-jakobsweg.info"
LINKSRH_STAGE_RE = re.compile(
    r'(\d+)\.\s*Etappe\s+von\s+(.+?)\s+nach\s+(.+?)\s*\(ca\.\s*([\d,\.]+)\s*km\)',
    re.IGNORECASE,
)
LINKSRH_N = 12


def scrape_linksrh():
    stages = []
    for nr in range(1, LINKSRH_N + 1):
        url = f"{LINKSRH_BASE}/index.php/linksrheinischer-jakobsweg/etappenuebersicht/{nr}-etappe"
        print(f"  Etappe {nr:2d} — {url}", flush=True)
        time.sleep(DELAY)
        html = fetch(url)
        if not html:
            print(f"    fetch error")
            continue
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)
        m = LINKSRH_STAGE_RE.search(text)
        if not m:
            print(f"    no match in page text")
            continue
        stages.append({
            "stage_nr":         int(m.group(1)),
            "start_name":       m.group(2).strip(),
            "end_name":         m.group(3).strip(),
            "via":              None,
            "dist_km":          parse_km(m.group(4)),
            "elev_up":          None,
            "elev_down":        None,
            "duration_hrs":     None,
            "difficulty":       None,
            "description":      None,
            "arrival_stations": [],
            "sbb_times":        {},
            "_source_url":      url,
        })
        print(f"    {m.group(2).strip()} → {m.group(3).strip()} ({m.group(4)} km)")

    stages.sort(key=lambda s: s["stage_nr"])
    if not stages:
        return None
    total_km = round(sum(s["dist_km"] for s in stages if s["dist_km"]), 1)
    print(f"  {len(stages)} stages, {total_km} km total")
    return {
        "route_id":   50,
        "route_type": "national",
        "land":       "de-hike",
        "name":       "Linksrheinischer Jakobsweg",
        "description": None,
        "start":      stages[0]["start_name"],
        "end":        stages[-1]["end_name"],
        "total_km":   total_km,
        "stages":     stages,
    }


# ---------------------------------------------------------------------------
# WestfalenWanderWeg — wildganz.com/fernwanderweg/westfalenwanderweg-etappe-N
# ---------------------------------------------------------------------------
# Every stage page has a bottom section listing all 11 stages with
# "WestfalenWanderWeg Etappe N" / km / "Start: X" / "Ziel: Y".
# Parse all stages from a single page.

WESTFALEN_URL1 = "https://www.wildganz.com/fernwanderweg/westfalenwanderweg-etappe-1"
WESTFALEN_STAGE_RE = re.compile(r'WestfalenWanderWeg\s+Etappe\s+(\d+)', re.I)


def scrape_westfalen():
    print(f"Fetching {WESTFALEN_URL1} ...", flush=True)
    time.sleep(DELAY)
    html = fetch(WESTFALEN_URL1)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    lines = [l.strip() for l in soup.get_text("\n").split("\n") if l.strip()]

    # Find the bottom stage-listing section (starts at "Etappen" header).
    # Each block: "WestfalenWanderWeg Etappe N" / "X km" / ... / "Start: X" / "Ziel: Y"
    stages = []
    seen_nrs = set()
    i = 0
    while i < len(lines):
        m = WESTFALEN_STAGE_RE.match(lines[i])
        if m:
            nr = int(m.group(1))
            if nr in seen_nrs:
                i += 1
                continue
            start = end = dist = None
            j = i + 1
            while j < len(lines) and j < i + 15:
                if lines[j].startswith("Start:"):
                    start = lines[j][len("Start:"):].strip()
                elif lines[j].startswith("Ziel:"):
                    end = lines[j][len("Ziel:"):].strip()
                elif re.match(r'^[\d,\.]+\s*km$', lines[j], re.I) and dist is None:
                    dist = parse_km(re.match(r'^([\d,\.]+)', lines[j]).group(1))
                if start and end and dist is not None:
                    break
                j += 1
            if start and end:
                seen_nrs.add(nr)
                stages.append({
                    "stage_nr":         nr,
                    "start_name":       start,
                    "end_name":         end,
                    "via":              None,
                    "dist_km":          dist,
                    "elev_up":          None,
                    "elev_down":        None,
                    "duration_hrs":     None,
                    "difficulty":       None,
                    "description":      None,
                    "arrival_stations": [],
                    "sbb_times":        {},
                    "_source_url":      WESTFALEN_URL1,
                })
                print(f"  Etappe {nr:2d}  {start} → {end} ({dist} km)")
            i = j
        else:
            i += 1

    stages.sort(key=lambda s: s["stage_nr"])
    if not stages:
        print("  ERROR: no stages parsed")
        return None
    total_km = round(sum(s["dist_km"] for s in stages if s["dist_km"]), 1)
    print(f"  {len(stages)} stages, {total_km} km total")
    return {
        "route_id":   51,
        "route_type": "national",
        "land":       "de-hike",
        "name":       "WestfalenWanderWeg",
        "description": None,
        "start":      stages[0]["start_name"],
        "end":        stages[-1]["end_name"],
        "total_km":   total_km,
        "stages":     stages,
    }


# ---------------------------------------------------------------------------
# Trail registry
# ---------------------------------------------------------------------------

TRAILS = {
    "eifelsteig":     scrape_eifelsteig,
    "italiac2c":      scrape_italiac2c,
    "sauerland":      scrape_sauerland,
    "linksrh":        scrape_linksrh,
    "westfalen":      scrape_westfalen,
}


def main():
    p = argparse.ArgumentParser(description="Scrape official trail websites")
    p.add_argument("--only",    help=f"trail slug: {', '.join(TRAILS)}")
    p.add_argument("--refresh", action="store_true", help="re-fetch even if cached")
    args = p.parse_args()

    if args.only and args.only not in TRAILS:
        print(f"Unknown trail '{args.only}'. Choose from: {', '.join(TRAILS)}")
        sys.exit(1)

    todo = {args.only: TRAILS[args.only]} if args.only else TRAILS

    routes = load_hikes()
    index = {(r["land"], r["route_id"]): i for i, r in enumerate(routes)}

    for slug, scrape_fn in todo.items():
        print(f"\n=== {slug} ===")
        time.sleep(DELAY)
        route = scrape_fn()
        if not route:
            print(f"  SKIPPED: scrape returned nothing")
            continue

        key = (route["land"], route["route_id"])
        if key in index and not args.refresh:
            existing = routes[index[key]]
            if len(existing.get("stages", [])) == len(route["stages"]):
                print(f"  Already cached with {len(route['stages'])} stages — use --refresh to re-fetch")
                continue

        if key in index:
            routes[index[key]] = route
            print(f"  Updated existing route_id={route['route_id']}")
        else:
            routes.append(route)
            index[key] = len(routes) - 1
            print(f"  Added route_id={route['route_id']}")

        save_hikes(routes)

    print("\nDone. Run: source .env && python3 scraper.py --import")


if __name__ == "__main__":
    main()
