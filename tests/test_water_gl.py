"""Water DXF import: the ground level of a junction from the drawing's GL text first, the lines' Z only where there is
no text and only when Z agrees with the texts (user request 22-Oct-2026, chit5: every GL had come from the
polylines' elevation - 74.533, -4.617 - though the node layer has its GL texts)."""
import ezdxf

from water_app import dxf_extract


def drawing(path, z_of_lines, texts_at=4):
    """A line of 5 junctions (symbols on layer node), 30 m apart; GL texts 78.0 + 0.1 i at the first texts_at of them;
    two polylines at the elevations z_of_lines (as chit5: -4.617, 26.8), or None: a 3D polyline with Z = the GL at each
    vertex."""
    doc = ezdxf.new()
    msp = doc.modelspace()
    for lay in ("PIPE", "node"):
        doc.layers.add(lay)
    pts = [(30.0 * i, 0.0) for i in range(5)]
    gl = [78.0 + 0.1 * i for i in range(5)]
    if z_of_lines is None:
        msp.add_polyline3d([(x, y, g) for (x, y), g in zip(pts, gl)], dxfattribs={"layer": "PIPE"})
    else:
        msp.add_lwpolyline(pts[:3], dxfattribs={"layer": "PIPE", "elevation": z_of_lines[0]})
        msp.add_lwpolyline(pts[2:], dxfattribs={"layer": "PIPE", "elevation": z_of_lines[1]})
    doc.blocks.new("FILLED_CIRCLE").add_circle((0, 0), 0.5)
    for i, (x, y) in enumerate(pts):
        msp.add_blockref("FILLED_CIRCLE", (x, y), dxfattribs={"layer": "node"})
        if i < texts_at:
            msp.add_text(f"{gl[i]:.3f}m", dxfattribs={"layer": "node", "insert": (x + 1.0, y - 1.5), "height": 0.8})
    doc.saveas(path)
    return gl


def gl_of(path):
    ex = dxf_extract.extract(path, ["PIPE"], ["node"], ["node"])
    return {(r["X"], r["Y"]): (r["GL"], r["GL_source"]) for r in ex["mh_rows"]}, ex


def test_gl_texts_before_a_polyline_elevation(tmp_path):
    path = str(tmp_path / "flat_elev.dxf")
    gl = drawing(path, z_of_lines=(-4.617, 26.8))
    got, ex = gl_of(path)
    for i in range(4):                                                  # from the texts, not -4.617 / 26.8
        g, src = got[(30.0 * i, 0.0)]
        assert g == round(gl[i], 3) and src.startswith("text")
    assert got[(120.0, 0.0)][0] is None                                 # no text there, and Z is no ground: empty
    assert any("Z of the lines not used" in s for s in ex["summary"])


def test_z_used_where_no_text_when_it_agrees(tmp_path):
    path = str(tmp_path / "real_z.dxf")
    gl = drawing(path, z_of_lines=None)                                 # a 3D drawing: Z = the ground
    got, ex = gl_of(path)
    assert got[(0.0, 0.0)][0] == 78.0 and got[(0.0, 0.0)][1].startswith("text")   # the text first
    assert got[(120.0, 0.0)] == (round(gl[4], 3), "Z")                  # no text: the agreeing Z
    assert not any("Z of the lines not used" in s for s in ex["summary"])


def lengths_drawing(path, spacing, len_layer, gl_missing=()):
    """8 junctions on a line, GL texts 73.0 + 0.1 i at them (layer node) but at gl_missing; at the middle of every pipe
    its length with decimals ("15.35m") on len_layer (user report 22-Oct-2026: such a length reads as a GL)."""
    doc = ezdxf.new()
    msp = doc.modelspace()
    for lay in ("PIPE", "node", "LEN"):
        doc.layers.add(lay)
    pts = [(spacing * i, 0.0) for i in range(8)]
    msp.add_lwpolyline(pts, dxfattribs={"layer": "PIPE"})
    doc.blocks.new("FC").add_circle((0, 0), 0.5)
    for i, (x, y) in enumerate(pts):
        msp.add_blockref("FC", (x, y), dxfattribs={"layer": "node"})
        if i not in gl_missing:
            msp.add_text(f"{73.0 + 0.1 * i:.3f}m", dxfattribs={"layer": "node", "insert": (x + 1.0, y - 1.5), "height": 0.8})
        if i < 7:
            msp.add_text(f"{spacing + 0.35:.2f}m", dxfattribs={"layer": len_layer, "insert": (x + spacing / 2, y + 2.0),
                                                                "height": 0.8})
    doc.saveas(path)


def gls(path, level_layers=()):
    ex = dxf_extract.extract(path, ["PIPE"], ["node"], list(level_layers))
    return [r["GL"] for r in sorted(ex["mh_rows"], key=lambda r: r["X"])], ex


def test_pipe_lengths_are_no_gl(tmp_path):
    want = [73.0, 73.1, 73.2, None, 73.4, 73.5, 73.6, 73.7]
    for len_layer in ("LEN", "node"):                     # on a layer of their own, or with the GL texts
        path = str(tmp_path / f"len_{len_layer}.dxf")
        lengths_drawing(path, 15.0, len_layer, gl_missing=(3,))
        got, ex = gls(path)
        assert got == want, (len_layer, got)              # before: all 15.35 (LEN taken as GL layer) / none at all
        assert ex["lvl_layers"] == ["node"]
    # a GL like the length of its pipe (73.2 beside a 73 m pipe) stays a GL: it is written at a junction
    path = str(tmp_path / "len73.dxf")
    lengths_drawing(path, 73.0, "node")
    assert gls(path)[0] == [round(73.0 + 0.1 * i, 3) for i in range(8)]


def test_gl_options(tmp_path):
    path = str(tmp_path / "opts.dxf")
    lengths_drawing(path, 15.0, "LEN", gl_missing=(3,))
    r = dxf_extract.gl_options(path, ["PIPE"], ["node"])
    by = {o["layer"]: o for o in r["options"]}
    assert r["guess"] == ["node"] and r["junctions"] == 8 and r["options"][0]["layer"] == "node"
    assert by["node"]["texts"] == 7 and by["node"]["lengths"] == 0 and by["node"]["near"] == 7
    assert (by["node"]["min"], by["node"]["max"]) == (73.0, 73.7) and by["node"]["level_like"]
    assert by["LEN"]["texts"] == 7 and by["LEN"]["lengths"] == 7 and by["LEN"]["near"] == 0 and not by["LEN"]["level_like"]
    # "no GL" chosen on the page: the import takes none
    got, _ = gls(path, ["(no GL layer)"])
    assert got == [None] * 8


def test_z_row_and_z_mode(tmp_path):
    """The Z of the line ends as a choice of its own (user question 22-Oct-2026): its numbers in the GL options, and the
    import with Z first / texts first / no GL."""
    real = str(tmp_path / "real_z.dxf")
    gl = drawing(real, z_of_lines=None)                                # a 3D drawing: Z = the ground (78.0 ...)
    flat = str(tmp_path / "flat.dxf")
    drawing(flat, z_of_lines=(-4.617, 26.8))                           # the elevations of two polylines
    real5, flat5 = str(tmp_path / "real5.dxf"), str(tmp_path / "flat5.dxf")       # a GL text at every junction
    drawing(real5, z_of_lines=None, texts_at=5)
    drawing(flat5, z_of_lines=(-4.617, 26.8), texts_at=5)
    zr = dxf_extract.gl_options(real5, ["PIPE"], ["node"])["z"]
    assert zr["junctions"] == 5 and zr["distinct"] == 5 and zr["text_diff"] == 0.0 and zr["ground_like"]
    zf = dxf_extract.gl_options(flat5, ["PIPE"], ["node"])["z"]
    assert zf["distinct"] == 2 and zf["text_diff"] > 1 and not zf["ground_like"]
    # no GL texts to choose from, Z like the ground: Z ticked

    def run(path, z_mode, layers=("node",)):
        ex = dxf_extract.extract(path, ["PIPE"], ["node"], list(layers), z_mode=z_mode)
        return [(r["GL"], r["GL_source"][:4]) for r in sorted(ex["mh_rows"], key=lambda r: r["X"])]
    nogl = str(tmp_path / "nogl.dxf")
    drawing(nogl, z_of_lines=None, texts_at=0)
    o = dxf_extract.gl_options(nogl, ["PIPE"], ["node"])
    assert o["guess"] == [] and o["z_guess"]
    # Z first: every junction from Z, even where a text is, and even when Z is no ground (the user's choice)
    assert [s for _, s in run(flat, "first")] == ["Z"] * 5
    assert run(flat, "first")[0][0] == -4.617
    # texts first ("auto"): Z far from the texts is not used; "off": no Z at all
    assert run(flat, "auto")[4] == (None, "")
    assert run(real, "auto")[4] == (round(gl[4], 3), "Z")
    assert run(real, "off")[4] == (None, "")
    # Z only (no GL layer): all from Z
    assert [g for g, _ in run(real, "first", ["(no GL layer)"])] == [round(g, 3) for g in gl]
