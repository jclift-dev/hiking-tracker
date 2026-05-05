#!/usr/bin/env python3
"""
Malerweg Scraper (Saxon Switzerland, Germany)
===============================================
Fetches the 8 stages of the Malerweg from saechsische-schweiz.de and
merges them into hikes.json with land="de-hike", route_id=1,
route_type="national".

Usage:
    pip3 install requests beautifulsoup4
    python3 scraper_malerweg.py              # fetch all 8 stages
    python3 scraper_malerweg.py --refresh    # re-fetch even if cached
    python3 scraper_malerweg.py --limit 3    # smoke test: first N stages

Push to Supabase:
    python3 scraper.py --import

Notes
-----
- Source: https://www.saechsische-schweiz.de/malerweg/en/plan-your-trip/
  Individual stage pages follow the pattern: .../stages-of-the-malerweg-trail/stage-N
- Data available per stage: distance (km), elev_up (UPHILL), elev_down (DOWNHILL).
  Duration is given as prose ("about three and a half hours") — set to null.
- Start/end names are hardcoded (transport info on stage pages is too
  inconsistent to parse reliably; the route endpoints are stable).
- No Cloudflare protection — plain requests work.
- sbb_times={}, cantons=[], arrival_stations=[] — ignored by UI.
"""

import argparse
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

try:
    from scraper import save, load_existing
except ImportError:
    print("scraper.py not found. Run from the project root.")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE      = "https://www.saechsische-schweiz.de"
STAGE_URL = BASE + "/malerweg/en/plan-your-trip/stages-of-the-malerweg-trail/stage-{n}"
N_STAGES  = 8
DELAY     = 1.0

# Hardcoded stage endpoints — the transport info on each stage page is too
# variable to parse reliably; these names come from the official route map.
STAGE_NAMES = [
    ("Pirna-Liebethal", "Stadt Wehlen"),
    ("Stadt Wehlen",    "Hohnstein"),
    ("Hohnstein",       "Altendorf"),
    ("Goßdorf-Kohlmühle", "Neumannmühle"),
    ("Neumannmühle",    "Schmilka"),
    ("Schmilka",        "Gohrisch"),
    ("Gohrisch",        "Weißig"),
    ("Weißig",          "Pirna"),
]

ROUTE_ID   = 1
LAND       = "de-hike"
ROUTE_TYPE = "national"
ROUTE_NAME = "Malerweg"
ROUTE_DESC = (
    "The Malerweg (Painters' Way) is a 116 km circular trail through Saxon "
    "Switzerland — the sandstone canyon landscape that inspired the Romantic "
    "painters Caspar David Friedrich and his contemporaries. Eight stages "
    "wind through the Elbe Sandstone Mountains past the Bastei rock formation, "
    "deep gorges, and the dramatic Schrammsteine ridge."
)

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": BASE + "/malerweg/",
})

# Field patterns on individual stage pages
# Distance: bold "<strong>11,5 km</strong>" or "11.5 km" in a facts section
_DIST_RE   = re.compile(r"([\d][.,\d]*)\s*km\b", re.IGNORECASE)
# Elevation: bold "<strong>110 m altitude difference</strong>" then UPHILL/DOWNHILL
_ELEV_RE   = re.compile(
    r"([\d,]+)\s*m\s+altitude\s+difference\s+(UPHILL|DOWNHILL)", re.IGNORECASE
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fetch(url, label="page"):
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
                print(f"  [warn] {e}, retrying in 5s")
                time.sleep(5)
                continue
            print(f"  [error] giving up on {label}: {e}")
            return None
    return None


def parse_stage_page(html, stage_nr):
    """
    Parse a single Malerweg stage page.
    Facts use a structured .fact__item layout:
      <span class="fact__number">11,5</span><span class="fact__unit"> km</span>
    with a <p> inside .fact__text describing the value (includes UPHILL/DOWNHILL).
    Start/end names come from the hardcoded STAGE_NAMES list (transport info
    on the page is too inconsistent to parse reliably).
    """
    soup = BeautifulSoup(html, "html.parser")
    start_name, end_name = STAGE_NAMES[stage_nr - 1]

    # --- Metrics from .fact__item elements ---
    dist_km = elev_up = elev_down = duration_hrs = None
    for item in soup.find_all("div", class_="fact__item"):
        num_el  = item.find(class_="fact__number")
        unit_el = item.find(class_="fact__unit")
        text_el = item.find(class_="fact__text")
        if not num_el or not unit_el:
            continue
        num_str  = num_el.get_text(strip=True).replace(",", ".")
        unit_str = unit_el.get_text(" ", strip=True).lower()
        desc_str = text_el.get_text(" ", strip=True).lower() if text_el else ""

        # Unit is usually " km" but stage 2 has just "m" (website bug) —
        # disambiguate from "m altitude" by checking no "altitude" in unit.
        is_km_unit = ("km" in unit_str or unit_str.strip() == "m") and "altitude" not in unit_str
        if is_km_unit and dist_km is None:
            try:
                val = round(float(num_str), 1)
                if 5 <= val <= 50:  # sanity-check: realistic day-stage km range
                    dist_km = val
            except ValueError:
                pass
        elif "hours" in unit_str and duration_hrs is None:
            # "3:30" → 3.5
            if ":" in num_str:
                h, m = num_str.split(":", 1)
                try:
                    duration_hrs = round(int(h) + int(m) / 60, 2)
                except ValueError:
                    pass
            else:
                try:
                    duration_hrs = float(num_str)
                except ValueError:
                    pass
        elif "altitude" in unit_str:
            try:
                val = int(num_str.replace(".", "").replace(",", ""))
            except ValueError:
                continue
            # Check only the first word of the description to avoid
            # false matches when both words appear in a long sentence
            words = desc_str.split()
            first_word = re.sub(r'\W+', '', words[0]) if words else ""
            if first_word == "uphill":
                elev_up = val
            elif first_word == "downhill":
                elev_down = val

    # --- Description: first 2 substantial paragraphs ---
    desc_paras = []
    for p in soup.find_all("p"):
        t = p.get_text(" ", strip=True)
        if len(t) < 60:
            continue
        if re.search(r"cookie|privacy|copyright|newsletter|altitude difference|km.*stage", t, re.I):
            continue
        if re.search(r"UPHILL|DOWNHILL|walking time.*stage|length of \d", t, re.I):
            continue
        desc_paras.append(t)
        if len(desc_paras) >= 2:
            break

    return {
        "stage_nr":         stage_nr,
        "start_name":       start_name,
        "end_name":         end_name,
        "via":              None,
        "dist_km":          dist_km,
        "elev_up":          elev_up,
        "elev_down":        elev_down,
        "duration_hrs":     duration_hrs,
        "difficulty":       None,
        "description":      "\n\n".join(desc_paras),
        "cantons":          [],
        "arrival_stations": [],
        "sbb_times":        {},
        "_stage_n":         stage_nr,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="Scrape Malerweg (Saxon Switzerland) stages")
    p.add_argument("--refresh", action="store_true",
                   help="Re-fetch every stage even if cached")
    p.add_argument("--limit", type=int, default=None,
                   help="Only fetch the first N stages (smoke test)")
    args = p.parse_args()

    existing = load_existing()
    key   = (LAND, ROUTE_TYPE, ROUTE_ID)
    route = existing.get(key) or {
        "route_id":    ROUTE_ID,
        "route_type":  ROUTE_TYPE,
        "land":        LAND,
        "name":        ROUTE_NAME,
        "description": ROUTE_DESC,
        "start":       "Pirna",
        "end":         "Pirna",   # circular trail
        "total_km":    116,
        "stages":      [],
    }
    existing[key] = route

    cached_by_n = {
        s.get("_stage_n"): s
        for s in route.get("stages", [])
        if s.get("_stage_n")
    }

    stage_range = list(range(1, N_STAGES + 1))
    if args.limit:
        stage_range = stage_range[:args.limit]
        print(f"(limited to first {len(stage_range)} stages)")

    new_stages = []
    try:
        for n in stage_range:
            cached = cached_by_n.get(n)
            if cached and not args.refresh:
                new_stages.append(cached)
                print(f"  [{n:2d}/{N_STAGES}] stage {n}: cached")
                continue

            url = STAGE_URL.format(n=n)
            time.sleep(DELAY)
            print(f"  [{n:2d}/{N_STAGES}] fetching stage {n}...", end=" ", flush=True)
            html = fetch(url, f"stage {n}")
            if not html:
                if cached:
                    new_stages.append(cached)
                    print("kept cached")
                else:
                    print("skipped")
                continue

            stage = parse_stage_page(html, n)
            new_stages.append(stage)
            print(
                f"{stage['start_name']} → {stage['end_name']} "
                f"({stage['dist_km']} km, ↑{stage['elev_up']}m ↓{stage['elev_down']}m)"
            )

    except KeyboardInterrupt:
        print("\nInterrupted — saving progress...")

    route["stages"]   = new_stages
    if new_stages:
        route["start"]    = new_stages[0]["start_name"]
        route["end"]      = new_stages[-1]["end_name"]
        total = sum(s["dist_km"] for s in new_stages if s.get("dist_km"))
        route["total_km"] = round(total, 1) or 116

    save(list(existing.values()))
    print(f"\nDone. {len(new_stages)} stages.")


if __name__ == "__main__":
    main()
