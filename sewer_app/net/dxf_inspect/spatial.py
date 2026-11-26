"""dxf_inspect: spatial helpers - a grid of points, distances to segments, crossings."""
import math
import collections


# ---------------------------------------------------------------- spatial helpers
class Grid:
    """Simple hash grid for nearest-point queries."""
    def __init__(self, cell):
        self.cell, self.d = max(cell, 1e-6), collections.defaultdict(list)

    def key(self, x, y):
        return (int(math.floor(x / self.cell)), int(math.floor(y / self.cell)))

    def add(self, x, y, item):
        self.d[self.key(x, y)].append((x, y, item))

    def near(self, x, y, r):
        kx, ky = self.key(x, y)
        n = int(math.ceil(r / self.cell))
        out = []
        for i in range(kx - n, kx + n + 1):
            for j in range(ky - n, ky + n + 1):
                for px, py, it in self.d.get((i, j), ()):
                    dd = math.hypot(px - x, py - y)
                    if dd <= r:
                        out.append((dd, px, py, it))
        out.sort(key=lambda t: t[0])
        return out


def point_seg_dist(p, a, b):
    ax, ay, bx, by = a[0], a[1], b[0], b[1]
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(p[0] - ax, p[1] - ay), 0.0
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L2))
    return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy)), t


def seg_cross(a, b, c, d):
    """Proper crossing of segments ab and cd (not touching at the ends)."""
    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    o1, o2, o3, o4 = orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)
    return (o1 * o2 < 0) and (o3 * o4 < 0)
