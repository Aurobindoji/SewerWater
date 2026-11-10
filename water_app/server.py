"""The water module's map page on its own server (isolation of sewer and water, user request 21-Oct-2026): its own
page (water_app/static/map.html), projects (water_app/projects) and results (water_app/output); the network tools are
water_app's own copies. Nothing of sewer_app is imported.

    .venv\\Scripts\\python -m water_app ui                 # http://127.0.0.1:8766/water
"""
import collections
import contextlib
import csv
import io
import json
import os
import re
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import HOME

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
PROJECTS = os.path.join(HOME, "projects")
OUT_ROOT = os.path.join(HOME, "output")
MAX_BODY = 30 * 1024 * 1024
MAX_DXF = 1024 * 1024 * 1024        # a DXF picked on the page (uploaded as it is, to projects\\dxf\\)
PORT = 8766
SEWER_START = "http://127.0.0.1:8765/"   # the start page (language, module) is the sewer server's


def proj_dir():
    return PROJECTS


def out_root():
    return OUT_ROOT


def code_version():
    """Changes when any .py file of water_app changes: a running server with other code is an old one."""
    import glob
    import hashlib
    here = os.path.dirname(os.path.abspath(__file__))
    h = hashlib.md5()
    for f in sorted(glob.glob(os.path.join(here, "*.py"))):
        h.update(f"{os.path.basename(f)}:{os.path.getmtime(f)}".encode())
    return h.hexdigest()[:12]


VERSION = code_version()


def safe_name(name):
    """A project name usable as a file name: letters (incl. Hindi with its vowel signs), digits, _ - (anything
    else -> _)."""
    import unicodedata
    s = "".join(c if c.isalnum() or c in "_-" or unicodedata.category(c).startswith("M") else " "
                for c in str(name or "").strip())
    s = re.sub(r"\s+", "_", s.strip())
    return s[:80] or "project"


def save_project(name, kml):
    os.makedirs(proj_dir(), exist_ok=True)
    path = os.path.join(proj_dir(), safe_name(name) + ".kml")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(kml)
    return path


def kmz_to_kml(data):
    """The first .kml inside a KMZ (zip) as text."""
    import zipfile
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        name = next((n for n in z.namelist() if n.lower().endswith(".kml")), None)
        if not name:
            raise ValueError("no .kml inside the KMZ")
        return z.read(name).decode("utf-8", errors="replace")


def list_projects():
    """Projects: drawn on the map (projects\\<name>.kml) and networks read from a DXF (projects\\<name>.dxf.json)."""
    if not os.path.isdir(proj_dir()):
        return []
    out = []
    for f in sorted(os.listdir(proj_dir())):
        if f.lower().endswith(".kml"):
            out.append({"name": f[:-4], "kind": "kml", "modified": os.path.getmtime(os.path.join(proj_dir(), f))})
        elif f.lower().endswith(".dxf.json"):
            out.append({"name": f[:-9], "kind": "dxf", "modified": os.path.getmtime(os.path.join(proj_dir(), f))})
    return sorted(out, key=lambda r: -r["modified"])


def is_dxf(stem):
    return os.path.isfile(os.path.join(proj_dir(), stem + ".dxf.json"))


NETS = {}                       # stem -> working state of netedit (kept in memory between the edits)


def net_state(stem):
    from . import netedit
    st = NETS.get(stem)
    if st is None:
        st = netedit.load(out_root(), stem)
        if st is None:
            raise ValueError(f"'{stem}': DXF network नहीं मिला")
        NETS[stem] = st
    return st


def net_import(req):
    from . import netedit
    path = str(req.get("path") or "").strip().strip('"')
    if not os.path.isfile(path):
        return {"ok": False, "log": f"file नहीं मिली: {path}"}
    stem = safe_name(req.get("name") or os.path.splitext(os.path.basename(path))[0])
    pipes = [x for x in req.get("pipe_layers") or [] if x]
    if not pipes:
        return {"ok": False, "log": "कम से कम एक pipe layer चुनें"}
    lines = []
    try:
        epsg = req.get("epsg")
        zm = req.get("z_mode") if req.get("z_mode") in ("auto", "first", "off") else "auto"   # Z of the line ends
        st = netedit.import_dxf(out_root(), stem, path, pipes, req.get("mh_layers") or [], req.get("level_layers") or [],
                                int(epsg) if epsg not in (None, "", "local") else None, log=lines.append, z_mode=zm,
                                node_prefix=name_prefix(req.get("node_prefix"), "J-"),
                                pipe_prefix=name_prefix(req.get("pipe_prefix"), "P-"))
    except Exception as e:
        return {"ok": False, "log": "\n".join(lines) + f"\n{type(e).__name__}: {e}"}
    NETS[stem] = st
    os.makedirs(proj_dir(), exist_ok=True)
    with open(os.path.join(proj_dir(), stem + ".dxf.json"), "w", encoding="utf-8") as fh:
        json.dump({"kind": "dxf", "dxf": path, "state": netedit.state_path(out_root(), stem)}, fh, ensure_ascii=False)
    out = netedit.page_data(st)
    out["log"] = "\n".join(lines)
    return out


def net_call(path, req, query):
    """The /api/net... calls of the page for a DXF network."""
    from . import netedit
    stem = safe_name(req.get("name") or (query.get("name") or [""])[0])
    try:
        st = net_state(stem)
        if path == "/api/net":
            return netedit.page_data(st)
        if path == "/api/net_texts":
            bb = [float((query.get(k) or ["0"])[0]) for k in ("s", "w", "n", "e")]
            hide = (query.get("hide") or ["0"])[0] == "1"     # the page writes the junction names / GLs itself
            return {"ok": True, "texts": netedit.texts_in(st, bb, hide_shown=hide)}
        if path == "/api/net_edit":
            touched = netedit.apply(st, req.get("ops") or [])
            return netedit.page_data(st, full=False, touched=touched)
        if path == "/api/net_undo":
            netedit.undo(st)
            return netedit.page_data(st)
        if path == "/api/net_repair":
            # a water main network keeps its loops (they are wanted there)
            rows = netedit.auto_repair(st, float(req.get("join_gap_m") or 1.0), float(req.get("tjoint_m") or 0.5),
                                       bool(req.get("loops", False)), bool(req.get("gl", True)))
            out = netedit.page_data(st)
            cnt = collections.Counter(r["repair"] for r in rows)
            out["log"] = "अपने-आप सुधार: " + (", ".join(f"{k} {v}" for k, v in cnt.most_common()) or "कुछ नहीं मिला")
            return out
        if path == "/api/net_place":
            moved = netedit.place(st, req["from"], req["to"], req.get("points") or [])
            return dict(netedit.page_data(st), points=moved)
        if path == "/api/net_save":
            files = netedit.save_network(st)
            files.pop("unchanged", False)
            return {"ok": True, "files": files, "outfalls": st["net"]["outfalls"]}
    except ValueError as e:
        return {"ok": False, "log": str(e)}
    except Exception as e:
        return {"ok": False, "log": f"{type(e).__name__}: {e}"}
    return {"ok": False, "log": "not found"}


PREFIX_RE = re.compile(r"[A-Za-z][A-Za-z0-9_/-]{0,7}")


def name_prefix(v, default):
    """A prefix of the junction / pipe names chosen on the page (user request 30-Oct-2026: N-, J-, M-, MH-, P-, CO- ...):
    a letter, then letters / digits / - _ /, up to 8; anything else (or nothing): the module's own."""
    v = str(v or "").strip()
    return v if PREFIX_RE.fullmatch(v) else default


def run_layout(name, kml, gl_mode="spots", flat_gl=None, snap=1.0, spacing=30.0, bend_nodes=False, node_prefix=None,
               pipe_prefix=None):
    """Save the KML, run 'layout' on it (roads, boundary, wards and spot levels all from that one file) and return
    {ok, log, files, manholes, conduits, marks} with the network in lon / lat for the map."""
    from . import geo, network
    from .layout_cmd import cmd_layout
    stem = safe_name(name)
    path = save_project(stem, kml)
    folder = os.path.join(out_root(), stem)
    os.makedirs(folder, exist_ok=True)
    args = ["--roads-kml", path, "--population-kml", path, "--out", folder,
            "--snap", f"{float(snap):g}",
            # spacing 0 (water): nodes only at the road junctions and ends - no node in the middle of a pipe
            "--spacing", f"{float(spacing):g}" if float(spacing or 0) > 0 else "1000000"] + \
        ([] if bend_nodes else ["--no-bend-nodes"]) + \
        ["--node-prefix", name_prefix(node_prefix, "J-"), "--pipe-prefix", name_prefix(pipe_prefix, "P-")]
    # the boundary only from its own folder / name: 'layout' takes the largest polygon of --boundary-kml, which in
    # this file could be a ward
    k = geo.read_kml(path)
    bnd = [f for f in k["polygons"] if len(f["coords"]) >= 3
           and re.search(r"boundary|सीमा", f"{f.get('folder') or ''} {f.get('name') or ''}", re.I)]
    wards_as_boundary = not bnd
    if not bnd:              # no project boundary: the wards together are the project area (each ward its own boundary)
        bnd = [f for f in k["polygons"] if len(f["coords"]) >= 3]
    if bnd:
        f_b = os.path.join(folder, f"{stem}_boundary.kml")
        with open(f_b, "w", encoding="utf-8") as fh:
            fh.write('<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
                     + "".join("<Placemark><name>Project boundary</name><Polygon><outerBoundaryIs><LinearRing><coordinates>"
                               + " ".join(f"{c[0]},{c[1]},0" for c in f["coords"])
                               + "</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>" for f in bnd)
                     + "</Document></kml>\n")
        args += ["--boundary-kml", f_b] + (["--boundary-all"] if wards_as_boundary else [])
    if gl_mode == "flat":
        if flat_gl is None or flat_gl == "":
            return {"ok": False, "log": "समतल GL का मान दें (m)"}
        args += ["--flat-gl", f"{float(flat_gl):g}"]
    elif gl_mode == "spots":
        args += ["--levels-kml", path]
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            cmd_layout(args)
    except SystemExit as e:
        return {"ok": False, "log": buf.getvalue() + "\n" + str(e.code or "")}
    except Exception as e:                                    # shown on the page, not a server crash
        return {"ok": False, "log": buf.getvalue() + f"\n{type(e).__name__}: {e}"}
    text = buf.getvalue()
    marks = [{"name": m.group(1), "manhole": m.group(2), "dist": float(m.group(3))}
             for m in re.finditer(r"point '(.+?)' -> nearest manhole (\S+) \((\d+(?:\.\d+)?) m away\)", text)]
    with open(os.path.join(folder, f"{stem}_layout_ui.json"), "w", encoding="utf-8") as fh:
        json.dump({"marks": marks, "log": text}, fh, ensure_ascii=False)
    return layout_result(stem)


def _paths(stem):
    """(folder, manholes CSV, conduits CSV, population CSV) of the project's network: the layout made from the
    map, or the corrected DXF network ('सहेजें' of the network panel)."""
    folder = os.path.join(out_root(), stem)
    if is_dxf(stem):
        from . import netedit
        netedit.rename_old_names(out_root(), stem)      # CO- / MH-G of an old import -> P- / J-G, before any file is read
        return (folder, os.path.join(folder, f"{stem}_network_manholes.csv"),
                os.path.join(folder, f"{stem}_network_conduits.csv"), os.path.join(folder, f"{stem}_population.csv"))
    return (folder, os.path.join(folder, f"{stem}_layout_manholes.csv"),
            os.path.join(folder, f"{stem}_layout_conduits.csv"), os.path.join(folder, f"{stem}_layout_population.csv"))


def to_latlng(stem):
    """Function (x, y) in the layout's metres -> [lat, lon]: UTM zone of the project's first road point, as
    'layout' chose it."""
    from pyproj import Transformer
    from . import geo
    if is_dxf(stem):
        from . import netedit
        f = netedit.converters(net_state(stem))[0]
        return lambda xy: f([xy])[0]
    k = geo.read_kml(os.path.join(proj_dir(), stem + ".kml"))
    first = next((f["coords"][0] for f in k["lines"] if f["coords"]), None)
    if first is None:
        raise ValueError("no road in the project KML")
    t = Transformer.from_crs(geo.utm_epsg(first[0], first[1]), 4326, always_xy=True)

    def ll(xy):
        lon, lat = t.transform(xy[0], xy[1])
        return [round(lat, 7), round(lon, 7)]
    return ll


def converters_for(stem):
    """(to_ll([[x, y], ...]) -> [[lat, lon], ...], to_xy([[lat, lon], ...]) -> [[x, y], ...]) of the project."""
    from pyproj import Transformer
    from . import geo
    if is_dxf(stem):
        from . import netedit
        return netedit.converters(net_state(stem))
    k = geo.read_kml(os.path.join(proj_dir(), stem + ".kml"))
    first = next((f["coords"][0] for f in k["lines"] if f["coords"]), None)
    if first is None:
        raise ValueError("no road in the project KML")
    epsg = geo.utm_epsg(first[0], first[1])
    fwd = Transformer.from_crs(epsg, 4326, always_xy=True)
    inv = Transformer.from_crs(4326, epsg, always_xy=True)

    def to_ll(pts):
        if not pts:
            return []
        lon, lat = fwd.transform([p[0] for p in pts], [p[1] for p in pts])
        return [[round(a, 7), round(b, 7)] for a, b in zip(lat, lon)]

    def to_xy(pts):
        if not pts:
            return []
        x, y = inv.transform([p[1] for p in pts], [p[0] for p in pts])
        return [[round(a, 3), round(b, 3)] for a, b in zip(x, y)]
    return to_ll, to_xy


def layout_result(stem):
    """The layout already made for a project (CSV files of output\\<stem>\\) for the map, or {ok: False}."""
    from . import network
    folder, f_mh, f_co, f_pop = _paths(stem)
    if not (os.path.isfile(f_mh) and os.path.isfile(f_co)):
        return {"ok": False, "log": "इस project का layout अभी नहीं बना"}
    net = network.read_extract_csv(f_mh, f_co)
    pop = {}
    if os.path.isfile(f_pop):
        with open(f_pop, encoding="utf-8") as fh:
            pop = {r["Manhole"]: float(r["Population"]) for r in csv.DictReader(fh)}
    ll = to_latlng(stem)
    mhs = [{"label": n, "latlng": ll(v["xy"]), "gl": v["ground"], "pop": round(pop.get(n, 0.0), 1)}
           for n, v in net["nodes"].items() if v.get("xy")]
    conds = [{"label": c["label"], "from": c["start_node"], "to": c["stop_node"], "length": round(c["length_m"], 1),
              "pts": [ll(p) for p in (c.get("vertices") or [net["nodes"][c["start_node"]]["xy"],
                                                         net["nodes"][c["stop_node"]]["xy"]])]}
             for c in net["conduits"]]
    meta = {}
    f_ui = os.path.join(folder, f"{stem}_layout_ui.json")
    if os.path.isfile(f_ui):
        with open(f_ui, encoding="utf-8") as fh:
            meta = json.load(fh)
    files = {"manholes": f_mh, "conduits": f_co, "plan_dxf": os.path.join(folder, f"{stem}_layout.dxf"),
             "kml": os.path.join(proj_dir(), stem + ".kml")}
    if os.path.isfile(f_pop):
        files["population"] = f_pop
    return {"ok": True, "name": stem, "log": meta.get("log", ""), "files": files, "manholes": mhs, "conduits": conds,
            "marks": meta.get("marks", []), "folder": folder, "population": round(sum(pop.values()), 1)}


STAGE_KEYS = ("base_year", "pop_initial", "pop_mid")


def stage_inputs(req):
    """The stage-wise check of the page (CPHEEO Table 2.1, p2-9): base year and the total population of the base
    year and of +15 years; the design population is that of +30 years. Empty = no such stage."""
    out = {}
    for k in STAGE_KEYS:
        v = req.get(k)
        if v in (None, ""):
            continue
        v = float(v)
        if k == "base_year":
            if not 1900 <= v <= 2200:
                raise ValueError("आधार वर्ष 1900 से 2200 के बीच दें")
            out[k] = int(v)
        elif v <= 0:
            raise ValueError("stage की आबादी 0 से अधिक दें (या खाली छोड़ें)")
        else:
            out[k] = v
    return out


def network_current(stem):
    """A DXF network: no edit since its last 'सहेजें' (zoning / design are of the saved one). A layout: True."""
    if not is_dxf(stem):
        return True
    st = net_state(stem)
    if "saved_edits" in st:
        return st["saved_edits"] == len(st["edits"])
    from datetime import datetime                   # saved before 'saved_edits' was kept: compare the times
    try:
        t_save = datetime.strptime(st["saved"], "%d-%m-%Y %H:%M")
        return not st["edits"] or datetime.strptime(st["edits"][-1]["time"][:16], "%d-%m-%Y %H:%M") <= t_save
    except (KeyError, ValueError):
        return False


def has_network(stem):
    """A network to zone / design: the DXF network being corrected on the map, or the layout made."""
    if is_dxf(stem):
        try:
            net_state(stem)
            return True
        except ValueError:
            return False
    return os.path.isfile(_paths(stem)[1])


def project_net(stem):
    """The network zoning / design work on (user decision 19-Oct-2026: no 'सहेजें' needed first - the network can be
    tried as it is edited): a DXF network as it is NOW in the map's working state (unsaved changes too); a layout
    from its CSV files."""
    from . import netedit, network
    if is_dxf(stem):
        net = netedit._tuples(net_state(stem)["net"])
        return {"nodes": {n: {"ground": v.get("ground"), "xy": v.get("xy"), "gl_source": str(v.get("gl_source") or "")}
                          for n, v in net["nodes"].items()},
                "conduits": [{"label": k["label"], "start_node": k["start_node"], "stop_node": k["stop_node"],
                              "length_m": k.get("length_m"), "vertices": k.get("vertices") or [],
                              "no_conn": bool(k.get("no_conn"))}
                             for k in net["conduits"]],
                "outfalls": []}
    _, f_mh, f_co, _ = _paths(stem)
    if not os.path.isfile(f_mh):
        raise ValueError("पहले Layout बनाएँ")
    return network.read_extract_csv(f_mh, f_co)


def net_rev(stem):
    """Which network a zoning / design was made from: a DXF network - its changes so far (count and the last one's
    time); a layout - the time of its files."""
    if is_dxf(stem):
        st = net_state(stem)
        e = st["edits"]
        return f"dxf:{len(e)}:{e[-1]['time'] if e else ''}:{len(st['net']['nodes'])}:{len(st['net']['conduits'])}"
    f_mh = _paths(stem)[1]
    return f"layout:{os.path.getmtime(f_mh):.3f}" if os.path.isfile(f_mh) else ""


def _ring_area(r):
    return sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(r, r[1:] + r[:1])) / 2.0


def _inside(p, ring):
    x, y = p
    c = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            c = not c
    return c


def _interior(ring, n=14):
    """A point well inside a (possibly concave) ring: of a grid over its box, the inside point farthest from the
    ring's vertices."""
    xs, ys = [p[0] for p in ring], [p[1] for p in ring]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    step = max(len(ring) // 300, 1)
    verts = ring[::step]
    best, bd = None, -1.0
    for i in range(1, n):
        for j in range(1, n):
            p = (x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * j / n)
            if _inside(p, ring):
                d = min((p[0] - v[0]) ** 2 + (p[1] - v[1]) ** 2 for v in verts)
                if d > bd:
                    best, bd = p, d
    return best or (sum(xs) / len(xs), sum(ys) / len(ys))


class Handler(BaseHTTPRequestHandler):
    server_version = "water_app_ui"

    def log_message(self, fmt, *args):                       # quiet console
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _local_only(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        if host not in ("127.0.0.1", "localhost"):
            self._send(403, {"ok": False, "log": "local use only"})
            return False
        return True

    def _route(self):
        """The request's path; the page calls /api/w/... (as when one server had both modules) - the same as /api/..."""
        u = urlparse(self.path)
        if u.path.startswith("/api/w/"):
            u = u._replace(path="/api/" + u.path[len("/api/w/"):])
        return u

    def _dxf_upload(self, n):
        """The bytes of a DXF picked on the page -> projects/dxf/<its name>.dxf of the module; its path back."""
        u = self._route()
        fname = os.path.basename((parse_qs(u.query).get("file") or [""])[0])
        if not fname.lower().endswith(".dxf"):
            self.rfile.read(min(n, MAX_DXF))
            return self._send(400, {"ok": False, "log": "केवल .dxf file (DWG हो तो पहले AutoCAD में DXF में save करें)"})
        if n > MAX_DXF:
            return self._send(413, {"ok": False, "log": f"file बहुत बड़ी ({n / 1048576:.0f} MB)"})
        folder = os.path.join(proj_dir(), "dxf")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, safe_name(fname[:-4]) + ".dxf")
        left = n
        with open(path + ".part", "wb") as fh:
            while left > 0:
                chunk = self.rfile.read(min(left, 1 << 20))
                if not chunk:
                    break
                fh.write(chunk)
                left -= len(chunk)
        if left:
            os.remove(path + ".part")
            return self._send(400, {"ok": False, "log": "upload अधूरा रहा"})
        os.replace(path + ".part", path)
        return self._send(200, {"ok": True, "path": path, "mb": round(n / 1048576, 1)})

    def do_GET(self):
        if not self._local_only():
            return
        u = self._route()
        if u.path in ("/", "/index.html", "/sewer"):    # the start page / the sewer module: the sewer server's
            self.send_response(302)
            self.send_header("Location", SEWER_START + ("sewer" if u.path == "/sewer" else "") + (f"?{u.query}" if u.query else ""))
            self.end_headers()
            return
        pages = {"/water": "map.html", "/i18n.js": "i18n.js"}
        if u.path in pages:
            with open(os.path.join(STATIC, pages[u.path]), "rb") as fh:
                ctype = "text/javascript; charset=utf-8" if u.path.endswith(".js") else "text/html; charset=utf-8"
                return self._send(200, fh.read(), ctype)
        if u.path == "/api/version":
            return self._send(200, {"ok": True, "version": VERSION, "pid": os.getpid(),
                                    "page_age_s": round(time.time() - LAST_PING[0], 1) if LAST_PING[0] else None})
        if u.path in ("/api/ohts", "/api/barriers", "/api/loops", "/api/crossings", "/api/wards",
                      "/api/bulk", "/api/prv", "/api/tw"):   # a DXF network's own drawing
            kind = u.path.rsplit("/", 1)[1]
            f = os.path.join(proj_dir(), safe_name((parse_qs(u.query).get("name") or [""])[0]) + f".{kind}.json")
            items = []
            if os.path.isfile(f):
                with open(f, encoding="utf-8") as fh:
                    items = json.load(fh)
            return self._send(200, {"ok": True, kind: items})
        if u.path in ("/api/city_wards_list", "/api/city_wards"):   # the towns' ward lists kept (city_wards)
            from . import city_wards as cw
            try:
                if u.path == "/api/city_wards_list":
                    return self._send(200, {"ok": True, "cities": cw.cities()})
                return self._send(200, dict(cw.load((parse_qs(u.query).get("city") or [""])[0]), ok=True))
            except Exception as e:
                return self._send(200, {"ok": False, "log": f"{e}"})
        if u.path == "/api/ping":                        # an open page: "still here"
            LAST_PING[0] = time.time()
            return self._send(200, {"ok": True})
        if u.path == "/api/projects":
            return self._send(200, {"ok": True, "projects": list_projects()})
        if u.path == "/api/water_last":
            from . import ui_api
            name = safe_name((parse_qs(u.query).get("name") or [""])[0])
            try:
                return self._send(200, ui_api.last_results(name))
            except Exception as e:
                return self._send(200, {"ok": False, "log": f"{type(e).__name__}: {e}"})
        if u.path == "/api/layout_result":
            name = safe_name((parse_qs(u.query).get("name") or [""])[0])
            try:
                return self._send(200, layout_result(name))
            except Exception as e:
                return self._send(200, {"ok": False, "log": f"{type(e).__name__}: {e}"})
        if u.path in ("/api/net", "/api/net_texts"):
            with LOCK:
                return self._send(200, net_call(u.path, {}, parse_qs(u.query)))
        if u.path == "/api/project":
            name = safe_name((parse_qs(u.query).get("name") or [""])[0])
            if is_dxf(name):
                return self._send(200, {"ok": True, "name": name, "kind": "dxf"})
            path = os.path.join(proj_dir(), name + ".kml")
            if not os.path.isfile(path):
                return self._send(404, {"ok": False, "log": f"project '{name}' not found"})
            with open(path, encoding="utf-8") as fh:
                return self._send(200, {"ok": True, "name": name, "kml": fh.read()})
        self._send(404, {"ok": False, "log": "not found"})

    def do_POST(self):
        if not self._local_only():
            return
        n = int(self.headers.get("Content-Length") or 0)
        if urlparse(self.path).path in ("/api/dxf_upload", "/api/w/dxf_upload"):
            return self._dxf_upload(n)
        if n > MAX_BODY:
            return self._send(413, {"ok": False, "log": "too large"})
        try:
            req = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except ValueError:
            return self._send(400, {"ok": False, "log": "bad JSON"})
        u = self._route()
        if u.path in ("/api/ohts_save", "/api/barriers_save", "/api/loops_save", "/api/crossings_save",
                      "/api/wards_save", "/api/bulk_save", "/api/prv_save", "/api/tw_save"):   # kept
            kind = u.path.rsplit("/", 1)[1][:-len("_save")]
            os.makedirs(proj_dir(), exist_ok=True)
            with open(os.path.join(proj_dir(), safe_name(req.get("name")) + f".{kind}.json"), "w", encoding="utf-8") as fh:
                json.dump(req.get(kind) or [], fh, ensure_ascii=False)
            return self._send(200, {"ok": True})
        if u.path == "/api/save":
            path = save_project(req.get("name"), req.get("kml") or "")
            return self._send(200, {"ok": True, "path": path, "name": safe_name(req.get("name"))})
        if u.path == "/api/kmz":
            import base64
            try:
                return self._send(200, {"ok": True, "kml": kmz_to_kml(base64.b64decode(req.get("data") or ""))})
            except Exception as e:
                return self._send(200, {"ok": False, "log": f"KMZ not read: {e}"})
        if u.path == "/api/layout":
            with LOCK:
                res = run_layout(req.get("name"), req.get("kml") or "", req.get("gl_mode", "spots"),
                                 req.get("flat_gl"), req.get("snap", 1.0), req.get("spacing", 30.0),
                                 bend_nodes=False, node_prefix=req.get("node_prefix"), pipe_prefix=req.get("pipe_prefix"))
            return self._send(200, res)
        if u.path == "/api/dxf_preview":                 # one layer of the drawing on the map
            from . import netedit
            path = str(req.get("path") or "").strip().strip('"')
            if not os.path.isfile(path):
                return self._send(200, {"ok": False, "log": f"file नहीं मिली: {path}"})
            ep = req.get("epsg")
            try:
                return self._send(200, netedit.dxf_preview(path, str(req.get("layer") or ""),
                                                           int(ep) if ep not in (None, "", "local") else None))
            except Exception as e:
                return self._send(200, {"ok": False, "log": f"{type(e).__name__}: {e}"})
        if u.path == "/api/dxf_layers":
            from . import netedit
            path = str(req.get("path") or "").strip().strip('"')
            if not os.path.isfile(path):
                return self._send(200, {"ok": False, "log": f"file नहीं मिली: {path}"})
            try:
                rows, guess = netedit.dxf_layers(path, water=True)
            except Exception as e:
                return self._send(200, {"ok": False, "log": f"{type(e).__name__}: {e}"})
            return self._send(200, {"ok": True, "layers": rows, "guess": guess,
                                    "name": safe_name(os.path.splitext(os.path.basename(path))[0])})
        if u.path == "/api/dxf_gl_options":            # the layers the GL could come from, for the user to choose
            from . import dxf_extract
            path = str(req.get("path") or "").strip().strip('"')
            if not os.path.isfile(path):
                return self._send(200, {"ok": False, "log": f"file नहीं मिली: {path}"})
            try:
                res = dxf_extract.gl_options(path, [x for x in req.get("pipe_layers") or [] if x],
                                             [x for x in req.get("mh_layers") or [] if x])
            except Exception as e:
                res = {"ok": False, "log": f"{type(e).__name__}: {e}"}
            return self._send(200, res)
        if u.path == "/api/dxf_import":
            with LOCK:
                return self._send(200, net_import(req))
        if u.path in ("/api/net_edit", "/api/net_undo", "/api/net_repair", "/api/net_save", "/api/net_place"):
            with LOCK:
                return self._send(200, net_call(u.path, req, {}))
        if u.path == "/api/projection":                  # the population projection of the page, by method
            from . import ui_api
            try:
                f = ui_api.projection_of(req)
                return self._send(200, {"ok": True, "projection": f})
            except Exception as e:
                return self._send(200, {"ok": False, "log": f"{e}"})
        if u.path == "/api/ward_kml_table":              # the ward table from a KML of the wards (ui_api.ward_kml_table)
            from . import ui_api
            try:
                return self._send(200, dict(ui_api.ward_kml_table(req.get("kml") or ""), ok=True))
            except Exception as e:
                return self._send(200, {"ok": False, "log": f"{e}"})
        if u.path in ("/api/city_wards_import", "/api/city_wards_xlsx"):   # the town's wards (city_wards, 9-Nov-2026)
            from . import city_wards as cw
            try:
                if u.path == "/api/city_wards_xlsx":
                    return self._send(200, dict(cw.export_b64(req), ok=True))
                import base64
                fname = os.path.basename(str(req.get("file") or ""))
                d = cw.import_xlsx(base64.b64decode(req.get("b64") or ""), fname)
                keep = cw.save(d, fname)
                return self._send(200, dict(keep, ok=True, notes=d["notes"]))
            except Exception as e:
                return self._send(200, {"ok": False, "log": f"{e}" if isinstance(e, ValueError) else f"{type(e).__name__}: {e}"})
        if u.path == "/api/water_join_plan":            # the isolated pieces' joins, a preview (ui_api.join_plan)
            from . import ui_api
            with LOCK:
                try:
                    res = dict(ui_api.join_plan(req.get("name"), req), ok=True)
                except Exception as e:
                    res = {"ok": False, "log": f"{type(e).__name__}: {e}" if not isinstance(e, ValueError) else str(e)}
            return self._send(200, res)
        if u.path in ("/api/water_zoning", "/api/water_design"):
            from . import ui_api
            with LOCK:
                try:
                    res = (ui_api.run_zoning if u.path == "/api/water_zoning" else ui_api.run_design)(req.get("name"), req)
                except Exception as e:
                    res = {"ok": False, "log": f"{type(e).__name__}: {e}"}
            return self._send(200, res)
        if u.path in ("/api/water_intze", "/api/water_intze_list"):   # Intze OHT drawings (intze_api, 9-Nov-2026)
            from . import intze_api
            try:                                           # one tank by its button (10-Nov-2026); the list of them
                res = (intze_api.tanks(req.get("name")) if u.path.endswith("_list")
                       else intze_api.export_all(req.get("name"), req, only=req.get("oht") or None))
            except ValueError as e:
                res = {"ok": False, "log": str(e)}
            except Exception as e:
                res = {"ok": False, "log": f"{type(e).__name__}: {e}"}
            return self._send(200, res)
        if u.path == "/api/water_export":                # DXF of the last zoning and its design (wdxf)
            from . import wdxf
            with LOCK:
                try:
                    path, cnt = wdxf.export(safe_name(req.get("name")))
                    res = {"ok": True, "path": path, "folder": os.path.dirname(path), "counts": cnt}
                except ValueError as e:
                    res = {"ok": False, "log": str(e)}
                except Exception as e:
                    res = {"ok": False, "log": f"{type(e).__name__}: {e}"}
            return self._send(200, res)
        self._send(404, {"ok": False, "log": "not found"})


LOCK = threading.Lock()


# when an open page last said it is open (it pings every 30 s): a second start of the bat file opens no new tab then
LAST_PING = [0.0]


PAGE_OPEN_S = 150                    # a background tab's timers may run only once a minute


class Server(ThreadingHTTPServer):
    # on Windows SO_REUSEADDR lets a SECOND server take the same port silently (the page then talks to whichever
    # answers, maybe an old one) - so no reuse there: a second start finds the port busy
    allow_reuse_address = os.name != "nt"


def serve(port=PORT, open_browser=True):
    url = f"http://127.0.0.1:{port}/water"
    try:
        srv = Server(("127.0.0.1", port), Handler)
    except OSError:
        running = None
        try:
            import urllib.request
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/version", timeout=5) as r:
                running = json.loads(r.read())
        except Exception:
            pass
        if not running or running.get("version") != VERSION:
            pid = f" - process {running.get('pid')}" if running else ""
            print(f"\n*** इस port ({url}) पर water_app का पुराना version (या कोई और program) पहले से चल रहा है{pid}.\n"
                  f"*** नया code तभी चलेगा जब उसकी काली window बंद करें (या उसमें Ctrl+C), फिर यह file दोबारा चलाएँ.\n"
                  f"*** An older water_app (or another program) is already running on this port ({url}){pid}.\n"
                  f"*** Close its black window (or press Ctrl+C in it), then start this file again.\n")
            return None
        age = running.get("page_age_s")
        if age is not None and age < PAGE_OPEN_S:       # a page of it is open: that tab, not one more
            print(f"water_app map UI पहले से चल रहा है और browser में खुला है: {url} - उसी tab पर जाएँ (नया tab नहीं खोला)\n"
                  f"(नया शुरू करना हो तो पहले उसकी window बंद करें)\n"
                  f"water_app map UI is already running and open in the browser: {url} - go to that tab (no new tab opened).\n"
                  f"(To start it anew, close its window first.)")
        else:
            print(f"water_app map UI पहले से चल रहा है: {url} - browser में खोला\n"
                  f"(नया शुरू करना हो तो पहले उसकी window बंद करें)\n"
                  f"water_app map UI is already running: {url} - opened in the browser.\n"
                  f"(To start it anew, close its window first.)")
        if open_browser and (running.get("page_age_s") is None or running["page_age_s"] >= PAGE_OPEN_S):
            webbrowser.open(url)                         # no page of it open: one
        return None
    url = f"http://127.0.0.1:{srv.server_address[1]}/water"
    print(f"water_app map UI: {url}   (Ctrl+C to stop)\nProjects: {PROJECTS}")
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return srv


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog="python -m water_app ui")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--no-browser", action="store_true", help="do not open the browser")
    a = ap.parse_args(argv)
    serve(a.port, not a.no_browser)
