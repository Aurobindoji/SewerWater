"""netedit: the drawing - its layers, a layer or the whole network previewed, the import."""
import collections
import json
import os
import re
import time
from sewer_app.net import repair
from .common import EX_TYPES, _TEXTS, _UNDO
from .coords import converters
from .files import store
from .suggest import _LEVELS
from .texts import _f, _net_json, _tuples


# ---------------------------------------------------------------- the drawing
_INV = {}                       # (path, mtime) -> inventory of the drawing (layers, lines, texts, inserts, points)


def _inventory(path):
    """The drawing's entities, read once per file version (the layer table and its previews)."""
    from sewer_app.net import dxf_inspect as di
    key = (os.path.abspath(path), os.path.getmtime(path))
    if key not in _INV:
        doc, _ = di.load(path)
        _INV.clear()                                    # one drawing at a time
        _INV[key] = di.inventory(doc.modelspace())
    return _INV[key]


def dxf_net_preview(path, pipe_layers, mh_layers=(), level_layers=(), epsg=32644, z_mode="auto",
                    node_prefix=None, pipe_prefix=None):
    """The network the import would make from these layers - for the map only, nothing saved (as the water page's,
    23-Nov-2026). The drawing is not read again (_inventory); the invert levels are left out (not shown). ->
    {nodes [[lat, lon, name, ground, sewers]], pipes [[part, [[lat, lon], ...]]], summary, problems {kind: count},
    lines (the extraction's summary), local}; part 1 = the largest connected part."""
    from sewer_app.net import dxf_extract
    from sewer_app.core import network
    ex = dxf_extract.extract(path, list(pipe_layers), list(mh_layers), list(level_layers), z_mode=z_mode,
                             node_prefix=node_prefix, pipe_prefix=pipe_prefix, inv=_inventory(path))
    net = _net_json(network.from_extract(ex))
    st = {"epsg": int(epsg) if epsg else None}
    xy = [v["xy"] for v in net["nodes"].values() if v.get("xy")]
    if st["epsg"] is None:                                       # local drawing: around the middle, as the import
        st["origin"] = [sum(p[0] for p in xy) / len(xy), sum(p[1] for p in xy) / len(xy)] if xy else [0.0, 0.0]
    to_ll = converters(st)[0]
    part = repair._parts(_tuples(net))
    deg = collections.Counter()
    for k in net["conduits"]:
        deg[k["start_node"]] += 1
        deg[k["stop_node"]] += 1
    names = [n for n in net["nodes"] if net["nodes"][n].get("xy")]
    pts = to_ll([net["nodes"][n]["xy"] for n in names])
    nodes = [[p[0], p[1], n, net["nodes"][n].get("ground"), deg[n]] for n, p in zip(names, pts)]
    flat, cut = [], []
    for k in net["conduits"]:
        q = k.get("vertices") or [net["nodes"][n]["xy"] for n in (k["start_node"], k["stop_node"])
                                  if net["nodes"].get(n, {}).get("xy")]
        flat += q
        cut.append(len(q))
    ll, pipes, i = to_ll(flat) if flat else [], [], 0
    for k, c in zip(net["conduits"], cut):
        pipes.append([part.get(k["start_node"], 0), [[round(a, 7), round(b, 7)] for a, b in ll[i:i + c]]])
        i += c
    joined = {n for n in net["nodes"] if deg[n]}
    n_parts = len({part[n] for n in joined if n in part})
    summ = {"manholes": len(net["nodes"]), "sewers": len(net["conduits"]),
            "length": round(sum(k["length_m"] or 0 for k in net["conduits"]), 1),
            "parts": n_parts, "ends": sum(1 for n in net["nodes"] if deg[n] == 1),
            # a sewer is a tree: pipes - manholes + parts = the loops to cut
            "loops": max(0, sum(1 for k in net["conduits"] if k["start_node"] != k["stop_node"]) - len(joined) + n_parts),
            "no_gl": sum(1 for v in net["nodes"].values() if v.get("ground") is None)}
    return {"ok": True, "nodes": nodes, "pipes": pipes, "summary": summ, "lines": ex["summary"],
            "problems": dict(collections.Counter(p["Problem"] for p in ex["problems"])), "local": not st["epsg"]}


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
    from sewer_app.net import dxf_inspect as di
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
    from sewer_app.net import dxf_extract, dxf_inspect as di
    from sewer_app.core import network
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
