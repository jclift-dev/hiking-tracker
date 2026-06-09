#!/usr/bin/env python3
"""
discover_trail_websites.py — Pipeline: catalog URL tag → official website → stage page detection

Three candidate sources:
  1. Named candidate/needs_level2 routes with a url/website tag (original behaviour)
  2. auto_excluded routes with no OSM children but a URL and length >= MIN_FLAT_KM
     ("flat" routes — no hierarchy in OSM but website may list day stages)
  3. Orphaned "Tappa N / Etappe N" relations with no parent in the catalog
     — grouped by base trail name, treated as a synthetic route candidate

Usage:
  python3 discover_trail_websites.py --smoke        # smoke test (covers all 3 sources)
  python3 discover_trail_websites.py               # full run
  python3 discover_trail_websites.py --resume      # skip already-processed ids

Output: trail_websites.json  (merged incrementally by osm_id)
"""

import argparse
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CATALOG_FILE  = Path("trails_catalog.json")
OUTPUT_FILE   = Path("trail_websites.json")
DELAY         = 1.5
TIMEOUT       = 15
MIN_FLAT_KM   = 80    # minimum length for auto_excluded flat routes
MIN_ORPHAN_N  = 3     # minimum stage count for an orphan group to be included

SESSION = requests.Session()
SESSION.headers["User-Agent"] = "Mozilla/5.0 (compatible; HikingTracker/1.0)"

# "Stage" in European languages used in OSM relation names
# IT: tappa/tappe  DE: etappe/abschnitt  FR: étape  ES/PT: etapa  NL: etappe/dag
# SV: etapp  NO/DA: etappe  PL: etap/odcinek  CZ/SK: etapa  HU: szakasz
# SL/HR: etapa  EN: stage/leg/day/section
STAGE_WORDS = [
    "tappa", "tappe",          # Italian
    "etappe", "abschnitt",     # German
    "étape", "etape",          # French
    "etapa", "etapas",         # Spanish / Portuguese / Slovenian / Croatian / Czech / Slovak
    "etapp",                   # Swedish
    "etap", "odcinek",         # Polish
    "szakasz",                 # Hungarian
    "jornada",                 # Spanish (alternative)
    "giornata",                # Italian (alternative)
    "stage", "stages",         # English
    "leg", "legs",             # English
    "section", "sections",     # English
    "dag",                     # Dutch / Norwegian / Danish (day)
    "deel",                    # Dutch (part)
    "itinerary", "day-walk", "daywalk",
]

# Keywords in link text or href suggesting a stage-listing page
STAGE_LINK_KEYWORDS = STAGE_WORDS + ["recorrido"]

# Link text/href patterns that are noise even if they match a keyword
STAGE_LINK_BLOCKLIST = [
    "completer", "news", "pdf", "gpx", "map", "shop", "book", "login",
    "registr", "facebook", "twitter", "instagram", "youtube",
]

# Regexes matching individual numbered stage mentions in page text
STAGE_LINE_PATTERNS = [
    re.compile(r'\betappe?\s*[a-z]?\d+\b',  re.I),  # Etappe 1 / Etappe N8
    re.compile(r'\bstage\s*\d+\b',           re.I),
    re.compile(r'\btappa\s*\d+\b',           re.I),
    re.compile(r'\bétape\s*\d+\b',           re.I),
    re.compile(r'\betape\s*\d+\b',           re.I),
    re.compile(r'\bjornada\s*\d+\b',         re.I),
    re.compile(r'\betapa\s*\d+\b',           re.I),
    re.compile(r'\betap\s*\d+\b',            re.I),
    re.compile(r'\betapp\s*\d+\b',           re.I),
    re.compile(r'\bdag\s*\d+\b',             re.I),
    re.compile(r'\bszakasz\s*\d+\b',         re.I),
    re.compile(r'\bodcinek\s*\d+\b',         re.I),
    re.compile(r'\babschnitt\s*\d+\b',       re.I),
]

# Regex to strip "- Tappa 3", ": Etappe 12", "Stage 5", "szakasz 2" etc. from a name
_sw = "|".join(re.escape(w) for w in STAGE_WORDS)
STAGE_SUFFIX_RE = re.compile(
    rf'\s*[-:–/]\s*(?:{_sw})(?:\s+variante?)?\s*[a-z0-9]*\s*$',
    re.I,
)

# Smoke test: representative sample covering all three sources
SMOKE_OSMS = {
    # Source 1 — named candidates with URL
    61186,    # Goldsteig — 38 stages confirmed
    2379540,  # HW3 Albverein — already in app (positive control)
    157289,   # HW4 Albverein — no stage page (negative control)
    2153742,  # Kammweg Erzgebirge-Vogtland
    # Source 2 — flat/auto_excluded routes with URL
    7700604,  # Cesta hrdinov SNP (Slovakia, 735km)
    6594270,  # Camino del Cid Senderista (Spain, 922km)
    3718434,  # Lahnwanderweg (Germany, 290km river valley) — actually candidate
    # Source 3 — orphan groups (added dynamically by build_candidate_list)
    # "Italia Coast to Coast" and "Heidschnuckenweg" will be included
}

SMOKE_ORPHAN_BASES = {
    "italia coast to coast",
    "heidschnuckenweg",
    "senders del 1714",
}


# ---------------------------------------------------------------------------
# Source helpers
# ---------------------------------------------------------------------------

def get_url(trail: dict) -> str:
    tags = trail.get("osm_tags_raw") or {}
    return tags.get("url") or tags.get("website") or ""


def build_candidate_list(catalog: list, smoke: bool = False) -> list:
    """
    Build the deduplicated list of trail dicts to process, across all three sources.
    Each entry has a '_source' key explaining where it came from.
    """
    seen = set()
    candidates = []

    def add(trail, source):
        oid = trail["osm_id"]
        if oid not in seen and get_url(trail):
            seen.add(oid)
            trail = dict(trail)
            trail["_source"] = source
            candidates.append(trail)

    # Source 1: named candidates / needs_level2 with URL
    for t in catalog:
        if t.get("filter_status") in ("candidate", "needs_level2") and t.get("name"):
            add(t, "candidate")

    # Source 2: auto_excluded flat routes (no OSM children, no parent) with URL + length
    for t in catalog:
        if (t.get("filter_status") == "auto_excluded"
                and t.get("parent_osm_id") is None
                and t.get("name")
                and (t.get("length_km") or 0) >= MIN_FLAT_KM):
            add(t, "flat_route")

    # Source 3: orphaned "Tappa N" groups
    for group in extract_orphan_groups(catalog):
        rep_id = group["osm_id"]
        if rep_id not in seen and group.get("_url"):
            seen.add(rep_id)
            candidates.append(group)

    if smoke:
        # Filter to smoke set for sources 1 & 2; for source 3 filter by base name
        def keep(t):
            if t["osm_id"] in SMOKE_OSMS:
                return True
            if t.get("_source") == "orphan_group":
                return t["name"].lower() in SMOKE_ORPHAN_BASES
            return False
        candidates = [t for t in candidates if keep(t)]

    return candidates


def extract_orphan_groups(catalog: list) -> list:
    """
    Find auto_excluded stage-named relations (Tappa N, Etappe N, …) with no parent
    in the catalog, group them by base trail name + URL, return synthetic route dicts.
    """
    STAGE_NAME_RE = re.compile(
        rf'\b(?:{_sw})\s*[a-z]?\d+\b', re.I
    )

    orphans = [
        t for t in catalog
        if t.get("filter_status") == "auto_excluded"
        and t.get("parent_osm_id") is None
        and t.get("name")
        and STAGE_NAME_RE.search(t["name"])
        and (t.get("length_km") or 0) > 5
    ]

    groups = {}
    for t in orphans:
        base = STAGE_SUFFIX_RE.sub("", t["name"]).strip()
        if not base:
            continue
        url = get_url(t)
        key = (base.lower(), url)
        if key not in groups:
            groups[key] = {"base_name": base, "url": url, "members": []}
        groups[key]["members"].append(t)

    result = []
    for (base_lower, url), g in groups.items():
        members = g["members"]
        if len(members) < MIN_ORPHAN_N:
            continue
        total_km = round(sum(m.get("length_km") or 0 for m in members), 1)
        rep_id   = min(m["osm_id"] for m in members)
        result.append({
            "osm_id":          rep_id,
            "name":            g["base_name"],
            "filter_status":   "orphan_group",
            "stage_count":     len(members),
            "length_km":       total_km,
            "needs_level2":    False,
            "osm_tags_raw":    {"url": url} if url else {},
            "_source":         "orphan_group",
            "_url":            url,
            "_member_osm_ids": sorted(m["osm_id"] for m in members),
        })

    return sorted(result, key=lambda x: -x["stage_count"])


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def fetch(url: str):
    try:
        r = SESSION.get(url, timeout=TIMEOUT, allow_redirects=True)
        return r.text if r.status_code == 200 else None
    except Exception:
        return None


def find_stage_links(html: str, base_url: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    seen, results = set(), []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        text = a.get_text(" ", strip=True)
        combined = (href + " " + text).lower()
        if not any(kw in combined for kw in STAGE_LINK_KEYWORDS):
            continue
        if any(bl in combined for bl in STAGE_LINK_BLOCKLIST):
            continue
        full = urljoin(base_url, href)
        if full not in seen and not href.startswith("#"):
            seen.add(full)
            results.append({"url": full, "text": text[:120]})
    return results


def count_stages_on_page(html: str) -> int:
    text = BeautifulSoup(html, "html.parser").get_text(" ")
    matches = set()
    for pat in STAGE_LINE_PATTERNS:
        for m in pat.finditer(text):
            matches.add(m.group().lower())
    return len(matches)


# ---------------------------------------------------------------------------
# Core pipeline step
# ---------------------------------------------------------------------------

def process_trail(trail: dict) -> dict:
    osm_id = trail["osm_id"]
    name   = trail.get("name") or f"(OSM {osm_id})"
    url    = get_url(trail)
    source = trail.get("_source", "?")

    result = {
        "osm_id":          osm_id,
        "name":            name,
        "filter_status":   trail.get("filter_status"),
        "source":          source,
        "length_km":       trail.get("length_km"),
        "catalog_stages":  trail.get("stage_count"),
        "official_url":    url,
        "stage_links":     [],
        "stage_count":     0,
        "status":          "no_url",
    }
    if trail.get("_member_osm_ids"):
        result["member_osm_ids"] = trail["_member_osm_ids"]

    if not url:
        return result

    src_tag = f"[{source}]"
    print(f"  {src_tag} [{osm_id}] {name[:50]}")
    print(f"    url → {url}")

    time.sleep(DELAY)
    html = fetch(url)
    if html is None:
        result["status"] = "fetch_error"
        print(f"    ✗ fetch error")
        return result

    links = find_stage_links(html, url)
    if not links:
        result["status"] = "no_stage_link"
        print(f"    ✗ no stage links on page")
        return result

    result["stage_links"] = links
    print(f"    ✓ stage link: \"{links[0]['text'][:60]}\"  →  {links[0]['url']}")

    time.sleep(DELAY)
    stage_html = fetch(links[0]["url"])
    if stage_html is None:
        result["status"] = "stage_page_error"
        print(f"    ✗ stage page fetch error")
        return result

    count = count_stages_on_page(stage_html)
    result["stage_count"] = count
    result["status"] = "found" if count > 0 else "stage_link_no_count"
    print(f"    {'✓' if count > 0 else '?'} {count} stage(s) detected")
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="Discover trail websites with stage pages")
    p.add_argument("--smoke",  action="store_true", help="Smoke test on representative subset")
    p.add_argument("--resume", action="store_true", help="Skip already-processed osm_ids")
    args = p.parse_args()

    catalog    = json.loads(CATALOG_FILE.read_text())
    candidates = build_candidate_list(catalog, smoke=args.smoke)

    by_source = {}
    for c in candidates:
        by_source.setdefault(c.get("_source", "?"), 0)
        by_source[c["_source"]] += 1

    print(f"Candidates: {len(candidates)} total")
    for src, n in sorted(by_source.items()):
        print(f"  {src:20s} {n}")
    print()

    existing = {}
    if args.resume and OUTPUT_FILE.exists():
        for r in json.loads(OUTPUT_FILE.read_text()):
            existing[r["osm_id"]] = r
        before = len(candidates)
        candidates = [t for t in candidates if t["osm_id"] not in existing]
        print(f"Resuming: skipping {before - len(candidates)} already done\n")

    results = list(existing.values())
    for trail in candidates:
        result = process_trail(trail)
        results.append(result)
        existing[result["osm_id"]] = result
        OUTPUT_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2))

    # Summary
    found    = [r for r in results if r["status"] == "found"]
    no_link  = [r for r in results if r["status"] == "no_stage_link"]
    errors   = [r for r in results if r["status"] in ("fetch_error", "stage_page_error")]
    no_count = [r for r in results if r["status"] == "stage_link_no_count"]

    print(f"\n{'='*65}")
    print(f"  found stage pages : {len(found)}")
    print(f"  no stage link     : {len(no_link)}")
    print(f"  link but no count : {len(no_count)}")
    print(f"  fetch errors      : {len(errors)}")
    print(f"{'='*65}")

    if found:
        print(f"\nTrails with confirmed stage pages:")
        for r in sorted(found, key=lambda x: -(x["stage_count"] or 0)):
            src = r.get("source", "?")[:8]
            print(f"  [{src:8s}] {r['name'][:48]:48s} {r['stage_count']:3d} stages  {r['length_km'] or '?':>7} km")

    print(f"\nOutput: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
