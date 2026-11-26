"""The areas of the zones (OZ / DMA) on the map: the project's area, the zones' triangles and the land they close in
(restructure stage 2, 15-Nov-2026: out of ui_api.py; zone_geom.py draws the lines)."""
import math
import os
from water_app.data import project as ui


BOUNDARY_GAP_M = 120.0         # zone boundaries drawn across open land up to this between points - the blocks


                               # between streets; wider empty land stays outside the zones, their lines go round
                               # it (user 14-Nov-2026; 400 m before, which drew the zones on into empty land)
BLOCK_MAX_M2 = None            # land the zones close in on every side is theirs, whatever its size: no ring round


                               # empty land inside the zones, lines only where zones meet and at the outer edge, as
                               # the DPR's key plan (user 15-Nov-2026; 3 ha before - larger land was ringed)
STEP_M = 10.0                  # points along the pipes / the project boundary for drawing the zone boundaries: as


                               # near each other as two mains along one road lie (40 m let a zone's line cut the
                               # other zone's main between its points - user 14-Nov-2026)
ALONE_M = 60.0                 # a pipe with no other pipe this near on one side of it (open land there) gets


STRIP_M = 20.0                 # ... a strip this wide on that side: the zone's line runs beside its outer pipes,


                               # not on them, and a zone reached by one pipe does not shrink to a point
STRAIGHT_M = 25.0              # a zone boundary is straightened: its points up to this far off a straight line go


                               # (user request 14-Nov-2026), where no point of the network changes its side by it


def _project_area(stem):
    """The project boundary polygon(s) in metres: the polygon called boundary, else the wards together (as the
    layout takes them); [] when there is none."""
    import re
    from water_app.core import geo
    f = os.path.join(ui.proj_dir(), stem + ".kml")
    if not os.path.isfile(f):                       # a network from a DXF: no boundary drawn
        return []
    k = geo.read_kml(f)
    polys = [f for f in k["polygons"] if len(f["coords"]) >= 3]
    bnd = [f for f in polys if re.search(r"boundary|सीमा", f"{f.get('folder') or ''} {f.get('name') or ''}", re.I)]
    _, to_xy = ui.converters_for(stem)
    return [[tuple(p) for p in to_xy([[c[1], c[0]] for c in f["coords"]])] for f in (bnd or polys)]


def _along(pts, step):
    """Points every `step` m along a polyline (its own vertices kept)."""
    out = [tuple(pts[0])]
    for a, b in zip(pts, pts[1:]):
        L = math.dist(a, b)
        n = max(1, int(L // step))
        out += [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(1, n + 1)]
    return out


def _mid_along(pts):
    """The point half way ALONG a pipe (it follows the bends of its road) - its valve is drawn there, on the pipe."""
    seg = [math.dist(pts[i - 1], pts[i]) for i in range(1, len(pts))]
    goal = sum(seg) / 2
    for i, L in enumerate(seg, 1):
        if goal <= L or i == len(seg):
            t = min(1.0, goal / L) if L else 0.0
            return (pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * t, pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * t)
        goal -= L
    return tuple(pts[0])


def _enclosed(neighbors, keep, inside, area=None, max_area=None):
    """The triangles left out for their length that the kept ones close in on every side: True for those - a block
    between streets belongs to its zones. Open land that reaches the edge of all the points, or the outside of the
    project boundary, stays out; and so does open land larger than max_area (m2, with area = each triangle's) -
    user 14-Nov-2026: a zone's line goes round empty land, the zones are not drawn on into it to meet there."""
    import numpy as np
    n = len(keep)
    comp = np.full(n, -1)
    open_ = []                                               # per piece of left-out land: reaches the outside?
    size = []
    for i0 in range(n):
        if keep[i0] or comp[i0] >= 0:
            continue
        k = len(open_)
        comp[i0] = k
        stack, out, a = [i0], False, 0.0
        while stack:
            i = stack.pop()
            out = out or not inside[i] or bool((neighbors[i] < 0).any())
            a += float(area[i]) if area is not None else 0.0
            for j in neighbors[i]:
                if j >= 0 and not keep[j] and comp[j] < 0:
                    comp[j] = k
                    stack.append(j)
        open_.append(out)
        size.append(a)
    ok = np.array([not o and (max_area is None or a <= max_area) for o, a in zip(open_, size)], dtype=bool)
    return (comp >= 0) & ok[np.maximum(comp, 0)] & inside if len(ok) else np.zeros(n, dtype=bool)


def _zone_tri(stem, net):
    """Triangles for zone_regions, built once for OZs and DMAs: points along every pipe (each standing for the nearer
    end of its pipe - a pipe between two zones is cut half way, where its valve is drawn) and along the project
    boundary (each standing for the node of the nearest pipe point); triangles
    longer than BOUNDARY_GAP_M (unless the zones close them in - _enclosed) or with their middle outside the boundary
    dropped. Returns (tg, node of each point,
    (X, Y) of the points on the pipes - the ones a straightened boundary must not pass)."""
    import numpy as np
    from matplotlib.path import Path
    import matplotlib.tri as mtri
    pts, who = [], []
    way, of_pipe, way_of = [], [], []                         # the pipe's direction at each point; its pipe
    for c in net["conduits"]:
        vs = c.get("vertices") or [net["nodes"][c["start_node"]]["xy"], net["nodes"][c["stop_node"]]["xy"]]
        run = _along(vs, STEP_M)
        half, gone = sum(math.dist(a, b) for a, b in zip(run, run[1:])) / 2, 0.0
        for i, p in enumerate(run):
            a, b = run[max(0, i - 1)], run[min(len(run) - 1, i + 1)]
            L = math.dist(a, b)
            gone += math.dist(run[i - 1], p) if i else 0.0
            pts.append(p)
            who.append(c["start_node"] if gone <= half else c["stop_node"])
            way.append(((b[0] - a[0]) / L, (b[1] - a[1]) / L) if L > 1e-9 else None)
            of_pipe.append(len(way_of))
        way_of.append(c["label"])
    if len(pts) < 3:
        return None, [], None
    n_pipe = len(pts)
    # open land beside a pipe: a point on that side of it, so its zone has a strip there, not a line of no width
    from scipy.spatial import cKDTree
    P1 = np.array(pts)
    near = cKDTree(P1).query_ball_point(P1, ALONE_M)
    pipe_of = np.array(of_pipe)
    for i in range(n_pipe):
        if way[i] is None:
            continue
        ux, uy = way[i]
        other = [j for j in near[i] if pipe_of[j] != pipe_of[i]]
        q = P1[other] - P1[i]
        side = q[:, 0] * -uy + q[:, 1] * ux if len(other) else np.zeros(0)       # + to the left of the pipe
        for sgn in (1.0, -1.0):
            if np.any(sgn * side > STRIP_M * 0.6):
                continue                                      # another pipe on this side of it
            pts.append((pts[i][0] - sgn * uy * STRIP_M, pts[i][1] + sgn * ux * STRIP_M))
            who.append(who[i])
    area = _project_area(stem)
    P0 = np.array(pts)
    for ring in area:
        for p in _along(list(ring) + [ring[0]], STEP_M)[:-1]:
            pts.append(p)
            who.append(who[int(np.argmin((P0[:, 0] - p[0]) ** 2 + (P0[:, 1] - p[1]) ** 2))])
    X = np.array([p[0] for p in pts])
    Y = np.array([p[1] for p in pts])
    tri = mtri.Triangulation(X, Y)
    T = tri.triangles
    el = np.max(np.stack([np.hypot(X[T[:, i]] - X[T[:, j]], Y[T[:, i]] - Y[T[:, j]])
                          for i, j in ((0, 1), (1, 2), (2, 0))]), axis=0)
    keep = el <= BOUNDARY_GAP_M
    inside = np.ones(len(T), dtype=bool)
    if area:
        mid = np.column_stack([X[T].mean(axis=1), Y[T].mean(axis=1)])
        inside = np.zeros(len(T), dtype=bool)
        for ring in area:
            inside |= Path(np.array(ring)).contains_points(mid)
        keep &= inside
    x, y = X[T], Y[T]
    a2 = np.abs((x[:, 1] - x[:, 0]) * (y[:, 2] - y[:, 0]) - (x[:, 2] - x[:, 0]) * (y[:, 1] - y[:, 0])) / 2
    keep |= _enclosed(tri.neighbors, keep, inside, a2, BLOCK_MAX_M2)
    ids = [f"p{i}" for i in range(len(pts))]
    return (ids, X, Y, T[keep]), who, (X[:n_pipe], Y[:n_pipe])
