"""Atomic JSON writes: a crash or Ctrl-C mid-write must never leave a truncated file."""

import json
import os
import tempfile


def write_json_atomic(path, obj, **dump_kwargs):
    """Serialise obj to path via a temp file in the same directory + os.replace."""
    path = os.fspath(path)
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, **dump_kwargs)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def write_hikes_json(path, routes):
    """Canonical hikes.json writer (atomic, compact, UTF-8).

    Every script that writes hikes.json must use this so the committed 4 MB file
    keeps one format and a run only produces a real diff, not a reformat.
    """
    write_json_atomic(path, routes, ensure_ascii=False, separators=(",", ":"))
