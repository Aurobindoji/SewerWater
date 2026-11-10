"""Pressure reducing valves of the water design (user request 30-Oct-2026: no pipe size lowers the 37.7 m of a low
pocket of network_utm - its pipes are the minimum and carry a few L/s). A PRV on a pipe the area beyond is reached
through only (a bridge) holds its downstream head: the whole area lower by the same amount, the solution exact (its
flows are its own demand), the rest of the network unchanged; in a loop it does nothing. Setting by itself: the lowest
keeping 17 m beyond it, up to 0.5 m; suggestions where junctions are above 31 m (5 at least for one PRV)."""
import openpyxl
import pytest

from test_dxf_extract import make_dxf
from test_water_ui import call, server  # noqa: F401  (the fixture)
from water_app import hydraulics as hy
from water_app import netedit
from water_app import prv

CRIT = {"residual_head_m": {"value": 17.0}, "residual_head_max_m": {"value": 21.0}}


def _net():
    """T (head 120) - A - B ... a ridge at A, a valley beyond B: B - C - D (a branch, reached through B-C only) and a
    loop A - E - F - A."""
    el = {"A": 95.0, "B": 90.0, "C": 70.0, "D": 68.0, "E": 94.0, "F": 94.0}
    nodes = {"T": {"elev": 100.0, "head": 120.0}}
    nodes.update({n: {"elev": e, "demand": 1.0} for n, e in el.items()})
    pipes = {"P0": ("T", "A"), "P1": ("A", "B"), "P2": ("B", "C"), "P3": ("C", "D"), "P4": ("A", "E"), "P5": ("E", "F"),
             "P6": ("F", "A")}
    net = {"nodes": nodes, "pipes": {k: {"a": a, "b": b, "length": 200.0, "d_mm": 100.0, "C": 140} for k, (a, b) in pipes.items()}}
    return net, hy.solve(net)


def test_a_prv_on_a_bridge_lowers_its_area_alike():
    net, r = _net()
    before = {n: r["pressure"][n] for n in "ABCDEF"}
    tree = prv.Tree(net)
    assert set(tree.bridge) == {"P0", "P1", "P2", "P3"}                            # not the loop's pipes
    (row,) = prv.apply(net, r, [({"name": "V1", "setting_m": ""}, "P2", 0.0)], CRIT, tree)
    assert row["active"] and row["down"] == "C" and row["nodes"] == 2 and row["auto"]
    # by itself: the weakest junction beyond it at 17 m (C: D lies 2 m lower), the setting up to 0.5 m
    cut = before["C"] - row["setting_m"]
    assert row["setting_m"] == pytest.approx(round((before["C"] - (min(before["C"], before["D"]) - 17)) * 2 + 0.49999) / 2)
    assert r["pressure"]["C"] == pytest.approx(row["setting_m"]) and r["pressure"]["D"] == pytest.approx(before["D"] - cut)
    assert 17.0 <= min(r["pressure"]["C"], r["pressure"]["D"]) < 17.5
    assert all(r["pressure"][n] == pytest.approx(before[n]) for n in "ABEF")       # the rest as it was
    assert row["max_before"] == pytest.approx(round(max(before["C"], before["D"]), 2))


def test_a_prv_in_a_loop_or_off_the_pipes_does_nothing():
    net, r = _net()
    before = dict(r["pressure"])
    rows = prv.apply(net, r, [({"name": "L"}, "P5", 0.0), ({"name": "X"}, None, 120.0)], CRIT)
    assert not any(x["active"] for x in rows)
    assert "loop" in rows[0]["note"] and rows[1]["note"].startswith("no pipe within 30 m")
    assert r["pressure"] == before
    net["pipes"]["P2"]["closed"] = True
    r = hy.solve(net)
    (row,) = prv.apply(net, r, [({"name": "Z"}, "P2", 0.0)], CRIT)
    assert not row["active"] and "closed" in row["note"]


def test_a_setting_given_and_the_stages():
    net, r = _net()
    (row,) = prv.apply(net, r, [({"name": "V", "setting_m": "5"}, "P2", 0.0)], CRIT)
    assert row["active"] and not row["auto"] and r["pressure"]["C"] == pytest.approx(5.0) and row["low"] == 2
    # a lower demand (a stage): the PRV holds the same head at C, so C keeps its 5 m
    for v in net["nodes"].values():
        if "demand" in v:
            v["demand"] = 0.4
    r2 = hy.solve(net)
    prv.shift(r2, [row])
    assert r2["pressure"]["C"] == pytest.approx(5.0)
    # a setting above what reaches it: inactive
    net, r = _net()
    (row,) = prv.apply(net, r, [({"name": "V", "setting_m": "60"}, "P2", 0.0)], CRIT)
    assert not row["active"] and row["note"].startswith("inactive")


def test_suggestions_where_above_31_m():
    net, r = _net()
    assert r["pressure"]["C"] > 31 and r["pressure"]["D"] > 31
    out, left = prv.suggest(net, r, CRIT, min_gain=2)
    assert [(g["pipe"], g["high_before"], g["high_after"]) for g in out] == [("P2", 2, 0)] and left == 0
    out, left = prv.suggest(net, r, CRIT)                                            # 5 at least: none here
    assert out == [] and left == 2
    # P2 taken: P1 brings neither down (B, on ground 20 m higher, limits its cut); P3 brings D down, C stays above
    out, left = prv.suggest(net, r, CRIT, taken={"P2"}, min_gain=1)
    assert [g["pipe"] for g in out] == ["P3"] and left == 1
    assert r["pressure"]["C"] > 31                                                  # suggest() changes nothing


def test_design_with_a_prv_on_the_map(server):  # noqa: F811
    url, tmp = server
    src = str(tmp / "prv.dxf")
    make_dxf(src)                                    # MH-1 - MH-2 - MH-6, MH-2 - MH-3 - MH-4 - MH-5 (a branch)
    netedit._UNDO.clear()
    d = call(url + "/api/w/dxf_import", {"path": src, "name": "wprv", "pipe_layers": ["PIPE"], "mh_layers": ["MH"],
                                         "level_layers": ["GL"], "epsg": "local"})
    assert d["ok"]
    a = d["nodes"]["MH-1"]["latlng"]
    m3, m4 = d["nodes"]["MH-3"]["latlng"], d["nodes"]["MH-4"]["latlng"]
    at = [(m3[0] + m4[0]) / 2, (m3[1] + m4[1]) / 2]                                    # on the pipe MH-3 - MH-4
    req = {"name": "wprv", "pop_factor": 1, "pop_total": 1000,
           "ohts": [{"name": "Ex-OHT-1", "lat": a[0], "lng": a[1], "existing": "1", "capacity_kl": 200, "staging_m": 25}],
           "prvs": [{"name": "PRV 1", "lat": at[0], "lng": at[1], "setting_m": "12"},
                    {"name": "PRV 2", "lat": a[0] + 0.01, "lng": a[1], "setting_m": ""}]}      # ~1 km off: no pipe
    assert call(url + "/api/w/prv_save", {"name": "wprv", "prv": [{"latlng": at, "props": {"name": "PRV 1"}}]})["ok"]
    assert call(url + "/api/w/prv?name=wprv")["prv"][0]["props"]["name"] == "PRV 1"
    # the PRV option of the page off (the default, user 31-Oct-2026): the PRVs on the map are not used, none suggested
    r = call(url + "/api/w/water_design", req)
    assert r["ok"] and r["prvs"] == [] and r["prv_suggest"] == [] and r["prv_option"] is False
    off = next(c for c in r["checks"] if c["check"] == "PRV")
    assert off["ok"] and "2 PRVs on the map not used" in off["detail"] and "विकल्प बंद" in off["detail_hi"]
    ws = openpyxl.load_workbook(r["files"]["dpr"])["D2 DS Estimate"]
    assert not any(row[2] and "Pressure reducing valves" in str(row[2]) for row in ws.iter_rows(values_only=True))
    req["use_prv"] = "1"
    r = call(url + "/api/w/water_design", req)
    assert r["ok"], r.get("log")
    p1, p2 = r["prvs"]
    assert p1["active"] and p1["setting_m"] == 12 and p1["size"] and p1["down"] == "MH-4" and p1["nodes"] == 2
    assert not p2["active"] and p2["pipe"] is None
    by = {n["label"]: n for n in r["nodes"]}
    assert by["MH-4"]["p"] == pytest.approx(12.0, abs=0.01) and by["MH-5"]["p"] < 17       # 12 m given: below 17
    c1 = next(c for c in r["checks"] if c["check"] == "PRV PRV 1")
    c2 = next(c for c in r["checks"] if c["check"] == "PRV PRV 2")
    assert not c1["ok"] and "below 17 m" in c1["detail"] and "17 m से कम" in c1["detail_hi"]
    assert not c2["ok"] and "कोई pipe नहीं" in c2["detail_hi"]
    assert not next(c for c in r["checks"] if c["check"].startswith("residual head >="))["ok"]
    # the DPR: the PRV at a yellow quotation rate in D2
    ws = openpyxl.load_workbook(r["files"]["dpr"])["D2 DS Estimate"]
    rows = [[c.value for c in row] for row in ws.iter_rows(min_row=6, max_col=12)]
    t = next(i for i, x in enumerate(rows) if x[2] and "Pressure reducing valves (PRV)" in str(x[2]))
    prv_, sv_, fix_, ch_ = rows[t + 1: t + 5]
    # the PRV itself at the yellow quotation rate; two isolating sluice valves (UPJN M208 via SV Rate) and a chamber
    assert "PRV 1 on" in prv_[2] and prv_[7] == 1 and prv_[8] == 100000 and prv_[9] == "Nos"
    assert "isolate" in sv_[2] and sv_[7] == 2 and sv_[8] == "='U01 SV Rate'!C6"
    assert "fixing" in fix_[2] and fix_[7] == 2 and fix_[8] == "='U01 SV Rate'!E6"
    assert "Chamber" in ch_[2] and ch_[7] == 1 and ch_[8] == "='U02 SV M'!K17"
