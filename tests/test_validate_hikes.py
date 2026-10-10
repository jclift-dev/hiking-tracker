import copy
import json
import os

import validate_hikes as v

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def good_route(**over):
    r = {
        "route_id": 1, "land": "ch-hike", "route_type": "national", "name": "R",
        "stages": [
            {"stage_nr": 1, "dist_km": 10, "elev_up": 5, "elev_down": 5, "duration_hrs": 3},
            {"stage_nr": 2, "dist_km": 8, "elev_up": 1, "elev_down": 1, "duration_hrs": 2},
        ],
    }
    r.update(over)
    return r


def errs(routes):
    return v.validate(routes)[0]


def warns(routes):
    return v.validate(routes)[1]


def test_valid_data_has_no_errors_or_warnings():
    assert v.validate([good_route()]) == ([], [])


def test_real_hikes_json_has_no_errors():
    with open(os.path.join(ROOT, "hikes.json"), encoding="utf-8") as f:
        assert errs(json.load(f)) == []


def test_duplicate_route_key():
    assert any("appears 2 times" in e for e in errs([good_route(), good_route()]))


def test_same_route_id_different_land_is_fine():
    assert errs([good_route(), good_route(land="uk")]) == []


def test_unknown_land():
    assert any("unknown land" in e for e in errs([good_route(land="xx-hike")]))


def test_missing_key():
    r = good_route()
    del r["name"]
    assert any("missing key 'name'" in e for e in errs([r]))


def test_no_stages():
    assert any("no stages" in e for e in errs([good_route(stages=[])]))


def test_duplicate_stage_nr():
    r = good_route()
    r["stages"][1]["stage_nr"] = 1
    assert any("duplicate stage_nr" in e for e in errs([r]))


def test_negative_and_non_numeric_values():
    r = good_route()
    r["stages"][0]["elev_down"] = -3
    r["stages"][1]["dist_km"] = "8"
    e = errs([r])
    assert any("elev_down is negative" in x for x in e)
    assert any("dist_km is not numeric" in x for x in e)


def test_bool_is_not_numeric():
    r = good_route()
    r["stages"][0]["dist_km"] = True
    assert any("not numeric" in e for e in errs([r]))


def test_non_contiguous_and_late_start_are_only_warnings():
    r = good_route()
    r["stages"][1]["stage_nr"] = 4
    assert errs([r]) == [] and any("not contiguous" in w for w in warns([r]))
    r2 = copy.deepcopy(good_route())
    for s in r2["stages"]:
        s["stage_nr"] += 1
    assert errs([r2]) == [] and any("starts at 2" in w for w in warns([r2]))


def test_legacy_hiking_hrs_warns():
    r = good_route()
    del r["stages"][0]["duration_hrs"]
    r["stages"][0]["hiking_hrs"] = 3
    assert errs([r]) == [] and any("legacy hiking_hrs" in w for w in warns([r]))


def test_top_level_must_be_list():
    assert v.validate({"a": 1})[0]


def test_every_route_maps_to_a_source():
    import route_sources
    with open(os.path.join(ROOT, "hikes.json"), encoding="utf-8") as f:
        routes = json.load(f)
    summary = route_sources.summarise(routes)
    assert "UNMAPPED" not in summary, summary.get("UNMAPPED", {}).get("route_ids")
    assert sum(v["routes"] for v in summary.values()) == len(routes)
    assert summary["schweizmobil.ch"]["routes"] == sum(1 for r in routes if r["land"].startswith("ch-"))
