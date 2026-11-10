"""L-section of the main trunk (user decision 12-Oct-2026: general form, option (a))."""
import ezdxf

from sewer_app import lsection, pipeline

from synthetic import INP, synth


def test_trunk_is_the_longest_path_with_new_manholes():
    net = synth()
    for k in net["conduits"]:                    # 45 m pipes: one new manhole in each (30 m spacing)
        k["length_m"] = 45.0
    out = pipeline.run(net, INP, log=lambda s: None)
    st, segs = lsection.trunks(out)["OUT"]
    # longest path: a 240 m branch joining the main sewer, then down the main sewer to OUT
    res = out["res"]
    assert st[0]["node"].startswith("B") and st[-1]["node"] == "OUT"
    assert abs(st[-1]["ch"] - sum(s["length"] for s in segs)) < 1e-9
    assert any(s["new"] for s in st)                               # spacing manholes on the trunk
    for s, g in zip(st, segs):                                     # pieces follow the designed grade
        d = res[g["parent"]]
        assert abs((g["up"] - g["dn"]) - d["slope"] * g["length"]) < 1e-9
    for a, b in zip(segs, segs[1:]):
        assert a["to"] == b["from"]


def test_drawing_sheets(tmp_path):
    out = pipeline.run(synth(), INP, log=lambda s: None)
    p = str(tmp_path / "ls.dxf")
    cnt = lsection.draw(out, p, max_sheet_m=500.0)
    st, _ = lsection.trunks(out)["OUT"]
    assert cnt["outfalls"] == 1 and cnt["sheets"] == len(lsection.sheets_of(st, 500.0)) >= 2
    msp = ezdxf.readfile(p).modelspace()
    texts = [e.dxf.text for e in msp.query("TEXT")]
    assert sum(1 for t in texts if t.startswith("LONGITUDINAL SECTION")) == cnt["sheets"]
    for s in st:                                                    # every trunk manhole in the table
        assert s["node"] in texts
