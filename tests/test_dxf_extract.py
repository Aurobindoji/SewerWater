"""dxf_extract on a small drawing made here: pipe lines, MH label texts and GL texts at a fixed offset from the
manholes, and one manhole drawn ON a continuous pipe line. (Old and new code give byte-identical CSVs on
oakdale.dxf - checked 12-Oct-2026 with the same arguments.)"""
import ezdxf

from sewer_app import dxf_extract, network


def make_dxf(path):
    doc = ezdxf.new()
    msp = doc.modelspace()
    for lay in ("PIPE", "MH", "GL"):
        doc.layers.add(lay)
    mhs = {"MH-1": (0.0, 0.0), "MH-2": (30.0, 0.0), "MH-3": (30.0, 30.0), "MH-4": (30.0, 60.0), "MH-5": (0.0, 60.0),
           "MH-6": (60.0, 0.0)}
    gls = {"MH-1": 85.50, "MH-2": 85.20, "MH-3": 85.00, "MH-4": 84.80, "MH-5": 84.60, "MH-6": 85.70}
    msp.add_line(mhs["MH-1"], mhs["MH-2"], dxfattribs={"layer": "PIPE"})
    msp.add_line(mhs["MH-6"], mhs["MH-2"], dxfattribs={"layer": "PIPE"})
    msp.add_lwpolyline([mhs["MH-2"], mhs["MH-3"], mhs["MH-4"], mhs["MH-5"]], dxfattribs={"layer": "PIPE"})  # MH-3, MH-4 on it
    for lab, (x, y) in mhs.items():
        msp.add_circle((x, y), 0.6, dxfattribs={"layer": "MH"})
        msp.add_text(lab, dxfattribs={"layer": "MH", "insert": (x + 1.0, y + 1.0), "height": 0.8})
        msp.add_text(f"{gls[lab]:.2f}", dxfattribs={"layer": "GL", "insert": (x + 1.0, y - 1.5), "height": 0.8})
    doc.saveas(path)
    return mhs, gls


def test_extract_small_drawing(tmp_path):
    path = str(tmp_path / "small.dxf")
    mhs, gls = make_dxf(path)
    ex = dxf_extract.extract(path, ["PIPE"], ["MH"], ["GL"])
    got = {r["Label"]: r for r in ex["mh_rows"]}
    assert set(got) == set(mhs)                                   # MH-3 / MH-4 found ON the polyline
    for lab, g in gls.items():
        assert got[lab]["GL"] == g, lab
        assert (got[lab]["X"], got[lab]["Y"]) == mhs[lab]
    assert len(ex["co_rows"]) == 5
    net = network.from_extract(ex, outfalls=["MH-5"])
    assert not network.validate(net)
    data, ground, xy = network.design_inputs(net)
    assert all(k["to_outfall"] is not None for k in data["conduits"])
    f_mh, f_co, f_x = dxf_extract.write_outputs(ex, str(tmp_path))
    net2 = network.read_extract_csv(f_mh, f_co, outfalls=["MH-5"])
    assert {k: (v["ground"], v["xy"]) for k, v in net2["nodes"].items()} == \
           {k: (v["ground"], v["xy"]) for k, v in net["nodes"].items()}
    assert [(k["label"], k["start_node"], k["stop_node"]) for k in net2["conduits"]] == \
           [(k["label"], k["start_node"], k["stop_node"]) for k in net["conduits"]]


def test_two_numbering_series_and_gl_with_hyphen(tmp_path):
    """greenfield lanes.dxf style (13-Oct-2026): manhole blocks on one layer with 'MH-1', 'GL-75.56 m', 'IL-..', 'D-..'
    under each; two separate networks numbered from MH-1 each; a few long rising mains on 'LinePrimitive'. The
    repeated labels get the part number (MH-1/1, MH-1/2), the GLs are read, the layer guess skips the rising main."""
    from sewer_app import dxf_inspect as di, netedit
    assert di.classify("GL-75.56 m") == [("level", 75.56)] and di.classify("IL-74.36 m") == [("invert", 74.36)]
    assert di.classify("D-1.20 m") == []
    path = str(tmp_path / "two.dxf")
    doc = ezdxf.new()
    msp = doc.modelspace()
    doc.blocks.new(name="MHSYM").add_circle((0, 0), 0.6)
    for lay in ("pipe0", "node", "LinePrimitive"):
        doc.layers.add(lay)
    gl = 80.0
    for y0 in (0.0, 500.0):                              # two networks, both numbered MH-1 .. MH-4
        pts = [(30.0 * i, y0) for i in range(4)]
        msp.add_lwpolyline(pts[:2], dxfattribs={"layer": "pipe0"})
        msp.add_lwpolyline(pts[1:3], dxfattribs={"layer": "pipe0"})
        msp.add_lwpolyline(pts[2:], dxfattribs={"layer": "pipe0"})
        for i, (x, y) in enumerate(pts, start=1):
            msp.add_blockref("MHSYM", (x, y), dxfattribs={"layer": "node"})
            for k, txt in enumerate((f"MH-{i}", f"GL-{gl:.2f} m", f"IL-{gl - 1.2:.2f} m", "D-1.20 m")):
                msp.add_text(txt, dxfattribs={"layer": "node", "insert": (x + 1.9, y + 1.9 - 2.0 * k), "height": 1.27})
            gl -= 0.1
    msp.add_lwpolyline([(0.0, 100.0), (400.0, 100.0), (800.0, 300.0)], dxfattribs={"layer": "LinePrimitive"})
    doc.saveas(path)
    rows, guess = netedit.dxf_layers(path)
    assert guess["pipe"] == ["pipe0"] and guess["mh"] == ["node"] and guess["level"] == ["node"]
    ex = dxf_extract.extract(path, ["pipe0"], ["node"])
    names = sorted(r["Label"] for r in ex["mh_rows"])
    assert names == sorted(f"MH-{i}/{p}" for i in range(1, 5) for p in (1, 2))
    assert all(r["GL"] is not None for r in ex["mh_rows"])
    assert not any(p["Problem"].startswith("MH label used by more than one node") for p in ex["problems"])
