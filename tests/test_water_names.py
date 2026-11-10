"""Water network names and texts on the map (user requests 21 / 22-Oct-2026): pipes are P-<n>, not the sewer's CO-<n>,
junctions without a drawing label J-G<n>, not MH-G<n> - a network imported before is renamed once, with its kept
zoning / design; the drawing's own junction names / GLs are not
written a second time next to the page's labels."""
import json
import os

import pytest

from water_app import netedit

from test_dxf_extract import make_dxf


@pytest.fixture
def st(tmp_path):
    path = str(tmp_path / "small.dxf")
    make_dxf(path)
    netedit._UNDO.clear()
    netedit._TEXTS.clear()
    return netedit.import_dxf(str(tmp_path / "out"), "small", path, ["PIPE"], ["MH"], ["GL"], None, log=lambda s: None)


def test_pipes_are_p(st):
    labels = [k["label"] for k in st["net"]["conduits"]]
    assert labels and all(x.startswith("P-") for x in labels)
    netedit.apply(st, [{"op": "connect", "a": "MH-1", "b": "MH-3"}])              # a new pipe: P- too
    assert st["net"]["conduits"][-1]["label"].startswith("P-")


def test_old_co_names_renamed_once(st, tmp_path):
    root, folder = str(tmp_path / "out"), str(tmp_path / "out" / "small")
    netedit.store(st)
    p = netedit.state_path(root, "small")
    with open(p, encoding="utf-8") as fh:
        old = fh.read().replace('"P-', '"CO-')                                     # as imported before 21-Oct-2026
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(old)
    zf = os.path.join(folder, "small_wzoning_ui.json")
    with open(zf, "w", encoding="utf-8") as fh:
        json.dump({"pipe_dma": {"CO-1": "OHT-1/DMA-1"}, "closed": [{"pipe": "CO-2"}], "note": "MCO-3 stays"}, fh)
    netedit._RENAME_SEEN.clear()
    st2 = netedit.load(root, "small")
    assert all(k["label"].startswith("P-") for k in st2["net"]["conduits"])
    with open(zf, encoding="utf-8") as fh:
        z = json.load(fh)
    assert z == {"pipe_dma": {"P-1": "OHT-1/DMA-1"}, "closed": [{"pipe": "P-2"}], "note": "MCO-3 stays"}
    with open(p + ".CO_names.bak", encoding="utf-8") as fh:                       # the old file kept
        assert fh.read() == old
    netedit._RENAME_SEEN.clear()
    assert netedit.rename_old_names(root, "small") == []                          # already P-: nothing more


def test_drawing_texts_not_twice(st):
    to_ll = netedit.converters(st)[0]
    (s, w), (n, e) = to_ll([[-20.0, -20.0], [100.0, 100.0]])
    bb = [min(s, n), min(w, e), max(s, n), max(w, e)]
    every = {t[2] for t in netedit.texts_in(st, bb)}
    shown = {t[2] for t in netedit.texts_in(st, bb, hide_shown=True)}
    assert {"MH-1", "85.50"} <= every                                              # name and GL of MH-1 in the drawing
    assert not shown                                                               # the page writes all of them itself
    netedit.apply(st, [{"op": "set_gl", "mh": "MH-1", "gl": 86.0}])              # GL changed on the map: the drawing's
    shown = {t[2] for t in netedit.texts_in(st, bb, hide_shown=True)}              # own value is worth seeing again
    assert shown == {"85.50"}


def test_unlabelled_junctions_are_j_and_old_mh_g_renamed(tmp_path):
    import ezdxf
    path = str(tmp_path / "nolab.dxf")
    doc = ezdxf.new()
    msp = doc.modelspace()
    for lay in ("PIPE", "GL"):
        doc.layers.add(lay)
    pts = [(0.0, 0.0), (30.0, 0.0), (30.0, 30.0), (60.0, 0.0)]
    for a, b in ((0, 1), (1, 2), (1, 3)):
        msp.add_line(pts[a], pts[b], dxfattribs={"layer": "PIPE"})
    for i, (x, y) in enumerate(pts):                                    # GLs only - no junction names in the drawing
        msp.add_text(f"{85 - i * 0.2:.2f}", dxfattribs={"layer": "GL", "insert": (x + 1.0, y - 1.5), "height": 0.8})
    doc.saveas(path)
    netedit._UNDO.clear()
    root = str(tmp_path / "out")
    st = netedit.import_dxf(root, "nolab", path, ["PIPE"], [], ["GL"], None, log=lambda s: None)
    assert st["net"]["nodes"] and all(n.startswith("J-G") for n in st["net"]["nodes"])
    netedit.store(st)
    p = netedit.state_path(root, "nolab")
    with open(p, encoding="utf-8") as fh:
        old = fh.read().replace('"J-G', '"MH-G').replace('"P-', '"CO-')                   # as imported before
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(old)
    netedit._RENAME_SEEN.clear()
    st2 = netedit.load(root, "nolab")
    assert all(n.startswith("J-G") for n in st2["net"]["nodes"])
    assert all(k["label"].startswith("P-") and k["start_node"].startswith("J-G") for k in st2["net"]["conduits"])
    assert os.path.isfile(p + ".MH_names.bak") and os.path.isfile(p + ".CO_names.bak")
