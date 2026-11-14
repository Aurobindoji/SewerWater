"""The boundary lines of the water zones (water_app/zone_geom.py; user request 14-Nov-2026: straight where they can
be, no needless zig-zag): between two rows of points the line runs straight half way; a straightened line never
passes a point of the network; an OZ's line is the very line of its DMAs."""
import numpy as np
from matplotlib.path import Path
import matplotlib.tri as mtri

from water_app import zone_geom


def grid(rows, n=13, step=40.0):
    """Points in rows (y of each row), `step` apart; row r of zone rows[r][1]. -> (tg, zone, X, Y)."""
    X, Y, zone = [], [], {}
    for y, z in rows:
        for i in range(n):
            zone[f"p{len(X)}"] = z
            X.append(i * step + (7.0 if len(Y) // n % 2 else 0.0))        # rows shifted: no four points on a circle
            Y.append(y)
    X, Y = np.array(X), np.array(Y)
    return ([f"p{i}" for i in range(len(X))], X, Y, mtri.Triangulation(X, Y).triangles), zone, X, Y


def inner(ring, x0, x1):
    """The points of a ring away from the ends of the rows."""
    return [p for p in ring if x0 < p[0] < x1]


def test_between_two_rows_the_line_is_straight():
    tg, zone, X, Y = grid([(0.0, "A"), (90.0, "B")])
    regs = zone_geom.zone_regions(tg, zone)
    assert set(regs) == {"A", "B"}
    for z, side in (("A", 0.0), ("B", 90.0)):
        (ring,) = regs[z]["rings"]
        ys = {round(p[1], 6) for p in inner(ring, 60.0, 420.0)}
        assert ys == {side, 45.0}                              # its own row and the middle line - no teeth between
    assert abs(regs["A"]["area"] + regs["B"]["area"] - 90.0 * 480.0) < 90.0 * 8.0
    # straightened: the middle line is two points, and the zones still share it
    st = zone_geom.zone_regions(tg, zone, straighten=25.0, guard=(X, Y))
    mid = {z: sorted({p for p in st[z]["rings"][0] if abs(p[1] - 45.0) < 1e-6}) for z in "AB"}
    assert mid["A"] == mid["B"] and len(mid["A"]) == 2
    assert len(st["A"]["rings"][0]) < len(regs["A"]["rings"][0])


def test_a_straightened_line_passes_no_point_of_the_network():
    # zone B is a tongue into zone A: three rows, the middle one B only in its middle
    rows = [(0.0, "A"), (40.0, "A"), (80.0, "A")]
    tg, zone, X, Y = grid(rows, n=15)
    for i in range(15 + 5, 15 + 10):
        zone[f"p{i}"] = "B"
    for i in range(30 + 5, 30 + 10):
        zone[f"p{i}"] = "B"
    plain = zone_geom.zone_regions(tg, zone)
    st = zone_geom.zone_regions(tg, zone, straighten=200.0, guard=(X, Y))        # far more than the rows apart
    pts = np.column_stack([X, Y])
    for regs in (plain, st):
        for z in "AB":
            inside = np.zeros(len(X), dtype=bool)
            for ring in regs[z]["rings"]:
                inside ^= Path(np.array(ring)).contains_points(pts, radius=1e-6)
            own = np.array([zone[f"p{i}"] == z for i in range(len(X))])
            edge = (X == X.min()) | (X == X.max()) | (Y == Y.min()) | (Y == Y.max()) | (X == X[15]) | (X == X[29])
            assert not (inside & ~own).any()                   # no point of the other zone inside its line
            assert (inside | ~own | edge).all()                # and its own points (off the outer edge) inside
    assert sum(len(r) for r in st["B"]["rings"]) <= sum(len(r) for r in plain["B"]["rings"])


def test_the_line_of_an_oz_is_the_line_of_its_dmas():
    tg, fine, X, Y = grid([(0.0, "d1"), (50.0, "d1"), (100.0, "d2"), (150.0, "d3"), (200.0, "d3")], n=11)
    parent = {"d1": "OZ-1", "d2": "OZ-1", "d3": "OZ-2"}
    dmas, ozs = zone_geom.zone_regions(tg, fine, straighten=25.0, guard=(X, Y), parent=parent)
    assert set(ozs) == {"OZ-1", "OZ-2"} and set(dmas) == {"d1", "d2", "d3"}
    assert abs(ozs["OZ-1"]["area"] - dmas["d1"]["area"] - dmas["d2"]["area"]) < 1e-6

    def edges(regs, names):
        return {frozenset((a, b)) for z in names for r in regs[z]["rings"] for a, b in zip(r, r[1:])}
    assert edges(ozs, ["OZ-1"]) <= edges(dmas, ["d1", "d2"])   # every piece of the OZ's line is a DMA's too
    assert edges(ozs, ["OZ-2"]) == edges(dmas, ["d3"])
    assert edges(ozs, ["OZ-1"]) & edges(ozs, ["OZ-2"])         # and the two OZs share their common line


def test_two_parts_touching_at_one_point_do_not_cross():
    # a bow tie: two triangles of one zone meeting at one point
    X = np.array([0.0, 0.0, 10.0, 20.0, 20.0])
    Y = np.array([0.0, 10.0, 5.0, 0.0, 10.0])
    tg = (["a", "b", "c", "d", "e"], X, Y, np.array([[0, 1, 2], [2, 3, 4]]))
    rings = zone_geom.zone_regions(tg, dict.fromkeys("abcde", "Z"))["Z"]["rings"]
    assert sorted(len(r) for r in rings) == [4, 4]             # two closed triangles, not one line crossing itself


def test_open_land_the_zones_close_in_is_theirs():
    """Triangles left out for their length: those shut in by kept ones on every side come back (no empty figure in
    the middle of the zones); those that reach the edge of the points, or lie outside the project, stay out."""
    from water_app import ui_api
    # a ring of points round an empty middle, and one point far outside it
    ang = np.linspace(0.0, 2 * np.pi, 24, endpoint=False)
    X = np.concatenate([300 * np.cos(ang), 330 * np.cos(ang + 0.13), [0.0], [2000.0]])
    Y = np.concatenate([300 * np.sin(ang), 330 * np.sin(ang + 0.13), [0.0], [0.0]])
    tri = mtri.Triangulation(X, Y)
    T = tri.triangles
    el = np.max(np.stack([np.hypot(X[T[:, i]] - X[T[:, j]], Y[T[:, i]] - Y[T[:, j]])
                          for i, j in ((0, 1), (1, 2), (2, 0))]), axis=0)
    keep = el <= 150.0                                         # the ring's own triangles; the middle's are too long
    assert not keep.all() and keep.any()
    back = ui_api._enclosed(tri.neighbors, keep, np.ones(len(T), dtype=bool))
    cx, cy = X[T].mean(axis=1), Y[T].mean(axis=1)
    middle = np.hypot(cx, cy) < 290.0
    assert back[middle & ~keep].all() and (middle & ~keep).any()          # the middle: shut in, comes back
    assert not back[(cx > 400.0)].any()                                    # towards the far point: open, stays out
    assert not (back & keep).any()
    # a size limit: the middle (about 28 ha) is too large to be a block between streets - it stays empty land
    a2 = np.abs((X[T][:, 1] - X[T][:, 0]) * (Y[T][:, 2] - Y[T][:, 0])
                - (X[T][:, 2] - X[T][:, 0]) * (Y[T][:, 1] - Y[T][:, 0])) / 2
    assert not ui_api._enclosed(tri.neighbors, keep, np.ones(len(T), dtype=bool), a2, 30000.0).any()
    assert ui_api._enclosed(tri.neighbors, keep, np.ones(len(T), dtype=bool), a2, 400000.0)[middle & ~keep].all()
    # the same middle outside the project boundary: stays out
    assert not ui_api._enclosed(tri.neighbors, keep, ~middle).any()
