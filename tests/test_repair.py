"""Network check and repair (user decision 12-Oct-2026: start the design work with the DXF network problems)."""
import ezdxf
import openpyxl

from sewer_app import network, pipeline, repair

from synthetic import INP


def broken():
    """A main sewer A0..A5 (30 m apart, ground falling 0.1 m per pipe) to OUT; a branch B0-B1 that ENDS 0.6 m short of
    A3 (gap); a branch C0-C1 whose end lies ON the middle of pipe A1-A2 (T-joint); a pipe A4-B0 that closes a loop;
    A2 and A3 without GL; two conduits labelled CO-1."""
    nodes = {}

    def node(lab, x, y, g):
        nodes[lab] = {"ground": g, "xy": (x, y), "gl_source": "text" if g is not None else ""}
    for i in range(6):
        node(f"A{i}", 30.0 * i, 0.0, None if i in (2, 3) else 100.0 - 0.1 * i)
    node("OUT", 180.0, 0.0, 99.3)
    node("B1", 90.0, 0.6, 99.9)                   # 0.6 m from A3
    node("B0", 90.0, 30.0, 100.2)
    node("C1", 45.0, 0.0, 99.95)                  # on pipe A1-A2
    node("C0", 45.0, -30.0, 100.3)
    conds = []

    def pipe(lab, a, b):
        pa, pb = nodes[a]["xy"], nodes[b]["xy"]
        conds.append({"label": lab, "start_node": a, "stop_node": b,
                      "length_m": ((pa[0] - pb[0]) ** 2 + (pa[1] - pb[1]) ** 2) ** 0.5, "vertices": [pa, pb]})
    for i in range(5):
        pipe(f"CO-{i + 1}", f"A{i}", f"A{i + 1}")
    pipe("CO-6", "A5", "OUT")
    pipe("CO-7", "B0", "B1")
    pipe("CO-8", "C0", "C1")
    pipe("CO-1", "A4", "B0")                      # duplicate label AND closes a loop once the gap is joined
    gaps = {"mh_rows": [], "co_rows": [], "problems": [
        {"Problem": "near-miss gap (not joined)", "Item": "B1 - A3", "X": 90.0, "Y": 0.6, "Detail": "0.60 m apart"}]}
    return {"nodes": nodes, "conduits": conds, "outfalls": ["OUT"]}, gaps


def test_check_finds_the_problems():
    net, ex = broken()
    kinds = {i["type"] for i in repair.check(net, ex, ["OUT"])}
    assert {"near-miss gap", "conduit label used twice"} <= kinds


def test_repair(tmp_path):
    net, ex = broken()
    fixed, log = repair.repair(net, ex, ["OUT"])
    kinds = [r["repair"] for r in log]
    assert "duplicate conduit label renamed" in kinds
    assert "near-miss gap joined" in kinds and "A3" not in fixed["nodes"]          # B1 kept: it has a GL
    assert "T-joint: line split at a manhole" in kinds
    assert any(k["start_node"] == "A1" and k["stop_node"] == "C1" for k in fixed["conduits"])
    assert "loop: conduit disconnected at its higher end" in kinds
    # GL of A2 interpolated along the sewer between C1 (99.95, now on the line A1-A2, 15 m) and B1 (99.90, 30 m)
    g = {n: v["ground"] for n, v in fixed["nodes"].items()}
    assert all(v is not None for v in g.values())
    assert fixed["nodes"]["A2"]["gl_source"] == repair.INTERP_SRC
    assert abs(g["A2"] - (99.95 / 15 + 99.90 / 30) / (1 / 15 + 1 / 30)) < 1e-3
    assert not network.validate(fixed)
    labels = [k["label"] for k in fixed["conduits"]]
    assert len(labels) == len(set(labels))
    assert sum(k["length_m"] for k in fixed["conduits"]) > 0
    out = pipeline.run(fixed, INP, log=lambda s: None)              # the repaired network designs
    assert any("interpolated along the sewer" in w for w in out["warnings"])
    xl, dxf = str(tmp_path / "c.xlsx"), str(tmp_path / "c.dxf")
    repair.write_check(repair.check(net, ex, ["OUT"]), log, xl, dxf, parts=repair.parts_report(fixed, ["OUT"]))
    assert "Issues" in openpyxl.load_workbook(xl, read_only=True).sheetnames
    assert "CHK_GAP_JOINED" in ezdxf.readfile(dxf).layers


def test_fill_gl_is_linear_along_a_run():
    nodes = {f"N{i}": {"ground": None, "xy": (10.0 * i, 0.0), "gl_source": ""} for i in range(6)}
    nodes["N0"]["ground"], nodes["N5"]["ground"] = 100.0, 95.0
    conds = [{"label": f"C{i}", "start_node": f"N{i}", "stop_node": f"N{i + 1}", "length_m": 10.0, "vertices": []}
             for i in range(5)]
    net = {"nodes": nodes, "conduits": conds, "outfalls": ["N5"]}
    log = []
    repair.fill_gl(net, log)
    for i in range(6):
        assert abs(net["nodes"][f"N{i}"]["ground"] - (100.0 - i)) < 1e-3


def test_cut_head_population_share():
    """pop_dist csv: a head made by a cut (cut_of, or label <MH>-C<n> at the same place after a CSV round trip)
    gets its share of the manhole's population by sewer length; a head given in the file keeps its value."""
    from sewer_app import flows
    nodes = {"A": {"xy": (0.0, 0.0)}, "A-C1": {"xy": (0.0, 0.0)}, "B": {"xy": (30.0, 0.0)},
             "B-C1": {"xy": (99.0, 0.0)}, "D-C2": {"xy": (5.0, 5.0), "cut_of": "D"}, "D": {"xy": (5.0, 5.0)}}
    assert flows.cut_heads(nodes) == {"A-C1": "A", "D-C2": "D"}            # B-C1 is elsewhere: a real manhole
    data = {"conduits": [{"start_node": "A", "stop_node": "B", "length_m": 30.0},
                         {"start_node": "A-C1", "stop_node": "B", "length_m": 10.0},
                         {"start_node": "D-C2", "stop_node": "B", "length_m": 20.0}]}
    pop = {"A": 100.0, "B": 50.0, "D": 40.0, "D-C2": 7.0}
    rows = flows.share_cut_heads(pop, data, flows.cut_heads(nodes))
    assert abs(pop["A"] - 75.0) < 1e-9 and abs(pop["A-C1"] - 25.0) < 1e-9 and pop["D-C2"] == 7.0
    assert [r["head"] for r in rows] == ["A-C1"]
