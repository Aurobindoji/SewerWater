"""Barrier lines drawn on the map - highway, expressway, railway, canal ... (user request 27-Oct-2026): no pipe of the
network crosses one. A pipe crossing a barrier is cut there (user decision 27-Oct-2026): its two parts stay along
their road on either side, each ending gap_m short of the line (given for each line, GAP_M when not - user
27-Oct-2026) at a dead end, a new junction without population of its own; a part between two crossings (no junction
of its own on it) is left out. A side of the network so cut off
from every OHT gets an OHT of its own from the zoning, or is reported as joined to none.

Crossings (user request 27-Oct-2026: a pipe laid across a road where needed): a short line drawn across a barrier
line or a zone loop. Where it crosses one (crossing_points), a pipe of the network crossing it within CROSS_TOL_M
goes through - not cut, not closed; where no pipe does, the crossing line itself is a new pipe joining the nearest
junction at each of its ends (within SNAP_MAX_M) - add_crossing_pipes, before the cut. Both given for each crossing
line on the page (tol_m, snap_m; user request 7-Nov-2026), the constants when not.

    pts = crossing_points(crossings, lines)          lines: the barriers and the loops' rings ("loop:<name>")
    net, made = add_crossing_pipes(net, crossings, lines, pts)
    net2, cuts = cut(net, barriers, pts)
    net      = {"nodes": {id: {"xy": (x, y), "ground": m, ...}}, "conduits": [{"label", "start_node", "stop_node",
                "length_m", "vertices": [(x, y), ...]}, ...]} (server.project_net)
    barriers = [{"name": "NH-19", "type": "highway", "gap_m": 1.0, "xy": [(x, y), ...]}, ...] in the same metres
    cuts     = [{"pipe": label, "barrier": name, "xy": (x, y), "parts": [labels kept]}, ...]
"""
import math

GAP_M = 1.0            # a cut pipe ends this short of the barrier line, on each side (a line's own gap_m: other)
GAP_MAX_M = 100.0      # the largest gap a line may ask for
CROSS_TOL_M = 10.0     # a pipe crossing a line within this of a crossing line goes through (a line's own tol_m: other)
CROSS_TOL_MAX_M = 100.0
SNAP_MAX_M = 100.0     # a new crossing pipe joins the nearest junction within this of each of its ends (its snap_m)
SNAP_MAX_MAX_M = 1000.0
MIN_PART_M = 0.5       # a part shorter than this is not kept (the junction is on the line itself)
TYPES = {"highway": "Highway", "expressway": "Expressway", "railway": "Railway line", "canal": "Canal / nala",
         "other": "Other"}


def clean(raw, to_xy):
    """The barriers of the page ([{name, type, gap_m, latlngs: [[lat, lng], ...]}]) in the project's metres; a line of
    fewer than 2 points is left out; gap_m empty / not a number: GAP_M, kept within 0 - GAP_MAX_M."""
    out = []
    for i, b in enumerate(raw or [], 1):
        pts = [p for p in (b or {}).get("latlngs") or [] if isinstance(p, (list, tuple)) and len(p) >= 2]
        if len(pts) < 2:
            continue
        t = str(b.get("type") or "other")
        try:
            gap = min(max(float(b.get("gap_m")), 0.0), GAP_MAX_M)
        except (TypeError, ValueError):
            gap = GAP_M
        out.append({"name": str(b.get("name") or "").strip() or f"Barrier {i}",
                    "type": t if t in TYPES else "other", "gap_m": gap,
                    "latlngs": [[float(p[0]), float(p[1])] for p in pts],
                    "xy": [tuple(p) for p in to_xy([[float(p[0]), float(p[1])] for p in pts])]})
    return out


def _num(v, default, lo, hi):
    """v as a number within lo - hi; empty / not a number: default."""
    try:
        return min(max(float(v), lo), hi)
    except (TypeError, ValueError):
        return default


def clean_crossings(raw, to_xy):
    """The crossing lines of the page ([{name, latlngs, tol_m, snap_m}]) in the project's metres; fewer than 2 points:
    left out. tol_m (CROSS_TOL_M) / snap_m (SNAP_MAX_M) empty / not a number: the constant, kept within their limits."""
    out = []
    for i, c in enumerate(raw or [], 1):
        pts = [p for p in (c or {}).get("latlngs") or [] if isinstance(p, (list, tuple)) and len(p) >= 2]
        if len(pts) < 2:
            continue
        out.append({"name": str(c.get("name") or "").strip() or f"Crossing {i}",
                    "latlngs": [[float(p[0]), float(p[1])] for p in pts],
                    "xy": [tuple(p) for p in to_xy([[float(p[0]), float(p[1])] for p in pts])],
                    "tol_m": _num(c.get("tol_m"), CROSS_TOL_M, 0.5, CROSS_TOL_MAX_M),
                    "snap_m": _num(c.get("snap_m"), SNAP_MAX_M, 1.0, SNAP_MAX_MAX_M)})
    return out


def ring_line(name, xy):
    """A zone loop's ring as a closed line for crossing_points / cut: name "loop:<name>"."""
    xy = [tuple(p) for p in xy]
    return {"name": f"loop:{name}", "type": "other", "gap_m": GAP_M, "xy": xy + xy[:1]}


def _cross(poly, line):
    """The points where polyline poly crosses polyline line (a touch at line's own ends: none)."""
    out, m = [], len(line) - 1
    for p, q in zip(poly, poly[1:]):
        for i, (a, b) in enumerate(zip(line, line[1:])):
            h = _hit(p, q, a, b)
            if h is None or (i == 0 and h[1] <= 1e-6) or (i == m - 1 and h[1] >= 1 - 1e-6):
                continue
            out.append((p[0] + h[0] * (q[0] - p[0]), p[1] + h[0] * (q[1] - p[1])))
    return out


def crossing_points(crossings, lines):
    """[(line name, point, crossing name, its tol_m)]: where each crossing line crosses a barrier line / loop ring."""
    return [(ln["name"], x, c["name"], c.get("tol_m", CROSS_TOL_M)) for c in crossings or [] for ln in lines or []
            for x in _cross(c["xy"], ln["xy"])]


def _poly(c, nodes):
    poly = [tuple(p) for p in (c.get("vertices") or [])]
    xa, xb = (nodes.get(c["start_node"]) or {}).get("xy"), (nodes.get(c["stop_node"]) or {}).get("xy")
    if len(poly) < 2 and xa is not None and xb is not None:
        poly = [tuple(xa), tuple(xb)]
    return poly


def through(points, line_name, xy, tol=None):
    """A pipe crossing line line_name at xy goes through it: a crossing line crosses there, within tol (None: that
    crossing line's own tol_m)."""
    return any(ln == line_name and math.dist(x, xy) <= (t if tol is None else tol) for ln, x, _, t in points or [])


def add_crossing_pipes(net, crossings, lines, points, tol=None):
    """A crossing line where no pipe of the network crosses the line(s) it crosses (within tol; None: the line's own
    tol_m, CROSS_TOL_M): a new pipe along it, from the junction nearest its start to the one nearest its end (each within
    its snap_m, SNAP_MAX_M). Returns (net, made): made = [{"crossing", "pipe" (new label or None), "existing": [pipes
    going through], "note", "snap_m"}]."""
    if not crossings:
        return net, []
    nodes = net["nodes"]
    lines = {ln["name"]: ln for ln in lines or []}
    deg = {}
    for c in net["conduits"]:
        deg[c["start_node"]] = deg.get(c["start_node"], 0) + 1
        deg[c["stop_node"]] = deg.get(c["stop_node"], 0) + 1
    labels = {c["label"] for c in net["conduits"]}
    new, made = [], []
    for cr in crossings:
        pts = [(ln, x) for ln, x, cn, _ in points if cn == cr["name"]]
        tl = cr.get("tol_m", CROSS_TOL_M) if tol is None else tol
        snap = cr.get("snap_m", SNAP_MAX_M)
        use = []
        for c in net["conduits"]:
            poly = _poly(c, nodes)
            if len(poly) < 2:
                continue
            bx = _bbox(poly)
            for ln, x in pts:
                if bx[0] - tl <= x[0] <= bx[2] + tl and bx[1] - tl <= x[1] <= bx[3] + tl and any(
                        math.dist(h, x) <= tl for h in _cross(poly, lines[ln]["xy"])):
                    use.append(c["label"])
                    break
        rec = {"crossing": cr["name"], "pipe": None, "existing": use, "note": None, "snap_m": snap,
               "lines": sorted({ln.split(":", 1)[-1] for ln, _ in pts})}
        if not pts:
            rec["note"] = "it crosses no barrier line / zone loop"
        if use or not pts:
            made.append(rec)
            continue
        ends = []
        for e in (cr["xy"][0], cr["xy"][-1]):
            cand = [(math.dist(v["xy"], e), str(n), n) for n, v in nodes.items() if v.get("xy") and deg.get(n)]
            d, _, n = min(cand) if cand else (math.inf, "", None)
            ends.append(n if d <= snap else None)
        if None in ends or ends[0] == ends[1]:
            rec["note"] = f"no junction within {snap:g} m of each of its ends: no pipe made"
            made.append(rec)
            continue
        a, b = ends
        vert = [tuple(nodes[a]["xy"])] + [tuple(p) for p in cr["xy"]] + [tuple(nodes[b]["xy"])]
        lab = f"X-{cr['name']}".replace(" ", "")
        while lab in labels:
            lab += "'"
        labels.add(lab)
        new.append({"label": lab, "start_node": a, "stop_node": b, "vertices": vert, "crossing": cr["name"],
                    "length_m": round(sum(math.dist(p, q) for p, q in zip(vert, vert[1:])), 3)})
        rec["pipe"] = lab
        made.append(rec)
    return (dict(net, conduits=list(net["conduits"]) + new) if new else net), made


def crossing_summary(made):
    """One line for the log / checks: what each crossing did."""
    return "; ".join(f"{m['crossing']} ({', '.join(m['lines']) or '-'}): " +
                     (f"new pipe {m['pipe']}" if m["pipe"] else
                      f"{', '.join(m['existing'])} go(es) through" if m["existing"] else m["note"] or "-")
                     for m in made)


TYPES_HI = {"highway": "Highway", "expressway": "Expressway", "railway": "रेलवे लाइन", "canal": "नहर / नाला",
            "other": "अन्य"}


def summary_hi(barriers, cuts):
    """summary() in Hindi, for the page."""
    by = {}
    for c in cuts:
        by.setdefault(c["barrier"], set()).add(c["pipe"])
    return "; ".join(f"{b['name']} ({TYPES_HI[b['type']]}): {len(by.get(b['name'], ()))} pipes कटे, रेखा से दोनों ओर "
                     f"{b.get('gap_m', GAP_M):g} m पहले बंद" for b in barriers or [])


def crossing_summary_hi(made):
    """crossing_summary() in Hindi, for the page."""
    return "; ".join(f"{m['crossing']} ({', '.join(m['lines']) or '-'}): " +
                     (f"नया pipe {m['pipe']}" if m["pipe"] else
                      f"{', '.join(m['existing'])} आर-पार (नहीं कटा)" if m["existing"] else
                      "किसी रुकावट रेखा / zone लूप को नहीं काटता" if not m["lines"] else
                      f"दोनों सिरों के {m.get('snap_m', SNAP_MAX_M):g} m भीतर junction नहीं - pipe नहीं बना")
                     for m in made)


def _hit(p, q, a, b):
    """Where segment p-q meets segment a-b: the shares along p-q and along a-b (0..1), else None."""
    rx, ry = q[0] - p[0], q[1] - p[1]
    sx, sy = b[0] - a[0], b[1] - a[1]
    den = rx * sy - ry * sx
    if abs(den) < 1e-12:
        return None                                       # parallel (a pipe along the barrier does not cross it)
    t = ((a[0] - p[0]) * sy - (a[1] - p[1]) * sx) / den
    u = ((a[0] - p[0]) * ry - (a[1] - p[1]) * rx) / den
    if -1e-9 <= t <= 1 + 1e-9 and -1e-9 <= u <= 1 + 1e-9:
        return min(max(t, 0.0), 1.0), min(max(u, 0.0), 1.0)
    return None


def _bbox(pts):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _part(poly, cum, s0, s1):
    """The piece of the polyline from s0 to s1 (metres along it)."""
    def at(s):
        for i in range(1, len(poly)):
            if s <= cum[i] + 1e-9 or i == len(poly) - 1:
                seg = cum[i] - cum[i - 1]
                f = (s - cum[i - 1]) / seg if seg > 0 else 0.0
                f = min(max(f, 0.0), 1.0)
                return (poly[i - 1][0] + f * (poly[i][0] - poly[i - 1][0]),
                        poly[i - 1][1] + f * (poly[i][1] - poly[i - 1][1]))
        return poly[-1]
    return [at(s0)] + [poly[i] for i in range(len(poly)) if s0 + 1e-9 < cum[i] < s1 - 1e-9] + [at(s1)]


def cut(net, barriers, points=None):
    """The network with every pipe crossing a barrier cut there (see the module text) - except where a crossing line
    crosses it (points: crossing_points); net itself is not changed."""
    if not barriers:
        return net, []
    nodes = {n: dict(v) for n, v in net["nodes"].items()}
    labels = {c["label"] for c in net["conduits"]}
    segs = []                                              # (barrier, a, b, bbox, first, last)
    for b in barriers:
        m = len(b["xy"]) - 1
        for i, (a_, b_) in enumerate(zip(b["xy"], b["xy"][1:])):
            segs.append((b, a_, b_, _bbox([a_, b_]), i == 0, i == m - 1))
    allbox = _bbox([p for b in barriers for p in b["xy"]])
    out, cuts = [], []
    for c in net["conduits"]:
        a, b = c["start_node"], c["stop_node"]
        xa, xb = (nodes.get(a) or {}).get("xy"), (nodes.get(b) or {}).get("xy")
        poly = [tuple(p) for p in (c.get("vertices") or [])]
        if len(poly) < 2:
            poly = [tuple(xa), tuple(xb)] if xa is not None and xb is not None else []
        if len(poly) < 2:
            out.append(c)
            continue
        if xa is not None and math.dist(poly[0], xa) > math.dist(poly[-1], xa):
            poly = poly[::-1]                              # vertices from the start node on
        bx = _bbox(poly)
        if bx[2] < allbox[0] or bx[0] > allbox[2] or bx[3] < allbox[1] or bx[1] > allbox[3]:
            out.append(c)
            continue
        cum = [0.0]
        for p, q in zip(poly, poly[1:]):
            cum.append(cum[-1] + math.dist(p, q))
        G = cum[-1]
        hits = []                                          # (metres along, barrier, point)
        for i, (p, q) in enumerate(zip(poly, poly[1:])):
            pb = _bbox([p, q])
            for bar, s0, s1, sb, first, last in segs:
                if pb[2] < sb[0] or pb[0] > sb[2] or pb[3] < sb[1] or pb[1] > sb[3]:
                    continue
                h = _hit(p, q, s0, s1)
                if h is None or (first and h[1] <= 1e-6) or (last and h[1] >= 1 - 1e-6):
                    continue                               # (the very end of a line: nothing to cross there)
                t = h[0]
                xy = (p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]))
                if through(points, bar["name"], xy):
                    continue                               # a crossing line there: the pipe goes through
                hits.append((cum[i] + t * (cum[i + 1] - cum[i]), bar, xy))
        if not hits or G <= 0:
            out.append(c)
            continue
        hits.sort(key=lambda h: h[0])
        L = float(c.get("length_m") or G)
        k = L / G                                          # the pipe's length (3D, given) to the drawn one
        ga, gb = (nodes.get(a) or {}).get("ground"), (nodes.get(b) or {}).get("ground")

        def ground(s):
            if ga is None or gb is None:
                return ga if gb is None else gb
            return round(ga + (gb - ga) * s / G, 3)

        def label(base):
            nm = base
            while nm in labels:
                nm += "'"
            labels.add(nm)
            return nm
        parts = []
        s_in = hits[0][0] - hits[0][1].get("gap_m", GAP_M)       # each line's own gap
        s_out = hits[-1][0] + hits[-1][1].get("gap_m", GAP_M)
        if s_in >= MIN_PART_M:                             # the start node's side
            end = f"{c['label']}-x1"
            pts = _part(poly, cum, 0.0, s_in)
            nodes[end] = {"xy": pts[-1], "ground": ground(s_in), "gl_source": "barrier cut", "cut": True}
            parts.append(dict(c, label=label(f"{c['label']}-1"), stop_node=end, length_m=round(s_in * k, 3),
                              vertices=pts))
        if G - s_out >= MIN_PART_M:                        # the stop node's side
            beg = f"{c['label']}-x2"
            pts = _part(poly, cum, s_out, G)
            nodes[beg] = {"xy": pts[0], "ground": ground(s_out), "gl_source": "barrier cut", "cut": True}
            parts.append(dict(c, label=label(f"{c['label']}-2"), start_node=beg, length_m=round((G - s_out) * k, 3),
                              vertices=pts))
        out += parts
        seen = set()
        for _, bar, xy in hits:
            if bar["name"] in seen:
                continue
            seen.add(bar["name"])
            cuts.append({"pipe": c["label"], "barrier": bar["name"], "type": bar["type"], "xy": xy,
                         "parts": [p["label"] for p in parts], "length_m": round(L, 2)})
    return dict(net, nodes=nodes, conduits=out), cuts


def summary(barriers, cuts):
    """One line for the log / checks: the barriers, the pipes cut at each and how far short of it they end."""
    if not barriers:
        return ""
    by = {}
    for c in cuts:
        by.setdefault(c["barrier"], set()).add(c["pipe"])
    return "; ".join(f"{b['name']} ({TYPES[b['type']]}): {len(by.get(b['name'], ()))} pipes cut, ending "
                     f"{b.get('gap_m', GAP_M):g} m short of the line on both sides" for b in barriers)


NEAR_M = 50.0          # separate pieces of the network closer than this: reported (near_parts)
NEAR_SHOW = 8          # gaps named in a message at most (the nearest)


def near_parts(net, lines=(), max_m=NEAR_M, skip=()):
    """Separate pieces of the network (connected along its pipes) that come within max_m of each other, joined by no
    pipe - a gap in the drawing (user request 30-Oct-2026: 1.8 m and 41 m between the pieces of three OHTs in
    network_sewer_water_v5): for each two such pieces their nearest junctions, nearest first - [{"a", "b", "dist_m",
    "xy": (xy of a, of b), "sizes": (junctions of a's piece, of b's)}]. Not reported: junctions on either side of one
    of lines (the barrier lines, the zone loops' rings - cut there on purpose); skip: junctions not to join at (the
    ends of the pipes cut at the lines, cut_ends - made by the cut, not drawn: on 30-Oct-2026 26 of the 61 gaps of
    network_sewer_water_v5 were between such ends on one side of a line)."""
    nodes = net["nodes"]
    adj = {}
    for c in net["conduits"]:
        a, b = c["start_node"], c["stop_node"]
        if (nodes.get(a) or {}).get("xy") is None or (nodes.get(b) or {}).get("xy") is None:
            continue
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    part, size = {}, {}
    for n0 in sorted(adj, key=str):
        if n0 in part:
            continue
        part[n0], st, k = n0, [n0], 0
        while st:
            u = st.pop()
            k += 1
            for v in adj[u]:
                if v not in part:
                    part[v] = n0
                    st.append(v)
        size[n0] = k
    if len(size) < 2:
        return []
    across = blocker(lines)
    grid, skip = {}, set(skip or ())
    for n in part:
        if n in skip:
            continue
        x, y = nodes[n]["xy"]
        grid.setdefault((math.floor(x / max_m), math.floor(y / max_m)), []).append(n)
    best = {}                                             # (piece, piece) -> (distance, a, b)
    for (i, j), cell in grid.items():
        near = [n for di in (-1, 0, 1) for dj in (-1, 0, 1) for n in grid.get((i + di, j + dj), ())]
        if len({part[n] for n in near}) < 2:
            continue                                      # one piece only around this cell
        for a in cell:
            pa, xa = part[a], nodes[a]["xy"]
            for b in near:
                pb = part[b]
                if pb == pa or str(pa) > str(pb):
                    continue                              # each two pieces once, seen from the first
                d = math.dist(xa, nodes[b]["xy"])
                if d <= max_m and d < best.get((pa, pb), (math.inf,))[0] and not across(xa, nodes[b]["xy"]):
                    best[(pa, pb)] = (d, a, b)
    # two pieces with a third between them, nearer to both (three in a row): their gaps are those to the third
    nb = {}
    for (pa, pb), (d, _, _) in best.items():
        nb.setdefault(pa, {})[pb] = nb.setdefault(pb, {})[pa] = d
    out = [{"a": a, "b": b, "dist_m": round(d, 2), "xy": (tuple(nodes[a]["xy"]), tuple(nodes[b]["xy"])),
            "sizes": (size[pa], size[pb])} for (pa, pb), (d, a, b) in best.items()
           if not any(r != pb and dr < d and nb[pb].get(r, math.inf) < d for r, dr in nb[pa].items())]
    return sorted(out, key=lambda g: (g["dist_m"], str(g["a"]), str(g["b"])))


def blocker(lines):
    """across(p, q): whether the straight line p-q crosses one of lines (barrier lines, zone loops' rings)."""
    segs = [(a, b, _bbox((a, b))) for ln in lines or () for a, b in zip(ln["xy"], ln["xy"][1:])]

    def across(p, q):
        x0, y0, x1, y1 = _bbox((p, q))
        return any(not (bb[2] < x0 or bb[0] > x1 or bb[3] < y0 or bb[1] > y1) and _hit(p, q, a, b) is not None
                   for a, b, bb in segs)
    return across


def cut_ends(cuts):
    """The new junctions at the ends of the pipes cut at the lines (cut: <pipe>-x1 / -x2)."""
    return {f"{c['pipe']}-x{i}" for c in cuts or () for i in (1, 2)}


def near_summary(gaps, max_m=NEAR_M, what="pipe"):
    """One line for the flags / log: how many gaps, the nearest ones named."""
    s = ", ".join(f"{g['a']} - {g['b']} {g['dist_m']:g} m" for g in gaps[:NEAR_SHOW])
    return (f"{len(gaps)} gap(s) of {max_m:g} m or less between separate pieces of the drawing, joined by no {what}: "
            f"{s}{' ...' if len(gaps) > NEAR_SHOW else ''} - if they are one network, join them in the DXF (or on the "
            f"map); shown on the map as red dashed lines")


def near_summary_hi(gaps, max_m=NEAR_M, what="pipe"):
    s = ", ".join(f"{g['a']} - {g['b']} {g['dist_m']:g} m" for g in gaps[:NEAR_SHOW])
    return (f"drawing के अलग टुकड़ों के बीच {len(gaps)} gap ({max_m:g} m या कम), कोई {what} नहीं जोड़ता: "
            f"{s}{' ...' if len(gaps) > NEAR_SHOW else ''} - एक ही network हो तो DXF में (या नक्शे पर) जोड़ें; नक्शे पर "
            f"लाल बिंदीदार रेखा")
