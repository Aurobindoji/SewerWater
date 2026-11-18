"""Water DXF import on badly made drawings (16-Nov-2026, measured on real drawings): levels written E-77.31 m / EL-77.87 m,
a node layer mixing levels with depths, pipe lengths not taken for GL, a typing error among the levels, survey points'
heights, one Z at every line end, lines drawn twice, power lines and road centre lines not taken for pipes."""
import ezdxf

from water_app import dxf_extract, dxf_inspect as di, netedit

PTS = [(30.0 * i, 0.0) for i in range(8)]
GL = [78.0 + 0.1 * i for i in range(8)]


def base(z=0.0):
    doc = ezdxf.new()
    msp = doc.modelspace()
    for lay in ("PIPE", "node"):
        doc.layers.add(lay)
    msp.add_lwpolyline(PTS, dxfattribs={"layer": "PIPE", "elevation": z})
    doc.blocks.new("DOT").add_circle((0, 0), 0.5)
    for x, y in PTS:
        msp.add_blockref("DOT", (x, y), dxfattribs={"layer": "node"})
    return doc, msp


def rows(path, level_layers=()):
    ex = dxf_extract.extract(path, ["PIPE"], ["node"], list(level_layers))
    return {r["X"]: (r["GL"], r["GL_source"]) for r in ex["mh_rows"]}, ex


def test_level_forms():
    assert di.classify("E-77.31 m") == [("level", 77.31)]
    assert di.classify("EL-77.87 m") == [("level", 77.87)]
    assert di.classify("GL-77.81 m") == [("level", 77.81)]
    assert di.classify("77.3380") == [("level", 77.338)]
    assert di.classify("MH-3-441") == [("id", "MH-3-441")]
    assert di.classify("IL-76.22 m") == [("invert", 76.22)]
    assert di.is_tagged_level("E-79.70m") and not di.is_tagged_level("1.20 m")


def test_e_levels_and_depths_on_one_layer(tmp_path):
    """A key plan's node layer: EL-<GL> m and the depth 1.20 m at every node - the depths are no GL."""
    doc, msp = base()
    for (x, y), g in zip(PTS, GL):
        msp.add_text(f"EL-{g:.2f} m", dxfattribs={"layer": "node", "insert": (x + 1, y + 1.5), "height": 0.8})
        msp.add_text("1.20 m", dxfattribs={"layer": "node", "insert": (x + 1, y - 1.5), "height": 0.8})
    path = str(tmp_path / "el.dxf")
    doc.saveas(path)
    got, ex = rows(path)
    assert ex["lvl_layers"] == ["node"]
    assert all(abs(got[x][0] - g) < 0.006 for (x, _), g in zip(PTS, GL))


def test_pipe_lengths_are_no_ground_level():
    """Lengths 7 - 93 m written beside the pipes (a pipe layer): spread far wider than a town's ground."""
    texts = [{"layer": "PIPE0", "text": f"{v:.1f} m", "x": i, "y": 0} for i, v in
             enumerate([7, 12, 18, 22, 25, 26, 27, 28, 30, 31, 33, 36, 40, 52, 70, 93] * 3)]
    assert "PIPE0" not in di.level_candidates(texts)
    near = [{"layer": "PIPE0", "text": f"{20 + 0.3 * i:.1f} m", "x": i, "y": 0} for i in range(30)]    # 20 - 29 m
    assert "PIPE0" not in di.level_candidates(near)                    # one decimal: lengths, however close
    good =[{"layer": "lev", "text": f"{76 + 0.1 * i:.3f}", "x": i, "y": 0} for i in range(30)]
    assert "lev" in di.level_candidates(good)


def test_a_typing_error_is_not_used(tmp_path):
    doc, msp = base()
    for i, ((x, y), g) in enumerate(zip(PTS, GL)):
        v = 777.08 if i == 3 else g
        msp.add_text(f"{v:.3f}", dxfattribs={"layer": "node", "insert": (x + 1, y + 1.5), "height": 0.8})
    path = str(tmp_path / "typo.dxf")
    doc.saveas(path)
    got, ex = rows(path, ["node"])
    assert got[PTS[3][0]][0] is None or got[PTS[3][0]][0] < 100        # never 777.08
    assert any(p["Problem"].startswith("level far from") and p["Detail"] == "777.08" for p in ex["problems"])


def test_survey_points_give_the_ground(tmp_path):
    doc, msp = base()
    doc.layers.add("survey")
    for (x, y), g in zip(PTS, GL):
        msp.add_point((x + 2.0, y + 1.0, g), dxfattribs={"layer": "survey"})
    path = str(tmp_path / "points.dxf")
    doc.saveas(path)
    got, ex = rows(path)
    assert all(got[x] == (round(g, 3), "survey point") for (x, _), g in zip(PTS, GL))


def test_one_z_everywhere_is_not_the_ground(tmp_path):
    doc, msp = base(z=74.681)
    path = str(tmp_path / "flat.dxf")
    doc.saveas(path)
    got, ex = rows(path)
    assert all(v[0] is None for v in got.values())


def test_lines_drawn_twice_kept_once(tmp_path):
    doc, msp = base()
    doc.layers.add("PIPE2")
    msp.add_lwpolyline(PTS[::-1], dxfattribs={"layer": "PIPE2"})       # the same main again, the other way round
    path = str(tmp_path / "twice.dxf")
    doc.saveas(path)
    ex = dxf_extract.extract(path, ["PIPE", "PIPE2"], ["node"], [])
    assert len(ex["co_rows"]) == 7                                       # cut at its 6 inner junctions, not 14
    assert any("drawn twice" in p["Problem"] for p in ex["problems"])


def test_power_line_and_road_centre_line_are_no_pipes(tmp_path):
    doc = ezdxf.new()
    msp = doc.modelspace()
    for lay in ("Ex-Utility-HT Line", "CENTER LINE", "WATER PIPE", "L&T SEWER LINE"):
        doc.layers.add(lay)
        msp.add_lwpolyline([(0, 0), (40, 0), (80, 0)], dxfattribs={"layer": lay})
    path = str(tmp_path / "survey.dxf")
    doc.saveas(path)
    netedit._INV.clear()
    _, guess = netedit.dxf_layers(path, water=True)
    assert guess["pipe"] == ["WATER PIPE"]


def test_the_chosen_prefix_on_the_drawing_names(tmp_path):
    """User decision 16-Nov-2026: JN- chosen at the import - the drawing's MH-1-595 becomes JN-1-595 (numbers kept)."""
    doc, msp = base()
    names = ["MH-1-5", "MH-1-6", "MH-1-7", "MH-2-5", "MH-2-6", "MH-2-7", "MH-3-5", "O-9"]
    for (x, y), nm in zip(PTS, names):
        msp.add_text(nm, dxfattribs={"layer": "node", "insert": (x, y + 1.5), "height": 0.8})
    path = str(tmp_path / "names.dxf")
    doc.saveas(path)
    ex = dxf_extract.extract(path, ["PIPE"], ["node"], [], node_prefix="JN-")
    got = sorted(r["Label"] for r in ex["mh_rows"])
    assert got == sorted(["JN-1-5", "JN-1-6", "JN-1-7", "JN-2-5", "JN-2-6", "JN-2-7", "JN-3-5", "JN-9"])
    keep = dxf_extract.extract(path, ["PIPE"], ["node"], [])            # no prefix chosen: the drawing's names
    assert sorted(r["Label"] for r in keep["mh_rows"]) == sorted(names)


def _grid_net():
    """A tank junction T at the left of a 3 x 2 street grid (100 m blocks); names as a drawing gives them."""
    pts = {"T": (0, 0), "MH-1-9": (100, 0), "MH-1-3": (200, 0), "MH-2-7": (100, 100), "MH-2-1": (200, 100),
           "MH-3-5": (300, 0)}
    links = [("T", "MH-1-9"), ("MH-1-9", "MH-1-3"), ("MH-1-3", "MH-3-5"), ("MH-1-9", "MH-2-7"), ("MH-2-7", "MH-2-1"),
             ("MH-2-1", "MH-1-3")]
    net = {"nodes": {n: {"xy": list(p), "ground": 78.0, "gl_source": "text"} for n, p in pts.items()},
           "conduits": [{"label": f"CO-{i}", "start_node": a, "stop_node": b, "length_m": 100.0, "vertices": [],
                         "id": i} for i, (a, b) in enumerate(links)],
           "outfalls": []}
    return net


def test_new_names_start_at_the_tank_and_run_along_a_line(tmp_path):
    """User request 17-Nov-2026: the app's own names, from the new tank along the pipes, the old ones kept."""
    net = _grid_net()
    order, pipes = netedit.renumber_order(net, [("T", [k["label"] for k in net["conduits"]])])
    assert order[0] == "T"
    assert order[:4] == ["T", "MH-1-9", "MH-1-3", "MH-3-5"]            # straight on first, along the line
    assert sorted(order) == sorted(net["nodes"]) and sorted(pipes) == sorted(k["label"] for k in net["conduits"])
    st = {"stem": "g", "net": net, "ex_issues": [], "reviewed": [], "edits": [], "next_id": 6, "_root": str(tmp_path),
          "kind": "dxf", "dxf": "", "summary": []}
    netedit._UNDO.pop("g", None)
    nmap, pmap = netedit.renumber(st, [("T", [k["label"] for k in net["conduits"]])], "JN-", "P-")
    assert nmap["T"] == "JN-1" and nmap["MH-3-5"] == "JN-4"
    assert set(st["net"]["nodes"]) == {f"JN-{i}" for i in range(1, 7)}
    assert st["net"]["nodes"]["JN-1"]["old"] == "T" and st["net"]["nodes"]["JN-4"]["old"] == "MH-3-5"
    assert {k["label"] for k in st["net"]["conduits"]} == {f"P-{i}" for i in range(1, 7)}
    assert all(k["start_node"] in st["net"]["nodes"] and k["stop_node"] in st["net"]["nodes"] for k in st["net"]["conduits"])
    files = netedit.save_network(st)
    rows = open(files["old_names"], encoding="utf-8-sig").read()
    assert "junction,JN-4,MH-3-5" in rows
    netedit.renumber(st, [("JN-1", [k["label"] for k in st["net"]["conduits"]])], "N-", "PI-")   # again: first name kept
    assert st["net"]["nodes"]["N-4"]["old"] == "MH-3-5"
    netedit.undo(st)
    assert "JN-4" in st["net"]["nodes"]


def test_network_preview_is_what_the_import_makes(tmp_path):
    """The page's network preview (18-Nov-2026): the same junctions and pipes as the import, an apart piece as a second
    part, its open ends counted - and nothing saved."""
    doc, msp = base()
    msp.add_line((500.0, 0.0), (530.0, 0.0), dxfattribs={"layer": "PIPE"})        # a piece apart from the rest
    p = str(tmp_path / "net.dxf")
    doc.saveas(p)
    r = netedit.dxf_net_preview(p, ["PIPE"], ["node"], epsg=None)
    st = netedit.import_dxf(str(tmp_path / "out"), "net", p, ["PIPE"], ["node"], epsg=None, log=lambda *a: None)
    s = r["summary"]
    assert (s["junctions"], s["pipes"]) == (len(st["net"]["nodes"]), len(st["net"]["conduits"]))
    assert s["parts"] == 2 and s["ends"] == 4
    assert sorted({part for part, _ in r["pipes"]}) == [1, 2] and r["local"]
    assert not (tmp_path / "net").exists()
    j = netedit.dxf_net_preview(p, ["PIPE"], ["node"], epsg=None, joints_only=True)["summary"]
    assert (j["junctions"], j["pipes"]) == (4, 2)
