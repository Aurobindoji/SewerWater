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
import heapq
import math
import time

from .criteria import Rules, load_catalog, load_criteria, slope_row, val
from .design import design_network, priced_cost
from .flows import design_flows

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
