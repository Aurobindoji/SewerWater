"""Map UI server (python -m sewer_app ui): pages, projects, KMZ, and a layout from the sample KML as the page sends it."""
import io
import json
import os
import threading
import urllib.error
import urllib.request
import zipfile
from http.server import ThreadingHTTPServer

import pytest

from sewer_app import ui

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


def call(url, body=None, host=None):
    req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json", **({"Host": host} if host else {})})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    return json.loads(data) if r.headers.get_content_type() == "application/json" else data.decode("utf-8")


def test_page_and_projects(server):
    page = call(server + "/sewer")
    assert "leaflet@1.9.4" in page and "leaflet-draw@1.0.4" in page and "i18n.js" in page
    assert "I18N_EN" in call(server + "/i18n.js")
    # nothing of the water module or the start page here (user decision 10-Nov-2026): "/" is the sewer page itself,
    # /water is not known; the page's button opens the water app through the launcher
    import http.client
    host, port = server.split("//")[1].split(":")
    c = http.client.HTTPConnection(host, int(port), timeout=10)
    c.request("GET", "/?lang=en")
    r = c.getresponse()
    assert r.status == 302 and r.getheader("Location") == "/sewer?lang=en"
    c.close()
    with pytest.raises(urllib.error.HTTPError):
        call(server + "/water")
    assert 'id="otherapp"' in page and "8764/api/open?module=${O.name}" in page and 'name: "water"' in page
    r = call(server + "/api/save", {"name": "वार्ड 5 / test", "kml": "<kml/>"})
    assert r["ok"] and r["name"] == "वार्ड_5_test"                      # no path separators survive
    assert [p["name"] for p in call(server + "/api/projects")["projects"]] == ["वार्ड_5_test"]
    assert call(server + "/api/project?name=" + urllib.request.quote("वार्ड_5_test"))["kml"] == "<kml/>"
    with pytest.raises(urllib.error.HTTPError) as e:                     # only for this computer's own address
        call(server + "/api/projects", host="example.com")
    assert e.value.code == 403


def test_kmz(server):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("doc.kml", "<kml>x</kml>")
    import base64
    r = call(server + "/api/kmz", {"data": base64.b64encode(buf.getvalue()).decode()})
    assert r["ok"] and r["kml"] == "<kml>x</kml>"


def test_layout_from_page(server):
    with open(SAMPLE, encoding="utf-8") as fh:
        kml = fh.read()
    r = call(server + "/api/layout", {"name": "sample", "kml": kml, "gl_mode": "spots", "snap": 1, "spacing": 30})
    assert r["ok"], r["log"]
    assert "boundary 5 points" in r["log"]                     # the boundary polygon, not a ward
    assert len(r["manholes"]) > 100 and len(r["conduits"]) >= len(r["manholes"]) - 1
    lat, lon = r["manholes"][0]["latlng"]
    assert 25.32 < lat < 25.34 and 82.98 < lon < 83.00          # back in lon / lat for the map
    assert abs(sum(m["pop"] for m in r["manholes"]) - 9000) < 2
    assert r["marks"] and r["marks"][0]["name"] == "STP"
    assert all(os.path.isfile(f) for f in r["files"].values())
    bad = call(server + "/api/layout", {"name": "sample", "kml": kml, "gl_mode": "flat", "flat_gl": ""})
    assert not bad["ok"]


def test_zoning_and_design_from_page(server):
    """After the layout: zoning options with costs and zones for the map, then the design of one option (the
    zoning is not run again for the same inputs)."""
    with open(SAMPLE, encoding="utf-8") as fh:
        kml = fh.read()
    assert call(server + "/api/layout", {"name": "s", "kml": kml})["ok"]
    cats = call(server + "/api/catalogs")["catalogs"]
    assert cats and all("TEST" not in c["name"] for c in cats)
    req = {"name": "s", "stp": "MH-17", "catalog": cats[0]["name"], "joint": "ss", "sewage_lpcd": 108,
           "start_depth": 0.7}
    z = call(server + "/api/zoning", req)
    assert z["ok"], z["log"]
    # the wards of the KML (9000) are the base-year population; the design is on the +30 years forecast
    fc = z["inputs"]["forecast"]
    assert z["inputs"]["pop_dist"] == "csv" and fc["pop"]["init"] == 9000 and z["inputs"]["pop_total"] == fc["design"]["ult"]
    assert abs(z["inputs"]["pop_scale"] * 9000 - z["inputs"]["pop_total"]) < 1e-6
    assert [o["rank"] for o in z["options"]] == list(range(1, len(z["options"]) + 1))
    for o in z["options"]:
        assert o["total_lakh"] >= o["pipe_lakh"] > 0
        assert {x["manhole"] for x in o["outlets"]} == set(o["conduit_zone"].values())
        assert any(x["role"].startswith("STP") for x in o["outlets"])                    # MH-17 is the STP
    assert os.path.isfile(z["files"]["xlsx"]) and os.path.isfile(z["files"]["costs"])
    opt = z["options"][-1]
    d = call(server + "/api/design", dict(req, option=opt["option"]))
    assert d["ok"], d["log"]
    s = d["summary"]
    assert s["option"] == opt["option"] and sorted(s["outfalls"]) == sorted(x["manhole"] for x in opt["outlets"])
    assert abs(s["pipe_lakh"] - opt["pipe_lakh"]) < 0.01 and s["max_depth"] == opt["max_depth"]
    assert len(d["sewers"]) == s["sewers"] and all(w["D"] >= 200 for w in d["sewers"])
    assert len(d["warnings_hi"]) == len(d["warnings"])                           # their Hindi for the page
    assert all(os.path.isfile(f) for f in d["files"].values())
    assert call(server + "/api/zoning", req)["cached"]                  # same inputs: zoning not run again
    assert not call(server + "/api/zoning", {"name": "nothing_here"})["ok"]


def test_max_depth_from_page(server):
    """'अधिकतम गहराई (m)' of the page: the project depth limit of this run - a lower limit adds pumping stations
    (sub-zones); the default is design_criteria.json's max_depth_project_m."""
    with open(SAMPLE, encoding="utf-8") as fh:
        kml = fh.read()
    assert call(server + "/api/layout", {"name": "s", "kml": kml})["ok"]
    assert call(server + "/api/catalogs")["max_depth"] == 10.0
    req = {"name": "s", "stp": "MH-17", "sewage_lpcd": 108, "start_depth": 0.7}
    deep = call(server + "/api/zoning", dict(req))                       # sample: about 4.3 m deep at most
    assert all(o["pumping_for_depth"] == 0 for o in deep["options"])
    low = call(server + "/api/zoning", dict(req, max_depth=3))
    assert low["ok"] and all(o["pumping_for_depth"] >= 1 for o in low["options"])
    assert all(o["max_depth"] <= 3.0 + 1e-6 for o in low["options"])
    for o in low["options"]:                    # main zones (slope) with boundaries; sub-zones (depth) inside them
        mains = {m["outlet"] for m in o["mains"]}
        assert mains and all(m["rings"] for m in o["mains"])
        assert set(o["subs"]) and all(o["parent"][s_] in mains for s_ in o["subs"])
        depth_subs = [s_ for s_ in o["subs"] if s_ not in mains]                # + the rest of each such main zone
        assert len(depth_subs) == o["pumping_for_depth"]
        assert {s_ for s_ in o["subs"] if s_ in mains} == {o["parent"][s_] for s_ in depth_subs}
        assert all(len(r) >= 3 for m in o["mains"] for r in m["rings"])
    d = call(server + "/api/design", dict(req, max_depth=3, option=low["options"][0]["option"]))
    assert d["ok"] and d["summary"]["max_depth"] <= 3.0 + 1e-6
    assert not call(server + "/api/zoning", dict(req, max_depth=50))["ok"]


def test_design_tables_and_edits(server):
    """Pipe / manhole tables of the page: the design gives every manhole and the manual checks of every sewer; the
    table's changes (diameter / slope of a conduit, GL / invert of a manhole) are designed as given, kept with the
    result and shown again; an unknown label is left out."""
    with open(SAMPLE, encoding="utf-8") as fh:
        kml = fh.read()
    assert call(server + "/api/layout", {"name": "s", "kml": kml})["ok"]
    req = {"name": "s", "stp": "MH-17", "sewage_lpcd": 108, "start_depth": 0.7, "mode": "given"}
    opt = call(server + "/api/zoning", req)["options"][0]["option"]
    d = call(server + "/api/design", dict(req, option=opt))
    assert d["ok"], d["log"]
    assert d["sizes"] and d["edits"] == {"conduits": {}, "manholes": {}, "trunk": []}
    assert {m["label"] for m in d["manholes"]} >= {s["from"] for s in d["sewers"]}
    assert all("checks" in s and "dd" in s and not s["edited"] for s in d["sewers"])
    s = max(d["sewers"], key=lambda x: x["q"])                       # a trunk sewer
    big = next(z["id_mm"] for z in d["sizes"] if z["id_mm"] > s["D"] + 1)
    mh = next(m for m in d["manholes"] if m["ins"] and m["outs"])
    edits = {"conduits": {s["label"]: {"D": big, "slope": 1 / 1500}, "NOPE": {"D": 300}},
             "manholes": {mh["label"]: {"gl": round(mh["gl"] + 1.0, 3)}}}
    e = call(server + "/api/design", dict(req, option=opt, edits=edits))
    assert e["ok"], e["log"]
    s2 = next(x for x in e["sewers"] if x["label"] == s["label"])
    assert s2["D"] == big and abs(s2["slope"] - 1 / 1500) < 1e-9 and s2["edited"]
    assert "slope < Table 3.13" in s2["checks"]
    m2 = next(m for m in e["manholes"] if m["label"] == mh["label"])
    assert abs(m2["gl"] - (mh["gl"] + 1.0)) < 1e-6 and m2["edited"]
    assert "NOPE" in e["edits"]["conduits"]                            # kept as given; the design ignored it
    last = call(server + "/api/last_results?name=s")
    assert last["design"]["req"]["edits"]["conduits"][s["label"]]["D"] == big


def test_bend_drop_from_page(server):
    """'मोड़ पर 30 mm drop' of the page: on by default (CPHEEO 3.20.3); off, a same-size sewer keeps its invert
    through a bend - no option is deeper, and the zoning is worked out again (not taken from the cache)."""
    assert ui.criteria_for()["sewer"]["drop_same_size_mm"]["value"] == 30
    assert ui.criteria_for(bend_drop=False)["sewer"]["drop_same_size_mm"]["value"] == 0
    assert ui.bend_drop_on(None) and ui.bend_drop_on(True) and not ui.bend_drop_on("false")
    with open(SAMPLE, encoding="utf-8") as fh:
        kml = fh.read()
    assert call(server + "/api/layout", {"name": "s", "kml": kml})["ok"]
    req = {"name": "s", "stp": "MH-17", "sewage_lpcd": 108, "start_depth": 0.7}
    on = {o["option"]: o for o in call(server + "/api/zoning", req)["options"]}
    z = call(server + "/api/zoning", dict(req, bend_drop=False))
    assert z["ok"] and not z["cached"] and "30 mm drop at a change of direction: OFF" in z["log"]
    off = {o["option"]: o for o in z["options"]}
    assert set(off) == set(on)
    assert all(off[k]["max_depth"] <= on[k]["max_depth"] + 1e-6 for k in on)
    assert any(off[k]["max_depth"] < on[k]["max_depth"] - 0.01 for k in on)
    k = next(iter(on))
    d_on = call(server + "/api/design", dict(req, option=k))
    d_off = call(server + "/api/design", dict(req, bend_drop=False, option=k))
    assert d_on["ok"] and d_off["ok"] and d_off["summary"]["max_depth"] <= d_on["summary"]["max_depth"] + 1e-6


def test_zoning_export(server, tmp_path):
    """Export of an option as the map shows it: DXF (main zones thick, sub-zones dashed, names, STP / PS, sewers by
    zone), KML for Google Earth, Excel with the zones / sub-zones table."""
    import xml.etree.ElementTree as ET
    import ezdxf
    import openpyxl
    from sewer_app import zone_export
    with open(SAMPLE, encoding="utf-8") as fh:
        kml = fh.read()
    assert call(server + "/api/layout", {"name": "s", "kml": kml})["ok"]
    z = call(server + "/api/zoning", {"name": "s", "stp": "MH-17", "sewage_lpcd": 108, "start_depth": 0.7, "max_depth": 3})
    o = z["options"][0]
    r = call(server + "/api/zoning_export", {"name": "s", "option": o["option"]})
    assert r["ok"], r.get("log")
    mains, parent, num, sub = zone_export.zone_names(o)
    msp = ezdxf.readfile(r["files"]["dxf"]).modelspace()
    zb = [e for e in msp.query("LWPOLYLINE") if e.dxf.layer.startswith("ZONE_BOUNDARY_")]
    sb = [e for e in msp.query("LWPOLYLINE") if e.dxf.layer.startswith("SUBZONE_BOUNDARY_")]
    assert {e.dxf.layer for e in zb} == {f"ZONE_BOUNDARY_{i}" for i in num.values()}         # the layer names it
    assert {e.dxf.layer for e in sb} == {f"SUBZONE_BOUNDARY_{v}" for v in sub.values()}
    names = {t.plain_text() for t in msp.query("MTEXT")}
    assert {f"ZONE {i}" for i in num.values()} <= names and {f"SUB-ZONE {v}" for v in sub.values()} <= names
    assert any(t.startswith("STP") for t in names)
    assert all(e.dxf.flags & 128 and e.dxf.const_width > 0 for e in sb)           # dashed along the ring, visible
    # every larger piece of a zone / sub-zone has its name inside
    for mz in o["mains"]:
        assert len(mz["ring_labels"]) == len(mz["rings"]) and mz["ring_labels"][0]
    tree = ET.parse(r["files"]["kml"])                                           # well-formed KML
    rows = list(openpyxl.load_workbook(r["files"]["xlsx"], read_only=True)["Zones"].iter_rows(values_only=True))
    assert {f"Zone {i}" for i in num.values()} <= {row[0] for row in rows[1:]}
    assert set(sub.values()) <= {row[1] for row in rows[1:]}
    import re                                                                    # exported files: English only
    for f in r["files"].values():
        if f.endswith((".kml", ".dxf")):
            with open(f, encoding="utf-8", errors="ignore") as fh:
                assert not re.search("[ऀ-ॿ]", fh.read()), f
    wb = openpyxl.load_workbook(r["files"]["xlsx"], read_only=True)
    assert not any(isinstance(v, str) and re.search("[ऀ-ॿ]", v)
                   for ws in wb.worksheets for row in ws.iter_rows(values_only=True) for v in row)
    assert not call(server + "/api/zoning_export", {"name": "s", "option": "NONE"})["ok"]
