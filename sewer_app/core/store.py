"""Files of the sewer module written whole or not at all, and data kept as JSON (rewrite stage 2, 26-Nov-2026;
this module's own copy of water_app/core/store.py - the two modules share no code).

Every file goes first to a temporary name in its own folder and then takes the real name in one step (os.replace):
a crash, a full disk or a second click never leaves half a file. Kept data is JSON only - never pickle, which runs
code when it is read (user decision 26-Nov-2026).

`typed=True` keeps what plain JSON loses, so the data reads back exactly as it was written: a tuple stays a tuple,
and a dict with keys other than text ({350: 2}) keeps them.
"""
import json
import os
import tempfile
import time

_TUPLE, _MAP = "__tuple__", "__map__"


def _replace(tmp, path):
    """os.replace, tried again for a moment when Windows holds the target (an antivirus or indexer reading it)."""
    for i in range(10):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if i == 9:
                raise
            time.sleep(0.05 * (i + 1))


def write_bytes(path, data):
    """data -> path, whole or not at all."""
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".~", suffix=".part", dir=folder)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        _replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def write_text(path, text):
    write_bytes(path, text.encode("utf-8"))


def _tag(x):
    if isinstance(x, dict):
        if all(isinstance(k, str) for k in x):
            if len(x) == 1 and next(iter(x)) in (_TUPLE, _MAP):  # a real key of that name: kept as a map
                return {_MAP: [[_tag(k), _tag(v)] for k, v in x.items()]}
            return {k: _tag(v) for k, v in x.items()}
        return {_MAP: [[_tag(k), _tag(v)] for k, v in x.items()]}
    if isinstance(x, tuple):
        return {_TUPLE: [_tag(v) for v in x]}
    if isinstance(x, list):
        return [_tag(v) for v in x]
    return x


def _untag(d):
    if len(d) == 1:
        if _TUPLE in d:
            return tuple(d[_TUPLE])
        if _MAP in d:
            return {(tuple(k) if isinstance(k, list) else k): v for k, v in d[_MAP]}
    return d


def dumps(obj, typed=False):
    return json.dumps(_tag(obj) if typed else obj, ensure_ascii=False, separators=(",", ":"))


def loads(text, typed=False):
    return json.loads(text, object_hook=_untag if typed else None)


def write_json(path, obj, typed=False):
    """obj as JSON -> path, whole or not at all."""
    write_text(path, dumps(obj, typed))


def read_json(path, typed=False):
    """The JSON of path (OSError when there is none, ValueError when it is not JSON)."""
    with open(path, encoding="utf-8") as fh:
        return loads(fh.read(), typed)
