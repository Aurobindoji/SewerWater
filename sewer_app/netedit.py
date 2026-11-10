"""A sewer network read from a DXF, shown on the map of the UI and corrected there (user decision 12-Oct-2026:
"DXF network को नक्शे पर देखकर सुधारना").

    rows, guess = netedit.dxf_layers(path)                 # layers of the drawing + suggested pipe / MH layers
    st = netedit.import_dxf(stem, path, pipes, mhs, levels, epsg)   # dxf_extract -> working state (JSON)
    page = netedit.page_data(st)                            # nodes, conduits (lat / lon), issues
    netedit.apply(st, ops)                                  # the user's corrections, each one logged
    netedit.auto_repair(st)                                 # repair.repair (gaps, T-joints, loops, missing GL)
    netedit.save_network(st)                                # CSV files for zoning / design + the log of edits

The working state is output\\<stem>\\<stem>_netedit.json; the drawing's texts (for showing them on the map next to
the manholes) are in <stem>_dxf_texts.json. Problems are those of repair.check: the ones dxf_extract found while
reading (labels / GLs matched in pass 2, manholes without a label, gaps, T-joints ...) are kept from the import and
dropped when their manhole is gone; the network problems (no GL, GL spikes, loops, parts without an outfall, short
conduits) are found again after every change. A person can mark a problem as checked ('reviewed').
"""
import collections
import json
import math
import os
import re
import time

from . import repair
from .spacing import label_namer

USER_GL = "edited in the map UI (user)"
EX_TYPES = {"label matched in pass 2 - CHECK", "label matched in pass 2 - low risk", "GL matched in pass 2 - CHECK",
            "GL matched in pass 2 - low risk", "no drawing label (name generated)", "manhole on a continuous line - check",
            "near-miss gap", "T-joint", "label used twice in the drawing", "label suggested (nearest unused label) - CHECK",
            "IL not below the GL - CHECK", "IL shallow - CHECK"}
LOW = {"label matched in pass 2 - low risk", "GL matched in pass 2 - low risk"}
GL_TYPES = {"GL matched in pass 2 - CHECK", "GL matched in pass 2 - low risk", "no ground level",
            "GL spike (> 2 m from all neighbours)"}
LABEL_TYPES = {"label matched in pass 2 - CHECK", "label matched in pass 2 - low risk",
               "no drawing label (name generated)", "label used twice in the drawing", "label suggested (nearest unused label) - CHECK"}
SUGGESTED = "label suggested (nearest unused label) - CHECK"
SUGGEST_RADIUS_M = 25.0         # a label further than this from the symbol is not suggested
SUGGEST_GL_M = 4.0              # the GL text is looked for this close to the label text
UNDO_MAX = 20
_UNDO = collections.defaultdict(lambda: collections.deque(maxlen=UNDO_MAX))
_TEXTS = {}


# ---------------------------------------------------------------- files
def state_path(out_root, stem):
    return os.path.join(out_root, stem, f"{stem}_netedit.json")


def load(out_root, stem):
    p = state_path(out_root, stem)
    if not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8") as fh:
        st = json.load(fh)
    st["_root"] = out_root
    return st


def store(st):
    p = state_path(st["_root"], st["stem"])
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    text = json.dumps({k: v for k, v in st.items() if not k.startswith("_")}, ensure_ascii=False,
                      separators=(",", ":"))                    # one string: much faster than json.dump to a file
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, p)


# ---------------------------------------------------------------- the drawing
_INV = {}                       # (path, mtime) -> inventory of the drawing (layers, lines, texts, inserts, points)


def _inventory(path):
    """The drawing's entities, read once per file version (the layer table and its previews)."""
    from . import dxf_inspect as di
    key = (os.path.abspath(path), os.path.getmtime(path))
    if key not in _INV:
        doc, _ = di.load(path)
        _INV.clear()                                    # one drawing at a time
        _INV[key] = di.inventory(doc.modelspace())
    return _INV[key]


def dxf_preview(path, layer, epsg=None, max_lines=4000, max_pts=3000):
    """What one layer holds, for the map: {types (entity kind -> count), lines [[lat, lon], ...], points
    [[lat, lon, text / block name, kind]], line_m, n_lines, avg_line_m, samples (commonest texts), blocks (block
    names), truncated, local}. Without an EPSG the layer is laid out around 0 / 0, as a local drawing is."""
    import collections as co
    layers, lines, texts, inserts, points = _inventory(path)
    if layer not in layers:
        raise ValueError(f"layer '{layer}' इस drawing में नहीं")
    ls = [ln for ln in lines if ln["layer"] == layer]
    ts = [t for t in texts if t["layer"] == layer]
    bs = [b for b in inserts if b["layer"] == layer]
    cs = [p for p in points if p["layer"] == layer]
    pts = [(t["x"], t["y"], t["text"][:30], "text") for t in ts] + [(b["x"], b["y"], b["name"][:30], "block") for b in bs] + \
          [(p["x"], p["y"], p["kind"].lower(), p["kind"].lower()) for p in cs]
    st = {"epsg": int(epsg) if epsg else None}
    if not st["epsg"]:
        xs = [p[0] for ln in ls for p in ln["pts"]] + [p[0] for p in pts]
        ys = [p[1] for ln in ls for p in ln["pts"]] + [p[1] for p in pts]
        st["origin"] = [sum(xs) / len(xs), sum(ys) / len(ys)] if xs else [0.0, 0.0]
    to_ll = converters(st)[0]
    keep = ls[:max_lines]
    flat, cut = [], []
    for ln in keep:                                       # at most 50 points a line: enough to see it
        p = ln["pts"]
        step = max(1, len(p) // 50)
        q = [[a[0], a[1]] for a in p[::step]] + ([[p[-1][0], p[-1][1]]] if (len(p) - 1) % step else [])
        cut.append(len(q))
        flat += q
    ll = to_ll(flat)
    out_lines, i = [], 0
    for n in cut:
        out_lines.append(ll[i:i + n])
        i += n
    pp = pts[:max_pts]
    pl = to_ll([[p[0], p[1]] for p in pp])
    tot = sum(ln["len"] for ln in ls)
    return {"ok": True, "layer": layer, "types": dict(layers[layer]["types"]), "lines": out_lines,
            "points": [[a[0], a[1], p[2], p[3]] for a, p in zip(pl, pp)],
            "line_m": round(tot, 1), "n_lines": len(ls), "avg_line_m": round(tot / len(ls), 1) if ls else None,
            "samples": [t for t, _ in co.Counter(t["text"] for t in ts if t["text"]).most_common(12)],
            "blocks": [b for b, _ in co.Counter(b["name"] for b in bs).most_common(5)],
            "truncated": len(ls) > max_lines or len(pts) > max_pts, "local": not st["epsg"]}


def dxf_layers(path, water=False):
    """Layers of a DXF with what is on them, and a guess of the pipe and manhole layers (as 'inspect'):
    ([{layer, line_m, texts, ids, levels, blocks, circles}], {"pipe": [...], "mh": [...], "level": [...]}).
    water: a drain (nala) is no pipe; the node / junction / valve symbols are its 'manholes'."""
    from . import dxf_inspect as di
    layers, lines, texts, inserts, points = _inventory(path)
    ids, lev = collections.Counter(), collections.Counter()
    for t in texts:
        for kind, _ in di.classify(t["text"]):
            if kind == "id":
                ids[t["layer"]] += 1
            elif kind == "level":
                lev[t["layer"]] += 1
    tcount = collections.Counter(t["layer"] for t in texts)
    nlines = collections.Counter(ln["layer"] for ln in lines)
    blocks = collections.Counter(b["layer"] for b in inserts)
    circles = collections.Counter(p["layer"] for p in points if p["kind"] == "CIRCLE")
    rows = []
    for lay, L in layers.items():
        rows.append({"layer": lay, "line_m": round(L["length"], 1), "texts": tcount[lay], "ids": ids[lay],
                     "levels": lev[lay], "blocks": blocks[lay], "circles": circles[lay], "lines": nlines[lay]})
    rows.sort(key=lambda r: (-r["line_m"], -r["texts"]))
    # sewer lines run manhole to manhole (tens of metres); a few very long lines (avg > 400 m) are rising mains
    pipe = [r["layer"] for r in rows if r["line_m"] > 0 and di.PIPE_NAME.search(r["layer"])
            and not di.NOT_PIPE_NAME.search(r["layer"]) and r["line_m"] / max(r["lines"], 1) <= 400
            and not (water and re.search(r"nala|nallah|nalla|drain", r["layer"], re.I))]
    # house numbers (HH-12) look like manhole names but are not
    not_mh = re.compile(r"tbm|bench|\bbm\b|level|elev|text|road|plot|house|\bhh\b|household", re.I)
    # a manhole layer: mostly names, or one name per symbol (name, GL, IL, depth written at every manhole)
    mh = [r["layer"] for r in rows if r["ids"] >= 5 and not not_mh.search(r["layer"]) and r["layer"] not in pipe
          and (r["ids"] >= 0.3 * r["texts"] or (r["blocks"] + r["circles"] and abs(r["ids"] - r["blocks"] - r["circles"])
                                                <= 0.2 * (r["blocks"] + r["circles"])))]
    mh += [r["layer"] for r in rows if (r["blocks"] or r["circles"]) and re.search(r"\bmh\b|mh-|manhole", r["layer"], re.I)
           and r["layer"] not in mh]
    # symbols of the network's nodes (a filled circle at every junction, often with its level)
    mh += [r["layer"] for r in rows if r["blocks"] + r["circles"] >= 5 and r["layer"] not in mh
           and re.search(r"node|junction|\bjn\b|jn-|valve", r["layer"], re.I)]
    return rows, {"pipe": pipe, "mh": mh, "level": list(di.level_candidates(texts))}


def import_dxf(out_root, stem, path, pipe_layers, mh_layers=(), level_layers=(), epsg=32644, log=print, z_mode="auto",
               il_layers=(),
               node_prefix=None, pipe_prefix=None):
    """dxf_extract.extract -> working state (network, problems of the drawing, settings) - saved and returned."""
    from . import dxf_extract, dxf_inspect as di, network
    ex = dxf_extract.extract(path, list(pipe_layers), list(mh_layers), list(level_layers), z_mode=z_mode, node_prefix=node_prefix, pipe_prefix=pipe_prefix,
                             il_layers=list(il_layers))
    for ln in ex["summary"]:
        log("   " + ln)
    net = network.from_extract(ex)
    probs = [{"Problem": p["Problem"], "Item": p["Item"], "X": _f(p.get("X")), "Y": _f(p.get("Y")),
              "Detail": str(p.get("Detail") or "")} for p in ex["problems"]]
    ex_issues = [i for i in repair.check(net, {"problems": probs}, []) if i["type"] in EX_TYPES]
    st = {"stem": stem, "kind": "dxf", "dxf": path, "pipe_layers": list(pipe_layers), "mh_layers": list(mh_layers),
          "level_layers": list(level_layers), "z_mode": z_mode, "il_layers": list(il_layers), "epsg": int(epsg) if epsg else None, "imported": time.strftime("%d-%m-%Y %H:%M"),
          "summary": ex["summary"], "net": _net_json(net), "ex_problems": probs, "ex_issues": ex_issues,
          "reviewed": [], "edits": [], "next_id": 0, "_root": out_root,
          # the names chosen on the page, when other than the module's own (30-Oct-2026)
          "prefix": {k: v for k, v in (("node", node_prefix), ("pipe", pipe_prefix)) if v and v != {"node": "MH-", "pipe": "CO-"}[k]}}
    for k in st["net"]["conduits"]:
        k["id"] = st["next_id"]
        st["next_id"] += 1
    if st["epsg"] is None:                                       # local drawing: map around the middle
        xs = [v["xy"][0] for v in st["net"]["nodes"].values() if v.get("xy")]
        ys = [v["xy"][1] for v in st["net"]["nodes"].values() if v.get("xy")]
        st["origin"] = [sum(xs) / len(xs), sum(ys) / len(ys)] if xs else [0.0, 0.0]
    # the drawing's texts, for the map (labels and levels of the drawing next to the manholes)
    doc, _ = di.load(path)
    _, _, texts, _, _ = di.inventory(doc.modelspace())
    os.makedirs(os.path.join(out_root, stem), exist_ok=True)
    tx = [[round(t["x"], 3), round(t["y"], 3), t["text"][:40], t["layer"]] for t in texts if t["text"]]
    with open(os.path.join(out_root, stem, f"{stem}_dxf_texts.json"), "w", encoding="utf-8") as fh:
        json.dump(tx, fh, ensure_ascii=False)
    _TEXTS.pop(stem, None)
    _LEVELS.pop(stem, None)
    _UNDO.pop(stem, None)
    store(st)
    return st


def _f(v):
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def _tuples(net):
    """The working network (JSON lists) in the form network.py / repair.py use (xy and vertices as tuples)."""
    return {"nodes": {n: dict(v, xy=tuple(v["xy"]) if v.get("xy") else None) for n, v in net["nodes"].items()},
            "conduits": [dict(k, vertices=[tuple(p) for p in k.get("vertices") or []]) for k in net["conduits"]],
            "outfalls": list(net["outfalls"])}


def _net_json(net):
    return {"nodes": {n: {"xy": list(v["xy"]) if v.get("xy") else None, "ground": v.get("ground"),
                          "gl_source": v.get("gl_source") or "",
                          **({"invert_drawing": v["invert_drawing"]} if v.get("invert_drawing") is not None else {})}
                      for n, v in net["nodes"].items()},
            "conduits": [{"label": k["label"], "start_node": k["start_node"], "stop_node": k["stop_node"],
                          "length_m": k["length_m"], "vertices": [list(p) for p in k.get("vertices") or []],
                          **({"id": k["id"]} if "id" in k else {})} for k in net["conduits"]],
            "outfalls": list(net.get("outfalls") or [])}


def _texts(st):
    stem = st["stem"]
    if stem not in _TEXTS:
        p = os.path.join(st["_root"], stem, f"{stem}_dxf_texts.json")
        with open(p, encoding="utf-8") as fh:
            _TEXTS[stem] = json.load(fh)
    return _TEXTS[stem]


def texts_in(st, bbox, limit=3000):
    """Texts of the drawing inside bbox (south, west, north, east in lat / lon): [[lat, lon, text, layer]]."""
    stem = st["stem"]
    _texts(st)
    s, w, n, e = bbox
    to_xy = converters(st)[1]
    (x0, y0), (x1, y1) = to_xy([[s, w], [n, e]])
    xa, xb, ya, yb = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
    sel = [t for t in _TEXTS[stem] if xa <= t[0] <= xb and ya <= t[1] <= yb][:limit]
    ll = converters(st)[0]([[t[0], t[1]] for t in sel])
    return [[p[0], p[1], t[2], t[3]] for p, t in zip(ll, sel)]


# ---------------------------------------------------------------- coordinates
def converters(st):
    """(to_latlng([[x, y], ...]) -> [[lat, lon], ...], to_xy([[lat, lon], ...]) -> [[x, y], ...]). Without an EPSG
    (local drawing coordinates) metres are laid out around 0 deg / 0 deg (no background map). A network placed on
    the map (place) is shifted by st["shift"] metres in its EPSG; x, y stay the drawing's."""
    if st.get("epsg"):
        from pyproj import Transformer
        fwd = Transformer.from_crs(st["epsg"], 4326, always_xy=True)
        inv = Transformer.from_crs(4326, st["epsg"], always_xy=True)
        dx, dy = st.get("shift") or (0.0, 0.0)

        def to_ll(pts):
            if not pts:
                return []
            lon, lat = fwd.transform([p[0] + dx for p in pts], [p[1] + dy for p in pts])
            return [[round(a, 7), round(b, 7)] for a, b in zip(lat, lon)]

        def to_xy(pts):
            if not pts:
                return []
            x, y = inv.transform([p[1] for p in pts], [p[0] for p in pts])
            return [[round(a - dx, 3), round(b - dy, 3)] for a, b in zip(x, y)]
        return to_ll, to_xy
    x0, y0 = st.get("origin") or (0.0, 0.0)
    return (lambda pts: [[round((p[1] - y0) / 110574.0, 8), round((p[0] - x0) / 111320.0, 8)] for p in pts],
            lambda pts: [[round(p[1] * 111320.0 + x0, 3), round(p[0] * 110574.0 + y0, 3)] for p in pts])


# ---------------------------------------------------------------- problems
def _key(i):
    return f"{i['type']}|{i['item']}"




def issues(st):
    """Problems now: [{key, type, item, x, y, detail, reviewed, low}]."""
    net = st["net"]
    nodes = net["nodes"]
    adj = collections.defaultdict(set)
    for k in net["conduits"]:
        adj[k["start_node"]].add(k["stop_node"])
        adj[k["stop_node"]].add(k["start_node"])
    out = []
    for i in st["ex_issues"]:
        parts = [p.strip() for p in str(i["item"]).split(" - ")] if i["type"] == "near-miss gap" else [str(i["item"])]
        if any(p not in nodes for p in parts if _looks_like_node(p, nodes, i)):
            continue                                            # its manhole was deleted / merged / renamed away
        if i["type"] == "near-miss gap" and len(parts) == 2 and _linked(adj, *parts):
            continue                                            # joined (directly or through a new manhole)
        out.append(dict(i))
    out += repair.check(_tuples(net), None, net["outfalls"], gravity=True)
    rev = set(st["reviewed"])
    for i in out:
        i["key"] = _key(i)
        i["reviewed"] = i["key"] in rev
        i["low"] = i["type"] in LOW
        if i.get("x") is None and str(i["item"]) in nodes and nodes[str(i["item"])].get("xy"):
            i["x"], i["y"] = nodes[str(i["item"])]["xy"]
    return out


NODE_ITEM = {"near-miss gap", "label matched in pass 2 - CHECK", "label matched in pass 2 - low risk",
             "GL matched in pass 2 - CHECK", "GL matched in pass 2 - low risk", "no drawing label (name generated)",
             "manhole on a continuous line - check", SUGGESTED}


def _looks_like_node(p, nodes, i):
    """The item of these problems is a manhole label (two for a gap) - a problem whose manhole is gone is dropped."""
    return i["type"] in NODE_ITEM


def _linked(adj, a, b, hops=3):
    """a and b joined by at most `hops` conduits (a gap closed by a sewer, maybe split by a new manhole)."""
    seen, front = {a}, {a}
    for _ in range(hops):
        front = {m for n in front for m in adj[n]} - seen
        if b in front:
            return True
        seen |= front
    return False


def _connected(net, a, b):
    return any({k["start_node"], k["stop_node"]} == {a, b} for k in net["conduits"])


# ---------------------------------------------------------------- labels too far from their symbol
ID_TEXT = re.compile(r"^\s*([A-Za-z]{1,8})\s*[-_ /]\s*(\d+[A-Za-z]?)\s*$")
LEVEL_TEXT = re.compile(r"^\s*(?:GL|RL|G\.L\.?|R\.L\.?)?\s*[:=\-]?\s*(\d{1,4}\.\d{1,3})\s*m?\s*$", re.I)


_LEVELS = {}


def _level_grid(st):
    """Level texts of the drawing in cells of SUGGEST_GL_M (built once per drawing)."""
    if st["stem"] not in _LEVELS:
        g = collections.defaultdict(list)
        for t in _texts(st):
            m = LEVEL_TEXT.match(t[2])
            if m:
                g[(int(t[0] // SUGGEST_GL_M), int(t[1] // SUGGEST_GL_M))].append((float(m.group(1)), t[0], t[1]))
        _LEVELS[st["stem"]] = g
    return _LEVELS[st["stem"]]


def suggestions(st, radius=SUGGEST_RADIUS_M):
    """For every manhole without a drawing label (name generated by dxf_extract), the label of the drawing that no
    manhole has and that lies nearest to it - one label for one manhole, the pairs chosen together so that the
    total distance is least (crowded places: two symbols close together with their labels written aside). With
    it the GL text written next to that label (within SUGGEST_GL_M), when it fits the neighbours' GL.
    Returns {manhole: {"label", "d", "lxy", "gl", "gxy"}}."""
    net = st["net"]
    nodes = net["nodes"]
    rev = set(st["reviewed"])          # a manhole renamed (by hand or by a suggestion) or marked as checked: done
    gen = [str(i["item"]) for i in st["ex_issues"]
           if i["type"] == "no drawing label (name generated)" and str(i["item"]) in nodes
           and nodes[str(i["item"])].get("xy") and _key(i) not in rev]
    if not gen:
        return {}
    # a name <label>/<part> (a label repeated in another part of the drawing) uses that label too
    pref = collections.Counter(m.group(1).upper() for n in nodes if n not in gen for m in [ID_TEXT.match(n.split("/")[0])] if m)
    keep = {p for p, c in pref.items() if c >= 0.05 * max(1, sum(pref.values()))}
    used = {n.upper() for n in nodes} | {n.split("/")[0].upper() for n in nodes}
    texts = _texts(st)
    labels, seen = [], set()
    for t in texts:
        m = ID_TEXT.match(t[2])
        if not m or m.group(1).upper() not in keep:
            continue
        lab = f"{m.group(1).upper()}-{m.group(2)}"
        if lab.upper() in used or lab in seen:
            continue
        seen.add(lab)
        labels.append((lab, t[0], t[1]))
    if not labels:
        return {}
    # candidate pairs within the radius, then the least total distance (assignment)
    cand = collections.defaultdict(dict)
    for i, n in enumerate(gen):
        x, y = nodes[n]["xy"]
        for j, (_, lx, ly) in enumerate(labels):
            d = math.hypot(lx - x, ly - y)
            if d <= radius:
                cand[i][j] = d
    if not cand:
        return {}
    rows = sorted(cand)
    cols = sorted({j for i in rows for j in cand[i]})
    ci = {j: k for k, j in enumerate(cols)}
    big = 1e6
    from scipy.optimize import linear_sum_assignment
    import numpy as np
    M = np.full((len(rows), len(cols)), big)
    for a, i in enumerate(rows):
        for j, d in cand[i].items():
            M[a, ci[j]] = d
    ra, cb = linear_sum_assignment(M)
    grid = _level_grid(st)
    adj = collections.defaultdict(list)
    for k in net["conduits"]:
        adj[k["start_node"]].append(k["stop_node"])
        adj[k["stop_node"]].append(k["start_node"])
    allg = sorted(v["ground"] for v in nodes.values() if v.get("ground") is not None)
    med = allg[len(allg) // 2] if allg else None
    out = {}
    for a, b in zip(ra, cb):
        d = M[a, b]
        if d >= big:
            continue
        n = gen[rows[a]]
        lab, lx, ly = labels[cols[b]]
        ng = [nodes[m]["ground"] for m in adj[n] if nodes.get(m, {}).get("ground") is not None]
        ref, tol = (sum(ng) / len(ng), 3.0) if ng else (med, 20.0)
        gl = None
        best = None
        cx, cy = int(lx // SUGGEST_GL_M), int(ly // SUGGEST_GL_M)
        for v, gx, gy in (q for i in (-1, 0, 1) for j in (-1, 0, 1) for q in grid.get((cx + i, cy + j), ())):
            dd = math.hypot(gx - lx, gy - ly)
            if dd <= SUGGEST_GL_M and ref is not None and abs(v - ref) <= tol and (best is None or dd < best[0]):
                best = (dd, v, gx, gy)
        if best:
            gl = {"value": best[1], "xy": [best[2], best[3]]}
        out[n] = {"label": lab, "d": round(float(d), 1), "lxy": [lx, ly], "gl": gl}
    return out


def label_levels(st, radius=SUGGEST_RADIUS_M):
    """Manholes whose GL is missing or was interpolated, but whose own label is written in the drawing (within
    radius) with a level next to it (within SUGGEST_GL_M, fitting the neighbours): {manhole: (GL, label distance)}.
    Typical after 'अपने-आप सुधार' filled levels before the label suggestions were applied."""
    nodes = st["net"]["nodes"]
    want = {n.upper(): n for n, v in nodes.items() if v.get("xy") and
            (v.get("ground") is None or "interpolated" in (v.get("gl_source") or ""))}
    if not want:
        return {}
    pos = collections.defaultdict(list)
    for t in _texts(st):
        m = ID_TEXT.match(t[2])
        if m:
            lab = f"{m.group(1).upper()}-{m.group(2)}".upper()
            if lab in want:
                pos[want[lab]].append((t[0], t[1]))
    adj = collections.defaultdict(list)
    for k in st["net"]["conduits"]:
        adj[k["start_node"]].append(k["stop_node"])
        adj[k["stop_node"]].append(k["start_node"])
    grid = _level_grid(st)
    out = {}
    for n, P in pos.items():
        x, y = nodes[n]["xy"]
        d, (lx, ly) = min((math.hypot(px - x, py - y), (px, py)) for px, py in P)
        if d > radius:
            continue
        ng = [nodes[m]["ground"] for m in adj[n] if m != n and nodes.get(m, {}).get("ground") is not None
              and "interpolated" not in (nodes[m].get("gl_source") or "")]
        if not ng:
            continue
        ref = sum(ng) / len(ng)
        cx, cy = int(lx // SUGGEST_GL_M), int(ly // SUGGEST_GL_M)
        best = None
        for v, gx, gy in (q for i in (-1, 0, 1) for j in (-1, 0, 1) for q in grid.get((cx + i, cy + j), ())):
            dd = math.hypot(gx - lx, gy - ly)
            if dd <= SUGGEST_GL_M and abs(v - ref) <= 3.0 and (best is None or dd < best[0]):
                best = (dd, v)
        if best:
            out[n] = (best[1], round(d, 1))
    return out


def _apply_suggestion(st, n, s, tn, tc):
    nodes = st["net"]["nodes"]
    if s["label"] in nodes:
        raise ValueError(f"'{s['label']}' नाम का manhole पहले से है")
    _apply1(st, {"op": "rename", "mh": n, "to": s["label"]}, tn, tc)
    st["edits"][-1]["change"] = "label (suggested)"
    st["edits"][-1]["detail"] += f" (drawing label {s['d']:.1f} m from the symbol)"
    v = nodes[s["label"]]
    det = f"{s['d']:.1f} m from the symbol"
    guessed = v.get("ground") is None or "interpolated" in (v.get("gl_source") or "")
    if s.get("gl") and guessed:                       # the drawing's level beats a level interpolated by repair
        old = v.get("ground")
        v["ground"] = s["gl"]["value"]
        v["gl_source"] = "text next to the suggested label - check"
        _log(st, "GL (suggested)", s["label"], f"{'-' if old is None else f'{old} (interpolated)'} -> {v['ground']}")
        det += f"; GL {v['ground']} (text next to the label)"
    st["ex_issues"].append({"type": SUGGESTED, "item": s["label"], "x": v["xy"][0], "y": v["xy"][1], "detail": det})


# ---------------------------------------------------------------- data for the page
def page_data(st, full=True, touched=None):
    """Everything the page draws: nodes, conduits (lat / lon), problems, totals. With full=False only the
    touched nodes / conduits (None = deleted)."""
    to_ll = converters(st)[0]
    net = st["net"]
    outs = set(net["outfalls"])

    def node(n):
        v = net["nodes"][n]
        p = to_ll([v["xy"]])[0] if v.get("xy") else None
        return {"latlng": p, "gl": v.get("ground"), "src": v.get("gl_source") or "", "out": n in outs,
                "il": v.get("invert_drawing")}

    def cond(k):
        pts = k.get("vertices") or [net["nodes"][n]["xy"] for n in (k["start_node"], k["stop_node"])
                                    if net["nodes"].get(n, {}).get("xy")]
        return {"id": k["id"], "label": k["label"], "from": k["start_node"], "to": k["stop_node"],
                "len": round(k["length_m"] or 0.0, 2), "pts": to_ll(pts)}
    iss = issues(st)
    ll = to_ll([[i["x"], i["y"]] if i.get("x") is not None else [0, 0] for i in iss])
    ilist = [[i["key"], i["type"], str(i["item"]), p[0] if i.get("x") is not None else None,
              p[1] if i.get("x") is not None else None, i.get("detail") or "", i["reviewed"], i["low"]]
             for i, p in zip(iss, ll)]
    parts = repair._parts(_tuples(net))
    summ = {"manholes": len(net["nodes"]), "conduits": len(net["conduits"]),
            "length": round(sum(k["length_m"] or 0 for k in net["conduits"]), 1),
            "parts": len(set(parts.values())), "outfalls": net["outfalls"],
            "no_gl": sum(1 for v in net["nodes"].values() if v.get("ground") is None), "edits": len(st["edits"]),
            "undo": len(_UNDO[st["stem"]])}
    sug = suggestions(st)
    sl = to_ll([s["lxy"] for s in sug.values()])
    out = {"ok": True, "kind": "dxf", "name": st["stem"], "issues": ilist, "summary": summ,
           "local": not st.get("epsg"), "epsg": st.get("epsg"), "dxf": st["dxf"],
           "suggest": {n: [s["label"], s["d"], s["gl"]["value"] if s["gl"] else None, p[0], p[1]]
                       for (n, s), p in zip(sug.items(), sl)},
           "label_levels": len(label_levels(st))}
    if full:
        # nodes in drawing order; lat / lon of all of them in one transform
        names = [n for n in net["nodes"] if net["nodes"][n].get("xy")]
        pts = to_ll([net["nodes"][n]["xy"] for n in names])
        out["nodes"] = {n: {"latlng": p, "gl": net["nodes"][n].get("ground"), "src": net["nodes"][n].get("gl_source") or "",
                            "out": n in outs, "il": net["nodes"][n].get("invert_drawing")} for n, p in zip(names, pts)}
        out["conduits"] = [cond(k) for k in net["conduits"]]
    else:
        tn, tc = touched
        out["nodes"] = {n: (node(n) if n in net["nodes"] else None) for n in tn}
        by_id = {k["id"]: k for k in net["conduits"]}
        out["conduits_upd"] = {str(i): (cond(by_id[i]) if i in by_id else None) for i in tc}
    return out


# ---------------------------------------------------------------- edits
def _plen(pts):
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def _snapshot(st):
    _UNDO[st["stem"]].append(json.dumps({"net": st["net"], "reviewed": st["reviewed"], "ex_issues": st["ex_issues"],
                                         "edits": st["edits"], "next_id": st["next_id"], "epsg": st.get("epsg"),
                                         "shift": st.get("shift"), "origin": st.get("origin")}, separators=(",", ":")))


def place(st, frm, to, points=()):
    """The whole network moved on the map: the drawing's point now shown at frm (lat, lon) goes to `to` - a shift in
    metres (a drawing in local coordinates: placed in the UTM zone of `to`). Lengths and levels unchanged. One undo
    step. Returns `points` (lat, lon - e.g. OHTs placed on the network) moved with it."""
    from . import geo
    to_xy = converters(st)[1]
    raw = to_xy([frm])[0]
    pts = to_xy(list(points))
    _snapshot(st)
    epsg = st.get("epsg") or geo.utm_epsg(to[1], to[0])
    st["epsg"], st["shift"] = int(epsg), [0.0, 0.0]
    t = converters(st)[1]([to])[0]                     # the place in the EPSG's metres
    st["shift"] = [round(t[0] - raw[0], 3), round(t[1] - raw[1], 3)]
    _log(st, "placed on the map", "network", f"EPSG {st['epsg']}, drawing shifted {st['shift'][0]:+.1f} m E, "
                                             f"{st['shift'][1]:+.1f} m N")
    store(st)
    return converters(st)[0](pts)


def undo(st):
    if not _UNDO[st["stem"]]:
        raise ValueError("पीछे जाने को कुछ नहीं")
    st.update(json.loads(_UNDO[st["stem"]].pop()))
    store(st)


def _log(st, op, item, detail=""):
    st["edits"].append({"time": time.strftime("%d-%m-%Y %H:%M:%S"), "change": op, "item": item, "detail": detail})


def _review(st, mh, types):
    rev = set(st["reviewed"])
    for i in st["ex_issues"]:
        if i["type"] in types and str(i["item"]) == mh:
            rev.add(_key(i))
    st["reviewed"] = sorted(rev)


def apply(st, ops):
    """Corrections from the page, in order; one undo step for the whole list. Returns (touched node labels,
    touched conduit ids). Raises ValueError (nothing changed) when an operation is not possible."""
    _snapshot(st)
    tn, tc = set(), set()
    try:
        for op in ops:
            _apply1(st, op, tn, tc)
    except Exception:
        st.update(json.loads(_UNDO[st["stem"]].pop()))           # back to the state before this list
        raise
    store(st)
    return tn, tc


def _apply1(st, op, tn, tc):
    net = st["net"]
    nodes, conds = net["nodes"], net["conduits"]
    by_id = {k["id"]: k for k in conds}
    kind = op.get("op")

    def need_mh(n):
        if n not in nodes:
            raise ValueError(f"manhole '{n}' नहीं है")
        return nodes[n]

    def attached(n):
        return [k for k in conds if n in (k["start_node"], k["stop_node"])]

    if kind == "set_gl":
        mh = op["mh"]
        v = need_mh(mh)
        old = v.get("ground")
        g = op.get("gl")
        v["ground"] = None if g in (None, "") else round(float(g), 3)
        v["gl_source"] = USER_GL if v["ground"] is not None else ""
        _review(st, mh, GL_TYPES)
        _log(st, "GL", mh, f"{old if old is not None else '-'} -> {v['ground'] if v['ground'] is not None else '-'}")
        tn.add(mh)
    elif kind == "rename_prefix":
        # the names of a network imported before, to another prefix at once (user request 30-Oct-2026): every
        # junction (kind "node") / pipe ("pipe") label <from><digit>... -> <to><digit>...; a new name already taken
        # by another: nothing changes
        old, new, what = str(op.get("from") or ""), str(op.get("to") or "").strip(), op.get("kind")
        if what not in ("node", "pipe") or not old or not new or new == old:
            return
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_/-]{0,7}", new):
            raise ValueError(f"prefix '{new}' नहीं चलेगा: अक्षर से शुरू, 8 तक अक्षर / अंक / - _ /")
        rx = re.compile(re.escape(old) + r"(?=\d)")
        labels = list(nodes) if what == "node" else [k["label"] for k in conds]
        ren = {x: new + x[len(old):] for x in labels if rx.match(x)}
        if not ren:
            raise ValueError(f"'{old}' से शुरू होने वाला कोई नाम नहीं")
        clash = (set(ren.values()) & (set(labels) - set(ren))) or (len(set(ren.values())) < len(ren))
        if clash:
            raise ValueError(f"नए नामों में से कुछ पहले से हैं (जैसे {sorted(set(ren.values()) & set(labels))[:3]}) - कुछ नहीं बदला")
        if what == "node":
            net["nodes"] = {ren.get(n, n): v for n, v in nodes.items()}
            for k in conds:
                k["start_node"], k["stop_node"] = ren.get(k["start_node"], k["start_node"]), ren.get(k["stop_node"], k["stop_node"])
            net["outfalls"] = [ren.get(o, o) for o in net["outfalls"]]
            tn.update(ren)
            tn.update(ren.values())
            tc.update(k["id"] for k in conds)
        else:
            for k in conds:
                if k["label"] in ren:
                    k["label"] = ren[k["label"]]
                    tc.add(k["id"])
        # the drawing's problems and the ones marked as checked: by the new names
        ks = {}
        for i in st["ex_issues"]:
            parts = [x.strip() for x in str(i["item"]).split(" - ")]
            item = " - ".join(ren.get(x, x) for x in parts)
            if item != str(i["item"]):
                ks[_key(i)] = f"{i['type']}|{item}"
                i["item"] = item
        st["reviewed"] = [ks.get(r, r) for r in st["reviewed"]]
        pre = dict(st.get("prefix") or {})
        if new == {"node": "MH-", "pipe": "CO-"}[what]:
            pre.pop(what, None)
        else:
            pre[what] = new
        st["prefix"] = pre
        _log(st, "names", f"{old}* -> {new}*", f"{len(ren)} {'junction' if what == 'node' else 'pipe'} names")
    elif kind == "rename":
        old, new = op["mh"], str(op["to"]).strip()
        need_mh(old)
        if not new or new == old:
            return
        if new in nodes:
            raise ValueError(f"'{new}' नाम का manhole पहले से है")
        nodes[new] = nodes.pop(old)
        for k in attached(old):
            for end in ("start_node", "stop_node"):
                if k[end] == old:
                    k[end] = new
            tc.add(k["id"])
        net["outfalls"] = [new if o == old else o for o in net["outfalls"]]
        for i in st["ex_issues"]:
            if i["type"] == "near-miss gap":
                i["item"] = " - ".join(new if p.strip() == old else p.strip() for p in str(i["item"]).split(" - "))
            elif str(i["item"]) == old:
                i["item"] = new
        st["reviewed"] = [r.replace(f"|{old}", f"|{new}") if r.endswith(f"|{old}") else r for r in st["reviewed"]]
        _review(st, new, LABEL_TYPES)
        _log(st, "label", old, f"-> {new}")
        tn.update([old, new])
    elif kind == "outfall":
        mh = op["mh"]
        need_mh(mh)
        on = bool(op.get("on"))
        net["outfalls"] = [o for o in net["outfalls"] if o != mh] + ([mh] if on else [])
        _log(st, "outfall", mh, "set" if on else "removed")
        tn.add(mh)
    elif kind == "delete_conduit":
        k = by_id.get(int(op["id"]))
        if k is None:
            raise ValueError("sewer नहीं मिला")
        conds.remove(k)
        _log(st, "sewer deleted", k["label"], f"{k['start_node']} - {k['stop_node']}, {k['length_m'] or 0:.1f} m")
        tc.add(k["id"])
        tn.update([k["start_node"], k["stop_node"]])
    elif kind == "delete_mh":
        mh = op["mh"]
        need_mh(mh)
        gone = attached(mh)
        for k in gone:
            conds.remove(k)
            tc.add(k["id"])
            tn.update([k["start_node"], k["stop_node"]])
        del nodes[mh]
        net["outfalls"] = [o for o in net["outfalls"] if o != mh]
        _log(st, "manhole deleted", mh, f"with {len(gone)} sewer(s): {', '.join(k['label'] for k in gone)}")
        tn.add(mh)
    elif kind == "connect":
        a, b = op["a"], op["b"]
        pa, pb = need_mh(a)["xy"], need_mh(b)["xy"]
        if a == b:
            raise ValueError("एक ही manhole")
        if _connected(net, a, b):
            raise ValueError(f"{a} और {b} पहले से जुड़े हैं")
        lab = str(op.get("label") or "").strip() or label_namer([k["label"] for k in conds], (st.get("prefix") or {}).get("pipe", "CO-"))()
        k = {"label": lab, "start_node": a, "stop_node": b, "length_m": round(math.dist(pa, pb), 3),
             "vertices": [list(pa), list(pb)], "id": st["next_id"]}
        st["next_id"] += 1
        conds.append(k)
        _log(st, "sewer added", lab, f"{a} - {b}, {k['length_m']:.1f} m (straight)")
        tc.add(k["id"])
        tn.update([a, b])
    elif kind == "merge":
        keep, drop = op["keep"], op["drop"]
        vk, vd = need_mh(keep), need_mh(drop)
        if keep == drop:
            raise ValueError("एक ही manhole")
        for k in attached(drop):
            tc.add(k["id"])
            if keep in (k["start_node"], k["stop_node"]):
                conds.remove(k)                                  # the sewer between the two: gone
                continue
            for end, vi in (("start_node", 0), ("stop_node", -1)):
                if k[end] == drop:
                    k[end] = keep
                    if k["vertices"]:
                        k["vertices"][vi] = list(vk["xy"])
            k["length_m"] = round(_plen(k["vertices"]), 3) if len(k["vertices"]) > 1 else k["length_m"]
            tn.update([k["start_node"], k["stop_node"]])
        if vk.get("ground") is None and vd.get("ground") is not None:
            vk["ground"], vk["gl_source"] = vd["ground"], vd.get("gl_source") or ""
        if drop in net["outfalls"] and keep not in net["outfalls"]:
            net["outfalls"].append(keep)
        net["outfalls"] = [o for o in net["outfalls"] if o != drop]
        del nodes[drop]
        _log(st, "manholes merged", drop, f"into {keep} ({math.dist(vk['xy'], vd['xy']):.2f} m apart)")
        tn.update([keep, drop])
    elif kind == "split":
        k = by_id.get(int(op["id"]))
        if k is None:
            raise ValueError("sewer नहीं मिला")
        p = converters(st)[1]([op["latlng"]])[0]
        P = k["vertices"] if len(k["vertices"]) > 1 else [nodes[k["start_node"]]["xy"], nodes[k["stop_node"]]["xy"]]
        best = None
        for i in range(len(P) - 1):
            a, b = P[i], P[i + 1]
            dx, dy = b[0] - a[0], b[1] - a[1]
            L2 = dx * dx + dy * dy
            t = 0.0 if not L2 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
            q = [a[0] + t * dx, a[1] + t * dy]
            d = math.dist(p, q)
            if best is None or d < best[0]:
                best = (d, i, q)
        _, i, q = best
        first, second = [list(x) for x in P[:i + 1]] + [q], [q] + [list(x) for x in P[i + 1:]]
        if _plen(first) < 0.05 or _plen(second) < 0.05:
            raise ValueError("sewer के सिरे पर नहीं तोड़ सकते - वहाँ manhole पहले से है")
        mh = str(op.get("label") or "").strip() or label_namer(list(nodes), (st.get("prefix") or {}).get("node", "MH-"))()
        if mh in nodes:
            raise ValueError(f"'{mh}' नाम का manhole पहले से है")
        nodes[mh] = {"xy": [round(q[0], 3), round(q[1], 3)], "ground": None, "gl_source": ""}
        lab2 = label_namer([c["label"] for c in conds], (st.get("prefix") or {}).get("pipe", "CO-"))()
        tot = k["length_m"] or _plen(P)
        f1 = _plen(first) / (_plen(P) or 1.0)
        k2 = {"label": lab2, "start_node": mh, "stop_node": k["stop_node"], "length_m": round(tot * (1 - f1), 3),
              "vertices": second, "id": st["next_id"]}
        st["next_id"] += 1
        k["stop_node"], k["vertices"], k["length_m"] = mh, first, round(tot * f1, 3)
        conds.append(k2)
        _log(st, "sewer split", k["label"], f"new manhole {mh} (no GL yet); second part {lab2}")
        tc.update([k["id"], k2["id"]])
        tn.update([mh, k["start_node"], k2["stop_node"]])
    elif kind == "move":
        mh = op["mh"]
        v = need_mh(mh)
        p = converters(st)[1]([op["latlng"]])[0]
        old = v["xy"]
        v["xy"] = p
        for k in attached(mh):
            for end, vi in (("start_node", 0), ("stop_node", -1)):
                if k[end] == mh and k["vertices"]:
                    k["vertices"][vi] = list(p)
            if len(k["vertices"]) > 1:
                k["length_m"] = round(_plen(k["vertices"]), 3)
            tc.add(k["id"])
        _log(st, "manhole moved", mh, f"{math.dist(old, p):.2f} m" if old else "")
        tn.add(mh)
    elif kind == "gl_from_labels":
        for n, (g, d) in label_levels(st).items():
            v = nodes[n]
            old = v.get("ground")
            v["ground"] = g
            v["gl_source"] = "text next to the manhole's label - check"
            _log(st, "GL (drawing, next to the label)", n,
                 f"{'-' if old is None else f'{old} (interpolated)'} -> {g} (label {d:.1f} m from the symbol)")
            tn.add(n)
    elif kind == "apply_suggestions":
        sug = suggestions(st)
        want = op.get("mh")
        todo = [(n, s) for n, s in sug.items() if want is None or n in (want if isinstance(want, list) else [want])]
        if want is not None and not todo:
            raise ValueError("इस manhole के लिए सुझाव नहीं")
        for n, s in todo:
            if s["label"] in nodes:
                continue                                         # taken meanwhile (only possible in a list)
            _apply_suggestion(st, n, s, tn, tc)
    elif kind == "review":
        rev = set(st["reviewed"])
        (rev.add if op.get("ok", True) else rev.discard)(op["key"])
        st["reviewed"] = sorted(rev)
        _log(st, "checked" if op.get("ok", True) else "check undone", op["key"])
    else:
        raise ValueError(f"unknown change '{kind}'")


def auto_repair(st, join_gap_m=1.0, tjoint_m=0.5, loops=True, gl=True):
    """repair.repair on the working network (one undo step); every repair is logged. Returns the repair rows."""
    _snapshot(st)
    net, rows = repair.repair(_tuples(st["net"]), {"problems": st["ex_problems"]}, st["net"]["outfalls"],
                              join_gap_m=join_gap_m, tjoint_m=tjoint_m, loops=loops, gl=gl)
    nj = _net_json(net)
    for k in nj["conduits"]:
        if "id" not in k:
            k["id"] = st["next_id"]
            st["next_id"] += 1
    st["net"] = nj
    for r in rows:
        _log(st, "auto: " + r["repair"], r["item"], str(r.get("detail") or ""))
    store(st)
    return rows


def save_network(st):
    """The corrected network as CSV (manholes / conduits, as dxf_extract writes them - for zoning / design and
    --csv) and the list of the changes made (<stem>_network_edits.csv). Returns the paths."""
    import csv
    from . import network
    folder = os.path.join(st["_root"], st["stem"])
    os.makedirs(folder, exist_ok=True)
    paths = {"manholes": os.path.join(folder, f"{st['stem']}_network_manholes.csv"),
             "conduits": os.path.join(folder, f"{st['stem']}_network_conduits.csv"),
             "edits": os.path.join(folder, f"{st['stem']}_network_edits.csv")}
    if st.get("saved_edits") == len(st["edits"]) and all(os.path.isfile(f) for f in paths.values()):
        return dict(paths, unchanged=True)       # nothing changed: the files (and the zoning made from them) stay
    net = _tuples(st["net"])
    f_mh, f_co = network.write_csv(net, os.path.join(folder, f"{st['stem']}_network_manholes.csv"),
                                   os.path.join(folder, f"{st['stem']}_network_conduits.csv"))
    f_ed = os.path.join(folder, f"{st['stem']}_network_edits.csv")
    with open(f_ed, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["Time", "Change", "Item", "Detail"])
        for e in st["edits"]:
            w.writerow([e["time"], e["change"], e["item"], e["detail"]])
    st["saved"] = time.strftime("%d-%m-%Y %H:%M")
    st["saved_edits"] = len(st["edits"])          # changes after this: the CSV files are older than the network
    store(st)
    return {"manholes": f_mh, "conduits": f_co, "edits": f_ed}
