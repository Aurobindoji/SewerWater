"""Label / GL matching of dxf_extract (sewer_app, 12-Oct-2026): offsets in text heights, GL paired with its label,
no false manholes where the drawing has manhole symbols, optimal pass 2, numbering prior."""
import ezdxf

from sewer_app import dxf_extract
from sewer_app import dxf_inspect as di


def drawing(path, n=40, small_every=4, symbols=True):
    """A straight sewer of n manholes 20 m apart. Label at 1.92 h up-right of the symbol, GL at 1.18 h up-right
    of the label; every small_every-th manhole uses the smaller text (h 0.89 instead of 1.27)."""
    doc = ezdxf.new()
    msp = doc.modelspace()
    for lay in ("PIPE", "MH-"):
        doc.layers.add(lay)
    truth = {}
    for i in range(n):
        x, y = 20.0 * i, 0.0
        h = 0.89 if i % small_every == 0 else 1.27
        lab, gl = f"MH-{100 + i}", round(85.0 - 0.05 * i + (0.3 if i % 3 else 0.0), 2)
        truth[(x, y)] = (lab, gl)
        lx, ly = x + 1.92 * h, y + 1.92 * h
        msp.add_text(lab, height=h, dxfattribs={"layer": "MH-", "insert": (lx, ly)})
        msp.add_text(f"{gl:.2f}", height=h, dxfattribs={"layer": "MH-", "insert": (lx + 1.18 * h, ly + 1.18 * h)})
        if i:
            msp.add_line((20.0 * (i - 1), 0.0), (x, y), dxfattribs={"layer": "PIPE"})
    if symbols:
        blk = doc.blocks.new("MHSYM")
        blk.add_circle((0, 0), 0.6)
        for (x, y) in truth:
            msp.add_blockref("MHSYM", (x, y), dxfattribs={"layer": "MH-"})
    doc.saveas(path)
    return truth


def test_offsets_in_text_heights_and_paired_gl(tmp_path):
    p = str(tmp_path / "d.dxf")
    truth = drawing(p)
    ex = dxf_extract.extract(p, ["PIPE"], ["MH-"], ["MH-"])
    got = {(r["X"], r["Y"]): (r["Label"], r["GL"]) for r in ex["mh_rows"]}
    assert got == truth                                   # every label and GL right, incl. the small texts
    assert not any("pass 2" in p_["Problem"] for p_ in ex["problems"])
    assert not any("continuous line" in p_["Problem"] for p_ in ex["problems"])     # no false manholes


def test_optimal_pass2_beats_greedy():
    """Two nodes 3 m apart, two texts: the greedy shortest pair (text A -> node 2, 1.0 m) would leave text B with
    nothing within reach; the optimal matching pairs both."""
    pairs = [(1.0, 0, "n2"), (1.6, 0, "n1"), (2.0, 1, "n2")]
    assert sorted(di.optimal_pairs(pairs, unmatched_cost=10.0)) == [(0, "n1"), (1, "n2")]


def test_numbering_prior_breaks_a_tie():
    """A text exactly between two free manholes goes to the one next to its neighbour number."""
    nodes = [{"id": i, "x": 10.0 * i, "y": 0.0, "deg": 1, "z": []} for i in range(4)]
    texts = [{"layer": "MH-", "text": "MH-7", "x": 0.0, "y": 0.0, "h": 1.0},          # pass 1 on node 0
             {"layer": "MH-", "text": "MH-50", "x": 30.0, "y": 0.0, "h": 1.0},         # pass 1 on node 3
             {"layer": "MH-", "text": "MH-8", "x": 15.0, "y": 0.0, "h": 1.0}]          # between nodes 1 and 2
    adj = {0: {1}, 1: {0, 2}, 2: {1, 3}, 3: {2}}
    lab = di.labels_near_nodes(nodes, texts, 10.0, None, adj=adj)
    assert lab[1] == "MH-8"                                                           # next to MH-7


def test_inventory_reads_points_and_circles():
    """A drawing with POINT entities (no radius attribute) is read; circles keep their radius."""
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_point((1.0, 2.0), dxfattribs={"layer": "NODE"})
    msp.add_circle((3.0, 4.0), 0.6, dxfattribs={"layer": "NODE"})
    _, _, _, _, points = di.inventory(msp)
    assert [(p["kind"], p["r"]) for p in points] == [("POINT", 0.0), ("CIRCLE", 0.6)]
