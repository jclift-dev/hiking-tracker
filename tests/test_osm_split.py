import pytest

pytest.importorskip("requests")
import scraper_osm as o  # noqa: E402

# Web Mercator metres near the equator ~ real metres, so 1000 units ~ 1 km.
def way(x0, x1, step=1000):
    n = int(abs(x1 - x0) // step)
    d = step if x1 > x0 else -step
    return [[x0 + i * d, 0] for i in range(n + 1)]


def node(*ways):
    return {"main": [{"ways": [{"geometry": {"type": "LineString", "coordinates": w}} for w in ways]}]}


def test_chain_orders_and_orients_segments():
    line = o.chain_ways([way(0, 10000), way(20000, 10000), way(20000, 30000)])
    xs = [p[0] for p in line]
    assert xs == sorted(xs) and xs[0] == 0 and xs[-1] == 30000


def test_chain_fixes_reversed_first_way():
    line = o.chain_ways([way(10000, 0), way(10000, 20000)])
    xs = [p[0] for p in line]
    assert xs[0] in (0, 20000) and xs == sorted(xs) or xs == sorted(xs, reverse=True)
    assert abs(xs[0] - xs[-1]) == 20000  # no jump back over the first way


def test_split_forward_segments_are_used():
    n = {"main": [{"ways": [{"geometry": {"type": "LineString", "coordinates": way(0, 10000)}}]},
                  {"forward": [{"ways": [{"geometry": {"type": "LineString", "coordinates": way(10000, 20000)}}]}],
                   "backward": [{"ways": [{"geometry": {"type": "LineString", "coordinates": way(20000, 10000)}}]}]}]}
    assert len(o._ways_merc(n)) == 2


def test_split_route_stage_count_and_shared_boundaries():
    stages, km = o.split_route(node(way(0, 60000)), 20, official_m=60000)
    assert len(stages) == 3 and km == 60
    for a, b in zip(stages, stages[1:]):
        assert a[-1] == b[0]


def test_split_route_refuses_on_length_mismatch(capsys):
    assert o.split_route(node(way(0, 60000)), 20, official_m=120000) == ([], 0)
    assert "not splitting" in capsys.readouterr().out


def test_dedupe_names_makes_consecutive_duplicates_distinct():
    out = o.dedupe_names(["A", "Warren", "Warren", "B"], 60)
    assert out == ["A", "Warren", "Warren (km 40)", "B"]
    assert o.dedupe_names(["A", "B"], 10) == ["A", "B"]
