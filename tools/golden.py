"""Golden outputs of the app, for a restructure that must not change what the app makes (user decision 15-Nov-2026:
the app restructured in stages, each stage proven to give the same results).

    python tools/golden.py snap  OUT_DIR          run the scenarios, write their outputs (canonical JSON) to OUT_DIR
    python tools/golden.py diff  OLD_DIR NEW_DIR  compare two snapshots; exit 1 on any difference

The scenarios go through the pages' own HTTP API (the URLs stay through the restructure, the code behind them may
move): both modules' servers run in this process on free ports, their data folders in a temporary folder
(WATER_APP_HOME / SEWER_APP_HOME set before the modules are imported). os.startfile is switched off, so Export DPR /
rate xlsx open nothing on the screen.

Kept of each output: the JSON answers (temporary paths, times and timestamps in file names masked, floats to 9
significant digits); every non-empty cell of every workbook (value or formula, number format, fill); every DXF
entity (type, layer, text, points to 1 mm). Mock data only (samples/sample_area.kml, the tests' small DXF).
"""
import datetime
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE = os.path.join(ROOT, "samples", "sample_area.kml")
TS = [(re.compile(r"\d{8}_\d{4,6}"), "<TS>"), (re.compile(r"\d{2}-\d{2}-\d{4} \d{2}:\d{2}"), "<TIME>"),
      (re.compile(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?"), "<TIME>"),
      (re.compile(r"\(\d+(\.\d+)? s\)"), "(<S> s)")]                      # run times in the logs
AUTH = {}                    # water's run token (rewrite stage 1): set when its server is imported; sewer ignores it
DROP = {"time", "modified", "mtime", "made", "version", "pid", "net_rev", "code_version", "stamp", "dpr_rates",
        "seconds"}


# --------------------------------------------------------------------------------------------- canonical outputs
class Canon:
    def __init__(self, tmp):
        self.tmp = [tmp, tmp.replace("\\", "/"), os.path.realpath(tmp), os.path.realpath(tmp).replace("\\", "/")]

    def text(self, s):
        for t in self.tmp:
            s = s.replace(t, "<TMP>")
        for rx, to in TS:
            s = rx.sub(to, s)
        return s

    def json(self, x):
        if isinstance(x, dict):
            return {k: self.json(v) for k, v in sorted(x.items()) if k not in DROP}
        if isinstance(x, (list, tuple)):
            return [self.json(v) for v in x]
        if isinstance(x, float):
            return float(f"{x:.9g}")
        if isinstance(x, str):
            return self.text(x)
        if isinstance(x, (datetime.date, datetime.datetime)):
            return "<DATE>"
        return x

    def xlsx(self, path):
        import openpyxl
        wb = openpyxl.load_workbook(path)
        out = {"sheets": wb.sheetnames}
        for ws in wb.worksheets:
            cells = {}
            for row in ws.iter_rows():
                for c in row:
                    if c.value is None:
                        continue
                    fill = c.fill.start_color.rgb if c.fill is not None and c.fill.fill_type == "solid" else None
                    cells[c.coordinate] = [self.json(c.value), c.number_format,
                                           fill if isinstance(fill, str) else None]
            out[ws.title] = cells
        return out

    def dxf(self, path):
        import ezdxf
        doc = ezdxf.readfile(path)
        ents = []
        for e in doc.modelspace():
            t = e.dxftype()
            d = {"t": t, "layer": e.dxf.layer}
            if t in ("TEXT", "MTEXT"):
                d["text"] = self.text(e.dxf.text if t == "TEXT" else e.text)
                d["at"] = [round(v, 3) for v in e.dxf.insert][:2]
            elif t == "LWPOLYLINE":
                d["pts"] = [[round(p[0], 3), round(p[1], 3)] for p in e.get_points("xy")]
            elif t == "LINE":
                d["pts"] = [[round(v, 3) for v in e.dxf.start][:2], [round(v, 3) for v in e.dxf.end][:2]]
            elif t == "CIRCLE":
                d["at"] = [round(v, 3) for v in e.dxf.center][:2]
                d["r"] = round(e.dxf.radius, 3)
            elif t == "INSERT":
                d["block"] = e.dxf.name
                d["at"] = [round(v, 3) for v in e.dxf.insert][:2]
            ents.append(d)
        ents.sort(key=lambda d: json.dumps(d, sort_keys=True))
        return {"layers": sorted(lay.dxf.name for lay in doc.layers), "entities": ents}


# ------------------------------------------------------------------------------------------------------ the run
class Run:
    def __init__(self, out, tmp):
        self.out, self.canon, self.n = out, Canon(tmp), 0
        self.times = []                                  # (the call, seconds): OUT_DIR + "_times.txt", not compared

    def call(self, url, body=None, raw=False):
        req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json", **AUTH})
        t0 = time.perf_counter()
        with urllib.request.urlopen(req, timeout=1800) as r:
            data = r.read()
        self.times.append((url.split("/api/", 1)[-1], time.perf_counter() - t0))
        return data if raw else json.loads(data)

    def keep(self, name, obj):
        self.n += 1
        with open(os.path.join(self.out, f"{self.n:02d}_{name}.json"), "w", encoding="utf-8") as fh:
            json.dump(obj, fh, ensure_ascii=False, indent=0, sort_keys=True)

    def answer(self, name, r):
        self.keep(name, self.canon.json(r))
        return r

    def files(self, name, paths):
        for k, p in sorted(paths.items()):
            if not p or not isinstance(p, str) or not os.path.isfile(p):
                continue
            if p.endswith(".xlsx"):
                self.keep(f"{name}_{k}_xlsx", self.canon.xlsx(p))
            elif p.endswith(".dxf"):
                self.keep(f"{name}_{k}_dxf", self.canon.dxf(p))
            elif p.endswith(".pdf"):
                import re as _re
                with open(p, "rb") as fh:
                    pages = len(_re.findall(rb"/Type\s*/Page[^s]", fh.read()))
                self.keep(f"{name}_{k}_pdf", {"pages": pages})


def serve(handler):
    from http.server import ThreadingHTTPServer
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def water(R, url, tmp):
    with open(SAMPLE, encoding="utf-8") as fh:
        kml = fh.read()
    w = url + "/api/"
    # 1. the KML layout, the OHT on the highest ground, zoning, design, both DXFs, DPR, rate xlsx
    r = R.answer("w1_layout", R.call(w + "layout", {"name": "wg", "kml": kml, "gl_mode": "spots", "snap": 1, "spacing": 100}))
    m = max(r["manholes"], key=lambda x: x["gl"] or 0)
    oht = {"name": "OHT-1", "lat": m["latlng"][0], "lng": m["latlng"][1], "capacity_kl": "", "staging_m": 22,
           "tubewells": 4}
    R.answer("w1_zoning", R.call(w + "water_zoning", {"name": "wg", "ohts": [oht], "pop_factor": 1.5}))
    R.files("w1_zoning_dxf", {"dxf": R.call(w + "water_export", {"name": "wg", "what": "zoning"}).get("path")})
    d = R.answer("w1_design", R.call(w + "water_design", {"name": "wg", "ohts": [oht], "pop_factor": 1.5}))
    R.files("w1_design", d.get("files") or {})
    R.files("w1_design_dxf", {"dxf": R.call(w + "water_export", {"name": "wg", "what": "design"}).get("path")})
    R.files("w1_dpr", {"dpr": R.call(w + "water_dpr", {"name": "wg"}).get("path")})
    rx = R.answer("w1_rates", R.call(w + "water_rates", {"act": "export", "name": "wg"}))
    R.files("w1_rates", {"xlsx": rx.get("path")})
    R.answer("w1_last", R.call(url + "/api/water_last?name=wg"))
    # 2. an existing OHT in a corner (new ones proposed), stages, tube wells, Intze drawings of a new tank
    c = min(r["manholes"], key=lambda x: x["latlng"][0] + x["latlng"][1])
    old = {"name": "OLD-1", "lat": c["latlng"][0], "lng": c["latlng"][1], "capacity_kl": 300, "staging_m": 22,
           "tubewells": 4, "rebore": 1}
    q = {"name": "wg", "ohts": [old], "pop_factor": 3, "base_year": 2027, "pop_initial": 20000, "pop_mid": 24000}
    R.answer("w2_zoning", R.call(w + "water_zoning", q))
    d = R.answer("w2_design", R.call(w + "water_design", q))
    R.files("w2_design", d.get("files") or {})
    R.files("w2_dpr", {"dpr": R.call(w + "water_dpr", {"name": "wg"}).get("path")})
    tanks = R.answer("w2_intze_list", R.call(w + "water_intze_list", {"name": "wg"}))
    new = [t for t in tanks.get("ohts") or [] if t.get("name")]
    if new:
        iz = R.answer("w2_intze", R.call(w + "water_intze", {"name": "wg", "oht": new[0]["name"]}))
        for o in iz.get("ohts") or []:                 # file names in the answer's folder
            R.files(f"w2_intze_{o['name']}", {k: os.path.join(iz["folder"], f) for k, f in (o.get("files") or {}).items()})
    # 3. the tests' small DXF network, a total population, an existing OHT
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    from test_dxf_extract import make_dxf
    src = os.path.join(tmp, "small.dxf")
    make_dxf(src)
    with open(src, "rb") as fh:
        req = urllib.request.Request(w + "dxf_upload?file=small.dxf", data=fh.read(),
                                     headers={"Content-Type": "application/octet-stream", **AUTH})
        with urllib.request.urlopen(req, timeout=120) as resp:
            path = json.loads(resp.read())["path"]
    d = R.answer("w3_import", R.call(w + "dxf_import", {"path": path, "name": "ws", "pipe_layers": ["PIPE"],
                                                        "mh_layers": ["MH"], "level_layers": ["GL"], "epsg": "local"}))
    R.answer("w3_save", R.call(w + "net_save", {"name": "ws"}))
    a = d["nodes"]["MH-1"]["latlng"]
    o3 = {"name": "Ex-OHT-1", "lat": a[0], "lng": a[1], "existing": "1", "capacity_kl": 200, "staging_m": 20}
    q3 = {"name": "ws", "ohts": [o3], "pop_factor": 1, "pop_total": 1500}
    R.answer("w3_zoning", R.call(w + "water_zoning", q3))
    d = R.answer("w3_design", R.call(w + "water_design", q3))
    R.files("w3_design", d.get("files") or {})
    R.files("w3_dpr", {"dpr": R.call(w + "water_dpr", {"name": "ws"}).get("path")})
    # 4. a barrier line (railway) between two junction columns, then a crossing at its first cut; design, DXF, DPR
    wb_ = R.call(w + "layout", {"name": "wb", "kml": kml, "gl_mode": "spots", "snap": 1, "spacing": 100})
    lats = sorted(m["latlng"][0] for m in wb_["manholes"])
    lngs = sorted({m["latlng"][1] for m in wb_["manholes"]})
    mid = (lngs[len(lngs) // 2] + lngs[len(lngs) // 2 + 1]) / 2
    bar = {"name": "Railway 1", "type": "railway", "latlngs": [[lats[0] - 0.01, mid], [lats[-1] + 0.01, mid]]}
    qb = {"name": "wb", "ohts": [], "pop_factor": 3, "barriers": [bar]}
    z = R.answer("w4_zoning_barrier", R.call(w + "water_zoning", qb))
    cut = (z.get("cuts") or [{}])[0]
    if cut.get("latlng"):
        xing = {"name": "Bridge", "latlngs": [[cut["latlng"][0], mid - 0.0002], [cut["latlng"][0], mid + 0.0002]]}
        qb = dict(qb, crossings=[xing])
        R.answer("w4_zoning_crossing", R.call(w + "water_zoning", qb))
    d = R.answer("w4_design", R.call(w + "water_design", qb))
    R.files("w4_design", d.get("files") or {})
    R.files("w4_design_dxf", {"dxf": R.call(w + "water_export", {"name": "wb", "what": "design"}).get("path")})
    R.files("w4_dpr", {"dpr": R.call(w + "water_dpr", {"name": "wb"}).get("path")})
    # 5. a zone loop over the west part (kept as its own OZ), zoning and design
    ring = [[lats[0] - 0.001, lngs[0] - 0.001], [lats[-1] + 0.001, lngs[0] - 0.001], [lats[-1] + 0.001, mid],
            [lats[0] - 0.001, mid]]
    ql = {"name": "wb", "ohts": [], "pop_factor": 5, "loops": [{"name": "Ward A", "latlngs": ring, "on_limit": "keep"}]}
    R.answer("w5_zoning_loop", R.call(w + "water_zoning", ql))
    d = R.answer("w5_design_loop", R.call(w + "water_design", ql))
    R.files("w5_design", d.get("files") or {})
    water_more(R, url, w, kml, path)
    R.answer("w_projects", R.call(url + "/api/projects"))


def _outputs(r):
    """The Outputs tab's answer, kept as the set of its file names (timestamps masked): a file's size changes with
    the zip times inside an xlsx, and two runs in one minute share a name."""
    names = sorted({_mask(str(f.get("file") or f.get("name") or "")) for f in r.get("files") or []})
    return dict({k: v for k, v in r.items() if k != "files"}, files=names)


def water_more(R, url, w, kml, path):
    """Stage 0 of the rewrite (26-Nov-2026): the calls the scenarios above did not make - saved projects and lists,
    the DXF dialog's calls, network corrections, simulation, the map export, rate import / reset, the outputs."""
    R.answer("w6_save", R.call(w + "save", {"name": "wk", "kml": kml}))
    R.answer("w6_project", R.call(url + "/api/project?name=wk"))
    R.answer("w6_list_save", R.call(w + "barriers_save", {"name": "wk", "barriers": [{"name": "B", "latlngs": [[1, 2], [3, 4]]}]}))
    R.answer("w6_list", R.call(url + "/api/barriers?name=wk"))
    R.answer("w6_layers", R.call(w + "dxf_layers", {"path": path}))
    R.answer("w6_preview", R.call(w + "dxf_preview", {"path": path, "layer": "PIPE", "epsg": "local"}))
    R.answer("w6_gl_options", R.call(w + "dxf_gl_options", {"path": path, "pipe_layers": ["PIPE"], "mh_layers": ["MH"]}))
    R.answer("w6_netpreview", R.call(w + "dxf_netpreview", {"path": path, "pipe_layers": ["PIPE"], "mh_layers": ["MH"],
                                                            "level_layers": ["GL"], "epsg": "local"}))
    R.answer("w6_missing", R.call(w + "dxf_layers", {"path": path + ".none"}))
    R.answer("w6_net", R.call(url + "/api/net?name=ws"))
    R.answer("w6_edit", R.call(w + "net_edit", {"name": "ws", "ops": [{"op": "set_gl", "mh": "MH-3", "gl": 85.05}]}))
    R.answer("w6_edit_bad", R.call(w + "net_edit", {"name": "ws", "ops": [{"op": "rename", "mh": "MH-6", "to": "MH-1"}]}))
    R.answer("w6_undo", R.call(w + "net_undo", {"name": "ws"}))
    R.answer("w6_repair", R.call(w + "net_repair", {"name": "ws"}))
    R.answer("w6_sim_info", R.call(url + "/api/water_sim_info?name=wg"))
    R.answer("w6_sim_ssa", R.call(w + "water_sim", {"name": "wg", "mode": "ssa"}))
    R.answer("w6_sim_eps", R.call(w + "water_sim", {"name": "wg", "mode": "eps"}))
    m = R.call(w + "water_map", {"name": "wg", "fmt": "kml"})
    m.pop("b64", None)
    R.answer("w6_map", m)
    rx = R.call(w + "water_rates", {"act": "export", "name": "wg"})
    import base64
    with open(rx["path"], "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode("ascii")
    R.answer("w6_rates_import", R.call(w + "water_rates", {"act": "import", "file": "rates.xlsx", "b64": b64}))
    R.answer("w6_rates_status", R.call(w + "water_rates", {"act": "status"}))
    R.answer("w6_rates_reset", R.call(w + "water_rates", {"act": "reset"}))
    R.answer("w6_outputs", _outputs(R.call(url + "/api/outputs?name=wg")))


def sewer_more(R, url, s, kml, tmp):
    """Stage 0 of the rewrite (26-Nov-2026): sewer from the tests' small DXF, saved projects and lists, the DXF
    dialog's calls, network corrections, the outputs."""
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    from test_dxf_extract import make_dxf
    src = os.path.join(tmp, "small_s.dxf")
    make_dxf(src)
    with open(src, "rb") as fh:
        req = urllib.request.Request(s + "dxf_upload?file=small_s.dxf", data=fh.read(),
                                     headers={"Content-Type": "application/octet-stream", **AUTH})
        with urllib.request.urlopen(req, timeout=120) as resp:
            path = json.loads(resp.read())["path"]
    R.answer("s4_layers", R.call(s + "dxf_layers", {"path": path}))
    R.answer("s4_preview", R.call(s + "dxf_preview", {"path": path, "layer": "PIPE", "epsg": "local"}))
    R.answer("s4_netpreview", R.call(s + "dxf_netpreview", {"path": path, "pipe_layers": ["PIPE"], "mh_layers": ["MH"],
                                                            "level_layers": ["GL"], "epsg": "local"}))
    R.answer("s4_import", R.call(s + "dxf_import", {"path": path, "name": "ss", "pipe_layers": ["PIPE"],
                                                    "mh_layers": ["MH"], "level_layers": ["GL"], "epsg": "local"}))
    R.answer("s4_edit", R.call(s + "net_edit", {"name": "ss", "ops": [{"op": "outfall", "mh": "MH-5", "on": True}]}))
    R.answer("s4_undo", R.call(s + "net_undo", {"name": "ss"}))
    R.answer("s4_edit2", R.call(s + "net_edit", {"name": "ss", "ops": [{"op": "outfall", "mh": "MH-5", "on": True}]}))
    R.answer("s4_repair", R.call(s + "net_repair", {"name": "ss"}))
    R.answer("s4_save", R.call(s + "net_save", {"name": "ss"}))
    R.answer("s4_net", R.call(url + "/api/net?name=ss"))
    q = {"name": "ss", "stp": "MH-5", "sewage_lpcd": 108, "start_depth": 0.7}
    z = R.answer("s4_zoning", R.call(s + "zoning", q))
    if z.get("options"):
        d = R.answer("s4_design", R.call(s + "design", dict(q, option=z["options"][0]["option"])))
        R.files("s4_design", d.get("files") or {})
    R.answer("s4_ksave", R.call(s + "save", {"name": "sk", "kml": kml}))
    R.answer("s4_project", R.call(url + "/api/project?name=sk"))
    R.answer("s4_list_save", R.call(s + "loops_save", {"name": "sk", "loops": [{"name": "L", "latlngs": [[1, 2], [3, 4], [5, 6]]}]}))
    R.answer("s4_list", R.call(url + "/api/loops?name=sk"))
    R.answer("s4_outputs", _outputs(R.call(url + "/api/outputs?name=sg")))


def _paths(x):
    """Every existing .xlsx / .dxf path in an answer."""
    if isinstance(x, dict):
        return {p for v in x.values() for p in _paths(v)}
    if isinstance(x, list):
        return {p for v in x for p in _paths(v)}
    if isinstance(x, str) and x.endswith((".xlsx", ".dxf")) and os.path.isfile(x):
        return {x}
    return set()


def sewer(R, url, tmp):
    with open(SAMPLE, encoding="utf-8") as fh:
        kml = fh.read()
    s = url + "/api/"
    R.answer("s1_layout", R.call(s + "layout", {"name": "sg", "kml": kml}))
    cats = R.answer("s1_catalogs", R.call(s + "catalogs"))["catalogs"]
    req = {"name": "sg", "stp": "MH-17", "catalog": cats[0]["name"], "joint": "ss", "sewage_lpcd": 108,
           "start_depth": 0.7}
    z = R.answer("s1_zoning", R.call(s + "zoning", req))
    R.files("s1_zoning", z.get("files") or {})
    for o in z["options"][:2]:
        d = R.answer(f"s1_design_{o['option']}", R.call(s + "design", dict(req, option=o["option"])))
        R.files(f"s1_design_{o['option']}", d.get("files") or {})
        e = R.answer(f"s1_zexport_{o['option']}", R.call(s + "zoning_export", {"name": "sg", "option": o["option"]}))
        for k, f in enumerate(sorted(_paths(e))):
            R.files(f"s1_zexport_{o['option']}_{k}", {"f": f})
    R.answer("s1_last", R.call(url + "/api/last_results?name=sg"))
    # 2. a barrier line (highway) between two manhole columns: zoning, design of the first option, its export
    lay = R.call(s + "layout", {"name": "sb", "kml": kml})
    lats = sorted(m["latlng"][0] for m in lay["manholes"])
    lngs = sorted({m["latlng"][1] for m in lay["manholes"]})
    mid = (lngs[len(lngs) // 2] + lngs[len(lngs) // 2 + 1]) / 2
    bar = {"name": "NH-19", "type": "highway", "latlngs": [[lats[0] - 0.01, mid], [lats[-1] + 0.01, mid]]}
    qb = {"name": "sb", "stp": "MH-17", "sewage_lpcd": 108, "start_depth": 0.7, "barriers": [bar]}
    z = R.answer("s2_zoning_barrier", R.call(s + "zoning", qb))
    o = z["options"][0]["option"]
    d = R.answer("s2_design_barrier", R.call(s + "design", dict(qb, option=o)))
    R.files("s2_design", d.get("files") or {})
    e = R.answer("s2_zexport", R.call(s + "zoning_export", {"name": "sb", "option": o}))
    for k, f in enumerate(sorted(_paths(e))):
        R.files(f"s2_zexport_{k}", {"f": f})
    # 3. a zone loop over the west third: its own outlet
    lats = sorted({m["latlng"][0] for m in lay["manholes"]})
    mid = (lngs[len(lngs) // 3] + lngs[len(lngs) // 3 + 1]) / 2
    ring = [[lats[0] - 0.001, lngs[0] - 0.001], [lats[-1] + 0.001, lngs[0] - 0.001], [lats[-1] + 0.001, mid],
            [lats[0] - 0.001, mid]]
    ql = {"name": "sb", "stp": "MH-17", "sewage_lpcd": 108, "start_depth": 0.7,
          "loops": [{"name": "Ward A", "latlngs": ring}]}
    R.answer("s3_zoning_loop", R.call(s + "zoning", ql))
    d = R.answer("s3_design_loop", R.call(s + "design", dict(ql, option="CURRENT")))
    R.files("s3_design", d.get("files") or {})
    sewer_more(R, url, s, kml, tmp)
    R.answer("s_projects", R.call(url + "/api/projects"))


def snap(out):
    tmp = tempfile.mkdtemp(prefix="golden_")
    os.environ["WATER_APP_HOME"] = os.path.join(tmp, "Water")
    os.environ["SEWER_APP_HOME"] = os.path.join(tmp, "Sewer")
    os.startfile = lambda *a, **k: None                       # Export DPR / rates: nothing opened on the screen
    sys.path.insert(0, ROOT)
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    from sewer_app.web import server as sui
    from water_app.web import server as wsrv
    # the run tokens (rewrite stages 1-2): one value for both servers here, as the calls go through one helper
    if hasattr(sui, "TOKEN"):
        sui.TOKEN = getattr(wsrv, "TOKEN", sui.TOKEN)
    AUTH.update({getattr(wsrv, "TOKEN_HEADER", "X-App-Token"): getattr(wsrv, "TOKEN", "")})
    R = Run(out, tmp)
    wsv, wurl = serve(wsrv.Handler)
    ssv, surl = serve(sui.Handler)
    try:
        water(R, wurl, tmp)
        sewer(R, surl, tmp)
    finally:
        wsv.shutdown()
        ssv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    with open(out.rstrip("/\\") + "_times.txt", "w", encoding="utf-8") as fh:
        for k, s in R.times:
            fh.write(f"{s:8.2f}  {k}\n")
        fh.write(f"{sum(s for _, s in R.times):8.2f}  total\n")
    print(f"{R.n} outputs in {out}")


def _mask(s):
    for rx, to in TS:
        s = rx.sub(to, s)
    return s


def _walk(a, b, path, out, limit=25):
    if len(out) >= limit:
        return
    if type(a) is not type(b):
        out.append(f"{path}: {str(a)[:120]!r} -> {str(b)[:120]!r}")
    elif isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(f"{path}/{k}: {'only new' if k not in a else 'only old'}")
            else:
                _walk(a[k], b[k], f"{path}/{k}", out, limit)
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append(f"{path}: {len(a)} items -> {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            _walk(x, y, f"{path}[{i}]", out, limit)
    elif isinstance(a, str) and _mask(a) == _mask(b):
        return                                          # (a mask added after the older snapshot was taken)
    elif a != b:
        out.append(f"{path}: {str(a)[:120]!r} -> {str(b)[:120]!r}")


def diff(old, new):
    fa, fb = sorted(os.listdir(old)), sorted(os.listdir(new))
    bad = 0
    for f in sorted(set(fa) | set(fb)):
        if f not in fa or f not in fb:
            print(f"{f}: {'only in new' if f not in fa else 'only in old'}")
            bad += 1
            continue
        with open(os.path.join(old, f), encoding="utf-8") as h1, open(os.path.join(new, f), encoding="utf-8") as h2:
            a, b = json.load(h1), json.load(h2)
        out = []
        _walk(a, b, "", out)
        if out:
            bad += 1
            print(f"== {f}")
            for x in out:
                print("  " + x)
    print(f"{len(set(fa) | set(fb))} outputs, {bad} different")
    return bad


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "snap":
        snap(sys.argv[2])
    elif len(sys.argv) == 4 and sys.argv[1] == "diff":
        sys.exit(1 if diff(sys.argv[2], sys.argv[3]) else 0)
    else:
        print(__doc__)
        sys.exit(2)
