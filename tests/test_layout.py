"""Sewer layout from roads (user decision 12-Oct-2026: roads from KML / Google Earth or DXF centrelines; any network
made here is a PFR)."""
import collections
import csv
import glob
import json
import math
import os

from sewer_app import layout, network, pipeline
from sewer_app.__main__ import main

from synthetic import INP


def grid_roads():
    """3 east-west and 3 north-south roads, 200 m long, crossing WITHOUT a vertex at the crossings; one more road
    ending 0.6 m short of the middle east-west road (T-junction); the first road drawn twice (overlap)."""
    lines = [[(0.0, y), (200.0, y)] for y in (0.0, 100.0, 200.0)]
    lines += [[(x, 0.0), (x, 200.0)] for x in (0.0, 100.0, 200.0)]
    lines.append([(50.0, 0.6), (50.0, -80.0)])           # short of y = 0 by 0.6 m
    lines.append([(0.0, 0.0), (200.0, 0.0)])               # duplicate
    return lines


def test_road_graph():
    nodes, edges = layout.road_graph(grid_roads(), snap=1.0, max_spacing=30.0)
    total = sum(L for *_, L in edges)
    assert abs(total - (6 * 200.0 + 80.0)) < 1.0            # duplicate dropped, T-road joined (80 m + 0.6 m snapped)
    assert all(L <= 30.0 + 1e-9 for *_, L in edges)
    deg = collections.Counter()
    for a, b, _, _ in edges:
        deg[a] += 1
        deg[b] += 1
    at = {xy: k for k, xy in nodes.items()}
    centre = min(nodes, key=lambda k: math.dist(nodes[k], (100.0, 100.0)))
    assert math.dist(nodes[centre], (100.0, 100.0)) < 1e-6 and deg[centre] == 4      # crossing became a junction
    tee = min(nodes, key=lambda k: math.dist(nodes[k], (50.0, 0.0)))
    assert math.dist(nodes[tee], (50.0, 0.0)) < 1e-6 and deg[tee] == 3                # T-road joined
    assert at                                                                         # nodes exist


def test_boundary_and_spot_levels():
    box = [(-10.0, -10.0), (110.0, -10.0), (110.0, 110.0), (-10.0, 110.0)]
    nodes, edges = layout.road_graph(grid_roads(), boundary=box)
    assert all(-10 - 1e-9 <= x <= 110 + 1e-9 and -10 - 1e-9 <= y <= 110 + 1e-9 for x, y in nodes.values())
    f = layout.gl_from_spots([(0, 0, 100.0), (300, 0, 97.0), (0, 300, 100.0), (300, 300, 97.0)])
    assert abs(f(150.0, 50.0) - 98.5) < 1e-9                  # plane falling 1 m per 100 m eastwards
    net = layout.make_network(nodes, edges, f, "test spots")
    assert all(v["gl_source"].startswith(layout.PFR_TAG) for v in net["nodes"].values())


def test_sample_kml(tmp_path, capsys):
    """The sample KML of samples/ (tools/make_sample_kml.py): roads, boundary, wards with population, spot levels and
    the STP in one file - layout reads every part of it."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    k = os.path.join(here, "samples", "sample_area.kml")
    out = str(tmp_path / "out")
    main(["layout", "--roads-kml", k, "--boundary-kml", k, "--population-kml", k, "--levels-kml", k, "--out", out])
    text = capsys.readouterr().out
    assert "16 spot levels" in text and "point 'STP' -> nearest manhole" in text
    with open(os.path.join(out, "sample_area_layout_population.csv"), encoding="utf-8") as fh:
        assert abs(sum(float(r["Population"]) for r in csv.DictReader(fh)) - 9000.0) < 1.0   # 5,200 + 3,800
    net = network.read_extract_csv(os.path.join(out, "sample_area_layout_manholes.csv"),
                                   os.path.join(out, "sample_area_layout_conduits.csv"))
    gls = [v["ground"] for v in net["nodes"].values()]
    assert all(g is not None for g in gls) and 80.4 < min(gls) < max(gls) < 83.4         # the sample's 80.6 - 83.2 m

    # the road grid has loops: a zoning option cuts them, and the new head manholes <MH>-C<n> (not in the population
    # file) get their share of their manhole's population - no cut sewer without flow, total unchanged
    from sewer_app import flows, zoning
    f_pop = os.path.join(out, "sample_area_layout_population.csv")
    inp = dict(INP, pop_dist="csv", pop_csv=f_pop, pop_total=9000)
    z = zoning.run(net, inp, log=lambda s: None)
    assert abs(sum(z["pop_node"].values()) - 9000.0) < 1.0                     # zoning reads the same file
    for ev in z["rank"]:                                   # zoning too: cut sewers carry their share, total kept
        assert ev["cuts"] and all(d["q"] > 0 for d in ev["res"].values())
        assert abs(sum(ev["zone_pop"].values()) - 9000.0) < 1.0
    net2, cuts = zoning.apply_option(net, z["rank"][0])
    assert cuts
    run = pipeline.run(net2, inp, log=lambda s: None)
    assert all(f["Q"] > 0 for f in run["flows"].values())
    pop = flows.distribute_population(0, "csv", {"conduits": []}, [], f_pop)
    at_outlets = sum(f["P"] for f in run["flows"].values() if f["to"] in net2["outfalls"])
    assert abs(at_outlets + sum(pop.get(o, 0.0) for o in net2["outfalls"]) - 9000.0) < 1.0


def kml(path, body):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write('<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
                 + body + "</Document></kml>")


def test_layout_from_kml_to_design(tmp_path):
    lon0, lat0, d = 83.00, 25.30, 0.001                       # ~100 m steps near Springfield
    roads = "".join(f"<Placemark><name>r{i}</name><LineString><coordinates>{lon0},{lat0 + i * d} "
                    f"{lon0 + 3 * d},{lat0 + i * d}</coordinates></LineString></Placemark>" for i in range(3))
    roads += "".join(f"<Placemark><name>c{i}</name><LineString><coordinates>{lon0 + i * d},{lat0} "
                     f"{lon0 + i * d},{lat0 + 2 * d}</coordinates></LineString></Placemark>" for i in range(4))
    kml(str(tmp_path / "roads.kml"), roads)
    poly = (f"{lon0 - d / 2},{lat0 - d / 2} {lon0 + 3.5 * d},{lat0 - d / 2} {lon0 + 3.5 * d},{lat0 + 2.5 * d} "
            f"{lon0 - d / 2},{lat0 + 2.5 * d} {lon0 - d / 2},{lat0 - d / 2}")
    kml(str(tmp_path / "pop.kml"), f"<Placemark><name>ward 1</name><ExtendedData><Data name=\"Population\">"
                                   f"<value>12,000</value></Data></ExtendedData><Polygon><outerBoundaryIs><LinearRing>"
                                   f"<coordinates>{poly}</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>")
    out = str(tmp_path / "out")
    main(["layout", "--roads-kml", str(tmp_path / "roads.kml"), "--boundary-kml", str(tmp_path / "pop.kml"),
          "--population-kml", str(tmp_path / "pop.kml"), "--flat-gl", "80.0", "--out", out])
    f_mh, f_co = os.path.join(out, "roads_layout_manholes.csv"), os.path.join(out, "roads_layout_conduits.csv")
    f_pop = os.path.join(out, "roads_layout_population.csv")
    assert os.path.isfile(os.path.join(out, "roads_layout.dxf"))
    with open(f_pop, encoding="utf-8") as fh:
        assert abs(sum(float(r["Population"]) for r in csv.DictReader(fh)) - 12000.0) < 0.5   # 2-decimal rounding
    net = network.read_extract_csv(f_mh, f_co)
    x0 = min(v["xy"][0] for v in net["nodes"].values())
    assert 680000 < x0 < 720000                               # UTM 44N metres, as the Springfield drawings
    inp = dict(INP, pop_dist="csv", pop_csv=f_pop, pop_total=12000)
    with open(tmp_path / "inp.json", "w", encoding="utf-8") as fh:
        json.dump(inp, fh)
    low = min(net["nodes"], key=lambda n: (net["nodes"][n]["xy"][0] + net["nodes"][n]["xy"][1]))
    main(["design", "--csv", f_mh, f_co, "--inputs", str(tmp_path / "inp.json"), "--outfall", low, "--out", out])
    assert glob.glob(os.path.join(out, "roads_layout_sewer_design_*_PFR.xlsx"))       # always a PFR
    run = pipeline.run(dict(net, outfalls=[low]), inp, log=lambda s: None)
    assert run["grade"] == "PFR"


def test_boundary_far_from_the_roads(tmp_path):
    """A boundary polygon that holds none of the roads (a ward taken as the boundary): a clear message, not a crash."""
    import pytest
    lon0, lat0, d = 83.00, 25.30, 0.001
    roads = "".join(f"<Placemark><name>r{i}</name><LineString><coordinates>{lon0},{lat0 + i * d} "
                    f"{lon0 + 3 * d},{lat0 + i * d}</coordinates></LineString></Placemark>" for i in range(3))
    far = f"{lon0 + 0.05},{lat0} {lon0 + 0.06},{lat0} {lon0 + 0.06},{lat0 + 0.01} {lon0 + 0.05},{lat0}"
    kml(str(tmp_path / "r.kml"), roads + f"<Placemark><name>Project boundary</name><Polygon><outerBoundaryIs><LinearRing>"
                                        f"<coordinates>{far}</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>")
    with pytest.raises(SystemExit) as e:
        main(["layout", "--roads-kml", str(tmp_path / "r.kml"), "--boundary-kml", str(tmp_path / "r.kml"),
              "--flat-gl", "80", "--out", str(tmp_path / "out")])
    assert "boundary" in str(e.value) and "km" in str(e.value)


def test_wards_together_as_the_boundary():
    """No project boundary, each ward its own polygon: the wards together are the boundary - a road through two
    wards is kept whole although a 1 m gap lies between the two polygons; a road outside every ward is left out."""
    w1 = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)]
    w2 = [(101.0, 0.0), (200.0, 0.0), (200.0, 100.0), (101.0, 100.0)]             # 1 m gap at x = 100 .. 101
    roads = [[(10.0, 50.0), (190.0, 50.0)], [(10.0, 300.0), (190.0, 300.0)]]      # through both wards / outside
    nodes, edges = layout.road_graph(roads, boundary=[w1, w2])
    assert abs(sum(L for *_, L in edges) - 180.0) < 0.5                        # the first road, whole
    assert all(p[1] < 200 for p in nodes.values())
    adj = collections.defaultdict(set)
    for a, b, *_ in edges:
        adj[a].add(b)
        adj[b].add(a)
    seen, stack = set(), [next(iter(adj))]
    while stack:
        n = stack.pop()
        if n not in seen:
            seen.add(n)
            stack += list(adj[n])
    assert seen == set(adj)                                                     # one connected road


def test_population_from_a_description_table(tmp_path):
    """GIS exports (ArcGIS ...) keep the fields in a description table: W_POP is read as the population."""
    from sewer_app import geo
    desc = ("<html><body><table><tr><td>Sarsouli</td></tr><tr><td><table><tr><td>W_Name</td><td>Sarsouli</td></tr>"
            "<tr bgcolor='#D4E4F3'><td>W_POP</td><td>12508</td></tr></table></td></tr></table></body></html>")
    p = tmp_path / "w.kml"
    p.write_text('<?xml version="1.0"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark>'
                 f'<name>Sarsouli</name><description><![CDATA[{desc}]]></description><Polygon><outerBoundaryIs>'
                 '<LinearRing><coordinates>82.96,25.35 82.97,25.35 82.97,25.36 82.96,25.35</coordinates></LinearRing>'
                 '</outerBoundaryIs></Polygon></Placemark></Document></kml>', encoding="utf-8")
    data = geo.read_kml(str(p))["polygons"][0]["data"]
    assert data["W_POP"] == "12508" and data["W_Name"] == "Sarsouli"
    assert "w_pop" in geo.POP_KEYS


def test_a_manhole_at_every_bend():
    """CPHEEO: sewers straight between manholes - a bend of the road is a manhole, a wobble within
    STRAIGHT_TOL_M is not; every sewer is one straight piece."""
    road = [(0, 0), (20, 0), (20, 20), (40, 20.4), (60, 20)]      # bend at (20,0) and (20,20), a wobble at (40,20.4)
    nodes, edges = layout.road_graph([road], snap=1, max_spacing=30)
    xy = set(nodes.values())
    assert (20, 0) in xy and (20, 20) in xy
    assert not any(abs(x - 40) < 1e-6 and abs(y - 20.4) < 1e-6 for x, y in xy)
    assert all(len(pts) == 2 for _, _, pts, _ in edges)
    assert len(edges) == 4                                         # 20 + 20 + 40 m (two 20 m pieces)
