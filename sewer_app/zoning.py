"""Zoning of a sewer area into drainage zones from the ground levels (GL) of the manholes, with several
options compared by pumping stations, depth and cost. Read-only: the network is not changed.

From the original scripts zoning.py (prepare, parts_of, terrain_options, zones_from_outlets, evaluate, evaluate_with_pumps,
triangulate, zone_regions, the zoning workbook and cost_workbook), working on a sewer_app network instead of a
SewerGEMS model or the dxf_extract CSVs. Project decision (12-Oct-2026): NO lift stations - only pumping
stations (zone outlets) and the STP; sewers down to max_depth_project_m; deeper -> new zone + pumping station.

Method
  1. Terrain basins: every manhole drains to its LOWEST neighbour (steepest descent along the streets);
     all manholes reaching the same low point form one basin (watershed on the sewer graph).
  2. Basins are joined step by step: first every basin smaller than min_zone_m, then the pair whose join needs
     the least RISE over the saddle. Two basins with fixed outlets are never joined. Each number of zones
     (max_zones ... 1) gives one option; the network's outfalls give option 'CURRENT'.
  3. Zones re-drawn from the outlets: every manhole joins the outlet with the least length + W x rise
     (W = 1 / Table 3.13 minimum slope of the smallest pipe). Conduits not on the tree are 'cut'.
  4. Each option designed (design_network); where a sewer goes deeper than max_depth_project_m the manhole just
     above becomes a new zone outlet (pumping station), repeated. Ranked by pumping stations, manholes deeper
     than the limits, pipe cost - an ordering only; the choice is the user's.

Maps (PNG: GL, each option, zone boundaries) and DXFs (zone boundaries of all options, full network drawing per
option) as in the original scripts zoning.py - write_outputs makes them all. The GL band map is not here yet.
"""
import collections
import os
import heapq
import re
import math
import time

from .criteria import Rules, load_catalog, load_criteria, slope_row, val
from .design import design_network, priced_cost, rate_ref
from . import pumping, rising_main
from .flows import design_flows
from .report import DEPTH_BANDS, load_sewer_rates, slice_quantities
from .spacing import spacing_limit

VSEP = "~"                             # virtual head node = <node>~<conduit> (disconnected end of a cut conduit)
GL_SPIKE_M = 2.0                       # screening threshold for a suspicious ground level (not from the manual)
CLIMB_M = 0.01 + 1e-6                  # "sewer climbing against ground": ground rise clearly more than 1 cm. Survey GLs
                                       # have 2-3 decimals, so many rises are exactly 0.01 m and float noise decided
                                       # them in the original scripts zoning.py (oakdale_B: 249 m of 2601 m at exactly 0.01 m)


# ---------------------------------------------------------------- input
def from_network(net):
    """(nodes {label: [gl, (x, y) or None]}, edges [(label, a, b, L, pts)], outfall labels) of a network."""
    nodes = {n: [v.get("ground"), tuple(v["xy"]) if v.get("xy") else None] for n, v in net["nodes"].items()}
    edges = [(k["label"], k["start_node"], k["stop_node"], k.get("length_m"), [tuple(p) for p in k.get("vertices") or []])
             for k in net["conduits"]]
    return nodes, edges, list(net["outfalls"])


def plen(pts):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))


def prepare(nodes, edges, spike_mode):
    """Graph + GL used for the zoning. Missing GL is filled from the neighbours (mean, repeated);
    with spike_mode 'neighbour' the GL spikes are replaced by the neighbours' mean. Returns
    (adj, E, gl, notes, number of spikes) with E = {label: dict(a, b, L, pts)}, notes = rows for sheet 'GL notes'."""
    E, adj = {}, collections.defaultdict(list)
    notes, skipped = [], 0
    for lab, a, b, L, pts in edges:
        if a == b or a not in nodes or b not in nodes:
            skipped += 1
            continue
        if lab in E:                                   # duplicate label: kept apart here, listed
            new = f"{lab}#{sum(1 for k in E if k.split('#')[0] == lab) + 1}"
            notes.append({"node": f"{lab} -> {new}", "issue": "conduit label used twice (rename it)",
                          "GL in data": None, "GL used for zoning": None, "how": "renamed for this zoning only"})
            lab = new
        if not pts:
            pa, pb = nodes[a][1], nodes[b][1]
            pts = [pa, pb] if pa and pb else []
        if not L:
            L = plen(pts) if pts else 0.0
        E[lab] = {"a": a, "b": b, "L": float(L), "pts": pts}
        adj[a].append((b, lab))
        adj[b].append((a, lab))
    gl = {n: nodes[n][0] for n in adj}
    if skipped:
        notes.append({"node": "-", "issue": f"{skipped} conduit(s) skipped: both ends the same node, or an end "
                      f"that is not a manhole / outfall", "GL in data": None, "GL used for zoning": None, "how": ""})
    # fill missing GL from the neighbours (repeat until nothing changes)
    miss = {n for n, g in gl.items() if g is None}
    while miss:
        done = {}
        for n in miss:
            gn = [gl[m] for m, _ in adj[n] if gl.get(m) is not None]
            if gn:
                done[n] = sum(gn) / len(gn)
        if not done:
            break
        for n, g in done.items():
            gl[n] = g
            notes.append({"node": n, "issue": "no GL", "GL in data": None, "GL used for zoning": round(g, 3),
                          "how": "mean of neighbours"})
        miss -= set(done)
    if miss:
        ok = [g for g in gl.values() if g is not None]
        mean = sum(ok) / len(ok) if ok else 0.0
        for n in miss:
            gl[n] = mean
            notes.append({"node": n, "issue": "no GL, no neighbour with GL", "GL in data": None,
                          "GL used for zoning": round(mean, 3), "how": "mean of all"})
    spikes = []
    for n in adj:
        gn = [gl[m] for m, _ in adj[n]]
        if not gn or gl[n] <= 0:
            continue
        diffs = [gl[n] - x for x in gn]
        if all(d > GL_SPIKE_M for d in diffs) or all(d < -GL_SPIKE_M for d in diffs):
            spikes.append((n, gl[n], sum(gn) / len(gn)))
    for n, g0, m in spikes:
        if spike_mode == "neighbour":
            gl[n] = m
        notes.append({"node": n, "issue": f"GL differs > {GL_SPIKE_M:g} m from ALL neighbours",
                      "GL in data": round(g0, 3), "GL used for zoning": round(gl[n], 3),
                      "how": "neighbours' mean (spike_gl 'neighbour')" if spike_mode == "neighbour"
                      else f"kept (neighbours' mean {m:.2f})"})
    return adj, E, gl, notes, len(spikes)


def parts_of(adj):
    part, k = {}, 0
    for s in sorted(adj):
        if s in part:
            continue
        k += 1
        part[s], st = k, [s]
        while st:
            n = st.pop()
            for m, _ in adj[n]:
                if m not in part:
                    part[m] = k
                    st.append(m)
    return part


# ---------------------------------------------------------------- 1-2: terrain basins and their joining
def terrain_options(adj, E, gl, fixed, min_len, max_zones):
    """Watershed basins and the joining hierarchy. Returns (basin rows, merge log, snapshots) with
    snapshots = {K: sorted outlet list} for K <= max_zones."""
    key = lambda n: (gl[n], n)                                            # noqa: E731 - strict order, no ties
    down = {}
    for n in adj:
        lo = min((m for m, _ in adj[n]), key=key)
        down[n] = lo if key(lo) < key(n) else None
    sink = {}
    for n in adj:
        path, x = [], n
        while x not in sink and down[x] is not None:
            path.append(x)
            x = down[x]
        s = sink.get(x, x)
        sink[x] = s
        for p in path:
            sink[p] = s

    count, length = collections.Counter(), collections.defaultdict(float)
    fx = collections.defaultdict(set)
    for n in adj:
        count[sink[n]] += 1
        if n in fixed:
            fx[sink[n]].add(n)
    nb = collections.defaultdict(dict)                                    # basin -> {basin: (saddle GL, conduit)}
    for lab, e in E.items():
        a, b = sink[e["a"]], sink[e["b"]]
        length[a] += e["L"] / 2
        length[b] += e["L"] / 2
        if a != b:
            s = (max(gl[e["a"]], gl[e["b"]]), lab)
            if b not in nb[a] or s < nb[a][b]:
                nb[a][b] = nb[b][a] = s
    ids = sorted(count)
    low = {i: gl[i] for i in ids}                                         # natural low point of the basin
    outl = {i: sorted(fx[i]) or [i] for i in ids}
    rows = [{"basin low point": i, "GL": round(gl[i], 3), "manholes": count[i], "sewer length (m)": round(length[i], 1),
             "fixed outlets inside": ", ".join(sorted(fx[i])), "neighbour basins": len(nb[i])}
            for i in sorted(ids, key=lambda i: -length[i])]

    alive, ver = {i: True for i in ids}, {i: 0 for i in ids}

    def pair(a, b):
        """(category, rise, a, b, ...) or None when the join is not allowed (both hold fixed outlets)."""
        if fx[a] and fx[b]:
            return None
        s, lab = nb[a][b]
        if fx[a] or fx[b]:
            drain = b if fx[a] else a                                     # the basin without a fixed outlet drains
        else:
            drain = a if low[a] > low[b] or (low[a] == low[b] and a > b) else b
        cat = 0 if min(length[a], length[b]) < min_len else 1
        return (cat, round(s - low[drain], 6), a, b, ver[a], ver[b], s, lab, drain)

    heap = []
    for a in ids:
        for b in nb[a]:
            if a < b:
                p = pair(a, b)
                if p:
                    heap.append(p)
    heapq.heapify(heap)
    nalive, snaps, merges, phase2 = len(ids), {}, [], False

    def snap():
        if nalive <= max_zones and nalive not in snaps:
            snaps[nalive] = sorted(o for i in ids if alive[i] for o in outl[i])

    while heap:
        cat, rise, a, b, va, vb, s, lab, drain = heapq.heappop(heap)
        if not (alive[a] and alive[b]) or ver[a] != va or ver[b] != vb:
            continue
        if cat == 1 and not phase2:
            phase2 = True
            snap()
        keep, gone = (b, a) if drain == a else (a, b)                     # the draining basin joins the other
        merges.append({"step": len(merges) + 1, "zones after": nalive - 1, "forced (small basin)": "yes" if cat == 0 else "",
                       "joined": ", ".join(outl[gone]), "into": ", ".join(outl[keep]),
                       "over conduit": lab, "saddle GL (m)": round(s, 3), "rise over saddle (m)": round(rise, 2),
                       "length joined (m)": round(length[gone], 1)})
        count[keep] += count[gone]
        length[keep] += length[gone]
        fx[keep] |= fx[gone]
        low[keep] = min(low[keep], low[gone])
        outl[keep] = sorted(fx[keep]) if fx[keep] else outl[keep]
        for m, sv in list(nb[gone].items()):
            del nb[m][gone]
            if m == keep:
                continue
            if m not in nb[keep] or sv < nb[keep][m]:
                nb[keep][m] = nb[m][keep] = sv
        nb[gone].clear()
        alive[gone] = False
        ver[keep] += 1
        nalive -= 1
        for m in nb[keep]:
            p = pair(keep, m)
            if p:
                heapq.heappush(heap, p)
        if phase2:
            snap()
    snap()                                                                # final state (no join possible any more)
    return rows, merges, snaps


# ---------------------------------------------------------------- 3: zones from outlets
def zones_from_outlets(outlets, adj, E, gl, W):
    """Multi-source Dijkstra from the outlets, cost = length + W x rise (flow direction). Returns
    (zone {node: outlet}, parent {node: (downstream node, conduit)}, extra outlets added for parts
    without any outlet)."""
    part = parts_of(adj)
    have = {part[o] for o in outlets if o in part}
    extra = []
    for p in sorted(set(part.values()) - have):
        low = min((n for n in part if part[n] == p), key=lambda n: (gl[n], n))
        extra.append(low)
    dist, par, zone = {}, {}, {}
    heap = [(0.0, o, o) for o in list(outlets) + extra if o in adj]
    for _, o, _ in heap:
        dist[o] = 0.0
    heapq.heapify(heap)
    while heap:
        d, n, z = heapq.heappop(heap)
        if n in zone:
            continue
        zone[n] = z
        for m, lab in adj[n]:
            if m in zone:
                continue
            nd = d + E[lab]["L"] + W * max(0.0, gl[n] - gl[m])               # sewage flows m -> n
            if nd < dist.get(m, float("inf")) - 1e-9:
                dist[m] = nd
                par[m] = (n, lab)
                heapq.heappush(heap, (nd, m, z))
    return zone, par, extra


# ---------------------------------------------------------------- 4: design and compare one option
def evaluate(name, outlets, adj, E, gl, xy, W, R, sizes, pop_node, lpcd, crit, stp, pumps_added=frozenset(),
             cut_pop=True, force=None, mid_scale=None):
    """One zoning option. cut_pop: the head of a cut conduit (virtual node) gets its share of the cut manhole's
    population by sewer length (as pipeline.run does for the heads <MH>-C<n>); False = as the original scripts (none - the
    cut sewer carries no flow; tools/compare_with_agent_zoning.py). force = {conduit: {"force_D", "force_slope"}}
    given by the user (edits.apply). mid_scale = +15 years population / design population: the +15 years peak flow
    at every zone outlet too (the pumps are sized on it - CPHEEO Table 2.1 p2-9, user decision 21-Oct-2026)."""
    zone, par, extra = zones_from_outlets(outlets, adj, E, gl, W)
    tree = {lab for _, lab in par.values()}
    conds, ground, xyv, cuts, vnodes, vdn = [], dict(gl), dict(xy), [], set(), {}
    for m, (n, lab) in par.items():
        conds.append({"label": lab, "start_node": m, "stop_node": n})
    for lab, e in E.items():
        if lab in tree:
            continue
        a, b = e["a"], e["b"]
        dn, up = (a, b) if (gl[a], a) < (gl[b], b) else (b, a)          # sewer runs down to the lower end
        v = f"{up}{VSEP}{lab}"
        vnodes.add(v)
        vdn[v] = (up, dn, lab)
        ground[v] = gl[up]
        if up in xy:
            xyv[v] = xy[up]
        conds.append({"label": lab, "start_node": v, "stop_node": dn})
        cuts.append({"option": name, "conduit": lab, "disconnect at": up, "zone there": zone.get(up),
                     "sewer flows to": dn, "zone": zone.get(dn), "length (m)": round(e["L"], 1),
                     "GL disconnected end": round(gl[up], 3), "GL downstream end": round(gl[dn], 3),
                     "why": "zone boundary" if zone.get(up) != zone.get(dn) else "closes a loop"})
    for k in conds:
        k.update({"length_m": E[k["label"]]["L"], "flow_lps": 0.0, "n": None, "to_outfall": True,
                  "up_invert_m": None, "dn_invert_m": None}, **(force or {}).get(k["label"], {}))
    data = {"conduits": conds}
    pe = dict(pop_node)
    if cut_pop:
        for v, (up, dn, lab) in vdn.items():
            Lup = sum(E[l]["L"] for _, l in adj[up])
            share = pop_node.get(up, 0.0) * E[lab]["L"] / Lup if Lup else 0.0
            pe[up] = pe.get(up, 0.0) - share
            pe[v] = share
    zone_pop = collections.defaultdict(float)
    for n, p in pe.items():
        zone_pop[zone.get(vdn[n][1] if n in vdn else n)] += p
    if pop_node:
        avg = {n: p * lpcd / 86400.0 for n, p in pe.items()}
        c = crit["sewer"]
        flows = design_flows(data, avg, pe, set(pop_node), "table",
                             val(c, "peak_factor_by_population") or [],
                             {"basis": "none", "rate": 0.0, "cap": val(c, "infiltration_max_fraction")})
        for k in conds:
            k["flow_lps"] = flows[k["label"]]["Q"]
    flows_mid = None
    if pop_node and mid_scale:                     # the same loads x the +15 years share, each sewer its own peak factor
        flows_mid = design_flows(data, {n: a * mid_scale for n, a in avg.items()}, {n: p * mid_scale for n, p in pe.items()},
                                 set(pop_node), "table", val(c, "peak_factor_by_population") or [],
                                 {"basis": "none", "rate": 0.0, "cap": val(c, "infiltration_max_fraction")})
    res, node_inv, info = design_network(data, ground, R, sizes, None, xyv)

    lim6, limp = R.max_depth, R.max_depth_project
    real = [n for n in info if n not in vnodes]

    def over(n, lim):
        return lim is not None and info[n].get("depth") is not None and info[n]["depth"] > lim + 1e-6
    deep6 = {n for n in real if over(n, lim6)}                # deeper than CPHEEO 6 m - accepted up to limp
    deep = {n for n in real if over(n, limp)}                 # deeper than the project limit - must not stay
    # first conduits deeper than the project limit (no such sewer above them): a pumping station (new zone
    # outlet) at their upstream manhole keeps everything above it within the limit (evaluate_with_pumps)
    deep_above, first, blocked = {}, [], []
    for d in res.values():                                    # res is filled upstream-first
        above = deep_above.get(d["from"], False)
        dp = limp is not None and any(x is not None and x > limp + 1e-6 for x in (d["depth_up"], d["depth_dn"]))
        if dp and not above:
            x = d["from"]
            if x in vnodes or x in outlets or (d["depth_up"] or 0) > limp + 1e-6:
                blocked.append(d)                             # too deep already at its own start (e.g. wrong GL)
            else:
                first.append(x)
        deep_above[d["to"]] = deep_above.get(d["to"], False) or above or dp
    up_len = sum(d["length"] for d in res.values() if d["g_dn"] is not None and d["g_up"] is not None
                 and d["g_dn"] > d["g_up"] + CLIMB_M)
    cost, miss = priced_cost(res)
    zones = sorted(set(zone.values()))
    zrows = []
    for z in zones:
        zn = [n for n in real if zone.get(n) == z]
        zc = [d for d in res.values() if zone.get(d["to"].split(VSEP)[0]) == z]
        q_out = sum(d["q"] for d in zc if d["to"] == z)
        q_mid = sum(flows_mid[d["label"]]["Q"] for d in zc if d["to"] == z and d["label"] in flows_mid) if flows_mid else None
        zd = [info[n]["depth"] for n in zn if info[n].get("depth") is not None]
        dist_stp = (math.hypot(xy[z][0] - xy[stp][0], xy[z][1] - xy[stp][1])
                    if stp and z in xy and stp in xy and z != stp and zone.get(stp) != z else None)
        zrows.append({"option": name, "zone outlet": z, "outlet GL (m)": round(gl[z], 3),
                      "outlet invert (m)": round(info[z]["invert"], 3) if info.get(z, {}).get("invert") is not None else None,
                      "outlet depth = wet well (m)": round(info[z]["depth"], 2) if info.get(z, {}).get("depth") is not None else None,
                      "manholes": len(zn), "sewer length (m)": round(sum(d["length"] for d in zc), 1),
                      "GL min": round(min(gl[n] for n in zn), 2) if zn else None,
                      "GL max": round(max(gl[n] for n in zn), 2) if zn else None,
                      "design flow at outlet (L/s)": round(q_out, 2),
                      "+15 years flow at outlet (L/s)": round(q_mid, 2) if q_mid is not None else None,
                      "max depth (m)": round(max(zd), 2) if zd else None,
                      "manholes deeper than CPHEEO limit": sum(1 for n in zn if n in deep6),
                      "manholes deeper than project limit": sum(1 for n in zn if n in deep),
                      "sewer climbing against ground (m)": round(sum(d["length"] for d in zc if d["g_dn"] is not None
                                                                     and d["g_up"] is not None and d["g_dn"] > d["g_up"] + CLIMB_M), 1),
                      "pipe cost (Rs lakh)": round(priced_cost({d["label"]: d for d in zc})[0] / 1e5, 2),
                      "role": ("STP (gravity)" if stp and zone.get(stp) == z else "pumping station"),
                      "why this outlet": ("added - sewer deeper than the project limit" if z in pumps_added
                                          else "outlet added (part had no outlet)" if z in extra else "zoning"),
                      "straight distance to STP (m)": round(dist_stp, 0) if dist_stp is not None else None})
    ps = sum(1 for z in zones if zone.get(stp) != z) if stp else max(len(zones) - 1, 0)
    deps = [info[n]["depth"] for n in real if info[n].get("depth") is not None]
    m = {"option": name, "zones": len(zones), "outlets": ", ".join(zones),
         "pumping stations": ps, "of these added for depth": len([z for z in zones if z in pumps_added]),
         "max depth (m)": round(max(deps), 2) if deps else None,
         "manholes deeper than CPHEEO limit": len(deep6),
         "manholes deeper than project limit": len(deep),
         "deep conduits not solved": len(blocked),
         "sewer with an end deeper than CPHEEO limit (m)": round(sum(d["length"] for d in res.values()
                                                                if d["to"] in deep6 or d["from"] in deep6), 0),
         "sewer climbing against ground (m)": round(up_len, 0),
         "cut conduits (disconnect one end)": len(cuts), "pipe cost (Rs lakh)": round(cost / 1e5, 2),
         "no rate for": ", ".join(miss), "outlets added (part without outlet)": ", ".join(extra)}
    return {"m": m, "zones": zrows, "cuts": cuts, "zone": zone, "res": res, "info": info, "deep": deep,
            "deep6": deep6, "vnodes": vnodes, "first_deep": sorted(set(first)), "blocked": blocked,
            "zone_pop": dict(zone_pop),
            "pumps_added": [z for z in zones if z in pumps_added]}


def evaluate_with_pumps(name, outlets, *args, max_rounds=40, **kw):
    """Lift stations are not built (project decision): where the gravity sewer of a zone goes deeper than
    max_depth_project_m, the manhole just above that point becomes a NEW zone outlet = pumping station, and the
    zones are drawn again; repeated until no sewer is deeper than the limit (or what is left cannot be solved -
    'deep conduits not solved', usually a wrong GL)."""
    outs, added = list(outlets), []
    for _ in range(max_rounds):
        ev = evaluate(name, outs, *args, pumps_added=set(added), **kw)
        new = [x for x in ev["first_deep"] if x not in outs]
        if not new:
            return ev
        outs += new
        added += new
    return ev


# ---------------------------------------------------------------- zone areas
def triangulate(gl, xy, max_edge):
    """Delaunay triangles of the manholes; triangles with a side longer than max_edge dropped (no data there).
    Returns (node labels, X, Y, triangles as index triples) or None (no matplotlib / too few points)."""
    try:
        import matplotlib.tri as mtri
        import numpy as np
    except ImportError:
        return None
    ns = [n for n in gl if n in xy]
    if len(ns) < 3:
        return None
    X = np.array([xy[n][0] for n in ns])
    Y = np.array([xy[n][1] for n in ns])
    t = mtri.Triangulation(X, Y).triangles
    el = np.max(np.stack([np.hypot(X[t[:, i]] - X[t[:, j]], Y[t[:, i]] - Y[t[:, j]])
                          for i, j in ((0, 1), (1, 2), (2, 0))]), axis=0)
    return ns, X, Y, t[el <= max_edge]


def zone_regions(tg, zone):
    """Area of every zone from the manhole triangles: each triangle is split into three pieces, one per corner
    manhole (corner - edge midpoint - centroid - edge midpoint), each piece belongs to its manhole's zone. So a
    boundary runs halfway between manholes of different zones; the outer edge follows the triangles (white =
    no data stays outside). Returns {zone: {"rings": [[(x, y), ...], ...], "area": m2, "label": (x, y),
    "pieces": [[(x, y) x4], ...]}}."""
    ns, X, Y, T = tg
    edges = collections.defaultdict(collections.Counter)
    pieces = collections.defaultdict(list)
    area = collections.defaultdict(float)
    sx, sy = collections.defaultdict(float), collections.defaultdict(float)
    key = lambda p: (round(p[0], 4), round(p[1], 4))                          # noqa: E731
    for tri in T:
        P = [(float(X[i]), float(Y[i])) for i in tri]
        c = ((P[0][0] + P[1][0] + P[2][0]) / 3, (P[0][1] + P[1][1] + P[2][1]) / 3)
        A = abs((P[1][0] - P[0][0]) * (P[2][1] - P[0][1]) - (P[2][0] - P[0][0]) * (P[1][1] - P[0][1])) / 2
        for k in range(3):
            z = zone.get(ns[tri[k]])
            if z is None:
                continue
            v, u, w = P[k], P[(k + 1) % 3], P[(k + 2) % 3]
            m1 = ((v[0] + u[0]) / 2, (v[1] + u[1]) / 2)
            m2 = ((v[0] + w[0]) / 2, (v[1] + w[1]) / 2)
            for p, q in ((v, m1), (m1, c), (c, m2), (m2, v)):
                kp, kq = key(p), key(q)
                edges[z][(min(kp, kq), max(kp, kq))] += 1
            pieces[z].append([v, m1, c, m2])
            area[z] += A / 3
            sx[z] += A / 3 * (v[0] + m1[0] + c[0] + m2[0]) / 4
            sy[z] += A / 3 * (v[1] + m1[1] + c[1] + m2[1]) / 4
    out = {}
    for z, cnt in edges.items():
        bnd = [e for e, n in cnt.items() if n % 2 == 1]                   # shared twice = inside the zone
        adj = collections.defaultdict(list)
        for i, (p, q) in enumerate(bnd):
            adj[p].append(i)
            adj[q].append(i)
        used, rings = set(), []
        for i0 in range(len(bnd)):
            if i0 in used:
                continue
            used.add(i0)
            start, cur = bnd[i0]
            ring = [start, cur]
            while cur != start:
                nxt = next((j for j in adj[cur] if j not in used), None)
                if nxt is None:
                    break
                used.add(nxt)
                p, q = bnd[nxt]
                cur = q if p == cur else p
                ring.append(cur)
            if len(ring) >= 4:
                rings.append(ring)
        # label: the zone's manhole nearest the area-weighted centre (always inside the zone)
        g = (sx[z] / area[z], sy[z] / area[z]) if area[z] else None
        mh = [i for i, n in enumerate(ns) if zone.get(n) == z]
        lab = None
        if g and mh:
            i = min(mh, key=lambda i: (X[i] - g[0]) ** 2 + (Y[i] - g[1]) ** 2)
            lab = (float(X[i]), float(Y[i]))
        out[z] = {"rings": rings, "area": area[z], "label": lab, "pieces": pieces[z]}
    return out


# ---------------------------------------------------------------- one zoning run
def run(net, inp, crit=None, stp=None, outfalls=(), max_zones=8, min_zone_m=None, spike_gl="keep",
        band_max_edge=None, log=print, cut_pop=True, given_only=True, only_given=False, fixed_inv=None):
    """Zoning options of a network. inp = the design inputs (pop_total, pop_dist, pop_csv, sewage_lpcd,
    start_depth, catalog, joint - as pipeline.run): population from the file when pop_dist is 'csv', otherwise
    spread by sewer length. stp / outfalls = fixed outlets. cut_pop: see evaluate. The user's edits (edits.apply):
    a conduit's force_D / force_slope and fixed_inv {manhole: outgoing invert}. Returns a dict for
    write_workbook / cost_workbook."""
    crit = crit or load_criteria()
    nodes, edges, model_outs = from_network(net)
    adj, E, gl, notes, n_spikes = prepare(nodes, edges, spike_gl)
    xy = {n: nodes[n][1] for n in adj if nodes[n][1]}
    fixed = [x for x in ([stp] if stp else []) + list(outfalls)]
    bad = [x for x in fixed if x not in adj]
    if bad:
        raise ValueError(f"not a connected node of this network: {', '.join(bad)}")
    total = sum(e["L"] for e in E.values())
    min_len = min_zone_m if min_zone_m is not None else max(1000.0, 0.02 * total)
    log(f"Network: {len(adj)} nodes, {len(E)} conduits, {total:,.0f} m, {len(set(parts_of(adj).values()))} part(s); "
        f"GL {min(gl.values()):.2f} - {max(gl.values()):.2f} m")

    R = Rules(crit)
    R.fixed_inv = dict(fixed_inv or {})
    force = {k["label"]: {"force_D": k.get("force_D"), "force_slope": k.get("force_slope")}
             for k in net["conduits"] if k.get("force_D") or k.get("force_slope")}
    dmin = (R.dmin or 0) / 1000.0
    if inp.get("start_depth"):
        R.cover = float(inp["start_depth"]) - dmin
    cat_name, cat_src, sizes = load_catalog(inp.get("catalog"), inp.get("joint") or "ss")
    _, smin = slope_row(R.slopes, R.dmin or sizes[0]["id_mm"])
    W = 1.0 / smin if smin else 250.0
    pop_node, lpcd = {}, inp.get("sewage_lpcd")
    # the pumps of the pumping stations: on the +15 years flow when its population is given (CPHEEO Table 2.1 p2-9:
    # pumping machinery 15 years; civil works 30 years) - user decision 21-Oct-2026
    mid_scale = (float(inp["pop_mid"]) / float(inp["pop_total"])
                 if inp.get("pop_mid") and inp.get("pop_total") and float(inp["pop_total"]) > 0 else None)
    if inp.get("pop_total"):
        if not lpcd:
            lpcd = val(crit["sewer"], "min_sewage_flow_lpcd") or 100
            log(f"(note) sewage per capita not given - CPHEEO minimum {lpcd} L/capita/day used")
        w = collections.defaultdict(float)
        for e in E.values():
            w[e["a"]] += e["L"] / 2
            w[e["b"]] += e["L"] / 2
        tw = sum(w.values()) or 1.0
        pop_node = {n: float(inp["pop_total"]) * w[n] / tw for n in adj}
    if inp.get("pop_dist") == "csv" and inp.get("pop_csv"):
        if not lpcd:
            lpcd = val(crit["sewer"], "min_sewage_flow_lpcd") or 100
        from .flows import distribute_population
        f = distribute_population(0, "csv", {"conduits": []}, [], inp["pop_csv"])
        sc = float(inp.get("pop_scale") or 1.0)          # wards' population scaled to the design population (forecast)
        pop_node = {n: f.get(n, 0.0) * sc for n in adj}
        log(f"Population from {inp['pop_csv']}: {sum(pop_node.values()):,.0f} persons on the network's manholes "
            f"(file {sum(f.values()):,.0f})")
    elif not inp.get("pop_total"):
        log("(note) no population - zero flow: every pipe at the smallest size, depths of the trunk sewers are "
            "UNDER-estimated")

    brows, merges, snaps = terrain_options(adj, E, gl, set(fixed), min_len, max_zones)
    log(f"Terrain basins (steepest descent): {len(brows)}; options with "
        f"{', '.join(str(k) for k in sorted(snaps, reverse=True))} zone(s)")
    opts = [(f"T{k}", outs) for k, outs in sorted(snaps.items(), reverse=True)]
    cur = sorted(set(model_outs) | set(fixed))
    if model_outs:
        opts.insert(0, ("CURRENT", cur))
    if only_given:                     # design on the given outfalls only: no other option is worked out
        if not cur:
            raise ValueError("no outfall given: mark the outfall(s) or give the STP manhole")
        opts, given_only = [], True
    evals = []
    for name, outs in opts:
        t1 = time.time()
        ev = evaluate_with_pumps(name, outs, adj, E, gl, xy, W, R, sizes, pop_node, lpcd, crit, stp, cut_pop=cut_pop,
                                 force=force, mid_scale=mid_scale)
        evals.append(ev)
        m = ev["m"]
        log(f"   {name:<8} {m['zones']:>3} zone(s), pumping stations {m['pumping stations']:>3} "
            f"({m['of these added for depth']} added for depth): max depth {m['max depth (m)']} m, "
            f"pipe Rs {m['pipe cost (Rs lakh)']:,.2f} lakh  ({time.time() - t1:.0f} s)")
    rank = sorted(evals, key=lambda ev: (ev["m"]["pumping stations"], ev["m"]["manholes deeper than project limit"],
                                         ev["m"]["manholes deeper than CPHEEO limit"], ev["m"]["pipe cost (Rs lakh)"]))
    if given_only and cur:
        # option GIVEN (user request 13-Oct-2026): only the given outfalls (and the STP) - no pumping station added
        # for depth, however deep the sewer gets. Listed after the ranked options (it is not ranked: its depth is
        # not limited); a part of the network without any outfall still gets an outlet (its lowest manhole).
        t1 = time.time()
        ev = evaluate("GIVEN", cur, adj, E, gl, xy, W, R, sizes, pop_node, lpcd, crit, stp, cut_pop=cut_pop,
                      force=force, mid_scale=mid_scale)
        m = ev["m"]
        log(f"   {'GIVEN':<8} {m['zones']:>3} zone(s), only the given outfalls (no pumping station for depth): max "
            f"depth {m['max depth (m)']} m, {m['manholes deeper than project limit']} manhole(s) deeper than the "
            f"project limit, pipe Rs {m['pipe cost (Rs lakh)']:,.2f} lakh  ({time.time() - t1:.0f} s)")
        rank.append(ev)
    for i, ev in enumerate(rank, 1):
        ev["m"]["rank"] = i
    Ls = sorted(e["L"] for e in E.values() if e["L"])
    max_edge = band_max_edge or (max(150.0, 5 * Ls[len(Ls) // 2]) if Ls else 150.0)
    tg = triangulate(gl, xy, max_edge)
    for ev in rank:
        ev["regs"] = zone_regions(tg, ev["zone"]) if tg else {}
        for z in ev["zones"]:
            rg = ev["regs"].get(z["zone outlet"])
            z["zone area (ha)"] = round(rg["area"] / 1e4, 2) if rg else None
    return {"rank": rank, "basins": brows, "merges": merges, "notes": notes, "n_spikes": n_spikes, "adj": adj,
            "E": E, "gl": gl, "xy": xy, "model_outs": model_outs, "fixed": fixed, "stp": stp, "outfalls": list(outfalls),
            "total": total, "min_len": min_len, "W": W, "R": R, "crit": crit, "catalog": (cat_name, cat_src),
            "joint": inp.get("joint") or "ss", "pop": inp.get("pop_total"), "lpcd": lpcd, "spike_gl": spike_gl,
            "max_edge": max_edge, "pop_node": pop_node, "mid_scale": mid_scale, "pop_mid": inp.get("pop_mid"), "pop_csv": inp.get("pop_csv") if inp.get("pop_dist") == "csv"
            else None, "cut_pop": cut_pop}


def write_workbook(z, path, source=""):
    """Zoning workbook: Summary, Options, Zones, Cut conduits, Node zones, Basins, Merges, GL notes."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    bold, head = Font(bold=True), PatternFill("solid", fgColor="D9E1F2")
    wb = Workbook()
    rank, R, adj, gl, xy = z["rank"], z["R"], z["adj"], z["gl"], z["xy"]
    dmin = (R.dmin or 0) / 1000.0

    def sheet(title, rows):
        ws = wb.create_sheet(title)
        cols = list(rows[0].keys()) if rows else ["(none)"]
        ws.append(cols)
        for c in ws[1]:
            c.font, c.fill = bold, head
            c.alignment = Alignment(wrap_text=True, vertical="top")
        for r in rows:
            ws.append([r.get(c) for c in cols])
        for i, c in enumerate(cols, 1):
            ws.column_dimensions[get_column_letter(i)].width = max(11, min(len(c) + 2, 40))
        ws.freeze_panes = "B2"
        return ws

    stp, outs = z["stp"], z["outfalls"]
    summ = [("Source", source), ("Read", time.strftime("%d-%m-%Y %H:%M")),
            ("Network", f"{len(adj)} nodes, {len(z['E'])} conduits, {z['total']:,.1f} m"),
            ("Fixed outlets", f"STP {stp or '-'}; others {', '.join(outs) or '-'}"),
            ("Outfalls in the network", ", ".join(z["model_outs"]) or "-"),
            ("GL for zoning", f"{z['spike_gl']}: spikes {'replaced by neighbours mean' if z['spike_gl'] == 'neighbour' else 'kept'}; "
                              f"missing GL from neighbours - sheet 'GL notes'"),
            ("Start depth / cover", f"{R.cover + dmin:.2f} m / {R.cover:.2f} m"),
            ("Pipe catalog", f"{z['catalog'][0]} ({z['joint']}) - {z['catalog'][1]}"[:300]),
            ("Population", (f"{sum(z['pop_node'].values()):,.0f} from {z['pop_csv']}" if z.get("pop_csv") else
                            f"{z['pop'] or 0:,.0f}") + f" at {z['lpcd'] or 0:g} L/capita/day"
                           + ("" if z.get("pop_csv") else ", spread by sewer length")
                           + ("; a cut conduit's head gets its share of the cut manhole's population by sewer length"
                              if z.get("cut_pop", True) else "; cut conduits carry no flow (as the original scripts)")
                           + "; Table 3.2 peak factor; no infiltration"),
            ("Minimum zone length", f"{z['min_len']:,.0f} m - screening choice (min_zone_m), not from the manual"),
            ("Climbing weight W", f"{z['W']:.0f} m of sewer per m of rise = 1 / Table 3.13 minimum slope of {R.dmin:g} mm"),
            ("Depth / lift stations", f"NO lift stations (project decision, lift_stations_allowed); sewers down to "
                                      f"max_depth_project_m {R.max_depth_project:g} m (project decision); deeper -> new "
                                      f"zone + pumping station; depths beyond the CPHEEO {R.max_depth:g} m (p205) are "
                                      f"listed - justify in the DPR"),
            ("Method", "1 terrain basins by steepest descent along the streets; 2 basins joined (small first, then least "
                       "rise over the saddle) - each number of zones = one option; 3 zones re-drawn from the outlets by "
                       "least length + W x rise; conduits not on the tree are cut (one end disconnected); 4 each option "
                       "designed with design_network"),
            ("Ranking", "pumping stations, then manholes deeper than the project / CPHEEO limit, then pipe "
                        "cost - an ordering only; pumping-station civil, pump, rising main and power costs are NOT "
                        "included (no sourced rate). The choice of zoning is a project decision."),
            ("Pumping stations", "zones whose outlet is not the STP zone" if stp else
                          "zones - 1 (one zone assumed to reach the STP by gravity; give the STP to fix it)"),
            ("Not changed", "the network was not changed; set the chosen outlets as outfalls and disconnect the cut "
                            "conduits, then design")]
    ws = wb.active
    ws.title = "Summary"
    for k, v in summ:
        ws.append([k, v])
        ws.cell(row=ws.max_row, column=1).font = bold
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 140
    sheet("Options", [dict({"rank": ev["m"]["rank"]}, **{k: v for k, v in ev["m"].items() if k != "rank"}) for ev in rank])
    sheet("Zones", [zz for ev in rank for zz in ev["zones"]])
    sheet("Cut conduits", [c for ev in rank for c in ev["cuts"]])
    nz = []
    for n in sorted(adj):
        row = {"node": n, "GL used (m)": round(gl[n], 3), "X": xy.get(n, (None,))[0],
               "Y": xy.get(n, (None, None))[1]}
        for ev in rank:
            row[f"{ev['m']['option']} zone"] = ev["zone"].get(n)
            row[f"{ev['m']['option']} depth (m)"] = (round(ev["info"][n]["depth"], 2)
                                                    if ev["info"].get(n, {}).get("depth") is not None else None)
        nz.append(row)
    sheet("Node zones", nz)
    sheet("Basins", z["basins"])
    sheet("Merges", z["merges"])
    sheet("GL notes", z["notes"])
    if z.get("gl_bands"):
        rows_b, text_b = z["gl_bands"]
        sheet("GL bands", rows_b)
        ws.append(["GL band map", text_b])
        ws.cell(row=ws.max_row, column=1).font = bold
    wb.save(path)
    return path


def cost_workbook(z, path, source=""):
    """Separate Excel comparing the cost of every option: its design without lift stations (pumping stations at
    the zone outlets only). Items with a sourced rate: pipe supply (catalog), laying by depth slice, excavation
    slice-wise, timbering (sewer_sor_rates.json - the same rules as the Cost sheet of the design report);
    amounts are Excel formulas. Pumping stations at the zone outlets: approximate capex and O&M present value
    (pumping.py). Quantities without a rate are listed, not priced. Sheets: Comparison, Items, Quantities, Notes,
    Pumping stations, SPS components."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    rank, crit, R = z["rank"], z["crit"], z["R"]
    cat_name, cat_src = z["catalog"]
    sr = load_sewer_rates()
    bold, head = Font(bold=True), PatternFill("solid", fgColor="D9E1F2")
    yellow = PatternFill("solid", fgColor="FFF2CC")
    wb = Workbook()
    wc = wb.active
    wc.title = "Comparison"
    wi = wb.create_sheet("Items")
    wq = wb.create_sheet("Quantities")
    wn = wb.create_sheet("Notes")
    wi.append(["Option", "Design", "Group", "Item", "Rate item", "Quantity calculation", "Unit", "Quantity",
               "Rate (Rs)", "Amount (Rs)"])
    bands = sr["depth_bands_m"]["value"] if sr else []
    blab = [f"{a:g}-{b:g}" for a, b in zip([0.0] + bands[:-1], bands)]
    DES = "no lift stations"
    groups = ["1 pipe supply", "2 laying", "3 excavation", "4 timbering", "5 pumping stations (approx.)",
              "6 pumping O&M (approx., present value)", "7 rising mains (approx.)"]
    K = rising_main.load_rates()
    qrows_all = []
    P = pumping.load_params()
    yrs = P["npv_years"]["value"]
    sps_rows, comp_rows = [], []
    pop_node, lpcd = z.get("pop_node") or {}, z.get("lpcd") or 0.0
    ms = z.get("mid_scale")                      # pumps on the +15 years flow (CPHEEO Table 2.1 p2-9) when given
    totals = collections.defaultdict(lambda: collections.defaultdict(float))

    def add(opt, des, grp, item, code, calc, unit, qty, rate):
        r_ = wi.max_row + 1
        wi.append([opt, des, grp, item, code, calc, unit, round(qty, 2), rate,
                   f'=IF(I{r_}="","",ROUND(H{r_}*I{r_},0))'])
        if rate in (None, ""):
            wi.cell(row=r_, column=9).fill = yellow
        else:                                                 # the same number as the Excel formula, for the UI
            totals[opt][grp] += round(round(qty, 2) * rate, 0)

    def price(opt, des, res):
        agg, szof = collections.defaultdict(float), {}
        for d in res.values():
            k = (d["size"]["material"], d["size"]["nominal"], d["D"])
            agg[k] += d["length"] or 0.0
            szof[k] = d["size"]
        for (mat, nom, D), L in sorted(agg.items(), key=lambda x: x[0][2]):
            rt = szof[(mat, nom, D)].get("rate_rs_per_m")
            add(opt, des, groups[0], f"Supply of {mat} pipe {nom} (ID {D:g} mm)",
                rate_ref(szof[(mat, nom, D)]) or ("" if rt else "NO RATE in catalog"),
                f"designed length of ID {D:g} mm", "m", L, float(rt) if rt else None)
        q = slice_quantities(res, sr) if sr else []
        if q:
            lay = sr["laying_rcc_np3"]["by_nominal_mm"]
            for nom in sorted({x["nom"] for x in q}):
                for i, b in enumerate(blab):
                    tot = sum(x["lens"][i] for x in q if x["nom"] == nom)
                    if tot > 0.0005:
                        spec = lay.get(str(nom))
                        add(opt, des, groups[1], f"Laying & jointing RCC NP3 {nom} mm, invert depth {b} m",
                            spec["codes"][i] if spec else "NO SOR item", f"length at depth {b} m", "m", tot,
                            spec["rates"][i] if spec else None)
            if any(x["vols"] for x in q):
                ex = sr["excavation_ordinary_soil"]
                for i, b in enumerate(blab):
                    tot = sum(x["vols"][i] for x in q if x["vols"])
                    if tot > 0.0005:
                        add(opt, des, groups[2], f"Excavation ordinary soil incl. refilling, slice {b} m below GL",
                            ex["codes"][i], f"stepped trench (Riverside DPR rule), slice {b} m", "cum", tot,
                            ex["rates"][i])
            tr = (sr.get("timbering_rule") or {}).get("value")
            tt = sum(x["timb"] or 0 for x in q)
            if isinstance(tr, dict) and tt:
                code = tr.get("code", "3041")
                rate = next((r__ for key in ("timbering_open", "timbering_close")
                             for c__, r__ in zip(sr.get(key, {}).get("codes", []), sr.get(key, {}).get("rates", []))
                             if c__ == code), None)
                add(opt, des, groups[3], f"{str(tr.get('type', '')).capitalize()} timbering 0-"
                    f"{tr.get('upto_depth_m', 3):g} m (trenches deeper than {tr.get('min_depth_m', 0):g} m)", code,
                    "min(depth, 3 m) x length, project decision", "sqm", tt, rate)
        return q

    for ev in rank:
        opt, vn = ev["m"]["option"], ev["vnodes"]
        q = price(opt, DES, ev["res"])
        res, info = ev["res"], ev["info"]
        real = [n for n in info if n not in vn]
        cnt = [0] * (len(DEPTH_BANDS) + 1)
        for n in real:
            dp = info[n].get("depth")
            if dp is not None and not info[n].get("outfall"):
                cnt[next((i for i, b in enumerate(DEPTH_BANDS) if dp <= b), len(DEPTH_BANDS))] += 1
        new_mh = 0
        for lab, d in res.items():
            lim = spacing_limit(crit, lab, d["D"])
            if lim and (d["length"] or 0) > lim + 0.5:
                new_mh += math.ceil(d["length"] / lim - 1e-9) - 1
        deps = [x for d in res.values() for x in (d["depth_up"], d["depth_dn"]) if x is not None]
        qq = {"option": opt, "zones": ev["m"]["zones"], "pumping stations": ev["m"]["pumping stations"],
              "of these added for depth": ev["m"]["of these added for depth"],
              "deep conduits not solved": ev["m"]["deep conduits not solved"],
              "max depth (m)": round(max(deps), 2) if deps else None,
              "sewer length (m)": round(sum(d["length"] or 0 for d in res.values()), 1)}
        lbl = ([f"0-{DEPTH_BANDS[0]}"] + [f"{a}-{b}" for a, b in zip(DEPTH_BANDS, DEPTH_BANDS[1:])]
               + [f">{DEPTH_BANDS[-1]}"])
        for l_, c_ in zip(lbl, cnt):
            qq[f"manholes, depth {l_} m"] = c_
        qq["new manholes for 30 m spacing (estimate)"] = new_mh
        qq["drop manholes"] = sum(1 for n in real if info[n].get("drop"))
        qq["road cutting area (sqm)"] = round(sum((x["W"] or 0) * x["L"] for x in q), 1) if q else None
        qq["cut conduits (disconnect one end)"] = ev["m"]["cut conduits (disconnect one end)"]
        # ---- pumping stations (approximate, pumping.py): every zone outlet that is not the STP; without an STP
        #      the zone with the largest outlet flow is taken as reaching the STP by gravity (assumption)
        zr = [x for x in ev["zones"] if x["role"] == "pumping station"]
        if not z["stp"] and zr:
            grav = max(zr, key=lambda x: (x["design flow at outlet (L/s)"] or 0, x["zone outlet"]))
            zr = [x for x in zr if x is not grav]
        capex_t = om_t = rm_t = 0.0
        n_sps = 0
        for x in zr:
            o, qp, dep = x["zone outlet"], x["design flow at outlet (L/s)"] or 0.0, x["outlet depth = wet well (m)"] or 0.0
            if qp <= 0:
                continue
            qa = (ev["zone_pop"].get(o, 0.0) if "zone_pop" in ev else
                  sum(p for n, p in pop_node.items() if ev["zone"].get(n) == o)) * lpcd / 86400.0
            dist = x.get("straight distance to STP (m)")
            rm = rising_main.rising_main(qp, dist, K) if dist else None
            qm = x.get("+15 years flow at outlet (L/s)") if ms else None
            if qm:                                      # pumps, E&M and energy on +15 years; civil on +30 years
                qa *= ms
            c = pumping.sps_cost(qp, qa, dep, P, rm_head=rm["head_m"] if rm else None, q_em_lps=qm or None)
            q_pump = qm or qp
            basis = (f"+15 years (CPHEEO Table 2.1 p2-9: pumping machinery 15 years)" if qm
                     else "+30 years (no +15 years population given)")
            capex_t += c["capex"]
            om_t += c["om_npv"]
            n_sps += 1
            if rm:
                rm_t += rm["cost_lakh"]
                add(opt, DES, groups[6], f"Rising main from {o} to the STP: {rm['n']} x DI {rm['dia']} mm, "
                    f"{rm['length']:.0f} m", "approx. (data/rising_main_rates.json)",
                    f"straight {dist:.0f} m x route factor; v {rm['velocity']:.2f} m/s, friction {rm['friction_m']:.1f} m; "
                    f"Rs {rm['per_m']:.0f}/m per main (supply, SOR laying, specials, excavation, thrust blocks)",
                    "m", rm["n"] * rm["length"], round(rm["per_m"], 2))
            supply = "HT" if c["ht"] else "LT"
            add(opt, DES, groups[4], f"Pumping station at {o} ({qp:.1f} L/s peak, incoming sewer {dep:.2f} m deep)",
                "approx. (data/pumping_station_cost.json)", f"civil {c['civil']:.1f} (on {qp:.1f} L/s) + E&M "
                f"{c['em']:.1f} + power connection {c['power']:.1f} lakh; pumps "
                f"{c['kw']:.1f} kW working on {q_pump:.1f} L/s, {supply} supply", "No", 1, round(c["capex"] * 1e5))
            add(opt, DES, groups[5], f"O&M of the pumping station at {o}, {yrs} years (present value)",
                "approx. (data/pumping_station_cost.json)", f"{c['om_year']:.2f} lakh / year (energy {c['energy_year']:.2f} "
                f"at {qa:.1f} L/s average, head {c['head']:.1f} m)", "No", 1, round(c["om_npv"] * 1e5))
            sps_rows.append({"option": opt, "pumping station (zone outlet)": o, "peak flow (L/s)": round(qp, 2),
                             "pumps sized on (L/s)": round(q_pump, 2), "pumps basis": basis,
                             "average flow (L/s)": round(qa, 2), "incoming sewer depth (m)": round(dep, 2),
                             "pump head (m)": round(c["head"], 2), "pumps working (kW)": round(c["kw"], 1),
                             "connected load (kW)": round(c["connected_kw"], 1), "supply": supply,
                             "wet well dia (m)": round(c["wet_well_dia"], 2),
                             "wet well height (m)": round(c["wet_well_height"], 2),
                             "civil (Rs lakh)": round(c["civil"], 2), "E&M (Rs lakh)": round(c["em"], 2),
                             "power connection (Rs lakh)": round(c["power"], 2),
                             "capex (Rs lakh)": round(c["capex"], 2), "O&M per year (Rs lakh)": round(c["om_year"], 2),
                             f"O&M {yrs} yr present value (Rs lakh)": round(c["om_npv"], 2),
                             "capex + O&M (Rs lakh)": round(c["total_npv"], 2),
                             "rising main": (f"{rm['n']} x DI {rm['dia']} mm, {rm['length']:.0f} m" if rm
                                             else "not priced (no STP given)"),
                             "rising main (Rs lakh)": round(rm["cost_lakh"], 2) if rm else None})
            for g_, name, amt, how in c["components"]:
                comp_rows.append({"option": opt, "pumping station": o, "group": g_, "component": name,
                                  "Rs lakh": round(amt, 2), "how": how})
        qq["pumping stations priced"] = n_sps
        qq["pumping stations capex (Rs lakh, approx.)"] = round(capex_t, 1)
        qq[f"pumping O&M {yrs} yr PV (Rs lakh, approx.)"] = round(om_t, 1)
        qq["rising mains (Rs lakh, approx.)"] = round(rm_t, 1) if z["stp"] else "no STP given"
        qrows_all.append(qq)
    last = wi.max_row
    for c in wi[1]:
        c.font, c.fill = bold, head
        c.alignment = Alignment(wrap_text=True, vertical="top")
    for col, w in zip("ABCDEFGHIJ", (9, 17, 15, 60, 16, 44, 6, 13, 11, 15)):
        wi.column_dimensions[col].width = w
    wi.freeze_panes = "A2"
    wi.auto_filter.ref = wi.dimensions

    cols = list(qrows_all[0].keys()) if qrows_all else ["(none)"]
    wq.append(cols)
    for r_ in qrows_all:
        wq.append([r_.get(c) for c in cols])
    for c in wq[1]:
        c.font, c.fill = bold, head
        c.alignment = Alignment(wrap_text=True, vertical="top")
    for i in range(1, len(cols) + 1):
        wq.column_dimensions[get_column_letter(i)].width = 14
    wq.freeze_panes = "B2"

    hdr = (["Rank", "Option", "Zones", "Pumping stations", "of these added for depth", "Max depth (m)",
            "MH deeper than CPHEEO 6 m", "Deep conduits not solved"]
           + [f"{g[2:].capitalize()} (Rs)" for g in groups]
           + ["TOTAL priced (Rs)", "TOTAL priced (Rs lakh)", "More than the cheapest (Rs lakh)",
              "Cost order (1 = cheapest)", "Items without rate"])
    wc.append(hdr)
    first, n_opt = 2, len(rank)
    ng = len(groups)
    gcol = [get_column_letter(9 + i) for i in range(ng)]
    tcol, lcol = get_column_letter(9 + ng), get_column_letter(10 + ng)
    for k, ev in enumerate(rank):
        r_ = first + k
        m = ev["m"]
        row = [m["rank"], m["option"], m["zones"], m["pumping stations"], m["of these added for depth"],
               m["max depth (m)"], m["manholes deeper than CPHEEO limit"], m["deep conduits not solved"]]
        for g in groups:
            row.append(f'=SUMIFS(Items!$J$2:$J${last},Items!$A$2:$A${last},$B{r_},Items!$C$2:$C${last},"{g}")')
        row.append(f"=SUM({gcol[0]}{r_}:{gcol[-1]}{r_})")
        row.append(f"=ROUND({tcol}{r_}/100000,2)")
        row.append(f"=ROUND(({tcol}{r_}-MIN(${tcol}${first}:${tcol}${first + n_opt - 1}))/100000,2)")
        row.append(f"=RANK({tcol}{r_},${tcol}${first}:${tcol}${first + n_opt - 1},1)")
        row.append(f'=COUNTIFS(Items!$A$2:$A${last},$B{r_},Items!$I$2:$I${last},"")')
        wc.append(row)
    for c in wc[1]:
        c.font, c.fill = bold, head
        c.alignment = Alignment(wrap_text=True, vertical="top")
    widths = [6, 10, 7, 10, 10, 9, 11, 10] + [15] * ng + [17, 14, 13, 10, 9]
    for i, w in enumerate(widths, start=1):
        wc.column_dimensions[get_column_letter(i)].width = w
    for row in wc.iter_rows(min_row=2, max_row=first + n_opt - 1, min_col=9, max_col=9 + ng):
        for c in row:
            c.number_format = "#,##0"
    for rr in range(first, first + n_opt):
        wc[f"{lcol}{rr}"].font = bold
    wc.freeze_panes = "C2"
    wc.append([])
    for txt in ("Rank = order of the zoning run (pumping stations, then manholes deeper than the CPHEEO 6 m, then pipe "
                "cost); 'Cost order' = order by the priced total - the two can differ.",
                f"No lift stations (project decision): sewers go down to max_depth_project_m {R.max_depth_project:g} m "
                f"at most; deeper -> a new zone with its own pumping station. Depths between {R.max_depth:g} m (CPHEEO "
                "p205) and the project limit are counted - to be justified in the DPR.",
                "Amounts = Excel formulas over sheet 'Items' (quantity x rate). Pumping stations (groups 5 and 6) are an "
                "APPROXIMATE cost scaled from the Riverside SPS (sheets 'Pumping stations', 'SPS components', "
                "data/pumping_station_cost.json) - for comparing options only, to be worked out in the DPR. Rising "
                "mains (group 7) only when the STP is given: DI to the STP, length = straight distance x route factor. "
                "NOT included: the STP (same for every option, see Notes); manholes; road "
                "reinstatement; bedding; dewatering; house connections; GST / cess / contingency. Their quantities: sheet "
                "'Quantities'.",
                "Without a given STP the zone with the largest outlet flow is taken as reaching the STP by gravity (no "
                "pumping station priced there)."):
        wc.append(["", txt])

    q_avg = sum(pop_node.values()) * lpcd / 86400.0
    stp_note = ("user: Rs 1.5 crore per MLD - the same for every option (same total flow): "
                + (f"{q_avg:.1f} L/s average = {q_avg * 86400 / 1e6:.2f} MLD -> Rs {pumping.stp_cost_lakh(q_avg, P):,.0f} lakh"
                   if pop_node else "no population given"))
    notes = [("Source", source), ("Made", time.strftime("%d-%m-%Y %H:%M")),
             ("Design per option", "design_network on the zone trees (no 30 m manhole split, population spread by "
                                   "length, Table 3.2 peak, no infiltration); no lift stations (project decision) - "
                                   "pumping stations at the zone outlets only"),
             ("Pipe rates", f"sewer_catalog.json set {cat_name}: {cat_src}"[:400]),
             ("SOR rates", (sr or {}).get("_source", "sewer_sor_rates.json not found - only pipe supply priced")),
             ("Trench", str(((sr or {}).get("trench_width_m") or {}).get("note", ""))),
             ("Timbering", str(((sr or {}).get("timbering_rule") or {}).get("note", ""))),
             ("Depth basis", str(((sr or {}).get("depth_basis") or {}).get("note", ""))),
             ("Start depth / cover", f"{R.cover + (R.dmin or 0) / 1000:.2f} m / {R.cover:.2f} m"),
             ("Yellow rate cell", "no sourced rate - item not in the total"),
             ("Not solved", "sewers still deeper than the project limit even with a pumping station at their upstream "
                            "manhole: column 'Deep conduits not solved' (usually a wrong GL)"),
             ("Pumping stations", "APPROXIMATE (user decision 12-Oct-2026: no rule per MLD; worked out from civil, "
                                  "mechanical and electrical parts in the DPR): each E&M part and the civil works follow "
                                  "the three stations of the user's DPRs (Riverside SPS-1 55.25 MLD; Lakeside SPS-1 11 MLD "
                                  "and SPS-2 4 MLD), civil also the depth; + power connection charge "
                                  "(data/pumping_station_cost.json, pumping.fit; reproduces the three within 3.3 %). The "
                                  "assumed values there (tariff, efficiency, O&M %, Lakeside capacities = peak flows) "
                                  "are to be verified"),
             ("Rising mains", "DI K-7 supply (Rate_2025-26 M.193) + laying 2197-2210 and excavation 2001 of the Springfield "
                              "SOR 2025-26 + specials 10 % + thrust blocks (data/rising_main_rates.json); smallest size "
                              "with velocity <= 1.8 m/s; friction by Hazen-Williams added to the pump head. For "
                              "comparison: Lakeside DPR rising main (450 & 300 mm) Rs 12,427 per m all-in"),
             ("Pumps", "sized on the +15 years peak flow at the zone outlet (CPHEEO Table 2.1 p2-9: pumping "
                       "machinery 15 years, civil works 30 years); energy at the +15 years average flow; the civil "
                       "works, wet well and rising main on the +30 years (design) flow - user decision 21-Oct-2026"
              if ms else "sized on the +30 years (design) flow - give the +15 years population to size them on "
                         "+15 years (CPHEEO Table 2.1 p2-9: pumping machinery 15 years)"),
             ("O&M", f"energy at the average flow x tariff + {P['om_em_fraction']['value']:g} x E&M + "
                     f"{P['om_civil_fraction']['value']:g} x civil per year; present value over {yrs} years at "
                     f"{P['discount_rate']['value']:.0%}"),
             ("STP", stp_note)]
    for k_, v_ in notes:
        wn.append([k_, v_])
        wn.cell(row=wn.max_row, column=1).font = bold
    wn.column_dimensions["A"].width = 22
    wn.column_dimensions["B"].width = 140
    for title_, rows_ in (("Pumping stations", sps_rows), ("SPS components", comp_rows)):
        ws_ = wb.create_sheet(title_)
        cols_ = list(rows_[0].keys()) if rows_ else ["(none)"]
        ws_.append(cols_)
        for c in ws_[1]:
            c.font, c.fill = bold, head
            c.alignment = Alignment(wrap_text=True, vertical="top")
        for r_ in rows_:
            ws_.append([r_.get(c) for c in cols_])
        for i in range(1, len(cols_) + 1):
            ws_.column_dimensions[get_column_letter(i)].width = 14
        ws_.freeze_panes = "C2"
    wb.save(path)
    z["option_costs"] = {o: {"groups_lakh": {g: round(v / 1e5, 2) for g, v in t.items()},
                             "total_lakh": round(sum(t.values()) / 1e5, 2)} for o, t in totals.items()}
    return path


# ---------------------------------------------------------------- maps (PNG) - from the original scripts zoning.py
PAL = ["#2563eb", "#16a34a", "#9333ea", "#ea580c", "#0891b2", "#ca8a04", "#db2777", "#4b5563",
       "#65a30d", "#7c3aed", "#0d9488", "#b91c1c"]


def _plt():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.collections import LineCollection
        return plt, LineCollection
    except ImportError:
        return None, None


def draw_gl_map(out_png, E, gl, xy, basin_lows, title):
    plt, LC = _plt()
    if plt is None or not xy:
        return None
    fig, ax = plt.subplots(figsize=(13, 14), dpi=130)
    ax.add_collection(LC([e["pts"] for e in E.values() if len(e["pts"]) > 1], colors="#9ca3af", linewidths=0.3))
    ns = [n for n in gl if n in xy]
    sc = ax.scatter([xy[n][0] for n in ns], [xy[n][1] for n in ns], c=[gl[n] for n in ns], s=3, cmap="terrain")
    fig.colorbar(sc, ax=ax, shrink=0.6, label="GL used for zoning (m)")
    bl = [n for n in basin_lows if n in xy]
    ax.plot([xy[n][0] for n in bl], [xy[n][1] for n in bl], "v", ms=5, color="black",
            label=f"terrain low points (basin sinks): {len(basin_lows)}")
    ax.set_aspect("equal")
    ax.autoscale()
    ax.ticklabel_format(useOffset=False, style="plain")
    ax.legend(loc="best", fontsize=9)
    ax.set_title(title, fontsize=11)
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)
    return out_png


def draw_option_map(out_png, ev, E, xy, title):
    plt, LC = _plt()
    if plt is None or not xy:
        return None
    zones = sorted(set(ev["zone"].values()))
    col = {z: PAL[i % len(PAL)] for i, z in enumerate(zones)}
    cutset = {c["conduit"] for c in ev["cuts"]}
    segs, cols = [], []
    for lab, e in E.items():
        if len(e["pts"]) < 2 or lab in cutset:
            continue
        segs.append(e["pts"])
        cols.append(col.get(ev["zone"].get(e["a"]), "#9ca3af"))
    fig, ax = plt.subplots(figsize=(13, 14), dpi=130)
    ax.add_collection(LC(segs, colors=cols, linewidths=0.6))
    cs = [E[c]["pts"] for c in cutset if len(E[c]["pts"]) > 1]
    if cs:
        ax.add_collection(LC(cs, colors="black", linewidths=1.2, linestyles="dashed"))
    d6 = [n for n in ev["deep6"] if n in xy and n not in ev["deep"]]
    ax.plot([xy[n][0] for n in d6], [xy[n][1] for n in d6], "o", ms=2.0, color="#f97316",
            label=f"manhole deeper than the CPHEEO 6 m - accepted, justify in DPR ({len(d6)})")
    dp = [n for n in ev["deep"] if n in xy]
    if dp:
        ax.plot([xy[n][0] for n in dp], [xy[n][1] for n in dp], "o", ms=3, color="#dc2626",
                label=f"manhole deeper than the project limit - not solved ({len(dp)})")
    added = set(ev["pumps_added"])
    for z in zones:
        if z in xy:
            zr = next(r for r in ev["zones"] if r["zone outlet"] == z)
            if z in added:                                    # pumping station added for depth: smaller mark
                ax.plot(*xy[z], marker="^", ms=9, color=col[z], mec="black", mew=0.8, zorder=6)
                ax.annotate(f"{z} ({zr['design flow at outlet (L/s)']} L/s)", xy[z], xytext=(6, 4),
                            textcoords="offset points", fontsize=6.5, color="black")
                continue
            ax.plot(*xy[z], marker="*", ms=18, color=col[z], mec="black", mew=0.8, zorder=6)
            ax.annotate(f"{z}\nGL {zr['outlet GL (m)']}, wet well {zr['outlet depth = wet well (m)']} m\n"
                        f"{zr['manholes']} MH, {zr['design flow at outlet (L/s)']} L/s", xy[z], xytext=(10, 6),
                        textcoords="offset points", fontsize=8, weight="bold", color=col[z],
                        bbox=dict(facecolor="white", alpha=.8, edgecolor=col[z]))
    ax.plot([], [], "*", ms=12, color="#9ca3af", mec="black", label="zone outlet = pumping station / STP")
    if added:
        ax.plot([], [], "^", ms=8, color="#9ca3af", mec="black",
                label=f"pumping station added - sewer would go deeper than the project limit ({len(added)})")
    ax.plot([], [], "--", color="black", label=f"cut conduit - disconnected at one end ({len(cutset)})")
    ax.set_aspect("equal")
    ax.autoscale()
    ax.ticklabel_format(useOffset=False, style="plain")
    ax.legend(loc="best", fontsize=9)
    ax.set_title(title, fontsize=11)
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)
    return out_png


# ---------------------------------------------------------------- zone boundaries and network drawing (DXF)
def draw_boundary_map(out_png, ev, regs, E, xy, gl, title):
    plt, LC = _plt()
    if plt is None or not regs:
        return None
    from matplotlib.collections import PolyCollection
    zones = sorted(set(ev["zone"].values()))
    col = {z: PAL[i % len(PAL)] for i, z in enumerate(zones)}
    fig, ax = plt.subplots(figsize=(13, 14), dpi=130)
    ax.add_collection(LC([e["pts"] for e in E.values() if len(e["pts"]) > 1], colors="#9ca3af",
                         linewidths=0.2, alpha=0.5))
    for z in zones:
        r = regs.get(z)
        if not r:
            continue
        ax.add_collection(PolyCollection(r["pieces"], facecolors=col[z], edgecolors="none", alpha=0.22))
        ax.add_collection(LC(r["rings"], colors="black", linewidths=1.4))
    zr = {x["zone outlet"]: x for x in ev["zones"]}
    for z in zones:
        r = regs.get(z)
        if r and r["label"]:
            ax.annotate(f"zone {z}\n{r['area'] / 1e4:,.1f} ha, {zr[z]['manholes']} MH", r["label"], ha="center",
                        va="center", fontsize=9, weight="bold", color="black",
                        bbox=dict(facecolor="white", alpha=.85, edgecolor=col[z], linewidth=1.5))
        if z in xy:
            ax.plot(*xy[z], marker="*", ms=17, color=col[z], mec="black", mew=0.9, zorder=6)
            ax.annotate(f"outlet {z}\nGL {gl[z]:.2f}", xy[z], xytext=(9, -14), textcoords="offset points",
                        fontsize=8, color="black", zorder=7)
    ax.set_aspect("equal")
    ax.autoscale()
    ax.ticklabel_format(useOffset=False, style="plain")
    ax.set_title(title, fontsize=11)
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)
    return out_png


def write_boundary_dxf(path, per_option, xy, gl, text_h):
    """One DXF, every option on its own layers: ZONE_<opt> (closed boundary polylines), ZONE_<opt>_TEXT (zone
    name, area, manholes), ZONE_<opt>_OUTLET (outlet circle + level). Drawing coordinates = the network's, so it
    can be XREF'd / INSERTed on the original drawing. per_option = [(option, ev, regs)]."""
    try:
        import ezdxf
        from ezdxf import colors as ezc
        from ezdxf import zoom
    except ImportError:
        return None
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$TILEMODE"] = 1
    msp = doc.modelspace()
    for k, (opt, ev, regs) in enumerate(per_option):
        zones = sorted(set(ev["zone"].values()))
        for suffix, aci in (("", 7), ("_TEXT", 7), ("_OUTLET", 1)):
            name = f"ZONE_{opt}{suffix}"
            if name not in doc.layers:
                doc.layers.add(name, color=aci)
            if k > 0:
                doc.layers.get(name).off()                                # only the first (best) option shown
        zr = {x["zone outlet"]: x for x in ev["zones"]}
        for i, z in enumerate(zones):
            rgb = tuple(int(PAL[i % len(PAL)][j:j + 2], 16) for j in (1, 3, 5))
            r = regs.get(z) or {}
            for ring in r.get("rings", []):
                pl = msp.add_lwpolyline(ring[:-1] if ring[0] == ring[-1] else ring, close=True,
                                        dxfattribs={"layer": f"ZONE_{opt}", "lineweight": 50})
                pl.rgb = rgb
            if r.get("label"):
                t = msp.add_mtext(f"ZONE {z}\\P{r['area'] / 1e4:,.1f} ha, {zr[z]['manholes']} MH\\P"
                                  f"outlet GL {gl[z]:.2f}", dxfattribs={"layer": f"ZONE_{opt}_TEXT",
                                                                       "char_height": text_h})
                t.set_location(r["label"], attachment_point=5)
                t.rgb = rgb
            if z in xy:
                msp.add_circle(xy[z], radius=text_h * 0.8, dxfattribs={"layer": f"ZONE_{opt}_OUTLET"})
                msp.add_text(f"OUTLET {z} GL {gl[z]:.2f}", height=text_h * 0.7,
                             dxfattribs={"layer": f"ZONE_{opt}_OUTLET"}).set_placement(
                    (xy[z][0] + text_h, xy[z][1] - text_h))
    try:
        zoom.extents(msp)
    except Exception:
        pass
    doc.saveas(path)
    return path


def write_network_dxf(path, ev, regs, E, xy, gl, R, h, zone_h, stp=None):
    """Full drawing of ONE option (no lift stations - project decision): pipes with flow arrow, label,
    diameter, slope 1:N, length; manholes with label, GL, IL, depth (D) - deeper than the CPHEEO 6 m on the red
    layer SEW_MH_DEEP (accepted up to the project limit, to be justified in the DPR) - all by
    cad.write_dxf (same layers and look as the design drawing) - plus:
      ZONE_BOUNDARY        thick closed boundary of every zone (zone colour, width in drawing units, drawn
                           underneath the pipes)
      ZONE_TEXT            zone name, area, manholes, outlet GL
      SEW_PUMPING_STATION  every zone outlet that is not the STP: double square + 'PUMPING STATION', wet-well
                           depth, design flow; '(added for depth)' where the sewer would go deeper than the limit
      SEW_STP              the STP (stp)
      ZONE_CUT             conduits to disconnect at one end (zone boundary / loop): cross + 'DISCONNECT'
    Coordinates = the network's (XREF / INSERT on the original drawing)."""
    from . import cad as dd
    from ezdxf.enums import TextEntityAlignment
    res, info, vn = ev["res"], ev["info"], ev["vnodes"]
    outlets = set(ev["zone"].values())
    nodes = {n: {"xy": xy[n], "gl": gl[n], "il": i.get("invert"), "outfall": n in outlets}
             for n, i in info.items() if n not in vn and n in xy}
    conds, cuts = [], []
    for lab, d in res.items():
        e = E.get(lab)
        if e is None:
            continue
        fr = d["from"].split(VSEP)[0]
        pts = e["pts"] if len(e["pts"]) > 1 else ([xy[e["a"]], xy[e["b"]]] if e["a"] in xy and e["b"] in xy else None)
        conds.append({"label": lab, "pts": pts, "D": d["D"], "slope": d["slope"], "length": d["length"],
                      "start": e["a"], "stop": e["b"], "dir": 1 if fr == e["a"] else -1})
        if d["from"] in vn and fr in xy:
            cuts.append((lab, fr))
    dd.snap_ends(nodes, conds)
    zones = sorted(outlets)
    stp_zone = ev["zone"].get(stp) if stp else None
    added = set(ev["pumps_added"])
    zr = {x["zone outlet"]: x for x in ev["zones"]}
    n_ps = 0

    def extra(doc, msp):
        nonlocal n_ps
        for name, aci in (("ZONE_BOUNDARY", 1), ("ZONE_TEXT", 7), ("SEW_PUMPING_STATION", 30), ("SEW_STP", 6),
                          ("ZONE_CUT", 6)):
            if name not in doc.layers:
                doc.layers.add(name, color=aci)
        # thick (width in drawing units, so it scales with the zoom) and drawn underneath: on the outer edge the
        # boundary runs through the outermost manholes and along their pipes, which stay visible on top of it
        w = max(1.2 * h, 0.4)
        under = {}
        for i, z in enumerate(zones):
            rgb = tuple(int(PAL[i % len(PAL)][j:j + 2], 16) for j in (1, 3, 5))
            r = regs.get(z) or {}
            for ring in r.get("rings", []):
                pl = msp.add_lwpolyline(ring[:-1] if ring[0] == ring[-1] else ring, close=True,
                                        dxfattribs={"layer": "ZONE_BOUNDARY", "const_width": w})
                pl.rgb = rgb
                under[pl.dxf.handle] = "1"
            if r.get("label"):
                t = msp.add_mtext(f"ZONE {z}\\P{r['area'] / 1e4:,.1f} ha, {zr[z]['manholes']} MH\\P"
                                  f"outlet GL {gl[z]:.2f}", dxfattribs={"layer": "ZONE_TEXT", "char_height": zone_h})
                t.set_location(r["label"], attachment_point=5)
                t.rgb = rgb
        try:
            msp.set_redraw_order(under)                                # boundaries drawn first = underneath
        except Exception:
            pass
        for z in zones:
            if z not in xy:
                continue
            x, y = xy[z]
            rz = zr.get(z, {})
            is_stp = stp is not None and (z == stp or z == stp_zone)
            lay = "SEW_STP" if is_stp else "SEW_PUMPING_STATION"
            n_ps += 0 if is_stp else 1
            for s_ in (2.6 * h, 1.9 * h):
                msp.add_lwpolyline([(x - s_, y - s_), (x + s_, y - s_), (x + s_, y + s_), (x - s_, y + s_)], close=True,
                                   dxfattribs={"layer": lay})
            txt = ("STP" if is_stp else "PUMPING STATION" + (" (added for depth)" if z in added else ""))
            txt += (f"  wet well {rz.get('outlet depth = wet well (m)')} m, Q {rz.get('design flow at outlet (L/s)')} L/s"
                    if rz else "")
            # down-left of the symbol: the MH texts are up-right (design_to_dxf)
            msp.add_text(txt, height=1.1 * h, dxfattribs={"layer": lay}).set_placement(
                (x - 2.9 * h, y - 2.9 * h), align=TextEntityAlignment.TOP_RIGHT)
        for lab, n in cuts:
            x, y = xy[n]
            s = 1.2 * h
            msp.add_line((x - s, y - s), (x + s, y + s), dxfattribs={"layer": "ZONE_CUT"})
            msp.add_line((x - s, y + s), (x + s, y - s), dxfattribs={"layer": "ZONE_CUT"})
            msp.add_text(f"DISCONNECT {lab} here", height=h, dxfattribs={"layer": "ZONE_CUT"}).set_placement(
                (x + 1.5 * s, y - 1.5 * s), align=TextEntityAlignment.TOP_LEFT)

    cnt = dd.write_dxf(path, nodes, conds, h, R.max_depth, extra=extra)
    cnt.update({"pumping": n_ps, "cuts": len(cuts)})
    return cnt


# ---------------------------------------------------------------- all outputs of one zoning run
def write_outputs(z, base, source="", network_dxf="all", mh_text_height=None, source_dxf=None, dxf_text_height=None,
                  band_map_on=True, gl_ref=None, gl_bands=None):
    """Everything the original scripts zoning.py main() writes, with file names <base>.xlsx, <base>_costs.xlsx, <base>_GL.png,
    <base>_NN_<option>.png, ..._boundary.png, <base>_zone_boundaries.dxf and <base>_NN_<option>_network.dxf
    (network_dxf 'all' | 'best' | 'none'). Text height of the network DXFs: mh_text_height, else 0.67 x the MH
    labels of source_dxf, else median conduit length / 25. Returns {kind: path or [paths]}."""
    from . import cad
    rank, E, xy, gl, R = z["rank"], z["E"], z["xy"], z["gl"], z["R"]
    stem = os.path.splitext(os.path.basename(str(source or "network").split(" + ")[0]))[0].replace("_manholes", "")
    files = {}
    if band_map_on:
        files["band_png"], _, files["band_text"] = band_outputs(
            z, base + "_GL_bands.png", gl_ref, gl_bands,
            f"{stem} - ground level in ranges above the reference GL (GL used for zoning: spikes {z['spike_gl']})")
    files.update({"xlsx": write_workbook(z, base + ".xlsx", source),
             "costs": cost_workbook(z, base + "_costs.xlsx", source)})
    files["gl_png"] = draw_gl_map(base + "_GL.png", E, gl, xy, [r["basin low point"] for r in z["basins"]],
                                  f"{stem} - ground level (GL) used for zoning and terrain low points")
    files["option_png"], files["boundary_png"] = [], []
    for ev in rank:
        m = ev["m"]
        p = draw_option_map(f"{base}_{m['rank']:02d}_{m['option']}.png", ev, E, xy,
                            f"{stem} - option {m['option']} (rank {m['rank']}): {m['zones']} zone(s), "
                            f"pumping stations {m['pumping stations']}, max depth {m['max depth (m)']} m, "
                            f"pipe Rs {m['pipe cost (Rs lakh)']} lakh")
        if p:
            files["option_png"].append(p)
        p = draw_boundary_map(f"{base}_{m['rank']:02d}_{m['option']}_boundary.png", ev, ev["regs"], E, xy, gl,
                              f"{stem} - zone boundaries, option {m['option']} (rank {m['rank']}): {m['zones']} "
                              f"zone(s); boundary halfway between manholes of different zones, no line where "
                              f"manholes are > {z['max_edge']:g} m apart")
        if p:
            files["boundary_png"].append(p)
    xs_, ys_ = [p[0] for p in xy.values()], [p[1] for p in xy.values()]
    text_h = dxf_text_height or (round(max(max(xs_) - min(xs_), max(ys_) - min(ys_)) / 300, 1) if xs_ else 2.5)
    files["boundary_dxf"] = write_boundary_dxf(base + "_zone_boundaries.dxf",
                                               [(ev["m"]["option"], ev, ev["regs"]) for ev in rank], xy, gl, text_h)
    files["network_dxf"] = []
    if network_dxf != "none":
        Ls = sorted(e["L"] for e in E.values() if e["L"])
        if mh_text_height:
            h_mh = mh_text_height
        elif source_dxf:
            h_mh = cad.source_text_height(source_dxf)[0] * 0.67
        else:
            h_mh = min(3.0, max(0.5, round(Ls[len(Ls) // 2] / 25, 2))) if Ls else 1.0
        for ev in (rank if network_dxf == "all" else rank[:1]):
            m = ev["m"]
            p = f"{base}_{m['rank']:02d}_{m['option']}_network.dxf"
            cnt = write_network_dxf(p, ev, ev["regs"], E, xy, gl, R, h_mh, text_h, z["stp"])
            files["network_dxf"].append((p, cnt))
    return files


# ---------------------------------------------------------------- GL band map (height ranges above a reference GL)
# each range its own CONTRASTING colour, in this fixed order (never cycled). Checked with the dataviz
# palette validator for a map (all pairs): the first 4 pass every check (worst colour-blind dE 13.0);
# 5-6 pass with a colour-blind warning (red / aqua), so the legend and sheet 'GL bands' name every range;
# 7-8 (magenta, orange) are close to red / yellow - a warning is printed. Below the reference = dark grey
# with diagonal hatching, gap / above every range = light grey with dots (texture, not colour alone).
RANGE_COLS = ["#2a78d6", "#eda100", "#4a3aa7", "#e34948", "#1baf7a", "#008300", "#e87ba4", "#eb6834"]
RANGE_NAMES = ["blue", "yellow", "violet", "red", "aqua", "green", "pink", "orange"]
BELOW_COL, GAP_COL = "#5f5e5a", "#bdbbb5"
BELOW_HATCH, GAP_HATCH = "//", ".."
BANDS_DEFAULT = "0-1.5, 1.5-3, 3-4.5, 4.5+"


def parse_range(tok, prev_hi):
    """One range in metres above the reference GL: '1.5-3'; only the upper value '3' (the lower value is then
    the upper value of the range before it, 0 for the first range); open last range '4.5+', '>4.5' or
    'above 4.5'. prev_hi = upper value of the range before (None for the first). Returns (lo, hi or None);
    raises ValueError with the reason."""
    t = tok.strip().lower().replace(" ", "").replace("m", "")
    m = re.fullmatch(r"(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)", t)
    if m:
        lo, hi = float(m.group(1)), float(m.group(2))
    else:
        m = re.fullmatch(r"(?:>|above|ऊपर)?(\d+(?:\.\d+)?)(\+)?", t)
        if not m:
            raise ValueError(f"'{tok.strip()}' not understood - write like 1.5-3, or 3, or 4.5+")
        if m.group(2) or t[0] in ">a":
            lo, hi = float(m.group(1)), None
        else:
            lo, hi = (prev_hi if prev_hi is not None else 0.0), float(m.group(1))
    if hi is not None and hi <= lo:
        raise ValueError(f"'{tok.strip()}': the upper value must be more than the lower ({lo:g})")
    if prev_hi is not None and lo < prev_hi - 1e-9:
        raise ValueError(f"'{tok.strip()}' overlaps the range before it (which ends at {prev_hi:g} m)")
    return lo, hi


def parse_bands(text):
    """'0-1.5, 1.5-3, 3.1-4.5, 4.5+' (metres above the reference GL, in order) -> [(lo, hi or None), ...].
    Raises ValueError with the reason."""
    out = []
    for tok in re.split(r"[,;]", text):
        if not tok.strip():
            continue
        if out and out[-1][1] is None:
            raise ValueError("only the LAST range may be open ('4.5+')")
        out.append(parse_range(tok, out[-1][1] if out else None))
    if not out:
        raise ValueError("no range given")
    if len(out) > len(RANGE_COLS):
        raise ValueError(f"at most {len(RANGE_COLS)} ranges (one clearly different colour each)")
    return out


def band_text(bands):
    return ", ".join(f"{lo:g}-{hi:g}" if hi is not None else f"{lo:g}+" for lo, hi in bands)


def band_intervals(bands):
    """Contiguous intervals (lo, hi, colour, label, kind, hatch) from -inf to +inf: the user's ranges each in
    its own contrasting colour, gaps between them and the parts below / above them in hatched grey."""
    f = lambda v: format(v, "g")                                           # noqa: E731
    iv = [(-math.inf, bands[0][0], BELOW_COL,
           "below the reference GL" if bands[0][0] == 0 else f"below {f(bands[0][0])} m (no range)", "below",
           BELOW_HATCH)]
    for i, (lo, hi) in enumerate(bands):
        if i and lo > bands[i - 1][1] + 1e-9:
            iv.append((bands[i - 1][1], lo, GAP_COL, f"{f(bands[i - 1][1])}-{f(lo)} m (gap - no range)", "gap",
                       GAP_HATCH))
        lab = f"range {i + 1}: {f(lo)}-{f(hi)} m" if hi is not None else f"range {i + 1}: above {f(lo)} m"
        iv.append((lo, math.inf if hi is None else hi, RANGE_COLS[i], f"{lab} [{RANGE_NAMES[i]}]", "range", None))
    if bands[-1][1] is not None:
        iv.append((bands[-1][1], math.inf, GAP_COL, f"above {f(bands[-1][1])} m (no range)", "above", GAP_HATCH))
    return iv


def ref_point(gl, xy, ref, ref_mh=None):
    """Where the reference GL is marked on the map: the given manhole, else among the manholes whose GL is
    closest to the reference (within 5 cm of the closest) the one nearest the middle of the area."""
    if ref_mh and ref_mh in xy:
        return ref_mh
    ns = [n for n in gl if n in xy]
    if not ns:
        return None
    xs, ys = sorted(xy[n][0] for n in ns), sorted(xy[n][1] for n in ns)
    cx, cy = xs[len(xs) // 2], ys[len(ys) // 2]
    dmin = min(abs(gl[n] - ref) for n in ns)
    cand = [n for n in ns if abs(gl[n] - ref) <= dmin + 0.05]
    return min(cand, key=lambda n: math.hypot(xy[n][0] - cx, xy[n][1] - cy))



def gl_span(ref, b):
    """Absolute GL span of an interval as text: '< 78.24', '78.24-79.74', '82.74 +'."""
    lo, hi = b[0], b[1]
    if lo == -math.inf:
        return f"< {ref + hi:.2f}"
    if hi == math.inf:
        return f"{ref + lo:.2f} +"
    return f"{ref + lo:.2f}-{ref + hi:.2f}"


def band_map(out_png, E, gl, xy, ref, bands, outs, max_edge, title, ref_mh=None):
    """Areas coloured by GL range above ref: the manholes are triangulated (Delaunay), triangles with an edge
    longer than max_edge are left blank (no data between far-apart streets), GL is interpolated linearly
    inside each triangle. Returns (png or None, rows for sheet 'GL bands')."""
    iv = band_intervals(bands)
    cls = lambda h: next(i for i, (lo, hi, *_) in enumerate(iv) if lo <= h < hi)   # noqa: E731
    n_mh, len_b, area = collections.Counter(), collections.defaultdict(float), collections.defaultdict(float)
    for n, g in gl.items():
        n_mh[cls(g - ref)] += 1
    for e in E.values():
        len_b[cls((gl[e["a"]] + gl[e["b"]]) / 2 - ref)] += e["L"]
    png, tri_ok = None, False
    try:
        import numpy as np
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.tri as mtri
        from matplotlib.patches import Patch
        from matplotlib.collections import LineCollection
        ns = [n for n in gl if n in xy]
        X = np.array([xy[n][0] for n in ns])
        Y = np.array([xy[n][1] for n in ns])
        Z = np.array([gl[n] - ref for n in ns])
        tri = mtri.Triangulation(X, Y)
        t = tri.triangles
        el = np.max(np.stack([np.hypot(X[t[:, i]] - X[t[:, j]], Y[t[:, i]] - Y[t[:, j]])
                              for i, j in ((0, 1), (1, 2), (2, 0))]), axis=0)
        tri.set_mask(el > max_edge)
        keep = ~tri.mask
        ar = 0.5 * np.abs((X[t[:, 1]] - X[t[:, 0]]) * (Y[t[:, 2]] - Y[t[:, 0]])
                          - (X[t[:, 2]] - X[t[:, 0]]) * (Y[t[:, 1]] - Y[t[:, 0]]))
        for k in np.nonzero(keep)[0]:
            area[cls(float(Z[t[k]].mean()))] += float(ar[k])
        tri_ok = True
        lo_z, hi_z = float(Z.min()) - 1.0, float(Z.max()) + 1.0
        levels = [max(iv[0][1] - 1e3, min(lo_z, iv[0][1] - 0.01))] + [b[1] for b in iv[:-1]] + [max(hi_z, iv[-1][0] + 0.01)]
        matplotlib.rcParams["hatch.color"] = "#ffffff"
        matplotlib.rcParams["hatch.linewidth"] = 0.6
        fig, ax = plt.subplots(figsize=(13, 14), dpi=130)
        ax.tricontourf(tri, Z, levels=levels, colors=[b[2] for b in iv], hatches=[b[5] for b in iv])
        ax.add_collection(LineCollection([e["pts"] for e in E.values() if len(e["pts"]) > 1],
                                         colors="#3d3d3a", linewidths=0.25, alpha=0.7))
        for lab in outs:
            if lab in xy:
                ax.plot(*xy[lab], marker="*", ms=16, color="white", mec="black", mew=1.0)
                ax.annotate(f"{lab} (GL {gl[lab]:.2f})", xy[lab], xytext=(8, 6), textcoords="offset points",
                            fontsize=9, weight="bold", bbox=dict(facecolor="white", alpha=.85, edgecolor="#3d3d3a"))
        # the reference level itself: the line where GL = reference (black dashed, white halo) and one marked
        # point with its level written on it
        from matplotlib.lines import Line2D
        import matplotlib.patheffects as pe
        ref_line = float(Z.min()) < 0 < float(Z.max())
        if ref_line:
            cs = ax.tricontour(tri, Z, levels=[0.0], colors="black", linewidths=1.6, linestyles="--")
            cs.set_path_effects([pe.Stroke(linewidth=3.6, foreground="white"), pe.Normal()])
        rp = ref_point(gl, xy, ref, ref_mh)
        if rp is not None:
            ax.plot(*xy[rp], marker="o", ms=15, color="black", mec="white", mew=3, zorder=7)
            ax.plot(*xy[rp], marker="o", ms=5, color="white", zorder=8)
            ax.annotate(f"REFERENCE GL {ref:.2f} m\n{rp} (GL {gl[rp]:.2f})", xy[rp], xytext=(16, -30),
                        textcoords="offset points", fontsize=11, weight="bold", color="black", zorder=9,
                        bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor="black", linewidth=2),
                        arrowprops=dict(arrowstyle="-", color="black", linewidth=1.5))
        tot_a = sum(area.values()) or 1.0
        handles = []
        if rp is not None:
            handles.append(Line2D([], [], marker="o", ms=11, color="black", mec="white", mew=2, linestyle="none",
                                  label=f"reference GL {ref:.2f} m - point {rp}"))
        if ref_line:
            handles.append(Line2D([], [], color="black", linewidth=1.6, linestyle="--",
                                  label=f"line where GL = {ref:.2f} m (reference level)"))
        handles += [Patch(facecolor=b[2], edgecolor="#3d3d3a", linewidth=0.5, hatch=b[5],
                          label=f"{b[3]}  (GL {gl_span(ref, b)})  - {100 * area[i] / tot_a:.0f} % of area, {n_mh[i]} MH")
                    for i, b in enumerate(iv) if n_mh[i] or area[i]]
        handles.append(Patch(facecolor="white", edgecolor="#3d3d3a", linewidth=0.5,
                             label=f"white = no data: manholes there more than {max_edge:g} m apart (open land, "
                                   f"large blocks) - GL not guessed"))
        ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.01, 1.0), fontsize=9,
                  title=f"reference GL {ref:.2f} m", title_fontsize=10, framealpha=0.95)
        ax.set_aspect("equal")
        ax.autoscale()
        ax.ticklabel_format(useOffset=False, style="plain")
        ax.set_title(title, fontsize=11)
        fig.savefig(out_png, bbox_inches="tight")
        plt.close(fig)
        png = out_png
    except ImportError:
        pass
    except Exception as e:                                                # e.g. too few / collinear points
        print(f"(note) GL band map not drawn: {type(e).__name__}: {str(e)[:120]}")
    tot_n, tot_l, tot_a = sum(n_mh.values()) or 1, sum(len_b.values()) or 1.0, sum(area.values()) or 1.0
    rows = [{"range": b[3], "kind": b[4],
             "height above reference from (m)": None if b[0] == -math.inf else b[0],
             "to (m)": None if b[1] == math.inf else b[1],
             "GL from (m)": None if b[0] == -math.inf else round(ref + b[0], 3),
             "GL to (m)": None if b[1] == math.inf else round(ref + b[1], 3), "colour": b[2],
             "manholes": n_mh[i], "manholes %": round(100 * n_mh[i] / tot_n, 1),
             "sewer length (m)": round(len_b[i], 1), "sewer length %": round(100 * len_b[i] / tot_l, 1),
             "area (ha, interpolated)": round(area[i] / 1e4, 2) if tri_ok else None,
             "area %": round(100 * area[i] / tot_a, 1) if tri_ok else None}
            for i, b in enumerate(iv)]
    return png, rows


def band_outputs(z, png_path, ref=None, bands_text=None, title=""):
    """GL band map of a zoning run (from the original scripts zoning.py; the terminal questions there are replaced by the
    arguments): ref = reference GL in m or a manhole label whose GL is the reference (default: the lowest GL);
    bands_text = ranges in m above it (default BANDS_DEFAULT). Returns (png or None, rows for sheet 'GL bands',
    settings text) - also kept in z["gl_bands"] for write_workbook."""
    gl, xy, E = z["gl"], z["xy"], z["E"]
    ref_mh = ref if isinstance(ref, str) and ref in gl else None
    if ref_mh:
        ref_v = gl[ref_mh]
    elif ref is None:
        ref_v = round(min(gl.values()), 2)
    else:
        ref_v = float(ref)
    bands = parse_bands(bands_text or BANDS_DEFAULT)
    outs = sorted(set(z["model_outs"]) | set(z["fixed"]))
    png, rows = band_map(png_path, E, gl, xy, ref_v, bands, outs, z["max_edge"],
                         title or f"ground level in ranges above the reference GL {ref_v:.2f} m", ref_mh)
    rp = ref_point(gl, xy, ref_v, ref_mh)
    text = (f"reference GL {ref_v:.2f} m" + (f" (GL of {ref_mh})" if ref_mh else "") + f", marked at {rp}; ranges "
            f"above it: {band_text(bands)}; areas interpolated linearly between manholes, white where the manholes "
            f"are more than {z['max_edge']:g} m apart (no data) - sheet 'GL bands'")
    z["gl_bands"] = (rows, text)
    return png, rows, text


# ---------------------------------------------------------------- the chosen option -> a network to design
def apply_option(net, ev):
    """The network with a zoning option applied, ready for pipeline.run: every zone outlet (STP / pumping station,
    incl. those added for depth) becomes an outfall, and every cut conduit (zone boundary or loop) is disconnected
    at its higher end - that end gets a NEW head manhole at the same place, labelled <manhole>-C<n> (the sewer of
    the other zone does not enter it). Returns (network, rows {"conduit", "disconnected from", "new head manhole",
    "zone", "why"})."""
    nodes = {n: dict(v) for n, v in net["nodes"].items()}
    conds = [dict(k) for k in net["conduits"]]
    by_label = {k["label"]: k for k in conds}
    used, rows = set(nodes), []
    for c in ev["cuts"]:
        k, up = by_label.get(c["conduit"]), c["disconnect at"]
        if k is None:
            continue
        i = 1
        while f"{up}-C{i}" in used:
            i += 1
        new = f"{up}-C{i}"
        used.add(new)
        nodes[new] = dict(nodes[up], gl_source=(str(nodes[up].get("gl_source") or "") + " (cut end of " + up + ")").strip(),
                          cut_of=up)
        if k["start_node"] == up:
            k["start_node"] = new
        elif k["stop_node"] == up:
            k["stop_node"] = new
        rows.append({"conduit": c["conduit"], "disconnected from": up, "new head manhole": new,
                     "zone": c.get("zone"), "why": c.get("why")})
    outlets = sorted(set(ev["zone"].values()))
    return {"nodes": nodes, "conduits": conds, "outfalls": outlets}, rows
