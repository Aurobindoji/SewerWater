"""User requests 20-Oct-2026: (1) manholes on top of each other with no sewer between them are a warning (red cross on
the map and in the exported drawing); (2) the zone export of an option that has been designed is drawn into the
design's plan DXF, so the drawing has the pipe labels, diameter / slope, flow arrows and manhole GL / IL too."""
import json
import os
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import ezdxf
import pytest

from sewer_app import repair, ui

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE = os.path.join(HERE, "samples", "sample_area.kml")


def net_of(nodes, conds):
    return {"nodes": {n: {"xy": xy, "ground": 80.0} for n, xy in nodes.items()},
            "conduits": [{"label": f"CO-{i}", "start_node": a, "stop_node": b, "length_m": 10.0, "vertices": []}
                         for i, (a, b) in enumerate(conds, start=1)], "outfalls": ["MH-1"]}


def test_overlapping_manholes():
    nodes = {"MH-1": (0.0, 0.0), "MH-2": (10.0, 0.0), "MH-2-C1": (10.0, 0.0), "MH-3": (20.0, 0.0),
             "MH-4": (20.4, 0.3), "MH-5": (30.0, 0.0), "MH-6": (31.5, 0.0)}
    net = net_of(nodes, [("MH-2", "MH-1"), ("MH-2-C1", "MH-3"), ("MH-3", "MH-4"), ("MH-5", "MH-6")])
    # MH-2 / MH-2-C1: same place, not joined (a loop cut head); MH-3 / MH-4 0.5 m but joined; MH-5 / MH-6 1.5 m
    assert repair.overlaps(net) == [("MH-2", "MH-2-C1", 0.0)]
    iss = [i for i in repair.check(net, None, ["MH-1"]) if i["type"] == repair.OVERLAP]
    assert len(iss) == 1 and iss[0]["item"] == "MH-2 - MH-2-C1" and (iss[0]["x"], iss[0]["y"]) == (10.0, 0.0)
    assert "loop cut head" in iss[0]["detail"]
    net["conduits"].append({"label": "CO-9", "start_node": "MH-2-C1", "stop_node": "MH-2", "length_m": 0.1})
    assert repair.overlaps(net) == []                          # joined by a sewer: no warning
    assert repair.overlaps(net_of({"A": (0, 0), "B": (0.9, 0)}, [])) == [("A", "B", 0.9)]
    assert repair.overlaps(net_of({"A": (0, 0), "B": (1.1, 0)}, [])) == []


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setattr(ui, "PROJECTS", str(tmp_path / "projects"))
    monkeypatch.setattr(ui, "OUT_ROOT", str(tmp_path / "output"))
    srv = ThreadingHTTPServer(("127.0.0.1", 0), ui.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def call(url, body=None):
    req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())


def test_zone_export_with_the_design(server):
    with open(SAMPLE, encoding="utf-8") as fh:
        assert call(server + "/api/layout", {"name": "s", "kml": fh.read()})["ok"]
    req = {"name": "s", "stp": "MH-17", "sewage_lpcd": 108, "start_depth": 0.7}
    z = call(server + "/api/zoning", req)
    a, b = z["options"][0]["option"], z["options"][-1]["option"]
    assert a != b
    plain = call(server + "/api/zoning_export", {"name": "s", "option": a})          # no design yet: zoning only
    assert plain["ok"] and plain["design"] is None
    layers = {e.dxf.layer for e in ezdxf.readfile(plain["files"]["dxf"]).modelspace()}
    assert not any(x.startswith("SEW_") for x in layers) and "SEWER_ZONE_1" in layers

    d = call(server + "/api/design", dict(req, option=a))
    assert d["ok"], d["log"]
    r = call(server + "/api/zoning_export", {"name": "s", "option": a})
    assert r["ok"], r.get("log")
    assert r["design"] == os.path.basename(d["files"]["plan_dxf"])
    doc = ezdxf.readfile(r["files"]["dxf"])
    msp = doc.modelspace()
    layers = {e.dxf.layer for e in msp}
    assert {"SEW_PIPE", "SEW_PIPE_TEXT", "SEW_MH", "SEW_MH_TEXT", "SEW_FLOW_ARROW"} <= layers     # the design
    assert {"ZONE_BOUNDARY_1", "ZONE_NAME", "STP"} <= layers                                        # the zoning
    texts = " ".join(t.dxf.text for t in msp.query("TEXT"))
    assert all(w["label"] in texts for w in d["sewers"][:20])                     # every sewer's label ...
    assert any(f"{m['gl']:.3f}" in texts for m in d["manholes"] if m.get("gl") is not None)   # ... and the levels
    assert doc.layers.get("SEWER_ZONE_1").is_off()           # zone-coloured copies of the sewers: switched off
    # the zone boundary under the design (draw order): every boundary has the lowest sort handle
    order = dict(msp.get_redraw_order())
    zb = [e for e in msp.query("LWPOLYLINE") if e.dxf.layer.startswith("ZONE_BOUNDARY_")]
    assert zb and all(order.get(e.dxf.handle) == "1" for e in zb)
    assert not any(e.dxf.handle in order for e in msp.query("LWPOLYLINE") if e.dxf.layer == "SEW_PIPE")
    assert not any(t.has_dxf_attrib("bg_fill") and t.dxf.bg_fill for t in msp.query("MTEXT")
                   if t.dxf.layer == "ZONE_NAME")             # names without a mask: the pipes under them show
    other = call(server + "/api/zoning_export", {"name": "s", "option": b})       # another option: not its design
    assert other["ok"] and other["design"] is None


def test_every_manhole_in_the_design(server):
    """User decision 20-Oct-2026: the manholes for the spacing (the page's distance, default 30 m) and at bends are put
    into the network before zoning and design - real manholes of the design (own inverts), fixed names, the same
    conduits as the plan DXF; a smaller distance gives more of them."""
    with open(SAMPLE, encoding="utf-8") as fh:
        assert call(server + "/api/layout", {"name": "p", "kml": fh.read(), "spacing": 100})["ok"]
    req = {"name": "p", "stp": "MH-5", "sewage_lpcd": 108, "start_depth": 0.7}
    z = call(server + "/api/zoning", req)
    assert z["ok"], z["log"]
    assert "new manholes before zoning / design" in z["log"] and z["piece_of"]
    d = call(server + "/api/design", dict(req, option=z["options"][0]["option"]))
    assert d["ok"], d["log"]
    assert max(w["length"] for w in d["sewers"]) <= 30.5                      # every sewer within the spacing
    assert not any(w["pieces"] for w in d["sewers"])                          # nothing left to cut after the design
    new = {m["label"]: m for m in d["new_manholes"]}
    assert new and all(m["why"] == "spacing" and m["invert"] is not None for m in new.values())
    assert set(new) <= {m["label"] for m in d["manholes"]}                   # designed manholes, with their IL
    labels = {w["label"] for w in d["sewers"]}
    assert set(z["piece_of"]) <= labels and all(z["piece_of"][p] in labels for p in z["piece_of"])
    groups = {name for name, _ in ezdxf.readfile(d["files"]["plan_dxf"]).groups}
    assert labels <= groups and set(new) <= groups                           # the same conduits and manholes as the DXF
    # the same network again: the same names
    d2 = call(server + "/api/design", dict(req, option=z["options"][0]["option"]))
    assert {m["label"] for m in d2["new_manholes"]} == set(new)
    # the page's distance: 20 m - more manholes, every sewer within 20 m; kept with the run
    z20 = call(server + "/api/zoning", dict(req, mh_spacing=20))
    assert z20["ok"] and not z20["cached"]
    d20 = call(server + "/api/design", dict(req, mh_spacing=20, option=z20["options"][0]["option"]))
    assert d20["ok"] and len(d20["new_manholes"]) > len(new) and max(w["length"] for w in d20["sewers"]) <= 20.5
    assert call(server + "/api/last_results?name=p")["design"]["req"]["mh_spacing"] == 20
    assert not call(server + "/api/zoning", dict(req, mh_spacing=2))["ok"]    # outside 5 - 150 m
    # the zone export: on the same network - every sewer in a zone colour
    e = call(server + "/api/zoning_export", {"name": "p", "option": z20["options"][0]["option"]})
    assert e["ok"], e.get("log")
    sew = [x for x in ezdxf.readfile(e["files"]["dxf"]).modelspace().query("LWPOLYLINE") if x.dxf.layer.startswith("SEWER_ZONE_")]
    assert len(sew) >= len(d20["sewers"]) - len(z20["options"][0]["cuts"])
    # the page's bend angle: another zoning (cache key), kept with the run
    z45 = call(server + "/api/zoning", dict(req, mh_spacing=20, bend_angle=45))
    assert z45["ok"] and not z45["cached"] and "45" in z45["log"]
    d45 = call(server + "/api/design", dict(req, mh_spacing=20, bend_angle=45, option=z45["options"][0]["option"]))
    assert d45["ok"] and call(server + "/api/last_results?name=p")["design"]["req"]["bend_angle"] == 45
    assert not call(server + "/api/zoning", dict(req, bend_angle=0))["ok"]
