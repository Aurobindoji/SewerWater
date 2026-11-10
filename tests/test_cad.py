"""Plan DXF of a design and the zoning outputs (maps + DXFs), on the synthetic network."""
import collections
import math
import os

import ezdxf

from sewer_app import cad, pipeline, zoning

from synthetic import INP, synth


def test_design_drawing(tmp_path):
    out = pipeline.run(synth(), INP, log=lambda s: None)
    path = str(tmp_path / "design.dxf")
    cnt = cad.design_drawing(out, path, text_height=1.0)
    net = out["net_split"]
    assert cnt["nodes"] == len(net["nodes"]) and cnt["conduits"] == len(net["conduits"]) == cnt["arrows"]
    assert not cnt["no_xy"] and not cnt["no_pts"]
    doc = ezdxf.readfile(path)
    txt = collections.defaultdict(list)
    for e in doc.modelspace().query("TEXT"):
        txt[e.dxf.layer].append(e.dxf.text)
    # pipe text "CO-1/200mm/1:250 L=28.0" (one line) or "CO-1/200mm" + "1:250 L=28.0" (two), in the conduit's group
    pipe, lead = {}, set()
    for g in doc.groups.groups():
        texts = [e for e in g if e.dxftype() == "TEXT"]
        if texts and texts[0].dxf.layer == "SEW_PIPE_TEXT":
            pipe[texts[0].dxf.text.split("/")[0]] = texts
            if any(e.dxftype() == "LINE" for e in g):
                lead.add(texts[0].dxf.text)
    assert set(pipe) == {k["label"] for k in net["conduits"]}
    checked = 0
    for lab, d in out["res"].items():                       # every unsplit conduit: diameter and slope as designed
        if lab in pipe and not out["made"].get(lab):
            s = "/".join(t.dxf.text for t in pipe[lab])
            assert s.startswith(f"{lab}/{d['D']:g}mm/1:{round(1 / d['slope'])} L="), s
            checked += 1
    assert checked
    # each pipe text stays between its manholes (or is at the smallest size, or off the pipe on a leader)
    r_mh = 0.6 * 1.0
    for k in net["conduits"]:
        a, b = net["nodes"][k["start_node"]]["xy"], net["nodes"][k["stop_node"]]["xy"]
        room = ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 - 2 * cad.MH_CLEAR * r_mh
        for t in pipe[k["label"]]:
            h = t.dxf.height
            assert (cad.text_width(t.dxf.text, h) <= room + 1e-6 or abs(h - cad.PIPE_TEXT_MIN) < 1e-9
                    or k["label"] in lead), k["label"]
    assert cad.pipe_text("CO-11830", 200, 1 / 250, 28.0, 100.0, 1.0, 0.6) == ([("CO-11830/200mm/1:250 L=28.0", 1)], 1.0)
    lines, h = cad.pipe_text("CO-11830", 200, 1 / 250, 28.0, 18.0, 1.0, 0.6)
    assert lines == [("CO-11830/200mm", 1), ("1:250 L=28.0", -1)] and h == 1.0       # two lines at full size
    lines, h = cad.pipe_text("CO-11830", 200, 1 / 250, 28.0, 9.0, 1.0, 0.6)
    assert len(lines) == 2 and cad.PIPE_TEXT_MIN < h < 1.0                          # two lines, smaller
    lines, h = cad.pipe_text("CO-11830", 200, 1 / 250, 28.0, 8.0, 1.0, 0.6)       # too short for the two: label only
    assert lines == [("CO-11830", 1)] and cad.text_width("CO-11830", h) <= 8.0 - 2 * cad.MH_CLEAR * 0.6 + 1e-9
    lines, h = cad.pipe_text("CO-11830", 200, 1 / 250, 28.0, 5.6, 1.0, 0.6)       # the label just fits, smaller
    assert lines == [("CO-11830", 1)] and cad.PIPE_TEXT_MIN <= h < 0.6
    assert cad.pipe_text("CO-11830", 200, 1 / 250, 28.0, 3.0, 1.0, 0.6) == ([("CO-11830", 0)], 1.0)   # on a leader
    mh = txt["SEW_MH_TEXT"]
    for n, i in out["node_info"].items():                   # GL / IL of every original manhole
        k = mh.index(n)
        assert mh[k + 1] == f"GL {i['ground']:.3f}" and mh[k + 2] == f"IL {i['invert']:.3f}", n


def test_short_pipe_label_on_a_leader(tmp_path):
    """A pipe too short even for its label at PIPE_TEXT_MIN: the label at full size at the end of a leader, square to
    the pipe, away from the manhole texts (up-right of the manholes) and clear of the manhole symbols."""
    for b, side in (((3.0, 0.0), "below"), ((0.0, 3.0), "left")):
        nodes = {"A": {"xy": (0.0, 0.0), "gl": 80.0, "il": 79.0}, "B": {"xy": b, "gl": 80.0, "il": 78.9}}
        conds = [{"label": "CO-7", "pts": [(0.0, 0.0), b], "D": 200, "slope": 1 / 30, "length": 3.0, "dir": 1}]
        path = str(tmp_path / f"short_{side}.dxf")
        assert cad.write_dxf(path, nodes, conds, 1.0)["leaders"] == 1
        g = next(g for _, g in ezdxf.readfile(path).groups if g.dxf.description == "CO CO-7")
        line = next(e for e in g if e.dxftype() == "LINE")
        text = next(e for e in g if e.dxftype() == "TEXT")
        assert text.dxf.text == "CO-7" and text.dxf.height == 1.0 and text.dxf.layer == line.dxf.layer == "SEW_PIPE_TEXT"
        s, e = line.dxf.start, line.dxf.end
        assert abs(s.x - b[0] / 2) < 1e-9 and abs(s.y - b[1] / 2) < 1e-9                  # from the middle of the pipe
        assert abs(math.dist((s.x, s.y), (e.x, e.y)) - cad.LEADER) < 1e-9
        assert (e.y < -2.9) if side == "below" else (e.x < -2.9)                          # square to the pipe, down / left
        assert min(math.dist((e.x, e.y), n["xy"]) for n in nodes.values()) > 2 * 0.6        # clear of the manholes


def test_zoning_outputs(tmp_path):
    z = zoning.run(synth(), INP, log=lambda s: None)
    f = zoning.write_outputs(z, str(tmp_path / "zoning"), source="synthetic")
    for k in ("xlsx", "costs", "gl_png", "boundary_dxf"):
        assert f[k] and os.path.isfile(f[k]), k
    assert len(f["option_png"]) == len(f["network_dxf"]) == len(z["rank"])
    doc = ezdxf.readfile(f["network_dxf"][0][0])
    assert "ZONE_BOUNDARY" in doc.layers and "SEW_PIPE" in doc.layers
