#!/usr/bin/env python3
"""
Alta Via 1 Scraper (Dolomites, Italy)
======================================
Fetches the 11 stages of the Alta Via 1 from altavia1dolomites.com and
merges them into hikes.json with land="it-hike", route_id=1,
route_type="national".

Usage:
    pip3 install requests beautifulsoup4
    python3 scraper_av1.py              # fetch all 11 stages
    python3 scraper_av1.py --refresh    # re-fetch even if already cached

Push to Supabase via the shared importer:
    python3 scraper.py --import

Notes
-----
- Source: https://altavia1dolomites.com/alta-via-1-stages/
  All 11 stages are on a single page — no individual stage URLs.
- Fields available per stage: distance, ascent (elev_up), descent (elev_down),
  non-stop duration (duration_hrs). No difficulty ratings on the site.
- Stage headings use a dash separator: "lago di braies – rifugio biella"
- sbb_times={}, cantons=[], arrival_stations=[] — ignored by the UI.
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

ROUTE_URL  = "https://altavia1dolomites.com/alta-via-1-stages/"
DELAY      = 1.0

ROUTE_ID   = 1
LAND       = "it-hike"
ROUTE_TYPE = "national"
ROUTE_NAME = "Alta Via 1"
ROUTE_DESC = (
    "The Alta Via 1 traverses 125 km through the heart of the Dolomites, "
    "from Lago di Braies in the north to the bus stop at Pissa near Belluno "
    "in the south. Eleven stages link iconic rifugios across high passes, "
    "rocky plateaus, and dramatic alpine scenery — a UNESCO World Heritage "
    "landscape of towering limestone peaks."
)

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": "https://altavia1dolomites.com/",
})

# Heading separators: "lago di braies – rifugio biella" or "stage 3 – name to name"
_STAGE_HEADING_RE = re.compile(r"stage\s+(\d+)", re.IGNORECASE)
_SEPARATOR_RE     = re.compile(r"\s+[–—-]\s+")

# Field regexes (from page text)
_DIST_RE     = re.compile(r"distance:\s*([\d.]+)\s*km", re.IGNORECASE)
_ASCENT_RE   = re.compile(r"ascent:\s*([\d,]+)\s*m", re.IGNORECASE)
_DESCENT_RE  = re.compile(r"descent:\s*([\d,]+)\s*m", re.IGNORECASE)
_TIME_RE     = re.compile(r"time:\s*([\d.]+)\s*hours?\s*non.?stop", re.IGNORECASE)


def _parse_int(s):
    """Parse '1,150' or '870' → int."""
    return int(s.replace(",", "").replace(".", ""))


def fetch(url):
    for attempt in range(2):
        try:
            r = SESSION.get(url, timeout=15)
            r.raise_for_status()
            return r.text
        except Exception as e:
            if attempt == 0:
                print(f"  [warn] {e}, retrying in 5s")
                time.sleep(5)
                continue
            print(f"  [error] giving up: {e}")
            return None
    return None


def parse_stages(html):
    """
    Parse all 11 stages from the single-page overview.
    Stages are delimited by heading elements (h2/h3/h4) whose text is
    exactly 'stage N' (case-insensitive). The name line follows immediately
    as the next non-empty text sibling.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Each stage lives in a wp-block-ugb-columns div.
    # Its full text looks like:
    #   "stage 1 lago di braies – rifugio biella distance:  6km ascent: 870m ..."
    _STAGE_BLOCK_RE = re.compile(r"^\s*stage\s+(\d+)\b", re.IGNORECASE)
    _STAGE_H2_RE    = re.compile(r"^\s*stage\s+(\d+)\s*[–—-]?\s*(.+)?$", re.IGNORECASE)

    # Find all ugb-columns blocks that begin with "stage N"
    blocks = soup.find_all("div", class_=re.compile(r"wp-block-ugb-columns"))
    stage_blocks = []
    for block in blocks:
        t = block.get_text(" ", strip=True)
        if _STAGE_BLOCK_RE.match(t):
            stage_blocks.append(block)

    stages = []
    for block in stage_blocks:
        section_text = block.get_text(" ", strip=True)

        # Parse stage number and name from h2 inside the block
        h2 = block.find("h2")
        heading_text = h2.get_text(" ", strip=True) if h2 else section_text
        m = _STAGE_H2_RE.match(heading_text)
        stage_nr = int(m.group(1)) if m else len(stages) + 1
        name_str = (m.group(2) or "").strip() if m else ""

        # Parse start/end from name: "lago di braies – rifugio biella"
        # or "rifugio biella to rifugio fanes"
        if _SEPARATOR_RE.search(name_str):
            parts_name = _SEPARATOR_RE.split(name_str, maxsplit=1)
            start_name = parts_name[0].strip().title()
            end_name   = parts_name[1].strip().title()
        elif re.search(r"\bto\b", name_str, re.I):
            parts_name = re.split(r"\s+to\s+", name_str, maxsplit=1, flags=re.I)
            start_name = parts_name[0].strip().title()
            end_name   = parts_name[1].strip().title()
        else:
            start_name = end_name = name_str.title() or f"Stage {stage_nr}"

        # Parse metric fields
        dist_m  = _DIST_RE.search(section_text)
        asc_m   = _ASCENT_RE.search(section_text)
        desc_m  = _DESCENT_RE.search(section_text)
        time_m  = _TIME_RE.search(section_text)

        dist_km      = round(float(dist_m.group(1)), 1) if dist_m else None
        elev_up      = _parse_int(asc_m.group(1))  if asc_m  else None
        elev_down    = _parse_int(desc_m.group(1)) if desc_m else None
        duration_hrs = float(time_m.group(1))       if time_m else None

        # Description: remove metric labels and name from block text
        desc_text = re.sub(
            r"stage\s+\d+\s*|"
            r"(distance|ascent|descent|time|expected time|lunch)\s*:\s*[^\n]*",
            " ", section_text, flags=re.IGNORECASE
        ).strip()
        desc_text = re.sub(r"\s+", " ", desc_text).strip()
        # Remove the start/end names from description
        desc_text = re.sub(re.escape(name_str), "", desc_text, flags=re.IGNORECASE).strip()
        desc_lines = [desc_text] if len(desc_text) > 30 else []

        stages.append({
            "stage_nr":         stage_nr,
            "start_name":       start_name,
            "end_name":         end_name,
            "via":              None,
            "dist_km":          dist_km,
            "elev_up":          elev_up,
            "elev_down":        elev_down,
            "duration_hrs":     duration_hrs,
            "difficulty":       None,
            "description":      "\n\n".join(desc_lines),
            "cantons":          [],
            "arrival_stations": [],
            "sbb_times":        {},
        })

    return stages


def main():
    p = argparse.ArgumentParser(description="Scrape Alta Via 1 (Dolomites) stages")
    p.add_argument("--refresh", action="store_true",
                   help="Re-fetch even if stages are already cached")
    args = p.parse_args()

    existing = load_existing()
    key   = (LAND, ROUTE_TYPE, ROUTE_ID)
    route = existing.get(key) or {
        "route_id":    ROUTE_ID,
        "route_type":  ROUTE_TYPE,
        "land":        LAND,
        "name":        ROUTE_NAME,
        "description": ROUTE_DESC,
        "start":       "Lago di Braies",
        "end":         "Belluno",
        "total_km":    125,
        "stages":      [],
    }
    existing[key] = route

    if route.get("stages") and not args.refresh:
        print(f"Already have {len(route['stages'])} cached stages. Use --refresh to re-fetch.")
        save(list(existing.values()))
        return

    print(f"Fetching {ROUTE_URL}")
    time.sleep(DELAY)
    html = fetch(ROUTE_URL)
    if not html:
        print("Could not fetch route page. Aborting.")
        sys.exit(1)

    stages = parse_stages(html)
    if not stages:
        print("No stages parsed. The page layout may have changed.")
        sys.exit(1)

    expected = 11
    if len(stages) != expected:
        print(f"  [warn] expected {expected} stages, got {len(stages)}")

    for s in stages:
        print(
            f"  [{s['stage_nr']:2d}/{len(stages)}] {s['start_name']} → {s['end_name']} "
            f"({s['dist_km']} km, ↑{s['elev_up']}m ↓{s['elev_down']}m, {s['duration_hrs']}h)"
        )

    route["stages"]   = stages
    route["start"]    = stages[0]["start_name"]
    route["end"]      = stages[-1]["end_name"]
    route["total_km"] = round(sum(s["dist_km"] for s in stages if s.get("dist_km")), 1) or 125

    save(list(existing.values()))
    print(f"\nDone. {len(stages)} stages.")


if __name__ == "__main__":
    main()
