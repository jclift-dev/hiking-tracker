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
  Camino Portugués             (pt-hike, route_id=3)   pilgrim.es
  SNP Trail                    (sk-hike, route_id=1)   snptrail.com  [hardcoded — multi-page]
  Kammweg Erzgebirge-Vogtland  (de-hike, route_id=48)  erzgebirge-tourismus.de  [hardcoded — overwrites 3 OSM sections]
  Vulkanring Vogelsberg        (de-hike, route_id=58)  vogelsberg-touristik.de  [hardcoded]
  Camino Espiritual del Sur    (es-hike, route_id=12)  caminoespiritualdelsur.com
  GR54 Tour de l'Oisans       (fr-hike, route_id=14)  geotrek-admin.ecrins-parcnational.fr
  Grande traversée Alpi Marittime (eu-hike, route_id=7) adminrando.marittimemercantour.eu

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
# Camino Portugués — pilgrim.es/en/portuguese-way/
# ---------------------------------------------------------------------------
# 25 walking stages, Lisboa → Santiago de Compostela.
# Stage cards: <a href="/en/portuguese-way/stage-N-.../">
#   <h3>N</h3><h3>Start</h3><h3>❯ End</h3><p>XXKm</p><p>X.Xh</p>

PILGRIM_URL      = "https://www.pilgrim.es/en/portuguese-way/"
PILGRIM_HREF_RE  = re.compile(r'/portuguese-way/stage-(\d+)-')
PILGRIM_KM_RE    = re.compile(r'^([\d.,]+)\s*[Kk][Mm]')
PILGRIM_HRS_RE   = re.compile(r'^([\d.,]+)\s*h$', re.IGNORECASE)


def scrape_camino_portugues():
    print(f"Fetching {PILGRIM_URL} ...")
    time.sleep(DELAY)
    html = fetch(PILGRIM_URL)
    if not html:
        print("  ERROR: fetch failed")
        return None

    soup = BeautifulSoup(html, "html.parser")
    stages = []
    seen = set()

    for a in soup.find_all("a", href=PILGRIM_HREF_RE):
        href = a.get("href", "")
        m = PILGRIM_HREF_RE.search(href)
        if not m:
            continue
        nr = int(m.group(1))
        if nr in seen:
            continue

        h3s = a.find_all("h3")
        # h3[0]=Start  h3[1]="❯End"  h3[2]="Stage N :"
        if len(h3s) < 2:
            continue

        start   = h3s[0].get_text(strip=True)
        end_raw = h3s[1].get_text(strip=True)
        end     = end_raw.replace("❯", "").strip()

        if not start or not end:
            continue

        # km in <div><i class="icon-location"></i>XXKm</div>
        # hrs in <div><i class="icon-clock"></i>X,Xh</div>
        km = hrs = None
        for div in a.find_all("div"):
            icon = div.find("i")
            if not icon:
                continue
            icon_cls = (icon.get("class") or [""])[0]
            text = div.get_text(strip=True)
            if icon_cls == "icon-location":
                km_m = PILGRIM_KM_RE.match(text)
                if km_m:
                    km = parse_km(km_m.group(1))
            elif icon_cls == "icon-clock":
                hrs_m = PILGRIM_HRS_RE.match(text)
                if hrs_m:
                    try:
                        hrs = round(float(hrs_m.group(1).replace(",", ".")), 1)
                    except ValueError:
                        pass

        seen.add(nr)
        stages.append({
            "stage_nr":         nr,
            "start_name":       start,
            "end_name":         end,
            "via":              None,
            "dist_km":          km,
            "elev_up":          None,
            "elev_down":        None,
            "duration_hrs":     hrs,
            "difficulty":       None,
            "description":      None,
            "arrival_stations": [],
            "sbb_times":        {},
            "_source_url":      PILGRIM_URL,
        })
        print(f"  Stage {nr:2d}  {start} → {end} ({km} km, {hrs}h)")

    stages.sort(key=lambda s: s["stage_nr"])
    if not stages:
        print("  ERROR: no stages found")
        return None
    total_km = round(sum(s["dist_km"] for s in stages if s["dist_km"]), 1)
    print(f"  {len(stages)} stages, {total_km} km total")
    return {
        "route_id":   3,
        "route_type": "international",
        "land":       "pt-hike",
        "name":       "Camino Portugués",
        "description": None,
        "start":      stages[0]["start_name"],
        "end":        stages[-1]["end_name"],
        "total_km":   total_km,
        "stages":     stages,
    }


# ---------------------------------------------------------------------------
# SNP Trail / E8 Slovakia — snptrail.com (hardcoded, static HTML multi-page)
# ---------------------------------------------------------------------------
# 27 stages, ~771 km, Dukelský Priesmyk (Dukla Pass) → Devín Castle.
# Slovak section of the E8 European Long Distance Path.
# Data verified against snptrail.com June 2026. URL pattern is inconsistent
# across pages (part2 has no hyphen; parts 3-5 have hyphen), so hardcoded.

SNP_PAGE_URLS = [
    "https://snptrail.com/maps-of-the-trail/",           # stages 1–5
    "https://snptrail.com/maps-of-the-trail-part2/",     # stages 6–10
    "https://snptrail.com/maps-of-the-trail-part-3/",    # stages 11–15
    "https://snptrail.com/maps-of-the-trail-part-4/",    # stages 16–20
    "https://snptrail.com/maps-of-the-trail-part-5/",    # stages 21–27
]

SNP_STAGES = [
    #  nr   start                              end                          km    page
    (1,  "Dukelský Priesmyk (Dukla Pass)",  "Svidník",                  26.4, SNP_PAGE_URLS[0]),
    (2,  "Svidník",                          "Zborov",                   29.0, SNP_PAGE_URLS[0]),
    (3,  "Zborov",                           "Žobrák",                   32.2, SNP_PAGE_URLS[0]),
    (4,  "Žobrák",                           "Veľký Šariš",              30.0, SNP_PAGE_URLS[0]),
    (5,  "Veľký Šariš",                      "Kysak",                    32.6, SNP_PAGE_URLS[0]),
    (6,  "Kysak",                            "Jahodná mountain hut",     30.3, SNP_PAGE_URLS[1]),
    (7,  "Jahodná mountain hut",             "Štós spa",                 35.8, SNP_PAGE_URLS[1]),
    (8,  "Štós spa",                         "Mountain hut Volovec",     31.9, SNP_PAGE_URLS[1]),
    (9,  "Mountain hut Volovec",             "Dobšinský Kopec",          29.0, SNP_PAGE_URLS[1]),
    (10, "Dobšinský Kopec",                  "Telgart",                  21.0, SNP_PAGE_URLS[1]),
    (11, "Telgart",                          "Andrejcová shelter",       16.2, SNP_PAGE_URLS[2]),
    (12, "Andrejcová shelter",               "Čertovica pass",           28.0, SNP_PAGE_URLS[2]),
    (13, "Čertovica",                        "Ďurková shelter",          25.6, SNP_PAGE_URLS[2]),
    (14, "Ďurková shelter",                  "Donovaly",                 27.7, SNP_PAGE_URLS[2]),
    (15, "Donovaly",                         "Kráľova Studňa Hotel",     20.4, SNP_PAGE_URLS[2]),
    (16, "Kráľova Studňa hotel",             "Skalka",                   26.0, SNP_PAGE_URLS[3]),
    (17, "Skalka",                           "Jalovské Lazy",            28.0, SNP_PAGE_URLS[3]),
    (18, "Jalovské Lazy",                    "Fačkovské Sedlo",          33.5, SNP_PAGE_URLS[3]),
    (19, "Fačkovské Sedlo",                  "Zliechov",                 20.0, SNP_PAGE_URLS[3]),
    (20, "Zliechov",                         "Trenčianske Teplice",      32.0, SNP_PAGE_URLS[3]),
    (21, "Trenčianske Teplice",              "Vyškovec",                 35.0, SNP_PAGE_URLS[4]),
    (22, "Vyškovec",                         "Veľká Javorina",           24.0, SNP_PAGE_URLS[4]),
    (23, "Veľká Javorina",                   "Brezová pod Bradlom",      31.7, SNP_PAGE_URLS[4]),
    (24, "Brezová pod Bradlom",              "Buková camping",           37.5, SNP_PAGE_URLS[4]),
    (25, "Buková",                           "Zochova Chata",            30.0, SNP_PAGE_URLS[4]),
    (26, "Zochova Chata",                    "Biely Kríž",               26.0, SNP_PAGE_URLS[4]),
    (27, "Biely Kríž",                       "Devín Castle",             31.0, SNP_PAGE_URLS[4]),
]


def scrape_snp():
    print("SNP Trail / E8 Slovakia — hardcoded from snptrail.com")
    stages = []
    for nr, start, end, km, src_url in SNP_STAGES:
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
            "_source_url":      src_url,
        })
        print(f"  Stage {nr:2d}  {start} → {end} ({km} km)")
    total_km = round(sum(s["dist_km"] for s in stages), 1)
    print(f"  {len(stages)} stages, {total_km} km total")
    return {
        "route_id":   1,
        "route_type": "national",
        "land":       "sk-hike",
        "name":       "SNP Trail",
        "description": None,
        "start":      stages[0]["start_name"],
        "end":        stages[-1]["end_name"],
        "total_km":   total_km,
        "stages":     stages,
    }


# ---------------------------------------------------------------------------
# Coast to Coast Walk — hardcoded (Wainwright guidebook staging, 2nd ed.)
# ---------------------------------------------------------------------------
# 14 stages, 306 km. St Bees (Cumbria) → Robin Hood's Bay (North Yorkshire).
# Distances converted from official miles; elevation backfill via OSM/OTD later.

C2C_URL = "https://www.nationaltrail.co.uk/en_GB/trails/coast-to-coast/"
C2C_STAGES = [
    ( 1, "St Bees",           "Ennerdale Bridge",  23.3),
    ( 2, "Ennerdale Bridge",  "Rosthwaite",        23.3),
    ( 3, "Rosthwaite",        "Grasmere",          14.5),
    ( 4, "Grasmere",          "Patterdale",        13.7),
    ( 5, "Patterdale",        "Shap",              25.7),
    ( 6, "Shap",              "Kirkby Stephen",    32.2),
    ( 7, "Kirkby Stephen",    "Keld",              19.3),
    ( 8, "Keld",              "Reeth",             17.7),
    ( 9, "Reeth",             "Richmond",          17.3),
    (10, "Richmond",          "Danby Wiske",       22.5),
    (11, "Danby Wiske",       "Ingleby Cross",     14.5),
    (12, "Ingleby Cross",     "Clay Bank Top",     19.3),
    (13, "Clay Bank Top",     "Glaisdale",         19.3),
    (14, "Glaisdale",         "Robin Hood's Bay",  32.2),
]


def scrape_c2c():
    print("Coast to Coast Walk — hardcoded (Wainwright guidebook staging)")
    stages = []
    for nr, start, end, km in C2C_STAGES:
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
            "_source_url":      C2C_URL,
        })
        print(f"  Stage {nr:2d}  {start} → {end} ({km} km)")
    total_km = round(sum(s["dist_km"] for s in stages), 1)
    print(f"  {len(stages)} stages, {total_km} km total")
    return {
        "route_id":   15,
        "route_type": "national",
        "land":       "uk",
        "name":       "Coast to Coast Walk",
        "description": (
            "The Coast to Coast Walk traverses northern England from St Bees on the "
            "Irish Sea coast to Robin Hood's Bay on the North Sea, passing through "
            "three national parks: the Lake District, the Yorkshire Dales, and the "
            "North York Moors. Devised by Alfred Wainwright and designated a National "
            "Trail in 2024, it covers 306 km (190 miles) of dramatically varied terrain."
        ),
        "start":      "St Bees",
        "end":        "Robin Hood's Bay",
        "total_km":   306,
        "stages":     stages,
    }


# ---------------------------------------------------------------------------
# Kammweg Erzgebirge-Vogtland — hardcoded (erzgebirge-tourismus.de)
# ---------------------------------------------------------------------------
# 17 stages, ~285 km. Geising → Blankenstein.
# Overwrites the 3 coarse OSM sections already in route_id=48.
# Stages 1–14 from erzgebirge-tourismus.de; 15–17 from komoot/trail sources.

KAMMWEG_URL = "https://www.erzgebirge-tourismus.de/en/summer/hiking/kammweg-erzgebirge-vogtland/"
KAMMWEG_STAGES = [
    ( 1, "Geising",                "Holzhau",                  24.5),
    ( 2, "Holzhau",                "Sayda",                    12.4),
    ( 3, "Sayda",                  "Seiffen",                   9.6),
    ( 4, "Seiffen",                "Olbernhau",                11.3),
    ( 5, "Olbernhau",              "Kühnhaide",                20.7),
    ( 6, "Kühnhaide",              "Satzung",                  14.7),
    ( 7, "Satzung",                "Bärenstein",               22.7),
    ( 8, "Bärenstein",             "Oberwiesenthal",           17.1),
    ( 9, "Oberwiesenthal",         "Breitenbrunn",             18.1),
    (10, "Breitenbrunn",           "Johanngeorgenstadt",       14.5),
    (11, "Johanngeorgenstadt",     "Weitersglashütte",         10.6),
    (12, "Weitersglashütte",       "Mühlleithen",              13.8),
    (13, "Mühlleithen",            "Schöneck",                 14.8),
    (14, "Schöneck",               "Eichigt",                  24.7),
    (15, "Eichigt",                "Tirpersdorf",              20.8),
    (16, "Tirpersdorf",            "Hof",                      23.2),
    (17, "Hof",                    "Blankenstein",             13.1),
]


def scrape_kammweg():
    print("Kammweg Erzgebirge-Vogtland — hardcoded (replaces 3 OSM sections)")
    stages = []
    for nr, start, end, km in KAMMWEG_STAGES:
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
            "_source_url":      KAMMWEG_URL,
        })
        print(f"  Etappe {nr:2d}  {start} → {end} ({km} km)")
    total_km = round(sum(s["dist_km"] for s in stages), 1)
    print(f"  {len(stages)} stages, {total_km} km total")
    return {
        "route_id":   48,
        "route_type": "national",
        "land":       "de-hike",
        "name":       "Kammweg Erzgebirge-Vogtland",
        "description": None,
        "start":      stages[0]["start_name"],
        "end":        stages[-1]["end_name"],
        "total_km":   total_km,
        "stages":     stages,
    }


# ---------------------------------------------------------------------------
# Vulkanring Vogelsberg — hardcoded (fernwege.de / vogelsberg-touristik.de)
# ---------------------------------------------------------------------------
# 6 stages, 117.7 km, circular from Laubach.

VULKANRING_URL = "https://www.vogelsberg-touristik.de/vulkanring"
VULKANRING_STAGES = [
    (1, "Laubach",       "Eichelsdorf",  18.6,  481, -522),
    (2, "Eichelsdorf",   "Burkhards",    17.0,  495, -282),
    (3, "Burkhards",     "Herchenhain",  16.0,  629, -324),
    (4, "Herchenhain",   "Herbstein",    20.1,  340, -583),
    (5, "Herbstein",     "Ulrichstein",  23.2,  713, -587),
    (6, "Ulrichstein",   "Laubach",      22.8,  414, -774),
]


def scrape_vulkanring():
    print("Vulkanring Vogelsberg — hardcoded (vogelsberg-touristik.de)")
    stages = []
    for nr, start, end, km, up, down in VULKANRING_STAGES:
        stages.append({
            "stage_nr":         nr,
            "start_name":       start,
            "end_name":         end,
            "via":              None,
            "dist_km":          km,
            "elev_up":          up,
            "elev_down":        down,
            "duration_hrs":     None,
            "difficulty":       None,
            "description":      None,
            "arrival_stations": [],
            "sbb_times":        {},
            "_source_url":      VULKANRING_URL,
        })
        print(f"  Etappe {nr}  {start} → {end} ({km} km, +{up}/-{abs(down)}m)")
    total_km = round(sum(s["dist_km"] for s in stages), 1)
    print(f"  {len(stages)} stages, {total_km} km total")
    return {
        "route_id":   58,
        "route_type": "national",
        "land":       "de-hike",
        "name":       "Vulkanring Vogelsberg",
        "description": None,
        "start":      stages[0]["start_name"],
        "end":        stages[-1]["end_name"],
        "total_km":   total_km,
        "stages":     stages,
    }


# ---------------------------------------------------------------------------
# Ith-Hils-Wanderweg — ith-hils-weg.de
# ---------------------------------------------------------------------------
# 7 stages, 107.8 km total. Circular: Coppenbrügge → … → Coppenbrügge.
# Lower Saxony (Weserbergland/Leinebergland). de-hike, route_id=59.
ITH_HILS_URL = "https://www.ith-hils-weg.de/seite/538519/etappen.html"
ITH_HILS_STAGES = [
    (1, "Coppenbrügge",    "Humboldtsee",    18.9),
    (2, "Humboldtsee",     "Eschershausen",  17.3),
    (3, "Eschershausen",   "Grünenplan",     13.0),
    (4, "Grünenplan",      "Delligsen",      14.0),
    (5, "Delligsen",       "Duingen",        18.8),
    (6, "Duingen",         "Salzhemmendorf", 15.7),
    (7, "Salzhemmendorf",  "Coppenbrügge",   10.1),
]


def scrape_ith_hils():
    print("Ith-Hils-Wanderweg — hardcoded (ith-hils-weg.de)")
    stages = []
    for nr, start, end, km in ITH_HILS_STAGES:
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
            "_source_url":      ITH_HILS_URL,
        })
        print(f"  Etappe {nr}  {start} → {end} ({km} km)")
    total_km = round(sum(s["dist_km"] for s in stages), 1)
    print(f"  {len(stages)} stages, {total_km} km total")
    return {
        "route_id":   59,
        "route_type": "national",
        "land":       "de-hike",
        "name":       "Ith-Hils-Wanderweg",
        "description": None,
        "start":      stages[0]["start_name"],
        "end":        stages[-1]["end_name"],
        "total_km":   total_km,
        "stages":     stages,
    }


# ---------------------------------------------------------------------------
# Camino Espiritual del Sur — caminoespiritualdelsur.com
# ---------------------------------------------------------------------------
# 14 stages, ~318 km. Guadix (Granada) → Caravaca de la Cruz (Murcia).
# WordPress static site. Distance (km) and elevation gain (m) on each stage page.

ESPIRITUAL_BASE = "https://www.caminoespiritualdelsur.com"
ESPIRITUAL_SLUGS = [
    # (nr, slug, start_name, end_name)
    (1,  "guadix-fonelas",                       "Guadix",                "Fonelas"),
    (2,  "fonelas-balneario_de_alicun",           "Fonelas",               "Balneario de Alicún"),
    (3,  "balneario-de-alucun-gorafe",            "Balneario de Alicún",   "Gorafe"),
    (4,  "gorafe-freila",                         "Gorafe",                "Freila"),
    (5,  "freila-baza",                           "Freila",                "Baza"),
    (6,  "baza-zujar",                            "Baza",                  "Zújar"),
    (7,  "zujar-benamaurel",                      "Zújar",                 "Benamaurel"),
    (8,  "benamaurel-cullar",                     "Benamaurel",            "Cúllar"),
    (9,  "cullar-orce",                           "Cúllar",                "Orce"),
    (10, "orce-huescar",                          "Orce",                  "Huéscar"),
    (11, "huescar-puebla-d-fadrique",             "Huéscar",               "Puebla de Don Fadrique"),
    (12, "puebla-d-fadrique-canada-de-la-cruz",   "Puebla de Don Fadrique","Cañada de la Cruz"),
    (13, "canada-de-la-cruz-archivel",            "Cañada de la Cruz",     "Archivel"),
    (14, "archivel-caravaca",                     "Archivel",              "Caravaca de la Cruz"),
]

ESPIRITUAL_KM_RE  = re.compile(r'(\d+(?:[.,]\d+)?)\s*km', re.IGNORECASE)
ESPIRITUAL_ELV_RE = re.compile(r'(\d+(?:[.,]\d+)?)\s*m(?:\b|etros?)', re.IGNORECASE)
ESPIRITUAL_DUR_RE = re.compile(r'(\d+)\s*h(?:oras?)?\s*(?:y\s*)?(\d+)?\s*(?:min(?:utos?)?)?', re.IGNORECASE)
ESPIRITUAL_NAME_RE = re.compile(
    r'Etapa\s+\d+[:\s]+([A-Za-záéíóúüñÁÉÍÓÚÜÑ\s\.\-]+?)\s*[-–]\s*([A-Za-záéíóúüñÁÉÍÓÚÜÑ\s\.\-]+?)(?=\s*\d|\s*<|\s*Dist|\Z)',
    re.IGNORECASE,
)


def _parse_espiritual_stage(nr, slug, start_name, end_name):
    url = f"{ESPIRITUAL_BASE}/trazado-principal/{slug}/"
    time.sleep(DELAY)
    html = fetch(url)
    if not html:
        print(f"  Stage {nr}: fetch failed")
        return None

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    text = re.sub(r'\s+', ' ', text)

    # Distance: first km value in page (usually the stage distance)
    km = None
    for m in ESPIRITUAL_KM_RE.finditer(text):
        val = parse_km(m.group(1))
        if val and 5 <= val <= 60:
            km = val
            break

    # Elevation gain: look for metre value near "Altura" or "altura"
    elev_up = None
    for m in re.finditer(r'[Aa]ltura[^\d]{0,20}(\d+)', text):
        elev_up = int(m.group(1))
        break
    if elev_up is None:
        for m in re.finditer(r'(\d{2,4})\s*m\b', text):
            val = int(m.group(1))
            if 50 <= val <= 2000:
                elev_up = val
                break

    # Duration
    dur = None
    m_dur = ESPIRITUAL_DUR_RE.search(text)
    if m_dur:
        h = int(m_dur.group(1))
        mins = int(m_dur.group(2)) if m_dur.group(2) else 0
        dur = round(h + mins / 60, 2) if h < 20 else None

    print(f"  Etapa {nr:2d}  {start_name} → {end_name} ({km} km, +{elev_up}m, {dur}h)")
    return {
        "stage_nr":         nr,
        "start_name":       start_name,
        "end_name":         end_name,
        "via":              None,
        "dist_km":          km,
        "elev_up":          elev_up,
        "elev_down":        None,
        "duration_hrs":     dur,
        "difficulty":       None,
        "description":      None,
        "arrival_stations": [],
        "sbb_times":        {},
        "_source_url":      url,
    }


def scrape_espiritual():
    print("Camino Espiritual del Sur — scraping caminoespiritualdelsur.com")
    stages = []
    for nr, slug, start_name, end_name in ESPIRITUAL_SLUGS:
        stage = _parse_espiritual_stage(nr, slug, start_name, end_name)
        if stage:
            stages.append(stage)

    stages.sort(key=lambda s: s["stage_nr"])
    if not stages:
        print("  ERROR: no stages found")
        return None
    total_km = round(sum(s["dist_km"] for s in stages if s["dist_km"]), 1)
    print(f"  {len(stages)} stages, {total_km} km total")
    return {
        "route_id":   12,
        "route_type": "national",
        "land":       "es-hike",
        "name":       "Camino Espiritual del Sur",
        "description": None,
        "start":      stages[0]["start_name"],
        "end":        stages[-1]["end_name"],
        "total_km":   total_km,
        "stages":     stages,
    }


# ---------------------------------------------------------------------------
# GR54 Tour de l'Oisans et Écrins — geotrek-admin.ecrins-parcnational.fr
# ---------------------------------------------------------------------------
# Public Geotrek API. Parent trek 937571 lists 13 child IDs in ranked order.
# Each child trek has departure, arrival, length_2d (m), ascent, descent, duration (h).

GR54_API     = "https://geotrek-admin.ecrins-parcnational.fr/api/v2/trek/{}/?format=json&language=fr"
GR54_PARENT  = 937571

# ---------------------------------------------------------------------------
# Grande traversée Alpi Marittime — adminrando.marittimemercantour.eu
# ---------------------------------------------------------------------------
# Cross-border FR/IT trail, Col de Larche → Grimaldi (Mediterranean coast).
# Public Geotrek API from the Mercantour/Alpi Marittime cross-border park.

ALPI_MARITTIME_API    = "https://adminrando.marittimemercantour.eu/api/v2/trek/{}/?format=json&language=fr"
ALPI_MARITTIME_PARENT = 169810


def scrape_alpi_marittime():
    print("Grande traversée Alpi Marittime — Geotrek API (Mercantour/Marittime)")
    r = SESSION.get(ALPI_MARITTIME_API.format(ALPI_MARITTIME_PARENT), timeout=15)
    if r.status_code != 200:
        print(f"  ERROR: parent fetch returned {r.status_code}")
        return None
    parent = r.json()
    child_ids = parent.get("children", [])
    if not child_ids:
        print("  ERROR: no children found on parent trek")
        return None

    stages = []
    for nr, cid in enumerate(child_ids, 1):
        time.sleep(0.4)
        r2 = SESSION.get(ALPI_MARITTIME_API.format(cid), timeout=15)
        if r2.status_code != 200:
            print(f"  Stage {nr} (id={cid}): HTTP {r2.status_code} — skipped")
            continue
        s = r2.json()
        dist = round(s["length_2d"] / 1000, 1) if s.get("length_2d") else None
        asc  = s.get("ascent")
        desc = s.get("descent")
        dur  = s.get("duration")
        dep  = (s.get("departure") or "").strip()
        arr  = (s.get("arrival")   or "").strip()
        print(f"  Stage {nr:2d}  {dep} → {arr}  {dist}km  +{asc}m/{desc}m")
        stages.append({
            "stage_nr":         nr,
            "start_name":       dep,
            "end_name":         arr,
            "via":              None,
            "dist_km":          dist,
            "elev_up":          asc,
            "elev_down":        abs(desc) if desc else None,
            "duration_hrs":     dur,
            "difficulty":       None,
            "description":      None,
            "arrival_stations": [],
            "sbb_times":        {},
            "_source_url":      f"https://rando.marittimemercantour.eu/trek/{cid}",
        })

    if not stages:
        print("  ERROR: no stages scraped")
        return None

    total_km = round(sum(s["dist_km"] for s in stages if s["dist_km"]), 1)
    print(f"  {len(stages)} stages, {total_km} km total")
    return {
        "route_id":    7,
        "route_type":  "international",
        "land":        "eu-hike",
        "name":        "Grande traversée Alpi Marittime",
        "description": None,
        "start":       stages[0]["start_name"],
        "end":         stages[-1]["end_name"],
        "total_km":    total_km,
        "stages":      stages,
    }


def scrape_gr54():
    print("GR54 Tour de l'Oisans et Écrins — Geotrek API")
    r = SESSION.get(GR54_API.format(GR54_PARENT), timeout=15)
    if r.status_code != 200:
        print(f"  ERROR: parent fetch returned {r.status_code}")
        return None
    parent = r.json()
    child_ids = parent.get("children", [])
    if not child_ids:
        print("  ERROR: no children found on parent trek")
        return None

    stages = []
    for nr, cid in enumerate(child_ids, 1):
        time.sleep(0.4)
        r2 = SESSION.get(GR54_API.format(cid), timeout=15)
        if r2.status_code != 200:
            print(f"  Stage {nr} (id={cid}): HTTP {r2.status_code} — skipped")
            continue
        s = r2.json()
        dist = round(s["length_2d"] / 1000, 1) if s.get("length_2d") else None
        asc  = s.get("ascent")
        desc = s.get("descent")
        dur  = s.get("duration")
        dep  = (s.get("departure") or "").strip()
        arr  = (s.get("arrival")   or "").strip()
        print(f"  Stage {nr:2d}  {dep} → {arr}  {dist}km  +{asc}m/{desc}m")
        stages.append({
            "stage_nr":         nr,
            "start_name":       dep,
            "end_name":         arr,
            "via":              None,
            "dist_km":          dist,
            "elev_up":          asc,
            "elev_down":        abs(desc) if desc else None,
            "duration_hrs":     dur,
            "difficulty":       None,
            "description":      None,
            "arrival_stations": [],
            "sbb_times":        {},
            "_source_url":      f"https://www.grand-tour-ecrins.fr/trek/{cid}",
        })

    if not stages:
        print("  ERROR: no stages scraped")
        return None

    total_km = round(sum(s["dist_km"] for s in stages if s["dist_km"]), 1)
    print(f"  {len(stages)} stages, {total_km} km total")
    return {
        "route_id":    14,
        "route_type":  "national",
        "land":        "fr-hike",
        "name":        "GR54 Tour de l'Oisans et Écrins",
        "description": None,
        "start":       stages[0]["start_name"],
        "end":         stages[-1]["end_name"],
        "total_km":    total_km,
        "_osm_id":     2909096,
        "stages":      stages,
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
    "frontera":           scrape_frontera,
    "peneda":             scrape_peneda,
    "camino-portugues":   scrape_camino_portugues,
    "snp":                scrape_snp,
    "kammweg":            scrape_kammweg,
    "vulkanring":         scrape_vulkanring,
    "espiritual":         scrape_espiritual,
    "c2c":                scrape_c2c,
    "ith-hils":           scrape_ith_hils,
    "gr54":               scrape_gr54,
    "alpi-marittime":     scrape_alpi_marittime,
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
