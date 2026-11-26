"""dxf_inspect: lines joined into a network, its parts and its checks (gaps, T-joints, loops)."""
import collections
from .reading import seg_len
from .spatial import Grid, point_seg_dist, seg_cross


def build_network(lines, tol):
    """Join line ends within tol -> nodes; each polyline = one edge between its end nodes; interior
    vertices kept for T-joint / crossing checks."""
    grid, nodes = Grid(max(tol, 0.01) * 2), []

    def node_at(x, y, z):
        hit = grid.near(x, y, tol)
        if hit:
            return hit[0][3]
        nid = len(nodes)
        nodes.append({"id": nid, "x": x, "y": y, "z": [z], "deg": 0, "edges": []})
        grid.add(x, y, nid)
        return nid

    edges = []
    for ln in lines:
        p = ln["pts"]
        if ln["closed"]:
            continue
        a = node_at(p[0][0], p[0][1], p[0][2])
        b = node_at(p[-1][0], p[-1][1], p[-1][2])
        nodes[b]["z"].append(p[-1][2])
        e = {"id": len(edges), "a": a, "b": b, "len": ln["len"], "pts": p, "layer": ln["layer"],
             "handle": ln["handle"]}
        edges.append(e)
        for n in (a, b):
            nodes[n]["deg"] += 1
            nodes[n]["edges"].append(e["id"])
    return nodes, edges, grid


def components(nodes, edges):
    parent = list(range(len(nodes)))

    def f(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for e in edges:
        ra, rb = f(e["a"]), f(e["b"])
        if ra != rb:
            parent[ra] = rb
    comp = collections.Counter(f(n["id"]) for n in nodes if n["deg"] > 0)
    return comp, f


def network_checks(nodes, edges, tol, gap_factor=10.0, spacing=30.0):
    comp, find = components(nodes, edges)
    used = [n for n in nodes if n["deg"] > 0]
    loops = len([e for e in edges if e["a"] != e["b"]]) - len(used) + len(comp)
    self_loops = sum(1 for e in edges if e["a"] == e["b"])
    dead = [n for n in used if n["deg"] == 1]
    # near-miss gaps: dead ends that almost touch another node (tol < d <= gap_factor*tol) in another part
    g = Grid(tol * gap_factor)
    for n in used:
        g.add(n["x"], n["y"], n["id"])
    gaps, seen_pairs = [], set()
    for n in dead:
        for dd, _, _, other in g.near(n["x"], n["y"], tol * gap_factor):
            if other != n["id"] and dd > tol and find(other) != find(n["id"]):
                pair = frozenset((n["id"], other))
                if pair not in seen_pairs:            # one gap seen from both ends counts once
                    seen_pairs.add(pair)
                    gaps.append((n["id"], other, dd))
                break
    # T-joints: a dead end lying on the interior of another edge (no node there)
    sg = Grid(25.0)
    for e in edges:
        p = e["pts"]
        for i in range(len(p) - 1):
            mx, my = (p[i][0] + p[i + 1][0]) / 2, (p[i][1] + p[i + 1][1]) / 2
            sg.add(mx, my, (e["id"], i))
    tjoints = []
    for n in dead:
        best = None
        for _, _, _, (eid, i) in sg.near(n["x"], n["y"], 25.0 + 1e6 * 0):
            e = edges[eid]
            if n["id"] in (e["a"], e["b"]):
                continue
            a, b = e["pts"][i], e["pts"][i + 1]
            if seg_len(a, b) > 50:      # long segments: check directly below
                continue
            d, t = point_seg_dist((n["x"], n["y"]), a, b)
            if d <= tol and 0.0 < t < 1.0:
                best = (n["id"], e["id"], d)
                break
        if best is None:
            for e in edges:
                if n["id"] in (e["a"], e["b"]):
                    continue
                p = e["pts"]
                for i in range(len(p) - 1):
                    if seg_len(p[i], p[i + 1]) <= 50:
                        continue
                    d, t = point_seg_dist((n["x"], n["y"]), p[i], p[i + 1])
                    if d <= tol and 0.0 < t < 1.0:
                        best = (n["id"], e["id"], d)
                        break
                if best:
                    break
        if best:
            tjoints.append(best)
    # crossings without a node (same set of pipe layers)
    crossings = 0
    cg = Grid(50.0)
    segs = []
    for e in edges:
        p = e["pts"]
        for i in range(len(p) - 1):
            segs.append((e["id"], p[i], p[i + 1]))
    if len(segs) <= 60000:
        for k, (eid, a, b) in enumerate(segs):
            cg.add((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, k)
        seen = set()
        for k, (eid, a, b) in enumerate(segs):
            r = seg_len(a, b) / 2 + 50
            for _, _, _, j in cg.near((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, r):
                if j <= k or (k, j) in seen:
                    continue
                seen.add((k, j))
                e2, c, d = segs[j]
                if e2 == eid:
                    continue
                if seg_cross(a, b, c, d):
                    crossings += 1
    else:
        crossings = None
    long_segs = []
    for e in edges:
        # straight run between vertices longer than the spacing: a manhole is needed in between anyway
        if e["len"] > spacing + 0.5:
            long_segs.append(e["id"])
    return {"parts": len(comp), "part_sizes": sorted(comp.values(), reverse=True)[:10], "loops": max(loops, 0),
            "self_loops": self_loops, "nodes": len(used), "edges": len(edges), "dead_ends": len(dead),
            "junctions": sum(1 for n in used if n["deg"] >= 3), "gaps": gaps, "tjoints": tjoints,
            "crossings": crossings, "long": long_segs,
            "length": sum(e["len"] for e in edges)}
