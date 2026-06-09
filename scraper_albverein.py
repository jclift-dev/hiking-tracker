#!/usr/bin/env python3
"""
scraper_albverein.py — fetches Hauptwanderwege from Schwäbischer Albverein
Source: https://wege.albverein.net/wanderwege/hauptwanderwege/{slug}/etappenbeschreibung-{slug}/
Trails: HW1 (route_id=33), HW2 (34), HW5 (35), HW7 (36), all land="de-hike"
"""

import argparse
import json
import re
import sys
import time
from html import unescape
from pathlib import Path

import requests

HIKES_FILE = Path("hikes.json")
DELAY = 1.5

TRAILS = [
    {
        "slug":       "hw1",
        "route_id":   33,
        "name":       "Schwäbische Alb-Nordrand-Weg",
        "start":      "Donauwörth",
        "end":        "Tuttlingen",
    },
    {
        "slug":       "hw2",
        "route_id":   34,
        "name":       "Schwäbische Alb-Südrand-Weg",
        "start":      "Donauwörth",
        "end":        "Tuttlingen",
    },
    {
        "slug":       "hw5",
        "route_id":   35,
        "name":       "Schwarzwald-Schwäbische-Alb-Allgäu-Weg",
        "start":      "Pforzheim",
        "end":        "Schwarzer Grat",
    },
    {
        "slug":       "hw7",
        "route_id":   36,
        "name":       "Schwäbische-Alb-Oberschwaben-Weg",
        "start":      "Lorch",
        "end":        "Friedrichshafen",
    },
    {
        "slug":       "hw3",
        "route_id":   37,
        "name":       "Main-Neckar-Rhein-Weg",
        "start":      "Wertheim",
        "end":        "Lörrach",
    },
    {
        "slug":       "hw6",
        "route_id":   38,
        "name":       "Limes-Wanderweg",
        "start":      "Miltenberg",
        "end":        "Wilburgstetten",
    },
    {
        "slug":       "hw8",
        "route_id":   39,
        "name":       "Frankenweg",
        "start":      "Pforzheim",
        "end":        "Rothenburg ob der Tauber",
    },
    {
        "slug":       "hw9",
        "route_id":   40,
        "name":       "Heuberg-Allgäu-Weg",
        "start":      "Spaichingen",
        "end":        "Schwarzer Grat",
    },
    {
        "slug":       "hw10",
        "route_id":   41,
        "name":       "Stromberg-Schwäbischer Wald-Weg",
        "start":      "Pforzheim",
        "end":        "Lorch",
    },
    {
        "slug":       "georg-fahrbach-weg-gfw",
        "route_id":   52,
        "name":       "Georg-Fahrbach-Weg",
        "start":      "Criesbach",
        "end":        "Stuttgart-Uhlbach",
    },
]

SESSION = requests.Session()
SESSION.headers["User-Agent"] = "Mozilla/5.0 (compatible; HikingTracker/1.0)"

STAGE_RE = re.compile(
    r'<strong>Etappe\s+(\d+)\s*\|\s*([^|<]+?)\s*–\s*([^|<]+?)\s*\|\s*([\d,\.]+)\s*Km</strong>',
    re.IGNORECASE,
)


def load_hikes():
    return json.loads(HIKES_FILE.read_text()) if HIKES_FILE.exists() else []


def save_hikes(routes):
    HIKES_FILE.write_text(json.dumps(routes, ensure_ascii=False, indent=2))


def fetch_stages(slug):
    url = f"https://wege.albverein.net/wanderwege/hauptwanderwege/{slug}/etappenbeschreibung-{slug}/"
    resp = SESSION.get(url, timeout=30)
    resp.raise_for_status()
    html = unescape(resp.text)
    stages = STAGE_RE.findall(html)
    return url, stages


def parse_km(s):
    return round(float(s.replace(",", ".")), 1)


def main():
    p = argparse.ArgumentParser(description="Scrape Albverein Hauptwanderwege")
    p.add_argument("--only",    help="slug to scrape: hw1, hw2, hw5, hw7")
    p.add_argument("--refresh", action="store_true", help="re-fetch even if already cached")
    args = p.parse_args()

    trails = [t for t in TRAILS if not args.only or t["slug"] == args.only]
    if not trails:
        print(f"Unknown slug '{args.only}'. Choose from: {', '.join(t['slug'] for t in TRAILS)}")
        sys.exit(1)

    routes = load_hikes()
    index = {(r["land"], r["route_id"]): i for i, r in enumerate(routes)}

    for trail in trails:
        key = ("de-hike", trail["route_id"])
        if key in index and not args.refresh:
            print(f"{trail['slug'].upper()}: already cached (use --refresh to re-fetch)")
            continue

        print(f"Fetching {trail['slug'].upper()} — {trail['name']} ...", flush=True)
        try:
            url, raw_stages = fetch_stages(trail["slug"])
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

        if not raw_stages:
            print(f"  ERROR: no stages found at {url}")
            continue

        stages = []
        for nr_s, start, end, km_s in raw_stages:
            stages.append({
                "stage_nr":        int(nr_s),
                "start_name":      start.strip(),
                "end_name":        end.strip(),
                "via":             None,
                "dist_km":         parse_km(km_s),
                "elev_up":         None,
                "elev_down":       None,
                "duration_hrs":    None,
                "difficulty":      None,
                "description":     None,
                "arrival_stations": [],
                "sbb_times":       {},
                "_source_url":     url,
            })

        total_km = round(sum(s["dist_km"] for s in stages), 1)
        print(f"  {len(stages)} stages, {total_km} km total")

        route = {
            "route_id":   trail["route_id"],
            "route_type": "regional",
            "land":       "de-hike",
            "name":       trail["name"],
            "description": None,
            "start":      trail["start"],
            "end":        trail["end"],
            "total_km":   total_km,
            "stages":     stages,
        }

        if key in index:
            routes[index[key]] = route
            print(f"  Updated existing route")
        else:
            routes.append(route)
            print(f"  Added route_id={trail['route_id']}")

        save_hikes(routes)
        time.sleep(DELAY)

    print("\nDone.")


if __name__ == "__main__":
    main()
