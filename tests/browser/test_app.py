"""Browser-level regression tests: save safety, chunked saves, export/import."""
import json

from harness import Mock

GOOD = {"format": "hiking-tracker-progress", "version": 1, "stages": {
    "ch-hike_1_1": {"completed_on": "2026-05-01", "rating": 5, "note": "imported note", "wishlist": False},
    "ch-hike_1_2": {"completed_on": "2026-04-10", "rating": 4, "note": None, "wishlist": True},
    "xx-hike_9_9": {"completed_on": "2026-04-10"},
    "ch-hike_1_3": {"rating": 9}}}


def test_no_js_errors_on_boot(open_app):
    page, _, errors = open_app()
    assert errors == []


def test_failed_state_load_never_overwrites(open_app):
    page, m, _ = open_app(Mock(user_state_get=500))
    page.evaluate("window.alert=()=>{}; window.event={stopPropagation(){}}; toggleStage('ch-hike_1_1')")
    page.wait_for_timeout(1200)
    assert m.rows == []


def test_single_stage_toggle_sends_one_row(open_app):
    page, m, _ = open_app()
    page.evaluate("window.event={stopPropagation(){}}; toggleStage('ch-hike_1_1')")
    page.wait_for_timeout(1200)
    assert [r["stage_key"] for r in m.rows] == ["ch-hike_1_1"]


def test_bulk_complete_is_chunked_and_undo_clears(open_app):
    page, m, _ = open_app(Mock(n_stages=450), wait_ms=5000)
    page.evaluate("markRouteComplete('ch-hike_1')")
    page.wait_for_timeout(4000)
    assert len(m.posts) == 3 and len({r["stage_key"] for r in m.rows}) == 450
    assert all(r["completed_on"] for r in m.rows)
    m.posts.clear()
    page.evaluate("markRouteComplete('ch-hike_1', true)")
    page.wait_for_timeout(4000)
    assert len(m.posts) == 3 and all(r["completed_on"] is None for r in m.rows)


def test_failed_save_shows_one_banner_and_retry_resends(open_app):
    page, m, _ = open_app(Mock(n_stages=450, user_state_post=500), wait_ms=5000)
    page.evaluate("markRouteComplete('ch-hike_1')")
    page.wait_for_timeout(4000)
    assert page.evaluate("failedSaves.size") == 450
    assert page.locator("#save-warning").count() == 1
    m.post_status = 201
    m.posts.clear()
    page.evaluate("document.querySelector('#save-warning a').click()")
    page.wait_for_timeout(3500)
    assert page.evaluate("failedSaves.size") == 0
    assert page.locator("#save-warning").count() == 0
    assert len(m.rows) == 450


def test_export_contents_and_guard(open_app):
    page, _, _ = open_app()
    page.evaluate("completed['ch-hike_1_1']='06.04.2026'; ratings['ch-hike_1_1']=4; notes['ch-hike_1_1']='nice'; wishlist['ch-hike_1_2']=true")
    with page.expect_download() as d:
        page.evaluate("exportProgress()")
    data = json.load(open(d.value.path()))
    assert data["format"] == "hiking-tracker-progress"
    assert data["stages"]["ch-hike_1_1"] == {"completed_on": "2026-04-06", "rating": 4, "note": "nice", "wishlist": False}
    assert data["stages"]["ch-hike_1_2"]["wishlist"] is True
    # refuses until user state has loaded (would export an empty file)
    page.evaluate("userStateLoaded=false; window.__a=null; window.alert=m=>window.__a=m")
    page.evaluate("exportProgress()")
    assert page.evaluate("window.__a")


def _import(page, m, tmp_path, text):
    f = tmp_path / "imp.json"
    f.write_text(text)
    n0 = len(m.posts)
    page.set_input_files("#import-file", str(f))
    page.wait_for_timeout(1200)
    return len(m.posts) - n0


def test_import_merge_rules_and_rejections(open_app, tmp_path):
    page, m, _ = open_app()
    page.on("dialog", lambda d: d.accept())
    page.evaluate("completed['ch-hike_1_1']='06.04.2026'; ratings['ch-hike_1_1']=3")
    assert _import(page, m, tmp_path, json.dumps(GOOD)) >= 1
    # local value kept, gaps filled, unknown stage / invalid rating skipped
    assert page.evaluate("[completed['ch-hike_1_1'],ratings['ch-hike_1_1'],notes['ch-hike_1_1'],completed['ch-hike_1_2'],ratings['ch-hike_1_2'],wishlist['ch-hike_1_2'],completed['ch-hike_1_3'],ratings['ch-hike_1_3']]") == \
        ["06.04.2026", 3, "imported note", "10.04.2026", 4, True, None, None]
    for bad in ("{nope", '{"format":"x"}',
                '{"format":"hiking-tracker-progress","version":2,"stages":{}}',
                '{"format":"hiking-tracker-progress","version":1}'):
        assert _import(page, m, tmp_path, bad) == 0
    assert _import(page, m, tmp_path, json.dumps(GOOD)) == 0  # idempotent
    page.evaluate("userStateLoaded=false")
    assert _import(page, m, tmp_path, json.dumps(GOOD)) == 0  # guarded until loaded
