"""
Map every route in hikes.json to the website/service its data came from.

Used by docs/data-sources.md (see issue #48) and the tests; a future
per-route `source` field in hikes.json / Supabase can be generated from this.

Precedence: (1) routes owned by a dedicated scraper (AUTHORITATIVE), (2) the
host of the `_source_url` the scraper recorded on the stages, (3) OpenStreetMap
(`_osm_id` on the stages, via Waymarked Trails), otherwise "UNMAPPED".
"""
import collections
from urllib.parse import urlparse

OSM = "OpenStreetMap (Waymarked Trails)"

# (land, route_id) -> host, for routes whose scraper doesn't record _source_url.
AUTHORITATIVE = {
    ("uk", 1): "southwestcoastpath.org.uk",      # scraper_swcp
    # OSM geometry split into day stages by distance (scraper_osm.SPLIT_KM; #48):
    ("uk", 3): OSM, ("uk", 5): OSM, ("uk", 6): OSM, ("uk", 7): OSM, ("uk", 8): OSM,
    ("uk", 15): OSM, ("de-hike", 73): OSM, ("se-hike", 22): OSM,
    ("fr-hike", 1): "le-gr20.fr",                # scraper_gr20
    ("fr-hike", 2): "podiensis.com",             # scraper_gr (GR65)
    ("fr-hike", 3): "chamina-voyages.com",       # scraper_gr (GR70)
    ("it-hike", 1): "altavia1dolomites.com",     # scraper_av1
    ("de-hike", 1): "saechsische-schweiz.de",    # scraper_malerweg
    ("eu-hike", 5): "hiking-europe.eu",          # scraper_e1
    ("eu-hike", 16): "viefrancigene.org",        # scraper_via_francigena
}


def _stage_host(route):
    c = collections.Counter()
    for s in route["stages"]:
        u = s.get("_source_url") or s.get("_url")
        if u:
            c[urlparse(u).netloc.replace("www.", "")] += 1
    return c.most_common(1)[0][0] if c else None


def source_of(route):
    land, rid = route["land"], route["route_id"]
    if land.startswith("ch-"):
        return "schweizmobil.ch"
    if (land, rid) in AUTHORITATIVE:
        return AUTHORITATIVE[(land, rid)]
    if land == "de-hike" and (rid == 2 or 10 <= rid <= 31):
        return "schwarzwaldverein.de"            # scraper_schwarzwaldverein
    host = _stage_host(route)
    if host:
        return host
    if any(s.get("_osm_id") for s in route["stages"]):
        return OSM
    return "UNMAPPED"


def summarise(routes):
    """{source: {routes, stages, prose_chars, route_ids}}"""
    out = collections.defaultdict(lambda: {"routes": 0, "stages": 0, "prose_chars": 0, "route_ids": []})
    for r in routes:
        o = out[source_of(r)]
        o["routes"] += 1
        o["stages"] += len(r["stages"])
        o["prose_chars"] += len(r.get("description") or "") + sum(len(s.get("description") or "") for s in r["stages"])
        o["route_ids"].append(f"{r['land']}:{r['route_id']}")
    return dict(out)


if __name__ == "__main__":
    import json
    import sys
    with open(sys.argv[1] if len(sys.argv) > 1 else "hikes.json", encoding="utf-8") as f:
        data = json.load(f)
    for k, v in sorted(summarise(data).items(), key=lambda kv: -kv[1]["routes"]):
        print(f"{k:36s} routes {v['routes']:4d}  stages {v['stages']:5d}  prose chars {v['prose_chars']:8d}")
