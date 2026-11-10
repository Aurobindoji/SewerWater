"""Pipes without service connections on a DXF network (user request 30-Oct-2026: a feeder / transmission main, a pipe
across open land): marked on the page (netedit "set_noconn", one undo step), no population is put on them when it is
spread by pipe length - the total of the page or the wards drawn on the map; a new pipe along a crossing line is one
too. The water still flows through them."""
import collections

import pytest

from test_dxf_extract import make_dxf
from test_water_ui import call, server  # noqa: F401  (the fixture)
from water_app import netedit, ui_api


def _leaf(conduits, a="start_node", b="stop_node"):
    """A pipe with an end no other pipe meets, and that end."""
    deg = collections.Counter(n for c in conduits for n in (c[a], c[b]))
    for c in conduits:
        for n in (c[a], c[b]):
            if deg[n] == 1:
                return c, n
    raise AssertionError("no dead end")


def test_mark_pipes_without_connections(tmp_path):
    src = str(tmp_path / "small.dxf")
    make_dxf(src)
    netedit._UNDO.clear()
    st = netedit.import_dxf(str(tmp_path / "out"), "nc", src, ["PIPE"], ["MH"], ["GL"], None, log=lambda s: None)
    k, _ = _leaf(st["net"]["conduits"])
    netedit.apply(st, [{"op": "set_noconn", "ids": [k["id"]], "value": True}])
    assert k["no_conn"] is True and st["edits"][-1]["change"] == "no connections"
    page = netedit.page_data(st)
    assert [c["label"] for c in page["conduits"] if c.get("nc")] == [k["label"]]
    assert netedit.load(str(tmp_path / "out"), "nc")["net"]["conduits"] == st["net"]["conduits"]   # kept on disk
    # a marked pipe split in two: both parts without connections
    pts = netedit.converters(st)[0]([[(k["vertices"][0][0] + k["vertices"][-1][0]) / 2,
                                      (k["vertices"][0][1] + k["vertices"][-1][1]) / 2]])
    netedit.apply(st, [{"op": "split", "id": k["id"], "latlng": pts[0]}])
    assert sum(1 for c in st["net"]["conduits"] if c.get("no_conn")) == 2
    netedit.undo(st)
    netedit.apply(st, [{"op": "set_noconn", "ids": [k["id"]], "value": False}])
    assert not any(c.get("no_conn") for c in st["net"]["conduits"])
    netedit.undo(st)
    netedit.undo(st)                                                               # before the mark
    assert not any(c.get("no_conn") for c in st["net"]["conduits"])
    with pytest.raises(ValueError):
        netedit.apply(st, [{"op": "set_noconn", "ids": [99999], "value": True}])


def test_no_population_on_pipes_without_connections(server):  # noqa: F811
    url, tmp = server
    src = str(tmp / "small.dxf")
    make_dxf(src)
    netedit._UNDO.clear()
    d = call(url + "/api/w/dxf_import", {"path": src, "name": "wnc", "pipe_layers": ["PIPE"], "mh_layers": ["MH"],
                                         "level_layers": ["GL"], "epsg": "local"})
    assert d["ok"]
    c, end = _leaf(d["conduits"], "from", "to")
    r = call(url + "/api/w/net_edit", {"name": "wnc", "ops": [{"op": "set_noconn", "ids": [c["id"]], "value": True}]})
    assert r["ok"] and r["conduits_upd"][str(c["id"])]["nc"] == 1
    # the total of the page: none on the dead end of the marked pipe, the rest by pipe length as before
    _, net, pop = ui_api._load("wnc", {"pop_total": 1000})
    assert pop.get(end, 0) == 0 and sum(pop.values()) == pytest.approx(1000)
    other = sum(x["len"] for x in d["conduits"] if x["id"] != c["id"])
    assert net["noconn_note"] == {"pipes": 1, "m": round(c["len"]), "crossings": 0} and other > 0
    # the wards: the same, and the dead end is not "in no ward" when outside them (no one lives along the pipe)
    lls = [v["latlng"] for v in d["nodes"].values()]
    e = 1e-6
    box = [[min(p[0] for p in lls) - e, min(p[1] for p in lls) - e], [max(p[0] for p in lls) + e, min(p[1] for p in lls) - e],
           [max(p[0] for p in lls) + e, max(p[1] for p in lls) + e], [min(p[0] for p in lls) - e, max(p[1] for p in lls) + e]]
    _, net, pop = ui_api._load("wnc", {"wards": [{"name": "W1", "population": 600, "latlngs": box}]})
    assert pop.get(end, 0) == 0 and sum(pop.values()) == pytest.approx(600) and net["ward_note"]["outside"] == []
    a = d["nodes"]["MH-1"]["latlng"]
    oht = {"name": "Ex-OHT-1", "lat": a[0], "lng": a[1], "existing": "1", "capacity_kl": 200, "staging_m": 20}
    z = call(url + "/api/w/water_zoning", {"name": "wnc", "ohts": [oht], "pop_factor": 1, "pop_total": 1000})
    assert z["ok"], z.get("log")
    f = next(x for x in z["flags"] if "without service connections" in x["text"])
    assert f["text"].startswith("1 pipes (") and "बिना कनेक्शन" in f["hi"]
