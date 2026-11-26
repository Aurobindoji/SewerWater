"""Water DXF import of a drawing converted from a PDF (17-Nov-2026, measured on a real one): everything on layer 0
told apart by colour, at paper size (1 unit = 2 m here), symbol strokes of 0.1 m in a pipe's colour, the pipes
stopping 2 - 4 m short of their junctions and each stroked twice, black buildings, the pipe labels (P-, D-, L-..m)
in one colour and the junction names with their levels in another."""
import ezdxf
import pytest

from water_app.net import dxf_extract, dxf_inspect as di, netedit

S = 2.0                      # metres per drawing unit
STEP = 20.0                  # junction spacing in drawing units (40 m)
NX, NY = 5, 4                # 20 junctions, 31 pipes
SHORT = 1.2                  # the pipes stop this far (units) from a junction


def _pdf_like(path):
    doc = ezdxf.new()
    msp = doc.modelspace()
    jn = {(i, j): (i * STEP, j * STEP) for i in range(NX) for j in range(NY)}
    pipes = [((i, j), (i + 1, j)) for i in range(NX - 1) for j in range(NY)] + \
            [((i, j), (i, j + 1)) for i in range(NX) for j in range(NY - 1)]
    for n, (a, b) in enumerate(pipes, start=1):
        (x1, y1), (x2, y2) = jn[a], jn[b]
        dx, dy = (x2 - x1) / STEP, (y2 - y1) / STEP
        p, q = (x1 + dx * SHORT, y1 + dy * SHORT), (x2 - dx * SHORT, y2 - dy * SHORT)
        col = 82 if n % 2 else 6                                      # pipes coloured by size
        msp.add_lwpolyline([p, q], dxfattribs={"color": col})
        off = (-dy * 0.05, dx * 0.05)                                 # stroked twice, a little apart
        msp.add_lwpolyline([(p[0] + off[0], p[1] + off[1]), (q[0] + off[0], q[1] + off[1])], dxfattribs={"color": col})
        mx, my = (x1 + x2) / 2 - dy * 1.5, (y1 + y2) / 2 + dx * 1.5    # labels beside the pipe's middle
        drawn = abs(q[0] - p[0]) + abs(q[1] - p[1])
        for k, t in enumerate((f"P-{n}", "D-110mm", f"L-{drawn * S:.0f}m")):
            msp.add_text(t, dxfattribs={"color": 5, "height": 1.2, "insert": (mx + dx * 3 * k - 1, my + dy * 3 * k - 0.5)})
    for n, ((i, j), (x, y)) in enumerate(sorted(jn.items()), start=1):
        msp.add_text(f"J-{n}", dxfattribs={"color": 7, "height": 1.2, "insert": (x + 0.6, y + 0.6)})
        msp.add_text(f"{78 + 0.05 * n:.2f}", dxfattribs={"color": 7, "height": 1.2, "insert": (x + 0.6, y - 1.8)})
    for i in range(NX - 1):                                           # black buildings between the pipes
        for j in range(NY - 1):
            x, y = i * STEP + 6, j * STEP + 6
            msp.add_lwpolyline([(x, y), (x + 8, y), (x + 8, y + 8), (x, y + 8)], close=True, dxfattribs={"color": 7})
            msp.add_line((x + 1, y + 1), (x + 3, y + 3), dxfattribs={"color": 7})
    for k in range(400):                                              # symbol strokes of 0.1 m in a pipe colour
        x, y = 3 + (k % 40) * 2.0, 70 + (k // 40) * 0.5
        msp.add_line((x, y), (x + 0.05, y), dxfattribs={"color": 82})
    doc.saveas(path)


@pytest.fixture(scope="module")
def pdf_dxf(tmp_path_factory):
    path = str(tmp_path_factory.mktemp("pdf") / "pdf_like.dxf")
    _pdf_like(path)
    return path


def test_split_by_colour_and_scaled(pdf_dxf):
    doc, _ = di.load(pdf_dxf)
    layers, lines, texts, _, _ = di.inventory(doc.modelspace())
    info = di.inventory.info
    assert info["split"] == "0"
    assert info["scale"] and abs(info["scale"][0] - S) < 0.05 * S
    assert {"0 colour 82", "0 colour 6", "0 colour 7", "0 colour 5"} <= set(layers)
    xs = [p[0] for ln in lines for p in ln["pts"]]
    assert max(xs) - min(xs) > 0.9 * (NX - 1) * STEP * S              # in metres now


def test_guess_takes_the_pipe_colours_and_the_junction_names(pdf_dxf):
    _, guess = netedit.dxf_layers(pdf_dxf, water=True)
    assert set(guess["pipe"]) == {"0 colour 82", "0 colour 6"}
    assert guess["mh"] == ["0 colour 7"]
    assert "0 colour 7" in guess["level"]


def test_import_gives_the_network(pdf_dxf):
    ex = dxf_extract.extract(pdf_dxf, ["0 colour 82", "0 colour 6"], ["0 colour 7"], ["0 colour 7"])
    rows = ex["mh_rows"]
    assert len(rows) == NX * NY
    assert len(ex["co_rows"]) == (NX - 1) * NY + NX * (NY - 1)
    assert all(r["Label"].startswith("J-") for r in rows)
    assert all(r["GL"] is not None for r in rows)
    text = "\n".join(ex["summary"])
    assert "a layer per colour" in text and "scaled x" in text
    assert "stop short of their junctions" in text and "drawn twice a little apart" in text


def test_a_drawing_in_metres_on_its_layers_is_left_as_it_is(tmp_path):
    doc = ezdxf.new()
    msp = doc.modelspace()
    for i in range(30):
        msp.add_line((40 * i, 0), (40 * i + 40, 0), dxfattribs={"layer": "PIPE", "color": 1 + i % 5})
        msp.add_text(f"L-{40}m", dxfattribs={"layer": "PIPE", "height": 1.0, "insert": (40 * i + 20, 1.0)})
    path = str(tmp_path / "m.dxf")
    doc.saveas(path)
    d, _ = di.load(path)
    layers, lines, _, _, _ = di.inventory(d.modelspace())
    assert di.inventory.info == {"split": None, "scale": None, "labelled": []}
    assert set(layers) == {"PIPE"} and lines[0]["len"] == 40


def test_gap_rule_needs_a_clear_gap():
    def ln(a, b):
        return {"pts": [(*a, 0.0), (*b, 0.0)], "len": abs(b[0] - a[0]) + abs(b[1] - a[1]), "closed": False}
    stop = [ln((50 * i + 3, 0), (50 * i + 47, 0)) for i in range(30)]         # 6 m gaps everywhere ...
    assert dxf_extract.gap_tolerance(stop, 0.5)[0] == pytest.approx(6.0)
    near = stop + [ln((2000, 0), (2040, 0)), ln((2040.8, 0), (2080, 0))]      # ... and one of 0.8 m: no rule
    assert dxf_extract.gap_tolerance(near, 0.5) is None
