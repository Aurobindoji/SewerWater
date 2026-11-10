"""Bulk / institutional consumers (user request 30-Oct-2026: a hospital, industry, station ... - a demand no
population gives): a point on the map with its KLD and peak factor, on the nearest junction; + 10 % distribution
losses, its own peak factor in the design, the same at every stage (user decisions 30-Oct-2026); in the OZ demand,
OHT capacity and tube wells of the zoning, and a yellow column of its own in DPR T1."""
import openpyxl
import pytest

from test_dxf_extract import make_dxf
from test_water_ui import SAMPLE, call, server  # noqa: F401  (the fixture)
from test_water_zoning import grid
from water_app import demand as dm
from water_app import netedit
from water_app import zoning as wz
from water_app.design import load_criteria


def test_zoning_counts_bulk_demand():
    crit = load_criteria()
    net = grid(n=6, pop=300)
    base = wz.make_zones(net, [{"name": "A", "node": (0, 0)}], crit)["zones"][0]
    net["nodes"][(3, 3)].update(bulk_raw=500.0, bulk_kl=550.0, bulk_peak_kl=1650.0)
    z = wz.make_zones(net, [{"name": "A", "node": (0, 0)}], crit)["zones"][0]
    assert z["demand_kld"] == pytest.approx(base["demand_kld"] + 550.0, abs=0.1) and z["bulk_kld"] == 500.0
    assert z["required_kl"] > base["required_kl"] and base["bulk_kld"] == 0
    assert dm.tubewells_new(10800, crit, 0, 2000.0) > dm.tubewells_new(10800, crit, 0)
    # a whole OZ of it in plan: the OHT proposed for the area sized on it too
    p = wz.plan(net, [], crit)
    assert sum(x["bulk_kld"] for x in p["zones"]) == 500.0


def test_bulk_consumer_on_a_dxf_network(server, tmp_path):  # noqa: F811
    url, tmp = server
    src = str(tmp / "small.dxf")
    make_dxf(src)
    netedit._UNDO.clear()
    d = call(url + "/api/w/dxf_import", {"path": src, "name": "wbk", "pipe_layers": ["PIPE"], "mh_layers": ["MH"],
                                         "level_layers": ["GL"], "epsg": "local"})
    assert d["ok"]
    a, m3 = d["nodes"]["MH-1"]["latlng"], d["nodes"]["MH-3"]["latlng"]
    oht = {"name": "Prop-OHT-1", "lat": a[0], "lng": a[1], "existing": "0", "capacity_kl": "", "staging_m": ""}
    req = {"name": "wbk", "ohts": [oht], "pop_factor": 1, "pop_total": 1500}
    z0 = call(url + "/api/w/water_zoning", req)
    w0 = call(url + "/api/w/water_design", req)
    assert z0["ok"] and w0["ok"], (z0.get("log"), w0.get("log"))
    # no fire demand in the network's flow (user decision 30-Oct-2026): domestic x 1.10 + floating only; the fire held
    # in the OHT (its capacity: the zoning's demand has it)
    assert w0["summary"]["demand_avg_lps"] == pytest.approx((1500 * 150 * 1.1 + 150 * 45) / 1000 / 86.4, abs=0.01)
    fire = next(c for c in w0["checks"] if c["check"] == "fire demand")
    assert "not in the network's peak flow" in fire["detail"] and "peak flow में नहीं" in fire["detail_hi"]
    assert z0["zones"][0]["demand_kld"] > (1500 * 150 * 1.1 + 150 * 45) / 1000 + 1
    bulk = [{"name": "Hospital", "lat": m3[0] + 1e-6, "lng": m3[1], "kld": "200", "peak": "3"},
            {"name": "Far", "lat": m3[0] + 0.01, "lng": m3[1], "kld": 10, "peak": ""},
            {"name": "Nothing", "lat": m3[0], "lng": m3[1], "kld": "", "peak": 2}]                # no KLD: left out
    req = dict(req, bulk=bulk)
    z = call(url + "/api/w/water_zoning", req)
    assert z["ok"], z.get("log")
    assert [(b["name"], b["peak"]) for b in z["bulk_pts"]] == [("Hospital", 3.0), ("Far", 2.5)]
    assert z["bulk_pts"][0]["node"] == "MH-3" and z["bulk_pts"][1]["dist_m"] > 200
    txt = [f["text"] for f in z["flags"]]
    assert any(t.startswith("2 bulk consumer(s): 210.0 KLD, 231.0 KLD with distribution losses") for t in txt)
    assert any("farther than 200 m" in t and "Far" in t for t in txt) and all(f.get("hi") for f in z["flags"])
    assert z["zones"][0]["demand_kld"] == pytest.approx(z0["zones"][0]["demand_kld"] + 231.0, abs=0.2)
    assert z["zones"][0]["bulk_kld"] == 210.0
    # the checking map (user request 30-Oct-2026): every junction's population and bulk KLD; OZ / DMA area and density
    load = {x[0]: x for x in z["node_load"]}
    assert len(load) == len(d["nodes"]) and sum(x[3] for x in load.values()) == pytest.approx(1500, abs=0.5)
    assert load["MH-3"][4] == 200.0 and sum(x[4] for x in load.values()) == 210.0
    oz = z["zones"][0]
    assert oz["area_ha"] > 0 and oz["density"] == pytest.approx(oz["population"] / oz["area_ha"], rel=0.01)
    assert all(x["area_ha"] > 0 and x["density"] > 0 for x in z["dmas"])
    assert call(url + "/api/w/water_last?name=wbk")["zoning"]["req"]["bulk"][0]["name"] == "Hospital"
    w = call(url + "/api/w/water_design", req)
    assert w["ok"], w.get("log")
    # the average demand + the bulk KLD with losses; at MH-3 the hospital at its own peak factor 3
    assert w["summary"]["demand_avg_lps"] == pytest.approx(w0["summary"]["demand_avg_lps"] + 231.0 / 86.4, abs=0.02)
    q = lambda r, n: next(x["q"] for x in r["nodes"] if x["label"] == n)
    assert q(w, "MH-3") == pytest.approx(q(w0, "MH-3") + 220.0 * 3 / 86.4, abs=0.01)
    assert any(c["check"] == "bulk consumers" and "Hospital 200 KLD x 3 at MH-3" in c["detail"] for c in w["checks"])
    # DPR T1: the bulk column (yellow, KLD of the OZ) in the demands; the consumers listed below
    ws = openpyxl.load_workbook(w["files"]["dpr"])["T10 OZ Demand"]
    head = {ws.cell(5, c).value: c for c in range(1, ws.max_column + 1)}
    cb = head["Bulk consumers (KLD without losses, every year)"]
    col = openpyxl.utils.get_column_letter(cb)
    assert ws.cell(6, cb).value == 210.0
    assert ws.cell(6, cb).fill.fgColor.rgb.endswith("FFF2CC")                      # yellow: an input
    assert f"+${col}6" in ws.cell(6, 10).value and f"+${col}6*(1+" in ws.cell(6, 13).value
    listed = [ws.cell(r, 2).value for r in range(1, ws.max_row + 1)]
    assert "BULK / INSTITUTIONAL CONSUMERS" in listed and "Hospital" in listed and "Far" in listed
    # kept with a DXF project, as its OHTs
    keep = [{"latlng": [m3[0], m3[1]], "props": {"name": "Hospital", "kld": "200", "peak": "3"}}]
    assert call(url + "/api/w/bulk_save", {"name": "wbk", "bulk": keep})["ok"]
    assert call(url + "/api/w/bulk?name=wbk")["bulk"] == keep


def test_a_bulk_point_of_the_kml_is_no_spot_level(server):  # noqa: F811
    url, _ = server
    with open(SAMPLE, encoding="utf-8") as fh:
        kml = fh.read()
    lay = {"gl_mode": "spots", "snap": 1, "spacing": 100}
    r0 = call(url + "/api/w/layout", dict(lay, name="wkb0", kml=kml))
    m = r0["manholes"][0]["latlng"]
    pt = (f'<Folder><name>Bulk consumers</name><Placemark><name>Hospital 2</name><ExtendedData><Data name="kind"><value>'
          f'bulk</value></Data><Data name="kld"><value>200</value></Data></ExtendedData><Point><coordinates>{m[1]},{m[0]},0'
          f'</coordinates></Point></Placemark></Folder>')
    r1 = call(url + "/api/w/layout", dict(lay, name="wkb1", kml=kml.replace("</Document>", pt + "</Document>")))
    assert r0["ok"] and r1["ok"], r1.get("log")
    assert [x["gl"] for x in r1["manholes"]] == [x["gl"] for x in r0["manholes"]]   # "Hospital 2" is no GL of 2 m
