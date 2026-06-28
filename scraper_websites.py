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
  High Scardus Trail           (eu-hike, route_id=12)  high-scardus-trail.com  MK/XK/AL, 20 hiking stages
  Vulkanring Vogelsberg        (de-hike, route_id=58)  vogelsberg-touristik.de  [hardcoded]
  Camino Espiritual del Sur    (es-hike, route_id=12)  caminoespiritualdelsur.com
  GR54 Tour de l'Oisans       (fr-hike, route_id=14)  geotrek-admin.ecrins-parcnational.fr
  Grande traversée Alpi Marittime (eu-hike, route_id=7) adminrando.marittimemercantour.eu
  Alto Tanaro Tour             (it-hike, route_id=44)  adminrando.marittimemercantour.eu
  Tour des glaciers de la Vanoise (fr-hike, route_id=15) adminrando.vanoise.com
  Camino Francés               (es-hike, route_id=15)  gronze.com  33 stages, SJdPP→Santiago
  Via de la Plata              (es-hike, route_id=16)  gronze.com  37 stages, Sevilla→Santiago (Sanabrés branch)
  Camino Inglés                (es-hike, route_id=17)  gronze.com  7 stages (Ferrol+A Coruña branches + shared trunk)
  Camino de Invierno           (es-hike, route_id=18)  gronze.com  11 stages, Ponferrada→Outeiro de Rei
  Camino Salvador              (es-hike, route_id=19)  gronze.com  7 stages, León→Grado
  Fisterra y Muxía             (es-hike, route_id=20)  gronze.com  7 stages, Santiago→Fisterra/Muxía
  Camino Aragonés              (es-hike, route_id=21)  gronze.com  7 stages, Somport→Estella
  Camino de Madrid             (es-hike, route_id=22)  gronze.com  14 stages, Madrid→Sahagún
  Camino Vasco del Litoral     (es-hike, route_id=23)  gronze.com  16 stages, Irun→Burgos/Belorado
  Camino del Ebro              (es-hike, route_id=24)  gronze.com  18 stages, Deltebre→Nájera
  Camino Vadiniense            (es-hike, route_id=25)  gronze.com  11 stages, San Vicente de la Barquera→León
  Ría de Muros-Noia            (es-hike, route_id=26)  gronze.com  5 stages
  Camino de Baztán             (es-hike, route_id=27)  gronze.com  6 stages, Bayonne→Puente la Reina
  Camino Catalán               (es-hike, route_id=28)  gronze.com  27 stages, Barcelona→Jaca
  Camino Olvidado              (es-hike, route_id=29)  gronze.com  28 stages, Bilbao→O Cebreiro
  Camino de Levante            (es-hike, route_id=30)  gronze.com  29 stages, Valencia→Zamora
  Ruta de la Lana              (es-hike, route_id=31)  gronze.com  30 stages, Alicante→Burgos
  Camino Mozárabe              (es-hike, route_id=32)  gronze.com  38 stages, multiple southern starts→Mérida
  Camino Portugués da Costa    (pt-hike, route_id=4)   gronze.com  13 stages, Porto→Pontevedra
  Camino de Vézelay            (fr-hike, route_id=30)  gronze.com  51 stages, Vézelay→Saint-Jean-Pied-de-Port
  Via Gebennensis              (eu-hike, route_id=13)  gronze.com  17 stages, Geneva→Le Puy-en-Velay (CH/FR)
  Camino de Arles              (eu-hike, route_id=14)  gronze.com  34 stages, Arles→Jaca (FR/ES)
  Camino del Piamonte          (eu-hike, route_id=15)  gronze.com  23 stages, Carcassonne→Roncesvalles (FR/ES)
  Via Francígena               (eu-hike, route_id=16)  gronze.com  51 stages, Lausanne→Rome (CH/IT)
  Camino di San Francesco      (it-hike, route_id=53)  gronze.com  23 stages, Roma→La Verna

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
# 19 stages, ~237 km, circular from Iserlohn.
# Stages 1–7 = common trunk; 8–13 = North loop; 14–19 = South loop.
# Overwrites the 3 coarse OSM sections already in route_id=44.

SAUERLAND_URL = "https://www.sauerland-waldroute.de/de/tourenplanung/wandern-in-etappen"
SAUERLAND_STAGES = [
    ( 1, "Iserlohn",               "Stephanopeler Tal",     13.0),
    ( 2, "Stephanopeler Tal",      "Volkringhausen",        12.5),
    ( 3, "Volkringhausen",         "Sundern-Amecke",        13.0),
    ( 4, "Sundern-Amecke",         "Arnsberg Schlossberg",  20.1),
    ( 5, "Arnsberg Schlossberg",   "Torhaus Möhnesee",      11.5),
    ( 6, "Torhaus Möhnesee",       "Neuhaus",                6.3),
    ( 7, "Neuhaus",                "Hirschberg",            20.4),
    ( 8, "Hirschberg",             "Bilsteintal",            2.8),
    ( 9, "Bilsteintal",            "Kallenhardt",           13.8),
    (10, "Kallenhardt",            "Bibertal",               5.3),
    (11, "Bibertal",               "Ringelstein",           11.5),
    (12, "Büren-Ringelstein",      "Brilon-Alme",           12.1),
    (13, "Brilon-Alme",            "Marsberg",              26.1),
    (14, "Marsberg",               "Diemeltalsperre",       22.3),
    (15, "Diemeltalsperre",        "Petersborn",            16.7),
    (16, "Petersborn",             "Langer Berg",            6.1),
    (17, "Langer Berg",            "Föckinghausen",         17.7),
    (18, "Föckinghausen",          "Eversberg",              6.1),
    (19, "Eversberg",              "Bilsteintal",            9.9),
]


def scrape_sauerland():
    print("Sauerland-Waldroute — hardcoded (replaces 3 OSM sections)")
    stages = []
    for nr, start, end, km in SAUERLAND_STAGES:
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
            "_source_url":      SAUERLAND_URL,
        })
        print(f"  Etappe {nr:2d}  {start} → {end} ({km} km)")
    total_km = round(sum(s["dist_km"] for s in stages), 1)
    print(f"  {len(stages)} stages, {total_km} km total")
    return {
        "route_id":   44,
        "route_type": "national",
        "land":       "de-hike",
        "name":       "Sauerland-Waldroute",
        "description": None,
        "start":      stages[0]["start_name"],
        "end":        stages[-1]["end_name"],
        "total_km":   total_km,
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
# Geotrek helper — shared by all Geotrek-based scrapers
# ---------------------------------------------------------------------------
# Three public Geotrek API instances:
#   Écrins:               geotrek-admin.ecrins-parcnational.fr
#   Mercantour/Marittime: adminrando.marittimemercantour.eu
#   Vanoise:              adminrando.vanoise.com

_ECRINS_API     = "https://geotrek-admin.ecrins-parcnational.fr/api/v2/trek/{}/?format=json&language=fr"
_MERCANTOUR_API = "https://adminrando.marittimemercantour.eu/api/v2/trek/{}/?format=json&language=fr"
_VANOISE_API    = "https://adminrando.vanoise.com/api/v2/trek/{}/?format=json&language=fr"


def _scrape_geotrek(api_tmpl, parent_id, source_tmpl):
    """Fetch all child stages from a Geotrek parent trek. Returns stage list or None."""
    r = SESSION.get(api_tmpl.format(parent_id), timeout=15)
    if r.status_code != 200:
        print(f"  ERROR: parent fetch returned {r.status_code}")
        return None
    child_ids = r.json().get("children", [])
    if not child_ids:
        print("  ERROR: no children found on parent trek")
        return None
    stages = []
    for nr, cid in enumerate(child_ids, 1):
        time.sleep(0.4)
        r2 = SESSION.get(api_tmpl.format(cid), timeout=15)
        if r2.status_code != 200:
            print(f"  Stage {nr} (id={cid}): HTTP {r2.status_code} — skipped")
            continue
        s = r2.json()
        dist = round(s["length_2d"] / 1000, 1) if s.get("length_2d") else None
        dep  = (s.get("departure") or "").strip()
        arr  = (s.get("arrival")   or "").strip()
        print(f"  Stage {nr:2d}  {dep} → {arr}  {dist}km  +{s.get('ascent')}m/{s.get('descent')}m")
        stages.append({
            "stage_nr":         nr,
            "start_name":       dep,
            "end_name":         arr,
            "via":              None,
            "dist_km":          dist,
            "elev_up":          s.get("ascent"),
            "elev_down":        abs(s["descent"]) if s.get("descent") else None,
            "duration_hrs":     s.get("duration"),
            "difficulty":       None,
            "description":      None,
            "arrival_stations": [],
            "sbb_times":        {},
            "_source_url":      source_tmpl.format(cid),
        })
    return stages or None


def _geotrek_route(api_tmpl, parent_id, source_tmpl, route_id, land, name,
                   route_type="regional", extra=None):
    print(f"{name} — Geotrek API")
    stages = _scrape_geotrek(api_tmpl, parent_id, source_tmpl)
    if not stages:
        return None
    total_km = round(sum(s["dist_km"] for s in stages if s["dist_km"]), 1)
    print(f"  {len(stages)} stages, {total_km} km total")
    route = {
        "route_id":    route_id,
        "route_type":  route_type,
        "land":        land,
        "name":        name,
        "description": None,
        "start":       stages[0]["start_name"],
        "end":         stages[-1]["end_name"],
        "total_km":    total_km,
        "stages":      stages,
    }
    if extra:
        route.update(extra)
    return route


# Écrins
def scrape_gr54():
    return _geotrek_route(_ECRINS_API, 937571,
        "https://www.grand-tour-ecrins.fr/trek/{}",
        14, "fr-hike", "GR54 Tour de l'Oisans et Écrins",
        route_type="national", extra={"_osm_id": 2909096})

# Mercantour / Alpi Marittime — cross-border FR/IT
def scrape_alpi_marittime():
    return _geotrek_route(_MERCANTOUR_API, 169810,
        "https://rando.marittimemercantour.eu/trek/{}",
        7, "eu-hike", "Grande traversée Alpi Marittime",
        route_type="international")

def scrape_boucle_4_vallees():
    return _geotrek_route(_MERCANTOUR_API, 169700,
        "https://rando.marittimemercantour.eu/trek/{}",
        8, "eu-hike", "La boucle des 4 vallées",
        route_type="international")

def scrape_mont_tenibre():
    return _geotrek_route(_MERCANTOUR_API, 165534,
        "https://rando.marittimemercantour.eu/trek/{}",
        9, "eu-hike", "Tour du Mont Ténibre")

# Mercantour / Alpi Marittime — Italian side (Cuneo/Piedmont)
def scrape_alto_tanaro():
    return _geotrek_route(_MERCANTOUR_API, 154947,
        "https://rando.marittimemercantour.eu/trek/{}",
        44, "it-hike", "Alto Tanaro Tour")

def scrape_alta_via_dei_re():
    return _geotrek_route(_MERCANTOUR_API, 154943,
        "https://rando.marittimemercantour.eu/trek/{}",
        45, "it-hike", "Alta Via dei Re")

def scrape_argentera():
    return _geotrek_route(_MERCANTOUR_API, 167486,
        "https://rando.marittimemercantour.eu/trek/{}",
        46, "it-hike", "Grand Tour de l'Argentera et des Merveilles")

def scrape_trekking_du_loup():
    return _geotrek_route(_MERCANTOUR_API, 169693,
        "https://rando.marittimemercantour.eu/trek/{}",
        47, "it-hike", "Le trekking du loup")

def scrape_giro_marguareis():
    return _geotrek_route(_MERCANTOUR_API, 154945,
        "https://rando.marittimemercantour.eu/trek/{}",
        48, "it-hike", "Giro del Marguareis")

def scrape_tour_marguareis():
    return _geotrek_route(_MERCANTOUR_API, 167509,
        "https://rando.marittimemercantour.eu/trek/{}",
        49, "it-hike", "Tour du parc naturel du Marguareis")

# Mercantour — French side (Alpes-Maritimes)
def scrape_randonnee_couleurs():
    return _geotrek_route(_MERCANTOUR_API, 165899,
        "https://rando.marittimemercantour.eu/trek/{}",
        25, "fr-hike", "La randonnée des couleurs")

def scrape_sentier_azur():
    return _geotrek_route(_MERCANTOUR_API, 167525,
        "https://rando.marittimemercantour.eu/trek/{}",
        26, "fr-hike", "Le sentier d'Azur")

# Mercantour / Alpi Marittime — cross-border (3-stage)
def scrape_alta_via_ligure():
    return _geotrek_route(_MERCANTOUR_API, 168820,
        "https://rando.marittimemercantour.eu/trek/{}",
        10, "eu-hike", "Sur l'Alta Via Ligure")

def scrape_mont_gramondo():
    return _geotrek_route(_MERCANTOUR_API, 168858,
        "https://rando.marittimemercantour.eu/trek/{}",
        11, "eu-hike", "Tour franco-italien du Mont Gramondo")

# Mercantour / Alpi Marittime — Italian side Liguria (Imperia)
def scrape_villages_ligures():
    return _geotrek_route(_MERCANTOUR_API, 169726,
        "https://rando.marittimemercantour.eu/trek/{}",
        50, "it-hike", "Les plus beaux villages Ligures")

# Vanoise (all Savoie, fr-73)
def scrape_vanoise():
    return _geotrek_route(_VANOISE_API, 56199,
        "https://rando.vanoise.com/fr/trek/{}",
        15, "fr-hike", "Tour des glaciers de la Vanoise")

def scrape_grande_casse():
    return _geotrek_route(_VANOISE_API, 56302,
        "https://rando.vanoise.com/fr/trek/{}",
        16, "fr-hike", "Tour de la Grande Casse")

def scrape_mean_martin():
    return _geotrek_route(_VANOISE_API, 56297,
        "https://rando.vanoise.com/fr/trek/{}",
        17, "fr-hike", "Tour de Méan Martin")

def scrape_vallaisonnay():
    return _geotrek_route(_VANOISE_API, 62072,
        "https://rando.vanoise.com/fr/trek/{}",
        18, "fr-hike", "Tour de la Vallaisonnay")

def scrape_gtt3():
    return _geotrek_route(_VANOISE_API, 54825,
        "https://rando.vanoise.com/fr/trek/{}",
        19, "fr-hike", "Grand Tour de Tarentaise - Beaufortain à Val d'Isère")

def scrape_gtt5():
    return _geotrek_route(_VANOISE_API, 54829,
        "https://rando.vanoise.com/fr/trek/{}",
        20, "fr-hike", "Grand Tour de Tarentaise - Traversée des 3 Vallées")

def scrape_gtt6():
    return _geotrek_route(_VANOISE_API, 54831,
        "https://rando.vanoise.com/fr/trek/{}",
        21, "fr-hike", "Grand Tour de Tarentaise - Massif de la Lauzière")

def scrape_tour_la_plagne():
    return _geotrek_route(_VANOISE_API, 56350,
        "https://rando.vanoise.com/fr/trek/{}",
        22, "fr-hike", "Grand Tour de Tarentaise - La Plagne")

def scrape_mont_pourri():
    return _geotrek_route(_VANOISE_API, 56511,
        "https://rando.vanoise.com/fr/trek/{}",
        23, "fr-hike", "Tour du Mont Pourri")

def scrape_gtt1():
    return _geotrek_route(_VANOISE_API, 54821,
        "https://rando.vanoise.com/fr/trek/{}",
        24, "fr-hike", "Grand Tour de Tarentaise - Beaufortain-Mont-Blanc")

def scrape_pointe_echelle():
    return _geotrek_route(_VANOISE_API, 56196,
        "https://rando.vanoise.com/fr/trek/{}",
        27, "fr-hike", "Tour de la Pointe de l'Échelle")


# ---------------------------------------------------------------------------
# High Scardus Trail — high-scardus-trail.com
# ---------------------------------------------------------------------------
# 20 hiking stages (stages 15 and 20 are bus transfers, excluded), ~190 km.
# Crosses North Macedonia (MK), Kosovo (XK), Albania (AL). → eu-hike 12.
# Stage pages: /en/tour/hiking-trail/high-scardus-trail-stage-NN-<slug>/<id>/

HST_BASE = "https://www.high-scardus-trail.com"
HST_STAGES = [
    ( 1, "Staro Selo",              "Mountain Hut Ljuboten",   f"{HST_BASE}/en/tour/hiking-trail/high-scardus-trail-stage-01-staro-selo-mountain-hut-ljuboten/65666968/"),
    ( 2, "Mountain Hut Ljuboten",   "Brezovica",               f"{HST_BASE}/en/tour/hiking-trail/high-scardus-trail-stage-02-mountain-hut-ljuboten-brezovica/65669459/"),
    ( 3, "Brezovica",               "Prevalla",                f"{HST_BASE}/en/tour/hiking-trail/high-scardus-trail-stage-03-brezovica-prevalla/65673318/"),
    ( 4, "Prevalla",                "Gornje Ljubinje",         f"{HST_BASE}/en/tour/hiking-trail/high-scardus-trail-stage-04-prevalla-gornje-ljubinje/65835558/"),
    ( 5, "Gornje Ljubinje",         "Kobilica Hut",            f"{HST_BASE}/en/tour/hiking-trail/high-scardus-trail-stage-05-gornje-ljubinje-kobilica-hut-vejce/66049838/"),
    ( 6, "Kobilica Hut",            "Veshala",                 f"{HST_BASE}/en/tour/hiking-trail/high-scardus-trail-stage-06-kobilica-hut-vejce-veshala-bozovce/65975107/"),
    ( 7, "Veshala",                 "Brod",                    f"{HST_BASE}/en/tour/hiking-trail/high-scardus-trail-stage-07-veshala-bozovce-brod/66215597/"),
    ( 8, "Brod",                    "Restelica",               f"{HST_BASE}/en/tour/hiking-trail/high-scardus-trail-stage-08-brod-restelica/66215632/"),
    ( 9, "Restelica",               "Strezimir",               f"{HST_BASE}/en/tour/hiking-trail/high-scardus-trail-stage-09-restelica-strezimir/66215711/"),
    (10, "Strezimir",               "Radomirë",                f"{HST_BASE}/en/tour/hiking-trail/high-scardus-trail-stage-10-strezimir-radomire/66215678/"),
    (11, "Radomirë",                "Grama",                   f"{HST_BASE}/en/tour/hiking-trail/high-scardus-trail-stage-11-radomire-grama/66215751/"),
    (12, "Grama",                   "Rabdisht",                f"{HST_BASE}/en/tour/hiking-trail/high-scardus-trail-stage-12-grama-rabdisht/66215780/"),
    (13, "Rabdisht",                "Stanet e Hinoskes",       f"{HST_BASE}/en/tour/hiking-trail/high-scardus-trail-stage-13-rabdisht-stanet-e-hinoskes/66215806/"),
    (14, "Stanet e Hinoskes",       "Bitushe",                 f"{HST_BASE}/en/tour/hiking-trail/high-scardus-trail-stage-14-stanet-e-hinoskes-bitushe-modric/66215813/"),
    (15, "Bitushe",                 "Jablanica",               f"{HST_BASE}/en/tour/hiking-trail/high-scardus-trail-stage-16-modric-jablanica/66215823/"),
    (16, "Jablanica",               "Stebleve",                f"{HST_BASE}/en/tour/hiking-trail/high-scardus-trail-stage-17-jablanica-stebleve/66215834/"),
    (17, "Stebleve",                "Qafa e Kryqit",           f"{HST_BASE}/en/tour/hiking-trail/high-scardus-trail-stage-18-stebleve-qafa-e-kryqit/66215841/"),
    (18, "Qafa e Kryqit",           "Vevcani",                 f"{HST_BASE}/en/tour/hiking-trail/high-scardus-trail-stage-19-qafa-e-kryqit-vevcani-velestovo/66215855/"),
    (19, "Vevcani",                 "Mountain Hut Spiridon",   f"{HST_BASE}/en/tour/hiking-trail/high-scardus-trail-stage-21-velestovo-mountain-hut-spiridon/66215863/"),
    (20, "Mountain Hut Spiridon",   "Sveti Naum",              f"{HST_BASE}/en/tour/hiking-trail/high-scardus-trail-stage-22-mountain-hut-spiridon-sveti-naum/66215882/"),
]

_HST_DIST_RE   = re.compile(r'Distance\s*([\d.]+)\s*km',              re.I)
_HST_ASCENT_RE = re.compile(r'Ascent\s*([\d,]+)\s*m',                 re.I)
_HST_DESC_RE   = re.compile(r'Descent\s*([\d,]+)\s*m',                re.I)


def _hst_parse_m(s):
    return int(s.replace(",", "")) if s else None


def scrape_high_scardus():
    print("High Scardus Trail (MK/XK/AL) — fetching 20 stage pages ...")
    stages = []
    for nr, start, end, url in HST_STAGES:
        time.sleep(DELAY)
        html = fetch(url)
        if not html:
            print(f"  stage {nr}: fetch failed — using None for stats")
            dist_km = elev_up = elev_down = None
        else:
            soup = BeautifulSoup(html, "html.parser")
            text = soup.get_text(" ")
            dm = _HST_DIST_RE.search(text)
            am = _HST_ASCENT_RE.search(text)
            ddm = _HST_DESC_RE.search(text)
            dist_km  = float(dm.group(1))  if dm  else None
            elev_up  = _hst_parse_m(am.group(1))  if am  else None
            elev_down = _hst_parse_m(ddm.group(1)) if ddm else None
        print(f"  Stage {nr:2d}  {start} → {end}  ({dist_km} km, ↑{elev_up} ↓{elev_down})")
        stages.append({
            "stage_nr":         nr,
            "start_name":       start,
            "end_name":         end,
            "via":              None,
            "dist_km":          dist_km,
            "elev_up":          elev_up,
            "elev_down":        elev_down,
            "duration_hrs":     None,
            "difficulty":       None,
            "description":      None,
            "arrival_stations": [],
            "sbb_times":        {},
            "_source_url":      url,
        })

    total_km = round(sum(s["dist_km"] for s in stages if s["dist_km"]), 1)
    print(f"  {len(stages)} stages, {total_km} km total")
    return {
        "route_id":   12,
        "route_type": "national",
        "land":       "eu-hike",
        "name":       "High Scardus Trail",
        "description": None,
        "start":      stages[0]["start_name"],
        "end":        stages[-1]["end_name"],
        "total_km":   total_km,
        "stages":     stages,
    }


# ---------------------------------------------------------------------------
# Stråsjöleden — Outdooractive (outdooractive.com), Sweden
# ---------------------------------------------------------------------------
# 16 stages, ~272 km. Korsholmen (Hudiksvall) -> Kilkoja (Ragunda), Hälsingland/
# Jämtland pilgrim trail. -> se-hike 22.
# Found via Outdooractive's plain-text search API (no auth needed):
#   https://www.outdooractive.com/api/search?q=<name>  -> XML list of OA ids
# Each stage page embeds schema.org JSON-LD with exact distance (metres) and
# elevation_ascent/elevation_descent (metres) in `amenityFeature`.

SJ_BASE = "https://www.outdooractive.com"
SJ_STAGES = [
    ( 1, "Korsholmen",      "Enånger",         f"{SJ_BASE}/en/r/22356000/"),
    ( 2, "Enånger",         "Njutånger",       f"{SJ_BASE}/en/r/22356090/"),
    ( 3, "Njutånger",       "Sörforsa",        f"{SJ_BASE}/en/r/23072175/"),
    ( 4, "Sörforsa",        "Nirsgård",        f"{SJ_BASE}/en/r/23083371/"),
    ( 5, "Nirsgård",        "Dellenbaden",     f"{SJ_BASE}/en/r/23169041/"),
    ( 6, "Dellenbaden",     "Mockastorp",      f"{SJ_BASE}/en/r/23169442/"),
    ( 7, "Mockastorp",      "Stråsjö Chapel",  f"{SJ_BASE}/en/r/22862089/"),
    ( 8, "Stråsjö Chapel",  "Sandvik",         f"{SJ_BASE}/en/r/23841657/"),
    ( 9, "Sandvik",         "Hennan",          f"{SJ_BASE}/en/r/23841829/"),
    (10, "Hennan",          "Tallnäs",         f"{SJ_BASE}/en/r/24276710/"),
    (11, "Tallnäs",         "Ramsjö",          f"{SJ_BASE}/en/r/24277001/"),
    (12, "Ramsjö",          "Flomyr",          f"{SJ_BASE}/en/r/24277089/"),
    (13, "Flomyr",          "Haverö",          f"{SJ_BASE}/en/r/24277125/"),
    (14, "Haverö",          "Överturingen",    f"{SJ_BASE}/en/r/31834674/"),
    (15, "Överturingen",    "Rätan",           f"{SJ_BASE}/en/r/31834791/"),
    (16, "Rätan",           "Kilkoja",         f"{SJ_BASE}/en/r/31858302/"),
]


def _oa_stage_stats(html):
    """Extract (dist_km, elev_up, elev_down) from an Outdooractive page's JSON-LD."""
    blobs = re.findall(r'application/ld\+json[^>]*>(.*?)</script>', html, re.S | re.I)
    for blob in blobs:
        blob = blob.strip()
        if 'potentialAction' not in blob:
            continue
        try:
            d = json.loads(blob)
        except json.JSONDecodeError:
            continue
        dist = d.get("potentialAction", {}).get("distance", {}).get("value")
        up = down = None
        for af in d.get("amenityFeature", []):
            if af.get("name") == "elevation_ascent":
                up = af.get("value")
            elif af.get("name") == "elevation_descent":
                down = af.get("value")
        dist_km = round(dist / 1000, 1) if dist else None
        return dist_km, (round(up) if up is not None else None), (round(down) if down is not None else None)
    return None, None, None


def scrape_strasjoleden():
    print("Stråsjöleden (SE) — fetching 16 stage pages ...")
    stages = []
    for nr, start, end, url in SJ_STAGES:
        time.sleep(DELAY)
        html = fetch(url)
        if not html:
            print(f"  stage {nr}: fetch failed — using None for stats")
            dist_km = elev_up = elev_down = None
        else:
            dist_km, elev_up, elev_down = _oa_stage_stats(html)
        print(f"  Stage {nr:2d}  {start} → {end}  ({dist_km} km, ↑{elev_up} ↓{elev_down})")
        stages.append({
            "stage_nr":         nr,
            "start_name":       start,
            "end_name":         end,
            "via":              None,
            "dist_km":          dist_km,
            "elev_up":          elev_up,
            "elev_down":        elev_down,
            "duration_hrs":     None,
            "difficulty":       None,
            "description":      None,
            "arrival_stations": [],
            "sbb_times":        {},
            "_source_url":      url,
        })

    total_km = round(sum(s["dist_km"] for s in stages if s["dist_km"]), 1)
    print(f"  {len(stages)} stages, {total_km} km total")
    return {
        "route_id":   22,
        "route_type": "national",
        "land":       "se-hike",
        "name":       "Stråsjöleden",
        "description": None,
        "start":      stages[0]["start_name"],
        "end":        stages[-1]["end_name"],
        "total_km":   total_km,
        "stages":     stages,
    }


# ---------------------------------------------------------------------------
# Müritz-Nationalpark-Wanderweg — Komoot collection, Germany
# ---------------------------------------------------------------------------
# 9 stages, ~175 km circular route (Waren -> ... -> Waren). OSM relation
# 181787 has no day-stage subroutes; the official park website links to a
# Komoot collection with a per-stage breakdown instead. -> de-hike 73.
# Komoot exposes a plain public JSON API behind its React app:
#   GET https://api.komoot.de/v007/collections/{collectionId}/compilation/
# -> _embedded.items[], each with name, distance (m), elevation_up/_down (m).

MURITZ_COLLECTION_ID = 1470717
MURITZ_STAGE_NAME_RE = re.compile(r'Stage \d+:\s*From\s+(.+?)\s+to\s+(.+?)\s*[–-]')


def scrape_muritz():
    print("Müritz-Nationalpark-Wanderweg (DE) — fetching Komoot collection ...")
    url = f"https://api.komoot.de/v007/collections/{MURITZ_COLLECTION_ID}/compilation/"
    resp = SESSION.get(url, timeout=30)
    resp.raise_for_status()
    items = resp.json()["_embedded"]["items"]

    stages = []
    for it in items:
        m = MURITZ_STAGE_NAME_RE.match(it["name"])
        start, end = m.groups() if m else ("?", "?")
        dist_km = round(it["distance"] / 1000, 1)
        elev_up = round(it["elevation_up"])
        elev_down = round(it["elevation_down"])
        print(f"  Stage {len(stages)+1:2d}  {start} → {end}  ({dist_km} km, ↑{elev_up} ↓{elev_down})")
        stages.append({
            "stage_nr":         len(stages) + 1,
            "start_name":       start,
            "end_name":         end,
            "via":              None,
            "dist_km":          dist_km,
            "elev_up":          elev_up,
            "elev_down":        elev_down,
            "duration_hrs":     None,
            "difficulty":       None,
            "description":      None,
            "arrival_stations": [],
            "sbb_times":        {},
            "_source_url":      f"https://www.komoot.com/tour/{it['id']}",
            "country":          "de",
            "admin1":           "de-mv",
        })

    total_km = round(sum(s["dist_km"] for s in stages if s["dist_km"]), 1)
    print(f"  {len(stages)} stages, {total_km} km total")
    return {
        "route_id":   73,
        "route_type": "regional",
        "land":       "de-hike",
        "name":       "Müritz-Nationalpark-Wanderweg",
        "description": None,
        "start":      stages[0]["start_name"],
        "end":        stages[-1]["end_name"],
        "total_km":   total_km,
        "stages":     stages,
    }


# ---------------------------------------------------------------------------
# gronze.com — shared helper for Spanish Camino routes
# ---------------------------------------------------------------------------
# Stage page format (stats inline text):
#   "Distancia: X,X km Desnivel: X.XXX m X.XXX m Duración: X h [Y min]"
#   H1: "Etapa N[A]?:StartName - EndName[ (variant)]"
# Spanish number conventions: comma = decimal sep; dot = thousands sep.
# gronze.com requires full browser Accept headers (blocks HikingTracker UA).

GRONZE_BASE = "https://www.gronze.com"
_GRONZE_HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "identity",
}
_GRONZE_DIST_RE = re.compile(r'Distancia:[\s\xa0]+([\d,.]+)\s*km',                     re.I)
_GRONZE_ELEV_RE = re.compile(r'Desnivel:[\s\xa0]+([\d,.]+)[\s\xa0]*m[\s\xa0]+([\d,.]+)[\s\xa0]*m', re.I)
_GRONZE_H1_RE   = re.compile(r'Etapa\s+[\d]+[A-Za-z]?:\s*(.+?)\s+-\s+(.+?)(?:\s*\(.*\))?\s*$')


def _gronze_fetch(path):
    url = GRONZE_BASE + path if path.startswith('/') else path
    try:
        r = SESSION.get(url, headers=_GRONZE_HEADERS, timeout=20)
        return r.text if r.status_code == 200 else None
    except Exception as e:
        print(f"  fetch error: {e}")
        return None


def _gronze_elev(s):
    """'1.419' (Spanish thousands sep) → 1419."""
    return int(s.replace('.', '').replace(',', '')) if s else None


def _gronze_parse_stage(nr, path):
    time.sleep(DELAY)
    html = _gronze_fetch(path)
    if not html:
        print(f"  stage {nr}: fetch failed")
        return None

    soup = BeautifulSoup(html, "html.parser")

    start_name = end_name = None
    h1 = soup.find('h1')
    if h1:
        h1_clean = re.sub(r'\s*\(.*\)\s*$', '', h1.get_text(strip=True))
        m = _GRONZE_H1_RE.match(h1_clean)
        if m:
            start_name = m.group(1).strip()
            end_name   = m.group(2).strip()

    dist_km = elev_up = elev_down = None
    # Search distance independently — some pages have no Desnivel
    for node in soup.find_all(string=re.compile('Distancia', re.I)):
        c = node.parent
        for _ in range(5):
            dm = _GRONZE_DIST_RE.search(c.get_text(' ', strip=True))
            if dm:
                dist_km = parse_km(dm.group(1))
                break
            c = c.parent
        if dist_km is not None:
            break
    # Search elevation independently
    for node in soup.find_all(string=re.compile('Desnivel', re.I)):
        c = node.parent
        for _ in range(5):
            em = _GRONZE_ELEV_RE.search(c.get_text(' ', strip=True))
            if em:
                elev_up   = _gronze_elev(em.group(1))
                elev_down = _gronze_elev(em.group(2))
                break
            c = c.parent
        if elev_up is not None:
            break

    print(f"  Stage {nr:2d}  {start_name} → {end_name}  ({dist_km} km, ↑{elev_up} ↓{elev_down})")
    return {"start_name": start_name, "end_name": end_name,
            "dist_km": dist_km, "elev_up": elev_up, "elev_down": elev_down}


def _gronze_route(paths, route_id, land, name, route_type="national"):
    stages = []
    for nr, path in enumerate(paths, 1):
        data = _gronze_parse_stage(nr, path)
        if not data:
            continue
        stages.append({
            "stage_nr":         nr,
            "start_name":       data["start_name"] or f"Stage {nr} start",
            "end_name":         data["end_name"]   or f"Stage {nr} end",
            "via":              None,
            "dist_km":          data["dist_km"],
            "elev_up":          data["elev_up"],
            "elev_down":        data["elev_down"],
            "duration_hrs":     None,
            "difficulty":       None,
            "description":      None,
            "arrival_stations": [],
            "sbb_times":        {},
            "_source_url":      GRONZE_BASE + path,
        })
    if not stages:
        return None
    total_km = round(sum(s["dist_km"] for s in stages if s["dist_km"]), 1)
    print(f"  {len(stages)} stages, {total_km} km total")
    return {
        "route_id":    route_id,
        "route_type":  route_type,
        "land":        land,
        "name":        name,
        "description": None,
        "start":       stages[0]["start_name"],
        "end":         stages[-1]["end_name"],
        "total_km":    total_km,
        "stages":      stages,
    }


# ---------------------------------------------------------------------------
# Camino Francés — gronze.com/camino-frances
# ---------------------------------------------------------------------------
# 33 stages, ~791 km. Saint-Jean-Pied-de-Port → Santiago de Compostela.
# Napoleon route at start; San Martín del Camino branch (not Villar de
# Mazarife); direct Triacastela→Sarria (not via Samos).

_CF_PATHS = [
    "/etapa/saint-jean-pied-port-donibane-garazi/roncesvalles-orreaga",
    "/etapa/roncesvalles-orreaga/zubiri",
    "/etapa/zubiri/pamplona-iruna",
    "/etapa/pamplona-iruna/puente-reina-gares",
    "/etapa/puente-reina-gares/estella-lizarra",
    "/etapa/estella-lizarra/arcos",
    "/etapa/arcos/logrono",
    "/etapa/logrono/najera",
    "/etapa/najera/santo-domingo-calzada",
    "/etapa/santo-domingo-calzada/belorado",
    "/etapa/belorado/san-juan-ortega",
    "/etapa/san-juan-ortega/burgos",
    "/etapa/burgos/hornillos-camino",
    "/etapa/hornillos-camino/castrojeriz",
    "/etapa/castrojeriz/fromista",
    "/etapa/fromista/carrion-condes",
    "/etapa/carrion-condes/terradillos-templarios",
    "/etapa/terradillos-templarios/bercianos-real-camino",
    "/etapa/bercianos-real-camino/mansilla-mulas",
    "/etapa/mansilla-mulas/leon",
    "/etapa/leon/san-martin-camino",
    "/etapa/san-martin-camino/astorga",
    "/etapa/astorga/foncebadon",
    "/etapa/foncebadon/ponferrada",
    "/etapa/ponferrada/villafranca-bierzo",
    "/etapa/villafranca-bierzo/cebreiro",
    "/etapa/cebreiro/triacastela",
    "/etapa/triacastela/sarria",
    "/etapa/sarria/portomarin",
    "/etapa/portomarin/palas-rei",
    "/etapa/palas-rei/arzua",
    "/etapa/arzua/pedrouzo-pino",
    "/etapa/pedrouzo-pino/santiago-compostela",
]


def scrape_camino_frances():
    print("Camino Francés — gronze.com (33 stages)")
    return _gronze_route(_CF_PATHS, 15, "es-hike", "Camino Francés", "international")


# ---------------------------------------------------------------------------
# Via de la Plata — gronze.com/via-plata
# ---------------------------------------------------------------------------
# 37 stages. Sevilla → Santiago de Compostela via the Sanabrés (western)
# branch. Canonical trunk: Sevilla→Granja de Moreruela (23s), then Tábara→
# Puebla de Sanabria→A Gudiña→Laza→Ourense→Santiago (14s).
# Skipped: Benavente branch (joins Camino Francés at Astorga) and the
# Verín alternative north of A Gudiña.

_VDP_PATHS = [
    "/etapa/sevilla/guillena",
    "/etapa/guillena/castilblanco-arroyos",
    "/etapa/castilblanco-arroyos/almaden-plata",
    "/etapa/almaden-plata/monesterio",
    "/etapa/monesterio/fuente-cantos",
    "/etapa/fuente-cantos/zafra",
    "/etapa/zafra/villafranca-barros",
    "/etapa/villafranca-barros/torremejia",
    "/etapa/torremejia/merida",
    "/etapa/merida/alcuescar",
    "/etapa/alcuescar/caceres",
    "/etapa/caceres/embalse-alcantara",
    "/etapa/embalse-alcantara/grimaldo",
    "/etapa/grimaldo/carcaboso",
    "/etapa/carcaboso/aldeanueva-camino",
    "/etapa/aldeanueva-camino/calzada-bejar",
    "/etapa/calzada-bejar/fuenterroble-salvatierra",
    "/etapa/fuenterroble-salvatierra/san-pedro-rozados",
    "/etapa/san-pedro-rozados/salamanca",
    "/etapa/salamanca/cubo-vino",
    "/etapa/cubo-vino/zamora",
    "/etapa/zamora/montamarta",
    "/etapa/montamarta/granja-moreruela",
    "/etapa/granja-moreruela/tabara",
    "/etapa/tabara/santa-marta-tera",
    "/etapa/santa-marta-tera/mombuey",
    "/etapa/mombuey/puebla-sanabria",
    "/etapa/puebla-sanabria/lubian",
    "/etapa/lubian/gudina",
    "/etapa/gudina/laza",
    "/etapa/laza/xunqueira-ambia",
    "/etapa/xunqueira-ambia/ourense",
    "/etapa/ourense/cea",
    "/etapa/cea/castro-dozon",
    "/etapa/castro-dozon/silleda",
    "/etapa/silleda/outeiro-vedra",
    "/etapa/outeiro-vedra/santiago-compostela",
]


def scrape_via_plata():
    print("Via de la Plata — gronze.com (37 stages, Sanabrés branch)")
    return _gronze_route(_VDP_PATHS, 16, "es-hike", "Via de la Plata", "national")


# ---------------------------------------------------------------------------
# Camino Inglés — gronze.com/camino-ingles
# ---------------------------------------------------------------------------
# 7 stages. Two starting branches (A Coruña 2s, Ferrol 3s) converge at
# Hospital de Bruma, then 2 shared stages to Santiago de Compostela.
# Stages 1–2: A Coruña branch. Stages 3–5: Ferrol branch. Stages 6–7: shared.

_CI_PATHS = [
    "/etapa/coruna/sergude",
    "/etapa/sergude/hospital-bruma",
    "/etapa/ferrol/pontedeume",
    "/etapa/pontedeume/betanzos",
    "/etapa/betanzos/hospital-bruma",
    "/etapa/hospital-bruma/sigueiro",
    "/etapa/sigueiro/santiago-compostela",
]


def scrape_camino_ingles():
    print("Camino Inglés — gronze.com (7 stages)")
    return _gronze_route(_CI_PATHS, 17, "es-hike", "Camino Inglés", "national")


# ---------------------------------------------------------------------------
# Camino de Invierno — gronze.com/camino-invierno
# ---------------------------------------------------------------------------
# 11 stages. Ponferrada → Outeiro de Rei (near Santiago). 268 km.

_CINV_PATHS = [
    "/etapa/ponferrada/medulas",
    "/etapa/medulas/xagoaza",
    "/etapa/barco-valdeorras/rua-valdeorras",
    "/etapa/rua-valdeorroas/quiroga",
    "/etapa/quiroga/pobra-do-brollon",
    "/etapa/pobra-do-brollon/monforte-lemos",
    "/etapa/monforte-lemos/chantada",
    "/etapa/chantada/rodeiro",
    "/etapa/rodeiro/lalin",
    "/etapa/lalin/silleda",
    "/etapa/silleda/outeiro-vedra",
]


def scrape_camino_invierno():
    print("Camino de Invierno — gronze.com (11 stages)")
    return _gronze_route(_CINV_PATHS, 18, "es-hike", "Camino de Invierno", "national")


# ---------------------------------------------------------------------------
# Camino Salvador — gronze.com/camino-salvador
# ---------------------------------------------------------------------------
# 7 stages. León → Grado (Asturias). 163 km.
# Connects the Camino Francés (León) to the Camino Primitivo (Oviedo/Grado).

_CS_PATHS = [
    "/etapa/leon/robla",
    "/etapa/robla/poladura-tercia",
    "/etapa/poladura-tercia/pajares",
    "/etapa/pajares/pola-lena",
    "/etapa/pola-lena/mieres",
    "/etapa/mieres/oviedo",
    "/etapa/oviedo/grado",
]


def scrape_camino_salvador():
    print("Camino Salvador — gronze.com (7 stages)")
    return _gronze_route(_CS_PATHS, 19, "es-hike", "Camino Salvador", "national")


# ---------------------------------------------------------------------------
# gronze.com — additional routes (es-hike 20–32, pt-hike 4, fr-hike 30,
#              eu-hike 13–16, it-hike 53)
# All use _gronze_route(). Branching routes include all listed stages.
# ---------------------------------------------------------------------------

# es-hike 20 — Fisterra y Muxía (Santiago→Fisterra/Muxía, 7 stages)
_FISTERRA_PATHS = [
    "/etapa/santiago-compostela/negreira",
    "/etapa/negreira/olveiroa",
    "/etapa/olveiroa/corcubion",
    "/etapa/corcubion/fisterra",
    "/etapa/olveiroa/muxia",
    "/etapa/muxia/fisterra",
    "/etapa/fisterra/faro-finisterre",
]

# es-hike 21 — Camino Aragonés (Somport→Estella, 7 stages; skip Atarés alt)
_ARAGONES_PATHS = [
    "/etapa/somport/jaca",
    "/etapa/jaca/arres",
    "/etapa/arres/ruesta",
    "/etapa/ruesta/sanguesa",
    "/etapa/sanguesa/monreal",
    "/etapa/monreal/puente-reina-gares",
    "/etapa/puente-reina-gares/estella-lizarra",
]

# es-hike 22 — Camino de Madrid (Madrid→Sahagún, 14 stages)
_MADRID_PATHS = [
    "/etapa/madrid/tres-cantos",
    "/etapa/tres-cantos/manzanares-real",
    "/etapa/manzanares-real/cercedilla",
    "/etapa/cercedilla/segovia",
    "/etapa/segovia/santa-maria-real-nieva",
    "/etapa/santa-maria-real-nieva/coca",
    "/etapa/coca/alcazaren",
    "/etapa/alcazaren/valladolid",
    "/etapa/puente-duero/penaflor-hornija",
    "/etapa/penaflor-hornija/medina-rioseco",
    "/etapa/medina-rioseco/cuenca-campos",
    "/etapa/cuenca-campos/santervas-campos",
    "/etapa/santervas-campos/sahagun",
    "/etapa/terradillos-templarios/bercianos-real-camino",
]

# es-hike 23 — Camino Vasco del Litoral (Irun→Burgos/Belorado, 16 stages)
_VASCO_PATHS = [
    "/etapa/irun/hernani",
    "/etapa/hernani/tolosa",
    "/etapa/tolosa/beasain",
    "/etapa/beasain/zegama",
    "/etapa/zegama/salvatierra-agurain",
    "/etapa/salvatierra-agurain/vitoria-gasteiz",
    "/etapa/vitoria-gasteiz/puebla-arganzon",
    "/etapa/puebla-arganzon/haro",
    "/etapa/haro/santo-domingo-calzada",
    "/etapa/santo-domingo-calzada/belorado",
    "/etapa/puebla-arganzon/miranda-ebro",
    "/etapa/miranda-ebro/pancorbo",
    "/etapa/pancorbo/briviesca",
    "/etapa/briviesca/monasterio-rodilla",
    "/etapa/monasterio-rodilla/burgos",
    "/etapa/burgos/hornillos-camino",
]

# es-hike 24 — Camino del Ebro (Deltebre→Nájera, 18 stages)
_EBRO_PATHS = [
    "/etapa/deltebre/rapita",
    "/etapa/rapita/tortosa",
    "/etapa/tortosa/xerta",
    "/etapa/xerta/gandesa",
    "/etapa/gandesa/fabara",
    "/etapa/fabara/caspe",
    "/etapa/caspe/escatron",
    "/etapa/escatron/quinto",
    "/etapa/quinto/burgo-ebro",
    "/etapa/burgo-ebro/zaragoza",
    "/etapa/zaragoza/alagon",
    "/etapa/alagon/gallur",
    "/etapa/gallur/tudela",
    "/etapa/tudela/alfaro",
    "/etapa/alfaro/calahorra",
    "/etapa/calahorra/alcanadre",
    "/etapa/alcanadre/logrono",
    "/etapa/logrono/najera",
]

# es-hike 25 — Camino Vadiniense (San Vicente de la Barquera→León, 11 stages)
_VADINIENSE_PATHS = [
    "/etapa/san-vicente-barquera/cades",
    "/etapa/cades/cicera",
    "/etapa/cicera/potes",
    "/etapa/potes/espinama",
    "/etapa/espinama/portilla-reina",
    "/etapa/portilla-reina/riano",
    "/etapa/riano/cremenes",
    "/etapa/cremenes/cistierna",
    "/etapa/cistierna/gradefes",
    "/etapa/gradefes/puente-villarente",
    "/etapa/mansilla-mulas/leon",
]

# es-hike 26 — Ría de Muros-Noia (5 stages)
_RIA_MUROS_PATHS = [
    "/etapa/muros/cruceiro-roo",
    "/etapa/cruceiro-roo/noia",
    "/etapa/porto-do-son/noia",
    "/etapa/noia/calle-urdilde",
    "/etapa/calle-urdilde/santiago-compostela",
]

# es-hike 27 — Camino de Baztán (Bayonne→Puente la Reina, 6 stages; FR+ES)
_BAZTAN_PATHS = [
    "/etapa/bayonne-baiona/espelette",
    "/etapa/souraide-zuraide/amaiur-maya",
    "/etapa/amaiur-maya/berroeta",
    "/etapa/berroeta/olague",
    "/etapa/olague/pamplona-iruna",
    "/etapa/pamplona-iruna/puente-reina-gares",
]

# es-hike 28 — Camino Catalán (Barcelona→Jaca, 27 stages incl. both BCN starts
#              and both Tàrrega→Zaragoza and Tàrrega→Huesca branches)
_CATALAN_PATHS = [
    "/etapa/barcelona/sant-cugat-valles",
    "/etapa/sant-cugat-valles/esparreguera",
    "/etapa/barcelona/molins-rei",
    "/etapa/molins-rei/esparreguera",
    "/etapa/esparreguera/monestir-montserrat",
    "/etapa/monestir-montserrat/igualada",
    "/etapa/igualada/panadella",
    "/etapa/panadella/tarrega",
    "/etapa/tarrega/palau-danglesola",
    "/etapa/palau-danglesola/lleida",
    "/etapa/lleida/fraga",
    "/etapa/fraga/candasnos",
    "/etapa/candasnos/bujaraloz",
    "/etapa/bujaraloz/pina-ebro",
    "/etapa/pina-ebro/burgo-ebro",
    "/etapa/burgo-ebro/zaragoza",
    "/etapa/tarrega/linyola",
    "/etapa/linyola/algerri",
    "/etapa/algerri/tamarite-litera",
    "/etapa/tamarite-litera/monzon",
    "/etapa/monzon/berbegal",
    "/etapa/berbegal/pueyo-fananas",
    "/etapa/pueyo-fananas/huesca",
    "/etapa/huesca/bolea",
    "/etapa/bolea/pena-estacion",
    "/etapa/pena-estacion/santa-cilia",
    "/etapa/jaca/arres",
]

# es-hike 29 — Camino Olvidado (Bilbao→O Cebreiro, 28 stages incl. branch alt.)
_OLVIDADO_PATHS = [
    "/etapa/bilbao-bilbo/mimetiz-zalla",
    "/etapa/mimetiz-zalla/villasana-mena",
    "/etapa/villasana-mena/espinosa-monteros",
    "/etapa/espinosa-monteros/santelices",
    "/etapa/santelices/arija",
    "/etapa/arija/olea",
    "/etapa/olea/aguilar-campoo",
    "/etapa/aguilar-campoo/cervera-pisuerga",
    "/etapa/cervera-pisuerga/tarilonte-pena",
    "/etapa/tarilonte-pena/guardo",
    "/etapa/guardo/puente-almuhey",
    "/etapa/guardo/caminayo/puente-almuhey",
    "/etapa/puente-almuhey/cistierna",
    "/etapa/cistierna/bonar",
    "/etapa/bonar/robles-valcueva",
    "/etapa/robles-valcueva/robla",
    "/etapa/robla/magdalena-leon",
    "/etapa/bonar/vegacervera",
    "/etapa/vegacervera/pola-gordon",
    "/etapa/pola-gordon/magdalena-leon",
    "/etapa/magdalena-leon/riello",
    "/etapa/riello/fasgar",
    "/etapa/fasgar/iguena",
    "/etapa/iguena/labaniego",
    "/etapa/labaniego/congosto",
    "/etapa/congosto/cabanas-raras",
    "/etapa/cabanas-raras/villafranca-bierzo",
    "/etapa/villafranca-bierzo/cebreiro",
]

# es-hike 30 — Camino de Levante (Valencia→Zamora, 29 stages)
_LEVANTE_PATHS = [
    "/etapa/valencia/algemesi",
    "/etapa/algemesi/xativa",
    "/etapa/xativa/moixent",
    "/etapa/moixent/font-figuera",
    "/etapa/font-figuera/almansa",
    "/etapa/almansa/higueruela",
    "/etapa/higueruela/chinchilla-montearagon",
    "/etapa/chinchilla-montearagon/albacete",
    "/etapa/albacete/roda",
    "/etapa/roda/san-clemente-cuenca",
    "/etapa/san-clemente-cuenca/pedroneras",
    "/etapa/pedroneras/toboso",
    "/etapa/toboso/villa-don-fadrique",
    "/etapa/villa-don-fadrique/tembleque",
    "/etapa/tembleque/mora-toledo",
    "/etapa/mora-toledo/toledo",
    "/etapa/toledo/torrijos",
    "/etapa/torrijos/escalona",
    "/etapa/escalona/san-martin-valdeiglesias",
    "/etapa/san-martin-valdeiglesias/cebreros",
    "/etapa/cebreros/san-bartolome-pinares",
    "/etapa/san-bartolome-pinares/avila",
    "/etapa/avila/gotarrendura",
    "/etapa/gotarrendura/arevalo",
    "/etapa/arevalo/medina-campo",
    "/etapa/medina-campo/siete-iglesias-trabancos",
    "/etapa/siete-iglesias-trabancos/toro",
    "/etapa/toro/zamora",
    "/etapa/zamora/montamarta",
]

# es-hike 31 — Ruta de la Lana (Alicante→Burgos, 30 stages; Sigüenza variant incl.)
_RUTA_LANA_PATHS = [
    "/etapa/alicante/orito",
    "/etapa/orito/petrer",
    "/etapa/petrer/villena",
    "/etapa/villena/caudete",
    "/etapa/caudete/almansa",
    "/etapa/almansa/alpera",
    "/etapa/alpera/alatoz",
    "/etapa/alatoz/casas-ibanez",
    "/etapa/casas-ibanez/villarta",
    "/etapa/villarta/campillo-altobuey",
    "/etapa/campillo-altobuey/monteagudo-salinas",
    "/etapa/monteagudo-salinas/fuentes-cuenca",
    "/etapa/fuentes-cuenca/cuenca",
    "/etapa/cuenca/villar-domingo-garcia",
    "/etapa/villar-domingo-garcia/villaconejos-trabaque",
    "/etapa/villaconejos-trabaque/salmeron-guadalajara",
    "/etapa/salmeron-guadalajara/viana-mondejar",
    "/etapa/viana-mondejar/cifuentes",
    "/etapa/cifuentes/mandayona",
    "/etapa/mandayona/atienza",
    "/etapa/mandayona/siguenza",
    "/etapa/siguenza/atienza",
    "/etapa/atienza/retortillo-soria",
    "/etapa/retortillo-soria/fresno-caracena",
    "/etapa/fresno-caracena/san-esteban-gormaz",
    "/etapa/san-esteban-gormaz/quintanarraya",
    "/etapa/quintanarraya/santo-domingo-silos",
    "/etapa/santo-domingo-silos/mecerreyes",
    "/etapa/mecerreyes/burgos",
    "/etapa/burgos/hornillos-camino",
]

# es-hike 32 — Camino Mozárabe (multiple southern starts→Mérida, 38 stages)
_MOZARABE_PATHS = [
    "/etapa/malaga/almogia",
    "/etapa/almogia/villanueva-concepcion",
    "/etapa/villanueva-concepcion/antequera",
    "/etapa/antequera/villanueva-algaidas",
    "/etapa/villanueva-algaidas/encinas-reales",
    "/etapa/encinas-reales/lucena",
    "/etapa/lucena/dona-mencia",
    "/etapa/dona-mencia/baena",
    "/etapa/almeria/rioja-almeria",
    "/etapa/rioja-almeria/alboloduy",
    "/etapa/alboloduy/abla",
    "/etapa/abla/hueneja",
    "/etapa/hueneja/alquife",
    "/etapa/alquife/guadix",
    "/etapa/guadix/peza",
    "/etapa/peza/quentar",
    "/etapa/quentar/granada",
    "/etapa/granada/pinos-puente",
    "/etapa/pinos-puente/moclin",
    "/etapa/moclin/alcala-real",
    "/etapa/alcala-real/alcaudete",
    "/etapa/jaen/martos",
    "/etapa/martos/alcaudete",
    "/etapa/alcaudete/baena",
    "/etapa/baena/castro-rio",
    "/etapa/castro-rio/santa-cruz-cordoba",
    "/etapa/santa-cruz-cordoba/cordoba",
    "/etapa/cordoba/cerro-muriano",
    "/etapa/cerro-muriano/villaharta",
    "/etapa/villaharta/alcaracejos",
    "/etapa/alcaracejos/hinojosa-duque",
    "/etapa/hinojosa-duque/monterrubio-serena",
    "/etapa/monterrubio-serena/castuera",
    "/etapa/castuera/campanario",
    "/etapa/campanario/don-benito",
    "/etapa/don-benito/torrefresneda",
    "/etapa/torrefresneda/merida",
    "/etapa/merida/alcuescar",
]

# pt-hike 4 — Camino Portugués da Costa (Porto→Pontevedra, 13 stages; incl. branches)
_COSTA_PATHS = [
    "/etapa/porto/labruge",
    "/etapa/labruge/povoa-varzim",
    "/etapa/povoa-varzim/marinhas",
    "/etapa/marinhas/viana-do-castelo",
    "/etapa/viana-do-castelo/caminha",
    "/etapa/caminha/porto-mougas",
    "/etapa/porto-mougas/ramallosa",
    "/etapa/caminha/tui",
    "/etapa/tui/redondela",
    "/etapa/ramallosa/vigo",
    "/etapa/ramallosa/san-miguel-oia/vigo",
    "/etapa/vigo/redondela",
    "/etapa/redondela/pontevedra",
]

# fr-hike 30 — Camino de Vézelay (Vézelay→Saint-Jean-Pied-de-Port, 51 stages)
# Main Berry branch (via Bourges/Argenton) + shared Limoges/Périgueux section +
# Bazas branch to Saint-Jean-Pied-de-Port. Alternative Nevers branch included.
# Incomplete Aiguillon branch (Bergerac→Eauze) excluded.
_VEZELAY_PATHS = [
    "/etapa/vezelay/saint-germain-des-bois-nievre",
    "/etapa/saint-germain-des-bois-nievre/champlemy",
    "/etapa/champlemy/charite-sur-loire",
    "/etapa/charite-sur-loire/baugy",
    "/etapa/baugy/bourges",
    "/etapa/bourges/charost",
    "/etapa/charost/neuvy-pailloux",
    "/etapa/neuvy-pailloux/chateauroux",
    "/etapa/chateauroux/velles",
    "/etapa/velles/argenton-sur-creuse",
    "/etapa/argenton-sur-creuse/gargilesse",
    "/etapa/vezelay/anthien",
    "/etapa/anthien/saint-reverien",
    "/etapa/saint-reverien/premery",
    "/etapa/premery/nevers",
    "/etapa/nevers/saint-pierre-le-moutier",
    "/etapa/saint-pierre-le-moutier/lurcy-levis",
    "/etapa/lurcy-levis/ainay-le-chateau",
    "/etapa/ainay-le-chateau/saint-amand-montrond",
    "/etapa/saint-amand-montrond/le-chatelet-cher",
    "/etapa/le-chatelet-cher/chatre",
    "/etapa/chatre/neuvy-saint-sepulchre",
    "/etapa/neuvy-saint-sepulchre/gargilesse",
    "/etapa/gargilesse/crozant",
    "/etapa/crozant/souterraine",
    "/etapa/souterraine/benevent-labbaye",
    "/etapa/benevent-labbaye/le-pont-du-dognon",
    "/etapa/le-pont-du-dognon/saint-leonard-noblat",
    "/etapa/saint-leonard-noblat/limoges",
    "/etapa/limoges/les-cars",
    "/etapa/les-cars/coquille",
    "/etapa/coquille/thiviers",
    "/etapa/thiviers/sorges",
    "/etapa/sorges/perigueux",
    "/etapa/perigueux/douville",
    "/etapa/douville/bergerac",
    "/etapa/bergerac/sainte-foy-grande",
    "/etapa/sainte-foy-grande/saint-ferme",
    "/etapa/saint-ferme/reole",
    "/etapa/reole/auros",
    "/etapa/auros/bazas",
    "/etapa/bazas/captieux",
    "/etapa/captieux/roquefort-landas",
    "/etapa/roquefort-landas/mont-marsan",
    "/etapa/mont-marsan/saint-sever",
    "/etapa/saint-sever/hagetmau",
    "/etapa/hagetmau/sault-navailles",
    "/etapa/sault-navailles/orthez",
    "/etapa/orthez/sauveterre-bearn",
    "/etapa/sauveterre-bearn/ostabat",
    "/etapa/ostabat/saint-jean-pied-port-donibane-garazi",
]

# eu-hike 13 — Via Gebennensis (Geneva→Le Puy-en-Velay, 17 stages; CH/FR)
_GEBENNENSIS_PATHS = [
    "/etapa/geneve/col-du-mont-sion",
    "/etapa/col-du-mont-sion/frangy",
    "/etapa/frangy/serrieres-en-chautagne",
    "/etapa/serrieres-en-chautagne/yenne",
    "/etapa/yenne/saint-genix-sur-guiers",
    "/etapa/saint-genix-sur-guiers/le-pin-isere",
    "/etapa/le-pin-isere/cote-saint-andre",
    "/etapa/cote-saint-andre/revel-tourdan",
    "/etapa/revel-tourdan/saint-romain-surieu",
    "/etapa/saint-romain-surieu/chavanay",
    "/etapa/chavanay/bourg-argental",
    "/etapa/bourg-argental/les-setoux",
    "/etapa/les-setoux/montfaucon-en-velay",
    "/etapa/montfaucon-en-velay/araules",
    "/etapa/araules/saint-julien-chapteuil",
    "/etapa/saint-julien-chapteuil/le-puy-en-velay",
    "/etapa/le-puy-en-velay/saint-privat-dallier",
]

# eu-hike 14 — Camino de Arles (Arles→Jaca, 34 stages; FR/ES)
_ARLES_PATHS = [
    "/etapa/arles/saint-gilles-gard",
    "/etapa/saint-gilles-gard/gallargues-le-montueux",
    "/etapa/gallargues-le-montueux/vendargues",
    "/etapa/vendargues/montpellier",
    "/etapa/montpellier/montarnaud",
    "/etapa/montarnaud/saint-guilhem-le-desert",
    "/etapa/saint-guilhem-le-desert/saint-jean-blaquiere",
    "/etapa/saint-jean-blaquiere/lodeve",
    "/etapa/lodeve/lunas",
    "/etapa/lunas/saint-gervais-sur-mare",
    "/etapa/saint-gervais-sur-mare/murat-sur-vebre",
    "/etapa/murat-sur-vebre/salvetat-sur-agout",
    "/etapa/salvetat-sur-agout/angles-tarn",
    "/etapa/angles-tarn/boissezon",
    "/etapa/boissezon/castres",
    "/etapa/castres/dourgne",
    "/etapa/dourgne/les-casses",
    "/etapa/les-casses/avignonet-lauragais",
    "/etapa/avignonet-lauragais/baziege",
    "/etapa/baziege/toulouse",
    "/etapa/toulouse/leguevin",
    "/etapa/leguevin/giscaro",
    "/etapa/giscaro/lisle-arne",
    "/etapa/lisle-arne/auch",
    "/etapa/auch/lisle-noe",
    "/etapa/lisle-noe/marciac",
    "/etapa/marciac/vidouze",
    "/etapa/vidouze/morlaas",
    "/etapa/morlaas/lescar",
    "/etapa/lescar/oloron-sainte-marie",
    "/etapa/oloron-sainte-marie/sarrance",
    "/etapa/sarrance/borce",
    "/etapa/borce/somport",
    "/etapa/somport/jaca",
]

# eu-hike 15 — Camino del Piamonte (Carcassonne→Roncesvalles, 23 stages; FR/ES)
_PIAMONTE_PATHS = [
    "/etapa/carcassonne/arzens",
    "/etapa/arzens/fanjeaux",
    "/etapa/fanjeaux/mirepoix",
    "/etapa/mirepoix/pamiers",
    "/etapa/pamiers/le-mas-dazil",
    "/etapa/le-mas-dazil/saint-lizier",
    "/etapa/saint-lizier/castillon-en-couserans",
    "/etapa/castillon-en-couserans/portet-daspet",
    "/etapa/portet-daspet/juzet-dizaut",
    "/etapa/juzet-dizaut/saint-bertrand-comminges",
    "/etapa/saint-bertrand-comminges/montserie",
    "/etapa/montserie/bourg-bigorre",
    "/etapa/bourg-bigorre/bagneres-bigorre",
    "/etapa/bagneres-bigorre/germs-sur-loussouet",
    "/etapa/germs-sur-loussouet/lourdes",
    "/etapa/lourdes/asson",
    "/etapa/asson/arudy",
    "/etapa/arudy/oloron-sainte-marie",
    "/etapa/oloron-sainte-marie/lhopital-saint-blaise",
    "/etapa/lhopital-saint-blaise/mauleon-licharre",
    "/etapa/mauleon-licharre/saint-just-ibarre",
    "/etapa/saint-just-ibarre/saint-jean-pied-port-donibane-garazi",
    "/etapa/saint-jean-pied-port-donibane-garazi/roncesvalles-orreaga",
]

# eu-hike 16 — Via Francígena (Lausanne→Roma, 51 stages; CH/IT)
_FRANCIGENA_PATHS = [
    "/etapa/lausanne/vevey",
    "/etapa/vevey/aigle",
    "/etapa/aigle/saint-maurice-valais",
    "/etapa/saint-maurice-valais/martigny",
    "/etapa/martigny/orsieres",
    "/etapa/orsieres/bourg-saint-pierre",
    "/etapa/bourg-saint-pierre/col-du-grand-saint-bernard",
    "/etapa/col-du-grand-saint-bernard/etroubles",
    "/etapa/etroubles/aosta",
    "/etapa/aosta/chatillon-italia",
    "/etapa/chatillon-italia/verres",
    "/etapa/verres/pont-saint-martin",
    "/etapa/pont-saint-martin/ivrea",
    "/etapa/ivrea/viverone",
    "/etapa/viverone/santhia",
    "/etapa/santhia/vercelli",
    "/etapa/vercelli/robbio",
    "/etapa/robbio/tromello",
    "/etapa/tromello/pavia",
    "/etapa/pavia/belgioioso",
    "/etapa/belgioioso/orio-litta",
    "/etapa/orio-litta/piacenza",
    "/etapa/piacenza/fiorenzuola-darda",
    "/etapa/fiorenzuola-darda/fidenza",
    "/etapa/fidenza/medesano",
    "/etapa/medesano/sivizzano",
    "/etapa/sivizzano/berceto",
    "/etapa/berceto/pontremoli",
    "/etapa/pontremoli/aulla",
    "/etapa/aulla/sarzana",
    "/etapa/sarzana/massa",
    "/etapa/massa/camaiore",
    "/etapa/camaiore/lucca",
    "/etapa/lucca/altopascio",
    "/etapa/altopascio/san-miniato",
    "/etapa/san-miniato/gambassi-terme",
    "/etapa/gambassi-terme/san-gimignano",
    "/etapa/san-gimignano/monteriggioni",
    "/etapa/monteriggioni/siena",
    "/etapa/siena/ponte-darbia",
    "/etapa/ponte-darbia/san-quirico-dorcia",
    "/etapa/san-quirico-dorcia/radicofani",
    "/etapa/radicofani/acquapendente",
    "/etapa/acquapendente/bolsena",
    "/etapa/bolsena/montefiascone",
    "/etapa/montefiascone/viterbo",
    "/etapa/viterbo/vetralla",
    "/etapa/vetralla/sutri",
    "/etapa/sutri/campagnano-di-roma",
    "/etapa/campagnano-di-roma/storta",
    "/etapa/storta/roma",
]

# it-hike 53 — Camino di San Francesco (Roma→La Verna, 23 stages)
_SAN_FRANCESCO_PATHS = [
    "/etapa/roma/monte-sacro",
    "/etapa/monte-sacro/monterotondo",
    "/etapa/monterotondo/ponticelli-di-scandriglia",
    "/etapa/ponticelli-di-scandriglia/poggio-san-lorenzo",
    "/etapa/poggio-san-lorenzo/rieti",
    "/etapa/rieti/poggio-bustone",
    "/etapa/poggio-bustone/piediluco",
    "/etapa/piediluco/ferentillo",
    "/etapa/ferentillo/spoleto",
    "/etapa/spoleto/poreta",
    "/etapa/poreta/trevi",
    "/etapa/trevi/spello",
    "/etapa/spello/assisi",
    "/etapa/assisi/valfabbrica",
    "/etapa/valfabbrica/san-pietro-vigneto",
    "/etapa/san-pietro-vigneto/gubbio",
    "/etapa/gubbio/pietralunga",
    "/etapa/pietralunga/citta-di-castello",
    "/etapa/citta-di-castello/citerna",
    "/etapa/citerna/sansepolcro",
    "/etapa/sansepolcro/pian-della-capanna",
    "/etapa/pian-della-capanna/pieve-santo-stefano",
    "/etapa/pieve-santo-stefano/verna",
]


def scrape_fisterra():
    print("Fisterra y Muxía — gronze.com (7 stages)")
    return _gronze_route(_FISTERRA_PATHS, 20, "es-hike", "Fisterra y Muxía")

def scrape_aragones():
    print("Camino Aragonés — gronze.com (7 stages)")
    return _gronze_route(_ARAGONES_PATHS, 21, "es-hike", "Camino Aragonés")

def scrape_camino_madrid():
    print("Camino de Madrid — gronze.com (14 stages)")
    return _gronze_route(_MADRID_PATHS, 22, "es-hike", "Camino de Madrid")

def scrape_camino_vasco():
    print("Camino Vasco del Litoral — gronze.com (16 stages)")
    return _gronze_route(_VASCO_PATHS, 23, "es-hike", "Camino Vasco del Litoral")

def scrape_camino_ebro():
    print("Camino del Ebro — gronze.com (18 stages)")
    return _gronze_route(_EBRO_PATHS, 24, "es-hike", "Camino del Ebro")

def scrape_camino_vadiniense():
    print("Camino Vadiniense — gronze.com (11 stages)")
    return _gronze_route(_VADINIENSE_PATHS, 25, "es-hike", "Camino Vadiniense")

def scrape_ria_muros():
    print("Ría de Muros-Noia — gronze.com (5 stages)")
    return _gronze_route(_RIA_MUROS_PATHS, 26, "es-hike", "Ría de Muros-Noia")

def scrape_camino_baztan():
    print("Camino de Baztán — gronze.com (6 stages, FR+ES)")
    return _gronze_route(_BAZTAN_PATHS, 27, "es-hike", "Camino de Baztán", "international")

def scrape_camino_catalan():
    print("Camino Catalán — gronze.com (27 stages)")
    return _gronze_route(_CATALAN_PATHS, 28, "es-hike", "Camino Catalán")

def scrape_camino_olvidado():
    print("Camino Olvidado — gronze.com (28 stages)")
    return _gronze_route(_OLVIDADO_PATHS, 29, "es-hike", "Camino Olvidado")

def scrape_camino_levante():
    print("Camino de Levante — gronze.com (29 stages)")
    return _gronze_route(_LEVANTE_PATHS, 30, "es-hike", "Camino de Levante")

def scrape_ruta_lana():
    print("Ruta de la Lana — gronze.com (30 stages)")
    return _gronze_route(_RUTA_LANA_PATHS, 31, "es-hike", "Ruta de la Lana")

def scrape_camino_mozarabe():
    print("Camino Mozárabe — gronze.com (38 stages, multiple starts)")
    return _gronze_route(_MOZARABE_PATHS, 32, "es-hike", "Camino Mozárabe")

def scrape_camino_portugues_costa():
    print("Camino Portugués da Costa — gronze.com (13 stages)")
    return _gronze_route(_COSTA_PATHS, 4, "pt-hike", "Camino Portugués da Costa", "international")

def scrape_camino_vezelay():
    print("Camino de Vézelay — gronze.com (51 stages)")
    return _gronze_route(_VEZELAY_PATHS, 30, "fr-hike", "Camino de Vézelay", "national")

def scrape_via_gebennensis():
    print("Via Gebennensis — gronze.com (17 stages, CH/FR)")
    return _gronze_route(_GEBENNENSIS_PATHS, 13, "eu-hike", "Via Gebennensis", "international")

def scrape_camino_arles():
    print("Camino de Arles — gronze.com (34 stages, FR/ES)")
    return _gronze_route(_ARLES_PATHS, 14, "eu-hike", "Camino de Arles", "international")

def scrape_camino_piamonte():
    print("Camino del Piamonte — gronze.com (23 stages, FR/ES)")
    return _gronze_route(_PIAMONTE_PATHS, 15, "eu-hike", "Camino del Piamonte", "international")

def scrape_via_francigena():
    print("Via Francígena — gronze.com (51 stages, CH/IT)")
    return _gronze_route(_FRANCIGENA_PATHS, 16, "eu-hike", "Via Francígena", "international")

def scrape_camino_san_francesco():
    print("Camino di San Francesco — gronze.com (23 stages)")
    return _gronze_route(_SAN_FRANCESCO_PATHS, 53, "it-hike", "Camino di San Francesco")


_CAMINO_NORTE_PATHS = [
    "/etapa/bayonne-baiona/saint-jean-luz-donibane-lohizune",
    "/etapa/saint-jean-luz-donibane-lohizune/irun",
    "/etapa/irun/san-sebastian-donostia",
    "/etapa/san-sebastian-donostia/zarautz",
    "/etapa/zarautz/deba",
    "/etapa/deba/markina-xemein",
    "/etapa/markina-xemein/gernika",
    "/etapa/gernika/lezama",
    "/etapa/lezama/bilbao-bilbo",
    "/etapa/bilbao-bilbo/portugalete",          # 10A official
    "/etapa/portugalete/castro-urdiales",
    "/etapa/castro-urdiales/laredo",
    "/etapa/laredo/guemes",
    "/etapa/guemes/santander",
    "/etapa/santander/santillana-mar",
    "/etapa/santillana-mar/comillas",
    "/etapa/comillas/colombres",
    "/etapa/colombres/llanes",
    "/etapa/llanes/ribadesella",
    "/etapa/ribadesella/colunga",
    "/etapa/colunga/villaviciosa",
    "/etapa/villaviciosa/gijon",                # coastal main route
    "/etapa/gijon/aviles",
    "/etapa/aviles/muros-nalon",
    "/etapa/muros-nalon/soto-luina",
    "/etapa/soto-luina/cadavedo",
    "/etapa/cadavedo/luarca",
    "/etapa/luarca/caridad",
    "/etapa/caridad/ribadeo",                   # 29A official
    "/etapa/ribadeo/gondan",
    "/etapa/gondan/mondonedo",
    "/etapa/mondonedo/abadin",
    "/etapa/abadin/vilalba",
    "/etapa/vilalba/baamonde",
    "/etapa/baamonde/sobrado-dos-monxes",       # 35A traditional
    "/etapa/sobrado-dos-monxes/arzua",
]


def scrape_camino_norte():
    print("Camino del Norte — gronze.com (36 stages, Bayonne → Arzúa; FR/ES)")
    return _gronze_route(_CAMINO_NORTE_PATHS, 14, "es-hike", "Camino del Norte", "international")


_TOURS_PARIS_PATHS = [
    # Paris → Tours via Orléans (main route, 10 stages)
    "/etapa/paris/ville-du-bois",
    "/etapa/ville-du-bois/etampes",
    "/etapa/etampes/angerville",
    "/etapa/angerville/artenay",
    "/etapa/artenay/orleans",
    "/etapa/orleans/beaugency",
    "/etapa/beaugency/blois",
    "/etapa/blois/chaumont-sur-loire",
    "/etapa/chaumont-sur-loire/amboise",
    "/etapa/amboise/tours",
    # Tours → Ostabat (shared trunk, 26 stages)
    "/etapa/tours/sorigny",
    "/etapa/sorigny/sainte-maure-touraine",
    "/etapa/sainte-maure-touraine/dange-saint-romain",
    "/etapa/dange-saint-romain/chatellerault",
    "/etapa/chatellerault/poitiers",
    "/etapa/poitiers/lusignan",
    "/etapa/lusignan/chenay",
    "/etapa/chenay/melle",
    "/etapa/melle/aulnay",
    "/etapa/aulnay/saint-jean-dangely",
    "/etapa/saint-jean-dangely/saintes",
    "/etapa/saintes/pons-charente-maritime",
    "/etapa/pons-charente-maritime/mirambeau",
    "/etapa/mirambeau/saint-aubin-blaye",
    "/etapa/saint-aubin-blaye/blaye",
    "/etapa/blaye/blanquefort",
    "/etapa/blanquefort/bordeaux",
    "/etapa/bordeaux/le-barp",
    "/etapa/le-barp/saugnacq-et-muret",
    "/etapa/saugnacq-et-muret/labouheyre",
    "/etapa/labouheyre/onesse-laharie",
    "/etapa/onesse-laharie/taller",
    "/etapa/taller/dax",
    "/etapa/dax/peyrehorade",
    "/etapa/peyrehorade/bergouey",
    "/etapa/bergouey/ostabat",
]


def scrape_camino_tours_paris():
    print("Camino de Tours y París — gronze.com (36 stages, Paris → Ostabat; FR)")
    return _gronze_route(_TOURS_PARIS_PATHS, 5, "fr-hike", "Camino de Tours y París", "national")


_SAN_JACOPO_PATHS = [
    "/etapa/firenze/prato",
    "/etapa/prato/pistoia",
    "/etapa/pistoia/pescia",
    "/etapa/pescia/lucca",
    "/etapa/lucca/pisa",
    "/etapa/pisa/tirrenia",
    "/etapa/tirrenia/chiesa-di-san-jacopo-acquaviva-livorno",
]

_LEBANIEGO_PATHS = [
    "/etapa/palencia/amayuelas-abajo",
    "/etapa/amayuelas-abajo/fromista",
    "/etapa/fromista/osorno-mayor",
    "/etapa/osorno-mayor/herrera-pisuerga",
    "/etapa/herrera-pisuerga/perazancas-ojeda",
    "/etapa/perazancas-ojeda/cervera-pisuerga",
    "/etapa/cervera-pisuerga/san-salvador-cantamuda",
    "/etapa/san-salvador-cantamuda/camasobres",
    "/etapa/camasobres/pesaguero",
    "/etapa/pesaguero/monasterio-santo-toribio-liebana",
]


def scrape_san_jacopo():
    print("Camino San Jacopo in Toscana — gronze.com (7 stages, Firenze → Livorno)")
    return _gronze_route(_SAN_JACOPO_PATHS, 54, "it-hike", "Camino San Jacopo in Toscana")

def scrape_camino_lebaniego():
    print("Camino Lebaniégo Castellano — gronze.com (10 stages, Palencia → Liébana)")
    return _gronze_route(_LEBANIEGO_PATHS, 34, "es-hike", "Camino Lebaniégo Castellano")


_VIA_AUGUSTA_PATHS = [
    "/etapa/cadiz/puerto-real",
    "/etapa/puerto-real/jerez-frontera",
    "/etapa/jerez-frontera/cuervo-sevilla",
    "/etapa/cuervo-sevilla/cabezas-san-juan",
    "/etapa/cabezas-san-juan/utrera",
    "/etapa/utrera/alcala-guadaira",
    "/etapa/alcala-guadaira/sevilla",
]

_PORTUGUES_INTERIOR_PATHS = [
    "/etapa/coimbra/penacova",
    "/etapa/penacova/mortagua",
    "/etapa/mortagua/tondela",
    "/etapa/tondela/viseu",
    "/etapa/viseu/almargem",
    "/etapa/almargem/ribolhos",
    "/etapa/ribolhos/bigorne",
    "/etapa/bigorne/lamego",
    "/etapa/lamego/santa-marta-penaguiao",
    "/etapa/santa-marta-penaguiao/vila-real",
    "/etapa/vila-real/vila-pouca-aguiar",
    "/etapa/vila-pouca-aguiar/vidago",
    "/etapa/vidago/chaves",
    "/etapa/chaves/verin",
]


def scrape_via_augusta():
    print("Vía Augusta — gronze.com (7 stages, Cádiz → Sevilla)")
    return _gronze_route(_VIA_AUGUSTA_PATHS, 33, "es-hike", "Vía Augusta")

def scrape_camino_portugues_interior():
    print("Camino Portugués Interior — gronze.com (14 stages, Coimbra → Verín)")
    return _gronze_route(_PORTUGUES_INTERIOR_PATHS, 5, "pt-hike", "Camino Portugués Interior", "international")


# ---------------------------------------------------------------------------
# UK cycling routes — hardcoded (official sites JS-rendered, no OSM day stages)
# Sources: Sustrans/NCN official guidebooks and CyclingUK route information.
# Distances are guidebook estimates and may vary from GPS tracks.
# ---------------------------------------------------------------------------

SEA_TO_SEA_URL = "https://www.sustrans.org.uk/national-cycle-network/sea-to-sea-c2c"
SEA_TO_SEA_STAGES = [
    # Southern (Whitehaven) route → Sunderland. 6 stages, ~203 km.
    (1, "Whitehaven",        "Ennerdale Bridge",       26.0),
    (2, "Ennerdale Bridge",  "Penrith",                51.0),
    (3, "Penrith",           "Alston",                 43.0),
    (4, "Alston",            "Stanhope",               23.0),
    (5, "Stanhope",          "Consett",                27.0),
    (6, "Consett",           "Sunderland",             33.0),
]


def scrape_sea_to_sea():
    print("C2C Sea to Sea (cycling) — hardcoded (NCN 71, Whitehaven → Sunderland)")
    stages = []
    for nr, start, end, km in SEA_TO_SEA_STAGES:
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
            "_source_url":      SEA_TO_SEA_URL,
        })
        print(f"  Stage {nr}  {start} → {end} ({km} km)")
    total_km = round(sum(s["dist_km"] for s in stages), 1)
    print(f"  {len(stages)} stages, {total_km} km total")
    return {
        "route_id":   1,
        "route_type": "national",
        "land":       "uk-cycle",
        "name":       "C2C Sea to Sea",
        "description": (
            "The C2C (Sea to Sea) is one of the UK's most popular long-distance "
            "cycling routes, crossing northern England from the Irish Sea at "
            "Whitehaven to the North Sea at Sunderland. NCN Route 71 traverses "
            "the Lake District fells and the North Pennines, including the climb "
            "over Hartside Pass at 580m."
        ),
        "start":    "Whitehaven",
        "end":      "Sunderland",
        "total_km": total_km,
        "stages":   stages,
    }


WAY_OF_THE_ROSES_URL = "https://www.wayoftheroses.co.uk/"
WAY_OF_THE_ROSES_STAGES = [
    # Morecambe → Bridlington. 7 stages, ~260 km.
    (1, "Morecambe",         "Settle",           65.0),
    (2, "Settle",            "Skipton",          23.0),
    (3, "Skipton",           "Ripon",            57.0),
    (4, "Ripon",             "York",             35.0),
    (5, "York",              "Market Weighton",  33.0),
    (6, "Market Weighton",   "Beverley",         17.0),
    (7, "Beverley",          "Bridlington",      30.0),
]


def scrape_way_of_the_roses():
    print("Way of the Roses (cycling) — hardcoded (Morecambe → Bridlington)")
    stages = []
    for nr, start, end, km in WAY_OF_THE_ROSES_STAGES:
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
            "_source_url":      WAY_OF_THE_ROSES_URL,
        })
        print(f"  Stage {nr}  {start} → {end} ({km} km)")
    total_km = round(sum(s["dist_km"] for s in stages), 1)
    print(f"  {len(stages)} stages, {total_km} km total")
    return {
        "route_id":   2,
        "route_type": "national",
        "land":       "uk-cycle",
        "name":       "Way of the Roses",
        "description": (
            "The Way of the Roses is a coast-to-coast cycling route crossing northern "
            "England from Morecambe Bay on the Irish Sea to Bridlington on the North "
            "Sea. The 260 km route passes through Lancashire, the Yorkshire Dales, "
            "Nidderdale, York, and the Yorkshire Wolds."
        ),
        "start":    "Morecambe",
        "end":      "Bridlington",
        "total_km": total_km,
        "stages":   stages,
    }


HADRIANS_CYCLEWAY_URL = "https://www.visitnorthumberland.com/things-to-do/cycling/hadrians-cycleway"
HADRIANS_CYCLEWAY_STAGES = [
    # Ravenglass → South Shields. 6 stages, ~224 km. NCN Route 72.
    (1, "Ravenglass",            "Whitehaven",            55.0),
    (2, "Whitehaven",            "Silloth",               57.0),
    (3, "Silloth",               "Carlisle",              30.0),
    (4, "Carlisle",              "Hexham",                43.0),
    (5, "Hexham",                "Newcastle upon Tyne",   23.0),
    (6, "Newcastle upon Tyne",   "South Shields",         16.0),
]


def scrape_hadrians_cycleway():
    print("Hadrian's Cycleway — hardcoded (NCN 72, Ravenglass → South Shields)")
    stages = []
    for nr, start, end, km in HADRIANS_CYCLEWAY_STAGES:
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
            "_source_url":      HADRIANS_CYCLEWAY_URL,
        })
        print(f"  Stage {nr}  {start} → {end} ({km} km)")
    total_km = round(sum(s["dist_km"] for s in stages), 1)
    print(f"  {len(stages)} stages, {total_km} km total")
    return {
        "route_id":   3,
        "route_type": "national",
        "land":       "uk-cycle",
        "name":       "Hadrian's Cycleway",
        "description": (
            "Hadrian's Cycleway (NCN Route 72) follows the route of Hadrian's Wall "
            "from Ravenglass on the Cumbrian coast to South Shields on the River Tyne. "
            "The 224 km route combines a spectacular coastal section through Cumbria "
            "with an inland leg along the Wall corridor through Carlisle and Hexham."
        ),
        "start":    "Ravenglass",
        "end":      "South Shields",
        "total_km": total_km,
        "stages":   stages,
    }


LON_LAS_CYMRU_URL = "https://www.sustrans.org.uk/national-cycle-network/lon-las-cymru"
LON_LAS_CYMRU_STAGES = [
    # Holyhead → Cardiff. 9 stages, ~352 km. NCN Route 8.
    (1, "Holyhead",         "Caernarfon",       25.0),
    (2, "Caernarfon",       "Porthmadog",       38.0),
    (3, "Porthmadog",       "Dolgellau",        44.0),
    (4, "Dolgellau",        "Machynlleth",      44.0),
    (5, "Machynlleth",      "Llanidloes",       44.0),
    (6, "Llanidloes",       "Rhayader",         24.0),
    (7, "Rhayader",         "Brecon",           59.0),
    (8, "Brecon",           "Merthyr Tydfil",   33.0),
    (9, "Merthyr Tydfil",   "Cardiff",          41.0),
]


def scrape_lon_las_cymru():
    print("Lôn Las Cymru — hardcoded (NCN 8, Holyhead → Cardiff)")
    stages = []
    for nr, start, end, km in LON_LAS_CYMRU_STAGES:
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
            "_source_url":      LON_LAS_CYMRU_URL,
        })
        print(f"  Stage {nr}  {start} → {end} ({km} km)")
    total_km = round(sum(s["dist_km"] for s in stages), 1)
    print(f"  {len(stages)} stages, {total_km} km total")
    return {
        "route_id":   4,
        "route_type": "national",
        "land":       "uk-cycle",
        "name":       "Lôn Las Cymru",
        "description": (
            "Lôn Las Cymru (NCN Route 8) traverses Wales from Holyhead on Anglesey "
            "to Cardiff, passing through Snowdonia, the Cambrian Mountains, and the "
            "Brecon Beacons. Much of the northern section follows disused railway "
            "trackbeds (Lôn Las Menai, Lôn Eifion, Mawddach Trail) before climbing "
            "through remote mid-Wales. The southern leg descends via the Taff Trail."
        ),
        "start":    "Holyhead",
        "end":      "Cardiff",
        "total_km": total_km,
        "stages":   stages,
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
    "boucle-4-vallees":   scrape_boucle_4_vallees,
    "mont-tenibre":       scrape_mont_tenibre,
    "alto-tanaro":        scrape_alto_tanaro,
    "alta-via-dei-re":    scrape_alta_via_dei_re,
    "argentera":          scrape_argentera,
    "trekking-du-loup":   scrape_trekking_du_loup,
    "giro-marguareis":    scrape_giro_marguareis,
    "tour-marguareis":    scrape_tour_marguareis,
    "randonnee-couleurs": scrape_randonnee_couleurs,
    "vanoise":            scrape_vanoise,
    "grande-casse":       scrape_grande_casse,
    "mean-martin":        scrape_mean_martin,
    "vallaisonnay":       scrape_vallaisonnay,
    "gtt3":               scrape_gtt3,
    "gtt5":               scrape_gtt5,
    "gtt6":               scrape_gtt6,
    "tour-la-plagne":     scrape_tour_la_plagne,
    "mont-pourri":        scrape_mont_pourri,
    "gtt1":               scrape_gtt1,
    "pointe-echelle":     scrape_pointe_echelle,
    "sentier-azur":       scrape_sentier_azur,
    "alta-via-ligure":    scrape_alta_via_ligure,
    "mont-gramondo":      scrape_mont_gramondo,
    "villages-ligures":   scrape_villages_ligures,
    "high-scardus":       scrape_high_scardus,
    "strasjoleden":       scrape_strasjoleden,
    "muritz":             scrape_muritz,
    "camino-frances":     scrape_camino_frances,
    "via-plata":          scrape_via_plata,
    "camino-ingles":      scrape_camino_ingles,
    "camino-invierno":    scrape_camino_invierno,
    "camino-salvador":    scrape_camino_salvador,
    "fisterra":               scrape_fisterra,
    "aragones":               scrape_aragones,
    "camino-madrid":          scrape_camino_madrid,
    "camino-vasco":           scrape_camino_vasco,
    "camino-ebro":            scrape_camino_ebro,
    "camino-vadiniense":      scrape_camino_vadiniense,
    "ria-muros":              scrape_ria_muros,
    "camino-baztan":          scrape_camino_baztan,
    "camino-catalan":         scrape_camino_catalan,
    "camino-olvidado":        scrape_camino_olvidado,
    "camino-levante":         scrape_camino_levante,
    "ruta-lana":              scrape_ruta_lana,
    "camino-mozarabe":        scrape_camino_mozarabe,
    "camino-portugues-costa": scrape_camino_portugues_costa,
    "camino-vezelay":         scrape_camino_vezelay,
    "via-gebennensis":        scrape_via_gebennensis,
    "camino-arles":           scrape_camino_arles,
    "camino-piamonte":        scrape_camino_piamonte,
    "via-francigena":         scrape_via_francigena,
    "camino-san-francesco":   scrape_camino_san_francesco,
    "via-augusta":            scrape_via_augusta,
    "camino-portugues-interior": scrape_camino_portugues_interior,
    "camino-norte":           scrape_camino_norte,
    "san-jacopo":             scrape_san_jacopo,
    "camino-lebaniego":       scrape_camino_lebaniego,
    "camino-tours-paris":     scrape_camino_tours_paris,
    # UK cycling (hardcoded — official sites are JS-rendered)
    "sea-to-sea":             scrape_sea_to_sea,
    "way-of-the-roses":       scrape_way_of_the_roses,
    "hadrians-cycleway":      scrape_hadrians_cycleway,
    "lon-las-cymru":          scrape_lon_las_cymru,
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
