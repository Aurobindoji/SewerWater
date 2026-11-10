"""WATER MODULE COPY of sewer_app/zoning.py (zone_regions only) (isolation of sewer and water, user request 21-Oct-2026): changes here do not\nreach the sewer module, nor the reverse. Water rules are written in directly (a water main network keeps its loops\nand has no outfalls)."""
import collections


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
