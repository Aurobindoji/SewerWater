"""Water phase 2 (user decisions 31-Oct-2026): the new tube wells and their rising mains - each its own main along the
roads to its OHT; suggested sites near the OHT, 100 m apart; the economical size (CPHEEO 6.7, Annexure 6.1); the surge
of a pump stop (CPHEEO 6.16.4); the T3 friction, the DPR sheets T7 / D5 and the repairs of the existing OHTs."""
import json
import math
import os

import openpyxl
import pytest

from test_dxf_extract import make_dxf
from test_water_ui import call, server  # noqa: F401  (the fixture)
from water_app import design as wd
from water_app import dpr as wdpr
from water_app import dpr_rm
from water_app import netedit
from water_app import rising

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(HERE, "water_app", "criteria.json"), encoding="utf-8") as fh:
    CRIT = json.load(fh)
SIZES = wd.load_pipes()


def test_friction_and_celerity_by_hand():
    # Hazen-Williams: 25 L/s through 1 km of 200 mm, C 140
    assert rising.hf(1000, 0.025, 0.2, 140) == pytest.approx(10.67 * 1000 * 0.025 ** 1.852 / (140 ** 1.852 * 0.2 ** 4.87))
    hd = next(s for s in SIZES if s["name"] == "HDPE 110")
    di = next(s for s in SIZES if s["name"] == "DI 200")
    assert rising.wall_mm(hd) == pytest.approx((110 - 99.3) / 2)
    # IS 8329:2000 clause 4.3, Table 2: K7 e = 7 (0.5 + 0.001 DN), at least 5 mm - DN 200 5.0, DN 300 5.6 (5.25 -> 5.3)
    assert rising.wall_mm(di) == 5.0
    assert rising.wall_mm(next(s for s in SIZES if s["name"] == "DI 300")) == pytest.approx(5.6)
    # c = 1425 / sqrt(1 + k d / (E t)), CPHEEO Eq. 6.16: HDPE ~ 215 m/s, DI ~ 1165 m/s
    c_hd = 1425 / math.sqrt(1 + 2.07e8 * 0.0993 / (9e7 * 0.00535))
    assert rising.celerity(hd, CRIT) == pytest.approx(c_hd) and 200 < c_hd < 230
    assert 1100 < rising.celerity(di, CRIT) < 1200
    # IS 8329 Amendment 1 Annex E, K7 DN 80-750: AOP 0.8 MPa, MOP 1.25 MPa (1 MPa = 101.97 m of water)
    S = CRIT["surge"]["value"]
    assert S["aop_m"]["DI"] == pytest.approx(0.8 * 101.97, abs=0.1) and S["mop_m"]["DI"] == pytest.approx(1.25 * 101.97, abs=0.1)


def test_k9_where_k7_is_exceeded():
    """User decision 31-Oct-2026: a DI rising main whose head / head + surge exceeds K-7's AOP 0.8 / MOP 1.25 MPa is
    laid in K9, with its own wall (IS 8329 Table 2), surge and AOP / MOP (Annex E, Amendment 1)."""
    di = next(s for s in SIZES if s["name"] == "DI 200")
    cls, c, h, aop, mop, ok = rising.pipe_class(di, 20.0, 0.5, CRIT)                  # 20 + ~60 m: within K-7
    assert cls == "K7" and ok and mop == pytest.approx(127.5)
    cls, c, h, aop, mop, ok = rising.pipe_class(di, 40.0, 0.8, CRIT)                  # 40 + ~95 m: above 127.5 m
    assert cls == "K9" and ok
    assert aop == pytest.approx(6.2 * 101.97) and mop == pytest.approx(7.4 * 101.97)
    assert c == pytest.approx(rising.celerity(di, CRIT, 6.3)) and c > rising.celerity(di, CRIT)   # thicker wall
    hd = next(s for s in SIZES if s["name"] == "HDPE 110")
    assert rising.pipe_class(hd, 50.0, 1.5, CRIT)[0] == "PN-6" and not rising.pipe_class(hd, 50.0, 1.5, CRIT)[5]


def test_the_economical_size_is_the_least_total():
    rate = lambda s, c="K7": {"HDPE 110": 400, "HDPE 140": 600, "HDPE 160": 800}.get(s, 2500 + 10 * int(s.split()[1]))
    alts = rising.economic(300.0, 0.025, 35.0, SIZES, rate, CRIT)
    best = [a for a in alts if a["best"]]
    assert len(best) == 1 and best[0]["total"] == min(a["total"] for a in alts)
    assert all(0.3 <= a["v"] <= 3.0 for a in alts)
    # a longer main: friction weighs more, the size does not get smaller
    alts2 = rising.economic(5000.0, 0.025, 35.0, SIZES, rate, CRIT)
    order = [s["name"] for s in SIZES]
    b1, b2 = (next(a["size"] for a in x if a["best"]) for x in (alts, alts2))
    assert order.index(b2) >= order.index(b1)
    # each total: pipe (+ 10 % specials) + pump sets now and again after 15 years + 30 years of energy
    a = alts[0]
    X = CRIT["rising_main_economics"]["value"]
    pw = (1 + X["interest"]) ** -15
    assert a["pipe"] == pytest.approx(300 * rate(a["size"]) * 1.10) and a["cls"] in ("K7", "PN-6")
    assert a["pumps"] == pytest.approx(a["kw"] * 1.5 * X["pump_rs_per_kw"] * (1 + pw)) and X["pump_rs_per_kw"] == 21048   # R3 B30
    assert a["energy"] == pytest.approx(a["kw"] * 16 * 365 * X["energy_rs_per_kwh"] * (1 - pw) / X["interest"] * (1 + pw))


def test_the_economical_size_at_the_k9_rate():
    """A DI size whose head / head + surge exceeds K-7 competes at its K9 rate (it is laid in K9 - user decision
    31-Oct-2026): the economical size counts the pipe it gets, not K-7's."""
    S = wdpr.settings()
    rate = dpr_rm.laid_rate(S)
    k7 = rate("DI 200")
    assert rate("DI 200", "K9") - k7 == pytest.approx(S["pipe_supply_k9"]["DI 200"] - S["pipe_supply"]["DI 200"])
    assert rate("DI 200", "K9") > k7 and rate("HDPE 110", "K9") == rate("HDPE 110")    # no K9 HDPE: its own rate
    alts = rising.economic(2000.0, 0.02, 95.0, SIZES, rate, CRIT)                     # 95 m: above K-7's AOP 81.6 m
    di = [a for a in alts if a["size"].startswith("DI")]
    assert di and all(a["cls"] == "K9" for a in di)
    X = CRIT["rising_main_economics"]["value"]
    for a in di:
        assert a["pipe"] == pytest.approx(2000.0 * rate(a["size"], "K9") * (1 + X["specials"]))
    low = rising.economic(2000.0, 0.02, 30.0, SIZES, rate, CRIT)                      # 30 m: K-7
    assert all(a["cls"] in ("K7", "PN-6") for a in low)


def _line():
    """An OHT at J0, junctions every 60 m along one road J0 - J1 - ... - J6, a branch J2 - K1 (60 m)."""
    nodes = {f"J{i}": {"xy": (60.0 * i, 0.0), "elev": 80.0} for i in range(7)}
    nodes["K1"] = {"xy": (120.0, 60.0), "elev": 80.0}
    pipes = {f"P{i}": {"a": f"J{i}", "b": f"J{i + 1}", "length": 60.0} for i in range(6)}
    pipes["Q1"] = {"a": "J2", "b": "K1", "length": 60.0}
    z = {"oz": {n: "OHT-1" for n in nodes}}
    return {"nodes": nodes, "pipes": pipes}, z


def test_suggested_sites_100_m_apart_and_the_routes():
    wnet, z = _line()
    rate = lambda s, c="K7": 1000.0
    R = rising.plan(wnet, z, [{"name": "OHT-1", "node": "J0"}], [], CRIT, SIZES, rate, {"OHT-1": 110.0},
                    {"OHT-1": 2})
    sites = [(t["node"], t["placed"]) for t in R["tws"]]
    # nearest along the road first, at least 100 m from the OHT and from each other: J2 (120 m), then K1 is 60 m from
    # J2 - too near; J4 (240 m)
    assert sites == [("J2", False), ("J4", False)]
    t1, t2 = R["tws"]
    assert t1["length_m"] == pytest.approx(120.0) and t1["path"] == ["J2", "J1", "J0"]
    assert t2["length_m"] == pytest.approx(240.0)
    assert t1["static_m"] == pytest.approx(110.0 - (80.0 - 6.0))
    assert R["oz"]["OHT-1"]["n"] == 2 and R["oz"]["OHT-1"]["friction_m"] == pytest.approx(max(t1["hf_m"], t2["hf_m"]))
    # DI only (user decision 7-Nov-2026: IS 4984 gives PE no surge allowance; Riverside water DPR p197 all D.I.)
    assert all(a["size"].startswith("DI") for x in (t1, t2) for a in x["alts"]) and t1["cls"] in ("K7", "K9")
    # the surge check: the head against the AOP, the head + surge against the MOP of the class taken
    for t in (t1, t2):
        assert t["surge_ok"] == (t["head_m"] <= t["aop_m"] and t["head_m"] + t["surge_m"] <= t["rating_m"])
        if t["cls"] in ("K7", "PN-6"):
            mat = "HDPE" if t["cls"] == "PN-6" else "DI"
            assert t["aop_m"] == CRIT["surge"]["value"]["aop_m"][mat] and t["rating_m"] == CRIT["surge"]["value"]["mop_m"][mat]
    # a head of 126 m: above K-7's AOP 81.6 m - a DI main goes K9 and passes
    R2 = rising.plan(wnet, z, [{"name": "OHT-1", "node": "J0"}], [], CRIT, SIZES, rate, {"OHT-1": 200.0}, {"OHT-1": 1})
    t = R2["tws"][0]
    assert t["head_m"] > 82 and (t["cls"] == "K9" and t["surge_ok"] if t["size"].startswith("DI") else not t["surge_ok"])
    # one placed near K1: it is used, one more suggested; a third too many: no site left, flagged
    R = rising.plan(wnet, z, [{"name": "OHT-1", "node": "J0"}], [{"name": "TW A", "xy": (121.0, 70.0)}], CRIT, SIZES,
                    rate, {"OHT-1": 110.0}, {"OHT-1": 4})
    assert [(t["name"], t["node"]) for t in R["tws"]][:1] == [("TW A", "K1")]
    # K1 - J2 - J1 - J0 along the roads, + the point's 10 m to K1
    assert R["tws"][0]["length_m"] == pytest.approx(60.0 + 120.0 + math.hypot(1.0, 10.0))
    assert R["flags"] and "found no site" in R["flags"][0]


def test_design_and_dpr_with_a_tube_well(server):  # noqa: F811
    url, tmp = server
    src = str(tmp / "rm.dxf")
    make_dxf(src)
    netedit._UNDO.clear()
    d = call(url + "/api/w/dxf_import", {"path": src, "name": "wrm", "pipe_layers": ["PIPE"], "mh_layers": ["MH"],
                                         "level_layers": ["GL"], "epsg": "local"})
    assert d["ok"]
    a, m5 = d["nodes"]["MH-1"]["latlng"], d["nodes"]["MH-5"]["latlng"]
    req = {"name": "wrm", "pop_factor": 1, "pop_total": 1000, "base_year": 2027, "pop_initial": 600, "pop_mid": 800,
           "ohts": [{"name": "Ex-OHT-1", "lat": a[0], "lng": a[1], "existing": "1", "capacity_kl": 200, "staging_m": 20}],
           "tws": [{"name": "TW 1", "lat": m5[0], "lng": m5[1], "discharge_lpm": "1200"}]}
    assert call(url + "/api/w/tw_save", {"name": "wrm", "tw": [{"latlng": m5, "props": {"name": "TW 1"}}]})["ok"]
    assert call(url + "/api/w/tw?name=wrm")["tw"][0]["props"]["name"] == "TW 1"
    r = call(url + "/api/w/water_design", req)
    assert r["ok"], r.get("log")
    (t,) = [x for x in r["rising"]["tws"] if x["placed"]]
    # MH-5 -> MH-4 -> MH-3 -> MH-2 -> MH-1 along the roads: 30 + 30 + 30 + 30 m
    assert t["oz"] == "Ex-OHT-1" and t["length_m"] == pytest.approx(120.0, abs=0.1) and t["lpm"] == 1200
    assert t["size"] and t["path"][0] == pytest.approx(m5) and t["path"][-1] == pytest.approx(a)
    chk = next(c for c in r["checks"] if c["check"] == "rising mains")
    assert "1 on the map" in chk["detail"] and "नक्शे पर" in chk["detail_hi"]
    wb = openpyxl.load_workbook(r["files"]["dpr"])
    assert {"T15 Rising Main", "D5 Rising Main"} <= set(wb.sheetnames)
    names = wb.sheetnames
    assert names.index("T15 Rising Main") < names.index("D1 Pipe & Road") < names.index("D5 Rising Main") < \
        names.index("S1 OHT Abstract")
    t3 = next(wb[n] for n in names if n.startswith("T14-"))
    fr = next(row for row in t3.iter_rows(values_only=True) if row[1] == "Frictional losses in rising main and pumping plant")
    rm = r["rising"]["oz"]["Ex-OHT-1"]["friction_m"]
    assert fr[5] == math.ceil(rm * 2) / 2 and "sheet T15 Rising Main" in fr[7]               # the note renamed too
    if t["cls"] == "K9":                                                             # its own (yellow) supply rate
        d5 = [row for row in wb["D5 Rising Main"].iter_rows(values_only=True) if row[2] and "DI K-9" in str(row[2])]
        assert d5 and d5[0][8] == json.load(open(os.path.join(HERE, "water_app", "dpr_water.json"), encoding="utf-8"))[
            "pipe_supply_k9"]["value"][t["size"]]
    # the NRV at the tube well: the UPJN rate 2025-26 (M209) of its valve size
    S = json.load(open(os.path.join(HERE, "water_app", "dpr_water.json"), encoding="utf-8"))
    rows = list(wb["D5 Rising Main"].iter_rows(values_only=True))
    i = next(k for k, row in enumerate(rows) if row[2] and "non return valves" in str(row[2]))
    dn = S["valve_of_pipe"]["value"][t["size"]]
    assert rows[i + 1][2] == f"{dn} mm - supply" and rows[i + 1][8] == S["nrv_rate"]["value"][str(dn)]
    abs_ = {row[1]: row for row in wb["ABS Com"].iter_rows(values_only=True) if row[1]}
    assert str(abs_["Rising Main and appurtenant works"][3]).startswith("='D5 Rising Main'!")
    assert abs_["Rising Main and appurtenant works"][2].startswith("=ROUND('D5 Rising Main'!$E$")
    assert str(abs_["Repairing of existing RCC overhead tanks"][3]).startswith("='S1 OHT Abstract'!")
    # repairs of the existing OHT: the detailed estimate of the Riverside water DPR (user decision 6-Nov-2026)
    ws = wb["S1 OHT Abstract"]
    rep = next(row for row in ws.iter_rows(values_only=True) if row[1] == "For operation zone Ex-OHT-1")
    assert rep[3] == "200 KL / 20 M" and rep[4].startswith("='S4-01 Rep Ex-OHT-1'!$K$")
    # the Riverside DPR's rising mains (p205-209): a 10 m bye pass at the OHT, a masonry chamber for the sluice valve
    i = next(k for k, row in enumerate(rows) if row[2] and str(row[2]).startswith("Supply of the following pipes"))
    assert rows[i + 1][7].endswith("+10*D6")
    ch = next(row for row in rows if row[2] and "Sluice valve chamber (masonry type)" in str(row[2]))
    assert ch[7].startswith("=D") and ch[8] == "='U02 SV M'!K17"


def test_a_cwr_zone_s_tube_wells_fill_the_cwr(server):  # noqa: F811
    """More than 3 new tube wells for one OHT: a CWR (UPJN rule) - its tube wells fill the CWR, a ground reservoir at
    the OHT (lifting to the ground level, as the Riverside water DPR), its own pumps the OHT (R3 'H P Calculation pp':
    the tube wells of its CWR zones 37 m, of the others 64-72 m); the other OZ's tube wells still to its OHT's top."""
    url, tmp = server
    src = str(tmp / "cwr.dxf")
    make_dxf(src)
    netedit._UNDO.clear()
    d = call(url + "/api/w/dxf_import", {"path": src, "name": "wcwr", "pipe_layers": ["PIPE"], "mh_layers": ["MH"],
                                         "level_layers": ["GL"], "epsg": "local"})
    a, m2, m5 = (d["nodes"][k]["latlng"] for k in ("MH-1", "MH-2", "MH-5"))
    req = {"name": "wcwr", "pop_factor": 1, "pop_total": 60000, "base_year": 2027, "pop_initial": 40000,
           "pop_mid": 50000, "ohts": [{"name": "OHT-1", "lat": a[0], "lng": a[1], "staging_m": 20}],
           "tws": [{"name": "TW 2", "lat": m2[0], "lng": m2[1]}, {"name": "TW 5", "lat": m5[0], "lng": m5[1]}]}
    r = call(url + "/api/w/water_design", req)
    assert r["ok"], r.get("log")
    R = r["rising"]
    assert "OHT-1" in R["cwr"]
    # the tube wells lift to the ground level at the CWR (MH-1's GL), not to the staging 20 m (Riverside water DPR
    # p136-195: TW to CWR staging 0, depth of water 0 - user decision 6-Nov-2026)
    assert R["top"]["OHT-1"] == pytest.approx(85.50, abs=0.01)
    gl = {"TW 2": 85.20, "TW 5": 84.60}
    tws = {x["name"]: x for x in R["tws"] if x["placed"]}
    assert set(tws) == set(gl) and {t["oz"] for t in tws.values()} == {"OHT-1", "Prop-OHT-1"}
    for n, t in tws.items():                  # water 15 m below GL + seasonal 5 + depression 4.5 (DPR, 6-Nov-2026)
        assert t["static_m"] == pytest.approx(R["top"][t["oz"]] - (gl[n] - 24.5), abs=0.01)
        assert t["gl"] == gl[n]
    assert R["gl"]["OHT-1"] == pytest.approx(85.50, abs=0.01)                 # each OHT's ground (DPR T12)
    # an OZ without a CWR: its tube wells to its OHT's top water level (staging + side water depth + the cone of a
    # new Intze OHT, user decision 10-Nov-2026)
    assert "Prop-OHT-1" not in R["cwr"]
    o = next(x for x in r["outlets"] if x["name"] == "Prop-OHT-1")
    from water_app import intze
    cone = intze.cone_depth(o["required_kl"], 3 if o["required_kl"] <= 100 else 4 if o["required_kl"] <= 1000 else 5)
    assert cone > 0.5
    assert 84.60 + 3 + cone <= R["top"]["Prop-OHT-1"] - o["staging_m"] <= 85.70 + 5 + cone   # GL 84.60-85.70
    chk = next(c for c in r["checks"] if c["check"] == "rising mains")
    assert "OHT-1 (a CWR) to the CWR" in chk["detail"] and "(CWR) CWR तक" in chk["detail_hi"]
