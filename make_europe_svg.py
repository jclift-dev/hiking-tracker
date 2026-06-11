#!/usr/bin/env python3
"""
Generate simplified SVG path data for the Europe dashboard map.
Downloads Natural Earth admin-1 10m GeoJSON (~40 MB, cached locally) and
projects to a flat equirectangular SVG with Douglas-Peucker simplification.

Usage:
    python3 make_europe_svg.py > europe_paths.js
    # Then paste the europePaths constant into index.html

Output format:
    const europePaths = [
      ['de-by', 'M...'],   // Bayern
      ['fr-ara', 'M...'],  // Auvergne-Rhône-Alpes
      ...
    ];
"""

import json
import math
import os
import sys

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CACHE_FILE = ".ne_admin1.json"
NE_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
    "master/geojson/ne_10m_admin_1_states_provinces.geojson"
)

# Countries to include by ISO A2 code
INCLUDE_COUNTRIES = {
    "GB", "FR", "DE", "AT", "IT", "ES", "IE", "CH", "SI", "MC", "LI", "PT",
    "HU", "CZ", "NL", "BE", "SE", "NO", "EE", "HR", "SK", "DK",
    "RS", "BG", "GR", "TR", "LT", "LV",
}

# SVG viewport — equirectangular projection
LON_MIN, LON_MAX = -12.0, 35.0
LAT_MIN, LAT_MAX = 34.0, 72.0
SVG_W, SVG_H = 1100, 920

# Minimum area (in SVG px²) to include a polygon (filters tiny islands/enclaves).
MIN_AREA_PX2 = 20.0
ALWAYS_INCLUDE = {"MC", "LI", "SI"}  # country codes exempt from min-area filter

# Douglas-Peucker epsilon in SVG px units.
# Higher = more simplification (fewer points).
DP_EPSILON = 1.5


# ---------------------------------------------------------------------------
# Projection helpers
# ---------------------------------------------------------------------------

def to_svg(lon, lat):
    x = (lon - LON_MIN) / (LON_MAX - LON_MIN) * SVG_W
    y = (LAT_MAX - lat) / (LAT_MAX - LAT_MIN) * SVG_H
    return round(x, 1), round(y, 1)


def polygon_area_px(pts):
    """Shoelace formula — absolute area for a list of (x,y) points."""
    n = len(pts)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += pts[i][0] * pts[j][1]
        area -= pts[j][0] * pts[i][1]
    return abs(area) / 2.0


# ---------------------------------------------------------------------------
# Douglas-Peucker simplification
# ---------------------------------------------------------------------------

def perp_dist(point, line_start, line_end):
    """Perpendicular distance from point to the line through line_start/end."""
    x0, y0 = point
    x1, y1 = line_start
    x2, y2 = line_end
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(x0 - x1, y0 - y1)
    return abs(dy * x0 - dx * y0 + x2 * y1 - y2 * x1) / math.hypot(dx, dy)


def rdp(points, epsilon):
    """Ramer-Douglas-Peucker polyline simplification."""
    if len(points) < 3:
        return points
    dmax, idx = 0.0, 0
    for i in range(1, len(points) - 1):
        d = perp_dist(points[i], points[0], points[-1])
        if d > dmax:
            dmax, idx = d, i
    if dmax > epsilon:
        left  = rdp(points[:idx + 1], epsilon)
        right = rdp(points[idx:],     epsilon)
        return left[:-1] + right
    return [points[0], points[-1]]


# ---------------------------------------------------------------------------
# Region code helpers
# ---------------------------------------------------------------------------

# Ireland: Natural Earth uses counties. Map each county name substring → province code.
IE_COUNTY_PROVINCE = {
    "Dublin": "ie-le", "Wicklow": "ie-le", "Wexford": "ie-le",
    "Carlow": "ie-le", "Kilkenny": "ie-le", "Waterford": "ie-le",
    "Tipperary": "ie-le", "Laois": "ie-le", "Offaly": "ie-le",
    "Kildare": "ie-le", "Meath": "ie-le", "Westmeath": "ie-le",
    "Longford": "ie-le", "Louth": "ie-le",
    "Cork": "ie-mu", "Kerry": "ie-mu", "Limerick": "ie-mu",
    "Clare": "ie-mu",
    "Galway": "ie-co", "Mayo": "ie-co", "Sligo": "ie-co",
    "Leitrim": "ie-co", "Roscommon": "ie-co",
    "Donegal": "ie-ul", "Cavan": "ie-ul", "Monaghan": "ie-ul",
    "Antrim": "ie-ul", "Armagh": "ie-ul", "Down": "ie-ul",
    "Fermanagh": "ie-ul", "Londonderry": "ie-ul", "Derry": "ie-ul",
    "Tyrone": "ie-ul",
}


def make_code(props):
    """Return a stable lowercase region code for a Natural Earth feature."""
    iso_a2 = (props.get("iso_a2") or "").upper().strip()
    name   = (props.get("name")   or "").strip()

    # Monaco / Liechtenstein / Slovenia — single polygon each
    if iso_a2 == "MC":
        return "mc"
    if iso_a2 == "LI":
        return "li"
    if iso_a2 == "SI":
        return "si"

    # Switzerland / Slovenia: merge to single country code (canton/municipality
    # detail is either in the Swiss view or below the granularity we track)
    if iso_a2 == "CH":
        return "ch"
    if iso_a2 == "SI":
        return "si"

    # Ireland: map county → province
    if iso_a2 == "IE":
        for county, code in IE_COUNTY_PROVINCE.items():
            if county.lower() in name.lower():
                return code
        return "ie-ul"  # N.Ireland catchall

    # All others: use iso_3166_2 (e.g. 'DE-BY' → 'de-by')
    iso2 = (props.get("iso_3166_2") or "").strip()
    if iso2 and iso2 not in ("-99", "") and "-" in iso2:
        return iso2.lower()

    # Fallback: country + adm1_code slug
    adm1 = (props.get("adm1_code") or "").strip()
    if adm1:
        slug = adm1.split("-")[-1].lower()
        return f"{iso_a2.lower()}-{slug}"

    slug = name.lower().replace(" ", "-")[:16]
    return f"{iso_a2.lower()}-{slug}"


# ---------------------------------------------------------------------------
# GeoJSON loading
# ---------------------------------------------------------------------------

def load_geojson():
    if os.path.exists(CACHE_FILE):
        print(f"[info] Using cached {CACHE_FILE}", file=sys.stderr)
        with open(CACHE_FILE) as f:
            return json.load(f)
    print("[info] Downloading Natural Earth admin-1 10m (~40 MB)…", file=sys.stderr)
    r = requests.get(NE_URL, timeout=180, stream=True)
    r.raise_for_status()
    data = b""
    for chunk in r.iter_content(65536):
        data += chunk
        print(f"\r  {len(data)//1024} KB", end="", flush=True, file=sys.stderr)
    print(file=sys.stderr)
    parsed = json.loads(data)
    with open(CACHE_FILE, "w") as f:
        json.dump(parsed, f)
    print(f"[info] Saved to {CACHE_FILE}", file=sys.stderr)
    return parsed


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    data = load_geojson()

    # code → {"name": str, "paths": [str]} — paths merged across multiple polygons
    regions = {}
    skipped = 0

    for feat in data["features"]:
        props  = feat.get("properties", {})
        iso_a2 = (props.get("iso_a2") or "").upper().strip()

        if iso_a2 not in INCLUDE_COUNTRIES:
            continue

        code   = make_code(props)
        name   = props.get("name_en") or props.get("name") or code
        geom   = feat.get("geometry", {})
        gtype  = geom.get("type", "")
        exempt = iso_a2 in ALWAYS_INCLUDE

        def process_polygon(rings):
            outer = rings[0]
            # Quick bbox check — skip if completely outside viewport
            lons = [c[0] for c in outer]
            lats = [c[1] for c in outer]
            if min(lons) > LON_MAX + 3 or max(lons) < LON_MIN - 3:
                return
            if min(lats) > LAT_MAX + 3 or max(lats) < LAT_MIN - 3:
                return

            projected = [to_svg(lon, lat) for lon, lat in outer]
            area = polygon_area_px(projected)

            if not exempt and area < MIN_AREA_PX2:
                return

            # Use a smaller epsilon for tiny exempt features (e.g. Monaco) so
            # they survive simplification without collapsing to a line.
            epsilon = DP_EPSILON if area >= MIN_AREA_PX2 else 0.3
            simplified = rdp(projected, epsilon)
            if len(simplified) < 3:
                return

            # Deduplicate consecutive identical points
            deduped = [simplified[0]]
            for pt in simplified[1:]:
                if pt != deduped[-1]:
                    deduped.append(pt)
            if len(deduped) < 3:
                return

            d = "M" + " L".join(f"{x},{y}" for x, y in deduped) + " Z"

            if code not in regions:
                regions[code] = {"name": name, "paths": []}
            regions[code]["paths"].append(d)

        if gtype == "Polygon":
            process_polygon(geom["coordinates"])
        elif gtype == "MultiPolygon":
            for poly in geom["coordinates"]:
                process_polygon(poly)
        else:
            skipped += 1

    print(
        f"[info] {len(regions)} region codes generated; {skipped} non-polygon features skipped",
        file=sys.stderr,
    )

    # Output JavaScript
    print("// Generated by make_europe_svg.py")
    print("// Paste this constant into index.html (before renderDashboard)")
    print(f"// {len(regions)} regions across {len(INCLUDE_COUNTRIES)} countries")
    print("const europePaths = [")
    for code, info in sorted(regions.items()):
        combined = " ".join(info["paths"])
        safe = combined.replace("\\", "\\\\").replace("'", "\\'")
        print(f"  ['{code}', '{safe}'],  // {info['name']}")
    print("];")


if __name__ == "__main__":
    main()
