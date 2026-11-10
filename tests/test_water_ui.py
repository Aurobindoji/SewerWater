"""Water module on its own server (water_app.server, isolation of sewer and water 21-Oct-2026): /water is its map
page; /api/w/... (as the page calls) works in water_app's own folders (a sewer project and a water project do not see
each other); layout without bend nodes, zoning (OZ / DMA), design and the
results kept for the next opening."""
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
    """The water module's own server (isolation of sewer and water, 21-Oct-2026), in tmp folders."""
    monkeypatch.setattr(wserver, "PROJECTS", str(tmp_path / "w_projects"))
    monkeypatch.setattr(wserver, "OUT_ROOT", str(tmp_path / "w_output"))
    srv = ThreadingHTTPServer(("127.0.0.1", 0), wserver.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", tmp_path
    srv.shutdown()
    srv.server_close()


@pytest.fixture
def sewer(tmp_path, monkeypatch):
    """The sewer server, in its own tmp folders: it does not see the water projects."""
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
        data = r.read()
    return json.loads(data) if r.headers.get_content_type() == "application/json" else data.decode("utf-8")


def test_water_layout_zoning_design(server, sewer):
    url, tmp = server
    assert "leaflet@1.9.4" in call(url + "/water")                         # the map page in water mode
    with open(SAMPLE, encoding="utf-8") as fh:
        kml = fh.read()
    r = call(url + "/api/w/layout", {"name": "wtest", "kml": kml, "gl_mode": "spots", "snap": 1, "spacing": 100})
    assert r["ok"], r["log"]
    assert os.path.isfile(tmp / "w_projects" / "wtest.kml") and not os.path.exists(tmp / "projects" / "wtest.kml")
    assert [p["name"] for p in call(url + "/api/w/projects")["projects"]] == ["wtest"]
    assert call(sewer + "/api/projects")["projects"] == []                  # the sewer side does not see it
    assert all(len(c["pts"]) >= 2 for c in r["conduits"])
    # water nodes only along the roads (<= 100 m apart), far fewer than the sewer's manholes at 30 m and every bend
    assert len(r["manholes"]) < 200
    assert all(m["label"].startswith("J-") for m in r["manholes"]) and all(c["label"].startswith("P-") for c in r["conduits"])
    # spacing 0: junctions only where roads meet and at their ends - no node in the middle of a pipe
    r0 = call(url + "/api/w/layout", {"name": "wtest0", "kml": kml, "gl_mode": "spots", "snap": 1, "spacing": 0})
    assert r0["ok"] and len(r0["manholes"]) < len(r["manholes"])
    deg = {}
    for c in r0["conduits"]:
        for n in (c["from"], c["to"]):
            deg[n] = deg.get(n, 0) + 1
    assert sum(1 for v in deg.values() if v == 2) <= 2            # (two roads drawn end to end only)
    m = max(r["manholes"], key=lambda x: x["gl"] or 0)                     # the OHT on the highest ground
    oht = {"name": "OHT-1", "lat": m["latlng"][0], "lng": m["latlng"][1], "capacity_kl": "", "staging_m": 22,
           "tubewells": 4}
    z = call(url + "/api/w/water_zoning", {"name": "wtest", "ohts": [oht], "pop_factor": 1.5})
    assert z["ok"], z.get("log")
    oz = z["zones"][0]
    assert oz["name"] == "OHT-1" and oz["population"] == round(9000 * 1.5)
    # 4 existing tube wells, none new: no CWR (only the new ones count - user decision 27-Oct-2026)
    assert oz["required_kl"] >= 0.33 * oz["demand_kld"] and oz["tubewells_new"] == 0 and oz["cwr_kl"] is None
    assert oz["rings"] and z["dmas"]
    assert z["storage"]["share"] == 0.33 and z["storage"]["hours"] == 16                # Elmwood 5-12, 13-22
    # filled 8 h only: mass balance 38.5 % > 33 % (CPHEEO Table 2.7 S.No.12 p175, the larger)
    z8 = call(url + "/api/w/water_zoning", {"name": "wtest", "ohts": [oht], "pop_factor": 1.5, "oht_inflow": "4-8, 16-20"})
    s8 = z8["storage"]["share"]
    a8 = z8["zones"][0]                     # + a third of the fire demand (CPHEEO S.No.13, user decision 30-Oct-2026)
    assert round(s8, 3) == 0.385 and a8["required_kl"] >= s8 * (a8["demand_kld"] - a8["fire_kld"]) + a8["fire_kld"] / 3 - 0.1
    assert z8["storage"]["fire_share"] == pytest.approx(1 / 3, abs=1e-3)
    assert z8["zones"][0]["required_kl"] > oz["required_kl"]
    d = call(url + "/api/w/water_design", {"name": "wtest", "ohts": [oht], "pop_factor": 1.5})
    assert d["ok"], d.get("log")
    assert d["summary"]["min_pressure"] >= 17.0 - 1e-6
    assert all(c["ok"] for c in d["checks"])
    assert all(c["check_hi"] and c["detail_hi"] for c in d["checks"])           # their Hindi for the page
    assert all(p["size"] for p in d["pipes"]) and d["outlets"][0]["flow"] > 0
    assert os.path.isfile(d["files"]["excel"])
    last = call(url + "/api/w/water_last?name=wtest")
    assert last["zoning"]["zones"][0]["name"] == "OHT-1" and last["design"]["summary"]["min_pressure"] >= 17 - 1e-6
    # an OHT without staging: the design finds it (0.5 m steps, just enough for 17 m)
    auto = call(url + "/api/w/water_design", {"name": "wtest", "ohts": [dict(oht, staging_m="")]})
    assert auto["ok"] and auto["outlets"][0]["staging_auto"] and 17 - 1e-6 <= auto["outlets"][0]["lowest_p"] < 17.5 + 1e-6


def test_water_table_edits(server):
    """Pipe / junction tables of the page: a pipe's size and a junction's GL / population changed in the table are
    designed with (the size kept as given), shown as edited, kept with the result; unknown labels left out."""
    url, _ = server
    with open(SAMPLE, encoding="utf-8") as fh:
        kml = fh.read()
    r = call(url + "/api/w/layout", {"name": "wed", "kml": kml, "gl_mode": "spots", "snap": 1, "spacing": 100})
    m = max(r["manholes"], key=lambda x: x["gl"] or 0)
    req = {"name": "wed", "ohts": [{"name": "OHT-1", "lat": m["latlng"][0], "lng": m["latlng"][1], "capacity_kl": "",
                                    "staging_m": 22, "tubewells": 0}], "pop_factor": 1}
    d = call(url + "/api/w/water_design", req)
    assert d["ok"] and d["sizes"] and d["edits"] == {"pipes": {}, "junctions": {}}
    assert all("checks" in p and not p["edited"] for p in d["pipes"]) and all("pop" in n for n in d["nodes"])
    p = next(x for x in d["pipes"] if not x["closed"])
    big = d["sizes"][-1]
    n = next(x for x in d["nodes"] if x["p"] is not None and x["label"] != m.get("label"))
    edits = {"pipes": {p["label"]: {"size": big}, "NOPE": {"size": big}},
             "junctions": {n["label"]: {"gl": n["gl"] - 2.0, "pop": 500}, "J-XX": {"gl": 1}}}
    e = call(url + "/api/w/water_design", dict(req, edits=edits))
    assert e["ok"], e.get("log")
    p2 = next(x for x in e["pipes"] if x["label"] == p["label"])
    assert p2["size"] == big and p2["edited"]
    n2 = next(x for x in e["nodes"] if x["label"] == n["label"])
    assert abs(n2["gl"] - (n["gl"] - 2.0)) < 1e-9 and n2["pop"] == 500 and n2["edited"]
    assert "edit ignored: pipe NOPE not in the network" in e["log"] and "edit ignored: junction J-XX" in e["log"]
    last = call(url + "/api/w/water_last?name=wed")
    assert last["design"]["edits"]["pipes"][p["label"]]["size"] == big


def test_existing_oht_then_proposed_ones_with_staging_from_the_design(server):
    """An existing OHT too small for the area: zoning proposes a new one; the design finds the staging of the new
    one (none given) - just enough for 17 m at its OZ's weakest node."""
    url, tmp = server
    with open(SAMPLE, encoding="utf-8") as fh:
        kml = fh.read()
    r = call(url + "/api/w/layout", {"name": "wplan", "kml": kml, "gl_mode": "spots", "snap": 1, "spacing": 100})
    m = min(r["manholes"], key=lambda x: x["latlng"][0] + x["latlng"][1])          # a corner
    old = {"name": "OLD-1", "lat": m["latlng"][0], "lng": m["latlng"][1], "capacity_kl": 300, "staging_m": 22,
           "tubewells": 1}
    z = call(url + "/api/w/water_zoning", {"name": "wplan", "ohts": [old], "pop_factor": 3})
    assert z["ok"], z.get("log")
    assert [p["name"] for p in z["proposed"]] == ["Prop-OHT-1"]
    oz = {x["name"]: x for x in z["zones"]}
    assert oz["OLD-1"]["existing"] and oz["OLD-1"]["demand_kld"] <= 300 / 0.33 + 1e-6
    assert oz["Prop-OHT-1"]["proposed"] and oz["Prop-OHT-1"]["required_kl"] > 0
    d = call(url + "/api/w/water_design", {"name": "wplan", "ohts": [old], "pop_factor": 3})
    assert d["ok"], d.get("log")
    out = {o["name"]: o for o in d["outlets"]}
    assert not out["OLD-1"]["staging_auto"] and out["OLD-1"]["staging_m"] == 22 and out["OLD-1"]["short_m"] is None
    n1 = out["Prop-OHT-1"]
    assert n1["staging_auto"] and n1["proposed"] and 10 <= n1["staging_m"] <= 30
    assert n1["staging_m"] * 2 == int(n1["staging_m"] * 2)                         # in steps of 0.5 m
    assert 17 - 1e-6 <= n1["lowest_p"] < 17.5 + 1e-6                               # just enough
    assert all(c["ok"] for c in d["checks"])
    # an existing OHT too low for its OZ - by default (CPHEEO Table 2.7 S.No.10 p173) it keeps its OZ and gets a
    # VFD pump at its outlet: the head missing, at its peak outlet flow
    vf = call(url + "/api/w/water_design", {"name": "wplan", "ohts": [dict(old, staging_m=16)], "pop_factor": 3})
    assert vf["ok"], vf.get("log")
    lv = {o["name"]: o for o in vf["outlets"]}
    assert lv["OLD-1"]["low_head"] == "vfd" and lv["OLD-1"]["vfd_head_m"] > 0 and lv["OLD-1"]["vfd_kw"] > 0
    assert lv["OLD-1"]["staging_m"] == 16 and lv["OLD-1"]["short_m"] is None and lv["OLD-1"]["lowest_p"] >= 17 - 1e-6
    assert lv["OLD-1"]["population"] == out["OLD-1"]["population"]                # the same OZ
    assert any(c["check"] == "OLD-1: VFD pump at the outlet" for c in vf["checks"]) and vf["checks"][0]["ok"]
    # set to give its higher ground to a new OHT: the junctions it cannot give 17 m go - by their ground in the
    # zoning, and those its designed pipes still leave below 17 m by zoning and design again
    low = call(url + "/api/w/water_design", {"name": "wplan", "ohts": [dict(old, staging_m=16, low_head="new_oht")],
                                             "pop_factor": 3})
    assert low["ok"], low.get("log")
    lo = {o["name"]: o for o in low["outlets"]}
    moved = [c for c in low["checks"] if c["check"].startswith("OLD-1:") and "new OHT" in c["check"]]
    assert moved and "Prop-OHT-" in moved[0]["detail"], low["checks"]
    assert lo["OLD-1"]["population"] < oz["OLD-1"]["population"] and not lo["OLD-1"]["vfd_head_m"]
    below = [n for n in low["nodes"] if n["oz"] == "OLD-1" and n["p"] is not None and n["p"] < 17 - 0.005]
    assert len(below) <= 1, below                                                  # at most the OHT's own node
    assert all(o["short_m"] is None for nm, o in lo.items() if nm != "OLD-1")
    zl = call(url + "/api/w/water_last?name=wplan")                                # the zones shown: as designed
    assert {x["name"] for x in zl["zoning"]["zones"]} == set(lo) and "design" in zl
    # no OHT at all: all proposed
    z0 = call(url + "/api/w/water_zoning", {"name": "wplan", "ohts": [], "pop_factor": 1})
    assert z0["ok"] and len(z0["proposed"]) == 1


def test_existing_and_new_tanks(server):
    """Ex-OHT (existing: capacity and staging required) and Prop-OHT (new: capacity from the OZ, a capacity given is
    not used); proposals numbered on after the Prop-OHTs drawn."""
    url, tmp = server
    with open(SAMPLE, encoding="utf-8") as fh:
        kml = fh.read()
    r = call(url + "/api/w/layout", {"name": "wex", "kml": kml, "gl_mode": "spots", "snap": 1, "spacing": 0})
    m = r["manholes"][0]
    ex = {"name": "Ex-OHT-1", "lat": m["latlng"][0], "lng": m["latlng"][1], "existing": "1", "capacity_kl": "",
          "staging_m": 20}
    bad = call(url + "/api/w/water_zoning", {"name": "wex", "ohts": [ex]})
    assert not bad["ok"] and "Ex-OHT-1" in bad["log"] and "क्षमता" in bad["log"]
    bad = call(url + "/api/w/water_zoning", {"name": "wex", "ohts": [dict(ex, capacity_kl=200, staging_m="")]})
    assert not bad["ok"] and "staging" in bad["log"]
    prop = {"name": "Prop-OHT-1", "lat": m["latlng"][0], "lng": m["latlng"][1], "existing": "0", "capacity_kl": 50,
            "staging_m": ""}
    z = call(url + "/api/w/water_zoning", {"name": "wex", "ohts": [dict(ex, capacity_kl=100), prop], "pop_factor": 3})
    assert z["ok"], z.get("log")
    oz = {x["name"]: x for x in z["zones"]}
    assert oz["Ex-OHT-1"]["existing"] and not oz["Prop-OHT-1"]["existing"]          # the 50 KL of a new tank: not used
    assert all(p["name"].startswith("Prop-OHT-") and p["name"] != "Prop-OHT-1" for p in z["proposed"])


def test_water_network_from_a_dxf(server, sewer):
    """The DXF panel in the water module: layers, network, save - then zoning and design on that network, its
    population the total given spread by pipe length (no wards); kept in the water folders only."""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from test_dxf_extract import make_dxf
    from water_app import netedit
    netedit._UNDO.clear()
    url, tmp = server
    src = str(tmp / "small.dxf")
    make_dxf(src)
    with open(src, "rb") as fh:                                                   # picked on the page: uploaded
        req = urllib.request.Request(url + "/api/w/dxf_upload?file=small.dxf", data=fh.read(),
                                     headers={"Content-Type": "application/octet-stream"})
    with urllib.request.urlopen(req, timeout=60) as r:
        path = json.loads(r.read())["path"]
    assert path.startswith(str(tmp / "w_projects" / "dxf"))                       # the water module's folder
    lay = call(url + "/api/w/dxf_layers", {"path": path})
    assert lay["ok"] and lay["guess"]["pipe"] == ["PIPE"]
    d = call(url + "/api/w/dxf_import", {"path": path, "name": "wsmall", "pipe_layers": ["PIPE"], "mh_layers": ["MH"],
                                         "level_layers": ["GL"], "epsg": "local"})
    assert d["ok"] and len(d["nodes"]) == 6
    assert [p["name"] for p in call(url + "/api/w/projects")["projects"]] == ["wsmall"]
    assert call(sewer + "/api/projects")["projects"] == []                        # not a sewer project
    assert call(url + "/api/w/net_save", {"name": "wsmall"})["ok"]
    a = d["nodes"]["MH-1"]["latlng"]
    oht = {"name": "Ex-OHT-1", "lat": a[0], "lng": a[1], "existing": "1", "capacity_kl": 200, "staging_m": 20}
    bad = call(url + "/api/w/water_zoning", {"name": "wsmall", "ohts": [oht], "pop_factor": 1})
    assert not bad["ok"] and "population" in bad["log"]                          # no wards, no total
    z = call(url + "/api/w/water_zoning", {"name": "wsmall", "ohts": [oht], "pop_factor": 1, "pop_total": 1500})
    assert z["ok"], z.get("log")
    assert z["population"] == 1500 and [x["name"] for x in z["zones"]] == ["Ex-OHT-1"]
    w = call(url + "/api/w/water_design", {"name": "wsmall", "ohts": [oht], "pop_factor": 1, "pop_total": 1500})
    assert w["ok"], w.get("log")
    assert len(w["pipes"]) == 5 and w["outlets"][0]["lowest_p"] >= 17 - 1e-6
    last = call(url + "/api/w/water_last?name=wsmall")
    assert last["network_current"] and last["design"]["req"]["pop_total"] == 1500
    # wards drawn on the DXF network (user 30-Oct-2026): their population on the junctions inside, the total given
    # not used; a junction in no ward gets none (warned, orange on the map); a ward with no junction is named
    far = max(d["nodes"], key=lambda n: d["nodes"][n]["latlng"][1])
    ins = [v["latlng"] for n, v in d["nodes"].items() if n != far]
    e = 1e-6
    la0, la1 = min(p[0] for p in ins) - e, max(p[0] for p in ins) + e
    lo0, lo1 = min(p[1] for p in ins) - e, max(p[1] for p in ins) + e
    assert d["nodes"][far]["latlng"][1] > lo1
    wards = [{"name": "Ward 7", "population": "1,200", "latlngs": [[la0, lo0], [la1, lo0], [la1, lo1], [la0, lo1]]},
             {"name": "Empty", "population": 300, "latlngs": [[la0 + 1, lo0], [la0 + 1.01, lo0], [la0 + 1.01, lo0 + .01]]}]
    z = call(url + "/api/w/water_zoning", {"name": "wsmall", "ohts": [oht], "pop_factor": 1, "pop_total": 1500,
                                           "wards": wards})
    assert z["ok"], z.get("log")
    assert z["population"] == 1200 and len(z["ward_out_pts"]) == 1
    txt = [f["text"] for f in z["flags"]]
    assert any(t.startswith("population from 2 ward(s) drawn on the map: 1,200 on 5 junctions") for t in txt)
    assert any(t.startswith("1 junctions (") and "lie in no ward" in t for t in txt)
    assert any("no junction inside" in t and "Empty" in t for t in txt)
    assert all(f.get("hi") for f in z["flags"])
    assert call(url + "/api/w/water_last?name=wsmall")["zoning"]["req"]["wards"][0]["name"] == "Ward 7"
    # a ward's character (user decision 6-Nov-2026, Riverside water DPR p76): its population is the present one, grown
    # by the character - Far-open x 1.0932 / 1.9183 / 3.3282 (7-Nov-2026) - in place of the page's factor; the stages by it too
    wc = [dict(wards[0], character="Far-open"), wards[1]]
    z = call(url + "/api/w/water_zoning", {"name": "wsmall", "ohts": [oht], "pop_factor": 1, "wards": wc})
    assert z["ok"], z.get("log")
    assert z["population"] == pytest.approx(1200 * 3.3282, abs=1)
    w = call(url + "/api/w/water_design", {"name": "wsmall", "ohts": [oht], "pop_factor": 1, "base_year": 2027,
                                           "wards": wc})
    assert w["ok"], w.get("log")
    st = {s["stage"]: s["pop"] for s in w["stages"]}
    assert st == {"init": round(1200 * 1.0932), "mid": round(1200 * 1.9183), "ult": round(1200 * 3.3282)}
    wb = openpyxl.load_workbook(w["files"]["dpr"])
    t8 = wb["T16 Ward Population"]
    row = next(r for r in t8.iter_rows(values_only=True) if r[1] == "Ward 7")
    assert row[2] == "Low (Far-open)" and row[3] == 1200       # the old name sent: the new one (9-Nov-2026) and row[5:8] == (1312, 2302, 3994)
    t2 = wb["T10 OZ Demand"]
    assert (t2["D6"].value, t2["E6"].value, t2["F6"].value) == (1312, 2302, 3994)
    assert {"T17 DMA Population", "T18 Water & Tube Wells", "T19 OHT Mass Balance", "T21 Pipe Table"} <= set(wb.sheetnames)
    # the ward table of the page (user decision 7-Nov-2026): each ward's no., name, population of a year (2025) and
    # the share covered; the ward drawn with that no. takes its covered population, one with no boundary goes on the
    # junctions in no ward; with the census, the five methods from 2025 and the adopted grows it
    wt = {"year": 2025, "rows": [{"no": "7", "name": "Riverside", "pop": "2000", "cov": "50", "hh": "300", "area": "12",
                                  "census": "1500"},
                                 {"no": "9", "name": "Sikraul", "pop": "400", "cov": "100"}]}
    census = "1991 800, 2001 950, 2011 1100"
    wn = [dict(wards[0], ward_no="7"), wards[1]]
    rq = {"name": "wsmall", "ohts": [oht], "pop_factor": 1, "base_year": 2027, "wards": wn, "ward_table": wt,
          "projection": {"base_pop": "", "census": census, "method": ""}}
    pj = call(url + "/api/w/projection", rq)["projection"]
    assert pj["from_year"] == 2025 and pj["from_pop"] == 1400 and pj["adopted"] == "geometrical"
    z = call(url + "/api/w/water_zoning", rq)
    assert z["ok"], z.get("log")
    assert z["population"] == pytest.approx(1400 * pj["ratio_from"]["ult"], abs=2)
    w = call(url + "/api/w/water_design", rq)
    assert w["ok"], w.get("log")
    st = {s["stage"]: s["pop"] for s in w["stages"]}
    assert st["init"] == pytest.approx(pj["pop"]["init"], abs=2) and st["ult"] == pytest.approx(pj["pop"]["ult"], abs=2)
    wb = openpyxl.load_workbook(w["files"]["dpr"])
    t8 = [r for r in wb["T16 Ward Population"].iter_rows(values_only=True)]
    lah = next(r for r in t8 if r[1] == "Riverside")
    assert lah[2] == "7" and lah[3] == 2000 and lah[8] == 0.5 and lah[13] == "-" and lah[14] == "yes"
    assert next(r for r in t8 if r[1] == "Sikraul")[14].startswith("no")
    assert call(url + "/api/w/water_last?name=wsmall")["design"]["req"]["ward_table"]["rows"][0]["no"] == "7"
    # the DMA-wise demand (example technical.xlsx 'Tech3', 9-Nov-2026): a row for each ward in the DMA, its no. and the
    # share of its design-year population; the junctions in no ward a row of their own
    dd = [r for r in wb["T5 DMA Demand"].iter_rows(min_row=10, values_only=True) if str(r[0]).startswith("Ex-OHT-1/")]
    assert [(r[1], r[2]) for r in dd] == [("7", 1.0), ("-", "-")], dd
    # the ward's character in the table (user decision 7-Nov-2026): Sikraul (no boundary: on the junctions in no
    # ward) Far-open by the page's factors, Riverside by the method - the stages and the DPR's formulas by them
    # (the town's Far-open population left empty: not balanced, the page's factors)
    wt2 = dict(wt, rows=[wt["rows"][0], dict(wt["rows"][1], char="Far-open")], growth={"Far-open": [1.1, 2.0, 3.0]},
               city={"Far-open": ""})
    rq2 = dict(rq, ward_table=wt2)
    pj = call(url + "/api/w/projection", rq2)["projection"]
    rf = pj["ratio_from"]
    want = {t: 1000 * rf[t] + 400 * f for t, f in (("init", 1.1), ("mid", 2.0), ("ult", 3.0))}
    assert {t: pj["wards"][t] for t in want} == pytest.approx(want)
    w = call(url + "/api/w/water_design", rq2)
    assert w["ok"], w.get("log")
    st = {s["stage"]: s["pop"] for s in w["stages"]}
    assert st == {t: pytest.approx(v, abs=2) for t, v in want.items()}
    wb = openpyxl.load_workbook(w["files"]["dpr"])
    t8 = wb["T16 Ward Population"]
    x = next(c.row for c in t8["B"] if c.value == "Sikraul")
    g = next(c.row for c in t8["B"] if c.value == "Low (Far-open)")
    assert t8.cell(x, 14).value == "Low (Far-open)" and t8.cell(x, 13).value == f"=ROUND(J{x}*$F${g},0)"
    assert t8.cell(g, 4).value == 1.1 and t8.cell(g, 6).value == 3.0
    # Far-open balanced to the adopted method (user decision 7-Nov-2026; example technical.xlsx T P470): the town's
    # population by character (default Springfield's; here given) grown by the method, less the others x their factors
    city = {"Proximal Developed": 100, "Core": 100, "Proximal Developing": 100, "Far-open": 200}
    rq3 = dict(rq, ward_table=dict(wt2, city=city))
    pj = call(url + "/api/w/projection", rq3)["projection"]
    G = {"Proximal Developed": [1.02, 1.25, 1.50], "Core": [1.04, 1.40, 1.85], "Proximal Developing": [1.06, 1.63, 2.45]}
    R = pj["town_ratio_from"]
    fo = [(500 * R[t] - sum(100 * v[j] for v in G.values())) / 200 for j, t in enumerate(("init", "mid", "ult"))]
    assert pj["far_open"]["factors"] == pytest.approx(fo, abs=1e-5) and all(x > 0 for x in fo)
    rf = pj["ratio_from"]
    want = {t: 1000 * rf[t] + 400 * fo[j] for j, t in enumerate(("init", "mid", "ult"))}
    assert {t: pj["wards"][t] for t in want} == pytest.approx(want)
    w = call(url + "/api/w/water_design", rq3)
    assert w["ok"], w.get("log")
    assert {s["stage"]: s["pop"] for s in w["stages"]} == {t: pytest.approx(v, abs=2) for t, v in want.items()}
    assert any("Far-open" in f["text"] and "balanced" in f["text"] for f in w.get("flags", []) + call(url + "/api/w/water_zoning", rq3)["flags"])
    t8 = openpyxl.load_workbook(w["files"]["dpr"])["T16 Ward Population"]
    g = next(c.row for c in t8["B"] if c.value == "Low (Far-open)")
    tg = next(c.row for c in t8["B"] if c.value == "The town by the adopted projection")
    assert t8.cell(g, 7).value == 200 and str(t8.cell(g, 4).value).startswith(f"=(D{tg}-")
    # the saturation density (CPHEEO Water Manual Part A Annexure 2.7; user decision 8-Nov-2026: only warned of):
    # Riverside 2000 / 12 ha (no character) x the adopted ratio above it - in the flags and T8, its population not cut
    d = 2000 / 12 * rf["ult"]
    sq = dict(rq3, ward_table=dict(rq3["ward_table"], sat=str(round(d * 0.9))))
    pj = call(url + "/api/w/projection", sq)["projection"]
    assert [x["no"] for x in pj["saturation"]["over"]] == ["7"] and pj["saturation"]["over"][0]["d"] == pytest.approx(d, abs=0.1)
    w = call(url + "/api/w/water_design", sq)
    assert w["ok"], w.get("log")
    assert {s["stage"]: s["pop"] for s in w["stages"]} == {t: pytest.approx(v, abs=2) for t, v in want.items()}
    fl = w.get("flags", []) + call(url + "/api/w/water_zoning", sq)["flags"]
    assert any("saturation" in f["text"] for f in fl)
    # CPHEEO Annexure 2.7 p974 (8-Nov-2026): the core's factor 1.50 above 1.10 warned of; the clauses in T8's note
    assert any(f["text"].startswith("Saturated (Core) x 1.50") and "p974" in f["text"] for f in fl)
    t8 = openpyxl.load_workbook(w["files"]["dpr"])["T16 Ward Population"]
    x = next(c.row for c in t8["B"] if c.value == "Riverside")
    assert t8.cell(x, 16).value == f'=IFERROR(H{x}*M{x}/J{x},"")'
    assert t8.cell(x, 17).value.startswith(f'=IF(P{x}="","",IF(P{x}>$P$')
    assert any("2.8.1.24" in str(c.value) and "585 Saturated (Core)" in str(c.value) for c in t8["B"])
    assert "saturation" not in call(url + "/api/w/projection", dict(sq, ward_table=dict(sq["ward_table"], sat="")))["projection"]
    # a method too slow for the factors: not balanced, the page's, warned
    slow = dict(rq3, projection=dict(rq3["projection"], method="arithmetical"),
                ward_table=dict(wt2, city=dict(city, **{"Far-open": 1})))
    pj = call(url + "/api/w/projection", slow)["projection"]
    assert "far_open" not in pj and "Far-open" in pj["far_open_error"]
    # kept with the project, as its barrier lines
    keep = [{"latlngs": wards[0]["latlngs"], "props": {"name": "Ward 7", "population": "1200"}}]
    assert call(url + "/api/w/wards_save", {"name": "wsmall", "wards": keep})["ok"]
    assert call(url + "/api/w/wards?name=wsmall")["wards"] == keep


def test_water_dxf_export(server):
    """Export DXF (user request 21-Oct-2026): the last zoning and, when made on it, its design in one drawing."""
    import ezdxf
    url, tmp = server
    with open(SAMPLE, encoding="utf-8") as fh:
        kml = fh.read()
    assert call(url + "/api/w/layout", {"name": "wx", "kml": kml, "gl_mode": "spots", "snap": 1, "spacing": 100})["ok"]
    r = call(url + "/api/w/water_export", {"name": "wx"})
    assert not r["ok"] and "Zoning" in r["log"]                              # nothing to export yet
    z = call(url + "/api/w/water_zoning", {"name": "wx", "pop_factor": 1.5})
    assert z["ok"]
    r = call(url + "/api/w/water_export", {"name": "wx"})
    assert r["ok"] and not r["counts"]["design"] and os.path.isfile(r["path"])
    layers = {e.dxf.layer for e in ezdxf.readfile(r["path"]).modelspace()}
    assert {"W_OZ_1", "W_DMA_BOUNDARY", "W_OHT", "W_PIPE", "W_JUNCTION", "W_JUNCTION_TEXT", "W_TITLE"} <= layers
    d = call(url + "/api/w/water_design", {"name": "wx", "pop_factor": 1.5})
    assert d["ok"], d.get("log")
    r = call(url + "/api/w/water_export", {"name": "wx"})
    assert r["ok"] and r["counts"]["design"] and r["counts"]["pipes"] == len(d["pipes"])
    msp = ezdxf.readfile(r["path"]).modelspace()
    txt = [e.dxf.text for e in msp.query("TEXT")]
    p = next(p for p in d["pipes"] if p["nominal"])
    assert any(t.startswith(f"{p['label']}/{p['nominal']:g}mm") or t == p["label"] for t in txt)
    n = next(x for x in d["nodes"] if x["head"] is not None)
    assert f"HGL {n['head']:.2f}" in txt and f"P {n['p']:.2f}" in txt
    assert len(msp.query("SOLID[layer=='W_FLOW_ARROW']")) > 0


def test_ward_table_from_a_kml():
    """'KML से वार्ड तालिका' (user decision 7-Nov-2026): a polygon with a ward number / name field is a ward, the others
    the zone; each ward's area and the share of it in the zone (only a check), its population / households where the
    KML gives them above 0, its boundary for the map."""
    from water_app import ui_api
    dx, dy = 0.0099, 0.009                       # about 1 km at Springfield
    sq = lambda x0, y0, x1, y1: " ".join(f"{x:.6f},{y:.6f}" for x, y in
                                         ((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)))
    pm = lambda name, data, c: (f"<Placemark><name>{name}</name><ExtendedData>" +
                                "".join(f'<Data name="{k}"><value>{v}</value></Data>' for k, v in data.items()) +
                                f"</ExtendedData><Polygon><outerBoundaryIs><LinearRing><coordinates>{c}"
                                "</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>")
    x, y = 82.95, 25.35
    kml = ('<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>' +
           pm("Zone", {"Zone_Name": "Z"}, sq(x, y, x + 2 * dx, y + dy)) +
           pm("A", {"W_NUM": "007", "W_Name": "Alpha", "W_POP": "1200", "W_HH": "0"}, sq(x, y, x + dx, y + dy)) +
           pm("B", {"W_NUM": "009", "W_Name": "Beta", "W_POP": "0"}, sq(x + 1.5 * dx, y, x + 2.5 * dx, y + dy)) +
           "</Document></kml>")
    r = ui_api.ward_kml_table(kml)
    a, b = r["rows"]
    assert (a["no"], a["name"], a["pop"], a["hh"], a["cov"]) == ("007", "Alpha", 1200, "", "")
    assert a["area"] == pytest.approx(100, rel=0.02) and a["kcov"] == pytest.approx(100, abs=1)
    assert (b["no"], b["pop"]) == ("009", "") and b["kcov"] == pytest.approx(50, abs=1.5)
    assert r["zone"]["area_ha"] == pytest.approx(200, rel=0.02)
    assert [w["no"] for w in r["wards"]] == ["007", "009"] and len(r["wards"][0]["latlngs"]) == 5
