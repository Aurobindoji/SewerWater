"""Isolated pieces of a DXF network joined by themselves (user request 30-Oct-2026): the junctions the zoning leaves to
no OHT, a straight pipe from each piece to the nearest served junction on its own side (no barrier line / zone loop
crossed), within the page's limit (500 m from 7-Nov-2026, was 100 m); a preview first, joined on the user's word by netedit "connect" (auto:
purple on the page, one Undo)."""
from test_dxf_extract import make_dxf
from test_water_ui import call, server  # noqa: F401  (the fixture)
from water_app import netedit
from water_app import server as wserver


def _import(url, tmp, name):
    src = str(tmp / f"{name}.dxf")
    make_dxf(src)                        # MH-1 - MH-2 - MH-6, MH-2 - MH-3 - MH-4 - MH-5 (MH-3 (30, 30), MH-4 (30, 60))
    netedit._UNDO.clear()
    d = call(url + "/api/w/dxf_import", {"path": src, "name": name, "pipe_layers": ["PIPE"], "mh_layers": ["MH"],
                                         "level_layers": ["GL"], "epsg": "local"})
    assert d["ok"]
    a = d["nodes"]["MH-1"]["latlng"]
    req = {"name": name, "pop_factor": 1, "pop_total": 1000,
           "ohts": [{"name": "Ex-OHT-1", "lat": a[0], "lng": a[1], "existing": "1", "capacity_kl": 200, "staging_m": 20}]}
    return d, req


def test_join_an_isolated_piece(server):  # noqa: F811
    url, tmp = server
    d, req = _import(url, tmp, "wjoin")
    c34 = next(c for c in d["conduits"] if {c["from"], c["to"]} == {"MH-3", "MH-4"})
    assert call(url + "/api/w/net_edit", {"name": "wjoin", "ops": [{"op": "delete_conduit", "id": c34["id"]}]})["ok"]
    z = call(url + "/api/w/water_zoning", req)
    assert z["ok"] and z["unserved"] == 2                                   # MH-4, MH-5
    j = call(url + "/api/w/water_join_plan", req)
    assert j["ok"] and j["pieces"] == 1 and j["left"] == [] and j["max_m"] == 500
    (x,) = j["joins"]
    assert (x["a"], x["b"], x["dist_m"], x["nodes"]) == ("MH-4", "MH-3", 30.0, 2)   # not MH-5 - MH-1 (60 m)
    # beyond the page's limit: left, nothing to join
    j = call(url + "/api/w/water_join_plan", dict(req, join_max_m=20))
    assert j["joins"] == [] and [(p["nodes"], p["cut"], p["near_m"]) for p in j["left"]] == [(2, False, 30.0)]
    # joined on the user's word: a purple pipe, the zoning serves every junction, one Undo takes it back
    r = call(url + "/api/w/net_edit", {"name": "wjoin", "ops": [{"op": "connect", "a": "MH-4", "b": "MH-3", "auto": True}]})
    assert r["ok"]
    (new,) = [c for c in r["conduits_upd"].values() if c and c.get("aj")]
    assert (new["from"], new["to"]) == ("MH-4", "MH-3")
    assert "joined by itself" in wserver.NETS["wjoin"]["edits"][-1]["detail"]
    assert call(url + "/api/w/water_zoning", req)["unserved"] == 0
    assert call(url + "/api/w/net_undo", {"name": "wjoin"})["ok"]
    assert call(url + "/api/w/water_zoning", req)["unserved"] == 2


def test_no_join_across_a_barrier(server):  # noqa: F811
    url, tmp = server
    d, req = _import(url, tmp, "wjoinb")
    n3, n4 = d["nodes"]["MH-3"]["latlng"], d["nodes"]["MH-4"]["latlng"]
    y = (n3[0] + n4[0]) / 2                                                   # a highway between MH-3 and MH-4
    lo, hi = min(v["latlng"][1] for v in d["nodes"].values()), max(v["latlng"][1] for v in d["nodes"].values())
    bar = {"name": "Barrier 1", "type": "highway", "gap_m": "1", "latlngs": [[y, lo - 0.001], [y, hi + 0.001]]}
    req = dict(req, barriers=[bar])
    z = call(url + "/api/w/water_zoning", req)
    assert z["ok"] and z["unserved"] == 3                                   # MH-4, MH-5 and the cut end beyond the line
    j = call(url + "/api/w/water_join_plan", req)
    # the only junctions near are across the highway: not joined back over it - a crossing line or an OHT there
    assert j["ok"] and j["joins"] == [] and [(p["nodes"], p["cut"]) for p in j["left"]] == [(3, True)]
    j = call(url + "/api/w/water_join_plan", dict(req, barriers=[]))
    assert j["unserved"] == 0 and j["joins"] == [] and j["left"] == []
