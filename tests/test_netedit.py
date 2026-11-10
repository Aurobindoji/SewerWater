"""DXF network shown on the map and corrected there (netedit + the /api/net... calls of the UI), on the small drawing
of test_dxf_extract (local coordinates: no background map)."""
import csv
import json
import math
import os
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from sewer_app import netedit, network, ui

from synthetic import INP
from test_dxf_extract import make_dxf


@pytest.fixture
def st(tmp_path):
    path = str(tmp_path / "small.dxf")
    make_dxf(path)
    netedit._UNDO.clear()
    return netedit.import_dxf(str(tmp_path / "out"), "small", path, ["PIPE"], ["MH"], ["GL"], None, log=lambda s: None)


def test_import_and_page(st):
    d = netedit.page_data(st)
    assert d["local"] and len(d["nodes"]) == 6 and len(d["conduits"]) == 5
    assert d["nodes"]["MH-1"]["gl"] == 85.5
    # local drawing: metres laid out around 0 / 0, distances kept
    a, b = d["nodes"]["MH-1"]["latlng"], d["nodes"]["MH-2"]["latlng"]
    to_xy = netedit.converters(st)[1]
    (x1, y1), (x2, y2) = to_xy([a, b])
    assert abs(math.dist((x1, y1), (x2, y2)) - 30.0) < 0.01
    types = {i[1] for i in d["issues"]}
    assert "part without an outfall" in types                            # no outfall marked yet
    tx = netedit.texts_in(st, [a[0] - 0.0001, a[1] - 0.0001, a[0] + 0.0001, a[1] + 0.0001])
    assert {"MH-1", "85.50"} <= {t[2] for t in tx}                         # the drawing's texts next to MH-1


def test_edits_undo_and_log(st):
    ll = netedit.page_data(st)["nodes"]
    netedit.apply(st, [{"op": "outfall", "mh": "MH-5", "on": True}, {"op": "set_gl", "mh": "MH-3", "gl": 85.05}])
    assert st["net"]["nodes"]["MH-3"]["gl_source"] == netedit.USER_GL
    assert "part without an outfall" not in {i["type"] for i in netedit.issues(st)}
    netedit.apply(st, [{"op": "rename", "mh": "MH-6", "to": "MH-60"}])
    assert "MH-6" not in st["net"]["nodes"] and any(k["start_node"] == "MH-60" or k["stop_node"] == "MH-60"
                                                    for k in st["net"]["conduits"])
    with pytest.raises(ValueError):                                         # name taken: nothing changes
        netedit.apply(st, [{"op": "set_gl", "mh": "MH-1", "gl": 90}, {"op": "rename", "mh": "MH-60", "to": "MH-1"}])
    assert st["net"]["nodes"]["MH-1"]["ground"] == 85.5
    # a loop closed by a new sewer is reported; deleting it again removes the problem
    tn, tc = netedit.apply(st, [{"op": "connect", "a": "MH-1", "b": "MH-3"}])
    new = next(k for k in st["net"]["conduits"] if k["id"] in tc)
    assert abs(new["length_m"] - math.hypot(30, 30)) < 0.01
    assert "loop" in {i["type"] for i in netedit.issues(st)}
    netedit.apply(st, [{"op": "delete_conduit", "id": new["id"]}])
    assert "loop" not in {i["type"] for i in netedit.issues(st)}
    # split MH-1 - MH-2 in the middle, then merge the new manhole back into MH-1
    c12 = next(k for k in st["net"]["conduits"] if {k["start_node"], k["stop_node"]} == {"MH-1", "MH-2"})
    mid = [(ll["MH-1"]["latlng"][0] + ll["MH-2"]["latlng"][0]) / 2, (ll["MH-1"]["latlng"][1] + ll["MH-2"]["latlng"][1]) / 2]
    tn, _ = netedit.apply(st, [{"op": "split", "id": c12["id"], "latlng": mid}])
    mh = (tn - {"MH-1", "MH-2"}).pop()
    parts = [k["length_m"] for k in st["net"]["conduits"] if mh in (k["start_node"], k["stop_node"])]
    assert sorted(round(x, 2) for x in parts) == [15.0, 15.0]
    assert "no ground level" in {i["type"] for i in netedit.issues(st)}      # the new manhole has no GL yet
    netedit.apply(st, [{"op": "move", "mh": mh, "latlng": netedit.converters(st)[0]([[15.0, 3.0]])[0]}])
    assert sorted(round(k["length_m"], 2) for k in st["net"]["conduits"] if mh in (k["start_node"], k["stop_node"])) \
        == [round(math.hypot(15, 3), 2)] * 2
    netedit.apply(st, [{"op": "merge", "keep": "MH-1", "drop": mh}])
    k = next(k for k in st["net"]["conduits"] if "MH-1" in (k["start_node"], k["stop_node"]))
    assert {k["start_node"], k["stop_node"]} == {"MH-1", "MH-2"} and mh not in st["net"]["nodes"]
    n_edits = len(st["edits"])
    netedit.undo(st)                                                        # merge undone
    assert mh in st["net"]["nodes"] and len(st["edits"]) == n_edits - 1
    netedit.apply(st, [{"op": "delete_mh", "mh": mh}])                    # with both halves of MH-1 - MH-2
    assert len(st["net"]["conduits"]) == 4
    rows = netedit.auto_repair(st)                                          # nothing left to fill
    assert all(r["repair"] != "ground level interpolated along the sewer" for r in rows)
    f = netedit.save_network(st)
    net = network.read_extract_csv(f["manholes"], f["conduits"])
    assert len(net["nodes"]) == 6 and len(net["conduits"]) == 4
    with open(f["edits"], encoding="utf-8-sig") as fh:
        log = list(csv.DictReader(fh))
    assert [r["Change"] for r in log][:3] == ["outfall", "GL", "label"] and len(log) == len(st["edits"])
    again = netedit.load(st["_root"], "small")                              # the working state survives a restart
    assert again["net"] == st["net"]


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setattr(ui, "PROJECTS", str(tmp_path / "projects"))
    monkeypatch.setattr(ui, "OUT_ROOT", str(tmp_path / "output"))
    ui.NETS.clear()
    ui.ZCACHE.clear()
    srv = ThreadingHTTPServer(("127.0.0.1", 0), ui.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def call(url, body=None):
    req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())


def test_dxf_project_from_page(server, tmp_path):
    path = str(tmp_path / "small.dxf")
    make_dxf(path)
    lay = call(server + "/api/dxf_layers", {"path": path})
    assert lay["ok"] and lay["guess"]["pipe"] == ["PIPE"] and "MH" in lay["guess"]["mh"]
    d = call(server + "/api/dxf_import", {"path": path, "pipe_layers": ["PIPE"], "mh_layers": ["MH"],
                                          "level_layers": ["GL"], "epsg": "local"})
    assert d["ok"] and d["local"] and len(d["nodes"]) == 6
    assert [p["kind"] for p in call(server + "/api/projects")["projects"]] == ["dxf"]
    assert call(server + "/api/project?name=small")["kind"] == "dxf"
    e = call(server + "/api/net_edit", {"name": "small", "ops": [{"op": "outfall", "mh": "MH-5", "on": True}]})
    assert e["ok"] and e["nodes"]["MH-5"]["out"] and e["summary"]["outfalls"] == ["MH-5"]
    bad = call(server + "/api/net_edit", {"name": "small", "ops": [{"op": "rename", "mh": "MH-1", "to": "MH-2"}]})
    assert not bad["ok"]
    req = {"name": "small", "pop_total": 1500, "sewage_lpcd": INP["sewage_lpcd"], "start_depth": 0.7}
    assert call(server + "/api/zoning", req)["ok"]                  # the network as it is on the map, not saved yet
    assert call(server + "/api/net_save", {"name": "small"})["ok"]
    z = call(server + "/api/zoning", req)
    assert z["ok"], z["log"]
    cur = next(o for o in z["options"] if o["option"] == "CURRENT")                  # MH-5 marked on the map
    assert [x["manhole"] for x in cur["outlets"]] == ["MH-5"]
    assert "data_grade" not in z["inputs"] and z["inputs"]["pop_dist"] == "length"
    r = call(server + "/api/design", dict(req, option="CURRENT"))
    assert r["ok"], r["log"]
    assert r["summary"]["grade"] == "DPR" and r["summary"]["sewers"] == 5           # levels of the drawing
    assert all(os.path.isfile(f) for f in r["files"].values())


def make_far(tmp_path):
    """4 manholes in a row; MH-4's label and GL written ~14 m away from its symbol, a stray label MH-9 at 20 m."""
    import ezdxf
    path = str(tmp_path / "far.dxf")
    doc = ezdxf.new()
    msp = doc.modelspace()
    for lay in ("PIPE", "MH", "GL"):
        doc.layers.add(lay)
    pts = {"MH-1": (0.0, 0.0), "MH-2": (30.0, 0.0), "MH-3": (60.0, 0.0), "MH-4": (90.0, 0.0)}
    gls = {"MH-1": 84.5, "MH-2": 84.4, "MH-3": 84.3, "MH-4": 84.1}
    msp.add_lwpolyline(list(pts.values()), dxfattribs={"layer": "PIPE"})
    for lab, (x, y) in pts.items():
        msp.add_circle((x, y), 0.6, dxfattribs={"layer": "MH"})
        lx, ly = (x + 1.0, y + 1.0) if lab != "MH-4" else (x - 6.0, y + 13.0)      # MH-4 written ~14 m away
        msp.add_text(lab, dxfattribs={"layer": "MH", "insert": (lx, ly), "height": 0.8})
        msp.add_text(f"{gls[lab]:.2f}", dxfattribs={"layer": "GL", "insert": (lx, ly + 1.5), "height": 0.8})
    msp.add_text("MH-9", dxfattribs={"layer": "MH", "insert": (82.0, 18.0), "height": 0.8})  # a stray label, 20 m
    doc.saveas(path)
    st = netedit.import_dxf(str(tmp_path / "out"), "far", path, ["PIPE"], ["MH"], ["GL"], None, log=lambda s: None)
    return st, pts


def test_label_written_far_from_its_symbol(tmp_path):
    """A label (and its GL) written 14 m away from the symbol - beyond dxf_extract's search radius: the manhole gets
    a generated name; netedit suggests the unused drawing label with the GL next to it, and applying it leaves a
    CHECK to look at."""
    st, pts = make_far(tmp_path)
    gen = [n for n in st["net"]["nodes"] if n not in pts]
    assert len(gen) == 1 and st["net"]["nodes"][gen[0]]["ground"] is None
    sug = netedit.suggestions(st)
    assert sug[gen[0]]["label"] == "MH-4" and sug[gen[0]]["gl"]["value"] == 84.1 and 13 < sug[gen[0]]["d"] < 15
    assert netedit.page_data(st)["suggest"][gen[0]][:3] == ["MH-4", sug[gen[0]]["d"], 84.1]
    netedit.auto_repair(st)                          # GL interpolated first (from MH-3) ...
    assert "interpolated" in st["net"]["nodes"][gen[0]]["gl_source"]
    netedit.apply(st, [{"op": "apply_suggestions"}])
    v = st["net"]["nodes"]["MH-4"]                   # ... replaced by the level written next to the label
    assert v["ground"] == 84.1 and gen[0] not in st["net"]["nodes"]
    iss = {(i["type"], i["item"]) for i in netedit.issues(st) if not i["reviewed"]}
    assert (netedit.SUGGESTED, "MH-4") in iss and ("no drawing label (name generated)", gen[0]) not in iss
    assert [e["change"] for e in st["edits"]][-2:] == ["label (suggested)", "GL (suggested)"]
    assert netedit.suggestions(st) == {}             # MH-4 is named now: the stray MH-9 is not offered again


def test_gl_from_the_label_text(tmp_path):
    """Named by hand after the GLs were interpolated: the level written next to the manhole's own label replaces
    the interpolated one ('Drawing के GL लगाएँ')."""
    st, pts = make_far(tmp_path)
    gen = next(n for n in st["net"]["nodes"] if n not in pts)
    netedit.auto_repair(st)
    netedit.apply(st, [{"op": "rename", "mh": gen, "to": "MH-4"}])
    assert "interpolated" in st["net"]["nodes"]["MH-4"]["gl_source"]
    L = netedit.label_levels(st)
    assert list(L) == ["MH-4"] and L["MH-4"][0] == 84.1 and netedit.page_data(st)["label_levels"] == 1
    netedit.apply(st, [{"op": "gl_from_labels"}])
    assert st["net"]["nodes"]["MH-4"]["ground"] == 84.1 and netedit.label_levels(st) == {}


def test_results_kept_for_the_page(server, tmp_path):
    """Zoning and design of the page are kept with the project and given back on opening it (page reload). They work
    on the network as it is on the map - no 'सहेजें' first (user decision 19-Oct-2026); after a change of the network
    they are marked stale, saved or not."""
    path = str(tmp_path / "small.dxf")
    make_dxf(path)
    call(server + "/api/dxf_import", {"path": path, "pipe_layers": ["PIPE"], "mh_layers": ["MH"], "level_layers": ["GL"],
                                      "epsg": "local"})
    call(server + "/api/net_edit", {"name": "small", "ops": [{"op": "outfall", "mh": "MH-5", "on": True}]})
    assert call(server + "/api/last_results?name=small")["network_saved"]               # a network to zone, unsaved
    req = {"name": "small", "pop_total": 1500, "sewage_lpcd": 108, "start_depth": 0.7, "max_zones": 8}
    assert call(server + "/api/zoning", req)["ok"]
    assert call(server + "/api/design", dict(req, option="CURRENT"))["ok"]
    call(server + "/api/net_save", {"name": "small"})                                  # saving changes nothing:
    last = call(server + "/api/last_results?name=small")                              # the results stay valid
    assert last["network_current"] and not last["zoning"]["stale"] and not last["design"]["stale"]
    assert last["zoning"]["req"]["pop_total"] == 1500 and last["design"]["summary"]["option"] == "CURRENT"
    call(server + "/api/net_edit", {"name": "small", "ops": [{"op": "set_gl", "mh": "MH-1", "gl": 85.6}]})
    last = call(server + "/api/last_results?name=small")
    assert last["zoning"]["stale"] and last["design"]["stale"]                         # made from the old network
    z = call(server + "/api/zoning", req)                                             # the edited network, unsaved
    assert z["ok"] and not z["cached"]
    assert not call(server + "/api/last_results?name=small")["zoning"]["stale"]


def test_design_on_given_outfalls_only(server, tmp_path):
    """Page option 'केवल दिए गए outfalls पर': only option GIVEN is worked out (no pumping station for depth) and
    designed; 'स्वतंत्र' gives the usual options without GIVEN; without any outfall / STP the given mode refuses."""
    path = str(tmp_path / "small.dxf")
    make_dxf(path)
    call(server + "/api/dxf_import", {"path": path, "pipe_layers": ["PIPE"], "mh_layers": ["MH"], "level_layers": ["GL"],
                                      "epsg": "local"})
    call(server + "/api/net_save", {"name": "small"})
    req = {"name": "small", "pop_total": 1500, "sewage_lpcd": 108, "start_depth": 0.7}
    bad = call(server + "/api/zoning", dict(req, mode="given"))
    assert not bad["ok"] and "outfall" in bad["log"]
    z = call(server + "/api/zoning", dict(req, mode="given", stp="MH-5"))
    assert z["ok"] and [o["option"] for o in z["options"]] == ["GIVEN"] and z["options"][0]["pumping_for_depth"] == 0
    d = call(server + "/api/design", dict(req, mode="given", stp="MH-5", option="GIVEN"))
    assert d["ok"] and d["summary"]["outfalls"] == ["MH-5"]
    auto = call(server + "/api/zoning", dict(req, stp="MH-5"))
    assert auto["ok"] and "GIVEN" not in [o["option"] for o in auto["options"]]
    assert call(server + "/api/last_results?name=small")["zoning"]["req"]["mode"] is None   # 'auto' = not given


def test_dxf_picked_on_the_page_is_uploaded(server, tmp_path):
    """A DXF picked in the file dialog: its bytes go to projects/dxf/ (the page cannot know the path); then read as
    one given by its path. Only .dxf."""
    path = str(tmp_path / "picked.dxf")
    make_dxf(path)
    with open(path, "rb") as fh:
        data = fh.read()

    def up(name, body):
        req = urllib.request.Request(server + "/api/dxf_upload?file=" + urllib.parse.quote(name), data=body,
                                     headers={"Content-Type": "application/octet-stream"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            return json.loads(e.read())
    r = up("picked.dxf", data)
    assert r["ok"] and r["path"].startswith(str(tmp_path / "projects" / "dxf"))
    with open(r["path"], "rb") as fh:
        assert fh.read() == data
    lay = call(server + "/api/dxf_layers", {"path": r["path"]})
    assert lay["ok"] and lay["guess"]["pipe"] == ["PIPE"]
    assert call(server + "/api/projects")["projects"] == []                 # the copy is no project by itself
    assert not up("drawing.dwg", b"x")["ok"]


def test_place_whole_network_on_the_map(st):
    """A drawing in local coordinates placed on the map: MH-1 to its real place (UTM zone there), lengths kept,
    a point on it (an OHT) moved with it; placed again (fine-tuning) only shifts; undo goes back."""
    d0 = netedit.page_data(st)
    a0, b0 = d0["nodes"]["MH-1"]["latlng"], d0["nodes"]["MH-2"]["latlng"]
    moved = netedit.place(st, a0, [25.2833, 82.9871], [b0])
    d = netedit.page_data(st)
    a, b = d["nodes"]["MH-1"]["latlng"], d["nodes"]["MH-2"]["latlng"]
    assert not d["local"] and d["epsg"] == 32644
    assert abs(a[0] - 25.2833) < 1e-6 and abs(a[1] - 82.9871) < 1e-6
    assert abs(moved[0][0] - b[0]) < 1e-6 and abs(moved[0][1] - b[1]) < 1e-6        # the OHT went with it
    to_xy = netedit.converters(st)[1]
    (x1, y1), (x2, y2) = to_xy([a, b])
    assert abs(math.dist((x1, y1), (x2, y2)) - 30.0) < 0.01                         # lengths kept
    assert st["net"]["nodes"]["MH-1"]["xy"] == netedit.load(st["_root"], "small")["net"]["nodes"]["MH-1"]["xy"]
    netedit.place(st, a, [25.2834, 82.9871])                                         # 11 m north
    a2 = netedit.page_data(st)["nodes"]["MH-1"]["latlng"]
    assert abs(a2[0] - 25.2834) < 1e-6 and st["epsg"] == 32644
    netedit.undo(st); netedit.undo(st)
    assert netedit.page_data(st)["local"] and netedit.page_data(st)["nodes"]["MH-1"]["latlng"] == a0


def test_layer_preview_tells_lines_from_points(tmp_path):
    """👁 of a layer: PIPE = lines (3 entities, 150 m, on the map), MH = circles and names (points), GL = level
    texts; the same drawing read once for the table and the previews."""
    path = str(tmp_path / "small.dxf")
    make_dxf(path)
    netedit._INV.clear()
    rows, _ = netedit.dxf_layers(path)
    p = netedit.dxf_preview(path, "PIPE")
    assert p["types"] == {"LINE": 2, "LWPOLYLINE": 1} and p["n_lines"] == 3 and p["line_m"] == 150.0
    assert len(p["lines"]) == 3 and not p["points"] and p["local"]
    assert len(p["lines"][2]) == 4                                                  # MH-2 .. MH-5
    m = netedit.dxf_preview(path, "MH", 32644)
    assert not m["lines"] and m["types"] == {"CIRCLE": 6, "TEXT": 6} and not m["local"]
    assert {q[3] for q in m["points"]} == {"text", "circle"} and "MH-1" in m["samples"]
    g = netedit.dxf_preview(path, "GL")
    assert "85.50" in g["samples"] and len(netedit._INV) == 1
    with pytest.raises(ValueError):
        netedit.dxf_preview(path, "NOPE")


def test_layer_guesses_house_numbers_drains_and_node_symbols(tmp_path):
    """HH-12 house numbers are no manholes; in water a drain (nala) is no pipe; a 'node' layer of symbols with
    levels is the junctions' layer."""
    import ezdxf
    doc = ezdxf.new()
    msp = doc.modelspace()
    for lay in ("PIPE152", "nala", "node", "HOUSE HOLDS"):
        doc.layers.add(lay)
    blk = doc.blocks.new("FILLED_CIRCLE")
    blk.add_circle((0, 0), 0.5)
    for i in range(8):
        msp.add_line((i * 30.0, 0), ((i + 1) * 30.0, 0), dxfattribs={"layer": "PIPE152"})
        msp.add_blockref("FILLED_CIRCLE", (i * 30.0, 0), dxfattribs={"layer": "node"})
        msp.add_text(f"{78 + i / 10:.3f}m", dxfattribs={"layer": "node", "insert": (i * 30.0 + 1, 1), "height": 0.8})
        msp.add_text(f"HH-{i + 1}", dxfattribs={"layer": "HOUSE HOLDS", "insert": (i * 30.0 + 5, 12), "height": 0.8})
    msp.add_lwpolyline([(0, -20), (250, -20)], dxfattribs={"layer": "nala"})
    path = str(tmp_path / "chit.dxf")
    doc.saveas(path)
    netedit._INV.clear()
    _, gw = netedit.dxf_layers(path, water=True)
    assert gw["pipe"] == ["PIPE152"] and gw["mh"] == ["node"] and gw["level"] == ["node"]
    _, gs = netedit.dxf_layers(path)
    assert "HOUSE HOLDS" not in gs["mh"] and "node" in gs["mh"]


def test_delete_what_a_loop_selects_at_once(st):
    """The select tool's loop (user 30-Oct-2026): the page sends the pipes with both ends inside, then the junctions
    inside - one list, one undo step; a pipe leaving the loop goes with its junction."""
    before = json.loads(json.dumps(st["net"]))
    inside = {"MH-1", "MH-2"}
    conds = [k["id"] for k in st["net"]["conduits"] if {k["start_node"], k["stop_node"]} <= inside]
    leaving = [k["id"] for k in st["net"]["conduits"] if len({k["start_node"], k["stop_node"]} & inside) == 1]
    assert conds and leaving
    netedit.apply(st, [{"op": "delete_conduit", "id": i} for i in conds] + [{"op": "delete_mh", "mh": n} for n in sorted(inside)])
    ids = {k["id"] for k in st["net"]["conduits"]}
    assert not inside & set(st["net"]["nodes"]) and not (set(conds) | set(leaving)) & ids
    netedit.undo(st)                                                         # all back in one step
    assert st["net"] == before
