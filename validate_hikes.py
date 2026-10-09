#!/usr/bin/env python3
"""
validate_hikes.py — sanity-check hikes.json before importing to Supabase.

Errors (exit 1): missing required keys, unknown land, duplicate (land, route_id),
duplicate stage_nr within a route, empty stages, negative/non-numeric numbers.
Warnings (exit 0): stage_nr not contiguous / not starting at 1, stages that
carry only the legacy hiking_hrs field.

Usage:
    python3 validate_hikes.py [path/to/hikes.json]
"""

import json
import sys
from collections import Counter

# Keep in sync with the Supabase CHECK constraint (see CLAUDE.md).
LANDS = {
    "at-hike", "be-hike", "ch-cycle", "ch-hike", "cz-hike", "de-hike", "dk-hike",
    "ee-hike", "es-hike", "eu-hike", "fr-hike", "hr-hike", "hu-hike", "ie-hike",
    "it-hike", "lt-hike", "lv-hike", "nl-hike", "no-hike", "pt-hike", "se-hike",
    "si-hike", "sk-hike", "uk", "uk-cycle",
}
ROUTE_KEYS = ("route_id", "land", "route_type", "name", "stages")
NUMERIC_STAGE_KEYS = ("dist_km", "elev_up", "elev_down", "duration_hrs", "hiking_hrs")


def validate(routes):
    errors, warnings = [], []

    if not isinstance(routes, list):
        return ["top level must be a list of routes"], warnings

    seen = Counter((r.get("land"), r.get("route_id")) for r in routes)
    for (land, rid), n in seen.items():
        if n > 1:
            errors.append(f"{land}:{rid} appears {n} times")

    for r in routes:
        tag = f"{r.get('land')}:{r.get('route_id')}"
        for k in ROUTE_KEYS:
            if k not in r:
                errors.append(f"{tag} missing key '{k}'")
        if r.get("land") not in LANDS:
            errors.append(f"{tag} unknown land {r.get('land')!r}")

        stages = r.get("stages") or []
        if not stages:
            errors.append(f"{tag} has no stages")
            continue

        nrs = []
        for s in stages:
            nr = s.get("stage_nr")
            if not isinstance(nr, int):
                errors.append(f"{tag} stage has non-integer stage_nr {nr!r}")
                continue
            nrs.append(nr)
            for k in NUMERIC_STAGE_KEYS:
                v = s.get(k)
                if v is None:
                    continue
                if isinstance(v, bool) or not isinstance(v, (int, float)):
                    errors.append(f"{tag} stage {nr} {k} is not numeric: {v!r}")
                elif v < 0:
                    errors.append(f"{tag} stage {nr} {k} is negative: {v}")
            if s.get("hiking_hrs") is not None and s.get("duration_hrs") is None:
                warnings.append(f"{tag} stage {nr} uses legacy hiking_hrs only")

        dupes = [n for n, c in Counter(nrs).items() if c > 1]
        if dupes:
            errors.append(f"{tag} duplicate stage_nr {sorted(dupes)}")
        elif nrs:
            ordered = sorted(nrs)
            if ordered[0] != 1:
                warnings.append(f"{tag} stage_nr starts at {ordered[0]}")
            elif ordered != list(range(1, len(ordered) + 1)):
                warnings.append(f"{tag} stage_nr is not contiguous")

    return errors, warnings


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "hikes.json"
    with open(path, encoding="utf-8") as f:
        routes = json.load(f)
    errors, warnings = validate(routes)

    n_stages = sum(len(r.get("stages") or []) for r in routes) if isinstance(routes, list) else 0
    legacy = [w for w in warnings if "legacy hiking_hrs" in w]
    other = [w for w in warnings if w not in legacy]

    for w in other:
        print(f"  [warn] {w}")
    if legacy:
        print(f"  [warn] {len(legacy)} stages use legacy hiking_hrs only (see issue #14)")
    for e in errors:
        print(f"  [error] {e}")

    print(f"{len(routes)} routes · {n_stages} stages · {len(errors)} errors · {len(warnings)} warnings")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
