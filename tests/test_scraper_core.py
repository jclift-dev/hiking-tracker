import json

import pytest

requests = pytest.importorskip("requests")
import scraper  # noqa: E402


def route(land="ch-hike", rid=1, stages=1):
    return {"route_id": rid, "land": land, "route_type": "national", "name": "R",
            "stages": [{"stage_nr": i + 1} for i in range(stages)]}


# --- persistence -----------------------------------------------------------

def test_load_existing_aborts_on_corrupt_file_and_keeps_it(tmp_path, monkeypatch):
    p = tmp_path / "hikes.json"
    p.write_text('[{"route_id":1,')
    monkeypatch.setattr(scraper, "OUTPUT", str(p))
    with pytest.raises(SystemExit):
        scraper.load_existing()
    assert p.read_text() == '[{"route_id":1,'
    assert (tmp_path / "hikes.json.bak").exists()


def test_load_existing_missing_file_starts_fresh(tmp_path, monkeypatch):
    monkeypatch.setattr(scraper, "OUTPUT", str(tmp_path / "nope.json"))
    assert scraper.load_existing() == {}


def test_save_then_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(scraper, "OUTPUT", str(tmp_path / "h.json"))
    scraper.save([route(), route("uk", 3)])
    assert set(scraper.load_existing()) == {("ch-hike", "national", 1), ("uk", "national", 3)}


# --- import ----------------------------------------------------------------

def test_import_rejects_unknown_land_before_any_request(monkeypatch, capsys):
    monkeypatch.setenv("SUPABASE_URL", "https://x.test")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "k")
    monkeypatch.setattr(scraper.SESSION, "post", lambda *a, **k: pytest.fail("no request expected"))
    with pytest.raises(SystemExit) as e:
        scraper.import_to_supabase([route(land="xx-hike")])
    assert e.value.code == 1
    assert "unknown land" in capsys.readouterr().out


def test_dry_run_sends_nothing_and_needs_no_credentials(monkeypatch, capsys):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    monkeypatch.setattr(scraper.SESSION, "post", lambda *a, **k: pytest.fail("no request expected"))
    scraper.import_to_supabase([route(stages=3), route("uk", 2, 2)], dry_run=True)
    out = capsys.readouterr().out
    assert "2 routes and 5 stages" in out and "ch-hike" in out and "uk" in out


class FakeResp:
    def __init__(self, code):
        self.status_code, self.ok, self.text = code, code < 400, "boom"


def fake_session(monkeypatch, codes):
    it = iter(codes)
    calls = []
    monkeypatch.setattr(scraper.time, "sleep", lambda s: None)
    monkeypatch.setattr(scraper.SESSION, "post",
                        lambda url, **k: (calls.append(url.rsplit("/", 1)[-1]) or FakeResp(next(it))))
    monkeypatch.setenv("SUPABASE_URL", "https://x.test")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "k")
    return calls


def test_import_success(monkeypatch):
    calls = fake_session(monkeypatch, [200, 200])
    scraper.import_to_supabase([route()])
    assert calls == ["routes", "stages"]


def test_import_retries_5xx_then_succeeds(monkeypatch):
    calls = fake_session(monkeypatch, [503, 200, 200])
    scraper.import_to_supabase([route()])
    assert calls == ["routes", "routes", "stages"]


def test_import_does_not_retry_4xx_and_skips_stages_when_routes_fail(monkeypatch):
    calls = fake_session(monkeypatch, [400])
    with pytest.raises(SystemExit) as e:
        scraper.import_to_supabase([route()])
    assert e.value.code == 1 and calls == ["routes"]


def test_import_exits_nonzero_when_stage_batch_fails(monkeypatch):
    fake_session(monkeypatch, [200, 400])
    with pytest.raises(SystemExit) as e:
        scraper.import_to_supabase([route()])
    assert e.value.code == 1


# --- SBB rate limit ---------------------------------------------------------

def test_sbb_429_loop_is_bounded(monkeypatch):
    class R429:
        status_code = 429
        def json(self): return {"errors": [{"message": "slow down"}]}
    monkeypatch.setattr(scraper.SESSION, "get", lambda *a, **k: R429())
    monkeypatch.setattr(scraper.time, "sleep", lambda s: None)
    monkeypatch.setattr(scraper, "SBB_MAX_429_ATTEMPTS", 3)
    with pytest.raises(scraper.SbbDailyLimitError):
        scraper.sbb_travel_minutes("Luzern")


# --- credentials -------------------------------------------------------------

def test_env_file_parser_handles_export_and_quotes(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('# c\nexport A_KEY="https://x/"\nB_KEY=\'abc\'\nC_KEY=v=1\n')
    for k in ("A_KEY", "B_KEY", "C_KEY"):
        monkeypatch.delenv(k, raising=False)
    scraper._load_env(str(env))
    import os
    assert os.environ["A_KEY"] == "https://x/" and os.environ["B_KEY"] == "abc" and os.environ["C_KEY"] == "v=1"
    for k in ("A_KEY", "B_KEY", "C_KEY"):
        monkeypatch.delenv(k, raising=False)


def test_importing_scraper_does_not_load_credentials(tmp_path):
    import os
    import subprocess
    import sys
    (tmp_path / ".env").write_text("SUPABASE_URL=https://x.test\nSUPABASE_SERVICE_KEY=secret\n")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = {k: v for k, v in os.environ.items() if not k.startswith("SUPABASE")}
    env["PYTHONPATH"] = root
    out = subprocess.run(
        [sys.executable, "-c",
         "import scraper, os; print(repr(scraper.SUPABASE_KEY), 'SUPABASE_SERVICE_KEY' in os.environ)"],
        cwd=tmp_path, env=env, capture_output=True, text=True, check=True).stdout
    assert out.strip().endswith("'' False"), out


# --- scraper_websites partial-scrape guard -----------------------------------

def test_websites_refuses_to_replace_a_route_with_fewer_stages():
    pytest.importorskip("bs4")
    import scraper_websites as w
    old = {"stages": [{}, {}, {}]}
    assert w.refuses_fewer_stages(old, {"stages": [{}, {}]}) is True
    assert w.refuses_fewer_stages(old, {"stages": [{}, {}]}, allow_fewer=True) is False
    assert w.refuses_fewer_stages(old, {"stages": [{}, {}, {}]}) is False      # same count
    assert w.refuses_fewer_stages(old, {"stages": [{}, {}, {}, {}]}) is False  # more is fine
    assert w.refuses_fewer_stages(None, {"stages": [{}]}) is False             # new route


# --- discover_trail_websites resume ---------------------------------------------

def test_resume_retries_fetch_errors_but_keeps_real_verdicts():
    pytest.importorskip("bs4")
    import discover_trail_websites as d
    prev = [{"osm_id": 1, "status": "found"},
            {"osm_id": 2, "status": "fetch_error"},
            {"osm_id": 3, "status": "no_stage_link"},
            {"osm_id": 4, "status": "stage_page_error"},
            {"osm_id": 5, "status": "stage_link_no_count"}]
    keep, retry = d.split_resumable(prev)
    assert [r["osm_id"] for r in keep] == [1, 3, 5]
    assert retry == 2


def test_load_existing_names_the_empty_routes_it_will_drop(tmp_path, monkeypatch, capsys):
    p = tmp_path / "h.json"
    good, empty = route(rid=1), route("uk", 9, stages=0)
    p.write_text(json.dumps([good, empty]))
    monkeypatch.setattr(scraper, "OUTPUT", str(p))
    existing = scraper.load_existing()
    out = capsys.readouterr().out
    assert list(existing) == [("ch-hike", "national", 1)]
    assert "1 stale/empty skipped" in out and "uk:9" in out and "will be dropped" in out
