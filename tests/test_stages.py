"""Stage-wise check from the page (CPHEEO sewer Table 2.1 p2-9, water Table 2.7 S.No.1 p168): the population of the
base year and of +15 years, the design population = +30 years. Sewer: flows at every outfall per stage, velocity at
the base-year peak (Table 3.9 p3-26: 0.6 m/s); water: the designed network run again at each stage's demand."""
import json
import os
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import openpyxl
import pytest

from sewer_app import ui
from water_app import server as wserver

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE = os.path.join(HERE, "samples", "sample_area.kml")


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setattr(ui, "PROJECTS", str(tmp_path / "projects"))
    monkeypatch.setattr(ui, "OUT_ROOT", str(tmp_path / "output"))
    srv = ThreadingHTTPServer(("127.0.0.1", 0), ui.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def call(url, body=None):
    req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())


def kml():
    with open(SAMPLE, encoding="utf-8") as fh:
        return fh.read()


def test_sewer_stages(server):
    """Population of the stages (user decision 22-Oct-2026): the base-year population - the wards' when none is given -
    and the census give the +15 / +30 years population with the floating population (population.forecast); the design
    is on +30 years, the base year and +15 years are checked (CPHEEO Table 2.1 p2-9)."""
    from sewer_app import population
    assert call(server + "/api/layout", {"name": "s", "kml": kml()})["ok"]
    cat = call(server + "/api/catalogs")["catalogs"][0]["name"]
    req = {"name": "s", "stp": "MH-17", "catalog": cat, "joint": "ss", "sewage_lpcd": 108, "start_depth": 0.7}
    z = call(server + "/api/zoning", req)
    assert z["ok"], z["log"]
    opt = z["options"][0]["option"]
    plain = call(server + "/api/design", dict(req, option=opt))
    f0 = population.forecast(2027, 9000, None, sewage_lpcd=108)                  # the wards: 9000 in the base year
    assert plain["ok"] and [x["pop"] for x in plain["stages"]] == [f0["design"][t] for t in ("init", "mid", "ult")]
    assert "geometrical" in plain["forecast"]

    census = "1991 2600, 2001 3300, 2011 4000"
    st_req = dict(req, option=opt, base_year=2027, pop_initial=4500, census=census, pop_method="geometrical")
    d = call(server + "/api/design", st_req)
    assert d["ok"], d["log"]
    st = d["stages"]
    f = population.forecast(2027, 4500, census, sewage_lpcd=108)
    assert [(x["stage"], x["year"], x["pop"]) for x in st] == [("init", 2027, f["design"]["init"]),
                                                                ("mid", 2042, f["design"]["mid"]),
                                                                ("ult", 2057, f["design"]["ult"])]
    for x in st:
        assert abs(sum(o["pop"] for o in x["outfalls"]) - x["pop"]) <= 2
        assert abs(sum(o["avg_mld"] for o in x["outfalls"]) - x["pop"] * 108 / 1e6) < 0.002
        assert any(o["role"].startswith("STP") for o in x["outfalls"])
    assert st[0]["v_limit"] == 0.6 and st[2]["v_limit"] == 0.8
    for a, b in zip(st, st[1:]):                                     # more people: more flow at every outfall
        assert all(oa["peak_lps"] < ob["peak_lps"] for oa, ob in zip(a["outfalls"], b["outfalls"]))
    # each sewer: lower flow at the base year -> lower velocity (d/D <= 0.8); the pipe table's check counts as the stage
    for w in d["sewers"]:
        if w["q"]:
            assert w["v_init"] <= w["v_mid"] + 1e-9 <= w["v"] + 2e-9
    slow = [w for w in d["sewers"] if "v (base year) < 0.6 m/s" in w["checks"]]
    assert len(slow) == st[0]["slow_n"] > 0
    assert abs(sum(w["length"] for w in slow) - st[0]["slow_m"]) < 0.5
    wb = openpyxl.load_workbook(d["files"]["report"], read_only=True)
    assert "Stages" in wb.sheetnames
    last = call(server + "/api/last_results?name=s")
    assert last["design"]["req"]["pop_initial"] == 4500 and last["design"]["req"]["census"] == census
    assert last["design"]["stages"][1]["year"] == 2042

    bad = call(server + "/api/design", dict(st_req, census="2001 6000, 2011 5000"))   # a falling town: +15 < base
    assert bad["ok"] and any("LESS than" in w for w in bad["warnings"])
    assert not call(server + "/api/design", dict(st_req, base_year=27))["ok"]
    assert not call(server + "/api/design", dict(st_req, pop_initial=-5))["ok"]
    assert not call(server + "/api/design", dict(st_req, census="2001 6000, 2011"))["ok"]


def test_pumps_on_the_mid_flow(server):
    """Zoning cost (user decision 21-Oct-2026, CPHEEO Table 2.1 p2-9: pumping machinery 15 years, civil works 30
    years): the pumps, E&M and energy of every pumping station are on the +15 years flow of the forecast; the civil
    works on the design flow."""
    assert call(server + "/api/layout", {"name": "p", "kml": kml()})["ok"]
    cat = call(server + "/api/catalogs")["catalogs"][0]["name"]
    req = {"name": "p", "catalog": cat, "joint": "ss", "sewage_lpcd": 108, "start_depth": 0.7, "max_depth": 3}
    b = call(server + "/api/zoning", req)
    assert b["ok"] and b["inputs"]["pop_mid"] < b["inputs"]["pop_total"]
    assert any(o["pumping"] for o in b["options"])
    wb = openpyxl.load_workbook(b["files"]["costs"], read_only=True)
    rows = list(wb["Pumping stations"].iter_rows(values_only=True))
    k, q, basis = rows[0].index("pumps sized on (L/s)"), rows[0].index("peak flow (L/s)"), rows[0].index("pumps basis")
    assert rows[1:] and all(r[k] < r[q] and r[basis].startswith("+15 years") for r in rows[1:])


@pytest.fixture
def wsrv(tmp_path, monkeypatch):
    """The water module's own server, in tmp folders."""
    monkeypatch.setattr(wserver, "PROJECTS", str(tmp_path / "w_projects"))
    monkeypatch.setattr(wserver, "OUT_ROOT", str(tmp_path / "w_output"))
    srv = ThreadingHTTPServer(("127.0.0.1", 0), wserver.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def test_water_stages(wsrv):
    server = wsrv
    r = call(server + "/api/w/layout", {"name": "w", "kml": kml(), "gl_mode": "spots", "snap": 1, "spacing": 100})
    assert r["ok"], r["log"]
    m = max(r["manholes"], key=lambda x: x["gl"] or 0)
    oht = {"name": "OHT-1", "lat": m["latlng"][0], "lng": m["latlng"][1], "capacity_kl": "", "staging_m": 22}
    req = {"name": "w", "ohts": [oht], "pop_factor": 1.5}
    assert call(server + "/api/w/water_zoning", req)["ok"]
    d = call(server + "/api/w/water_design", dict(req, base_year="2027", pop_initial=9000, pop_mid=11000))
    assert d["ok"], d.get("log")
    st = d["stages"]
    assert [(x["year"], x["pop"]) for x in st] == [(2027, 9000), (2042, 11000), (2057, 13500)]
    ult = st[2]
    assert abs(ult["min_p"] - d["summary"]["min_pressure"]) < 0.01            # the design itself
    assert abs(ult["avg_lps"] - d["summary"]["demand_avg_lps"]) < 0.01
    # less demand: less head loss - the residual head rises, the outlet flow and the velocities fall
    assert st[0]["min_p"] >= st[1]["min_p"] >= st[2]["min_p"]
    assert st[0]["oz"][0]["flow_lps"] < st[1]["oz"][0]["flow_lps"] < st[2]["oz"][0]["flow_lps"]
    assert st[0]["slow_n"] >= st[2]["slow_n"]
    assert all(p["v_init"] <= p["v"] + 1e-6 for p in d["pipes"] if "v_init" in p)
    wb = openpyxl.load_workbook(d["files"]["excel"], read_only=True)
    assert "Stages" in wb.sheetnames
    last = call(server + "/api/w/water_last?name=w")
    assert last["design"]["req"]["pop_mid"] == 11000 and len(last["design"]["stages"]) == 3
    plain = call(server + "/api/w/water_design", req)
    assert plain["ok"] and plain["stages"] == []
