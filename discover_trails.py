#!/usr/bin/env python3
"""
Trail Discovery Script
======================
Builds a catalogue of long-distance hiking trails in Europe for review and
selective import into the app.

Phase 1 — Overpass API
    Fetches all hiking/foot routes in Europe tagged network=iwn/nwn/rwn and
    saves their raw OSM tags to trails_catalog.json.

Phase 2 — Waymarked Trails API
    Enriches shortlisted candidates with computed length, stage count, and
    bounding box. Skips rwn routes with no distance tag or distance < 80 km
    (too many to check; saved as filter_status="unverified").

Both phases are resumable: re-running adds new Overpass entries and continues
WT enrichment from where it left off.

Output: trails_catalog.json

Usage:
    python3 discover_trails.py                     # full run (Overpass + WT)
    python3 discover_trails.py --smoke-test        # IE only, first 5 WT calls
    python3 discover_trails.py --overpass-only     # Overpass phase, skip WT
    python3 discover_trails.py --enrich-only       # skip Overpass, resume WT
    python3 discover_trails.py --limit 20          # cap WT calls at 20
    python3 discover_trails.py --refresh-id 12345  # re-fetch WT for one id
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests

try:
    from scraper_osm import TRAILS as _OSM_TRAILS
    IN_APP_IDS = {t[0] for t in _OSM_TRAILS}
except ImportError:
    print("[warn] scraper_osm.py not found — in-app marking disabled", file=sys.stderr)
    IN_APP_IDS = set()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

OVERPASS_URL  = "https://overpass-api.de/api/interpreter"
WT_BASE       = "https://hiking.waymarkedtrails.org/api/v1/details/relation"
WT_DELAY      = 1.8     # seconds between WT requests
CATALOG_FILE  = Path("trails_catalog.json")

# Overpass bounding box for Europe (south, west, north, east)
EUROPE_BBOX   = (34, -30, 72, 45)

# Smoke test: single small country
SMOKE_COUNTRY = "IE"

# rwn routes with distance_tag_km below this skip WT enrichment
RWN_MIN_KM    = 80

# Auto-exclude after WT enrichment if shorter than this
MIN_LENGTH_KM = 50

SESSION = requests.Session()
SESSION.headers["User-Agent"] = "HikingTracker/1.0 (https://github.com/jclift-dev/hiking-tracker)"


# ---------------------------------------------------------------------------
# Overpass
# ---------------------------------------------------------------------------

def build_query(smoke_test):
    if smoke_test:
        return (
            f'[out:json][timeout:60];\n'
            f'area["ISO3166-1"="{SMOKE_COUNTRY}"]->.search;\n'
            f'(\n'
            f'  relation["type"~"^(route|superroute)$"]["route"~"^(hiking|foot)$"]'
            f'["network"~"^(iwn|nwn|rwn)$"](area.search);\n'
            f');\n'
            f'out tags qt;'
        )
    s, w, n, e = EUROPE_BBOX
    return (
        f'[out:json][timeout:600][bbox:{s},{w},{n},{e}];\n'
        f'(\n'
        f'  relation["type"~"^(route|superroute)$"]["route"~"^(hiking|foot)$"]["network"~"^(iwn|nwn)$"];\n'
        f'  relation["type"~"^(route|superroute)$"]["route"="hiking"]["network"="rwn"];\n'
        f');\n'
        f'out tags qt;'
    )


# Superroutes contain only relations as members (no direct ways/nodes), so the
# global bbox filter can't determine their geographic extent and silently drops
# them. This separate unbounded query catches hiking superroutes globally.
SUPERROUTE_QUERY = (
    '[out:json][timeout:120];\n'
    '(\n'
    '  relation["type"="superroute"]["route"~"^(hiking|foot)$"]["network"~"^(iwn|nwn|rwn)$"];\n'
    ');\n'
    'out tags qt;'
)


def run_overpass(smoke_test):
    label = f"smoke-test ({SMOKE_COUNTRY})" if smoke_test else "Europe"
    print(f"\nPhase 1 — Overpass ({label})...")
    query = build_query(smoke_test)

    elements = []
    for attempt in range(3):
        try:
            resp = SESSION.post(OVERPASS_URL, data={"data": query}, timeout=660)
            resp.raise_for_status()
            elements = resp.json().get("elements", [])
            print(f"  → {len(elements)} relations returned from Overpass (bbox)")
            break
        except Exception as exc:
            wait = 15 * (attempt + 1)
            if attempt < 2:
                print(f"  [warn] attempt {attempt + 1} failed ({exc}) — retry in {wait}s")
                time.sleep(wait)
            else:
                print(f"  [error] Overpass failed after 3 attempts: {exc}")
                sys.exit(1)

    # Supplementary superroute query — no bbox (superroutes have no direct way
    # members so bbox filtering silently drops them from the main query)
    if not smoke_test:
        print(f"  Fetching superroutes globally (no bbox)...")
        for attempt in range(3):
            try:
                resp = SESSION.post(OVERPASS_URL, data={"data": SUPERROUTE_QUERY}, timeout=180)
                resp.raise_for_status()
                superroutes = resp.json().get("elements", [])
                existing_ids = {e["id"] for e in elements}
                new_superroutes = [e for e in superroutes if e["id"] not in existing_ids]
                elements.extend(new_superroutes)
                print(f"  → {len(superroutes)} superroutes found globally, "
                      f"{len(new_superroutes)} new (not already in bbox results)")
                break
            except Exception as exc:
                wait = 15 * (attempt + 1)
                if attempt < 2:
                    print(f"  [warn] superroute attempt {attempt + 1} failed ({exc}) — retry in {wait}s")
                    time.sleep(wait)
                else:
                    print(f"  [warn] superroute query failed after 3 attempts: {exc} — skipping")

    return elements


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def parse_distance_km(raw):
    if not raw:
        return None
    m = re.match(r"^([\d.,]+)\s*(km|mi|miles?)?$", str(raw).strip(), re.I)
    if not m:
        return None
    try:
        val = float(m.group(1).replace(",", "."))
    except ValueError:
        return None
    unit = (m.group(2) or "km").lower()
    if unit in ("mi", "mile", "miles"):
        val *= 1.60934
    return round(val, 1)


def make_entry(elem):
    tags   = elem.get("tags", {})
    osm_id = elem["id"]
    dist_raw = tags.get("distance") or tags.get("length")
    dist_km  = parse_distance_km(dist_raw)
    return {
        # --- OSM identity ---
        "osm_id":            osm_id,
        "name":              tags.get("name", ""),
        "name_en":           tags.get("name:en") or tags.get("int_name", ""),
        "ref":               tags.get("ref", ""),
        "network":           tags.get("network", ""),
        "route_tag":         tags.get("route", ""),
        # --- OSM geography ---
        "osm_from":          tags.get("from", ""),
        "osm_to":            tags.get("to", ""),
        "country_tag":       tags.get("country", ""),
        "state_tag":         tags.get("state", ""),
        # --- OSM distance (unreliable, but capture it) ---
        "distance_tag_raw":  dist_raw,
        "distance_tag_km":   dist_km,
        # --- OSM trail metadata ---
        "sac_scale":         tags.get("sac_scale", ""),
        "operator":          tags.get("operator", ""),
        "website":           tags.get("website") or tags.get("url", ""),
        "wikipedia":         tags.get("wikipedia", ""),
        "wikidata":          tags.get("wikidata", ""),
        "description":       tags.get("description") or tags.get("description:en", ""),
        # --- Waymarked Trails enrichment (filled in Phase 2) ---
        "wt_enriched":       False,
        "length_km":         dist_km,
        "length_source":     "osm_tag" if dist_km else None,
        "stage_count":       None,
        "max_stage_km":      None,
        "has_viable_stages": None,
        "bbox":              None,
        "stages_raw":        None,   # [{id, length_m}] from WT parent route.main
        "level2_descent":    False,  # True once level-2 descent has been attempted
        "needs_level2":      False,  # True when level-1 children are sections (all >40km), not day stages
        "parent_osm_id":     None,   # set when this entry is a section of a larger trail in the catalog
        # --- App status ---
        "already_in_app":    osm_id in IN_APP_IDS,
        "filter_status":     "in_app" if osm_id in IN_APP_IDS else None,
        "filter_reason":     None,
        "waymarked_url":     f"https://hiking.waymarkedtrails.org/#route?id={osm_id}",
        # --- Full tag dump (never re-query for a forgotten field) ---
        "osm_tags_raw":      tags,
    }


# ---------------------------------------------------------------------------
# Waymarked Trails enrichment
# ---------------------------------------------------------------------------

def fetch_wt(osm_id):
    url = f"{WT_BASE}/{osm_id}"
    for attempt in range(2):
        try:
            time.sleep(WT_DELAY)
            resp = SESSION.get(url, timeout=20)
            if resp.status_code == 404:
                return None
            if resp.status_code >= 500 and attempt == 0:
                time.sleep(10)
                continue
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            if attempt == 0:
                time.sleep(10)
                continue
            print(f"   [warn] WT fetch failed for {osm_id}: {exc}")
            return None
    return None


def enrich(entry, wt):
    route_node = wt.get("route", {})

    # Length — WT computed is more reliable than OSM tag
    length_m = route_node.get("length") or wt.get("official_length")
    if length_m:
        entry["length_km"]    = round(length_m / 1000, 1)
        entry["length_source"] = (
            "waymarked_computed" if route_node.get("length") else "waymarked_official"
        )

    # Direct route-type children (day stages at level 1)
    children = [
        c for c in route_node.get("main", [])
        if c.get("route_type") == "route" and (c.get("length") or 0) >= 1000
    ]
    entry["stage_count"]       = len(children)
    entry["stages_raw"]        = [
        {"id": c["id"], "length_m": c.get("length")} for c in children
    ]
    entry["max_stage_km"]      = (
        round(max(c.get("length", 0) for c in children) / 1000, 1)
        if children else None
    )
    entry["has_viable_stages"] = len(children) >= 2
    # If every child is >40 km the "stages" are really sections, not day stages
    entry["needs_level2"] = bool(children and all(
        (c.get("length") or 0) > 40_000 for c in children
    ))

    # Bounding box — tells us which countries the route crosses
    if wt.get("bbox"):
        entry["bbox"] = wt["bbox"]

    # WT name may be better than the raw OSM tag (e.g. has language suffix stripped)
    if not entry["name"] and wt.get("name"):
        entry["name"] = wt["name"]

    entry["wt_enriched"] = True


def get_section_ids(wt):
    """Return OSM IDs of route-type children at level 1 (section candidates)."""
    main = wt.get("route", {}).get("main", [])
    return [c["id"] for c in main if c.get("route_type") == "route" and c.get("id")]


def apply_level2(entry, sections_wt_list):
    """Update entry with day stages found at level 2 across all section WT responses."""
    all_stages = []
    for wt in sections_wt_list:
        sec_main = wt.get("route", {}).get("main", [])
        stages = [
            c for c in sec_main
            if c.get("route_type") == "route" and (c.get("length") or 0) >= 1000
        ]
        all_stages.extend(stages)

    entry["level2_descent"] = True

    if not all_stages:
        return  # nothing found — filter_status stays as-is

    entry["stage_count"]       = len(all_stages)
    entry["stages_raw"]        = [{"id": c["id"], "length_m": c.get("length")} for c in all_stages]
    entry["max_stage_km"]      = round(max(c.get("length", 0) for c in all_stages) / 1000, 1)
    entry["has_viable_stages"] = len(all_stages) >= 2
    # Reset so apply_filters() can re-evaluate
    entry["filter_status"]     = None
    entry["filter_reason"]     = None


def backfill_needs_level2(catalog):
    """
    Compute needs_level2 for entries enriched before this field was introduced.
    An entry needs level-2 descent when ALL its level-1 children are >40km
    (they are sections rather than day stages).
    """
    for entry in catalog.values():
        if entry.get("needs_level2") is not None:
            continue  # already set
        stages = entry.get("stages_raw") or []
        if not stages:
            entry["needs_level2"] = False
            continue
        entry["needs_level2"] = all((s.get("length_m") or 0) > 40_000 for s in stages)


def tag_child_sections(catalog):
    """
    Build a child→parent index from stages_raw and set parent_osm_id on each
    entry that appears as a section of a larger trail in the catalog.
    Only tags entries where the parent is enriched (so we know it's deliberate).
    """
    child_to_parent = {}
    for entry in catalog.values():
        if not entry.get("wt_enriched") or not entry.get("stages_raw"):
            continue
        for stage in entry["stages_raw"]:
            child_id = stage.get("id")
            if child_id and child_id != entry["osm_id"]:
                child_to_parent[child_id] = entry["osm_id"]

    for entry in catalog.values():
        parent_id = child_to_parent.get(entry["osm_id"])
        if parent_id and parent_id in catalog:
            entry["parent_osm_id"] = parent_id
        elif entry.get("parent_osm_id") and entry["parent_osm_id"] not in child_to_parent.values():
            entry["parent_osm_id"] = None  # stale — parent no longer references this child


def apply_section_suppression(catalog):
    """
    Suppress child-section entries in favour of their parent trails.
    Runs after apply_filters so parent statuses are already resolved.
    Only suppresses if the parent is a genuine candidate (not auto_excluded/unverified)
    and the child itself is not already in the app or firmly excluded.
    """
    # Statuses we do not override — in_app and auto_excluded are firm decisions
    PRESERVE = {"in_app", "auto_excluded", "section_of_parent"}
    suppressed = 0
    for entry in catalog.values():
        if entry.get("filter_status") in PRESERVE:
            continue
        parent_id = entry.get("parent_osm_id")
        if not parent_id:
            continue
        parent = catalog.get(parent_id)
        if not parent:
            continue
        if parent.get("filter_status") not in ("auto_excluded", "unverified", None):
            parent_name = (parent.get("name") or "?")[:40]
            entry["filter_status"] = "section_of_parent"
            entry["filter_reason"] = f"child of {parent_id}: {parent_name}"
            suppressed += 1
    return suppressed


def should_enrich(entry):
    if entry.get("already_in_app") or entry.get("wt_enriched"):
        return False
    net = entry.get("network", "")
    if net in ("iwn", "nwn"):
        return True
    if net == "rwn":
        dist = entry.get("distance_tag_km")
        return dist is not None and dist >= RWN_MIN_KM
    return False


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def apply_filters(catalog):
    for entry in catalog.values():
        # Skip only firmly decided statuses — re-evaluate pending_enrichment entries
        # that may have since been enriched
        if entry.get("filter_status") and entry.get("filter_status") != "pending_enrichment":
            continue

        if not entry.get("wt_enriched"):
            net  = entry.get("network", "")
            dist = entry.get("distance_tag_km")
            if net in ("iwn", "nwn") or (net == "rwn" and dist and dist >= RWN_MIN_KM):
                # Will be enriched on the next run (held back by --limit or first pass)
                entry["filter_status"] = "pending_enrichment"
                entry["filter_reason"] = None
            else:
                # rwn below/missing distance threshold — won't be auto-enriched
                entry["filter_status"] = "unverified"
                entry["filter_reason"] = "rwn_below_distance_threshold"
            continue

        length = entry.get("length_km")
        if length is not None and length < MIN_LENGTH_KM:
            entry["filter_status"] = "auto_excluded"
            entry["filter_reason"] = f"too_short ({length} km)"
            continue

        if not entry.get("has_viable_stages"):
            entry["filter_status"] = "auto_excluded"
            entry["filter_reason"] = "no_day_stages"
            continue

        entry["filter_status"] = "candidate"
        entry["filter_reason"] = None


# ---------------------------------------------------------------------------
# Catalog I/O
# ---------------------------------------------------------------------------

def load_catalog():
    if not CATALOG_FILE.exists():
        return {}
    try:
        with CATALOG_FILE.open(encoding="utf-8") as f:
            return {e["osm_id"]: e for e in json.load(f)}
    except Exception as exc:
        print(f"[warn] could not load {CATALOG_FILE}: {exc} — starting fresh")
        return {}


def save_catalog(catalog):
    order = {"iwn": 0, "nwn": 1, "rwn": 2}
    entries = sorted(
        catalog.values(),
        key=lambda e: (order.get(e.get("network", ""), 9), (e.get("name") or "").lower()),
    )
    with CATALOG_FILE.open("w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def print_summary(catalog, smoke_test):
    from collections import Counter

    if smoke_test:
        print("\n[SMOKE TEST — results are Ireland only]\n")

    statuses = Counter(e.get("filter_status") for e in catalog.values())
    networks = Counter(e.get("network") for e in catalog.values())

    print(f"{'='*64}")
    print(f"Catalog total : {len(catalog)} routes  ({CATALOG_FILE})")
    print(f"By network    : {dict(networks)}")
    print(f"\nBy filter_status:")
    for status, count in sorted(statuses.items(), key=lambda x: x[0] or ""):
        print(f"  {(status or 'unknown'):25s}  {count:4d}")

    pending = sum(1 for e in catalog.values() if e.get("filter_status") == "pending_enrichment")
    if pending:
        print(f"\n  → {pending} routes pending WT enrichment (run without --limit to complete)")

    candidates = [e for e in catalog.values() if e.get("filter_status") == "candidate"]
    if candidates:
        ready     = [e for e in candidates if not e.get("needs_level2")]
        need_l2   = [e for e in candidates if e.get("needs_level2")]
        sections  = sum(1 for e in catalog.values() if e.get("filter_status") == "section_of_parent")

        print(f"\nCandidates — day-stage trails ({len(ready)} routes with viable day stages, ≥{MIN_LENGTH_KM} km):")
        print(f"  {'net':3}  {'name':50}  {'km':>6}  {'stg':>4}  {'in-app'}")
        print(f"  {'-'*3}  {'-'*50}  {'-'*6}  {'-'*4}  {'-'*6}")
        for e in sorted(ready, key=lambda x: -(x.get("length_km") or 0)):
            km    = f"{e['length_km']:.0f}" if e.get("length_km") else "  ?"
            stg   = str(e.get("stage_count") or "?")
            app   = "✓" if e.get("already_in_app") else ""
            print(f"  {e['network']:3}  {(e['name'] or '?')[:50]:50}  {km:>6}  {stg:>4}  {app}")

        if need_l2:
            print(f"\nCandidates — need 2-level descent ({len(need_l2)} multi-section trails):")
            print(f"  (scraper handles these automatically; stage counts are section counts, not day stages)")
            print(f"  {'net':3}  {'name':50}  {'km':>6}  {'sec':>4}  {'max_sec_km':>10}")
            print(f"  {'-'*3}  {'-'*50}  {'-'*6}  {'-'*4}  {'-'*10}")
            for e in sorted(need_l2, key=lambda x: -(x.get("length_km") or 0)):
                km  = f"{e['length_km']:.0f}" if e.get("length_km") else "  ?"
                sec = str(e.get("stage_count") or "?")
                mx  = f"{e['max_stage_km']:.0f}" if e.get("max_stage_km") else "?"
                app = "✓" if e.get("already_in_app") else ""
                print(f"  {e['network']:3}  {(e['name'] or '?')[:50]:50}  {km:>6}  {sec:>4}  {mx:>9}  {app}")
            print(f"  → run --recheck-large-stages to compute actual day-stage counts")

        if sections:
            print(f"\n  ({sections} child-section entries suppressed — they are sub-routes of listed parents)")

    print("="*64)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="Discover long-distance hiking trails in Europe.")
    p.add_argument("--smoke-test",    action="store_true",
                   help=f"IE-only Overpass query, first 5 WT enrichment calls")
    p.add_argument("--overpass-only", action="store_true",
                   help="Run Overpass phase only, skip WT enrichment")
    p.add_argument("--enrich-only",   action="store_true",
                   help="Skip Overpass, run WT enrichment on un-enriched entries")
    p.add_argument("--limit",         type=int, default=None,
                   help="Cap WT enrichment calls at N (useful for testing)")
    p.add_argument("--refresh-id",    type=int, action="append", dest="refresh_ids",
                   help="Re-fetch WT data for this osm_id even if already enriched (repeatable)")
    p.add_argument("--recheck-excluded", action="store_true",
                   help="Attempt level-2 descent for auto_excluded no_day_stages entries ≥100 km")
    p.add_argument("--recheck-large-stages", action="store_true",
                   help="Attempt level-2 descent for candidates whose level-1 children are all >40km (sections not day stages)")
    args = p.parse_args()

    wt_limit    = 5 if args.smoke_test else args.limit
    refresh_ids = set(args.refresh_ids or [])

    catalog = load_catalog()

    # ------------------------------------------------------------------
    # Phase 0: Sync in-app status (always runs — no network calls)
    # Keeps already_in_app / filter_status consistent when trails are
    # added to scraper_osm.py between full Overpass runs.
    # ------------------------------------------------------------------
    synced = 0
    for entry in catalog.values():
        in_app_now = entry["osm_id"] in IN_APP_IDS
        if in_app_now and not entry.get("already_in_app"):
            entry["already_in_app"] = True
            entry["filter_status"]  = "in_app"
            synced += 1
        elif not in_app_now and entry.get("already_in_app"):
            entry["already_in_app"] = False
    if synced:
        print(f"Phase 0 — In-app sync: {synced} entries newly marked in_app")
        save_catalog(catalog)

    # ------------------------------------------------------------------
    # Phase 1: Overpass
    # ------------------------------------------------------------------
    if not args.enrich_only:
        elements = run_overpass(args.smoke_test)
        new_count = updated_count = 0
        for elem in elements:
            osm_id = elem.get("id")
            if not osm_id:
                continue
            if osm_id not in catalog:
                catalog[osm_id] = make_entry(elem)
                new_count += 1
            else:
                # Refresh OSM fields but preserve existing WT enrichment data
                existing = catalog[osm_id]
                refreshed = make_entry(elem)
                osm_fields = (
                    "osm_tags_raw", "name", "name_en", "ref", "network", "route_tag",
                    "osm_from", "osm_to", "country_tag", "state_tag",
                    "distance_tag_raw", "distance_tag_km",
                    "sac_scale", "operator", "website", "wikipedia",
                    "wikidata", "description", "already_in_app",
                )
                for k in osm_fields:
                    existing[k] = refreshed[k]
                # Re-evaluate in-app status
                existing["filter_status"] = (
                    "in_app" if existing["already_in_app"] else existing.get("filter_status")
                )
                updated_count += 1

        print(f"  → {new_count} new entries added, {updated_count} existing entries refreshed")
        save_catalog(catalog)

    # ------------------------------------------------------------------
    # Phase 2: Waymarked Trails enrichment
    # ------------------------------------------------------------------
    if not args.overpass_only:
        to_enrich = [
            e for e in catalog.values()
            if e["osm_id"] in refresh_ids or should_enrich(e)
        ]
        if wt_limit is not None:
            to_enrich = to_enrich[:wt_limit]

        total = len(to_enrich)
        print(f"\nPhase 2 — Waymarked Trails enrichment"
              f" ({total} routes{f', capped at {wt_limit}' if wt_limit else ''})...")

        if total == 0:
            print("  → nothing to enrich (all candidates already enriched)")
        else:
            try:
                for i, entry in enumerate(to_enrich, 1):
                    osm_id = entry["osm_id"]
                    name   = (entry.get("name") or "unnamed")[:50]
                    print(f"  [{i:4d}/{total}] {osm_id}  {name}", end=" ... ", flush=True)
                    wt = fetch_wt(osm_id)
                    if wt:
                        enrich(entry, wt)
                        km  = f"{entry['length_km']} km" if entry.get("length_km") else "? km"
                        stg = entry.get("stage_count", 0)
                        needs_l2 = entry.get("needs_level2")
                        print(f"{km}, {stg} section{'s' if stg != 1 else ''} (need L2)" if needs_l2
                              else f"{km}, {stg} stage{'s' if stg != 1 else ''}")
                        # Auto-descend when all level-1 children are sections (>40km each)
                        if needs_l2 and not entry.get("level2_descent"):
                            section_ids = get_section_ids(wt)
                            if section_ids:
                                sections_wt = [sw for sid in section_ids if (sw := fetch_wt(sid))]
                                apply_level2(entry, sections_wt)
                                real_stg = entry.get("stage_count", 0)
                                real_mx  = entry.get("max_stage_km", 0)
                                entry["needs_level2"] = real_mx > 40  # still sections if all still large
                                print(f"         → L2: {real_stg} day stage{'s' if real_stg != 1 else ''}, max {real_mx:.1f}km")
                    else:
                        print("no WT data")

                    if i % 10 == 0:
                        save_catalog(catalog)

            except KeyboardInterrupt:
                print("\nInterrupted — saving progress...")
                save_catalog(catalog)
                sys.exit(0)

    # ------------------------------------------------------------------
    # Phase 3: Level-2 descent (optional — --recheck-excluded)
    # Targets auto_excluded / no_day_stages entries ≥ 100 km that haven't
    # been attempted yet. Fetches the parent WT data, finds section IDs at
    # level 1, fetches each section, and checks for day stages at level 2.
    # ------------------------------------------------------------------
    if args.recheck_excluded and not args.overpass_only:
        to_descend = [
            e for e in catalog.values()
            if e.get("filter_status") == "auto_excluded"
            and e.get("filter_reason") == "no_day_stages"
            and (e.get("length_km") or 0) >= 100
            and not e.get("level2_descent")
        ]
        total_d = len(to_descend)
        print(f"\nPhase 3 — Level-2 descent ({total_d} auto_excluded no_day_stages entries ≥ 100 km)...")

        if total_d == 0:
            print("  → nothing to descend into")
        else:
            promoted = 0
            try:
                for i, entry in enumerate(to_descend, 1):
                    osm_id = entry["osm_id"]
                    name   = (entry.get("name") or "unnamed")[:45]
                    km     = entry.get("length_km", "?")
                    print(f"  [{i:4d}/{total_d}] {osm_id}  {name} ({km} km)", end=" ... ", flush=True)

                    wt = fetch_wt(osm_id)
                    if not wt:
                        print("no WT data")
                        entry["level2_descent"] = True
                        continue

                    section_ids = get_section_ids(wt)
                    if not section_ids:
                        print(f"0 sections at L1 — flat structure confirmed")
                        entry["level2_descent"] = True
                        continue

                    sections_wt = []
                    for sec_id in section_ids:
                        sec_wt = fetch_wt(sec_id)
                        if sec_wt:
                            sections_wt.append(sec_wt)

                    before = entry.get("has_viable_stages")
                    apply_level2(entry, sections_wt)

                    if entry.get("has_viable_stages"):
                        stg = entry["stage_count"]
                        print(f"→ {stg} day stage{'s' if stg != 1 else ''} found via {len(section_ids)} section(s) ✓")
                        promoted += 1
                    else:
                        print(f"0 day stages across {len(section_ids)} section(s)")

                    if i % 10 == 0:
                        save_catalog(catalog)

            except KeyboardInterrupt:
                print("\nInterrupted — saving progress...")
                save_catalog(catalog)
                sys.exit(0)

            print(f"\n  → {promoted}/{total_d} entries promoted to candidate")

    # ------------------------------------------------------------------
    # Phase 4: Level-2 descent for large-stage candidates (--recheck-large-stages)
    # Targets candidates where all level-1 children are >40km (sections, not day
    # stages) and level-2 descent hasn't been attempted yet.
    # ------------------------------------------------------------------
    if getattr(args, "recheck_large_stages", False) and not args.overpass_only:
        to_descend_l2 = [
            e for e in catalog.values()
            if e.get("needs_level2")
            and not e.get("level2_descent")
            and not e.get("already_in_app")
        ]
        total_l2 = len(to_descend_l2)
        print(f"\nPhase 4 — Level-2 descent for large-stage candidates ({total_l2} entries)...")

        if total_l2 == 0:
            print("  → nothing to descend (all large-stage candidates already processed)")
        else:
            promoted = 0
            try:
                for i, entry in enumerate(to_descend_l2, 1):
                    osm_id = entry["osm_id"]
                    name   = (entry.get("name") or "unnamed")[:45]
                    km     = entry.get("length_km", "?")
                    sec    = entry.get("stage_count", "?")
                    print(f"  [{i:4d}/{total_l2}] {osm_id}  {name} ({km} km, {sec} sections)", end=" ... ", flush=True)

                    wt = fetch_wt(osm_id)
                    if not wt:
                        print("no WT data")
                        entry["level2_descent"] = True
                        continue

                    section_ids = get_section_ids(wt)
                    if not section_ids:
                        print("0 sections at L1")
                        entry["level2_descent"] = True
                        entry["needs_level2"] = False
                        continue

                    sections_wt = [sw for sid in section_ids if (sw := fetch_wt(sid))]
                    apply_level2(entry, sections_wt)

                    real_stg = entry.get("stage_count", 0)
                    real_mx  = entry.get("max_stage_km", 0)
                    entry["needs_level2"] = real_mx > 40
                    if real_stg >= 2:
                        print(f"→ {real_stg} day stages, max {real_mx:.1f}km ✓")
                        promoted += 1
                    else:
                        print(f"0 day stages across {len(section_ids)} section(s)")

                    if i % 5 == 0:
                        save_catalog(catalog)

            except KeyboardInterrupt:
                print("\nInterrupted — saving progress...")
                save_catalog(catalog)
                sys.exit(0)

            print(f"\n  → {promoted}/{total_l2} entries updated with real day-stage counts")
            save_catalog(catalog)

    backfill_needs_level2(catalog)
    tag_child_sections(catalog)
    apply_filters(catalog)
    suppressed = apply_section_suppression(catalog)
    if suppressed:
        print(f"\n  → {suppressed} child-section entries suppressed (section_of_parent)")
    save_catalog(catalog)
    print_summary(catalog, args.smoke_test)


if __name__ == "__main__":
    main()
