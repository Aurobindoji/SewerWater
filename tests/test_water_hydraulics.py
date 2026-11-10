"""The water solver against hand results: one pipe, pipes in series, parallel pipes, two tanks, and a looped grid
checked for continuity / loop energy and against an independent Hardy Cross solution."""
import itertools
import math

import pytest

from water_app import hydraulics as hy


def hl(Q_ls, L, d_mm, C, minor=1.0):
    return hy.resistance(L, d_mm, C, minor) * (Q_ls / 1000.0) ** 1.852


def test_one_pipe_from_a_tank():
    net = {"nodes": {"T": {"elev": 80, "head": 100.0}, "J": {"elev": 78, "demand": 10.0}},
           "pipes": {"P": {"a": "T", "b": "J", "length": 500, "d_mm": 150, "C": 140}}}
    r = hy.solve(net, minor_loss=1.0)
    assert r["converged"]
    assert r["flow"]["P"] == pytest.approx(10.0, rel=1e-6)
    assert r["head"]["J"] == pytest.approx(100.0 - hl(10.0, 500, 150, 140), abs=1e-4)
    assert r["pressure"]["J"] == pytest.approx(r["head"]["J"] - 78)
    assert r["velocity"]["P"] == pytest.approx(0.010 / (math.pi * 0.15 ** 2 / 4), rel=1e-6)
    # minor losses: the head loss 10 % more (CPHEEO 6.6(vi))
    r2 = hy.solve(net)
    assert 100 - r2["head"]["J"] == pytest.approx(1.10 * (100 - r["head"]["J"]), rel=1e-6)


def test_pipes_in_series_and_flow_direction():
    net = {"nodes": {"T": {"elev": 0, "head": 50.0}, "A": {"elev": 0, "demand": 4.0}, "B": {"elev": 0, "demand": 6.0}},
           "pipes": {"1": {"a": "A", "b": "T", "length": 300, "d_mm": 200, "C": 140},       # drawn against the flow
                     "2": {"a": "A", "b": "B", "length": 400, "d_mm": 100, "C": 145}}}
    r = hy.solve(net, minor_loss=1.0)
    assert r["flow"]["1"] == pytest.approx(-10.0, rel=1e-6)                                  # from T to A
    assert r["flow"]["2"] == pytest.approx(6.0, rel=1e-6)
    assert r["head"]["B"] == pytest.approx(50 - hl(10, 300, 200, 140) - hl(6, 400, 100, 145), abs=1e-4)


def test_parallel_pipes_share_the_flow():
    net = {"nodes": {"T": {"elev": 0, "head": 40.0}, "J": {"elev": 0, "demand": 30.0}},
           "pipes": {"a": {"a": "T", "b": "J", "length": 600, "d_mm": 150, "C": 140},
                     "b": {"a": "T", "b": "J", "length": 900, "d_mm": 200, "C": 140}}}
    r = hy.solve(net, minor_loss=1.0)
    qa, qb = r["flow"]["a"], r["flow"]["b"]
    assert qa + qb == pytest.approx(30.0, rel=1e-6)
    assert hl(qa, 600, 150, 140) == pytest.approx(hl(qb, 900, 200, 140), rel=1e-5)          # same head loss


def test_flow_between_two_tanks_and_an_unsupplied_junction():
    net = {"nodes": {"T1": {"elev": 0, "head": 30.0}, "T2": {"elev": 0, "head": 25.0},
                     "X": {"elev": 0, "demand": 1.0}, "Y": {"elev": 0, "demand": 1.0}},
           "pipes": {"P": {"a": "T1", "b": "T2", "length": 1000, "d_mm": 150, "C": 140},
                     "Q": {"a": "X", "b": "Y", "length": 50, "d_mm": 100, "C": 140}}}
    r = hy.solve(net, minor_loss=1.0)
    q = ((5.0 / hy.resistance(1000, 150, 140)) ** (1 / 1.852)) * 1000
    assert r["flow"]["P"] == pytest.approx(q, rel=1e-6)
    assert r["unsupplied"] == ["X", "Y"]
    assert "X" not in r["head"]


def grid(n=4, spacing=200.0):
    """n x n junctions fed by a tank at one corner, some pipes larger - a looped network."""
    nodes = {"T": {"elev": 75.0, "head": 75.0 + 25.0}}
    pipes = {}
    for i, j in itertools.product(range(n), range(n)):
        nodes[f"J{i}{j}"] = {"elev": 75.0 + 0.3 * i - 0.2 * j, "demand": 1.5 + 0.25 * ((i * 7 + j * 3) % 5)}
    pipes["in"] = {"a": "T", "b": "J00", "length": 100, "d_mm": 300, "C": 140}
    for i, j in itertools.product(range(n), range(n)):
        if i + 1 < n:
            pipes[f"v{i}{j}"] = {"a": f"J{i}{j}", "b": f"J{i+1}{j}", "length": spacing, "d_mm": 200 if j == 0 else 99.3, "C": 145}
        if j + 1 < n:
            pipes[f"h{i}{j}"] = {"a": f"J{i}{j}", "b": f"J{i}{j+1}", "length": spacing * 1.2, "d_mm": 150 if i == 0 else 99.3, "C": 145}
    return {"nodes": nodes, "pipes": pipes}


def test_looped_grid_conserves_mass_and_energy():
    net = grid()
    r = hy.solve(net, minor_loss=1.0, tol=1e-10)
    assert r["converged"] and not r["unsupplied"]
    for n, v in net["nodes"].items():                                     # continuity at every junction
        if v.get("head") is not None:
            continue
        net_in = sum((r["flow"][p] if q["b"] == n else -r["flow"][p]) for p, q in net["pipes"].items() if n in (q["a"], q["b"]))
        assert net_in == pytest.approx(v["demand"], abs=1e-6)
    for p, q in net["pipes"].items():                                     # energy on every pipe
        h = hl(abs(r["flow"][p]), q["length"], q["d_mm"], q["C"]) * (1 if r["flow"][p] >= 0 else -1)
        assert r["head"][q["a"]] - r["head"][q["b"]] == pytest.approx(h, abs=1e-6)
    total = sum(v.get("demand", 0) for v in net["nodes"].values())
    assert r["flow"]["in"] == pytest.approx(total, rel=1e-9)


def test_looped_grid_agrees_with_hardy_cross():
    """An independent solution: Hardy Cross on the 9 elementary loops of the 4 x 4 grid."""
    n = 4
    net = grid(n)
    total = sum(v.get("demand", 0) for v in net["nodes"].values())
    # a first balanced guess: the flow in along the first row, then down each column
    Q = {p: 0.0 for p in net["pipes"]}
    Q["in"] = total
    dem = {k: v["demand"] for k, v in net["nodes"].items() if k != "T"}
    col = [sum(dem[f"J{i}{j}"] for i in range(n)) for j in range(n)]
    for j in range(n - 1):                                               # along row 0, left to right
        Q[f"h0{j}"] = sum(col[j + 1:])
    for j in range(n):                                                   # down each column
        for i in range(n - 1):
            Q[f"v{i}{j}"] = sum(dem[f"J{k}{j}"] for k in range(i + 1, n))
    loops = []
    for i, j in itertools.product(range(n - 1), range(n - 1)):           # clockwise: h(i,j) v(i,j+1) -h(i+1,j) -v(i,j)
        loops.append([(f"h{i}{j}", 1), (f"v{i}{j+1}", 1), (f"h{i+1}{j}", -1), (f"v{i}{j}", -1)])
    R = {p: hy.resistance(q["length"], q["d_mm"], q["C"]) for p, q in net["pipes"].items()}
    for _ in range(500):
        worst = 0.0
        for lp in loops:
            num = sum(s * R[p] * (Q[p] / 1000) * abs(Q[p] / 1000) ** 0.852 for p, s in lp)
            den = sum(1.852 * R[p] * abs(Q[p] / 1000) ** 0.852 for p, s in lp)
            dq = -num / den * 1000
            for p, s in lp:
                Q[p] += s * dq
            worst = max(worst, abs(dq))
        if worst < 1e-9:
            break
    r = hy.solve(net, minor_loss=1.0, tol=1e-10)
    for p in net["pipes"]:
        assert r["flow"][p] == pytest.approx(Q[p], abs=1e-5)
