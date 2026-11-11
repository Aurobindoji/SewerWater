"""Sewer layout from roads (PFR): a manhole at every road junction, road end and bend (CPHEEO: a sewer is laid
straight between manholes, a change of direction needs a manhole) and at most max_spacing apart along the roads, a
sewer along every road centreline. The network is then zoned and designed like a drawn one (the
zoning turns the road grid into sewer trees - loops cut, outlets / pumping stations chosen).

User decision 12-Oct-2026: roads come from a KML / Google Earth file or from road centrelines in a DWG / DXF; ground
levels from the drawing's spot levels, a DEM GeoTIFF, or a flat assumed level. A network made here is ALWAYS a PFR
(alignment not surveyed): every gl_source starts with 'PFR layout'.

    nodes, edges = road_graph(polylines, snap=1.0, max_spacing=30.0, boundary=polygon)
    net = make_network(nodes, edges, gl_fn, "DEM xyz.tif")
"""
import collections
import math

PFR_TAG = "PFR layout"


# ---------------------------------------------------------------- geometry
def inside(pt, poly):
    """Point in polygon (ray casting); poly = [(x, y)]."""
    x, y = pt
    c = False
    n = len(poly)
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


def _seg_inter(p, q, r, s):
    """(t, u) where p + t (q - p) = r + u (s - r), both in [0, 1]; None if parallel / apart."""
    dx1, dy1, dx2, dy2 = q[0] - p[0], q[1] - p[1], s[0] - r[0], s[1] - r[1]
    den = dx1 * dy2 - dy1 * dx2
    if abs(den) < 1e-12:
        return None
    t = ((r[0] - p[0]) * dy2 - (r[1] - p[1]) * dx2) / den
    u = ((r[0] - p[0]) * dy1 - (r[1] - p[1]) * dx1) / den
    if -1e-9 <= t <= 1 + 1e-9 and -1e-9 <= u <= 1 + 1e-9:
        return t, u
    return None


def _foot(p, a, b):
    """(distance, t) of point p to segment a-b."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    t = 0.0 if not L2 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy)), t


def _plen(pts):
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


# ---------------------------------------------------------------- road graph
STRAIGHT_TOL_M = 1.0      # a road within this of a straight line is straight there: no bend, no manhole


def _straighten(pts, tol):
    """The corners of a polyline (Douglas-Peucker): first and last point and every point where the line leaves the
    straight line by more than tol - the bends that need a manhole."""
    if len(pts) <= 2:
        return list(pts)
    keep = {0, len(pts) - 1}
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        best, bd = None, tol
        for k in range(i + 1, j):
            d = _seg_dist(pts[k], pts[i], pts[j])
            if d > bd:
                best, bd = k, d
        if best is not None:
            keep.add(best)
            stack += [(i, best), (best, j)]
    out = [pts[k] for k in sorted(keep)]
    return [p for i, p in enumerate(out) if i == 0 or math.dist(p, out[i - 1]) > 1e-9]


BOUNDARY_TOL_M = 10.0     # several boundary polygons (wards): a road within this of one of them is inside


def _seg_dist(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    t = 0.0 if not L2 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def road_graph(polylines, snap=1.0, max_spacing=30.0, boundary=None, min_dangle_m=0.0, bend_nodes=True):
    """Road centrelines -> (nodes {id: (x, y)}, edges [(a, b, [(x, y), ...], length)]).
    1. segments (inside the boundary polygon when given - a segment is kept when its middle is inside);
    2. every crossing of two segments and every segment end lying on another segment within `snap` becomes a split
       point (so a T-junction drawn a little short or long is joined);
    3. ends closer than `snap` are one node; duplicate pieces between the same nodes are dropped;
    4. runs of pieces through nodes with two pieces are joined into one road between junctions / ends; road ends
       shorter than min_dangle_m are dropped;
    5. every road is cut at its bends - the corners of the road straightened to within STRAIGHT_TOL_M, so that
       the wobble of a hand-drawn road is no bend - and each straight stretch is divided into equal parts not
       longer than max_spacing: a manhole at every bend and division, the sewer straight between two manholes.
       bend_nodes=False (water mains): no node at the bends - each road into equal parts along its line."""
    segs = []
    # boundary: one polygon, or several (the wards together: a piece is kept when its middle is inside one of them or
    # within BOUNDARY_TOL_M of one - a narrow gap left between two wards drawn side by side does not cut a road)
    polys = None
    if boundary:
        multi = isinstance(boundary[0][0], (list, tuple))
        polys = [[tuple(p[:2]) for p in pg] for pg in (boundary if multi else [boundary])]
    tol = BOUNDARY_TOL_M if polys and len(polys) > 1 else 0.0

    def keep(pt):
        if any(inside(pt, pg) for pg in polys):
            return True
        return tol > 0 and any(_seg_dist(pt, c, d) <= tol for pg in polys for c, d in zip(pg, pg[1:] + pg[:1]))
    for pl in polylines:
        pts = [tuple(p[:2]) for p in pl]
        for a, b in zip(pts, pts[1:]):
            if math.dist(a, b) <= 1e-6:
                continue
            if polys is None:
                segs.append((a, b))
                continue
            # cut at the boundary; keep the pieces whose middle is inside
            ts = {0.0, 1.0}
            for pg in polys:
                for c, d in zip(pg, pg[1:] + pg[:1]):
                    r = _seg_inter(a, b, c, d)
                    if r:
                        ts.add(min(1.0, max(0.0, r[0])))
            ts = sorted(ts)
            for t0, t1 in zip(ts, ts[1:]):
                if t1 - t0 < 1e-9:
                    continue
                p = (a[0] + t0 * (b[0] - a[0]), a[1] + t0 * (b[1] - a[1]))
                q = (a[0] + t1 * (b[0] - a[0]), a[1] + t1 * (b[1] - a[1]))
                if keep(((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)):
                    segs.append((p, q))
    # ---- 2 split points: crossings and ends on other segments (hash grid)
    cell = max(snap * 4, 25.0)
    grid = collections.defaultdict(list)
    for i, (a, b) in enumerate(segs):
        for gx in range(int(math.floor((min(a[0], b[0]) - snap) / cell)), int(math.floor((max(a[0], b[0]) + snap) / cell)) + 1):
            for gy in range(int(math.floor((min(a[1], b[1]) - snap) / cell)), int(math.floor((max(a[1], b[1]) + snap) / cell)) + 1):
                grid[(gx, gy)].append(i)
    cuts = collections.defaultdict(set)
    snap_to = {}                                        # (segment, end 0/1) -> point on another segment
    seen = set()
    for ids in grid.values():
        for x in range(len(ids)):
            for y in range(x + 1, len(ids)):
                i, j = ids[x], ids[y]
                if (i, j) in seen:
                    continue
                seen.add((i, j))
                (a, b), (c, d) = segs[i], segs[j]
                r = _seg_inter(a, b, c, d)
                if r:
                    t, u = r
                    if 1e-6 < t < 1 - 1e-6:
                        cuts[i].add(t)
                    if 1e-6 < u < 1 - 1e-6:
                        cuts[j].add(u)
                    continue
                for (si, sa, sb), (oj, oa, ob) in (((i, a, b), (j, c, d)), ((j, c, d), (i, a, b))):
                    for end, p in ((0, sa), (1, sb)):
                        dd, u = _foot(p, oa, ob)
                        if dd <= snap and snap < u * math.dist(oa, ob) < math.dist(oa, ob) - snap:
                            cuts[oj].add(u)
                            snap_to[(si, end)] = (oa[0] + u * (ob[0] - oa[0]), oa[1] + u * (ob[1] - oa[1]))
    pieces = []
    for i, (a, b) in enumerate(segs):
        a2, b2 = snap_to.get((i, 0), a), snap_to.get((i, 1), b)
        ts = [0.0] + sorted(cuts[i]) + [1.0]
        P = [(a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])) for t in ts]
        P[0], P[-1] = a2, b2
        pieces += [(p, q) for p, q in zip(P, P[1:]) if math.dist(p, q) > 1e-6]
    # ---- 3 nodes: ends within snap merged
    ng = collections.defaultdict(list)
    pos, parent = [], []

    def find(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    def node_of(p):
        gx, gy = int(math.floor(p[0] / snap)), int(math.floor(p[1] / snap))
        for i in range(gx - 1, gx + 2):
            for j in range(gy - 1, gy + 2):
                for k in ng.get((i, j), ()):
                    if math.dist(pos[k], p) <= snap:
                        return find(k)
        k = len(pos)
        pos.append(p)
        parent.append(k)
        ng[(gx, gy)].append(k)
        return k
    raw = {}
    for p, q in pieces:
        a, b = node_of(p), node_of(q)
        if a == b:
            continue
        key = (min(a, b), max(a, b))
        if key not in raw:                                   # duplicate pieces (overlapping lines) dropped
            raw[key] = [pos[a], pos[b]] if a < b else [pos[b], pos[a]]
    # ---- 4 join runs through degree-2 nodes
    adj = collections.defaultdict(list)
    for (a, b), pts in raw.items():
        adj[a].append((b, (a, b)))
        adj[b].append((a, (a, b)))
    used, roads = set(), []
    for start in list(adj):
        if len(adj[start]) == 2:
            continue
        for nb, key in adj[start]:
            if key in used:
                continue
            chain, cur, prev_key = [start], nb, key
            used.add(key)
            while len(adj[cur]) == 2:
                chain.append(cur)
                (n1, k1), (n2, k2) = adj[cur]
                nxt, k = (n2, k2) if k1 == prev_key else (n1, k1)
                if k in used:
                    break
                used.add(k)
                prev_key, cur = k, nxt
            chain.append(cur)
            roads.append(chain)
    for key in raw:                                           # closed rings with no junction
        if key not in used:
            a, b = key
            chain, cur, prev_key = [a], b, key
            used.add(key)
            while cur != a:
                chain.append(cur)
                (n1, k1), (n2, k2) = adj[cur]
                nxt, k = (n2, k2) if k1 == prev_key else (n1, k1)
                used.add(k)
                prev_key, cur = k, nxt
            chain.append(a)
            roads.append(chain)
    if min_dangle_m:
        deg = collections.Counter()
        for ch in roads:
            deg[ch[0]] += 1
            deg[ch[-1]] += 1
        roads = [ch for ch in roads if not ((deg[ch[0]] == 1 or deg[ch[-1]] == 1)
                                            and _plen([pos[k] for k in ch]) < min_dangle_m)]
    # ---- 5 manholes along the roads
    nodes, edges, ids = {}, [], {}

    def nid(k):
        if k not in ids:
            ids[k] = len(ids) + 1
            nodes[ids[k]] = pos[k]
        return ids[k]
    def tmp(xy):
        new = len(nodes) + 1 + 100000000                      # temporary key, renumbered below
        nodes[new] = xy
        return new
    for ch in roads:
        pts = [pos[k] for k in ch]
        if _plen(pts) <= 1e-6:
            continue
        if not bend_nodes:                                    # a water main: nodes only along the road, it follows the bends
            L = _plen(pts)
            n = max(1, math.ceil(L / max_spacing - 1e-9))
            from .spacing import point_at, sub_poly
            chain = [nid(ch[0])] + [tmp(point_at(pts, L * i / n)) for i in range(1, n)] + [nid(ch[-1])]
            for i in range(n):
                edges.append((chain[i], chain[i + 1], sub_poly(pts, L * i / n, L * (i + 1) / n), L / n))
            continue
        corners = _straighten(pts, STRAIGHT_TOL_M)            # the road's ends and bends
        prev = nid(ch[0])
        for j in range(len(corners) - 1):
            a, b = corners[j], corners[j + 1]
            L = math.dist(a, b)
            n = max(1, math.ceil(L / max_spacing - 1e-9))
            chain = [prev]
            for i in range(1, n):
                chain.append(tmp((a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n)))
            chain.append(nid(ch[-1]) if j == len(corners) - 2 else tmp(b))
            for i in range(n):
                edges.append((chain[i], chain[i + 1], [nodes[chain[i]], nodes[chain[i + 1]]], L / n))
            prev = chain[-1]
    # renumber 1..N in order of appearance
    order, ren = [], {}
    for a, b, _, _ in edges:
        for k in (a, b):
            if k not in ren:
                ren[k] = len(ren) + 1
                order.append(k)
    return ({ren[k]: nodes[k] for k in order},
            [(ren[a], ren[b], pts, L) for a, b, pts, L in edges])


# ---------------------------------------------------------------- ground levels
def gl_from_spots(spots):
    """GL function from spot levels [(x, y, z)]: linear on their triangles (TIN), nearest level outside them."""
    import numpy as np
    from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator
    P = np.array([(x, y) for x, y, _ in spots])
    Z = np.array([z for _, _, z in spots])
    lin, near = LinearNDInterpolator(P, Z), NearestNDInterpolator(P, Z)

    def f(x, y):
        v = float(lin(x, y))
        return v if v == v else float(near(x, y))                 # NaN outside the triangles
    return f


def gl_from_raster(path, epsg=None):
    """GL function from a DEM GeoTIFF (rasterio). Points are given in the drawing's system; when the DEM is in
    another CRS, epsg = the drawing's EPSG code is needed to transform."""
    try:
        import rasterio
    except ImportError as e:
        raise ValueError("reading a DEM needs the package rasterio (pip install rasterio)") from e
    ds = rasterio.open(path)
    band = ds.read(1)
    tr = None
    if epsg and ds.crs and ds.crs.to_epsg() != epsg:
        from pyproj import Transformer
        tr = Transformer.from_crs(epsg, ds.crs.to_epsg(), always_xy=True)

    def f(x, y):
        if tr:
            x, y = tr.transform(x, y)
        r, c = ds.index(x, y)
        if 0 <= r < band.shape[0] and 0 <= c < band.shape[1]:
            v = float(band[r, c])
            return None if (ds.nodata is not None and v == ds.nodata) else v
        return None
    return f


def make_network(nodes, edges, gl_fn, gl_source, outfalls=(), node_prefix="MH-", pipe_prefix="CO-"):
    """sewer_app network of a road graph: manholes MH-<n>, conduits CO-<n> (drawn as the roads run); a water
    network: junctions J-<n>, pipes P-<n> (node_prefix / pipe_prefix)."""
    net_nodes = {}
    for k, (x, y) in nodes.items():
        g = gl_fn(x, y) if gl_fn else None
        net_nodes[f"{node_prefix}{k}"] = {"ground": None if g is None else round(g, 3), "xy": (x, y),
                                "gl_source": f"{PFR_TAG}: {gl_source}" if g is not None else f"{PFR_TAG}: no level"}
    conds = [{"label": f"{pipe_prefix}{i}", "start_node": f"{node_prefix}{a}", "stop_node": f"{node_prefix}{b}", "length_m": L,
              "vertices": [tuple(p) for p in pts]} for i, (a, b, pts, L) in enumerate(edges, 1)]
    return {"nodes": net_nodes, "conduits": conds, "outfalls": list(outfalls)}


def population_by_polygons(net, polygons):
    """{manhole: population} from polygons [([(x, y)], population)] (e.g. wards / colonies of a KML with their
    population): the population of each polygon is spread over the manholes inside it in proportion to half the
    length of the sewers meeting there (as pop_dist 'length'). Manholes outside every polygon get none; a polygon
    with no manhole inside is listed. Returns (pop, rows)."""
    w = collections.defaultdict(float)
    for k in net["conduits"]:
        for n in (k["start_node"], k["stop_node"]):
            w[n] += (k["length_m"] or 0.0) / 2.0
    pop, rows = {}, []
    for i, (poly, p) in enumerate(polygons, 1):
        ins = [n for n, v in net["nodes"].items() if v.get("xy") and inside(v["xy"], poly)]
        tw = sum(w[n] for n in ins)
        for n in ins:
            pop[n] = pop.get(n, 0.0) + (p * w[n] / tw if tw else p / len(ins))
        rows.append({"polygon": i, "population": p, "manholes inside": len(ins), "sewer length inside (m)": round(tw * 2, 1)})
    return pop, rows


def nearest_node(net, xy):
    return min(net["nodes"], key=lambda n: math.dist(net["nodes"][n]["xy"], xy))
