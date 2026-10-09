"""
Single source of truth for `land` values.

Adding a land: add it to ALL_LANDS below, run `python3 lands.py` and apply the
printed SQL in Supabase, then update the land table in CLAUDE.md and
docs/trails.md. enrich_regions.py, validate_hikes.py and scraper.py --import
all read from here.
"""

ALL_LANDS = frozenset({
    "at-hike", "be-hike", "ch-cycle", "ch-hike", "cz-hike", "de-hike", "dk-hike",
    "ee-hike", "es-hike", "eu-hike", "fr-hike", "hr-hike", "hu-hike", "ie-hike",
    "it-hike", "lt-hike", "lv-hike", "nl-hike", "no-hike", "pt-hike", "se-hike",
    "si-hike", "sk-hike", "uk", "uk-cycle",
})

# Swiss lands come from SchweizMobil and have no country/admin1 enrichment.
EU_LANDS = frozenset(l for l in ALL_LANDS if not l.startswith("ch-"))


def check_sql():
    values = ",".join(f"'{l}'" for l in sorted(ALL_LANDS))
    out = []
    for table in ("routes", "stages"):
        out.append(f"ALTER TABLE {table} DROP CONSTRAINT {table}_land_check;")
        out.append(f"ALTER TABLE {table} ADD CONSTRAINT {table}_land_check\n  CHECK (land IN ({values}));")
    return "\n".join(out)


if __name__ == "__main__":
    print(check_sql())
