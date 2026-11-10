"""
dxf_extract.py - take ONLY the minimum data for a sewer design out of a DXF / DWG (read-only):

  manholes : label, X, Y, ground level (GL)
  conduits : from manhole -> to manhole, drawn length, polyline vertices (X, Y)

    python dxf_extract.py "oakdale.dxf" --pipe-layers PIPE0,PIPE1,PIPE2
    python dxf_extract.py "...\\oakdale.dxf" --pipe-layers PIPE0,PIPE1,PIPE2 --mh-layers MH- --level-layers MH-

Identification (same logic as dxf_inspect.py, run that first to choose the layers):
  - pipe lines   : LINE / LWPOLYLINE / POLYLINE on --pipe-layers; ends joined within --tol (m)
  - manholes     : the line ends / junctions (one manhole per node), AND manholes drawn ON a continuous
                   line: a manhole symbol (block / circle on --mh-layers) or a left-over MH label (no line
                   end at its usual offset) within --mid-snap m of the inside of a line cuts the line
                   there (--no-midline switches this off); each cut is listed under Problems
  - MH label     : ID text (e.g. MH-1173) on --mh-layers, matched ONE-TO-ONE to the nodes after removing the
                   usual text-to-symbol offset (learnt from isolated manholes); else MH-G<n> (NODE_PREFIX)
  - GL           : level text (e.g. '85.41 m') on --level-layers, matched one-to-one in the same way
                   (default: the level-like layer that covers most nodes); else Z of the line end if
                   the drawing is 3D; else empty (listed under Problems)
  - conduit label: CO-<n> in drawing order (PIPE_PREFIX); direction = as drawn (the design orients it from the outfall)
Diameters, slopes, flows and all other layers are NOT taken.

Output (output\\dxf_extract\\):
  <name>_manholes.csv   Label, X, Y, GL, GL_source
  <name>_conduits.csv   Label, From, To, Length_m, Vertices ("x y;x y;...")
  <name>_extract.xlsx   the same two tables + Problems (no GL, no / duplicate label, gaps, T-joints, loops)
Nothing is written into the drawing.
"""

import os
import sys
import csv
import time
import argparse
import collections
import math

from . import dxf_inspect as di

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))      # the sewer_app folder
OUT_DIR = os.path.join(BASE, "output", "dxf_extract")
PIPE_PREFIX = "CO-"               # sewer conduits are CO-<n> (the water copy: P-<n>)
LENGTH_NEAR_M = 6.0               # a pipe's length is written within this of the pipe ...
LENGTH_TOL_M = 0.5                # ... and equal to its length within this (written to 0.1 / 1 m) ...
LENGTH_MID = (0.2, 0.8)           # ... along its middle (share of the pipe's length): a GL is written at a junction
NODE_PREFIX = "MH-G"              # a manhole without a drawing label: MH-G<n> (the water copy: J-G<n>)


def split_at_midline_manholes(lines, points, tol, snap):
    """A manhole drawn ON a continuous pipe line (not at its end) would otherwise be lost: the line
    runs through it and only its two ends become manholes. points = [(x, y, source)] of manhole
    positions (symbols, or label texts moved back by their learnt offset). Each point within `snap` m
    of the INSIDE of a line (more than tol from both its ends) cuts that line there. Returns
    (new lines, list of cuts (x, y, source, handle, distance))."""
    import math
    cell = max(snap * 4, 10.0)
    grid = collections.defaultdict(list)                    # segment bins
    for li, ln in enumerate(lines):
        if ln["closed"]:
            continue
        P = ln["pts"]
        for si in range(len(P) - 1):
            (x1, y1), (x2, y2) = P[si][:2], P[si + 1][:2]
            for i in range(int(math.floor((min(x1, x2) - snap) / cell)), int(math.floor((max(x1, x2) + snap) / cell)) + 1):
                for j in range(int(math.floor((min(y1, y2) - snap) / cell)), int(math.floor((max(y1, y2) + snap) / cell)) + 1):
                    grid[(i, j)].append((li, si))
    cuts = collections.defaultdict(list)                    # line index -> [(chainage, x, y, src)]
    log = []
    for x, y, src in points:
        best = None
        for li, si in grid.get((int(math.floor(x / cell)), int(math.floor(y / cell))), ()):
            P = lines[li]["pts"]
            d, t = di.point_seg_dist((x, y), P[si], P[si + 1])
            if d <= snap and (best is None or d < best[0]):
                best = (d, li, si, t)
        if best is None:
            continue
        d, li, si, t = best
        P = lines[li]["pts"]
        px, py = P[si][0] + t * (P[si + 1][0] - P[si][0]), P[si][1] + t * (P[si + 1][1] - P[si][1])
        if min(math.hypot(px - P[0][0], py - P[0][1]), math.hypot(px - P[-1][0], py - P[-1][1])) <= max(tol, 1.0):
            continue                                        # at a line end = already a manhole
        ch = sum(di.seg_len(P[k], P[k + 1]) for k in range(si)) + t * di.seg_len(P[si], P[si + 1])
        if any(abs(ch - c[0]) <= max(tol, 1.0) for c in cuts[li]):
            continue                                        # same place already cut
        cuts[li].append((ch, px, py, src))
        log.append((round(px, 3), round(py, 3), src, lines[li]["handle"], round(d, 2)))
    out = []
    for li, ln in enumerate(lines):
        if li not in cuts:
            out.append(ln)
            continue
        P, z = ln["pts"], ln["pts"][0][2]
        segs_ch = [0.0]
        for k in range(len(P) - 1):
            segs_ch.append(segs_ch[-1] + di.seg_len(P[k], P[k + 1]))
        cs = sorted(cuts[li])
        pieces, cur, ci = [], [P[0]], 0
        for k in range(len(P) - 1):
            while ci < len(cs) and cs[ci][0] <= segs_ch[k + 1] + 1e-9:
                # the Z there along the segment (a 3D line: its own height - was the line's first Z, 22-Oct-2026)
                sl = segs_ch[k + 1] - segs_ch[k]
                f = (cs[ci][0] - segs_ch[k]) / sl if sl > 0 else 0.0
                cp = (cs[ci][1], cs[ci][2], P[k][2] + f * (P[k + 1][2] - P[k][2]) if len(P[k]) > 2 else z)
                cur.append(cp)
                pieces.append(cur)
                cur, ci = [cp], ci + 1
            cur.append(P[k + 1])
        pieces.append(cur)
        clean = []
        for pc in pieces:                               # drop repeated points (cut exactly at a vertex)
            q = [pc[0]]
            for r_ in pc[1:]:
                if di.seg_len(q[-1], r_) > 1e-6:
                    q.append(r_)
            clean.append(q)
        pieces = clean
        for n_, pc in enumerate(pieces):
            if len(pc) >= 2:
                out.append(dict(ln, pts=pc, len=sum(di.seg_len(pc[q], pc[q + 1]) for q in range(len(pc) - 1)),
                                handle=f"{ln['handle']}/{n_ + 1}"))
    return out, log


def _network(path, pipe_layers, mh_layers, tol, level_radius, mid_snap, midline):
    """The drawing read and its network built (the first part of extract): (layers, texts, inserts, points, pipe
    layers, mh layers, nodes, edges, network checks, used nodes, mid-line log)."""
    doc, _ = di.load(path)
    layers, lines, texts, inserts, points = di.inventory(doc.modelspace())
    pipe_layers = [s.strip() for s in pipe_layers if s.strip()]
    missing = [l for l in pipe_layers if l not in layers]
    if missing:
        raise ValueError(f"Layer(s) not in the drawing: {', '.join(missing)}. Layers: {', '.join(sorted(layers))}")
    pl = [ln for ln in lines if ln["layer"] in pipe_layers]
    mh_lay = set(s.strip() for s in mh_layers if s.strip())

    # ---- manholes drawn ON a continuous line: cut the line there (symbols on mh_layers, and MH
    #      labels left over after matching, moved back by the learnt label offset)
    mid_log = []
    if midline:
        nodes0, _, _ = di.build_network(pl, tol)
        di.labels_near_nodes(nodes0, texts, level_radius, mh_lay or None)
        inf0 = getattr(di.labels_near_nodes, "info", {})
        cand = [(q["x"], q["y"], f"symbol {q.get('name') or q.get('kind')}")
                for q in list(inserts) + list(points) if mh_lay and q["layer"] in mh_lay]
        # sewer_app (12-Oct-2026): when the drawing HAS manhole symbols, they alone mark the manholes on a line -
        # a label that found no line end is then a matching problem, not a manhole (oakdale.dxf: 1035 false
        # manholes were made from such labels). Without symbols, left-over labels are used, the learnt offset
        # scaled by the text height when the offsets are in text heights.
        if not cand:
            lab_items = [(t["x"], t["y"], v, t.get("h") or 1.0) for t in texts if (not mh_lay or t["layer"] in mh_lay)
                         for kind, v in di.classify(t["text"]) if kind == "id"]
            g0 = di.Grid(max(tol, 0.5))
            for n in nodes0:
                if n["deg"] > 0:
                    g0.add(n["x"], n["y"], n["id"])
            offs = [(ox, oy) for ox, oy, _ in inf0.get("offsets", [])] or [(0.0, 0.0)]
            scale = inf0.get("offset_unit") == "text height"
            for x, y, v, h in lab_items:
                u = h if scale else 1.0
                # a label is 'left over' when no line end lies at any learnt offset from it
                if any(g0.near(x - ox * u, y - oy * u, mid_snap) for ox, oy in offs):
                    continue
                cand += [(x - ox * u, y - oy * u, f"label {v}") for ox, oy in offs[:1]]
        pl, mid_log = split_at_midline_manholes(pl, cand, tol, mid_snap)
    nodes, edges, _ = di.build_network(pl, tol)
    if not edges:
        raise ValueError("No lines on the pipe layers.")
    chk = di.network_checks(nodes, edges, tol)
    used = [n for n in nodes if n["deg"] > 0]
    return layers, texts, inserts, points, pipe_layers, mh_lay, nodes, edges, chk, used, mid_log


def length_texts(texts, edges, near=None):
    """Indexes of the decimal texts ("73.35m", "15.4") that are the LENGTH of the pipe they are written beside, not a
    ground level (user report 22-Oct-2026: a pipe length with decimals reads as a GL - with short pipes a whole layer
    of lengths could be taken for the GL layer): the nearest pipe within LENGTH_NEAR_M has that length (LENGTH_TOL_M)
    and the text is written along its middle (LENGTH_MID: not near a junction, where a GL is written - a GL of 73.2
    next to a 73 m pipe stays a GL)."""
    near = LENGTH_NEAR_M if near is None else near
    cell, grid, run = 25.0, collections.defaultdict(list), {}
    for k, e in enumerate(edges):
        if e["a"] == e["b"]:
            continue
        P = e["pts"]
        run[k] = [0.0]
        for j in range(len(P) - 1):
            run[k].append(run[k][-1] + math.dist(P[j][:2], P[j + 1][:2]))
            (x1, y1), (x2, y2) = P[j][:2], P[j + 1][:2]
            for gx in range(int((min(x1, x2) - near) // cell), int((max(x1, x2) + near) // cell) + 1):
                for gy in range(int((min(y1, y2) - near) // cell), int((max(y1, y2) + near) // cell) + 1):
                    grid[(gx, gy)].append((k, j))
    out = set()
    for i, t in enumerate(texts):
        v = next((v for kind, v in di.classify(t["text"]) if kind == "level"), None)
        if v is None:
            continue
        best = None
        for k, j in grid.get((int(t["x"] // cell), int(t["y"] // cell)), ()):
            P = edges[k]["pts"]
            d, f = di.point_seg_dist((t["x"], t["y"]), P[j], P[j + 1])
            if d <= near and (best is None or d < best[0]):
                best = (d, k, run[k][j] + f * (run[k][j + 1] - run[k][j]))
        if best:
            d, k, ch = best
            L = run[k][-1]
            if abs(v - edges[k]["len"]) <= LENGTH_TOL_M and L > 0 and LENGTH_MID[0] <= ch / L <= LENGTH_MID[1]:
                out.add(i)
    return out


def gl_options(path, pipe_layers, mh_layers=(), tol=0.5, level_radius=10.0, mid_snap=1.5, midline=True):
    """The layers the GL could come from, for the user to choose (user request 22-Oct-2026: 'स्क्रिप्ट विकल्प दे ... यूजर
    चुनकर कन्फर्म कर दे'): every layer with decimal texts - how many, how many of them are the lengths of their pipes
    (length_texts), the range / median of the others, how many junctions have one within level_radius, samples - and
    the guess (as extract: the level-like layer, without the lengths, near most junctions)."""
    _, texts, _, _, _, _, nodes, edges, _, used, _ = _network(path, pipe_layers, mh_layers, tol, level_radius,
                                                              mid_snap, midline)
    drop = length_texts(texts, edges)
    by = collections.defaultdict(list)
    for i, t in enumerate(texts):
        v = next((v for kind, v in di.classify(t["text"]) if kind == "level"), None)
        if v is not None:
            by[t["layer"]].append((i, v))
    rows = []
    for lay, items in by.items():
        keep = [(i, v) for i, v in items if i not in drop]
        g = di.Grid(max(level_radius, 1.0))
        for i, _ in keep:
            g.add(texts[i]["x"], texts[i]["y"], i)
        vals = sorted(v for _, v in keep)
        med = vals[len(vals) // 2] if vals else None
        rows.append({"layer": lay, "texts": len(items), "lengths": len(items) - len(keep),
                     "min": vals[0] if vals else None, "max": vals[-1] if vals else None, "median": med,
                     "near": sum(1 for n in used if g.near(n["x"], n["y"], level_radius)),
                     "level_like": bool(vals) and len(vals) >= 5 and med > 10 and
                     sum(1 for v in vals if abs(v - med) <= 15) >= 0.8 * len(vals),
                     "samples": [t for t, _ in collections.Counter(texts[i]["text"] for i, _ in keep).most_common(6)]})
    rows.sort(key=lambda r: (-r["level_like"], -r["near"], r["layer"]))
    guess = [rows[0]["layer"]] if rows and rows[0]["level_like"] and rows[0]["near"] else []
    # SEWER: the invert levels (user request 22-Oct-2026 - 'GL के लिए विकल्प दिखें और IL के लिए भी; IL सदैव GL से कम'):
    # per layer the texts marked IL / INV and how many of its values lie below the GL of their manhole (the guessed
    # GL layer's text nearest to it) - a layer mostly below the GL is an IL layer; one layer with GL and IL written
    # as plain numbers: the lower value at a manhole (split_gl_il)
    split = di.split_gl_il(nodes, texts, set(guess), level_radius) if guess else set()
    gtx = di.Grid(max(level_radius, 1.0))
    for i, t in enumerate(texts):
        if t["layer"] in guess and i not in drop and i not in split:
            v = next((v for kind, v in di.classify(t["text"]) if kind == "level"), None)
            if v is not None:
                gtx.add(t["x"], t["y"], v)
    gn = di.Grid(max(level_radius, 1.0))
    for n in used:
        h = gtx.near(n["x"], n["y"], level_radius)
        if h:
            gn.add(n["x"], n["y"], h[0][3])
    il_rows = []
    for lay in sorted({t["layer"] for t in texts}):
        vals, marked, below, cmp_n = [], 0, 0, 0
        for i, t in enumerate(texts):
            if t["layer"] != lay or i in drop:
                continue
            for kind, v in di.classify(t["text"]):
                if kind == "invert" or (kind == "level" and (lay not in guess or i in split)):
                    marked += kind == "invert"
                    vals.append(v)
                    h = gn.near(t["x"], t["y"], level_radius)
                    if h and abs(h[0][3] - v) <= 2 * di.IL_MAX_DEPTH_M:
                        cmp_n += 1
                        below += di.IL_MIN_DEPTH_M <= h[0][3] - v <= di.IL_MAX_DEPTH_M
                    break
        if not vals or (not marked and not below):
            continue
        vals.sort()
        il_rows.append({"layer": lay, "texts": len(vals), "marked": marked, "plain": len(vals) - marked,
                        "min": vals[0], "max": vals[-1], "median": vals[len(vals) // 2],
                        "compared": cmp_n, "below": below,
                        "il_like": (marked >= 5 and below >= 0.8 * cmp_n) or (cmp_n >= 3 and below >= 0.8 * cmp_n)})
    il_rows.sort(key=lambda r: (-r["il_like"], -r["below"], r["layer"]))
    il_guess = [r["layer"] for r in il_rows if r["il_like"]][:1]
    # Z of the line ends (user question 22-Oct-2026: 'Z वाला विकल्प नहीं है?'): at how many junctions, its range,
    # how many different values (a few: the elevations of whole polylines, not the ground - chit5: 3) and how far
    # from the GL texts of the guessed layer (median, at the junctions having both)
    zs = {n["id"]: max(n["z"]) for n in used if any(abs(z) > 0.001 for z in n["z"])}
    zv = sorted(zs.values())
    diff = []
    if guess and zs:
        g = di.Grid(max(level_radius, 1.0))
        for i, t in enumerate(texts):
            if t["layer"] in guess and i not in drop:
                v = next((v for kind, v in di.classify(t["text"]) if kind == "level"), None)
                if v is not None:
                    g.add(t["x"], t["y"], v)
        for n in used:
            h = g.near(n["x"], n["y"], level_radius) if n["id"] in zs else None
            if h:
                diff.append(abs(zs[n["id"]] - h[0][3]))
    distinct = len({round(v, 2) for v in zv})
    z = {"junctions": len(zv), "min": zv[0] if zv else None, "max": zv[-1] if zv else None,
         "median": zv[len(zv) // 2] if zv else None, "distinct": distinct,
         "text_diff": round(sorted(diff)[len(diff) // 2], 2) if diff else None,
         "ground_like": bool(zv) and distinct >= max(5, 0.1 * len(zv)) and (not diff or sorted(diff)[len(diff) // 2]
                                                                           <= di.Z_TEXT_AGREE_M)}
    return {"ok": True, "junctions": len(used), "options": rows, "guess": guess, "z": z,
            "z_guess": bool(not guess and z["ground_like"]), "il_options": il_rows, "il_guess": il_guess,
            "il_depth": [di.IL_MIN_DEPTH_M, di.IL_MAX_DEPTH_M, di.IL_SHALLOW_M]}


def extract(path, pipe_layers, mh_layers=(), level_layers=(), tol=0.5, level_radius=10.0, mid_snap=1.5,
            midline=True, z_mode="auto", il_layers=(), node_prefix=None, pipe_prefix=None):
    """The body of the original scripts dxf_extract.main() up to the tables. Returns {"mh_rows", "co_rows", "problems",
    "summary" (text lines), "lvl_layers", "path"}. Raises ValueError for layers not in the drawing. The texts that are
    the lengths of their pipes (length_texts) are not used as GL. z_mode: Z of the line ends "auto" / "first" / "off"
    (dxf_inspect.node_levels). il_layers: the layers of the invert levels (IL) - each manhole's IL from them, only
    when below its GL (dxf_inspect.node_inverts; user request 22-Oct-2026); the rows get IL / IL_source."""
    # the names chosen on the page (user request 30-Oct-2026): node_prefix + "G" for a node without a drawing label,
    # pipe_prefix for the pipes; else the module's own
    npre = f"{node_prefix}G" if node_prefix else NODE_PREFIX
    ppre = pipe_prefix or PIPE_PREFIX
    layers, texts, inserts, points, pipe_layers, mh_lay, nodes, edges, chk, used, mid_log = _network(
        path, pipe_layers, mh_layers, tol, level_radius, mid_snap, midline)

    # ---- manhole labels
    adj = collections.defaultdict(set)
    for e in edges:
        if e["a"] != e["b"]:
            adj[e["a"]].add(e["b"])
            adj[e["b"]].add(e["a"])
    labels = di.labels_near_nodes(nodes, texts, level_radius, mh_lay or None, adj=adj)
    cnt = collections.Counter(v for v in labels.values() if v)
    dup = {k for k, c in cnt.items() if c > 1}
    # sewer_app (13-Oct-2026, greenfield lanes.dxf): two numbering series in one drawing - every repeated label lies in
    # different PARTS of the network. Such a label keeps its name with the part number: <label>/<part> (part 1 =
    # largest); only a label repeated within one part is still replaced by a generated name.
    comp, find = di.components(nodes, edges)
    part_no = {root: i for i, (root, _) in enumerate(sorted(comp.items(), key=lambda kv: (-kv[1], kv[0])), start=1)}
    copies = collections.defaultdict(list)
    for n in used:
        if labels.get(n["id"]) in dup:
            copies[labels[n["id"]]].append(n["id"])
    by_part = {lab: ids for lab, ids in copies.items() if len({find(i) for i in ids}) == len(ids)}
    dup -= set(by_part)
    final, gen = {}, 0
    for n in used:
        lab = labels.get(n["id"])
        if lab in by_part:
            lab = f"{lab}/{part_no[find(n['id'])]}"
        elif not lab or lab in dup:
            gen += 1
            lab = f"{npre}{gen}"                  # generated: no label, or a label shared by several nodes
        final[n["id"]] = lab

    # ---- ground levels (a text that is the length of its pipe is no GL - length_texts)
    drop = length_texts(texts, edges)
    il_lay = [s.strip() for s in il_layers if s.strip()]
    # a layer that is both GL and IL layer, the IL written as a plain number: the lower value at a manhole is its IL
    il_split = di.split_gl_il(nodes, texts, set(il_lay) & {s.strip() for s in level_layers}, level_radius)         if il_lay else set()
    gl_texts = [t for i, t in enumerate(texts) if i not in drop and i not in il_split]
    lvl_given = [s.strip() for s in level_layers if s.strip()]
    if lvl_given:
        lvl_layers = lvl_given
    else:
        cover = []
        for lay, vals in di.level_candidates(gl_texts).items():
            g = di.Grid(max(level_radius, 1.0))
            for x, y, v in vals:
                g.add(x, y, v)
            cover.append((sum(1 for n in used if g.near(n["x"], n["y"], level_radius)), lay))
        cover.sort(reverse=True)
        lvl_layers = [cover[0][1]] if cover and cover[0][0] else []
    li0 = getattr(di.labels_near_nodes, "info", {})
    lres, per_node, _ = di.node_levels(nodes, gl_texts, inserts, lvl_layers, level_radius, z_mode=z_mode,
                                       anchors=li0.get("text_at"), pass2_labels=li0.get("pass2", set()))

    # ---- invert levels (sewer): from il_layers, below the GL
    il_of, il_bad = di.node_inverts(nodes, texts, il_lay, lvl_layers, level_radius,
                                    {k: v[1] for k, v in per_node.items()}, split=il_split, skip=drop)         if il_lay else ({}, [])

    # ---- tables
    mh_rows = []
    for n in used:
        src, gl = per_node.get(n["id"], (None, None))
        il = il_of.get(n["id"])
        mh_rows.append({"Label": final[n["id"]], "X": round(n["x"], 3), "Y": round(n["y"], 3),
                        "GL": round(gl, 3) if gl is not None else None, "GL_source": src or "",
                        "IL": round(il, 3) if il is not None else None, "IL_source": "text" if il is not None else ""})
    co_rows = []
    for k, e in enumerate(edges, start=1):
        if e["a"] == e["b"]:
            continue                      # closed line on itself - not a conduit
        co_rows.append({"Label": f"{ppre}{k}", "From": final[e["a"]], "To": final[e["b"]],
                        "Length_m": round(e["len"], 3),
                        "Vertices": ";".join(f"{p[0]:.3f} {p[1]:.3f}" for p in e["pts"])})
    li, gi = getattr(di.labels_near_nodes, "info", {}), getattr(di.node_levels, "info", {})
    nid_of = {final[n["id"]]: n["id"] for n in used}
    for r in mh_rows:
        if r["GL_source"] == "text" and nid_of[r["Label"]] in gi.get("pass2", set()):
            r["GL_source"] = "text, pass 2 - check"
    prob = []
    # sewer_app (12-Oct-2026): pass-2 matches split by a second piece of evidence - a label whose number is within 2
    # of a neighbour's along the sewer, a GL within 1 m of its neighbours' mean, is 'low risk'; the rest 'CHECK'
    import re as _re

    def _num(lab):
        m_ = _re.search(r"(\d+)(?:/\d+)?$", str(lab or ""))          # MH-12/2: 12 (the /2 is the part)
        return int(m_.group(1)) if m_ and labels.get(lab_of.get(lab)) else None
    lab_of = {final[n["id"]]: n["id"] for n in used}
    gl_of = {n["id"]: per_node.get(n["id"], (None, None))[1] for n in used}
    for n in used:
        nid = n["id"]
        if nid in li.get("pass2", set()):
            a = _num(final[nid])
            nb = [_num(final[m]) for m in adj.get(nid, ())]
            agree = a is not None and any(b is not None and abs(a - b) <= 2 for b in nb)
            prob.append({"Problem": ("label matched in pass 2 - number fits a neighbour (low risk)" if agree else
                                     "label matched in pass 2 (nearest free text) - CHECK in CAD"),
                         "Item": final[nid], "X": round(n["x"], 3), "Y": round(n["y"], 3), "Detail": ""})
        if nid in gi.get("pass2", set()):
            g0 = gl_of.get(nid)
            nb = [gl_of[m] for m in adj.get(nid, ()) if gl_of.get(m) is not None]
            dev = abs(g0 - sum(nb) / len(nb)) if (g0 is not None and nb) else None
            prob.append({"Problem": ("GL matched in pass 2 - within 1 m of its neighbours (low risk)"
                                     if dev is not None and dev <= 1.0 else
                                     "GL matched in pass 2 (nearest free text) - CHECK in CAD"),
                         "Item": final[nid], "X": round(n["x"], 3), "Y": round(n["y"], 3),
                         "Detail": f"{dev:.2f} m from the neighbours' mean" if dev is not None else ""})
    for r in mh_rows:
        if r["GL"] is None:
            prob.append({"Problem": "no GL", "Item": r["Label"], "X": r["X"], "Y": r["Y"], "Detail": ""})
    for n in used:
        if not labels.get(n["id"]):
            prob.append({"Problem": "no MH label in the drawing", "Item": final[n["id"]], "X": round(n["x"], 3),
                         "Y": round(n["y"], 3), "Detail": "generated name"})
        elif labels[n["id"]] in dup:
            prob.append({"Problem": "MH label used by more than one node", "Item": final[n["id"]],
                         "X": round(n["x"], 3), "Y": round(n["y"], 3), "Detail": f"drawing label {labels[n['id']]}"})
    for nid, other, d in chk["gaps"]:
        prob.append({"Problem": "near-miss gap (not joined)", "Item": f"{final.get(nid)} - {final.get(other)}",
                     "X": round(nodes[nid]["x"], 3), "Y": round(nodes[nid]["y"], 3), "Detail": f"{d:.2f} m apart"})
    for nid, eid, d in chk["tjoints"]:
        prob.append({"Problem": "line ends on another line without a node", "Item": final.get(nid),
                     "X": round(nodes[nid]["x"], 3), "Y": round(nodes[nid]["y"], 3),
                     "Detail": f"on line handle {edges[eid]['handle']}"})
    for x, y, src, hdl, d in mid_log:
        prob.append({"Problem": "manhole on a continuous line - line cut there (check in CAD)", "Item": src,
                     "X": x, "Y": y, "Detail": f"line handle {hdl}, {d} m from the line"})
    if chk["loops"]:
        prob.append({"Problem": f"{chk['loops']} loop(s) in the network", "Item": "", "X": None, "Y": None,
                     "Detail": "a sewer must be a tree - remove or split one line per loop"})
    if chk["parts"] > 1:
        prob.append({"Problem": f"{chk['parts']} separate parts", "Item": "", "X": None, "Y": None,
                     "Detail": f"nodes per part {chk['part_sizes']} - one outfall per part, or join them"})

    for nid, v, gl in il_bad:                     # an IL is always below its GL (sewer, 22-Oct-2026)
        n = nodes[nid]
        prob.append({"Problem": "IL not below the GL", "Item": final.get(nid), "X": round(n["x"], 3),
                     "Y": round(n["y"], 3), "Detail": f"IL {v:.3f} m, GL {gl:.3f} m (depth {gl - v:.2f} m, "
                                                      f"{di.IL_MIN_DEPTH_M:g} - {di.IL_MAX_DEPTH_M:g} m) - not taken"})
    il_shallow = [(nid, v, per_node[nid][1]) for nid, v in il_of.items()
                  if per_node.get(nid, (None, None))[1] is not None and per_node[nid][1] - v < di.IL_SHALLOW_M]
    for nid, v, gl in il_shallow:                 # taken - less than the cover 0.9 m + a 150 mm pipe
        n = nodes[nid]
        prob.append({"Problem": "IL shallow", "Item": final.get(nid), "X": round(n["x"], 3), "Y": round(n["y"], 3),
                     "Detail": f"IL {v:.3f} m, GL {gl:.3f} m: depth {gl - v:.2f} m < {di.IL_SHALLOW_M:g} m "
                               f"(cover 0.9 m, CPHEEO p3-124, + 150 mm pipe)"})

    # ---- summary lines (printed by main)
    gl_n = sum(1 for r in mh_rows if r["GL"] is not None)
    gls = [r["GL"] for r in mh_rows if r["GL"] is not None]
    summ = [f"Pipe layers : {', '.join(pipe_layers)} - {len(co_rows)} conduits, {chk['length']:,.1f} m",
            f"Manholes    : {len(mh_rows)}; label from drawing {len(mh_rows) - gen}, generated {gen}"
            + (f" ({len(dup)} duplicate label(s))" if dup else "")
            + (f"; {len(by_part)} label(s) repeated in different parts of the network (two numbering series?) "
               f"named <label>/<part>, e.g. {next(iter(by_part))}/{part_no[find(by_part[next(iter(by_part))][0])]}"
               if by_part else ""),
            f"GL          : {gl_n} of {len(mh_rows)} - texts of {', '.join(l for l in lvl_layers if l != '(no GL layer)') or '-'} "
            f"{lres['text']}, Z of the lines {lres['z']}, block attributes {lres['attr']} (Z: {z_mode})"
            + (f", range {min(gls):.3f} - {max(gls):.3f}" if gls else "") + f"; missing {len(mh_rows) - gl_n}"]
    for name, inf in (("Label match", li), ("GL match   ", gi)):
        if inf:
            summ.append(f"{name} : {inf['matched']} of {inf['texts']} texts placed one-to-one - pass 1 (learnt offsets) "
                        f"{inf['pass1']}, pass 2 (nearest free, CHECK) {inf['pass2_n']}; unused texts {inf['texts_unused']}")
            summ.append(f"              offsets text -> symbol (dx, dy, count) from {inf['offset_samples']} isolated "
                        f"manholes: {inf['offsets']}")
            if inf["unused_offsets"]:
                summ.append(f"              unused texts lie at (dx, dy ~2 m, count): {inf['unused_offsets']}")
    if il_lay:
        il_n = sum(1 for r in mh_rows if r["IL"] is not None)
        summ.append(f"IL          : {il_n} of {len(mh_rows)} from {', '.join(il_lay)}"
                    + (f" ({len(il_split)} written as a plain number next to the GL)" if il_split else "")
                    + (f"; {len(il_bad)} not taken - not {di.IL_MIN_DEPTH_M:g}-{di.IL_MAX_DEPTH_M:g} m below the GL"
                       if il_bad else "")
                    + (f"; {len(il_shallow)} shallower than {di.IL_SHALLOW_M:g} m (CHECK)" if il_shallow else ""))
    n_len = sum(1 for i in drop if texts[i]["layer"] in lvl_layers)
    if n_len:
        summ.append(f"GL note     : {n_len} decimal text(s) on {', '.join(lvl_layers)} are the lengths of their pipes - "
                    f"not used as GL")
    if gi and gi.get("z_ignored"):
        summ.append(f"GL note     : {gi['z_ignored']}; the nodes without a GL text are filled along the pipes (auto repair)")
    if midline:
        n_sym = sum(1 for r_ in mid_log if r_[2].startswith("symbol"))
        summ.append(f"Mid-line    : {len(mid_log)} manhole(s) drawn on a continuous line - line cut there "
                    f"({n_sym} from symbols, {len(mid_log) - n_sym} from left-over MH labels); sheet Problems")
    summ.append(f"Network     : {chk['parts']} part(s), {chk['loops']} loop(s), {len(chk['gaps'])} near-miss gap(s), "
                f"{len(chk['tjoints'])} T-joint(s) without node, {chk['dead_ends']} dead ends")
    summ.append(f"Problems    : {len(prob)} (sheet Problems)")
    return {"mh_rows": mh_rows, "co_rows": co_rows, "problems": prob, "summary": summ, "lvl_layers": lvl_layers,
            "path": path}


def write_outputs(ex, out_dir=None, stem=None):
    """<stem>_manholes.csv, <stem>_conduits.csv and <stem>_extract.xlsx (+ Problems) in out_dir.
    Returns (manholes csv, conduits csv, xlsx)."""
    out_dir = out_dir or OUT_DIR
    os.makedirs(out_dir, exist_ok=True)
    stem = stem or os.path.splitext(os.path.basename(ex["path"]))[0]
    mh_rows, co_rows, prob = ex["mh_rows"], ex["co_rows"], ex["problems"]
    f_mh = os.path.join(out_dir, f"{stem}_manholes.csv")
    f_co = os.path.join(out_dir, f"{stem}_conduits.csv")
    for fn, rows in ((f_mh, mh_rows), (f_co, co_rows)):
        with open(fn, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    f_x = os.path.join(out_dir, f"{stem}_extract.xlsx")
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    wb = Workbook()
    bold, head = Font(bold=True), PatternFill("solid", fgColor="D9E1F2")
    for i, (name, rows) in enumerate((("Manholes", mh_rows), ("Conduits", co_rows), ("Problems", prob))):
        ws = wb.active if i == 0 else wb.create_sheet(name)
        ws.title = name
        cols = list(rows[0].keys()) if rows else ["(none)"]
        ws.append(cols)
        for c in ws[1]:
            c.font, c.fill = bold, head
        for r in rows:
            ws.append([r.get(c) for c in cols])
        ws.freeze_panes = "A2"
    wb.save(f_x)
    return f_mh, f_co, f_x


def main():
    ap = argparse.ArgumentParser(description="Minimum sewer data (manholes + connectivity) from a DXF / DWG.")
    ap.add_argument("dxf")
    ap.add_argument("--pipe-layers", required=True, help="comma separated, e.g. PIPE0,PIPE1,PIPE2")
    ap.add_argument("--mh-layers", default="", help="layer(s) with the manhole symbols / MH labels, e.g. MH-")
    ap.add_argument("--level-layers", default="", help="layer(s) with the GL texts; default: best match")
    ap.add_argument("--tol", type=float, default=0.5, help="snap tolerance for joining line ends (m)")
    ap.add_argument("--level-radius", type=float, default=10.0, help="max distance node -> label / GL text (m)")
    ap.add_argument("--mid-snap", type=float, default=1.5,
                    help="a manhole symbol / left-over MH label within this distance (m) of the inside of a "
                         "pipe line cuts the line there (manhole drawn on a continuous line)")
    ap.add_argument("--no-midline", action="store_true", help="do not cut lines at manholes drawn on them")
    ap.add_argument("--out", help="output folder (default sewer_app\\output\\dxf_extract)")
    a = ap.parse_args()
    t0 = time.time()
    try:
        ex = extract(os.path.abspath(a.dxf.strip('"')), a.pipe_layers.split(","), a.mh_layers.split(","),
                     a.level_layers.split(","), a.tol, a.level_radius, a.mid_snap, not a.no_midline)
    except ValueError as e:
        sys.exit(str(e))
    f_mh, f_co, f_x = write_outputs(ex, a.out)
    for ln in ex["summary"]:
        print(ln)
    print(f"\nWritten: {f_mh}\n         {f_co}\n         {f_x}   ({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()


