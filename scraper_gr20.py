#!/usr/bin/env python3
"""
GR20 Scraper (Corsica, France)
================================
Fetches the 16 stages of the GR20 from le-gr20.fr and merges them into
hikes.json with land="fr-hike", route_id=1, route_type="national".

Usage:
    pip3 install requests beautifulsoup4
    python3 scraper_gr20.py              # fetch all 16 stages
    python3 scraper_gr20.py --refresh    # re-fetch even if cached
    python3 scraper_gr20.py --limit 3    # smoke test: first N stages only

Push to Supabase:
    python3 scraper.py --import

Notes
-----
- Source: https://www.le-gr20.fr/en/pages/profile-stages/
  Overview page lists links to 16 individual stage pages.
- Each stage page has: start/end (h1), altitude gain, altitude loss,
  estimated walking time (North→South direction). Distance is not
  published per individual stage page — dist_km is null.
- The route traditionally walks South (Calenzana → Conca), but stage
  pages show N→S data first. We use N→S (first table/section).
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

BASE      = "https://www.le-gr20.fr"
INDEX_URL = f"{BASE}/en/pages/profile-stages/"
DELAY     = 1.0

ROUTE_ID   = 1
LAND       = "fr-hike"
ROUTE_TYPE = "national"
ROUTE_NAME = "GR20"
ROUTE_DESC = (
    "The GR20 crosses Corsica from north to south over 180 km and 16 stages, "
    "from Calenzana in the Balagne to Conca near Porto-Vecchio. Widely "
    "regarded as one of the most demanding long-distance trails in Europe, "
    "it traverses the island's granite spine through remote mountain terrain "
    "above 2,000 m with no road crossings for days at a time."
)

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": BASE + "/",
})

# Field patterns from individual stage pages (N→S direction appears first)
# Colon is optional — some stage pages omit it: "Altitude gain  + 800m"
_ELEV_UP_RE   = re.compile(r"Altitude gain\s*:?\s*\+?\s*(\d+)\s*m", re.IGNORECASE)
_ELEV_DOWN_RE = re.compile(r"Altitude loss\s*:?\s*-?\s*(\d+)\s*m", re.IGNORECASE)
_TIME_RE      = re.compile(r"Estimated time\s*:?\s*(\d+)h(\d+)?", re.IGNORECASE)


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


def discover_stage_urls(html):
    """Find ordered stage page links from the overview page."""
    soup = BeautifulSoup(html, "html.parser")
    seen, urls = set(), []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Stage links end in .html and are under /en/pages/
        if not href.endswith(".html"):
            continue
        if "profile-stages" not in href and "pages/" not in href:
            continue
        # Skip the overview page itself
        if href.rstrip("/") == "/en/pages/profile-stages":
            continue
        # Normalise to absolute
        if href.startswith("/"):
            href = BASE + href
        elif not href.startswith("http"):
            href = BASE + "/" + href
        if href not in seen:
            seen.add(href)
            urls.append(href)
    return urls


def parse_stage_page(html, url):
    """Parse a single stage page into a stage dict (without stage_nr)."""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n")

    # Start/end from h1: "Ortu di u Piobbu to Carrozzu"
    h1 = soup.find("h1")
    title = h1.get_text(" ", strip=True) if h1 else ""
    if " to " in title:
        start_name, end_name = (s.strip() for s in title.split(" to ", 1))
    else:
        # Fallback: derive from URL slug
        slug = url.rstrip("/").split("/")[-1].replace(".html", "").replace("-", " ")
        start_name = end_name = slug.title()

    # Take N→S direction (first occurrence of each field)
    up_m   = _ELEV_UP_RE.search(text)
    down_m = _ELEV_DOWN_RE.search(text)
    time_m = _TIME_RE.search(text)

    elev_up      = int(up_m.group(1))    if up_m   else None
    elev_down    = int(down_m.group(1))  if down_m else None
    hrs, mins    = None, None
    if time_m:
        hrs  = int(time_m.group(1))
        mins = int(time_m.group(2)) if time_m.group(2) else 0
    duration_hrs = round(hrs + mins / 60, 2) if hrs is not None else None

    # Description: first substantive paragraphs
    desc_paras = []
    for p in soup.find_all("p"):
        t = p.get_text(" ", strip=True)
        if len(t) < 50:
            continue
        if re.search(r"cookie|privacy|copyright|newsletter|altitude|estimated", t, re.I):
            continue
        desc_paras.append(t)
        if len(desc_paras) >= 2:
            break

    return {
        "stage_nr":         None,
        "start_name":       start_name,
        "end_name":         end_name,
        "via":              None,
        "dist_km":          None,   # not published per-stage page
        "elev_up":          elev_up,
        "elev_down":        elev_down,
        "duration_hrs":     duration_hrs,
        "difficulty":       "difficult",   # GR20 is uniformly demanding
        "description":      "\n\n".join(desc_paras),
        "cantons":          [],
        "arrival_stations": [],
        "sbb_times":        {},
        "_url":             url,   # internal resume key
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="Scrape GR20 (Corsica) stages")
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
        "start":       "Calenzana",
        "end":         "Conca",
        "total_km":    180,
        "stages":      [],
    }
    existing[key] = route

    cached_by_url = {
        s.get("_url"): s
        for s in route.get("stages", [])
        if s.get("_url")
    }

    print(f"Fetching index: {INDEX_URL}")
    time.sleep(DELAY)
    index_html = fetch(INDEX_URL, "index page")
    if not index_html:
        print("Could not fetch index page. Aborting.")
        sys.exit(1)

    urls = discover_stage_urls(index_html)
    if not urls:
        print("No stage links found on index page. Aborting.")
        sys.exit(1)

    expected = 16
    print(f"Found {len(urls)} stage link(s)" + ("" if len(urls) == expected else f" (expected {expected})"))
    if args.limit:
        urls = urls[:args.limit]
        print(f"  (limited to first {len(urls)})")

    new_stages = []
    try:
        for i, url in enumerate(urls, start=1):
            cached = cached_by_url.get(url)
            if cached and not args.refresh:
                cached["stage_nr"] = i
                new_stages.append(cached)
                print(f"  [{i:2d}/{len(urls)}] {url.split('/')[-1]}: cached")
                continue

            time.sleep(DELAY)
            print(f"  [{i:2d}/{len(urls)}] fetching {url.split('/')[-1]}...", end=" ", flush=True)
            html = fetch(url, url)
            if not html:
                if cached:
                    cached["stage_nr"] = i
                    new_stages.append(cached)
                    print("kept cached")
                else:
                    print("skipped")
                continue

            stage = parse_stage_page(html, url)
            stage["stage_nr"] = i
            new_stages.append(stage)
            print(
                f"{stage['start_name']} → {stage['end_name']} "
                f"(↑{stage['elev_up']}m ↓{stage['elev_down']}m, {stage['duration_hrs']}h)"
            )

    except KeyboardInterrupt:
        print("\nInterrupted — saving progress...")

    route["stages"]   = new_stages
    if new_stages:
        route["start"]    = new_stages[0]["start_name"]
        route["end"]      = new_stages[-1]["end_name"]

    save(list(existing.values()))
    print(f"\nDone. {len(new_stages)} stages.")


if __name__ == "__main__":
    main()
