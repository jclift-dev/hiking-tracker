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
  Stormarnweg                  (de-hike, route_id=53)  wildganz.com
  Oberlausitzer Bergweg        (de-hike, route_id=54)  oberlausitzer-bergweg.de
  Werra-Burgen-Steig Hessen    (de-hike, route_id=55)  werra-burgen-steig-hessen.de
  König-Ludwig-Weg             (de-hike, route_id=56)  koenig-ludwig-weg.de  [hardcoded — JS-rendered]
  X27 Friedrich-Wilhelm-Grimme-Weg (de-hike, route_id=57)  ich-geh-wandern.de
  Camino de la Frontera        (es-hike, route_id=11)  caminodelafrontera.es
  Grande Rota Peneda-Gerês     (pt-hike, route_id=2)   walkingpenedageres.pt

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
# Stormarnweg — wildganz.com/fernwanderweg/stormarnweg
# ---------------------------------------------------------------------------
# Index page lists all 6 stages: "Etappe N" / km in el-freifeld1 / Start: / Ziel:

STORMARNWEG_URL = "https://www.wildganz.com/fernwanderweg/stormarnweg"
STORMARNWEG_BLOCK_RE = re.compile(
    r'Etappe\s+(\d+)\s*</div>.*?el-freifeld1[^>]*>([\d,.]+\s*km).*?Start:\s*(.*?)</.*?Ziel:\s*(.*?)</',
    re.DOTALL,
)


def scrape_stormarnweg():
    print(f"Fetching {STORMARNWEG_URL} ...", flush=True)
    time.sleep(DELAY)
    html = fetch(STORMARNWEG_URL)
    if not html:
        print("  ERROR: fetch failed")
        return None

    stages = []
    seen = set()
    for m in STORMARNWEG_BLOCK_RE.finditer(html):
        nr = int(m.group(1))
        if nr in seen:
            continue
        seen.add(nr)
        km_raw = re.sub(r'[^\d,.]', '', m.group(2))
        start = re.sub(r'\s+', ' ', m.group(3)).strip()
        end   = re.sub(r'\s+', ' ', m.group(4)).strip()
        stages.append({
            "stage_nr":         nr,
            "start_name":       start,
            "end_name":         end,
            "via":              None,
            "dist_km":          parse_km(km_raw),
            "elev_up":          None,
            "elev_down":        None,
            "duration_hrs":     None,
            "difficulty":       None,
            "description":      None,
            "arrival_stations": [],
            "sbb_times":        {},
            "_source_url":      STORMARNWEG_URL,
        })
        print(f"  Etappe {nr:2d}  {start} → {end} ({parse_km(km_raw)} km)")

    stages.sort(key=lambda s: s["stage_nr"])
    if not stages:
        print("  ERROR: no stages found")
        return None
    total_km = round(sum(s["dist_km"] for s in stages if s["dist_km"]), 1)
    print(f"  {len(stages)} stages, {total_km} km total")
    return {
        "route_id":   53,
        "route_type": "regional",
        "land":       "de-hike",
        "name":       "Stormarnweg",
        "description": None,
        "start":      stages[0]["start_name"],
        "end":        stages[-1]["end_name"],
        "total_km":   total_km,
        "stages":     stages,
    }


# ---------------------------------------------------------------------------
# Oberlausitzer Bergweg — oberlausitzer-bergweg.de/tourenplanung/etappen
# ---------------------------------------------------------------------------
# Each stage block: "Oberlausitzer Bergweg - Etappe N" heading, prose description
# with "von[m] X [bis] nach Y" pattern, "Strecke X,X km" following.

OBERLAUSITZ_URL = "https://www.oberlausitzer-bergweg.de/tourenplanung/etappen"
OBERLAUSITZ_STAGE_RE = re.compile(
    r'Oberlausitzer Bergweg - Etappe (\d+)(.*?)(?=Oberlausitzer Bergweg - Etappe|\Z)',
    re.DOTALL,
)
OBERLAUSITZ_FROM_TO_RE = re.compile(
    r'vo[nm]\s+(.+?)\s+(?:bis\s+zu\s+\w+\s+\w+\s+|bis\s+)?nach\s+(.+?)(?:\s+auf\s+\w|\.\s*Strecke|\s*Strecke)',
    re.DOTALL,
)
OBERLAUSITZ_KM_RE = re.compile(r'Strecke\s+([\d,\.]+)\s*km')


def scrape_oberlausitz():
    print(f"Fetching {OBERLAUSITZ_URL} ...", flush=True)
    time.sleep(DELAY)
    html = fetch(OBERLAUSITZ_URL)
    if not html:
        print("  ERROR: fetch failed")
        return None

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    # Normalise whitespace
    text = re.sub(r'\s+', ' ', text)

    stages = []
    for m in OBERLAUSITZ_STAGE_RE.finditer(text):
        nr   = int(m.group(1))
        body = m.group(2)
        km_m = OBERLAUSITZ_KM_RE.search(body)
        ft_m = OBERLAUSITZ_FROM_TO_RE.search(body)
        start = re.sub(r'\s+bis\s+zu\s+.*$', '', ft_m.group(1).strip()) if ft_m else None
        end   = ft_m.group(2).strip() if ft_m else None
        stages.append({
            "stage_nr":         nr,
            "start_name":       start or f"Etappe {nr} start",
            "end_name":         end   or f"Etappe {nr} end",
            "via":              None,
            "dist_km":          parse_km(km_m.group(1)) if km_m else None,
            "elev_up":          None,
            "elev_down":        None,
            "duration_hrs":     None,
            "difficulty":       None,
            "description":      None,
            "arrival_stations": [],
            "sbb_times":        {},
            "_source_url":      OBERLAUSITZ_URL,
        })
        print(f"  Etappe {nr:2d}  {start} → {end} ({(parse_km(km_m.group(1)) if km_m else '?')} km)")

    stages.sort(key=lambda s: s["stage_nr"])
    if not stages:
        print("  ERROR: no stages found")
        return None
    total_km = round(sum(s["dist_km"] for s in stages if s["dist_km"]), 1)
    print(f"  {len(stages)} stages, {total_km} km total")
    return {
        "route_id":   54,
        "route_type": "national",
        "land":       "de-hike",
        "name":       "Oberlausitzer Bergweg",
        "description": None,
        "start":      stages[0]["start_name"],
        "end":        stages[-1]["end_name"],
        "total_km":   total_km,
        "stages":     stages,
    }


# ---------------------------------------------------------------------------
# Werra-Burgen-Steig Hessen — werra-burgen-steig-hessen.de/abschnitte
# ---------------------------------------------------------------------------
# Page lists 11 sections: "X5 H (N) Start-End Länge: X km"
# Use rsplit("-", 1) for start/end (acceptable for the one compound-name case).

WERRA_URL = "https://www.werra-burgen-steig-hessen.de/abschnitte"
WERRA_RE = re.compile(
    r'X5 H \((\d+)\)\s+(.+?)\s+Länge:\s+([\d,\.]+)\s*km',
    re.IGNORECASE,
)


def scrape_werra():
    print(f"Fetching {WERRA_URL} ...", flush=True)
    time.sleep(DELAY)
    html = fetch(WERRA_URL)
    if not html:
        print("  ERROR: fetch failed")
        return None

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    text = re.sub(r'\s+', ' ', text)

    raw = []
    seen = set()
    for m in WERRA_RE.finditer(text):
        nr = int(m.group(1))
        if nr in seen:
            continue
        seen.add(nr)
        raw.append((nr, m.group(2).strip(), parse_km(m.group(3))))

    # Smart split: use lsplit or rsplit depending on which makes start match prev_end
    def smart_split(label, prev_end):
        parts_l = label.split("-", 1)
        start_l = parts_l[0].strip()
        end_l   = parts_l[1].strip() if len(parts_l) > 1 else ""
        parts_r = label.rsplit("-", 1)
        start_r = parts_r[0].strip()
        end_r   = parts_r[1].strip() if len(parts_r) > 1 else ""
        if prev_end and start_r == prev_end:
            return start_r, end_r
        return start_l, end_l

    stages = []
    prev_end = None
    for nr, label, km in raw:
        start, end = smart_split(label, prev_end)
        prev_end = end
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
            "_source_url":      WERRA_URL,
        })
        print(f"  X5H({nr:2d})  {start} → {end} ({km} km)")


    stages.sort(key=lambda s: s["stage_nr"])
    if not stages:
        print("  ERROR: no stages found")
        return None
    total_km = round(sum(s["dist_km"] for s in stages if s["dist_km"]), 1)
    print(f"  {len(stages)} stages, {total_km} km total")
    return {
        "route_id":   55,
        "route_type": "national",
        "land":       "de-hike",
        "name":       "Werra-Burgen-Steig Hessen",
        "description": None,
        "start":      stages[0]["start_name"],
        "end":        stages[-1]["end_name"],
        "total_km":   total_km,
        "stages":     stages,
    }


# ---------------------------------------------------------------------------
# König-Ludwig-Weg — koenig-ludwig-weg.de (JS-rendered; hardcoded from official source)
# ---------------------------------------------------------------------------
# 6 stages, 122.8 km total. Berg (near Starnberg) → Füssen.
# Source data extracted from koenig-ludwig-weg.de stage pages.

KOENIG_LUDWIG_URL = "https://www.koenig-ludwig-weg.de/en/stages"

KOENIG_LUDWIG_STAGES = [
    (1, "Berg",             "Dießen",           32.6),
    (2, "Dießen",           "Paterzell",        17.2),
    (3, "Paterzell",        "Hohenpeißenberg",  13.0),
    (4, "Hohenpeißenberg",  "Rottenbuch",       13.0),
    (5, "Rottenbuch",       "Prem",             22.4),
    (6, "Prem",             "Füssen",           24.6),
]


def scrape_koenig_ludwig():
    print(f"König-Ludwig-Weg — hardcoded (JS-rendered source)")
    stages = []
    for nr, start, end, km in KOENIG_LUDWIG_STAGES:
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
            "_source_url":      KOENIG_LUDWIG_URL,
        })
        print(f"  Etappe {nr}  {start} → {end} ({km} km)")
    total_km = round(sum(s["dist_km"] for s in stages), 1)
    print(f"  {len(stages)} stages, {total_km} km total")
    return {
        "route_id":   56,
        "route_type": "national",
        "land":       "de-hike",
        "name":       "König-Ludwig-Weg",
        "description": None,
        "start":      stages[0]["start_name"],
        "end":        stages[-1]["end_name"],
        "total_km":   total_km,
        "stages":     stages,
    }


# ---------------------------------------------------------------------------
# X27 Friedrich-Wilhelm-Grimme-Weg — ich-geh-wandern.de
# ---------------------------------------------------------------------------
# 4 stages, ~85 km. Altenhundem → Bigge (Attendorn).
# Each stage page has "Länge: XX.XXkm" in the page text.

X27_STAGES = [
    (1, "altenhundem-schmallenberg",  "Altenhundem", "Schmallenberg"),
    (2, "schmallenberg-nordenau",     "Schmallenberg", "Nordenau"),
    (3, "nordenau-siedlinghausen",    "Nordenau",    "Siedlinghausen"),
    (4, "siedlinghausen-bigge",       "Siedlinghausen", "Bigge"),
]
X27_BASE = "https://www.ich-geh-wandern.de/friedrich-wilhelm-grimme-weg-etappe"
X27_KM_RE = re.compile(r'Länge:\s*([\d.]+)\s*km')


def scrape_x27():
    stages = []
    for nr, slug, start, end in X27_STAGES:
        url = f"{X27_BASE}-{nr}-{slug}"
        print(f"  Fetching stage {nr} — {url}", flush=True)
        time.sleep(DELAY)
        html = fetch(url)
        if not html:
            print(f"    fetch error")
            continue
        km_m = X27_KM_RE.search(html)
        km = round(float(km_m.group(1)), 1) if km_m else None
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
            "_source_url":      url,
        })
        print(f"    {start} → {end} ({km} km)")

    if not stages:
        print("  ERROR: no stages fetched")
        return None
    total_km = round(sum(s["dist_km"] for s in stages if s["dist_km"]), 1)
    print(f"  {len(stages)} stages, {total_km} km total")
    return {
        "route_id":   57,
        "route_type": "national",
        "land":       "de-hike",
        "name":       "X27 Friedrich-Wilhelm-Grimme-Weg",
        "description": None,
        "start":      stages[0]["start_name"],
        "end":        stages[-1]["end_name"],
        "total_km":   total_km,
        "stages":     stages,
    }


# ---------------------------------------------------------------------------
# Camino de la Frontera — caminodelafrontera.es/etapas-del-camino-de-la-frontera/
# ---------------------------------------------------------------------------
# Single page listing all stages: "Etapa NN: Start – End (X,XX kms)"

FRONTERA_URL = "https://caminodelafrontera.es/etapas-del-camino-de-la-frontera/"
FRONTERA_RE = re.compile(
    r'[Ee]tapa\s+0?(\d+):\s*(.+?)\s*[–—-]\s*(.+?)\s*\([\s]*([\d,\.]+)\s*kms?\)',
    re.DOTALL,
)


def scrape_frontera():
    print(f"Fetching {FRONTERA_URL} ...", flush=True)
    time.sleep(DELAY)
    html = fetch(FRONTERA_URL)
    if not html:
        print("  ERROR: fetch failed")
        return None

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    text = re.sub(r'\s+', ' ', text)

    stages = []
    seen = set()
    for m in FRONTERA_RE.finditer(text):
        nr = int(m.group(1))
        if nr in seen:
            continue
        seen.add(nr)
        start = m.group(2).strip()
        end   = m.group(3).strip()
        km    = parse_km(m.group(4))
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
            "_source_url":      FRONTERA_URL,
        })
        print(f"  Etapa {nr:2d}  {start} → {end} ({km} km)")

    stages.sort(key=lambda s: s["stage_nr"])
    if not stages:
        print("  ERROR: no stages found")
        return None
    total_km = round(sum(s["dist_km"] for s in stages if s["dist_km"]), 1)
    print(f"  {len(stages)} stages, {total_km} km total")
    return {
        "route_id":   11,
        "route_type": "national",
        "land":       "es-hike",
        "name":       "Camino de la Frontera",
        "description": None,
        "start":      stages[0]["start_name"],
        "end":        stages[-1]["end_name"],
        "total_km":   total_km,
        "stages":     stages,
    }


# ---------------------------------------------------------------------------
# Grande Rota Peneda-Gerês — walkingpenedageres.pt/pt/etapas/
# ---------------------------------------------------------------------------
# Single page listing all 19 stages: "Etapa N | Start – End"
# No distance data available in static HTML.

PENEDA_URL = "https://www.walkingpenedageres.pt/pt/etapas/"
PENEDA_RE = re.compile(
    r'Etapa\s+(\d+)\s*\|\s*(.+?)\s*[–—-]\s*(.+?)(?=\s*Etapa\s+\d+|\s*PLANEIE|\s*PESQUISAR|\Z)',
    re.DOTALL,
)


def scrape_peneda():
    print(f"Fetching {PENEDA_URL} ...", flush=True)
    time.sleep(DELAY)
    html = fetch(PENEDA_URL)
    if not html:
        print("  ERROR: fetch failed")
        return None

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    text = re.sub(r'\s+', ' ', text)

    stages = []
    seen = set()
    for m in PENEDA_RE.finditer(text):
        nr = int(m.group(1))
        if nr in seen:
            continue
        seen.add(nr)
        start = m.group(2).strip()
        end   = m.group(3).strip()
        stages.append({
            "stage_nr":         nr,
            "start_name":       start,
            "end_name":         end,
            "via":              None,
            "dist_km":          None,
            "elev_up":          None,
            "elev_down":        None,
            "duration_hrs":     None,
            "difficulty":       None,
            "description":      None,
            "arrival_stations": [],
            "sbb_times":        {},
            "_source_url":      PENEDA_URL,
        })
        print(f"  Etapa {nr:2d}  {start} → {end}")

    stages.sort(key=lambda s: s["stage_nr"])
    if not stages:
        print("  ERROR: no stages found")
        return None
    print(f"  {len(stages)} stages (no km data in static HTML)")
    return {
        "route_id":   2,
        "route_type": "national",
        "land":       "pt-hike",
        "name":       "Grande Rota Peneda-Gerês",
        "description": None,
        "start":      stages[0]["start_name"],
        "end":        stages[-1]["end_name"],
        "total_km":   None,
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
    "stormarnweg":    scrape_stormarnweg,
    "oberlausitz":    scrape_oberlausitz,
    "werra":          scrape_werra,
    "koenig-ludwig":  scrape_koenig_ludwig,
    "x27":            scrape_x27,
    "frontera":       scrape_frontera,
    "peneda":         scrape_peneda,
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
