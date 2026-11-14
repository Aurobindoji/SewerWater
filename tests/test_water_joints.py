"""Junctions only where pipes join (user request 14-Nov-2026, water only): a drawing with a point every 30 m (as a
sewer's manholes) gives a water network a junction on each; the option takes the junctions between two pipes out -
their pipes become one, same route and length. Ends, joints, and the junctions something stands on stay."""
import json

from test_dxf_extract import make_dxf
from test_water_ui import call, server  # noqa: F401  (the fixture)
from water_app import netedit


def net_of(pipes, xy=None, **flags):
    """pipes = [(label, from, to, length)]; the junctions on a line unless xy gives their places."""
    names = sorted({n for _, a, b, _ in pipes for n in (a, b)})
    xy = xy or {n: [10.0 * i, 0.0] for i, n in enumerate(names)}
    return {"nodes": {n: {"xy": list(xy[n]), "ground": 100.0, "gl_source": "t"} for n in names},
            "conduits": [dict({"label": lab, "start_node": a, "stop_node": b, "length_m": ln,
                               "vertices": [list(xy[a]), list(xy[b])], "id": i}, **flags.get(lab, {}))
                         for i, (lab, a, b, ln) in enumerate(pipes)], "outfalls": []}


def test_a_line_of_points_becomes_one_pipe():
    # A - B - C - D - E drawn in pieces, the middle one against the others
    net = net_of([("P1", "A", "B", 30.0), ("P2", "C", "B", 30.0), ("P3", "C", "D", 25.5), ("P4", "D", "E", 4.5)])
    assert netedit.through_merge(net) == ["B", "C", "D"]
    assert sorted(net["nodes"]) == ["A", "E"] and len(net["conduits"]) == 1
    k = net["conduits"][0]
    assert (k["label"], k["start_node"], k["stop_node"], k["length_m"]) == ("P1", "A", "E", 90.0)
    assert k["vertices"] == [[0.0, 0.0], [10.0, 0.0], [20.0, 0.0], [30.0, 0.0], [40.0, 0.0]]     # the route kept


def test_joints_ends_and_placed_junctions_stay():
    # a tee at B: A - B - C and B - D; an OHT on X between D and E
    net = net_of([("P1", "A", "B", 10.0), ("P2", "B", "C", 10.0), ("P3", "B", "D", 10.0), ("P4", "D", "X", 10.0),
                  ("P5", "X", "E", 10.0)])
    assert netedit.through_merge(net, keep={"X"}) == ["D"]
    assert sorted(net["nodes"]) == ["A", "B", "C", "E", "X"]
    assert sorted((k["start_node"], k["stop_node"], k["length_m"]) for k in net["conduits"]) == [
        ("A", "B", 10.0), ("B", "C", 10.0), ("B", "X", 20.0), ("X", "E", 10.0)]


def test_a_ring_and_a_second_route_keep_a_junction():
    ring = net_of([("P1", "A", "B", 10.0), ("P2", "B", "C", 10.0), ("P3", "C", "D", 10.0), ("P4", "D", "A", 10.0)])
    netedit.through_merge(ring)
    ends = [frozenset((k["start_node"], k["stop_node"])) for k in ring["conduits"]]
    assert len(ring["nodes"]) == 3 and all(len(e) == 2 for e in ends) and len(set(ends)) == 3   # a ring stays a ring
    assert sum(k["length_m"] for k in ring["conduits"]) == 40.0
    # two routes from T to U (through M, and through N): one stays a single pipe, the other keeps its junction - no
    # two pipes between the same two junctions
    two = net_of([("P0", "S", "T", 10.0), ("P1", "T", "M", 10.0), ("P2", "M", "U", 10.0), ("P3", "T", "N", 12.0),
                  ("P4", "N", "U", 12.0), ("P5", "U", "V", 10.0), ("P6", "T", "W", 5.0), ("P7", "U", "Z", 5.0)])
    netedit.through_merge(two)
    ends = [frozenset((k["start_node"], k["stop_node"])) for k in two["conduits"]]
    assert len(ends) == len(set(ends)) and len(two["nodes"]) == 7 and ("M" in two["nodes"]) != ("N" in two["nodes"])
    assert round(sum(k["length_m"] for k in two["conduits"]), 3) == 74.0   # nothing lost


def test_pipes_with_and_without_connections_are_not_joined():
    net = net_of([("P1", "A", "B", 10.0), ("P2", "B", "C", 10.0)], P2={"no_conn": True})
    assert netedit.through_merge(net) == [] and len(net["conduits"]) == 2


def test_import_option_and_the_button_with_undo(server, tmp_path):  # noqa: F811
    url, tmp = server
    src = str(tmp_path / "small.dxf")
    make_dxf(src)                              # MH-1 - MH-2 - MH-6, and MH-2 - MH-3 - MH-4 - MH-5 (MH-3, MH-4 between)
    netedit._UNDO.clear()
    req = {"path": src, "pipe_layers": ["PIPE"], "mh_layers": ["MH"], "level_layers": ["GL"], "epsg": "local"}
    plain = call(url + "/api/w/dxf_import", dict(req, name="as_drawn"))
    assert plain["ok"] and plain["summary"]["manholes"] == 6 and plain["summary"]["conduits"] == 5
    d = call(url + "/api/w/dxf_import", dict(req, name="joints", joints_only=True))
    assert d["ok"] and d["summary"]["manholes"] == 4 and d["summary"]["conduits"] == 3
    assert "junctions only where pipes join: 2 junctions" in d["log"]
    long = max(d["conduits"], key=lambda c: c["len"])
    assert long["len"] == 90.0 and {long["from"], long["to"]} == {"MH-2", "MH-5"} and len(long["pts"]) == 4
    # the same on a network imported as drawn, by the button; a tube well on MH-3 keeps it; undo brings all back
    with open(tmp / "w_projects" / "as_drawn.tw.json", "w", encoding="utf-8") as fh:
        json.dump([{"latlng": plain["nodes"]["MH-3"]["latlng"], "props": {}}], fh)
    r = call(url + "/api/w/net_joints", {"name": "as_drawn"})
    assert r["ok"] and r["removed"] == 1 and sorted(r["nodes"]) == ["MH-1", "MH-2", "MH-3", "MH-5", "MH-6"]
    assert call(url + "/api/w/net_joints", {"name": "as_drawn"})["removed"] == 0
    back = call(url + "/api/w/net_undo", {"name": "as_drawn"})                 # the second press changed nothing
    back = call(url + "/api/w/net_undo", {"name": "as_drawn"})
    assert back["summary"]["manholes"] == 6 and back["summary"]["conduits"] == 5
