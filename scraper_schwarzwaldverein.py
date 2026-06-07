"""
scraper_schwarzwaldverein.py — Schwarzwaldverein Fernwanderwege

Scrapes stage data for long-distance trails managed by Schwarzwaldverein e.V.
from https://www.schwarzwaldverein.de/natursport-und-wege/fernwanderwege/{slug}/

Usage:
    python3 scraper_schwarzwaldverein.py              # all trails
    python3 scraper_schwarzwaldverein.py --only mittelweg
    python3 scraper_schwarzwaldverein.py --refresh    # re-fetch all
    python3 scraper_schwarzwaldverein.py --limit 3    # first N trails
    python3 scraper.py --import                       # push to Supabase
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Trail catalog
# All trails are land="de-hike". route_id continues from scraper_osm.py (max=9).
# ---------------------------------------------------------------------------

TRAILS = [
    # (slug, display_name, route_id, route_type, description)
    # route_id 2: Westweg replaces the truncated OSM version (OSM 62900 stops at Titisee; Schwarzwaldverein has all 11 stages to Basel)
    ("westweg",                         "Westweg",                               2,  "national", "The Black Forest's main north-south trail from Pforzheim to Basel (western variant)"),
    ("mittelweg",                       "Mittelweg",                             10, "national", "North-south trail through the Black Forest from Pforzheim to Waldshut"),
    ("ostweg",                          "Ostweg",                                11, "national", "Eastern route through the Black Forest from Pforzheim to Schaffhausen"),
    ("querweg-freiburg-bodensee",       "Querweg Freiburg–Bodensee",             12, "national", "East-west traverse from Freiburg to Lake Constance"),
    ("markgraefler-wiiwegli",           "Markgräfler Wiiwegli",                  13, "national", "Wine trail through the Markgräflerland from Freiburg to Grenzach-Wyhlen"),
    ("schluchtensteig",                 "Schluchtensteig",                       14, "national", "Gorge trail through southern Black Forest from Stühlingen to Wehr"),
    ("kandel-hoehenweg",                "Kandelhöhenweg",                        15, "national", "Ridge trail via the Kandel peak from Freiburg to Oberkirch"),
    ("schwarzwald-jura-bodensee",       "Schwarzwald-Jura-Bodensee-Weg",        16, "national", "Trail linking the Black Forest, Jura plateau, and Lake Constance"),
    ("zweitaelersteig",                 "ZweiTälerSteig",                        17, "national", "Circular trail through the Elz and Simons valleys from Waldkirch"),
    ("breisgauer-weinweg",              "Breisgauer Weinweg",                    18, "national", "Wine trail through the Breisgau region from Freiburg to Lahr"),
    ("gaeurandweg",                     "Gäurandweg",                            19, "national", "Trail along the northern Black Forest escarpment from Mühlacker to Freudenstadt"),
    ("hochrhein-hoehenweg",             "Hochrhein-Höhenweg",                    20, "national", "Trail along the High Rhine from Basel to Schaffhausen"),
    ("interregio-wanderweg",            "Interregio-Wanderweg",                  21, "national", "Cross-border trail linking Germany, Switzerland, and France (Neuenburg–Mulhouse loop)"),
    ("murgleiter",                      "Murgleiter",                            22, "national", "Trail above the Murg valley from Gaggenau to Schliffkopf"),
    ("ortenauer-weinpfad",              "Ortenauer Weinpfad",                    23, "national", "Wine trail through the Ortenau region from Gernsbach to Diersburg"),
    ("querweg-gengenbach-alpirsbach",   "Querweg Gengenbach–Alpirsbach",         24, "national", "Short east-west traverse from Gengenbach to Alpirsbach"),
    ("querweg-lahr-rottweil",           "Querweg Lahr–Rottweil",                 25, "national", "East-west traverse from Lahr to Rottweil"),
    ("querweg-schwarzwald-kaiserstuhl-rhein", "Querweg Schwarzwald–Kaiserstuhl–Rhein", 26, "national", "Cross-Black Forest traverse from Donaueschingen to Breisach"),
    ("renchtalsteig",                   "Renchtalsteig",                         27, "national", "Trail along the Rench valley and ridges from Bottenau to Schauenburg"),
    ("rheinauenweg",                    "Rheinauenweg",                          28, "national", "Flat trail along the Rhine floodplain from Kehl to Weil am Rhein"),
    ("schwarzwald-nordrandweg",         "Schwarzwald-Nordrandweg",               29, "national", "Northern Black Forest edge trail from Mühlacker to Durlach"),
    ("wasserweltensteig",               "Wasserweltensteig",                     30, "national", "Water-themed trail from Triberg to Neuhausen am Rheinfall"),
    ("hotzenwald-querweg",              "Hotzenwald-Querweg",                    31, "national", "Short traverse through the Hotzenwald from Schopfheim to Waldshut"),
]

BASE_URL = "https://www.schwarzwaldverein.de/natursport-und-wege/fernwanderwege/{slug}/"
HIKES_JSON = Path("hikes.json")
DELAY = 2.0

SESSION = requests.Session()
SESSION.headers["User-Agent"] = "HikingTracker/1.0 (https://github.com/jclift-dev/hiking-tracker)"

# Regex for stage lines: "N[a/b]?. Etappe [A/B]?: Start – End / X km"
# or "N[a/b]?. Etappe [A/B]?: Start – End X km" (no slash)
STAGE_PAT = re.compile(
    r'^(\d+[ab]?)\.\s*Etappe\s*(?:[ABab]:?\s*)?:?\s*'  # number + "Etappe"
    r'(.+?)\s*'                                           # content
    r'(?:/\s*)?(\d+(?:[,.]\d+)?)\s*km\s*$',             # distance
    re.UNICODE | re.IGNORECASE,
)

DIFF_MAP = {
    "leicht": "easy",
    "mittel": "moderate",
    "schwer": "difficult",
}


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------

def load_existing():
    if not HIKES_JSON.exists():
        return {}
    data = json.loads(HIKES_JSON.read_text(encoding="utf-8"))
    return {(r["land"], r["route_type"], r["route_id"]): r for r in data}


def save(routes):
    HIKES_JSON.write_text(
        json.dumps(routes, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  → Saved {len(routes)} routes to hikes.json")


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_dist(raw):
    """Parse German decimal distance string '22,5' or '22.5' → float."""
    try:
        return round(float(raw.replace(",", ".")), 1)
    except ValueError:
        return None


def scrape_trail(slug, display_name):
    """
    Fetch and parse a trail page. Returns a dict with stages, or None on failure.
    """
    url = BASE_URL.format(slug=slug)
    try:
        resp = SESSION.get(url, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  Fetch failed: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # Extract all icon-list text items
    items = [
        el.get_text(" ", strip=True)
        for el in soup.select("span.elementor-icon-list-text")
    ]

    stages = []
    seen_stage_nrs = set()

    for item in items:
        m = STAGE_PAT.match(item)
        if not m:
            continue
        raw_nr, content, dist_raw = m.group(1), m.group(2).strip(), m.group(3)

        # Canonical stage number: strip trailing a/b
        canonical_nr = int(re.sub(r"[ab]$", "", raw_nr, flags=re.IGNORECASE))
        if canonical_nr in seen_stage_nrs:
            continue  # skip second variant
        seen_stage_nrs.add(canonical_nr)

        dist_km = parse_dist(dist_raw)

        # Split on " – "/" — " (en/em-dash with leading space) or " -" (hyphen with leading space)
        # Requires at least a leading space to avoid splitting hyphenated place names (VS-Villingen)
        parts = re.split(r"\s+[–—]\s*|\s+-\s*", content, maxsplit=1)
        start_name = parts[0].strip() if parts else content
        end_name   = parts[1].strip() if len(parts) > 1 else ""

        # Strip redundant "Etappe " prefix the site occasionally adds to start_name
        start_name = re.sub(r"^Etappe\s+", "", start_name, flags=re.IGNORECASE).strip()

        # Clean trailing slash artefacts (e.g. "Bad Liebenzell / ")
        end_name = re.sub(r"\s*/\s*$", "", end_name).strip()

        stages.append({
            "stage_nr":         canonical_nr,
            "start_name":       start_name,
            "end_name":         end_name,
            "via":              None,
            "dist_km":          dist_km,
            "elev_up":          None,
            "elev_down":        None,
            "duration_hrs":     None,
            "difficulty":       None,
            "description":      None,
            "cantons":          [],
            "arrival_stations": [],
            "sbb_times":        {},
            "_source_slug":     slug,
        })

    # Sort by stage_nr in case parsing order was non-linear
    stages.sort(key=lambda s: s["stage_nr"])

    # Re-number so stage_nr is 1-based and gapless
    for i, s in enumerate(stages, start=1):
        s["stage_nr"] = i

    # Extract route-level summary from items
    total_km   = None
    difficulty = None
    total_elev_up   = None
    total_elev_down = None
    start_place = stages[0]["start_name"] if stages else ""
    end_place   = stages[-1]["end_name"]  if stages else ""

    for item in items:
        # "249 km / 254,5 km" or "246 km" — take first number
        m_km = re.match(r"^(\d+(?:[,.]\d+)?)\s*km", item)
        if m_km and total_km is None and not STAGE_PAT.match(item):
            total_km = parse_dist(m_km.group(1))

        m_diff = re.match(r"^(leicht|mittel|schwer)$", item, re.IGNORECASE)
        if m_diff:
            difficulty = DIFF_MAP.get(m_diff.group(1).lower())

        m_auf = re.match(r"^Aufstieg:\s*([\d.,]+)\s*hm", item)
        if m_auf:
            total_elev_up = int(float(m_auf.group(1).replace(".", "").replace(",", ".")))

        m_ab = re.match(r"^Abstieg:\s*([\d.,]+)\s*hm", item)
        if m_ab:
            total_elev_down = int(float(m_ab.group(1).replace(".", "").replace(",", ".")))

    # Apply route-level difficulty to all stages
    for s in stages:
        s["difficulty"] = difficulty

    return {
        "total_km":   total_km,
        "start":      start_place,
        "end":        end_place,
        "elev_up":    total_elev_up,
        "elev_down":  total_elev_down,
        "difficulty": difficulty,
        "stages":     stages,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    p.add_argument("--only",    default=None, help="Only process this trail slug")
    p.add_argument("--refresh", action="store_true", help="Re-fetch all trails even if cached")
    p.add_argument("--limit",   type=int, default=None, help="Only process first N trails")
    args = p.parse_args()

    existing = load_existing()
    catalog = TRAILS
    if args.only:
        catalog = [t for t in catalog if t[0] == args.only]
        if not catalog:
            print(f"No trail with slug '{args.only}' in catalog.")
            sys.exit(1)
    if args.limit:
        catalog = catalog[:args.limit]

    total_stages = 0

    for slug, display_name, route_id, route_type, description in catalog:
        key = ("de-hike", route_type, route_id)

        if not args.refresh and key in existing:
            n = len(existing[key].get("stages", []))
            print(f"\nSkipping {display_name} — already cached ({n} stages). "
                  f"Use --refresh to re-fetch.")
            total_stages += n
            continue

        print(f"\n  Fetching {display_name} ({slug})...")
        result = scrape_trail(slug, display_name)
        time.sleep(DELAY)

        if not result or not result["stages"]:
            print(f"  No stages found for {display_name}, skipping.")
            continue

        stages = result["stages"]
        n = len(stages)
        print(f"  → {n} stages  ({result['total_km']} km)  diff={result['difficulty']}")
        for s in stages:
            print(f"     [{s['stage_nr']:2d}] {s['start_name']} → {s['end_name']} "
                  f"({s['dist_km']} km)")

        route = {
            "route_id":    route_id,
            "route_type":  route_type,
            "land":        "de-hike",
            "name":        display_name,
            "description": description,
            "start":       result["start"],
            "end":         result["end"],
            "total_km":    result["total_km"],
            "stages":      stages,
        }

        existing[key] = route
        total_stages += n

        save(list(existing.values()))

    print(f"\n{'='*60}")
    print(f"Schwarzwaldverein scrape complete. "
          f"{len(catalog)} trails, {total_stages} stages total.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
