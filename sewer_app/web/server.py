"""Map UI: draw the project boundary, roads, wards with population, spot levels and the STP on a map in the
browser, save them as KML, make the sewer layout from them (python -m sewer_app layout), compare the zoning options
(python -m sewer_app zoning) and design the chosen one (python -m sewer_app design --zoning-option) - all on this
computer.

    .venv\\Scripts\\python -m sewer_app ui                 # opens http://127.0.0.1:8765 in the browser

The page (static/map.html) needs the internet only for the map tiles and the Leaflet library. Projects are KML
files in projects\\<name>.kml (the same KML Google Earth writes and 'layout' reads); a layout run writes to
output\\<name>\\ as the command line does. The server listens on 127.0.0.1 only.
"""
import collections
import contextlib
import io
import json
import os
import re
import hmac
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from sewer_app.data.project import NETS, _ck, is_dxf, layout_result, list_projects, net_state, open_output, out_root, output_files, proj_dir, read_list, safe_name, save_project, write_list  # noqa: F401
from sewer_app.data.inputs import ZCACHE, catalogs, criteria_for  # noqa: F401
from sewer_app.data.results import last_results  # noqa: F401
from sewer_app.run.zoning_run import export_zoning, run_zoning  # noqa: F401
from sewer_app.run.design_run import run_design  # noqa: F401
from sewer_app.core import store
from sewer_app import PKG

STATIC = os.path.join(PKG, "static")
MAX_BODY = 30 * 1024 * 1024
MAX_DXF = 1024 * 1024 * 1024        # a DXF picked on the page (uploaded as it is, to projects\dxf\)
# The run's secret (rewrite stage 2, user decision 26-Nov-2026): written into the page this server gives, sent back by
# the page with every POST (header X-App-Token). Another page of the browser cannot read it (not its origin), and no
# other program on this computer knows it - so only this app's own page can make the server do anything.
TOKEN = secrets.token_urlsafe(32)
TOKEN_HEADER = "X-App-Token"


def code_version():
    """Changes when any .py file of sewer_app changes: a running server with other code is an old one."""
    import glob
    import hashlib
    here = PKG                                    # every module of the package, in its folders
    h = hashlib.md5()
    for f in sorted(glob.glob(os.path.join(here, "*.py"))):
        h.update(f"{os.path.basename(f)}:{os.path.getmtime(f)}".encode())
    return h.hexdigest()[:12]


VERSION = code_version()


def kmz_to_kml(data):
    """The first .kml inside a KMZ (zip) as text."""
    import zipfile
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        name = next((n for n in z.namelist() if n.lower().endswith(".kml")), None)
        if not name:
            raise ValueError("no .kml inside the KMZ")
        return z.read(name).decode("utf-8", errors="replace")


def net_import(req):
    from sewer_app.net import netedit
    path, missing = dxf_path(req)
    if missing:
        return missing
    stem = safe_name(req.get("name") or os.path.splitext(os.path.basename(path))[0])
    pipes = [x for x in req.get("pipe_layers") or [] if x]
    if not pipes:
        return {"ok": False, "log": "कम से कम एक pipe layer चुनें"}
    lines = []
    try:
        zm = req.get("z_mode") if req.get("z_mode") in ("auto", "first", "off") else "auto"   # Z of the line ends
        st = netedit.import_dxf(out_root(), stem, path, pipes, req.get("mh_layers") or [], req.get("level_layers") or [],
                                epsg_of(req), log=lines.append, z_mode=zm,
                                il_layers=[x for x in req.get("il_layers") or [] if x],
                                node_prefix=name_prefix(req.get("node_prefix"), "MH-"),
                                pipe_prefix=name_prefix(req.get("pipe_prefix"), "CO-"))
    except Exception as e:
        return {"ok": False, "log": "\n".join(lines) + f"\n{type(e).__name__}: {e}"}
    NETS[_ck(stem)] = st
    ZCACHE.pop(_ck(stem), None)
    os.makedirs(proj_dir(), exist_ok=True)
    store.write_json(os.path.join(proj_dir(), stem + ".dxf.json"), {"kind": "dxf", "dxf": path, "state": netedit.state_path(out_root(), stem)})
    out = netedit.page_data(st)
    out["log"] = "\n".join(lines)
    return out


def net_call(path, req, query):
    """The /api/net... calls of the page for a DXF network."""
    from sewer_app.net import netedit
    stem = safe_name(req.get("name") or (query.get("name") or [""])[0])
    try:
        st = net_state(stem)
        if path == "/api/net":
            return netedit.page_data(st)
        if path == "/api/net_texts":
            bb = [float((query.get(k) or ["0"])[0]) for k in ("s", "w", "n", "e")]
            return {"ok": True, "texts": netedit.texts_in(st, bb)}
        if path == "/api/net_edit":
            touched = netedit.apply(st, req.get("ops") or [])
            ZCACHE.pop(_ck(stem), None)
            return netedit.page_data(st, full=False, touched=touched)
        if path == "/api/net_undo":
            netedit.undo(st)
            ZCACHE.pop(_ck(stem), None)
            return netedit.page_data(st)
        if path == "/api/net_repair":
            # a gravity sewer is a tree: its loops are cut
            rows = netedit.auto_repair(st, float(req.get("join_gap_m") or 1.0), float(req.get("tjoint_m") or 0.5),
                                       bool(req.get("loops", True)), bool(req.get("gl", True)))
            ZCACHE.pop(_ck(stem), None)
            out = netedit.page_data(st)
            cnt = collections.Counter(r["repair"] for r in rows)
            out["log"] = "अपने-आप सुधार: " + (", ".join(f"{k} {v}" for k, v in cnt.most_common()) or "कुछ नहीं मिला")
            return out
        if path == "/api/net_place":
            moved = netedit.place(st, req["from"], req["to"], req.get("points") or [])
            ZCACHE.pop(_ck(stem), None)
            return dict(netedit.page_data(st), points=moved)
        if path == "/api/net_save":
            files = netedit.save_network(st)
            if not files.pop("unchanged", False):
                ZCACHE.pop(_ck(stem), None)
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


def run_layout(name, kml, gl_mode="spots", flat_gl=None, snap=1.0, spacing=30.0, bend_nodes=True, node_prefix=None,
               pipe_prefix=None):
    """Save the KML, run 'layout' on it (roads, boundary, wards and spot levels all from that one file) and return
    {ok, log, files, manholes, conduits, marks} with the network in lon / lat for the map."""
    from sewer_app.core import geo
    from sewer_app.run.layout_cmd import cmd_layout
    stem = safe_name(name)
    path = save_project(stem, kml)
    folder = os.path.join(out_root(), stem)
    os.makedirs(folder, exist_ok=True)
    args = ["--roads-kml", path, "--population-kml", path, "--out", folder,
            "--snap", f"{float(snap):g}",
            # spacing 0 (water): nodes only at the road junctions and ends - no node in the middle of a pipe
            "--spacing", f"{float(spacing):g}" if float(spacing or 0) > 0 else "1000000"] + \
        ([] if bend_nodes else ["--no-bend-nodes"]) + \
        ["--node-prefix", name_prefix(node_prefix, "MH-"), "--pipe-prefix", name_prefix(pipe_prefix, "CO-")]
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
        store.write_text(f_b, '<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
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
    store.write_json(os.path.join(folder, f"{stem}_layout_ui.json"), {"marks": marks, "log": text})
    ZCACHE.pop(_ck(stem), None)                                    # a new layout: the old zoning no longer applies
    return layout_result(stem)


# ---------------------------------------------------------------------------------------- the page's calls (HTTP)
LOCAL_HOSTS = ("127.0.0.1", "localhost")
PAGES = {"/sewer": ("map.html", "text/html; charset=utf-8"), "/guide": ("guide.html", "text/html; charset=utf-8"), "/i18n.js": ("i18n.js", "text/javascript; charset=utf-8"),
         "/favicon.ico": ("favicon.ico", "image/x-icon"),        # the app icon on the tab (14-Nov-2026)
         "/map.css": ("map.css", "text/css; charset=utf-8")}
# the page's scripts (restructure stage 8, 15-Nov-2026: map.html's one script split into static/js/*.js)
PAGES.update({f"/js/{f}": (f"js/{f}", "text/javascript; charset=utf-8")
              for f in sorted(os.listdir(os.path.join(STATIC, "js"))) if f.endswith(".js")})
# a DXF network's zoning tools (27-Oct-2026), each a list kept as projects\<name>.<kind>.json:
# GET /api/<kind>?name=... reads it, POST /api/<kind>_save writes it
# the map libraries shipped with the app (static/vendor, rewrite stage 2, 26-Nov-2026: not from a CDN at run time)
_TYPES = {".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".png": "image/png",
          ".svg": "image/svg+xml"}
for _d, _, _fs in os.walk(os.path.join(STATIC, "vendor")):
    for _f in _fs:
        _rel = os.path.relpath(os.path.join(_d, _f), STATIC).replace(os.sep, "/")
        if os.path.splitext(_f)[1] in _TYPES:
            PAGES["/" + _rel] = (_rel, _TYPES[os.path.splitext(_f)[1]])
LISTS = ("barriers", "loops", "crossings")


def _problem(e, plain=()):
    """An exception as the page's answer; the kinds in `plain` are messages for the user, shown as they are."""
    return {"ok": False, "log": str(e) if isinstance(e, plain) else f"{type(e).__name__}: {e}"}


def _answer(fn, *args, plain=()):
    """fn(*args), or what went wrong in it as the page's answer."""
    try:
        return fn(*args)
    except Exception as e:
        return _problem(e, plain)


def dxf_path(req):
    """The DXF the page names -> (its path, None); (the path, the answer saying so) when there is no such file, or it
    is not a .dxf (only drawings are read on the page's word - rewrite stage 2, 26-Nov-2026)."""
    path = str(req.get("path") or "").strip().strip('"')
    if not path.lower().endswith(".dxf"):
        return path, {"ok": False, "log": f"केवल .dxf file / only a .dxf file: {path}"}
    return path, (None if os.path.isfile(path) else {"ok": False, "log": f"file नहीं मिली: {path}"})


def epsg_of(req):
    """The EPSG code the page gives; None for a drawing in local coordinates."""
    epsg = req.get("epsg")
    return int(epsg) if epsg not in (None, "", "local") else None


class Handler(BaseHTTPRequestHandler):
    server_version = "sewer_app_ui"

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
        if host not in LOCAL_HOSTS:
            self._send(403, {"ok": False, "log": "local use only"})
            return False
        return True

    def _route(self):
        """The request's path."""
        return urlparse(self.path)

    def _dxf_upload(self, n):
        """The bytes of a DXF picked on the page -> projects/dxf/<its name>.dxf; its path back."""
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

    def _own_page(self):
        """A POST of this app's own pages (and of programs, which send no Origin). A page of another site open in
        the same browser could otherwise post to this server unseen - its Origin is not this computer."""
        origin = self.headers.get("Origin")
        if origin is None or urlparse(origin).hostname in LOCAL_HOSTS:
            return True
        self.rfile.read(min(int(self.headers.get("Content-Length") or 0), MAX_BODY))   # read, so the answer arrives
        self._send(403, {"ok": False, "log": "local use only"})
        return False

    def _token_ok(self):
        """The POST carries this run's TOKEN (the app's own page sends it); else refused, its body read first."""
        if hmac.compare_digest(str(self.headers.get(TOKEN_HEADER) or "").encode(), TOKEN.encode()):
            return True
        self.rfile.read(min(int(self.headers.get("Content-Length") or 0), MAX_DXF))
        self._send(403, {"ok": False, "token": True,
                         "log": "page पुराना है (app दोबारा चला) - page दोबारा खोलें (F5) / the page is out of date: reload it"})
        return False

    def _name(self, u):
        """The project named in the query, as a file name."""
        return safe_name((parse_qs(u.query).get("name") or [""])[0])

    # ------------------------------------------------------------------------------------------------ GET
    def do_GET(self):
        if not self._local_only():
            return
        u = self._route()
        if u.path in ("/", "/index.html"):               # this module's own page (the start page: the launcher's)
            self.send_response(302)
            self.send_header("Location", "/sewer" + (f"?{u.query}" if u.query else ""))
            self.end_headers()
            return
        if u.path in PAGES:
            fname, ctype = PAGES[u.path]
            with open(os.path.join(STATIC, fname), "rb") as fh:
                data = fh.read()
            if fname == "map.html":                       # the run's token, for the page's POSTs
                data = data.replace(b"__APP_TOKEN__", TOKEN.encode("ascii"))
            return self._send(200, data, ctype)
        if u.path.startswith("/api/") and u.path[5:] in LISTS:
            return self._send(200, {"ok": True, u.path[5:]: read_list(self._name(u), u.path[5:])})
        get = self.GET.get(u.path)
        if get is None:
            return self._send(404, {"ok": False, "log": "not found"})
        res = get(self, u)
        return self._send(*res) if isinstance(res, tuple) else self._send(200, res)

    def _get_version(self, u):
        return {"ok": True, "version": VERSION, "pid": os.getpid(),
                "page_age_s": round(time.time() - LAST_PING[0], 1) if LAST_PING[0] else None}

    def _get_ping(self, u):                              # an open page: "still here"
        LAST_PING[0] = time.time()
        return {"ok": True}

    def _get_projects(self, u):
        return {"ok": True, "projects": list_projects()}

    def _get_catalogs(self, u):
        return {"ok": True, "catalogs": catalogs(),
                "max_depth": criteria_for()["sewer"]["max_depth_project_m"]["value"]}

    def _get_last_results(self, u):
        with LOCK:
            return _answer(last_results, self._name(u))

    def _get_layout_result(self, u):
        return _answer(layout_result, self._name(u))

    def _get_net(self, u):
        with LOCK:
            return net_call(u.path, {}, parse_qs(u.query))

    def _get_project(self, u):
        name = self._name(u)
        if is_dxf(name):
            return {"ok": True, "name": name, "kind": "dxf"}
        path = os.path.join(proj_dir(), name + ".kml")
        if not os.path.isfile(path):
            return 404, {"ok": False, "log": f"project '{name}' not found"}
        with open(path, encoding="utf-8") as fh:
            return {"ok": True, "name": name, "kml": fh.read()}

    def _get_outputs(self, u):                           # the Outputs tab: the project's files (16-Nov-2026)
        return _answer(output_files, self._name(u))

    GET = {"/api/version": _get_version, "/api/ping": _get_ping, "/api/projects": _get_projects,
           "/api/outputs": _get_outputs, "/api/catalogs": _get_catalogs, "/api/last_results": _get_last_results,
           "/api/layout_result": _get_layout_result, "/api/net": _get_net, "/api/net_texts": _get_net,
           "/api/project": _get_project}

    # ----------------------------------------------------------------------------------------------- POST
    def do_POST(self):
        if not self._local_only() or not self._own_page() or not self._token_ok():
            return
        n = int(self.headers.get("Content-Length") or 0)
        u = self._route()
        if u.path == "/api/dxf_upload":
            return self._dxf_upload(n)
        if n > MAX_BODY:
            return self._send(413, {"ok": False, "log": "too large"})
        try:
            req = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except ValueError:
            return self._send(400, {"ok": False, "log": "bad JSON"})
        if u.path.startswith("/api/") and u.path.endswith("_save") and u.path[5:-5] in LISTS:   # the same, kept
            kind = u.path[5:-5]
            write_list(req.get("name"), kind, req.get(kind))
            return self._send(200, {"ok": True})
        post = self.POST.get(u.path)
        if post is None:
            return self._send(404, {"ok": False, "log": "not found"})
        return self._send(200, post(self, u, req))

    def _post_save(self, u, req):
        path = save_project(req.get("name"), req.get("kml") or "")
        return {"ok": True, "path": path, "name": safe_name(req.get("name"))}

    def _post_kmz(self, u, req):
        import base64
        try:
            return {"ok": True, "kml": kmz_to_kml(base64.b64decode(req.get("data") or ""))}
        except Exception as e:
            return {"ok": False, "log": f"KMZ not read: {e}"}

    def _post_layout(self, u, req):
        with LOCK:
            return run_layout(req.get("name"), req.get("kml") or "", req.get("gl_mode", "spots"),
                              req.get("flat_gl"), req.get("snap", 1.0), req.get("spacing", 30.0),
                              bend_nodes=True, node_prefix=req.get("node_prefix"), pipe_prefix=req.get("pipe_prefix"))

    def _post_dxf_preview(self, u, req):                 # one layer of the drawing on the map
        from sewer_app.net import netedit
        path, missing = dxf_path(req)
        return missing or _answer(lambda: netedit.dxf_preview(path, str(req.get("layer") or ""), epsg_of(req)))

    def _post_dxf_layers(self, u, req):
        from sewer_app.net import netedit
        path, missing = dxf_path(req)
        if missing:
            return missing
        try:
            rows, guess = netedit.dxf_layers(path)
        except Exception as e:
            return _problem(e)
        return {"ok": True, "layers": rows, "guess": guess,
                "name": safe_name(os.path.splitext(os.path.basename(path))[0])}

    def _post_dxf_gl_options(self, u, req):              # the layers the GL could come from, for the user to choose
        from sewer_app.net import dxf_extract
        path, missing = dxf_path(req)
        return missing or _answer(dxf_extract.gl_options, path, [x for x in req.get("pipe_layers") or [] if x],
                                  [x for x in req.get("mh_layers") or [] if x])

    def _post_dxf_netpreview(self, u, req):               # the network of the ticked layers, nothing saved
        from sewer_app.net import netedit
        path, missing = dxf_path(req)
        if missing:
            return missing
        pipes = [x for x in req.get("pipe_layers") or [] if x]
        if not pipes:
            return {"ok": False, "log": "कम से कम एक sewer layer चुनें"}
        zm = req.get("z_mode") if req.get("z_mode") in ("auto", "first", "off") else "auto"
        return _answer(lambda: netedit.dxf_net_preview(
            path, pipes, req.get("mh_layers") or [], req.get("level_layers") or [], epsg_of(req), zm,
            name_prefix(req.get("node_prefix"), "MH-"), name_prefix(req.get("pipe_prefix"), "CO-")))

    def _post_dxf_import(self, u, req):
        with LOCK:
            return net_import(req)

    def _post_net(self, u, req):
        with LOCK:
            return net_call(u.path, req, {})

    def _post_zoning_export(self, u, req):
        with LOCK:
            return export_zoning(req.get("name"), req)

    def _post_zoning(self, u, req):
        with LOCK:
            return run_zoning(req.get("name"), req)

    def _post_design(self, u, req):
        with LOCK:
            return run_design(req.get("name"), req)

    def _post_open_output(self, u, req):                 # a file of the Outputs tab opened / shown in its folder
        return _answer(open_output, safe_name(req.get("name", "")), str(req.get("file") or ""), bool(req.get("folder")))

    POST = {"/api/save": _post_save, "/api/kmz": _post_kmz, "/api/layout": _post_layout,
            "/api/dxf_preview": _post_dxf_preview, "/api/dxf_layers": _post_dxf_layers,
            "/api/dxf_gl_options": _post_dxf_gl_options, "/api/dxf_import": _post_dxf_import,
            "/api/dxf_netpreview": _post_dxf_netpreview,
            "/api/net_edit": _post_net, "/api/net_undo": _post_net, "/api/net_repair": _post_net,
            "/api/net_save": _post_net, "/api/net_place": _post_net, "/api/zoning_export": _post_zoning_export,
            "/api/zoning": _post_zoning, "/api/design": _post_design, "/api/open_output": _post_open_output}


LOCK = threading.Lock()
# when an open page last said it is open (it pings every 30 s): a second start of the bat file opens no new tab then
LAST_PING = [0.0]
PAGE_OPEN_S = 150                    # a background tab's timers may run only once a minute


class Server(ThreadingHTTPServer):
    # on Windows SO_REUSEADDR lets a SECOND server take the same port silently (the page then talks to whichever
    # answers, maybe an old one) - so no reuse there: a second start finds the port busy
    allow_reuse_address = os.name != "nt"


def serve(port=8765, open_browser=True):
    url = f"http://127.0.0.1:{port}/"
    try:
        srv = Server(("127.0.0.1", port), Handler)
    except OSError:
        running = None
        try:
            import urllib.request
            with urllib.request.urlopen(url + "api/version", timeout=5) as r:
                running = json.loads(r.read())
        except Exception:
            pass
        if not running or running.get("version") != VERSION:
            pid = f" - process {running.get('pid')}" if running else ""
            print(f"\n*** इस port ({url}) पर sewer_app का पुराना version (या कोई और program) पहले से चल रहा है{pid}.\n"
                  f"*** नया code तभी चलेगा जब उसकी काली window बंद करें (या उसमें Ctrl+C), फिर यह file दोबारा चलाएँ.\n"
                  f"*** An older sewer_app (or another program) is already running on this port ({url}){pid}.\n"
                  f"*** Close its black window (or press Ctrl+C in it), then start this file again.\n")
            return None
        age = running.get("page_age_s")
        if age is not None and age < PAGE_OPEN_S:       # a page of it is open: that tab, not one more
            print(f"sewer_app map UI पहले से चल रहा है और browser में खुला है: {url} - उसी tab पर जाएँ (नया tab नहीं खोला)\n"
                  f"(नया शुरू करना हो तो पहले उसकी window बंद करें)\n"
                  f"sewer_app map UI is already running and open in the browser: {url} - go to that tab (no new tab opened).\n"
                  f"(To start it anew, close its window first.)")
        else:
            print(f"sewer_app map UI पहले से चल रहा है: {url} - browser में खोला\n"
                  f"(नया शुरू करना हो तो पहले उसकी window बंद करें)\n"
                  f"sewer_app map UI is already running: {url} - opened in the browser.\n"
                  f"(To start it anew, close its window first.)")
        if open_browser and (running.get("page_age_s") is None or running["page_age_s"] >= PAGE_OPEN_S):
            webbrowser.open(url)                         # no page of it open: one
        return None
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    print(f"sewer_app map UI: {url}   (Ctrl+C to stop)\nProjects: {proj_dir()}")
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
    ap = argparse.ArgumentParser(prog="python -m sewer_app ui")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true", help="do not open the browser")
    a = ap.parse_args(argv)
    serve(a.port, not a.no_browser)
