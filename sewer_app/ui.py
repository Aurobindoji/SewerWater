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
MAX_DXF = 1024 * 1024 * 1024        # a DXF picked on the page (uploaded as it is, to projects\dxf\)
# the water module has its own server (water_app/server.py, port 8766), page and folders - isolation of sewer and
# water (user request 21-Oct-2026); /water here only sends the browser there
WATER_URL = "http://127.0.0.1:8766/water"


def proj_dir():
    return PROJECTS


def out_root():
    return OUT_ROOT


def _ck(stem):
    """Key of the in-memory caches."""
    return stem


def code_version():
    """Changes when any .py file of sewer_app changes: a running server with other code is an old one."""
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


# ---------------------------------------------------------------- a network read from a DXF, corrected on the map
NETS = {}                       # stem -> working state of netedit (kept in memory between the edits)


def net_state(stem):
    from . import netedit
    st = NETS.get(_ck(stem))
    if st is None:
        st = netedit.load(out_root(), stem)
        if st is None:
            raise ValueError(f"'{stem}': DXF network नहीं मिला")
        NETS[_ck(stem)] = st
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
                                il_layers=[x for x in req.get("il_layers") or [] if x],
                                node_prefix=name_prefix(req.get("node_prefix"), "MH-"),
                                pipe_prefix=name_prefix(req.get("pipe_prefix"), "CO-"))
    except Exception as e:
        return {"ok": False, "log": "\n".join(lines) + f"\n{type(e).__name__}: {e}"}
    NETS[_ck(stem)] = st
    ZCACHE.pop(_ck(stem), None)
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
    from . import geo, network
    from .__main__ import cmd_layout
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
    ZCACHE.pop(_ck(stem), None)                                    # a new layout: the old zoning no longer applies
    return layout_result(stem)


def _paths(stem):
    """(folder, manholes CSV, conduits CSV, population CSV) of the project's network: the layout made from the
    map, or the corrected DXF network ('सहेजें' of the network panel)."""
    folder = os.path.join(out_root(), stem)
    if is_dxf(stem):
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


def export_zoning(name, req):
    """DXF + KML + Excel of one option of the project's last zoning, as the map shows it (zone_export)."""
    import time
    from . import network, zone_export
    stem = safe_name(name)
    folder, f_mh, f_co, _ = _paths(stem)
    f = os.path.join(folder, f"{stem}_zoning_ui.json")
    if not os.path.isfile(f):
        return {"ok": False, "log": "पहले zoning चलाएँ"}
    with open(f, encoding="utf-8") as fh:
        z = json.load(fh)
    opt = next((o for o in z["options"] if o["option"] == req.get("option")), None)
    if opt is None:
        return {"ok": False, "log": f"option '{req.get('option')}' इस zoning में नहीं"}
    if "mains" not in opt:
        return {"ok": False, "log": "यह zoning ज़ोन-सीमाओं से पहले की है - \"Zoning options निकालें\" फिर से चलाएँ"}
    zq = z.get("req") or {}                          # the network the zoning was made on (its manholes at bends, spacing)
    from . import edits as ed
    net = design_net(stem, criteria_for(zq.get("max_depth"), zq.get("bend_drop"), zq.get("mh_spacing"),
                                        zq.get("bend_angle"), ed.clean(zq.get("edits"))["trunk"]),
                     barriers=zq.get("barriers"), loops=zq.get("loops"), crossings=zq.get("crossings"))
    to_ll, to_xy = converters_for(stem)
    q = z.get("req") or {}
    info = {"project": stem, "option": opt["option"], "zoning": z.get("time", ""),
            "STP manhole": q.get("stp") or "-",
            "design method": ("only the given outfalls / STP (sewer depth may grow)" if q.get("mode") == "given"
                              else "free (pumping station added where the sewer gets deeper than the limit)"),
            "max depth (m)": q.get("max_depth") or "design_criteria.json", "max zones from the ground slope": q.get("max_zones") or "-",
            "30 mm drop at a change of direction": "on (CPHEEO)" if bend_drop_on(q.get("bend_drop")) else "off (page)",
            "population": q.get("pop_total") or "-",
            "zones / sub-zones / PS": f"{len(opt['mains'])} / {len(opt.get('subs') or {})} / {opt['pumping']} "
                                      f"({opt['pumping_for_depth']} for depth)",
            "pipe cost (Rs lakh)": opt.get("pipe_lakh"), "total cost (Rs lakh, approx.)": opt.get("total_lakh"),
            "exported": time.strftime("%d-%m-%Y %H:%M")}
    base = os.path.join(folder, f"{stem}_zones_{opt['option']}_{time.strftime('%Y%m%d_%H%M')}")
    design_dxf = design_drawing_of(stem, opt["option"])
    if design_dxf:
        info["design drawing"] = os.path.basename(design_dxf)
    try:
        files = zone_export.export(opt, folder, base, to_ll, to_xy, net, info, design_dxf=design_dxf)
    except Exception as e:
        return {"ok": False, "log": f"{type(e).__name__}: {e}"}
    return {"ok": True, "files": files, "folder": folder, "design": os.path.basename(design_dxf) if design_dxf else None}


def design_drawing_of(stem, option):
    """The plan DXF of the project's last design when it is of this zoning option and of the network as it is now
    (not stale) - the zone export draws the zones into it; None otherwise."""
    f = os.path.join(out_root(), stem, f"{stem}_design_ui.json")
    if not os.path.isfile(f):
        return None
    with open(f, encoding="utf-8") as fh:
        d = json.load(fh)
    path = (d.get("files") or {}).get("plan_dxf")
    if (d.get("summary") or {}).get("option") != option or d.get("net_rev") != net_rev(stem):
        return None
    if not path or not os.path.isfile(path):
        return None
    return path


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


# ---------------------------------------------------------------- zoning and design from the page
ZCACHE = {}                    # stem -> (key of the inputs, zoning result): design of an option needs no re-run
INPUT_DEFAULTS = {"catalog": None, "joint": "ss", "sewage_lpcd": 108.0, "start_depth": 0.7, "peak": "table",
                  "infil_basis": "none", "infil_rate": 0.0, "data_grade": "PFR"}


def catalogs():
    """Pipe catalogs of data/sewer_catalog.json that can be used as they are: [{name, source, joints}], default
    first. Test sets and combinations still to be filled are left out."""
    from .criteria import CATALOG_FILE, load_catalog
    with open(CATALOG_FILE, encoding="utf-8") as fh:
        raw = json.load(fh)
    out = []
    for name, st in raw.get("sets", {}).items():
        if "TEST" in name.upper():
            continue
        joints = sorted((st.get("joint_n") or {}).keys())
        try:
            load_catalog(name, joints[0] if joints else "ss")
        except Exception:
            continue
        out.append({"name": name, "source": str(st.get("source") or "")[:160], "joints": joints})
    default = raw.get("default")
    return sorted(out, key=lambda c: (c["name"] != default, c["name"]))


def design_inputs(stem, req):
    """Inputs of zoning / design (the keys of an inputs.json) from the page, written to output\\<stem>\\
    <stem>_inputs.json so that the command line gives the same run. Population (user decision 22-Oct-2026): the
    base-year population of the page (or, without it, the wards' population of the layout) and the town's census
    figures -> the +15 / +30 years population with the floating population (population.forecast, as the Riverside
    DPR); the design runs on the +30 years figure, the wards' population only shares it out. An older run with only
    a design population (pop_total) still works as before."""
    from . import population
    folder, _, _, f_pop = _paths(stem)
    inp = dict(INPUT_DEFAULTS)
    for k in ("catalog", "joint", "sewage_lpcd", "start_depth"):
        if req.get(k) not in (None, ""):
            inp[k] = req[k] if k in ("catalog", "joint") else float(req[k])
    if not inp["catalog"]:
        inp["catalog"] = catalogs()[0]["name"]
    if is_dxf(stem):
        inp.pop("data_grade")               # levels of the drawing: DPR unless they are interpolated / assumed
    wards = None
    if os.path.isfile(f_pop):
        with open(f_pop, encoding="utf-8") as fh:
            wards = sum(float(r["Population"]) for r in csv.DictReader(fh))
        inp.update(pop_dist="csv", pop_csv=f_pop)
    else:
        inp.update(pop_dist="length")
    st = stage_inputs(req)
    base = st.get("pop_initial") or (wards if not req.get("pop_total") else None)
    if base:
        f = population.forecast(st.get("base_year") or 2027, base, req.get("census") or None,
                                req.get("pop_method") or None, sewage_lpcd=float(inp["sewage_lpcd"]))
        inp.update(base_year=f["base_year"], pop_initial=f["design"]["init"], pop_mid=f["design"]["mid"],
                   pop_total=f["design"]["ult"], forecast=f)
    else:
        inp["pop_total"] = round(wards, 1) if wards else float(req.get("pop_total") or 0)
        inp.update(st)
    if wards and inp.get("pop_total"):
        inp["pop_scale"] = inp["pop_total"] / wards          # the wards' population shares the design population out
    if not inp.get("pop_total"):
        raise ValueError("आबादी नहीं है: आधार वर्ष की आबादी दें (या वार्ड में population भरकर Layout दोबारा बनाएँ)")
    with open(os.path.join(folder, f"{stem}_inputs.json"), "w", encoding="utf-8") as fh:
        json.dump(dict(inp, _readme="written by the map UI (python -m sewer_app ui)"), fh, ensure_ascii=False, indent=2)
    return inp


STAGE_KEYS = ("base_year", "pop_initial", "pop_mid", "census", "pop_method")


def stage_inputs(req):
    """The stage-wise check of the page (CPHEEO Table 2.1, p2-9): base year and the total population of the base
    year and of +15 years; the design population is that of +30 years. Empty = no such stage."""
    out = {}
    for k in STAGE_KEYS[:3]:
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


def bend_drop_on(v):
    """'मोड़ पर 30 mm drop' of the page: on unless switched off (an older saved run has no such field)."""
    return v not in (False, 0, "0", "false", "off", "no")


MH_SPACING_RANGE = (5.0, 150.0)
BEND_ANGLE_RANGE = (1.0, 90.0)


def criteria_for(max_depth=None, bend_drop=True, mh_spacing=None, bend_angle=None, trunk=None):
    """design_criteria.json, with the project depth limit (max_depth_project_m) given on the page for this run, the
    30 mm drop where a sewer of the same size changes direction (drop_same_size_mm) switched off when the page says so
    (user decision 16-Oct-2026: on by default, as CPHEEO), and the largest distance between manholes
    (max_manhole_spacing_m, default 30 m, CPHEEO 3.71.1) and the bend that gets a manhole (bend_manhole_min_angle_deg,
    default 20 deg, a project decision) given on the page (user requests 20-Oct-2026); trunk: the sewers marked on the
    page as trunk sewers with no house connections (trunk_conduits - CPHEEO Table 3.31 spacing, user request
    21-Oct-2026)."""
    from .criteria import load_criteria
    crit = load_criteria()
    if trunk:
        tc = crit["sewer"].setdefault("trunk_conduits", {})
        tc["note"] = (f"PROJECT DECISION (marked in the map UI): {len(trunk)} trunk sewer(s) with no house "
                      f"connections - manhole spacing by CPHEEO Table 3.31 (p3-127). " + str(tc.get("note") or ""))
        tc["value"] = sorted(str(x) for x in trunk)
    if mh_spacing not in (None, ""):
        v = float(mh_spacing)
        if not MH_SPACING_RANGE[0] <= v <= MH_SPACING_RANGE[1]:
            raise ValueError(f"Manholes की दूरी {MH_SPACING_RANGE[0]:g} से {MH_SPACING_RANGE[1]:g} m के बीच दें")
        sp = crit["sewer"]["max_manhole_spacing_m"]
        if abs(v - float(sp["value"])) > 1e-9:
            sp["note"] = (f"PROJECT DECISION (user input in the map UI): {v:g} m for this run (design_criteria.json: "
                          f"{float(sp['value']):g} m, CPHEEO 3.71.1 p3-126: 30 m). " + str(sp.get("note") or ""))
            sp["value"] = v
    if bend_angle not in (None, ""):
        v = float(bend_angle)
        if not BEND_ANGLE_RANGE[0] <= v <= BEND_ANGLE_RANGE[1]:
            raise ValueError(f"मोड़ का कोण {BEND_ANGLE_RANGE[0]:g} से {BEND_ANGLE_RANGE[1]:g} degree के बीच दें")
        ba = crit["sewer"]["bend_manhole_min_angle_deg"]
        if ba.get("value") != v:
            ba["note"] = (f"PROJECT DECISION (user input in the map UI): {v:g} deg for this run (design_criteria.json: "
                          f"{ba.get('value')}). " + str(ba.get("note") or ""))
            ba["value"] = v
    if max_depth not in (None, ""):
        v = float(max_depth)
        if not 2.0 <= v <= 30.0:
            raise ValueError("अधिकतम गहराई 2 से 30 m के बीच दें")
        mp = crit["sewer"]["max_depth_project_m"]
        if abs(v - float(mp["value"])) > 1e-9:
            mp["note"] = (f"PROJECT DECISION (user input in the map UI): {v:g} m for this run (design_criteria.json: "
                          f"{float(mp['value']):g} m). " + str(mp.get("note") or ""))
            mp["value"] = v
    if not bend_drop_on(bend_drop):
        dr = crit["sewer"]["drop_same_size_mm"]
        dr["note"] = (f"PROJECT DECISION (user input in the map UI): no drop at a change of direction for this run "
                      f"(design_criteria.json: {float(dr['value'] or 0):g} mm, CPHEEO 'usually 30 mm'). "
                      + str(dr.get("note") or ""))
        dr["value"] = 0
    return crit


LOOP_GAP_M = 0.5        # a sewer crossing a zone loop stops this short of it, on both sides


def design_net(stem, crit, log=None, barriers=None, loops=None, crossings=None):
    """The project's network for zoning and design: as it is now on the map (project_net), its sewers cut at the
    barrier lines of the page (barriers.py, user 27-Oct-2026: no sewer crosses a highway / railway ...) and at the
    zone loops (an area enclosed on the map is a zone of its own, user 27-Oct-2026: the sewers crossing the loop stop
    LOOP_GAP_M short of it; its lowest manhole is its outlet - a pumping station, or the STP when inside), with the
    manholes at bends and for the spacing put in (spacing.presplit - user decision 20-Oct-2026: every manhole in the
    design). A crossing line of the page lets the sewers through a barrier / loop where it crosses it, or is a new
    sewer itself where none crosses there (barriers.add_crossing_pipes). net["barriers"] / net["barrier_cuts"] tell
    which were cut, net["crossings"] what each crossing did, net["zone_loops"] the loops: name, manholes, outlet."""
    from . import barriers as sb, spacing
    net = project_net(stem)
    to_xy = converters_for(stem)[1]
    bars = sb.clean(barriers, to_xy) if barriers else []
    crs = sb.clean_crossings(crossings, to_xy) if crossings else []
    rings = []
    for i, lp in enumerate(loops or [], 1):
        ring = [[float(q[0]), float(q[1])] for q in (lp or {}).get("latlngs") or [] if isinstance(q, (list, tuple)) and len(q) >= 2]
        if len(ring) < 3:
            continue
        name = str(lp.get("name") or "").strip() or f"Zone loop {i}"
        rings.append((name, sb.clean([{"name": f"loop:{name}", "type": "other", "gap_m": LOOP_GAP_M,
                                       "latlngs": ring + ring[:1]}], to_xy)))
    pts = sb.crossing_points(crs, bars + [ln[0] for _, ln in rings])
    net, made = sb.add_crossing_pipes(net, crs, bars + [ln[0] for _, ln in rings], pts)
    net, cuts = sb.cut(net, bars, pts)
    if log and bars:
        log("barrier lines: " + sb.summary(bars, cuts) + " (a dead end); a side so cut off drains to an outlet of its "
            "own")
    if log and made:
        log("crossings: " + sb.crossing_summary(made))
    zl = []
    for name, line in rings:
        net, lc = sb.cut(net, line, pts)
        cuts += lc
        xy = [tuple(q) for q in line[0]["xy"]]
        taken = {n for x in zl for n in x["manholes"]}
        inside = {n for n, v in net["nodes"].items() if n not in taken and v.get("xy") and _inside(v["xy"], xy)}
        low = [n for n in inside if net["nodes"][n].get("ground") is not None]
        out = min(low, key=lambda n: (net["nodes"][n]["ground"], str(n))) if low else None
        zl.append({"name": name, "manholes": inside, "outlet": out, "cut": len(lc), "ring": xy})
        if log:
            log(f"zone loop {name}: {len(inside)} manholes, outlet {out or '-'}"
                + (f" (GL {net['nodes'][out]['ground']:.2f}, the lowest inside)" if out else " (no manhole inside)")
                + f"; {len(lc)} sewers cut at it, ending {LOOP_GAP_M:g} m short on both sides")
    net, rows = spacing.presplit(net, crit)
    net.update(barriers=bars, barrier_cuts=cuts, zone_loops=zl, crossings=made)
    if log and rows:
        nb = sum(1 for r in rows if r["why"].startswith("bend"))
        sp = crit["sewer"]
        log(f"new manholes before zoning / design: {len(rows)} - {nb} at bends of "
            f"{sp['bend_manhole_min_angle_deg']['value']} deg or more (CPHEEO 3.71), {len(rows) - nb} for the spacing "
            f"of {sp['max_manhole_spacing_m']['value']:g} m (3.71.1); ground there INTERPOLATED along the sewer")
    return net


def zone_reasons(net, stp, max_depth):
    """Why each zone of a zoning option (user request 30-Oct-2026, as the water module's): a function of an outlet row
    of zoning.evaluate -> {"kind": stp / given / loop / depth / part / terrain, "barriers": the barrier lines its part
    of the network is cut off by, "loop", "isolated": its part joined to the rest by no sewer in the drawing,
    "max_depth"}."""
    import collections
    adj = collections.defaultdict(set)
    for k in net["conduits"]:
        adj[k["start_node"]].add(k["stop_node"])
        adj[k["stop_node"]].add(k["start_node"])
    part, parts = {}, collections.defaultdict(set)              # the connected parts of the network
    for n0 in sorted(adj, key=str):
        if n0 in part:
            continue
        st = [n0]
        part[n0] = n0
        while st:
            u = st.pop()
            parts[n0].add(u)
            for v in adj[u]:
                if v not in part:
                    part[v] = n0
                    st.append(v)
    at = {}                                                     # a cut manhole -> the line it was cut at
    for c in net.get("barrier_cuts", []):
        at[f"{c['pipe']}-x1"] = at[f"{c['pipe']}-x2"] = c["barrier"]
    loop_out = {x["outlet"]: x["name"] for x in net.get("zone_loops", []) if x.get("outlet")}
    given = set(net.get("outfalls") or [])
    main = part.get(stp)

    def why(zr):
        o, w = zr["zone outlet"], str(zr.get("why this outlet") or "")
        ns = parts.get(part.get(o), set()) if part.get(o) != main else set()   # the STP's part: the main one
        cut = sorted({at[n] for n in ns if n in at})
        bars = [b for b in cut if not b.startswith("loop:")]
        loops = sorted({b[5:] for b in cut if b.startswith("loop:")})
        kind = ("stp" if zr.get("role", "").startswith("STP") else "depth" if w.startswith("added")
                else "loop" if o in loop_out else "given" if o in given else "part" if "no outlet" in w else "terrain")
        return {"kind": kind, "barriers": bars, "loop": loop_out.get(o) or (loops[0] if loops else None),
                "isolated": kind == "part" and not bars and not loops and part.get(o) != main,
                "max_depth": max_depth}
    return why


def barrier_res(net, ll):
    """The barrier lines and their cuts for the page: the lines, where sewers were cut, and the parts of the cut
    sewers before the new manholes (the page has the network's sewers as they were, not these)."""
    parts = {lab for c in net.get("barrier_cuts", []) for lab in c["parts"]}
    parts |= {m["pipe"] for m in net.get("crossings", []) if m["pipe"]}            # new sewers along crossing lines
    geo = {}
    for k in net["conduits"]:                       # a part the new manholes divided: its pieces, end to end
        lab = k.get("piece_of") or k["label"]
        if lab in parts:
            pts = [ll(p) for p in (k.get("vertices") or [net["nodes"][k["start_node"]]["xy"], net["nodes"][k["stop_node"]]["xy"]])]
            geo[lab] = geo.get(lab, []) + (pts[1:] if geo.get(lab) else pts)
    return {"zone_loops": [{"name": x["name"], "manholes": len(x["manholes"]), "outlet": x["outlet"]} for x in net.get("zone_loops", [])],
            "barriers": [{"name": b["name"], "type": b["type"], "latlngs": b["latlngs"]} for b in net.get("barriers", [])],
            "cuts": [{"pipe": c["pipe"], "barrier": c["barrier"], "latlng": ll(c["xy"])} for c in net.get("barrier_cuts", [])],
            "cut_parts": [{"label": lab, "pts": pts} for lab, pts in geo.items()],
            "crossings": net.get("crossings", [])}


def _zoning(stem, inp, stp, max_zones, log, mode="auto", max_depth=None, bend_drop=True, edits=None, mh_spacing=None,
            bend_angle=None, barriers=None, loops=None, crossings=None):
    """mode 'auto': all zoning options, pumping stations added where the sewer gets deeper than max_depth (the
    project limit; default design_criteria.json); 'given': only the outfalls marked on the map / the STP (option
    GIVEN), the sewer may get deeper than the project limit. bend_drop, mh_spacing, bend_angle: see criteria_for. edits: the pipe /
    manhole tables' changes (edits.py) - on the returned network (net['_fixed_inv'] = the given inverts)."""
    from . import edits as ed
    from . import network, zoning
    _, f_mh, f_co, _ = _paths(stem)
    bend_drop = bend_drop_on(bend_drop)
    edits = ed.clean(edits)
    if not has_network(stem):
        raise ValueError("पहले DXF network खोलें या Layout बनाएँ")
    crit = criteria_for(max_depth, bend_drop, mh_spacing, bend_angle, edits["trunk"])
    # the base year stage does not change the zoning; the +15 years population does (the pumps are sized on its
    # flow - CPHEEO Table 2.1 p2-9, user decision 21-Oct-2026)
    zin = {k: v for k, v in inp.items() if k not in ("base_year", "pop_initial")}
    key = json.dumps([zin, stp, max_zones, mode, max_depth, bend_drop, edits, barriers or [], loops or [], crossings or [], net_rev(stem),
                      crit["sewer"]["max_manhole_spacing_m"]["value"],
                      crit["sewer"]["bend_manhole_min_angle_deg"]["value"]], sort_keys=True)
    hit = ZCACHE.get(_ck(stem))
    if hit and hit[0] == key:
        return hit[1], hit[2], False
    net = design_net(stem, crit, log, barriers, loops, crossings)   # a DXF network: as it is now on the map
    if stp and stp not in net["nodes"]:
        raise ValueError(f"STP manhole '{stp}' इस network में नहीं है")
    if edits["conduits"] or edits["manholes"]:
        net, fixed, notes = ed.apply(net, edits)
        net["_fixed_inv"] = fixed
        log(f"table edits: {len(edits['conduits'])} conduit(s), {len(edits['manholes'])} manhole(s)"
            + "".join(f"\n   {s}" for s in notes))
    outs = list(net_state(stem)["net"]["outfalls"]) if is_dxf(stem) else []   # outfalls marked on the map
    net["outfalls"] = sorted(set(outs + ([stp] if stp else [])))
    for lp in net.get("zone_loops", []):             # a zone loop: its own outlet, unless one is given inside it
        given = sorted(lp["manholes"] & set(net["outfalls"]))
        if given:
            lp["outlet"] = given[0]
            log(f"zone loop {lp['name']}: its outlet is {given[0]}, given inside it (STP / outfall)")
        elif lp["outlet"]:
            net["outfalls"] = sorted(set(net["outfalls"]) | {lp["outlet"]})
    if mode == "given" and not net["outfalls"]:
        raise ValueError("केवल दिए गए outfalls पर design के लिए नक्शे पर outfall चिह्नित करें या STP manhole भरें")
    if not bend_drop:
        log("30 mm drop at a change of direction: OFF (page) - same-size sewers keep their invert through a bend")
    z = zoning.run(net, inp, crit=crit, stp=stp or None, max_zones=int(max_zones or 8),
                   log=log, given_only=mode == "given", only_given=mode == "given", fixed_inv=net.get("_fixed_inv"))
    ZCACHE[_ck(stem)] = (key, z, net)
    return z, net, True


FIELDS = ("catalog", "joint", "sewage_lpcd", "start_depth", "stp", "max_zones", "pop_total", "mode", "max_depth",
          "bend_drop", "edits", "mh_spacing", "bend_angle", "barriers", "loops", "crossings") + STAGE_KEYS


def _keep(stem, kind, res, req):
    """The page's last zoning / design result, kept with the project (output\\<stem>\\<stem>_<kind>_ui.json) so that
    it is shown again when the project is opened (page reload, app restart)."""
    folder = os.path.join(out_root(), stem)
    os.makedirs(folder, exist_ok=True)
    import time
    keep = dict(res, req={k: req.get(k) for k in FIELDS + ("option",)}, time=time.strftime("%d-%m-%Y %H:%M"),
                net_rev=net_rev(stem))
    with open(os.path.join(folder, f"{stem}_{kind}_ui.json"), "w", encoding="utf-8") as fh:
        json.dump(keep, fh, ensure_ascii=False, separators=(",", ":"))
    if kind == "zoning":                                # a new zoning: the design of the old one is not shown again
        try:
            os.remove(os.path.join(folder, f"{stem}_design_ui.json"))
        except OSError:
            pass


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
                              "length_m": k.get("length_m"), "vertices": k.get("vertices") or []}
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


def last_results(stem):
    """What the page shows again on opening a project: {network_saved (= a network to zone), network_current,
    zoning, design} - a zoning / design made from another state of the network than the one now is 'stale'."""
    folder, f_mh, _, _ = _paths(stem)
    out = {"ok": True, "network_saved": has_network(stem), "network_current": True}
    if not out["network_saved"]:
        return out
    rev = net_rev(stem)
    for kind in ("zoning", "design"):
        f = os.path.join(folder, f"{stem}_{kind}_ui.json")
        if os.path.isfile(f):
            with open(f, encoding="utf-8") as fh:
                r = json.load(fh)
            if r.get("net_rev") is not None:
                r["stale"] = r["net_rev"] != rev
            else:                                   # kept before net_rev: the saved files' time, as before
                r["stale"] = (not os.path.isfile(f_mh) or os.path.getmtime(f) < os.path.getmtime(f_mh)
                              or not network_current(stem))
            out[kind] = r
    return out


def _source(stem):
    if is_dxf(stem):
        st = net_state(stem)
        return f"{st['dxf']} (corrected on the map: {len(st['edits'])} change(s), list in {stem}_network_edits.csv)"
    return os.path.join(proj_dir(), stem + ".kml")


BOUNDARY_GAP_M = 300.0        # drawn zone boundaries span open land up to this (m) - one line round a zone


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


def run_zoning(name, req):
    """Zoning options of the project's layout (zoning.run + the same files as 'python -m sewer_app zoning'):
    for the page the ranked options with their costs, and for each option the zone of every sewer, the outlets
    (STP / pumping stations) and the cut sewers."""
    import time
    from . import zoning
    from .zoning import VSEP
    stem = safe_name(name)
    folder, f_mh, _, _ = _paths(stem)
    if not has_network(stem):
        return {"ok": False, "log": "पहले DXF network खोलें या Layout बनाएँ"}
    lines = []
    try:
        inp = design_inputs(stem, req)
        if inp.get("forecast"):
            from .population import summary as pop_summary
            lines.append(pop_summary(inp["forecast"]))
        stp = (req.get("stp") or "").strip() or None
        z, net, fresh = _zoning(stem, inp, stp, req.get("max_zones") or 8, lines.append, req.get("mode") or "auto",
                                req.get("max_depth"), req.get("bend_drop"), req.get("edits"), req.get("mh_spacing"),
                                req.get("bend_angle"), req.get("barriers"), req.get("loops"), req.get("crossings"))
        base = os.path.join(folder, f"{stem}_zoning_{time.strftime('%Y%m%d_%H%M')}")
        f = zoning.write_outputs(z, base, source=_source(stem), network_dxf="best")
    except Exception as e:
        return {"ok": False, "log": "\n".join(lines) + f"\n{type(e).__name__}: {e}"}
    ll = to_latlng(stem)
    costs = z.get("option_costs") or {}
    why = zone_reasons(net, stp, criteria_for(req.get("max_depth"))["sewer"]["max_depth_project_m"]["value"])
    # boundaries to DRAW: triangles up to BOUNDARY_GAP_M long, so that a zone is enclosed by one line across
    # open land between its manholes (the zone areas of the tables keep the zoning's own, shorter limit)
    tg = zoning.triangulate(z["gl"], z["xy"], max(BOUNDARY_GAP_M, 2 * z["max_edge"]))

    def outer(reg):
        """Outer boundary rings only (in metres): a ring lying inside a larger ring of the same zone is a hole
        (no data) and would only clutter the boundary; a piece smaller than 1 % of the zone's largest (a manhole
        alone among another zone's) is not drawn."""
        rs = sorted((reg or {}).get("rings", []), key=lambda r: -abs(_ring_area(r)))
        keep = []
        for r in rs:
            if len(r) >= 3 and not any(_inside(r[0], k) for k in keep):
                keep.append(r)
        big = abs(_ring_area(keep[0])) if keep else 0
        return [r for r in keep if abs(_ring_area(r)) >= 0.01 * big]

    def rings(reg):
        return [[ll(p) for p in ring] for ring in outer(reg)]

    def ring_labels(reg):
        """A point inside each piece of a zone for its name (a zone can lie in several pieces where manholes are far
        apart); none for pieces smaller than 5 % of the largest."""
        keep = outer(reg)
        big = abs(_ring_area(keep[0])) if keep else 0
        return [ll(_interior(r)) if abs(_ring_area(r)) >= 0.05 * big else None for r in keep]

    opts = []
    for ev in z["rank"]:
        m = ev["m"]
        c = costs.get(m["option"], {})
        # main zones = the zones from the slope of the ground (outlets of the option without the pumping stations
        # added for depth); sub-zones = the areas of the pumping stations added for depth, each inside a main zone
        outs = sorted(set(ev["zone"].values()))
        added = set(ev.get("pumps_added") or [])
        base_zone, _, _ = zoning.zones_from_outlets([o for o in outs if o not in added], z["adj"], z["E"], z["gl"], z["W"])
        parent = {o: base_zone.get(o, o) for o in outs}
        main_regs = zoning.zone_regions(tg, base_zone) if tg else {}
        mains = [{"outlet": o, "rings": rings(main_regs.get(o)), "ring_labels": ring_labels(main_regs.get(o)),
                  "label": ll(main_regs[o]["label"]) if main_regs.get(o, {}).get("label") else None}
                 for o in sorted(set(base_zone.values()))]
        # sub-zones: those of the pumping stations added for depth, and - in a main zone that has such - the rest of
        # the main zone (the area that reaches the main outlet itself)
        with_subs = {parent[o] for o in added}
        sub_regs = zoning.zone_regions(tg, ev["zone"]) if (tg and (added or with_subs)) else {}
        subs = {o: {"rings": rings(sub_regs.get(o)), "ring_labels": ring_labels(sub_regs.get(o)),
                    "label": ll(sub_regs[o]["label"]) if sub_regs.get(o, {}).get("label") else None}
                for o in outs if o in added or o in with_subs}
        opts.append({
            "option": m["option"], "rank": m["rank"], "zones": m["zones"], "pumping": m["pumping stations"],
            "pumping_for_depth": m["of these added for depth"], "max_depth": m["max depth (m)"],
            "deep_project": m["manholes deeper than project limit"], "deep_cpheeo": m["manholes deeper than CPHEEO limit"],
            "pipe_lakh": m["pipe cost (Rs lakh)"], "total_lakh": c.get("total_lakh"), "groups_lakh": c.get("groups_lakh", {}),
            "cuts": [r["conduit"] for r in ev["cuts"]],
            "conduit_zone": {lab: d["to"].split(VSEP)[0] if ev["zone"].get(d["to"].split(VSEP)[0]) is None
                             else ev["zone"][d["to"].split(VSEP)[0]] for lab, d in ev["res"].items()},
            "outlets": [{"manhole": zr["zone outlet"], "role": zr["role"], "why": zr["why this outlet"],
                         "latlng": ll(z["xy"][zr["zone outlet"]]) if zr["zone outlet"] in z["xy"] else None,
                         "flow_lps": zr["design flow at outlet (L/s)"], "depth": zr["outlet depth = wet well (m)"],
                         "manholes": zr["manholes"], "area_ha": zr.get("zone area (ha)"), "reason": why(zr)}
                        for zr in ev["zones"]],
            "mains": mains, "parent": parent, "subs": subs})
    files = {k: v for k, v in f.items() if isinstance(v, str)}
    # the network's conduits cut by the new manholes (spacing.presplit): piece -> the conduit drawn on the map
    piece_of = {k["label"]: k["piece_of"] for k in net["conduits"] if k.get("piece_of") and k["label"] != k["piece_of"]}
    from .population import summary as pop_summary
    res = {"ok": True, "options": opts, "log": "\n".join(lines), "files": files, "inputs": inp,
           "cached": not fresh, "stp": stp, "piece_of": piece_of,
           "forecast": pop_summary(inp["forecast"]) if inp.get("forecast") else ""}
    res.update(barrier_res(net, ll))
    # separate pieces of the drawing close to each other, joined by no sewer: a gap to join (user 30-Oct-2026), not
    # across a barrier line / zone loop (cut there on purpose)
    from . import barriers as sb
    gaps = sb.near_parts(net, net.get("barriers", []) + [{"xy": x["ring"]} for x in net.get("zone_loops", [])
                                                          if x.get("ring")], skip=sb.cut_ends(net.get("barrier_cuts")))
    res["near_gaps"] = [{"a": g["a"], "b": g["b"], "dist_m": g["dist_m"], "latlngs": [ll(p) for p in g["xy"]]}
                        for g in gaps]
    if gaps:
        res["log"] += "\n" + sb.near_summary(gaps, what="sewer")
    _keep(stem, "zoning", res, req)
    return res


def run_design(name, req):
    """Design of the project's layout with a zoning option applied (as 'python -m sewer_app design
    --zoning-option'): report Excel, plan DXF, L-section DXF; for the page every designed sewer with its size,
    slope, depths and velocity."""
    import time
    from . import cad, dpr, hindi, lsection, pipeline, report, zoning
    from . import DesignError
    from . import edits as ed
    stem = safe_name(name)
    folder, f_mh, _, _ = _paths(stem)
    if not has_network(stem):
        return {"ok": False, "log": "पहले DXF network खोलें या Layout बनाएँ"}
    lines = []
    try:
        inp = design_inputs(stem, req)
        stp = (req.get("stp") or "").strip() or None
        z, net, _ = _zoning(stem, inp, stp, req.get("max_zones") or 8, lines.append, req.get("mode") or "auto",
                            req.get("max_depth"), req.get("bend_drop"), req.get("edits"), req.get("mh_spacing"),
                            req.get("bend_angle"), req.get("barriers"), req.get("loops"), req.get("crossings"))
        opt = req.get("option") or z["rank"][0]["m"]["option"]
        ev = next((e for e in z["rank"] if e["m"]["option"] == opt), None)
        if ev is None:
            return {"ok": False, "log": f"option '{opt}' नहीं मिला"}
        net2, applied = zoning.apply_option(net, ev)
        trunk = ed.clean(req.get("edits"))["trunk"]
        if trunk:                       # the trunk sewers and their pieces (pipeline takes them from the inputs)
            inp["trunk"] = ed.trunk_labels(net2, trunk)
        out = pipeline.run(net2, inp, crit=criteria_for(req.get("max_depth"), req.get("bend_drop"), req.get("mh_spacing"),
                                                       req.get("bend_angle"), trunk),
                           log=lines.append,
                           fixed_inv=net.get("_fixed_inv"))
        out["log"].insert(0, f"zoning option {opt} applied (map UI): outfalls {', '.join(net2['outfalls'])}; "
                             f"{len(applied)} cut conduit(s) disconnected at one end")
        if trunk:
            out["log"].insert(1, f"trunk sewers (page, CPHEEO Table 3.31 spacing): {len(trunk)} marked, "
                                 f"{len(inp['trunk'])} conduit(s) of the design")
        base = os.path.join(folder, f"{stem}_{opt}_sewer_design_{time.strftime('%Y%m%d_%H%M')}"
                                    + ("_PFR" if out["grade"] != "DPR" else ""))
        xl = report.write_report(out, base + ".xlsx", source=_source(stem))
        # the DPR sheets in the format of the Riverside estimate (user request 22-Oct-2026); its pumping stations as
        # in the zoning comparison: every zone outlet but the STP's (without an STP, the zone with the largest flow is
        # taken as reaching it by gravity)
        zr = [x for x in ev.get("zones") or [] if x["role"] == "pumping station"]
        if not stp and zr:
            grav = max(zr, key=lambda x: (x["design flow at outlet (L/s)"] or 0, x["zone outlet"]))
            zr = [x for x in zr if x is not grav]
        import glob
        prev = sorted(glob.glob(os.path.join(folder, f"{stem}_*_DPR.xlsx")), key=os.path.getmtime)
        xl_dpr = dpr.write_dpr(out, base + "_DPR.xlsx", title=f"{stem.replace('_', ' ').upper()} SEWERAGE SCHEME",
                               inp=inp, stations=[{"outfall": x["zone outlet"], "dist": x.get("straight distance to STP (m)")}
                                                  for x in zr if (x["design flow at outlet (L/s)"] or 0) > 0],
                               previous=prev[-1] if prev else None)    # the texts typed in its Project sheet are kept
        cad.design_drawing(out, base + ".dxf")
        lsection.draw(out, base + "_Lsection.dxf")
    except DesignError as e:
        return {"ok": False, "log": "\n".join(lines) + f"\n*** {e}"}
    except Exception as e:
        return {"ok": False, "log": "\n".join(lines) + f"\n{type(e).__name__}: {e}"}
    from .criteria import slope_row
    given = ed.clean(req.get("edits"))
    ll = to_latlng(stem)
    xy = out["xy"]
    res = out["res"]
    R = out["rules"]
    sewers = []
    # each sewer as drawn (with its bends, where the new manholes at bends lie), from its upstream manhole down
    verts = {k["label"]: k.get("vertices") or [] for k in net2["conduits"]}
    orig = {k["label"]: k.get("piece_of") or k["label"] for k in net2["conduits"]}   # the network's conduit of a piece
    trunk_set = set(inp.get("trunk") or [])
    gl_of = dict(out["ground"], **{m["label"]: m["ground"] for m in out["new_mh"]})

    def pieces_of(lab, d):
        """The conduits the new manholes (30 m spacing, bends) cut a designed sewer into - as in the plan DXF - from
        upstream down: label (the first keeps the sewer's), manholes, length, inverts, ground, depth, line."""
        made = (out.get("made") or {}).get(lab)
        if not made or len(made) < 2:
            return []
        out_ = []
        for p in (made[::-1] if d["rev"] else made):
            a_, b_, up, dn = (p["stop"], p["start"], p["dn"], p["up"]) if d["rev"] else (p["start"], p["stop"], p["up"], p["dn"])
            pts = [tuple(q) for q in p["vertices"]]
            pts = pts[::-1] if d["rev"] else pts
            g_a, g_b = gl_of.get(a_), gl_of.get(b_)
            out_.append({"label": p["label"], "from": a_, "to": b_, "length": p["length"], "il_up": up, "il_dn": dn,
                         "gl_up": g_a, "gl_dn": g_b, "depth_up": g_a - up if g_a is not None else None,
                         "depth_dn": g_b - dn if g_b is not None else None, "pts": [ll(q) for q in pts]})
        return out_

    for lab, d in res.items():
        a, b = xy.get(d["from"]), xy.get(d["to"])
        if not a or not b:
            continue
        line = [tuple(p) for p in verts.get(lab) or []]
        line = (line[::-1] if d["rev"] else line) if len(line) >= 2 else [a, b]
        line[0], line[-1] = a, b
        _, s_min = slope_row(R.slopes, d["D"])
        cov = [g - (il + d["D"] / 1000.0) if g is not None and il is not None else None
               for g, il in ((d["g_up"], d.get("up")), (d["g_dn"], d.get("dn")))]
        sewers.append({"label": lab, "pts": [ll(p) for p in line], "D": d["D"], "slope": d["slope"], "length": d["length"],
                       "q": d["q"], "v": d["v"], "depth_up": d["depth_up"], "depth_dn": d["depth_dn"],
                       "gl_up": d["g_up"], "gl_dn": d["g_dn"], "il_up": d.get("up"), "il_dn": d.get("dn"),
                       "from": d["from"], "to": d["to"], "flags": d.get("flags") or [],
                       "dd": d.get("dd"), "s_min": s_min, "cover_up": cov[0], "cover_dn": cov[1],
                       "edited": lab in given["conduits"], "checks": _sewer_checks(d, R, s_min, cov),
                       "pieces": pieces_of(lab, d), "orig": orig.get(lab, lab), "trunk": lab in trunk_set,
                       **{f"{x}_{t}": d.get(f"{x}_{t}") for t in ("init", "mid") for x in ("q", "v", "dd")}})
    manholes = []
    ins, outs_ = {}, {}
    for d in res.values():
        ins.setdefault(d["to"], []).append(d["label"])
        outs_.setdefault(d["from"], []).append(d["label"])
    for n, i in out["node_info"].items():
        if n not in xy:
            continue
        chk = []
        if i.get("depth") is not None and R.max_depth is not None and i["depth"] > R.max_depth + 1e-6:
            chk.append(f"depth > {R.max_depth:g} m (CPHEEO)")
        if i.get("depth") is not None and R.max_depth_project and i["depth"] > R.max_depth_project + 1e-6:
            chk.append(f"depth > {R.max_depth_project:g} m (project)")
        nv = net2["nodes"].get(n) or {}
        manholes.append({"label": n, "latlng": ll(xy[n]), "gl": i.get("ground"), "invert": i.get("invert"),
                         "new": "" if nv.get("cut_of") else nv.get("new_mh") or "",   # put in at a bend / for the spacing
                         "depth": i.get("depth"), "drop": i.get("drop") or "", "max_in_drop": i.get("max_in_drop"),
                         "outfall": bool(i.get("outfall")), "ins": ins.get(n, []), "outs": outs_.get(n, []),
                         "edited": n in given["manholes"], "checks": chk})
    # the new manholes of the drawing (30 m spacing, bends): on the page too, so that the map and the DXF agree
    # the new manholes: put in before the zoning (spacing.presplit - real manholes of the design) and those planned
    # after it (trunk sewers, Table 3.31)
    # (their GL interpolated along the sewer, or the survey level given in the manhole table - user request 21-Oct-2026)
    new_mh = [{"label": n, "latlng": ll(xy[n]), "why": v["new_mh"], "conduit": v.get("on_conduit"),
               "gl": out["node_info"].get(n, {}).get("ground"), "invert": out["node_info"].get(n, {}).get("invert"),
               "gl_edited": "gl" in given["manholes"].get(n, {}),
               "depth": out["node_info"].get(n, {}).get("depth")}
              for n, v in net2["nodes"].items() if v.get("new_mh") and not v.get("cut_of") and n in xy]
    new_mh += [{"label": m["label"], "latlng": ll((m["x"], m["y"])), "why": m.get("why", "spacing"), "conduit": m["conduit"],
                "gl": m["ground"], "invert": m["invert"], "depth": m["depth"]}
               for m in out["new_mh"] if m.get("x") is not None]
    by_d = {}
    for d in res.values():
        by_d[d["D"]] = by_d.get(d["D"], 0.0) + (d["length"] or 0.0)
    deps = [x for d in res.values() for x in (d["depth_up"], d["depth_dn"]) if x is not None]
    pipe = zoning.priced_cost(res)[0] / 1e5
    summary = {"option": opt, "sewers": len(res), "length": round(sum(d["length"] or 0 for d in res.values()), 1),
               "new_manholes": len(new_mh),
               "new_manholes_bend": sum(1 for m in new_mh if str(m.get("why", "")).startswith("bend")),
               "grade": out["grade"], "max_depth": round(max(deps), 2) if deps else None,
               "pipe_lakh": round(pipe, 2), "by_diameter": [[D, round(L, 1)] for D, L in sorted(by_d.items())],
               "outfalls": net2["outfalls"]}
    sizes = [{"id_mm": z["id_mm"], "nominal": z.get("nominal")} for z in out["catalog"][2]]
    from .population import summary as pop_summary
    res = {"ok": True, "summary": summary, "sewers": sewers, "manholes": manholes, "new_manholes": new_mh,
           "forecast": pop_summary(inp["forecast"]) if inp.get("forecast") else "",
           "sizes": sizes, "edits": given,
           "rules": {"vmin": R.vmin, "ddmax": R.ddmax, "cover": round(R.cover, 3), "max_depth": R.max_depth,
                     "max_depth_project": R.max_depth_project, "vmin_init": R.vmin_init},
           "stages": _stage_roles(out["stages"], ev),
           "warnings": out["warnings"], "plan_lines": out["plan_lines"], "log": "\n".join(out["log"]),
           "warnings_hi": [hindi.hi(w) for w in out["warnings"]],          # for the page (user 30-Oct-2026)
           "files": {"report": xl, "dpr": xl_dpr, "plan_dxf": base + ".dxf", "lsection_dxf": base + "_Lsection.dxf"}}
    res.update(barrier_res(net, ll))
    _keep(stem, "design", res, dict(req, option=opt, edits=given))
    return res


def _stage_roles(stages, ev):
    """pipeline.stage_table with the role of each outfall in the zoning option (STP / pumping station)."""
    role = {zr["zone outlet"]: zr["role"] for zr in ev.get("zones") or []}
    for st in stages:
        for o in st["outfalls"]:
            o["role"] = role.get(o["outfall"], "outfall")
    return stages


def _sewer_checks(d, R, s_min, cov):
    """The manual rules a designed sewer breaks (pipe table of the page): velocity at the ultimate peak, Table 3.13
    slope, d/D, cover at both ends, depth (CPHEEO / project limit)."""
    out = []
    if d["q"] and R.vmin and (d["v"] is None or d["v"] < R.vmin - 1e-9):
        out.append(f"v < {R.vmin:g} m/s")
    if "v_init" in d and d["q"] and R.vmin_init and (d["v_init"] is None or d["v_init"] < R.vmin_init - 1e-9):
        out.append(f"v (base year) < {R.vmin_init:g} m/s")
    if s_min and d["slope"] < s_min * (1 - 1e-6):
        out.append("slope < Table 3.13")
    if d["q"] and (d.get("dd") is None or d["dd"] > R.ddmax + 1e-6):
        out.append(f"d/D > {R.ddmax:g}")
    if any(c is not None and c < R.cover - 0.005 for c in cov):
        out.append(f"cover < {R.cover:.2f} m")
    deps = [x for x in (d["depth_up"], d["depth_dn"]) if x is not None]
    if deps and R.max_depth is not None and max(deps) > R.max_depth + 1e-6:
        out.append(f"depth > {R.max_depth:g} m (CPHEEO)")
    if deps and R.max_depth_project and max(deps) > R.max_depth_project + 1e-6:
        out.append(f"depth > {R.max_depth_project:g} m (project)")
    return out


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
        if host not in ("127.0.0.1", "localhost"):
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

    def do_GET(self):
        if not self._local_only():
            return
        u = self._route()
        if u.path == "/water":                           # the water module: its own server
            self.send_response(302)
            self.send_header("Location", WATER_URL + (f"?{u.query}" if u.query else ""))
            self.end_headers()
            return
        pages = {"/": "start.html", "/index.html": "start.html", "/sewer": "map.html", "/i18n.js": "i18n.js"}
        if u.path in pages:
            with open(os.path.join(STATIC, pages[u.path]), "rb") as fh:
                ctype = "text/javascript; charset=utf-8" if u.path.endswith(".js") else "text/html; charset=utf-8"
                return self._send(200, fh.read(), ctype)
        if u.path == "/api/version":
            return self._send(200, {"ok": True, "version": VERSION, "pid": os.getpid(),
                                    "page_age_s": round(time.time() - LAST_PING[0], 1) if LAST_PING[0] else None})
        if u.path == "/api/ping":                        # an open page: "still here"
            LAST_PING[0] = time.time()
            return self._send(200, {"ok": True})
        if u.path in ("/api/barriers", "/api/loops", "/api/crossings"):   # a DXF network's zoning tools (27-Oct-2026)
            kind = u.path.rsplit("/", 1)[1]
            f = os.path.join(proj_dir(), safe_name((parse_qs(u.query).get("name") or [""])[0]) + f".{kind}.json")
            items = []
            if os.path.isfile(f):
                with open(f, encoding="utf-8") as fh:
                    items = json.load(fh)
            return self._send(200, {"ok": True, kind: items})
        if u.path == "/api/projects":
            return self._send(200, {"ok": True, "projects": list_projects()})
        if u.path == "/api/catalogs":
            return self._send(200, {"ok": True, "catalogs": catalogs(),
                                    "max_depth": criteria_for()["sewer"]["max_depth_project_m"]["value"]})
        if u.path == "/api/last_results":
            name = safe_name((parse_qs(u.query).get("name") or [""])[0])
            try:
                with LOCK:
                    return self._send(200, last_results(name))
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
        if urlparse(self.path).path == "/api/dxf_upload":
            return self._dxf_upload(n)
        if n > MAX_BODY:
            return self._send(413, {"ok": False, "log": "too large"})
        try:
            req = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except ValueError:
            return self._send(400, {"ok": False, "log": "bad JSON"})
        u = self._route()
        if u.path in ("/api/barriers_save", "/api/loops_save", "/api/crossings_save"):   # the same, kept
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
                                 bend_nodes=True, node_prefix=req.get("node_prefix"), pipe_prefix=req.get("pipe_prefix"))
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
                rows, guess = netedit.dxf_layers(path)
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
        if u.path == "/api/zoning_export":
            with LOCK:
                return self._send(200, export_zoning(req.get("name"), req))
        if u.path in ("/api/zoning", "/api/design"):
            with LOCK:
                res = (run_zoning if u.path == "/api/zoning" else run_design)(req.get("name"), req)
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
    print(f"sewer_app map UI: {url}   (Ctrl+C to stop)\nProjects: {PROJECTS}")
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
