"""Manhole spacing (CPHEEO 3.71, p285/p286): conduits longer than the allowed spacing get new manholes at
equal intervals, and the network is split there.

From the original scripts sewer_design.py: spacing_limit, plen_of, point_at, sub_poly, plan_new_manholes, label_namer and
assign_new_labels (unchanged apart from taking plain data instead of the SewerGEMS model). split_network
does in plain data what split_conduits did in the model: each conduit is split in its DRAWN direction - the
original conduit keeps its start node and ends at the first new manhole, new conduits carry on to the
original stop node; inverts on the designed straight grade; ground at new manholes INTERPOLATED.

Manholes at bends (user decisions 20-Oct-2026, CPHEEO 3.71 p3-125 and 3.71.1 p3-126 'additional manholes at changes
of directions'): a conduit drawn with bends (a DXF network) gets a new manhole at every bend of
bend_manhole_min_angle_deg or more (design_criteria.json: 20 deg; bend_angle) - the polyline straightened to within
BEND_TOL_M first, so that the wobble of a drawn road is no bend; bends closer than BEND_MIN_GAP_M to a manhole or to
each other are left (the larger one kept). The straight stretches between them are then divided for the spacing.

presplit (user decision 20-Oct-2026: 'design मे सभी mh लिए जाएं'): these manholes are put into the network BEFORE
zoning and design - real manholes with their own design (inverts, drops at bends, population by sewer length) and
fixed names: <start manhole>-<n> for a new manhole, <conduit>-<n> for its pieces (the first keeps the conduit's
label). plan_new_manholes / split_network after the design then only add what presplit could not know before it:
the spacing of trunk sewers by diameter (Table 3.31).
"""
import collections
import math
import re

from .criteria import table_rows, val

BEND_TOL_M = 1.0          # as layout.STRAIGHT_TOL_M: a line within this of a straight line has no bend there
BEND_MIN_GAP_M = 2.0      # a bend this close to a manhole (or to another bend) gets no manhole of its own


def bend_angle(crit, D):
    """The bend (deg) above which a conduit of diameter D (mm) gets a manhole there: bend_manhole_min_angle_deg - a
    number, or {up to diameter: angle} (the first row D fits, the last row for larger sewers); None = no bend
    manholes."""
    c = crit["sewer"]
    if "bend_manhole_min_angle_deg" not in c:
        return None
    v = val(c, "bend_manhole_min_angle_deg")
    if v is None or isinstance(v, (int, float)):
        return v
    rows = table_rows(v)
    return next((a for dm, a in rows if (D or 0) <= dm + 0.5), rows[-1][1]) if rows else None


def _seg_dist(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.dist(p, a)
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.dist(p, (a[0] + t * dx, a[1] + t * dy))


def _turn(a, b, c):
    """Change of direction at b (degrees, 0 = straight on)."""
    d = abs(math.degrees(math.atan2(c[1] - b[1], c[0] - b[0]) - math.atan2(b[1] - a[1], b[0] - a[0]))) % 360
    return min(d, 360 - d)


def bends(poly, min_angle, tol=BEND_TOL_M, gap=BEND_MIN_GAP_M):
    """[(chainage along the polyline, angle deg)] of its bends that need a manhole: the corners of the polyline
    straightened to within tol (Douglas-Peucker) that turn by min_angle or more, not within gap of an end or of a
    larger bend."""
    if not poly or len(poly) < 3 or min_angle is None:
        return []
    keep, stack = {0, len(poly) - 1}, [(0, len(poly) - 1)]
    while stack:
        i, j = stack.pop()
        best, bd = None, tol
        for k in range(i + 1, j):
            d = _seg_dist(poly[k], poly[i], poly[j])
            if d > bd:
                best, bd = k, d
        if best is not None:
            keep.add(best)
            stack += [(i, best), (best, j)]
    idx = sorted(keep)
    ch, run = {}, 0.0
    for k in range(len(poly)):
        if k:
            run += math.dist(poly[k - 1], poly[k])
        ch[k] = run
    total = run
    cand = [(ch[b], _turn(poly[a], poly[b], poly[c])) for a, b, c in zip(idx, idx[1:], idx[2:])]
    cand = [(c, t) for c, t in cand if t >= min_angle - 1e-9 and gap <= c <= total - gap]
    out = []
    for c, t in sorted(cand, key=lambda x: -x[1]):            # the larger bends first
        if all(abs(c - o) >= gap for o, _ in out):
            out.append((c, t))
    return sorted(out)


def spacing_limit(crit, lab, D):
    c = crit["sewer"]
    trunk = {str(x) for x in (val(c, "trunk_conduits") or [])}
    rows = table_rows(val(c, "max_manhole_spacing_trunk_m"))
    if lab in trunk and rows:
        return next((sp for dm, sp in rows if D <= dm + 0.5), None)
    return val(c, "max_manhole_spacing_m")


def plen_of(poly):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(poly, poly[1:]))


def point_at(poly, ch):
    """Point at chainage ch (m) along a polyline (coordinate units = model units, assumed m)."""
    run = 0.0
    for (x1, y1), (x2, y2) in zip(poly, poly[1:]):
        seg = math.hypot(x2 - x1, y2 - y1)
        if seg and run + seg >= ch:
            t = (ch - run) / seg
            return x1 + t * (x2 - x1), y1 + t * (y2 - y1)
        run += seg
    return poly[-1]


def sub_poly(poly, a, b):
    """Part of a polyline between distances a and b along it (vertices in between kept)."""
    pts, run = [point_at(poly, a)], 0.0
    for p, q in zip(poly, poly[1:]):
        run += math.hypot(q[0] - p[0], q[1] - p[1])
        if a + 1e-6 < run < b - 1e-6:
            pts.append(q)
    pts.append(point_at(poly, b))
    return pts


def polylines(net):
    """{conduit label: [(x, y), ...]} in the drawn direction, from the network (vertices, at least 2)."""
    return {k["label"]: [tuple(p) for p in k["vertices"]] for k in net["conduits"] if len(k.get("vertices") or []) >= 2}


NEW_GL_SRC = "interpolated along the sewer (new manhole: {why})"


def presplit(net, crit):
    """(network with the manholes at bends and for the spacing inserted, rows {"label", "why", "conduit", "x", "y",
    "ground"}). Every conduit: a manhole at each bend of bend_angle or more, then every straight stretch divided into
    equal parts not longer than max_manhole_spacing_m (not for trunk_conduits - their spacing depends on the
    designed diameter, Table 3.31, and is planned after the design). Ground at a new manhole: interpolated along the
    sewer between its two manholes (gl_source says so - check on site). Conduit attributes (force_D, force_slope of
    the table edits) go to every piece. Names fixed by the drawing: new manholes <start manhole>-<n> (n counted per
    start manhole), pieces <conduit>-<n>, n from 2 (the first keeps the label)."""
    c = crit["sewer"]
    lim = val(c, "max_manhole_spacing_m")
    trunk = {str(x) for x in (val(c, "trunk_conduits") or [])}
    angle = bend_angle(crit, None)
    nodes = {n: dict(v) for n, v in net["nodes"].items()}
    used_n, used_c = set(nodes), {k["label"] for k in net["conduits"]}
    count = collections.Counter()
    conds, rows = [], []

    def free(base, used, start):
        i = start
        while f"{base}-{i}" in used:
            i += 1
        used.add(f"{base}-{i}")
        return f"{base}-{i}", i

    for k in net["conduits"]:
        a, b = k["start_node"], k["stop_node"]
        pa, pb = (nodes.get(a) or {}).get("xy"), (nodes.get(b) or {}).get("xy")
        poly = [tuple(p) for p in k.get("vertices") or []]
        if len(poly) < 2:
            poly = [tuple(pa), tuple(pb)] if pa and pb else []
        L, plen = k.get("length_m") or 0.0, plen_of(poly) if poly else 0.0
        if not poly or plen <= 0 or L <= 0:
            conds.append(dict(k, presplit=True))
            continue
        cuts = [(ch, f"bend {t:.0f} deg") for ch, t in bends(poly, angle)]
        if lim and k["label"] not in trunk:
            ends = [0.0] + [ch for ch, _ in cuts] + [plen]
            for s, e in zip(ends, ends[1:]):
                n = math.ceil((e - s) * L / plen / lim - 1e-9) if (e - s) * L / plen > lim + 0.5 else 1
                cuts += [(s + (e - s) * i / n, "spacing") for i in range(1, n)]
        if not cuts:
            conds.append(dict(k, presplit=True))
            continue
        cuts.sort()
        ga, gb = (nodes.get(a) or {}).get("ground"), (nodes.get(b) or {}).get("ground")
        chain = [a]
        for ch, why in cuts:
            count[a] += 1
            lab, i = free(a, used_n, count[a])
            count[a] = i
            x, y = point_at(poly, ch)
            g = ga + (gb - ga) * ch / plen if (ga is not None and gb is not None) else None
            nodes[lab] = {"xy": (x, y), "ground": g, "gl_source": NEW_GL_SRC.format(why=why), "new_mh": why,
                          "on_conduit": k["label"]}
            rows.append({"label": lab, "why": why, "conduit": k["label"], "x": x, "y": y, "ground": g})
            chain.append(lab)
        chain.append(b)
        marks = [0.0] + [ch for ch, _ in cuts] + [plen]
        for j in range(len(chain) - 1):
            plab = k["label"] if j == 0 else free(k["label"], used_c, j + 1)[0]
            pts = sub_poly(poly, marks[j], marks[j + 1])
            conds.append(dict(k, label=plab, start_node=chain[j], stop_node=chain[j + 1], presplit=True,
                              length_m=(marks[j + 1] - marks[j]) * L / plen, vertices=pts, piece_of=k["label"]))
    return {"nodes": nodes, "conduits": conds, "outfalls": list(net["outfalls"])}, rows


def plan_new_manholes(res, crit, R, polys, xy, checked=()):
    """Conduits longer than the allowed manhole spacing are divided into equal parts; one new
    manhole per division point. The sewer keeps its designed straight grade, so inverts follow
    the slope line. Ground between the two existing manholes is interpolated linearly (no
    survey there) - CHECK on site / with a DEM. Coordinates from the conduit polyline (or the
    straight line between the end manholes). Chainage and numbering from the design u/s end.
    A conduit with bends first gets a manhole at each bend (bends), then each stretch between two manholes is
    divided for the spacing; row["why"] = "bend <angle> deg" or "spacing". checked = conduits whose bends presplit
    has already given manholes (its pieces are not looked at again: a bend it straightened away stays so)."""
    rows = []
    for lab, d in res.items():
        lim = spacing_limit(crit, lab, d["D"])
        min_angle = bend_angle(crit, d["D"])
        L = d["length"] or 0
        poly = polys.get(lab)
        if poly is None and xy and d["from"] in xy and d["to"] in xy:
            poly = [xy[d["from"]], xy[d["to"]]]
        elif poly is not None and d["rev"]:
            poly = list(reversed(poly))
        plen = plen_of(poly) if poly else None
        bend = [(c * L / plen, t) for c, t in bends(poly, min_angle)] if (poly and plen and L and lab not in checked) else []
        if not bend and (not lim or L <= lim + 0.5):
            continue
        cuts = [(ch, f"bend {t:.0f} deg") for ch, t in bend]
        ends = [0.0] + [ch for ch, _ in bend] + [L]
        for a, b in zip(ends, ends[1:]):                       # each straight stretch: equal parts within the limit
            nseg = math.ceil((b - a) / lim - 1e-9) if (lim and b - a > lim + 0.5) else 1
            cuts += [(a + (b - a) * i / nseg, "spacing") for i in range(1, nseg)]
        cuts.sort()
        marks = [0.0] + [ch for ch, _ in cuts] + [L]
        for i, (ch, why) in enumerate(cuts, start=1):
            x = y = None
            if poly and plen:
                x, y = point_at(poly, ch * plen / L)
            g = (d["g_up"] + (d["g_dn"] - d["g_up"]) * ch / L) if (d["g_up"] is not None and d["g_dn"] is not None) else None
            inv = d["up"] - d["slope"] * ch
            rows.append({"conduit": lab, "label": f"{lab}-N{i}", "from": d["from"], "to": d["to"],
                         "chainage": ch, "spacing": max(ch - marks[i - 1], marks[i + 1] - ch), "limit": lim,
                         "why": why, "x": x, "y": y, "ground": g,
                         "invert": inv, "depth": (g - inv) if g is not None else None,
                         "cover": (g - inv - d["D"] / 1000.0) if g is not None else None, "D": d["D"],
                         "ground_src": "interpolated", "in_model": False})
    return rows


def label_namer(labels, fallback_prefix):
    """Returns a function giving the next free label in the network's own naming style: the most common
    '<prefix><number>' pattern among the existing labels (e.g. MH-253 -> MH-254, CO-254 -> CO-255),
    zero-padding kept; fallback_prefix if no label has that form."""
    pat = re.compile(r"^(.*?)(\d+)$")
    existing, count, top, pad = set(), collections.Counter(), {}, {}
    for lab in labels:
        existing.add(lab)
        m = pat.match(lab)
        if m:
            p, digits = m.group(1), m.group(2)
            count[p] += 1
            top[p] = max(top.get(p, 0), int(digits))
            if digits.startswith("0") and len(digits) > 1:
                pad[p] = max(pad.get(p, 0), len(digits))
    prefix = count.most_common(1)[0][0] if count else fallback_prefix
    state = {"n": top.get(prefix, 0)}
    width = pad.get(prefix, 0)

    def nxt():
        while True:
            state["n"] += 1
            lab = f"{prefix}{str(state['n']).zfill(width)}"
            if lab not in existing:
                existing.add(lab)
                return lab
    return nxt


def assign_new_labels(manhole_labels, rows):
    """Final labels of the planned new manholes in the manhole naming style (continuing the numbering),
    in the order conduit by conduit, upstream to downstream. manhole_labels = existing manholes (not the
    outfalls). The conduit each one sits on stays in the 'conduit' field."""
    nxt = label_namer(manhole_labels, "MH-")
    for m in rows:
        m["label"] = nxt()


def split_network(net, res, rows, conduit_labels=None):
    """Network with the planned new manholes inserted (rows of plan_new_manholes, labels assigned).
    Returns (new net, made) with made = {original conduit: [pieces in drawn order: {"label", "start",
    "stop", "up", "dn", "D", "length", "vertices"}]} - the first piece keeps the original label.
    Conduits whose polyline cannot be had are left whole and listed in made as None."""
    polys = polylines(net)
    xy = {n: v["xy"] for n, v in net["nodes"].items() if v.get("xy")}
    co_name = label_namer(conduit_labels if conduit_labels is not None else [k["label"] for k in net["conduits"]], "CO-")
    by = collections.defaultdict(list)
    for m in rows:
        by[m["conduit"]].append(m)
    nodes = {n: dict(v) for n, v in net["nodes"].items()}
    conduits, made = [], {}
    for k in net["conduits"]:
        lab, ms, d = k["label"], by.get(k["label"]), res.get(k["label"])
        if not ms or d is None:
            conduits.append(dict(k))
            continue
        L = d["length"]
        sl, el = k["start_node"], k["stop_node"]
        poly = polys.get(lab) or ([xy[sl], xy[el]] if sl in xy and el in xy else None)
        if not poly or any(m["x"] is None for m in ms):
            conduits.append(dict(k))
            made[lab] = None
            continue
        start_inv, stop_inv = (d["dn"], d["up"]) if d["rev"] else (d["up"], d["dn"])
        for m in ms:
            m["_dch"] = (L - m["chainage"]) if d["rev"] else m["chainage"]
        ms = sorted(ms, key=lambda m: m["_dch"])
        plen = plen_of(poly)
        for m in ms:
            nodes[m["label"]] = {"ground": m["ground"], "xy": (m["x"], m["y"]), "gl_source": "interpolated",
                                 "new": True, "on_conduit": lab}
            m["in_model"] = True
        chain = [sl] + [m["label"] for m in ms] + [el]
        dchs = [0.0] + [m["_dch"] for m in ms] + [L]
        invs = [start_inv] + [m["invert"] for m in ms] + [stop_inv]
        pieces = []
        for j in range(len(chain) - 1):
            plab = lab if j == 0 else co_name()
            pts = sub_poly(poly, dchs[j] * plen / L, dchs[j + 1] * plen / L)
            pieces.append({"label": plab, "start": chain[j], "stop": chain[j + 1], "up": invs[j], "dn": invs[j + 1],
                           "D": d["D"], "length": dchs[j + 1] - dchs[j], "vertices": pts})
            conduits.append({"label": plab, "start_node": chain[j], "stop_node": chain[j + 1],
                             "length_m": dchs[j + 1] - dchs[j], "vertices": pts, "split_from": lab})
        made[lab] = pieces
    return {"nodes": nodes, "conduits": conduits, "outfalls": list(net["outfalls"])}, made
