"""The areas of the zones (OZ / DMA) for the map and the DXF - the water module's own (it began as a copy of
zone_regions of sewer_app/zoning.py; isolation of sewer and water, user request 21-Oct-2026: changes here do not reach
the sewer module, nor the reverse).

User request 14-Nov-2026: the boundary lines straight where they can be, no needless zig-zag -
  - between two zones a boundary runs straight through a triangle, from the middle of one of its sides to the middle
    of the other (it used to go by the triangle's centre: a saw's teeth wherever a row of points faces another);
  - then every stretch of boundary is straightened (straighten, m): points up to that far off a straight line are
    left out, as long as no point of the network changes its side by it. A stretch between two zones is straightened
    once, so both zones' lines stay on each other.
"""
import collections
import math


def _key(p):
    return (round(p[0], 4), round(p[1], 4))


def _pieces(P, Z):
    """The parts of one triangle (corners P, their zones Z) by zone: [(zone, polygon)]. One zone: the triangle. Two:
    cut straight from the middle of one mixed side to the middle of the other. Three: a piece per corner (corner -
    side middle - centre - side middle)."""
    mid = lambda a, b: ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)                       # noqa: E731
    if Z[0] == Z[1] == Z[2]:
        return [(Z[0], [P[0], P[1], P[2]])]
    for k in range(3):                                  # corner k alone, the other two of one zone
        i, j = (k + 1) % 3, (k + 2) % 3
        if Z[i] == Z[j]:
            mi, mj = mid(P[k], P[i]), mid(P[k], P[j])
            return [(Z[k], [P[k], mi, mj]), (Z[i], [P[i], P[j], mj, mi])]
    c = ((P[0][0] + P[1][0] + P[2][0]) / 3, (P[0][1] + P[1][1] + P[2][1]) / 3)
    return [(Z[k], [P[k], mid(P[k], P[(k + 1) % 3]), c, mid(P[k], P[(k + 2) % 3])]) for k in range(3)]


def _area_centre(poly):
    a = sx = sy = 0.0
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        w = x1 * y2 - x2 * y1
        a += w
        sx += (x1 + x2) * w
        sy += (y1 + y2) * w
    if abs(a) < 1e-12:
        return 0.0, poly[0]
    return abs(a) / 2, (sx / (3 * a), sy / (3 * a))


def _rings(bnd):
    """Closed lines from boundary edges [(p, q)]. Where more than two edges meet (two parts of a zone touching at one
    point) the line turns as far right as it can: the rings touch there, none crosses itself."""
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
            free = [j for j in adj[cur] if j not in used]
            if not free:
                break
            if len(free) > 1:
                prev = ring[-2]
                d = (cur[0] - prev[0], cur[1] - prev[1])

                def turn(j, cur=cur, d=d):
                    p, q = bnd[j]
                    o = q if p == cur else p
                    e = (o[0] - cur[0], o[1] - cur[1])
                    return math.atan2(d[0] * e[1] - d[1] * e[0], d[0] * e[0] + d[1] * e[1])
                nxt = min(free, key=turn)
            else:
                nxt = free[0]
            used.add(nxt)
            p, q = bnd[nxt]
            cur = q if p == cur else p
            ring.append(cur)
        if len(ring) >= 4:
            rings.append(ring)
    return rings


class _Straight:
    """Stretches of boundary straightened: Douglas-Peucker to `tol` m, a straight piece taken only when no guard
    point (a point of the network) lies between it and the line it replaces. A stretch is worked out once, in one
    direction, and given back to both zones that share it."""

    def __init__(self, tol, guard):
        import numpy as np
        self.np, self.tol, self.done = np, tol, {}
        self.gx = np.asarray(guard[0], dtype=float) if guard is not None else np.zeros(0)
        self.gy = np.asarray(guard[1], dtype=float) if guard is not None else np.zeros(0)
        order = np.argsort(self.gx)
        self.gx, self.gy = self.gx[order], self.gy[order]

    def _swept(self, pts):
        """A guard point inside the closed figure of the points (the line and the straight piece across it)?"""
        if len(pts) < 3 or not len(self.gx):
            return False
        np = self.np
        from matplotlib.path import Path
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        a, b = np.searchsorted(self.gx, min(xs)), np.searchsorted(self.gx, max(xs), side="right")
        if a >= b:
            return False
        gy = self.gy[a:b]
        m = (gy >= min(ys)) & (gy <= max(ys))
        if not m.any():
            return False
        return bool(Path(np.array(pts)).contains_points(np.column_stack([self.gx[a:b][m], gy[m]])).any())

    def _open(self, pts):
        np = self.np
        n = len(pts)
        if n < 3:
            return list(pts)
        A = np.array(pts, dtype=float)
        keep, stack = {0, n - 1}, [(0, n - 1)]
        while stack:
            i, j = stack.pop()
            if j <= i + 1:
                continue
            p, q = A[i], A[j]
            d = q - p
            L2 = float(d @ d)
            w = A[i + 1:j] - p
            if L2 < 1e-12:
                dist = np.hypot(w[:, 0], w[:, 1])
            else:
                t = np.clip((w @ d) / L2, 0.0, 1.0)
                r = w - np.outer(t, d)
                dist = np.hypot(r[:, 0], r[:, 1])
            k = i + 1 + int(np.argmax(dist))
            if float(dist.max()) > self.tol or self._swept(pts[i:j + 1]):
                keep.add(k)
                stack += [(i, k), (k, j)]
        return [pts[i] for i in sorted(keep)]

    def chain(self, pts):
        """An open stretch between two meeting points of boundaries (its ends stay)."""
        rev = (pts[0], pts[1]) > (pts[-1], pts[-2])
        c = tuple(pts[::-1] if rev else pts)
        if c not in self.done:
            self.done[c] = self._open(list(c))
        out = self.done[c]
        return out[::-1] if rev else out

    def closed(self, ring):
        """A ring with no meeting point on it (ring[0] == ring[-1]): begun at its lowest point, in one direction."""
        body = ring[:-1]
        i = body.index(min(body))
        body = body[i:] + body[:i]
        if len(body) > 2 and body[1] > body[-1]:
            body = [body[0]] + body[:0:-1]
        far = max(range(len(body)), key=lambda k: (body[k][0] - body[0][0]) ** 2 + (body[k][1] - body[0][1]) ** 2)
        a, b = self.chain(body[:far + 1]), self.chain(body[far:] + [body[0]])
        return a + b[1:]


def _shares(tg, zone):
    """Every triangle shared out by the zones of its corners -> per zone: its edges (counted), area, centre sums."""
    ns, X, Y, T = tg
    edges = collections.defaultdict(collections.Counter)
    area = collections.defaultdict(float)
    sx, sy = collections.defaultdict(float), collections.defaultdict(float)
    for tri in T:
        P = [(float(X[i]), float(Y[i])) for i in tri]
        for z, poly in _pieces(P, [zone.get(ns[i]) for i in tri]):
            if z is None:
                continue
            ks = [_key(p) for p in poly]
            for kp, kq in zip(ks, ks[1:] + ks[:1]):
                edges[z][(min(kp, kq), max(kp, kq))] += 1
            a, c = _area_centre(poly)
            area[z] += a
            sx[z] += a * c[0]
            sy[z] += a * c[1]
    return edges, area, sx, sy


def _knots(bnd):
    """The points where boundaries meet or end: not exactly two edges at them."""
    ends = collections.defaultdict(set)
    for b in bnd.values():
        for p, q in b:
            ends[p].add(q)
            ends[q].add(p)
    return {p for p, v in ends.items() if len(v) != 2}


def _straight_rings(rings, knots, st):
    """Every ring cut at the meeting points and its stretches straightened (st)."""
    out = []
    for ring in rings:
        if ring[0] != ring[-1]:
            out.append(ring)
            continue
        at = [i for i, p in enumerate(ring[:-1]) if p in knots]
        if not at:
            new = st.closed(ring)
        else:
            body = ring[at[0]:-1] + ring[:at[0]]            # begun at a meeting point
            cut = [i - at[0] for i in at] + [len(body)]
            body.append(body[0])
            new = []
            for a, b in zip(cut, cut[1:]):
                new += st.chain(body[a:b + 1])[:-1]
            new.append(new[0])
        out.append(new if len(new) >= 4 else ring)
    return out


def _result(tg, members, edges, area, sx, sy, knots, st):
    """{zone: rings, area, label} of the zones with these edges; members = {zone: its point names' zones}."""
    ns, X, Y, _ = tg
    out = {}
    for z, cnt in edges.items():
        rings = _rings([e for e, n in cnt.items() if n % 2 == 1])     # an edge twice = inside the zone
        if st is not None:
            rings = _straight_rings(rings, knots, st)
        # label: the zone's point nearest the area-weighted centre (always inside the zone)
        g = (sx[z] / area[z], sy[z] / area[z]) if area[z] else None
        mh = members.get(z) or []
        lab = None
        if g and mh:
            i = min(mh, key=lambda i: (X[i] - g[0]) ** 2 + (Y[i] - g[1]) ** 2)
            lab = (float(X[i]), float(Y[i]))
        out[z] = {"rings": rings, "area": area[z], "label": lab}
    return out


def zone_regions(tg, zone, straighten=0.0, guard=None, parent=None):
    """Area of every zone from the triangles of points (tg = names, X, Y, triangles; zone = {name: zone}): each
    triangle is shared out by the zones of its corners (_pieces), so a boundary runs halfway between points of
    different zones; the outer edge follows the triangles (no data stays outside). straighten (m) and guard
    (X, Y of the network's points): see the module text. Returns {zone: {"rings": [[(x, y), ...], ...], "area": m2,
    "label": (x, y)}}.
    parent = {zone: the larger zone it lies in} (a DMA's OZ): then (the zones, the larger zones) - the larger ones
    made of their zones' areas, so that a line of both is one and the same line."""
    ns = tg[0]
    edges, area, sx, sy = _shares(tg, zone)
    members = collections.defaultdict(list)
    for i, n in enumerate(ns):
        if zone.get(n) is not None:
            members[zone[n]].append(i)
    bnd = {z: [e for e, n in cnt.items() if n % 2 == 1] for z, cnt in edges.items()}
    knots = _knots(bnd) if straighten > 0 else None
    st = _Straight(straighten, guard) if straighten > 0 else None
    out = _result(tg, members, edges, area, sx, sy, knots, st)
    if parent is None:
        return out
    p_edges = collections.defaultdict(collections.Counter)
    p_area, p_sx, p_sy = (collections.defaultdict(float) for _ in range(3))
    p_members = collections.defaultdict(list)
    for z, cnt in edges.items():
        p = parent.get(z)
        if p is None:
            continue
        p_edges[p].update(cnt)
        p_area[p] += area[z]
        p_sx[p] += sx[z]
        p_sy[p] += sy[z]
        p_members[p] += members[z]
    return out, _result(tg, p_members, p_edges, p_area, p_sx, p_sy, knots, st)
