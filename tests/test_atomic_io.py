import json
import os

import pytest

import atomic_io
from atomic_io import write_json_atomic


def test_writes_and_replaces(tmp_path):
    p = tmp_path / "x.json"
    write_json_atomic(p, {"a": 1})
    write_json_atomic(p, {"a": 2}, separators=(",", ":"))
    assert p.read_text() == '{"a":2}'
    assert os.listdir(tmp_path) == ["x.json"]


def test_failed_serialisation_keeps_original_and_leaves_no_temp(tmp_path):
    p = tmp_path / "x.json"
    write_json_atomic(p, {"ok": True})
    with pytest.raises(TypeError):
        write_json_atomic(p, {"bad": object()})
    assert json.loads(p.read_text()) == {"ok": True}
    assert os.listdir(tmp_path) == ["x.json"]


def test_creates_file_when_missing(tmp_path):
    p = tmp_path / "new.json"
    write_json_atomic(str(p), [1, 2])
    assert json.loads(p.read_text()) == [1, 2]


def test_write_hikes_json_is_compact_utf8(tmp_path):
    p = tmp_path / "h.json"
    atomic_io.write_hikes_json(p, [{"name": "Müritz", "stages": []}])
    assert p.read_text(encoding="utf-8") == '[{"name":"Müritz","stages":[]}]'


def test_committed_hikes_json_is_in_canonical_format():
    """A writer that reformats hikes.json would turn every run into a 4 MB diff."""
    import json
    import os
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hikes.json")
    raw = open(path, encoding="utf-8").read()
    assert raw == json.dumps(json.loads(raw), ensure_ascii=False, separators=(",", ":"))
