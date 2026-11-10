"""Zone loops (user request 27-Oct-2026): an area enclosed on the map is a zone of its own - the pipes crossing the
loop are closed there (valves); a loop over the OZ limit (50,000) or under one DMA is handled as the user chose:
keep (one OZ as drawn), merge (into the neighbouring OZ) or split (new OZs within it); not chosen yet: kept, and the
page asks."""
import pytest

from water_app import design as wd
from water_app import zoning as wz

from test_water_ui import SAMPLE, call, server  # noqa: F401  (the fixture)


def _grid(n=10, pop=100.0):
    """n x n junctions 100 m apart, pipes along the rows and columns."""
    nodes = {f"{i}-{j}": {"xy": (i * 100.0, j * 100.0), "elev": 80.0, "pop": pop} for i in range(n) for j in range(n)}
    pipes = {}
    for i in range(n):
        for j in range(n):
            if i + 1 < n:
                pipes[f"h{i}-{j}"] = {"a": f"{i}-{j}", "b": f"{i + 1}-{j}", "length": 100.0}
            if j + 1 < n:
                pipes[f"v{i}-{j}"] = {"a": f"{i}-{j}", "b": f"{i}-{j + 1}", "length": 100.0}
    return {"nodes": nodes, "pipes": pipes}


def _loop(net, mode, i_max=3, name="L1"):
    """The loop around the junctions with i <= i_max, its boundary pipes closed (as ui_api._loops)."""
    inside = {n for n in net["nodes"] if int(n.split("-")[0]) <= i_max}
    bnd = sorted(p for p, x in net["pipes"].items() if (x["a"] in inside) != (x["b"] in inside))
    for p in bnd:
        net["pipes"][p]["closed"] = True
    return {"name": name, "nodes": inside, "boundary": bnd, "mode": mode}


@pytest.fixture
def crit():
    return wd.load_criteria()


def test_a_loop_is_a_zone_of_its_own_with_valves_at_its_boundary(crit):
    net = _grid(pop=150.0)                                  # 15,000 people, one OZ without the loop
    lp = _loop(net, "keep")
    z = wz.plan(net, [], crit, loops=[lp])
    inside = {z["oz"][n] for n in lp["nodes"]}
    outside = {z["oz"][n] for n in net["nodes"] if n not in lp["nodes"]}
    assert len(inside) == 1 and not inside & outside
    assert set(lp["boundary"]) <= set(z["closed_pipes"])
    x = z["loops"][0]
    assert x["zones"] == sorted(inside) and x["population"] == 6000 and not x["over"] and not x["under"]


def test_over_the_limit_keep_or_split(crit):
    net = _grid(pop=1500.0)                                 # the loop: 40 x 1,500 = 60,000 > 50,000
    z = wz.plan(net, [], crit, loops=[_loop(net, "keep")])
    x = z["loops"][0]
    assert x["over"] and len(x["zones"]) == 1
    f = [f for f in z["flags"] if f["zone"] == x["zones"][0] and "population" in f["text"]]
    assert f and f[0]["level"] == "warn" and "kept as drawn" in f[0]["text"]
    net = _grid(pop=1500.0)
    z = wz.plan(net, [], crit, loops=[_loop(net, "split")])
    x = z["loops"][0]
    assert x["over"] and len(x["zones"]) == 2
    assert all(zz["population"] <= 50000 for zz in z["zones"] if zz["name"] in x["zones"])


def test_under_one_dma_keep_or_merge(crit):
    net = _grid(pop=150.0)
    lp = _loop(net, "keep", i_max=0)                        # 10 x 150 = 1,500 people = 300 connections < 500
    z = wz.plan(net, [], crit, loops=[lp])
    x = z["loops"][0]
    assert x["under"] and len(x["zones"]) == 1 and not z["unserved"]       # an OHT of its own all the same
    net = _grid(pop=150.0)
    lp = _loop(net, "merge", i_max=0)
    z = wz.plan(net, [], crit, loops=[lp])
    x = z["loops"][0]
    k = x["merged_into"]
    assert k and x["zones"] == [k] and {z["oz"][n] for n in net["nodes"]} == {k}
    assert not set(lp["boundary"]) & set(z["closed_pipes"]) and len(z["proposed"]) == 1


def test_loops_from_the_page_and_the_question(server):  # noqa: F811
    url, _ = server
    with open(SAMPLE, encoding="utf-8") as fh:
        kml = fh.read()
    r = call(url + "/api/w/layout", {"name": "wl", "kml": kml, "gl_mode": "spots", "snap": 1, "spacing": 100})
    lats = sorted({m["latlng"][0] for m in r["manholes"]})
    lngs = sorted({m["latlng"][1] for m in r["manholes"]})
    mid = (lngs[2] + lngs[3]) / 2                                           # a strip at the west edge
    ring = [[lats[0] - 0.001, lngs[0] - 0.001], [lats[-1] + 0.001, lngs[0] - 0.001], [lats[-1] + 0.001, mid],
            [lats[0] - 0.001, mid]]
    loop = {"name": "Ward A", "latlngs": ring, "on_limit": ""}
    req = {"name": "wl", "ohts": [], "pop_factor": 1, "loops": [loop]}
    z = call(url + "/api/w/water_zoning", req)
    assert z["ok"], z.get("log")
    x = z["loops"][0]
    assert x["name"] == "Ward A" and len(x["zones"]) == 1 and x["mode"] == "keep" and x["latlngs"] == ring
    assert x["under"] and z["loop_ask"] and z["loop_ask"][0]["name"] == "Ward A"         # under one DMA: asked
    assert any(f["text"].startswith("zone loop Ward A") for f in z["flags"])
    assert any(f["hi"].startswith("zone लूप Ward A: आबादी") for f in z["flags"])
    m = call(url + "/api/w/water_zoning", dict(req, loops=[dict(loop, on_limit="merge")]))
    assert m["ok"] and not m["loop_ask"] and m["loops"][0]["merged_into"]
    assert len(m["zones"]) == 1
    d = call(url + "/api/w/water_design", dict(req, loops=[dict(loop, on_limit="keep")]))
    assert d["ok"], d.get("log")
    assert any(c["check"] == "zone loop Ward A" for c in d["checks"]) and d["loops"][0]["answered"]
    assert call(url + "/api/w/water_last?name=wl")["design"]["req"]["loops"][0]["on_limit"] == "keep"


def test_small_pieces_cut_off_by_a_loop_go_to_the_neighbour_or_into_it(crit):
    """User report 27-Oct-2026: a loop drawn across roads gave every bit of road cut off inside it an OZ of its own
    (8 - 193 people). A small piece inside not joined to the loop's main part goes out to the neighbour; a small
    piece outside joined only to the loop comes in."""
    from water_app import ui_api
    net = _grid()
    del net["pipes"]["h4-0"], net["pipes"]["v4-0"]          # 4-0: joined only to 3-0, inside the loop
    lp = {"name": "L", "nodes": {n for n in net["nodes"] if int(n.split("-")[0]) <= 3} | {"8-8"}}   # 8-8: a stray
    ppc, dmin = crit["persons_per_connection"]["value"], crit["dma_min_connections"]["value"]
    pc = ui_api._loop_pieces(net, lp, lambda P: P / ppc < dmin, set())
    assert pc == (1, 100.0, 1, 100.0)
    assert "8-8" not in lp["nodes"] and "4-0" in lp["nodes"] and len(lp["nodes"]) == 41
    # a piece holding a given OHT stays where it is
    lp = {"name": "L", "nodes": {n for n in net["nodes"] if int(n.split("-")[0]) <= 3} | {"8-8"}}
    assert ui_api._loop_pieces(net, lp, lambda P: P / ppc < dmin, {"8-8", "4-0"})[::2] == (0, 0)


def test_a_crossing_keeps_a_loop_boundary_pipe_open(server):  # noqa: F811
    """A crossing line across a zone loop (user 27-Oct-2026): the boundary pipe there is not closed (no valve)."""
    url, _ = server
    with open(SAMPLE, encoding="utf-8") as fh:
        kml = fh.read()
    r = call(url + "/api/w/layout", {"name": "wlx", "kml": kml, "gl_mode": "spots", "snap": 1, "spacing": 100})
    lats = sorted({m["latlng"][0] for m in r["manholes"]})
    lngs = sorted({m["latlng"][1] for m in r["manholes"]})
    mid = (lngs[len(lngs) // 2] + lngs[len(lngs) // 2 + 1]) / 2
    ring = [[lats[0] - 0.001, lngs[0] - 0.001], [lats[-1] + 0.001, lngs[0] - 0.001], [lats[-1] + 0.001, mid],
            [lats[0] - 0.001, mid]]
    req = {"name": "wlx", "ohts": [], "pop_factor": 5, "loops": [{"name": "A", "latlngs": ring, "on_limit": "keep"}]}
    z0 = call(url + "/api/w/water_zoning", req)
    n0 = z0["loops"][0]["boundary_pipes"]
    lat = None                                       # where a pipe crosses the loop's east side
    for c in r["conduits"]:
        for p, q in zip(c["pts"], c["pts"][1:]):
            if (p[1] - mid) * (q[1] - mid) < 0 and lats[0] < p[0] < lats[-1]:
                lat = p[0] + (q[0] - p[0]) * (mid - p[1]) / (q[1] - p[1])
        if lat is not None:
            break
    xing = {"name": "X", "latlngs": [[lat, mid - 0.0003], [lat, mid + 0.0003]]}
    z = call(url + "/api/w/water_zoning", dict(req, crossings=[xing]))
    assert z["ok"], z.get("log")
    assert z["loops"][0]["boundary_pipes"] == n0 - 1
    assert any("open at crossings" in f["text"] for f in z["flags"])


def test_why_each_oz(crit):
    """The reason of each OZ (user request 30-Oct-2026): a tank given; a piece the given tank could not take; a piece
    above 50,000 cut into OZs; a piece joined to nothing (isolation)."""
    net = _grid(pop=1500.0)                                  # 150,000 people on one piece
    net["nodes"]["far"] = {"xy": (5000.0, 0.0), "elev": 80.0, "pop": 3000.0}
    net["nodes"]["far2"] = {"xy": (5100.0, 0.0), "elev": 80.0, "pop": 0.0}
    net["pipes"]["pf"] = {"a": "far", "b": "far2", "length": 100.0}
    z = wz.plan(net, [{"name": "Ex-1", "node": "0-0", "capacity_kl": 500, "staging_m": 25, "tubewells": 0}], crit)
    w = z["why"]
    assert w["Ex-1"] == {"kind": "given", "existing": True}
    big = [k for k, x in w.items() if x["kind"] == "proposed" and x["piece_nodes"] > 2]
    assert big and all(w[k]["next_to"] == ["Ex-1"] and w[k]["parts"] == len(big) >= 2 for k in big)
    far = next(k for k, x in w.items() if x["kind"] == "proposed" and x["piece_nodes"] == 2)
    assert w[far]["next_to"] == [] and w[far]["parts"] == 1 and w[far]["piece_population"] == 3000
