"""The sewer module's projects on disk (restructure stage 6, 15-Nov-2026: out of ui.py): the folders, a project's name as
a file name, its network (the layout made from the map, or a DXF network being corrected - its working state in
memory, NETS), the map's projection of it, the lists drawn on a DXF network and the stage inputs of a request.
Nothing here knows of HTTP."""
import csv
import json
import os
import re
from sewer_app import HOME
from sewer_app.core import store


PROJECTS = os.path.join(HOME, "projects")


OUT_ROOT = os.path.join(HOME, "output")


# the water module has its own server (water_app/web/server.py, port 8766), page and folders - isolation of sewer and
# water (user requests 21-Oct-2026, 10-Nov-2026): nothing of it here; the start page is the launcher's (port 8764)


def proj_dir():
    return PROJECTS


def out_root():
    return OUT_ROOT


def _ck(stem):
    """Key of the in-memory caches."""
    return stem


def safe_name(name):
    """A project name usable as a file name: letters (incl. Hindi with its vowel signs), digits, _ - (anything
    else -> _)."""
    import unicodedata
    s = "".join(c if c.isalnum() or c in "_-" or unicodedata.category(c).startswith("M") else " "
                for c in str(name or "").strip())
    s = re.sub(r"\s+", "_", s.strip())[:80] or "project"
    # names Windows keeps for its devices (con.kml would be the console, not a file)
    if s.split(".")[0].upper() in _DEVICES:
        s = "_" + s
    return s


_DEVICES = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(10)), *(f"LPT{i}" for i in range(10))}


def save_project(name, kml):
    os.makedirs(proj_dir(), exist_ok=True)
    path = os.path.join(proj_dir(), safe_name(name) + ".kml")
    store.write_text(path, kml)
    return path


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
    from sewer_app.net import netedit
    st = NETS.get(_ck(stem))
    if st is None:
        st = netedit.load(out_root(), stem)
        if st is None:
            raise ValueError(f"'{stem}': DXF network नहीं मिला")
        NETS[_ck(stem)] = st
    return st


def paths(stem):
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
    from sewer_app.core import geo
    if is_dxf(stem):
        from sewer_app.net import netedit
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
    from sewer_app.core import geo
    if is_dxf(stem):
        from sewer_app.net import netedit
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
    from sewer_app.core import network
    folder, f_mh, f_co, f_pop = paths(stem)
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


STAGE_KEYS = ("base_year", "pop_initial", "pop_mid", "census", "pop_method", "floating_pct")


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
    return os.path.isfile(paths(stem)[1])


def project_net(stem):
    """The network zoning / design work on (user decision 19-Oct-2026: no 'सहेजें' needed first - the network can be
    tried as it is edited): a DXF network as it is NOW in the map's working state (unsaved changes too); a layout
    from its CSV files."""
    from sewer_app.net import netedit
    from sewer_app.core import network
    if is_dxf(stem):
        net = netedit._tuples(net_state(stem)["net"])
        return {"nodes": {n: {"ground": v.get("ground"), "xy": v.get("xy"), "gl_source": str(v.get("gl_source") or "")}
                          for n, v in net["nodes"].items()},
                "conduits": [{"label": k["label"], "start_node": k["start_node"], "stop_node": k["stop_node"],
                              "length_m": k.get("length_m"), "vertices": k.get("vertices") or []}
                             for k in net["conduits"]],
                "outfalls": []}
    _, f_mh, f_co, _ = paths(stem)
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
    f_mh = paths(stem)[1]
    return f"layout:{os.path.getmtime(f_mh):.3f}" if os.path.isfile(f_mh) else ""


def list_file(name, kind):
    return os.path.join(proj_dir(), safe_name(name) + f".{kind}.json")


def read_list(name, kind):
    f = list_file(name, kind)
    if not os.path.isfile(f):
        return []
    with open(f, encoding="utf-8") as fh:
        return json.load(fh)


def write_list(name, kind, items):
    store.write_json(list_file(name, kind), items or [])


# ---- the Outputs tab (user request 16-Nov-2026): the project's output files, each opened from the page
OUTPUT_EXT = (".dxf", ".xlsx", ".kml", ".kmz", ".pdf", ".csv")


def output_files(stem):
    """The files of a project's output folder (and its sub-folders) a user opens - drawings, workbooks, KML, PDF, CSV -
    newest first: {ok, folder, files: [{file (relative, /), size, mtime, time}]}."""
    import time
    folder = os.path.join(out_root(), stem)
    files = []
    if os.path.isdir(folder):
        for root, _dirs, names in os.walk(folder):
            for f in names:
                if not f.lower().endswith(OUTPUT_EXT) or f.startswith("~$"):
                    continue
                p = os.path.join(root, f)
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                files.append({"file": os.path.relpath(p, folder).replace(os.sep, "/"), "size": st.st_size,
                              "mtime": st.st_mtime, "time": time.strftime("%d-%m-%Y %H:%M", time.localtime(st.st_mtime))})
    files.sort(key=lambda x: -x["mtime"])
    return {"ok": True, "folder": folder, "files": files}


def open_output(stem, rel="", folder=False):
    """A file of the project's output folder opened in its own program (Excel, AutoCAD ...), or the folder in Explorer
    with the file selected (folder=True; no file: the folder itself). Only within that folder."""
    import subprocess
    base = os.path.realpath(os.path.join(out_root(), stem))
    p = os.path.realpath(os.path.join(base, rel or ""))
    if os.path.commonpath([base, p]) != base or not os.path.exists(p):
        raise ValueError("file नहीं मिली / file not found: " + (rel or stem))
    if os.path.isfile(p) and not p.lower().endswith(OUTPUT_EXT):   # never a program (.bat, .exe ...) put there
        raise ValueError("यह file यहाँ से नहीं खुलती / this kind of file is not opened: " + (rel or stem))
    if not hasattr(os, "startfile"):
        raise ValueError("यहाँ file नहीं खुल सकती (Windows नहीं) / cannot open files here")
    if folder and os.path.isfile(p):
        subprocess.Popen(["explorer", "/select,", p])
    else:
        os.startfile(p)
    return {"ok": True, "path": p}
