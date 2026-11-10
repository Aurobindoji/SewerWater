"""Prefixes of the junction / pipe names chosen on the page (user request 30-Oct-2026: N-, J-, M-, MH-, P-, CO- ...),
for a layout and for a DXF import; the defaults as before (water J- / P-, sewer MH- / CO-)."""
import json
import os
import urllib.request

from test_water_ui import SAMPLE, call, server  # noqa: F401  (the fixture)
from test_dxf_extract import make_dxf
from sewer_app import ui
from water_app import netedit, server as wserver


def test_names(server):  # noqa: F811
    url, tmp = server
    with open(SAMPLE, encoding="utf-8") as fh:
        kml = fh.read()
    r = call(url + "/api/w/layout", {"name": "wp", "kml": kml, "gl_mode": "spots", "snap": 1, "spacing": 100})
    assert all(m["label"].startswith("J-") for m in r["manholes"]) and all(c["label"].startswith("P-") for c in r["conduits"])
    r = call(url + "/api/w/layout", {"name": "wp", "kml": kml, "gl_mode": "spots", "snap": 1, "spacing": 100,
                                     "node_prefix": "N-", "pipe_prefix": "L-"})
    assert all(m["label"].startswith("N-") for m in r["manholes"]) and all(c["label"].startswith("L-") for c in r["conduits"])
    bad = call(url + "/api/w/layout", {"name": "wp", "kml": kml, "gl_mode": "spots", "snap": 1, "spacing": 100,
                                       "node_prefix": "1 x;", "pipe_prefix": ""})        # not a prefix: the default
    assert all(m["label"].startswith("J-") for m in bad["manholes"]) and all(c["label"].startswith("P-") for c in bad["conduits"])
    # a DXF import with the sewer's names in the water module: kept, not renamed to P- / J-G when opened again
    netedit._UNDO.clear()
    src = str(tmp / "small.dxf")
    make_dxf(src)
    d = call(url + "/api/w/dxf_import", {"path": src, "name": "wpx", "pipe_layers": ["PIPE"], "mh_layers": ["MH"],
                                         "level_layers": ["GL"], "epsg": "local", "node_prefix": "MH-", "pipe_prefix": "CO-"})
    assert d["ok"] and all(c["label"].startswith("CO-") for c in d["conduits"])
    netedit._RENAME_SEEN.clear()
    assert netedit.rename_old_names(wserver.out_root(), "wpx") == []
    st = netedit.load(wserver.out_root(), "wpx")
    assert st["prefix"] == {"node": "MH-", "pipe": "CO-"} and all(k["label"].startswith("CO-") for k in st["net"]["conduits"])


def test_sewer_layout_names(tmp_path, monkeypatch):
    monkeypatch.setattr(ui, "PROJECTS", str(tmp_path / "projects"))
    monkeypatch.setattr(ui, "OUT_ROOT", str(tmp_path / "output"))
    with open(SAMPLE, encoding="utf-8") as fh:
        kml = fh.read()
    r = ui.run_layout("sp", kml)
    assert all(m["label"].startswith("MH-") for m in r["manholes"]) and all(c["label"].startswith("CO-") for c in r["conduits"])
    r = ui.run_layout("sp", kml, node_prefix="M-", pipe_prefix="S-")
    assert all(m["label"].startswith("M-") for m in r["manholes"]) and all(c["label"].startswith("S-") for c in r["conduits"])


def test_rename_the_prefix_of_a_network(tmp_path):
    """A network imported before: its names to another prefix at once (user request 30-Oct-2026), one undo step; a
    new name taken already: nothing changes."""
    import pytest
    src = str(tmp_path / "small.dxf")
    make_dxf(src)
    netedit._UNDO.clear()
    st = netedit.import_dxf(str(tmp_path / "out"), "rn", src, ["PIPE"], ["MH"], ["GL"], None, log=lambda s: None)
    netedit.apply(st, [{"op": "outfall", "mh": "MH-5", "on": True}])
    before = json.loads(json.dumps(st["net"]))
    netedit.apply(st, [{"op": "rename_prefix", "kind": "node", "from": "MH-", "to": "J-"},
                       {"op": "rename_prefix", "kind": "pipe", "from": "P-", "to": "L-"}])
    net = st["net"]
    assert sorted(net["nodes"]) == sorted("J-" + n[3:] for n in before["nodes"])
    assert all(k["label"].startswith("L-") and k["start_node"].startswith("J-") and k["stop_node"].startswith("J-")
               for k in net["conduits"])
    assert net["outfalls"] == ["J-5"] and st["prefix"] == {"pipe": "L-"}          # J-: the water default, not kept
    assert st["edits"][-1]["change"] == "names" and st["edits"][-1]["item"] == "P-* -> L-*"
    netedit.undo(st)                                                               # both back in one step
    assert st["net"] == before
    netedit.apply(st, [{"op": "connect", "a": "MH-1", "b": "MH-3", "label": "X1"}])
    netedit.apply(st, [{"op": "rename", "mh": "MH-6", "to": "J-1"}])
    with pytest.raises(ValueError):                                                # J-1 is there: nothing changes
        netedit.apply(st, [{"op": "rename_prefix", "kind": "node", "from": "MH-", "to": "J-"}])
    assert "MH-1" in st["net"]["nodes"]
