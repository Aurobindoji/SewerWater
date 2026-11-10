"""Barrier lines in the sewer module (user request 27-Oct-2026: highway / expressway / railway ... - no sewer crosses
one): a sewer crossing it is cut there, both parts ending 1 m short of the line; zoning and design work on the cut
network, so the side cut off from the STP drains to an outlet of its own."""
import os

from sewer_app import barriers as sb

from test_ui import SAMPLE, call, server  # noqa: F401  (the fixture)


def _crosses(pts, bar):
    a, b = bar["latlngs"]
    for p, q in zip(pts, pts[1:]):
        h = sb._hit((p[1], p[0]), (q[1], q[0]), (a[1], a[0]), (b[1], b[0]))
        if h is not None:
            return True
    return False


def _side(bar, ll):
    (a0, a1), (b0, b1) = bar["latlngs"]
    return (b0 - a0) * (ll[1] - a1) - (b1 - a1) * (ll[0] - a0) > 0


def test_sewer_zoning_and_design_do_not_cross_a_barrier(server):  # noqa: F811
    with open(SAMPLE, encoding="utf-8") as fh:
        kml = fh.read()
    lay = call(server + "/api/layout", {"name": "sb", "kml": kml})
    assert lay["ok"]
    lats = sorted(m["latlng"][0] for m in lay["manholes"])
    lngs = sorted({m["latlng"][1] for m in lay["manholes"]})
    mid = (lngs[len(lngs) // 2] + lngs[len(lngs) // 2 + 1]) / 2           # between two manholes (none on the line)
    bar = {"name": "NH-19", "type": "highway", "latlngs": [[lats[0] - 0.01, mid], [lats[-1] + 0.01, mid]]}
    req = {"name": "sb", "stp": "MH-17", "sewage_lpcd": 108, "start_depth": 0.7, "barriers": [bar]}
    z = call(server + "/api/zoning", req)
    assert z["ok"], z["log"]
    assert z["cuts"] and z["cut_parts"] and "barrier lines: NH-19 (Highway)" in z["log"]
    assert all(not _crosses(c["pts"], bar) for c in z["cut_parts"])
    # a gap in the drawing (user 30-Oct-2026): two manholes 40 m apart along the top road, joined only through the
    # other side of the line - now two pieces on one side; none across the line (cut there on purpose)
    assert [({g["a"], g["b"]}, g["dist_m"]) for g in z["near_gaps"]] == [({"MH-108", "MH-130"}, 40.03)]
    assert len({_side(bar, p) for p in z["near_gaps"][0]["latlngs"]}) == 1 and "1 gap(s) of 50 m" in z["log"]
    opt = z["options"][0]
    d = call(server + "/api/design", dict(req, option=opt["option"]))
    assert d["ok"], d["log"]
    assert d["cuts"] and all(not _crosses(w["pts"], bar) for w in d["sewers"])
    assert not {c["pipe"] for c in d["cuts"]} & {w["label"] for w in d["sewers"]}
    # both sides drain: an outlet on each side of the line
    xy = {m["label"]: m["latlng"] for m in d["manholes"]}               # (with the new ones at the cuts)
    outs = [x["latlng"] for x in opt["outlets"] if x["latlng"]]
    assert {_side(bar, p) for p in outs} == {True, False}, outs
    assert {_side(bar, xy[o]) for o in d["summary"]["outfalls"]} == {True, False}
    # the barrier lines are kept with the zoning; without them the zoning is another (not the cached one)
    assert not call(server + "/api/zoning", dict(req, barriers=[]))["cached"]
    r = call(server + "/api/zoning_export", {"name": "sb", "option": opt["option"]})
    assert r["ok"], r.get("log")


def test_sewer_dxf_project_keeps_its_barrier_lines(server, tmp_path):  # noqa: F811
    b = [{"latlngs": [[25.3, 83.0], [25.31, 83.0]], "props": {"name": "Rail", "type": "railway"}}]
    assert call(server + "/api/barriers_save", {"name": "dx", "barriers": b})["ok"]
    assert call(server + "/api/barriers?name=dx")["barriers"] == b
    assert os.path.isfile(tmp_path / "projects" / "dx.barriers.json")


def test_sewer_zone_loop_has_its_own_outlet(server):  # noqa: F811
    """A zone loop (user 27-Oct-2026): the manholes inside drain to the lowest of them; no sewer crosses the loop."""
    with open(SAMPLE, encoding="utf-8") as fh:
        kml = fh.read()
    lay = call(server + "/api/layout", {"name": "sl", "kml": kml})
    lats = sorted({m["latlng"][0] for m in lay["manholes"]})
    lngs = sorted({m["latlng"][1] for m in lay["manholes"]})
    mid = (lngs[len(lngs) // 3] + lngs[len(lngs) // 3 + 1]) / 2
    ring = [[lats[0] - 0.001, lngs[0] - 0.001], [lats[-1] + 0.001, lngs[0] - 0.001], [lats[-1] + 0.001, mid],
            [lats[0] - 0.001, mid]]
    req = {"name": "sl", "stp": "MH-17", "sewage_lpcd": 108, "start_depth": 0.7,
           "loops": [{"name": "Ward A", "latlngs": ring}]}
    z = call(server + "/api/zoning", req)
    assert z["ok"], z["log"]
    lp = z["zone_loops"][0]
    assert lp["name"] == "Ward A" and lp["manholes"] > 0 and lp["outlet"] and "zone loop Ward A" in z["log"]
    assert z["near_gaps"] == [] and "gap(s)" not in z["log"]      # cut at the loop on purpose: no gap to join
    cur = next(o for o in z["options"] if o["option"] == "CURRENT")
    assert lp["outlet"] in {x["manhole"] for x in cur["outlets"]}
    edge = {"name": "edge", "latlngs": [[lats[0] - 0.001, mid], [lats[-1] + 0.001, mid]]}
    d = call(server + "/api/design", dict(req, option="CURRENT"))
    assert d["ok"], d["log"]
    assert all(not _crosses(w["pts"], edge) for w in d["sewers"])
    assert lp["outlet"] in d["summary"]["outfalls"]
    assert call(server + "/api/loops_save", {"name": "dx", "loops": [{"latlngs": ring, "props": {"name": "A"}}]})["ok"]
    assert call(server + "/api/loops?name=dx")["loops"][0]["props"]["name"] == "A"


def test_sewer_crossing_lets_a_sewer_through(server):  # noqa: F811
    """A crossing line (user 27-Oct-2026): the sewer crossing the barrier there is not cut."""
    with open(SAMPLE, encoding="utf-8") as fh:
        kml = fh.read()
    lay = call(server + "/api/layout", {"name": "sx", "kml": kml})
    lats = sorted({m["latlng"][0] for m in lay["manholes"]})
    lngs = sorted({m["latlng"][1] for m in lay["manholes"]})
    mid = (lngs[len(lngs) // 2] + lngs[len(lngs) // 2 + 1]) / 2
    bar = {"name": "NH-19", "type": "highway", "latlngs": [[lats[0] - 0.01, mid], [lats[-1] + 0.01, mid]]}
    req = {"name": "sx", "stp": "MH-17", "sewage_lpcd": 108, "start_depth": 0.7, "barriers": [bar]}
    z0 = call(server + "/api/zoning", req)
    c = z0["cuts"][0]
    xing = {"name": "Culvert", "latlngs": [[c["latlng"][0], mid - 0.0002], [c["latlng"][0], mid + 0.0002]]}
    z = call(server + "/api/zoning", dict(req, crossings=[xing]))
    assert z["ok"], z["log"]
    assert c["pipe"] not in {x["pipe"] for x in z["cuts"]} and z["crossings"][0]["existing"] == [c["pipe"]]
    assert "crossings: Culvert (NH-19)" in z["log"]
    assert call(server + "/api/crossings_save", {"name": "dx", "crossings": [{"latlngs": xing["latlngs"], "props": {}}]})["ok"]
    assert call(server + "/api/crossings?name=dx")["crossings"][0]["props"] == {}


def test_why_each_sewer_zone(server):  # noqa: F811
    """The reason of each zone (user request 30-Oct-2026, as the water module's): the STP's by gravity, a part cut off
    by a barrier line without an outfall, a zone loop's own outlet."""
    with open(SAMPLE, encoding="utf-8") as fh:
        kml = fh.read()
    lay = call(server + "/api/layout", {"name": "sw", "kml": kml})
    lats = sorted({m["latlng"][0] for m in lay["manholes"]})
    lngs = sorted({m["latlng"][1] for m in lay["manholes"]})
    mid = (lngs[len(lngs) // 2] + lngs[len(lngs) // 2 + 1]) / 2
    bar = {"name": "NH-19", "type": "highway", "latlngs": [[lats[0] - 0.01, mid], [lats[-1] + 0.01, mid]]}
    z = call(server + "/api/zoning", {"name": "sw", "stp": "MH-17", "sewage_lpcd": 108, "start_depth": 0.7,
                                      "barriers": [bar]})
    assert z["ok"], z["log"]
    cur = next(o for o in z["options"] if o["option"] == "CURRENT")
    r = {x["manhole"]: x["reason"] for x in cur["outlets"]}
    assert r["MH-17"]["kind"] == "stp"
    other = [v for k, v in r.items() if k != "MH-17"]
    assert other and all(v["kind"] == "part" and v["barriers"] == ["NH-19"] and not v["isolated"] for v in other)
    assert all(isinstance(v["max_depth"], (int, float)) for v in r.values())
