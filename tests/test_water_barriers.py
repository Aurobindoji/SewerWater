"""Barrier lines (highway, expressway, railway ... - user request 27-Oct-2026): no pipe crosses one. A pipe crossing
it is cut there, both parts ending 1 m short of the line (user decision 27-Oct-2026); a KML's barrier lines are no
roads; zoning and design work on the cut network, so no OZ reaches across the line."""
import os

import pytest

from water_app import barriers as wb
from water_app import geo as wgeo
from sewer_app import geo as sgeo

from test_water_ui import SAMPLE, call, server  # noqa: F401  (the fixture)


def _net():
    return {"nodes": {"A": {"xy": (0.0, 0.0), "ground": 80.0}, "B": {"xy": (100.0, 0.0), "ground": 90.0},
                      "C": {"xy": (100.0, 100.0), "ground": 90.0}, "D": {"xy": (0.0, 100.0), "ground": 80.0}},
            "conduits": [{"label": "P1", "start_node": "A", "stop_node": "B", "length_m": 100.0,
                          "vertices": [(0.0, 0.0), (100.0, 0.0)]},
                         {"label": "P2", "start_node": "B", "stop_node": "C", "length_m": 100.0, "vertices": []},
                         # drawn from its stop node: the vertices are turned round
                         {"label": "P3", "start_node": "C", "stop_node": "D", "length_m": 100.0,
                          "vertices": [(0.0, 100.0), (100.0, 100.0)]}]}


def test_a_pipe_crossing_is_cut_both_sides_short_of_the_line():
    bar = [{"name": "NH-19", "type": "highway", "xy": [(40.0, -50.0), (40.0, 150.0)]}]
    net, cuts = wb.cut(_net(), bar)
    c = {k["label"]: k for k in net["conduits"]}
    assert set(c) == {"P1-1", "P1-2", "P2", "P3-1", "P3-2"}
    assert c["P1-1"]["start_node"] == "A" and c["P1-1"]["length_m"] == pytest.approx(39.0)
    assert c["P1-2"]["stop_node"] == "B" and c["P1-2"]["length_m"] == pytest.approx(59.0)
    assert c["P1-1"]["vertices"][-1] == pytest.approx((39.0, 0.0)) and c["P1-2"]["vertices"][0] == pytest.approx((41.0, 0.0))
    assert net["nodes"]["P1-x1"]["ground"] == pytest.approx(83.9)                   # GL along the pipe
    assert net["nodes"]["P1-x2"]["ground"] == pytest.approx(84.1)
    assert c["P3-1"]["start_node"] == "C" and c["P3-1"]["vertices"][0] == pytest.approx((100.0, 100.0))
    assert c["P3-1"]["length_m"] == pytest.approx(59.0)
    assert {x["pipe"] for x in cuts} == {"P1", "P3"} and all(x["barrier"] == "NH-19" for x in cuts)
    assert "NH-19 (Highway): 2 pipes cut" in wb.summary(bar, cuts)
    # nothing crosses: every part on one side of x = 40
    for k in net["conduits"]:
        xs = [p[0] for p in (k["vertices"] or [net["nodes"][k["start_node"]]["xy"], net["nodes"][k["stop_node"]]["xy"]])]
        assert max(xs) < 40 or min(xs) > 40


def test_two_crossings_drop_the_middle_and_a_junction_on_the_line_keeps_one_side():
    bars = [{"name": "rail", "type": "railway", "xy": [(30.0, -10.0), (30.0, 10.0)]},
            {"name": "canal", "type": "canal", "xy": [(70.0, -10.0), (70.0, 10.0)]}]
    net, cuts = wb.cut({"nodes": _net()["nodes"], "conduits": _net()["conduits"][:1]}, bars)
    assert sorted(k["label"] for k in net["conduits"]) == ["P1-1", "P1-2"]
    assert {k["label"]: k["length_m"] for k in net["conduits"]} == pytest.approx({"P1-1": 29.0, "P1-2": 29.0})
    assert {x["barrier"] for x in cuts} == {"rail", "canal"}
    # the line through the junction B itself: only A's side stays
    net, _ = wb.cut({"nodes": _net()["nodes"], "conduits": _net()["conduits"][:1]},
                    [{"name": "x", "type": "other", "xy": [(100.0, -5.0), (100.0, 5.0)]}])
    assert [k["label"] for k in net["conduits"]] == ["P1-1"]
    # no barrier, or one along a pipe / away from it: unchanged
    for bar in ([], [{"name": "y", "type": "other", "xy": [(0.0, 0.0), (100.0, 0.0)]}],
                [{"name": "z", "type": "other", "xy": [(500.0, 0.0), (500.0, 10.0)]}]):
        net, cuts = wb.cut(_net(), bar)
        assert [k["label"] for k in net["conduits"]] == ["P1", "P2", "P3"] and not cuts


@pytest.mark.parametrize("geo", [wgeo, sgeo])
def test_kml_barrier_lines_are_no_roads(tmp_path, geo):
    kml = tmp_path / "b.kml"
    kml.write_text('<?xml version="1.0"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
                   '<Folder><name>Roads (Paths)</name><Placemark><name>Road 1</name><LineString><coordinates>'
                   '83.0,25.3,0 83.01,25.3,0</coordinates></LineString></Placemark></Folder>'
                   '<Folder><name>Barrier lines</name><Placemark><name>NH-19</name><ExtendedData><Data name="kind">'
                   '<value>barrier</value></Data><Data name="type"><value>highway</value></Data></ExtendedData>'
                   '<LineString><coordinates>83.005,25.29,0 83.005,25.31,0</coordinates></LineString></Placemark>'
                   '</Folder></Document></kml>', encoding="utf-8")
    k = geo.read_kml(str(kml))
    assert [x["name"] for x in k["lines"]] == ["Road 1"]
    assert [x["name"] for x in k["barriers"]] == ["NH-19"] and k["barriers"][0]["data"]["type"] == "highway"


def _side(b, ll):
    (a0, a1), (b0, b1) = b["latlngs"][0], b["latlngs"][1]
    return (b0 - a0) * (ll[1] - a1) - (b1 - a1) * (ll[0] - a0) > 0


def test_zoning_and_design_do_not_cross_a_barrier(server):  # noqa: F811
    import ezdxf
    url, tmp = server
    with open(SAMPLE, encoding="utf-8") as fh:
        kml = fh.read()
    r = call(url + "/api/w/layout", {"name": "wbar", "kml": kml, "gl_mode": "spots", "snap": 1, "spacing": 100})
    assert r["ok"], r["log"]
    lats = sorted(m["latlng"][0] for m in r["manholes"])
    lngs = sorted({m["latlng"][1] for m in r["manholes"]})
    mid = (lngs[len(lngs) // 2] + lngs[len(lngs) // 2 + 1]) / 2           # between two junctions (none on the line)
    bar = {"name": "Railway 1", "type": "railway", "latlngs": [[lats[0] - 0.01, mid], [lats[-1] + 0.01, mid]]}
    req = {"name": "wbar", "ohts": [], "pop_factor": 3, "barriers": [bar]}
    z = call(url + "/api/w/water_zoning", req)
    assert z["ok"], z.get("log")
    assert z["cuts"] and z["cut_parts"] and z["barriers"][0]["name"] == "Railway 1"
    assert any("Railway 1 (Railway line)" in f["text"] and "pipes cut" in f["text"] for f in z["flags"])
    # every message also in Hindi for the page (user request 30-Oct-2026), the English kept for the files
    assert all(f.get("hi") for f in z["flags"])
    assert any(f["hi"].startswith("Railway 1 (रेलवे लाइन):") and "pipes कटे" in f["hi"] for f in z["flags"])
    # a gap in the drawing (user 30-Oct-2026): J-40 and J-46, 40 m apart along the top road, joined only through the
    # other side of the line - now two pieces on one side; none across the line (cut there on purpose)
    assert [(g["a"], g["b"], g["dist_m"]) for g in z["near_gaps"]] == [("J-40", "J-46", 40.03)]
    assert len({_side(bar, p) for p in z["near_gaps"][0]["latlngs"]}) == 1
    assert any("1 gap(s) of 50 m or less" in f["text"] and "J-40 - J-46 40.03 m" in f["text"] and
               "J-40 - J-46 40.03 m" in f["hi"] for f in z["flags"])
    # the gap's distance from the page (user request 7-Nov-2026): within 30 m, none
    z2 = call(url + "/api/w/water_zoning", dict(req, near_m="30"))
    assert z2["near_gaps"] == [] and not any("gap(s)" in f["text"] for f in z2["flags"])
    # why each OZ (user request 30-Oct-2026): a piece cut off by the line
    assert all(x["why"]["kind"] == "proposed" and x["why"]["barriers"] == ["Railway 1"] and not x["why"]["isolated"]
               for x in z["zones"])
    d = call(url + "/api/w/water_design", req)
    assert d["ok"], d.get("log")
    cut = {c["pipe"] for c in d["cuts"]}
    labels = {p["label"] for p in d["pipes"]}
    assert not cut & labels and {c["label"] for c in d["cut_parts"]} <= labels
    assert any(c["check"] == "barrier lines: no pipe crosses" for c in d["checks"])
    # every OZ on one side of the line
    side = {}
    for n in d["nodes"]:
        if n.get("oz"):
            side.setdefault(n["oz"], set()).add(_side(bar, n["latlng"]))
    assert len(side) >= 2 and all(len(v) == 1 for v in side.values()), side
    assert call(url + "/api/w/water_last?name=wbar")["design"]["req"]["barriers"][0]["name"] == "Railway 1"
    x = call(url + "/api/w/water_export", {"name": "wbar"})
    assert x["ok"] and x["counts"]["barriers"] == 1 and x["counts"]["pipes"] == len(d["pipes"])
    msp = ezdxf.readfile(x["path"]).modelspace()
    assert len(msp.query("LWPOLYLINE[layer=='W_BARRIER']")) == 1
    assert any(t.dxf.text == "Railway 1 (Railway line)" for t in msp.query("TEXT[layer=='W_BARRIER']"))


def test_dxf_project_keeps_its_barrier_lines(server):  # noqa: F811
    url, tmp = server
    b = [{"latlngs": [[25.3, 83.0], [25.31, 83.0]], "props": {"name": "NH-19", "type": "highway"}}]
    assert call(url + "/api/w/barriers_save", {"name": "dx", "barriers": b})["ok"]
    assert call(url + "/api/w/barriers?name=dx")["barriers"] == b
    assert call(url + "/api/w/barriers?name=none")["barriers"] == []
    assert os.path.isfile(tmp / "w_projects" / "dx.barriers.json")


def test_a_crossing_lets_a_pipe_through_or_is_a_new_pipe():
    """Crossings (user request 27-Oct-2026): where a crossing line crosses a barrier, the pipe there (within 10 m)
    is not cut; where no pipe crosses there, the crossing line is a new pipe between the nearest junctions."""
    bar = [{"name": "NH-19", "type": "highway", "gap_m": 1.0, "xy": [(40.0, -50.0), (40.0, 150.0)]}]
    xs = [{"name": "C1", "xy": [(35.0, 3.0), (45.0, 3.0)]},                    # 3 m from P1's crossing: P1 through
          {"name": "C2", "xy": [(10.0, 50.0), (90.0, 50.0)]}]                  # no pipe there: a new pipe
    pts = wb.crossing_points(xs, bar)
    assert [(ln, n, t) for ln, _, n, t in pts] == [("NH-19", "C1", 10.0), ("NH-19", "C2", 10.0)]
    net, made = wb.add_crossing_pipes(_net(), xs, bar, pts)
    m = {x["crossing"]: x for x in made}
    assert m["C1"]["existing"] == ["P1"] and m["C1"]["pipe"] is None
    assert m["C2"]["pipe"] == "X-C2" and not m["C2"]["existing"]
    new = next(c for c in net["conduits"] if c["label"] == "X-C2")
    assert (new["start_node"], new["stop_node"]) == ("A", "B")                  # the nearest (ties: by name)
    assert new["vertices"][0] == (0.0, 0.0) and new["vertices"][-1] == (100.0, 0.0)
    net, cuts = wb.cut(net, bar, pts)
    labels = {c["label"] for c in net["conduits"]}
    assert "P1" in labels and "X-C2" in labels                                  # through, not cut
    assert {"P3-1", "P3-2"} <= labels and {c["pipe"] for c in cuts} == {"P3"}  # P3: no crossing, cut
    assert "C1 (NH-19): P1 go(es) through" in wb.crossing_summary(made)
    # each crossing line's own distances (user request 7-Nov-2026): within 2 m P1 (3 m away) is cut, and no
    # junction within 1 m of the line's ends: no new pipe either
    xs = [dict(xs[0], tol_m=2.0, snap_m=1.0)]
    pts = wb.crossing_points(xs, bar)
    net, made = wb.add_crossing_pipes(_net(), xs, bar, pts)
    assert made[0]["existing"] == [] and made[0]["pipe"] is None and "within 1 m" in made[0]["note"]
    assert "P1" in {c["pipe"] for c in wb.cut(net, bar, pts)[1]}
    c = wb.clean_crossings([{"name": "x", "latlngs": [[0, 0], [1, 1]], "tol_m": "", "snap_m": "5000"}], lambda p: p)
    assert (c[0]["tol_m"], c[0]["snap_m"]) == (wb.CROSS_TOL_M, wb.SNAP_MAX_MAX_M)    # empty: 10 m; at most 1000 m


def test_crossings_from_the_page(server):  # noqa: F811
    url, tmp = server
    with open(SAMPLE, encoding="utf-8") as fh:
        kml = fh.read()
    r = call(url + "/api/w/layout", {"name": "wx", "kml": kml, "gl_mode": "spots", "snap": 1, "spacing": 100})
    lats = sorted({m["latlng"][0] for m in r["manholes"]})
    lngs = sorted({m["latlng"][1] for m in r["manholes"]})
    mid = (lngs[len(lngs) // 2] + lngs[len(lngs) // 2 + 1]) / 2
    bar = {"name": "Rail", "type": "railway", "latlngs": [[lats[0] - 0.01, mid], [lats[-1] + 0.01, mid]]}
    z0 = call(url + "/api/w/water_zoning", {"name": "wx", "ohts": [], "pop_factor": 3, "barriers": [bar]})
    c = z0["cuts"][0]                                                            # a pipe cut there without a crossing
    xing = {"name": "Bridge", "latlngs": [[c["latlng"][0], mid - 0.0002], [c["latlng"][0], mid + 0.0002]]}
    z = call(url + "/api/w/water_zoning", {"name": "wx", "ohts": [], "pop_factor": 3, "barriers": [bar],
                                          "crossings": [xing]})
    assert z["ok"], z.get("log")
    assert c["pipe"] not in {x["pipe"] for x in z["cuts"]} and len(z["cuts"]) == len(z0["cuts"]) - 1
    assert z["crossings"][0]["existing"] == [c["pipe"]]
    assert any("crossings: Bridge (Rail)" in f["text"] for f in z["flags"])
    assert call(url + "/api/w/crossings_save", {"name": "dx", "crossings": [{"latlngs": xing["latlngs"], "props": {}}]})["ok"]
    assert call(url + "/api/w/crossings?name=dx")["crossings"][0]["latlngs"] == xing["latlngs"]
