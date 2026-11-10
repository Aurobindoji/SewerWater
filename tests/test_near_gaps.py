"""Gaps between separate pieces of the drawing (user request 30-Oct-2026: 1.8 m and 41 m between the pieces of three
OHTs in network_sewer_water_v5, found only after the zoning): two pieces of the network within 50 m of each other,
joined by no pipe, are reported with their nearest junctions - not when a barrier line / zone loop lies between them
(cut there on purpose). Both modules' copies of barriers.py."""
import pytest

from sewer_app import barriers as sb
from water_app import barriers as wb


def _net(gap):
    """Two pieces: A-B-C along y = 0 and D-E from C + gap to the east; F alone with G 500 m away."""
    xy = {"A": (0.0, 0.0), "B": (100.0, 0.0), "C": (200.0, 0.0), "D": (200.0 + gap, 0.0), "E": (300.0 + gap, 0.0),
          "F": (1000.0, 0.0), "G": (1500.0, 0.0)}
    pipes = [("P1", "A", "B"), ("P2", "B", "C"), ("P3", "D", "E"), ("P4", "F", "G")]
    return {"nodes": {n: {"xy": p} for n, p in xy.items()},
            "conduits": [{"label": k, "start_node": a, "stop_node": b, "length_m": 100.0, "vertices": []}
                         for k, a, b in pipes]}


@pytest.mark.parametrize("mod", [wb, sb])
def test_two_pieces_close_by_are_a_gap(mod):
    g = mod.near_parts(_net(1.8))
    assert [(x["a"], x["b"], x["dist_m"]) for x in g] == [("C", "D", 1.8)]          # the nearest junctions only
    assert g[0]["sizes"] == (3, 2) and g[0]["xy"] == ((200.0, 0.0), (201.8, 0.0))
    assert [(x["a"], x["b"]) for x in mod.near_parts(_net(41.0))] == [("C", "D")]
    assert mod.near_parts(_net(60.0)) == []                                        # farther than 50 m
    assert [x["dist_m"] for x in mod.near_parts(_net(60.0), max_m=100.0)] == [60.0]
    one = _net(1.8)
    one["conduits"].append({"label": "P5", "start_node": "C", "stop_node": "D", "length_m": 1.8, "vertices": []})
    assert mod.near_parts(one) == []                                               # joined: one piece
    s = mod.near_summary(g)
    assert "1 gap(s) of 50 m or less" in s and "C - D 1.8 m" in s
    assert "C - D 1.8 m" in mod.near_summary_hi(g, what="sewer") and "कोई sewer नहीं" in mod.near_summary_hi(g, what="sewer")


@pytest.mark.parametrize("mod", [wb, sb])
def test_no_gap_across_a_barrier_line(mod):
    bar = [{"name": "NH-19", "xy": [(201.0, -50.0), (201.0, 50.0)]}]
    assert mod.near_parts(_net(1.8), bar) == []
    # a line away from the gap: still one
    assert len(mod.near_parts(_net(1.8), [{"name": "x", "xy": [(50.0, -50.0), (50.0, 50.0)]}])) == 1
    # cut at the line by barriers.cut: the two ends 2 m apart across it are no gap
    net, cuts = mod.cut(_net(1.8), [{"name": "rail", "type": "railway", "xy": [(150.0, -50.0), (150.0, 50.0)]}])
    assert cuts and [(x["a"], x["b"]) for x in mod.near_parts(net, [{"xy": [(150.0, -50.0), (150.0, 50.0)]}])] == [("C", "D")]
    # two pipes cut at one line, 5 m apart: their ends on one side are pieces apart, but made by the cut, not drawn
    two = {"nodes": {"A": {"xy": (0.0, 0.0)}, "B": {"xy": (100.0, 0.0)}, "C": {"xy": (0.0, 80.0)},
                     "D": {"xy": (100.0, 80.0)}},
           "conduits": [{"label": "P1", "start_node": "A", "stop_node": "B", "length_m": 100.0,
                         "vertices": [(0.0, 0.0), (100.0, 0.0)]},
                        {"label": "P2", "start_node": "C", "stop_node": "D", "length_m": 170.0,
                         "vertices": [(0.0, 80.0), (45.0, 5.0), (55.0, 5.0), (100.0, 80.0)]}]}
    line = [{"name": "NH", "type": "highway", "xy": [(50.0, -50.0), (50.0, 50.0)]}]
    net, cuts = mod.cut(two, line)
    assert len(mod.near_parts(net, line)) == 2                                     # P1-x1 - P2-x1, P1-x2 - P2-x2
    assert mod.cut_ends(cuts) == {"P1-x1", "P1-x2", "P2-x1", "P2-x2"}
    assert mod.near_parts(net, line, skip=mod.cut_ends(cuts)) == []


def test_many_gaps_named_nearest_first():
    nodes, conduits = {}, []
    for i in range(10):                     # ten pieces in a row, each 10 m long, gaps of 1, 2, ... 9 m
        x0 = sum(10.0 + k for k in range(1, i + 1))
        nodes[f"a{i}"], nodes[f"b{i}"] = {"xy": (x0, 0.0)}, {"xy": (x0 + 10.0, 0.0)}
        conduits.append({"label": f"p{i}", "start_node": f"a{i}", "stop_node": f"b{i}", "length_m": 10.0})
    g = wb.near_parts({"nodes": nodes, "conduits": conduits})
    assert [x["dist_m"] for x in g] == [float(k) for k in range(1, 10)]
    s = wb.near_summary(g)
    assert s.startswith("9 gap(s)") and "b0 - a1 1 m" in s and "b7 - a8 8 m ..." in s and "b8 - a9" not in s
