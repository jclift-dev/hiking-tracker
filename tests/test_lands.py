import os
import re

import lands

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_eu_lands_exclude_swiss_and_are_a_subset():
    assert not any(l.startswith("ch-") for l in lands.EU_LANDS)
    assert lands.EU_LANDS < lands.ALL_LANDS
    assert lands.ALL_LANDS - lands.EU_LANDS == {"ch-hike", "ch-cycle"}


def test_check_sql_lists_every_land_for_both_tables():
    sql = lands.check_sql()
    for table in ("routes", "stages"):
        assert f"ALTER TABLE {table} ADD CONSTRAINT {table}_land_check" in sql
    for land in lands.ALL_LANDS:
        assert sql.count(f"'{land}'") == 2


def test_claude_md_check_template_matches_lands_py():
    text = open(os.path.join(ROOT, "CLAUDE.md"), encoding="utf-8").read()
    m = re.search(r"CHECK \(land IN \(([^)]*)\)\)", text)
    assert set(re.findall(r"'([^']+)'", m.group(1))) == set(lands.ALL_LANDS)


def test_land_table_in_claude_md_matches_lands_py():
    text = open(os.path.join(ROOT, "CLAUDE.md"), encoding="utf-8").read()
    documented = set(re.findall(r"^\| `([a-z-]+)` +\|", text, re.M)) - {"land"}  # minus header cell
    assert documented == set(lands.ALL_LANDS)
