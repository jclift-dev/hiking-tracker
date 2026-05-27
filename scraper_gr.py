#!/usr/bin/env python3
"""
GR Trails Scraper (France)
==========================
Scrapes stage data for French GR long-distance trails and merges them
into hikes.json (land="fr-hike").

Trails:
  gr65  Via Podiensis / GR65 (Le Puy-en-Velay → St-Jean-Pied-de-Port)
        Source: podiensis.com — index table + per-stage pages
        route_id=2, 32 stages

  gr70  GR70 Chemin de Stevenson (Le Puy-en-Velay → Alès)
        Source: chamina-voyages.com — single-page table
        route_id=3, 13 stages

  gr20  Distance backfill only (existing fr-hike/route_id=1)
        Source: thepostrace.com blog post
        Only fills dist_km where currently null — does not touch
        existing elevation data or stage names.
        Note: thepostrace uses 15 stages; the existing le-gr20.fr data
        has 16 (different intermediate waypoints in the southern section).
        Backfill is sequential, best-effort for stages 1–15.

Usage:
    pip3 install requests beautifulsoup4
    python3 scraper_gr.py              # all trails
    python3 scraper_gr.py --only gr65  # one trail only
    python3 scraper_gr.py --refresh-trail gr65  # re-fetch even if cached
    python3 scraper_gr.py --limit 3    # smoke test: first N stages only

Push to Supabase:
    python3 scraper.py --import

Deferred — cross-border or foreign-land trails requiring a Supabase
CHECK constraint update and possibly new land= values before adding:
    gr5   GR5 Grande Traversée des Alpes (FR/CH) — no free table source found
    gr11  GR11 Traverse of the Pyrenees  (ES)    — Spanish trail, land="es-hike"
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
# GR_TRAILS catalog
# ---------------------------------------------------------------------------

GR_TRAILS = [
    {
        "slug":        "gr65",
        "land":        "fr-hike",
        "route_id":    2,
        "route_type":  "national",
        "name":        "GR65 Via Podiensis",
        "description": (
            "The GR65 Via Podiensis runs 750 km across France from Le Puy-en-Velay "
            "in the Auvergne to Saint-Jean-Pied-de-Port at the foot of the Pyrenees, "
            "one of the four great pilgrim roads to Santiago de Compostela. Over 32 "
            "stages it traverses the Aubrac plateau, the valleys of the Lot and the "
            "Célé, the bastide towns of Quercy and the Gers countryside, passing "
            "through Conques, Figeac, Cahors and Moissac."
        ),
        "start":    "Le Puy-en-Velay",
        "end":      "Saint-Jean-Pied-de-Port",
        "total_km": 751,
    },
    {
        "slug":        "gr70",
        "land":        "fr-hike",
        "route_id":    3,
        "route_type":  "national",
        "name":        "GR70 Chemin de Stevenson",
        "description": (
            "The GR70 Chemin de Stevenson follows the 1878 journey of Robert Louis "
            "Stevenson and his donkey Modestine across the Massif Central, covering "
            "270 km in 13 stages from Le Puy-en-Velay to Alès. The route traverses "
            "the Velay, the Margeride, the Gévaudan and the Cévennes, passing through "
            "La Bastide-Puylaurent, Pont-de-Montvert and Florac before descending to "
            "the Cévennes foothills. The classic endpoint is Saint-Jean-du-Gard; "
            "the final stage to Alès is optional."
        ),
        "start":    "Le Puy-en-Velay",
        "end":      "Alès",
        "total_km": 270,
    },
]

# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
})

DELAY = 1.5  # seconds between requests — small independent sites, be polite


def fetch(url, label=""):
    for attempt in range(2):
        try:
            r = SESSION.get(url, timeout=15)
            if r.status_code == 404:
                print(f"  [warn] 404 — {label or url}")
                return None
            if r.status_code >= 500 and attempt == 0:
                print(f"  [warn] {r.status_code} — {label}, retrying in 5s…")
                time.sleep(5)
                continue
            r.raise_for_status()
            return r.text
        except Exception as e:
            if attempt == 0:
                print(f"  [warn] {e}, retrying in 5s")
                time.sleep(5)
                continue
            print(f"  [error] {label}: {e}")
            return None
    return None


# ---------------------------------------------------------------------------
# Field parsers
# ---------------------------------------------------------------------------

def _km(s):
    """'23,60 km' → 23.6"""
    m = re.search(r"([\d.,]+)\s*km", s or "", re.I)
    return round(float(m.group(1).replace(",", ".")), 1) if m else None


def _m(s):
    """'1 210 m' → 1210  |  '620 m' → 620"""
    m = re.search(r"([\d\s]+)\s*m\b", s or "", re.I)
    return int(re.sub(r"\s", "", m.group(1))) if m else None


def _hrs(s):
    """'6h00' → 6.0  |  '7h30' → 7.5  |  '6h' → 6.0"""
    m = re.match(r"(\d+)h(\d+)?", (s or "").strip(), re.I)
    if not m:
        return None
    return round(int(m.group(1)) + int(m.group(2) or 0) / 60, 2)


_DIFF_FR = {
    "facile":        "easy",
    "aisée":         "easy",
    "moyenne":       "moderate",
    "difficile":     "difficult",
    "très difficile":"demanding",
}


def _difficulty(s):
    return _DIFF_FR.get((s or "").strip().lower())


def _route_skeleton(trail):
    """Return a fresh route dict (no stages) from a catalog entry."""
    return {
        "route_id":    trail["route_id"],
        "route_type":  trail["route_type"],
        "land":        trail["land"],
        "name":        trail["name"],
        "description": trail["description"],
        "start":       trail["start"],
        "end":         trail["end"],
        "total_km":    trail["total_km"],
        "stages":      [],
    }


# ---------------------------------------------------------------------------
# GR65 — podiensis.com
# ---------------------------------------------------------------------------

_PODIENSIS_BASE  = "https://www.podiensis.com"
_PODIENSIS_INDEX = f"{_PODIENSIS_BASE}/les-etapes"


def _parse_gr65_index(html):
    """Parse the stage index table → list of (nr, start, end, dist_km, url)."""
    soup  = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return []
    stages = []
    for row in table.find_all("tr"):
        cols = row.find_all(["td", "th"])
        if not cols or cols[0].name == "th":
            continue
        cells = [c.get_text(strip=True) for c in cols]
        if len(cells) < 4:
            continue
        try:
            nr = int(cells[0])
        except ValueError:
            continue
        a    = row.find("a", href=True)
        url  = f"{_PODIENSIS_BASE}/{a['href']}" if a else None
        stages.append((nr, cells[1], cells[2], _km(cells[3]), url))
    return stages


def _parse_gr65_stage(html, url):
    """Parse an individual podiensis.com stage page.

    Table layout (row, col):
      0: Distance | <val> | Durée        | <val>
      1: Dén. pos | <val> | Dén. nég.    | <val>
      2: Pt haut  | <val> | Pt bas       | <val>
      3: Difficulté| <val>| …
    """
    soup  = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return {}
    rows = table.find_all("tr")

    def cell(r, c):
        if r >= len(rows):
            return ""
        cols = rows[r].find_all(["td", "th"])
        return cols[c].get_text(strip=True) if c < len(cols) else ""

    return {
        "dist_km":      _km(cell(0, 1)),
        "duration_hrs": _hrs(cell(0, 3)),
        "elev_up":      _m(cell(1, 1)),
        "elev_down":    _m(cell(1, 3)),
        "difficulty":   _difficulty(cell(3, 1)),
        "_url":         url,
    }


def scrape_gr65(trail, existing, args):
    key   = (trail["land"], trail["route_type"], trail["route_id"])
    route = existing.get(key) or _route_skeleton(trail)
    existing[key] = route

    refresh       = trail["slug"] in (args.refresh_trail or [])
    cached_by_url = {s["_url"]: s for s in route.get("stages", []) if s.get("_url")}

    print(f"Fetching GR65 index: {_PODIENSIS_INDEX}")
    time.sleep(DELAY)
    index_html = fetch(_PODIENSIS_INDEX, "GR65 index")
    if not index_html:
        print("Could not fetch GR65 index. Aborting.")
        return

    index_rows = _parse_gr65_index(index_html)
    if not index_rows:
        print("No stages found in GR65 index table.")
        return

    expected = 32
    print(f"Found {len(index_rows)} stage(s)"
          + ("" if len(index_rows) == expected else f" (expected {expected})"))

    if args.limit:
        index_rows = index_rows[:args.limit]
        print(f"  (limited to first {len(index_rows)})")

    new_stages = []
    try:
        for nr, start, end, dist_idx, url in index_rows:
            cached = cached_by_url.get(url)
            if cached and not refresh:
                cached["stage_nr"] = nr
                new_stages.append(cached)
                print(f"  [{nr:2d}/{len(index_rows)}] cached: {start} → {end}")
                continue

            time.sleep(DELAY)
            print(f"  [{nr:2d}/{len(index_rows)}] {start} → {end} … ", end="", flush=True)

            if not url:
                new_stages.append({
                    "stage_nr": nr, "start_name": start, "end_name": end,
                    "via": None, "dist_km": dist_idx,
                    "elev_up": None, "elev_down": None, "duration_hrs": None,
                    "difficulty": None, "description": "",
                    "cantons": [], "arrival_stations": [], "sbb_times": {},
                })
                print("no URL, skipped detail")
                continue

            html = fetch(url, f"stage {nr}")
            if not html:
                new_stages.append({
                    "stage_nr": nr, "start_name": start, "end_name": end,
                    "via": None, "dist_km": dist_idx,
                    "elev_up": None, "elev_down": None, "duration_hrs": None,
                    "difficulty": None, "description": "",
                    "cantons": [], "arrival_stations": [], "sbb_times": {},
                })
                print("fetch failed")
                continue

            d = _parse_gr65_stage(html, url)
            new_stages.append({
                "stage_nr":         nr,
                "start_name":       start,
                "end_name":         end,
                "via":              None,
                "dist_km":          d.get("dist_km") or dist_idx,
                "elev_up":          d.get("elev_up"),
                "elev_down":        d.get("elev_down"),
                "duration_hrs":     d.get("duration_hrs"),
                "difficulty":       d.get("difficulty"),
                "description":      "",
                "cantons":          [],
                "arrival_stations": [],
                "sbb_times":        {},
                "_url":             url,
            })
            print(
                f"{d.get('dist_km')} km "
                f"↑{d.get('elev_up')}m ↓{d.get('elev_down')}m "
                f"{d.get('duration_hrs')}h ({d.get('difficulty')})"
            )

    except KeyboardInterrupt:
        print("\nInterrupted — saving progress…")

    route["stages"]   = new_stages
    route["start"]    = new_stages[0]["start_name"] if new_stages else trail["start"]
    route["end"]      = new_stages[-1]["end_name"]  if new_stages else trail["end"]
    route["total_km"] = round(
        sum(s["dist_km"] for s in new_stages if s.get("dist_km")), 1
    ) or trail["total_km"]
    print(f"  → GR65: {len(new_stages)} stages, {route['total_km']} km")


# ---------------------------------------------------------------------------
# GR70 — chamina-voyages.com
# ---------------------------------------------------------------------------

_CHAMINA_GR70_URL = (
    "https://www.chamina-voyages.com/les-etapes-chemin-de-stevenson-gr70"
)


def scrape_gr70(trail, existing, args):
    key   = (trail["land"], trail["route_type"], trail["route_id"])
    route = existing.get(key) or _route_skeleton(trail)
    existing[key] = route

    refresh = trail["slug"] in (args.refresh_trail or [])

    if route.get("stages") and not refresh:
        print(f"GR70: already have {len(route['stages'])} stages — "
              "use --refresh-trail gr70 to re-fetch")
        return

    print(f"Fetching GR70: {_CHAMINA_GR70_URL}")
    time.sleep(DELAY)
    html = fetch(_CHAMINA_GR70_URL, "GR70")
    if not html:
        print("Could not fetch GR70 page.")
        return

    soup  = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        print("GR70: no table found.")
        return

    stages, nr = [], 0
    for row in table.find_all("tr"):
        cols = row.find_all(["td", "th"])
        if len(cols) < 4:
            continue
        name = cols[0].get_text(strip=True)
        # Skip header (empty or "Distance") and total row
        if not name or "total" in name.lower() or cols[1].name == "th":
            continue

        # "Puy-en-Velay > Monastier-sur-Gazeille" → start / end
        if ">" in name:
            start, _, end = name.partition(">")
            start, end = start.strip(), end.strip()
        else:
            start = end = name
        # Strip "(optionnel)" qualifier
        end = re.sub(r"\s*\(optionnel\)\s*", "", end, flags=re.I).strip()
        # Normalise city name variants from this source
        if start == "Puy-en-Velay":
            start = "Le Puy-en-Velay"
        if end == "Puy-en-Velay":
            end = "Le Puy-en-Velay"

        dist = _km(cols[1].get_text(strip=True))
        up   = _m(cols[2].get_text(strip=True))
        down = _m(cols[3].get_text(strip=True))

        # Guard against total row slipping through
        if dist is None and up is None:
            continue

        nr += 1
        stages.append({
            "stage_nr":         nr,
            "start_name":       start,
            "end_name":         end,
            "via":              None,
            "dist_km":          dist,
            "elev_up":          up,
            "elev_down":        down,
            "duration_hrs":     None,   # not published on this page
            "difficulty":       None,
            "description":      "",
            "cantons":          [],
            "arrival_stations": [],
            "sbb_times":        {},
        })
        print(f"  [{nr:2d}] {start} → {end}: {dist} km ↑{up}m ↓{down}m")

    if args.limit:
        stages = stages[:args.limit]

    route["stages"]   = stages
    route["start"]    = stages[0]["start_name"] if stages else trail["start"]
    route["end"]      = stages[-1]["end_name"]  if stages else trail["end"]
    route["total_km"] = round(
        sum(s["dist_km"] for s in stages if s.get("dist_km")), 1
    ) or trail["total_km"]
    print(f"  → GR70: {len(stages)} stages, {route['total_km']} km")


# ---------------------------------------------------------------------------
# GR20 distance backfill — thepostrace.com
# ---------------------------------------------------------------------------

_THEPOSTRACE_GR20 = (
    "https://thepostrace.com/en/blog/"
    "gr20-les-etapes-distance-et-denivele-de-la-traversee-de-la-corse/"
)


def backfill_gr20_distances(existing, args):
    """
    Backfill dist_km for existing GR20 stages from a secondary source.

    thepostrace.com lists 15 stages; the existing le-gr20.fr data has 16
    (different intermediate waypoints in the southern section, stages 11–16).
    Stages 1–10 share the same waypoints on both sources; stages 11–15 are
    approximately sequential. Stage 16 (Bavella→Conca) remains null.
    """
    key   = ("fr-hike", "national", 1)
    route = existing.get(key)
    if not route:
        print("GR20: not in hikes.json — skipping backfill")
        return

    stages  = route.get("stages", [])
    missing = sum(1 for s in stages if s.get("dist_km") is None)
    refresh = "gr20" in (args.refresh_trail or [])

    if missing == 0 and not refresh:
        print(f"GR20: all {len(stages)} stages already have dist_km — skipping")
        return

    print(f"GR20: fetching distances from thepostrace.com "
          f"({missing}/{len(stages)} stages need dist_km)")
    time.sleep(DELAY)
    html = fetch(_THEPOSTRACE_GR20, "GR20 distances")
    if not html:
        print("GR20: fetch failed — skipping backfill")
        return

    soup  = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        print("GR20: no table found on thepostrace page")
        return

    # Table header: Stage | Ascent (m) | Negative ascent (m) | Distance (km)
    tp_rows = []
    for row in table.find_all("tr"):
        cols = row.find_all(["td", "th"])
        if not cols or cols[0].name == "th":
            continue
        m = re.search(r"([\d.]+)", cols[3].get_text(strip=True))
        tp_rows.append((cols[0].get_text(strip=True), float(m.group(1)) if m else None))

    print(f"  thepostrace: {len(tp_rows)} stages | hikes.json: {len(stages)} stages")

    count = 0
    for i, (tp_name, dist) in enumerate(tp_rows):
        if i >= len(stages):
            break
        stage = stages[i]
        if stage.get("dist_km") is None or refresh:
            stage["dist_km"] = dist
            count += 1
            print(f"  [{i+1:2d}] {stage['start_name']} → {stage['end_name']}: "
                  f"{dist} km  (source: {tp_name})")

    # Only update total_km if every stage now has a distance; otherwise the
    # partial sum would be misleadingly low (stage 16 Bavella→Conca has no
    # match in the 15-stage thepostrace source and stays null).
    if all(s.get("dist_km") for s in stages):
        route["total_km"] = round(sum(s["dist_km"] for s in stages), 1)
    print(f"  → GR20: backfilled {count} stages, total_km={route['total_km']} km")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="Scrape French GR trail stages")
    p.add_argument(
        "--only", metavar="SLUG",
        help="Process only this trail (gr65 | gr70 | gr20)",
    )
    p.add_argument(
        "--refresh-trail", metavar="SLUG", action="append",
        help="Re-fetch this trail even if cached (repeatable)",
    )
    p.add_argument(
        "--limit", type=int, default=None,
        help="Smoke test: process at most N stages per trail",
    )
    args = p.parse_args()

    existing = load_existing()

    run_gr20   = not args.only or args.only == "gr20"
    run_trails = [t for t in GR_TRAILS
                  if not args.only or t["slug"] == args.only]

    for trail in run_trails:
        print(f"\n=== {trail['name']} ({trail['slug']}) ===")
        if trail["slug"] == "gr65":
            scrape_gr65(trail, existing, args)
        elif trail["slug"] == "gr70":
            scrape_gr70(trail, existing, args)

    if run_gr20:
        print("\n=== GR20 distance backfill ===")
        backfill_gr20_distances(existing, args)

    save(list(existing.values()))
    print("\nDone.")


if __name__ == "__main__":
    main()
