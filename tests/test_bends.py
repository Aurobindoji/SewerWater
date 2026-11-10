"""Manholes at bends and for the spacing (user decisions 20-Oct-2026, CPHEEO 3.71 p3-125 'additional manholes at
changes of directions', 3.71.1 p3-126 30 m): a manhole at every bend of 20 deg or more, then the straight stretches
divided for the spacing - put into the network before zoning and design (spacing.presplit), so that the design takes
every manhole."""
from sewer_app import spacing
from sewer_app.criteria import Rules, load_criteria


def test_bends_of_a_polyline():
    assert spacing.bends([(0, 0), (20, 0), (20, 20)], 10) == [(20.0, 90.0)]
    assert spacing.bends([(0, 0), (10, 0.5), (20, 0)], 10) == []                 # a wobble within 1 m: no bend
    five = [(0, 0), (20, 0), (40, 40 * 0.0875)]                                   # 5 deg (3.5 m off the line)
    assert spacing.bends(five, 10) == [] and len(spacing.bends(five, 4)) == 1
    assert spacing.bends([(0, 0), (1.5, 0), (1.5, 20)], 10) == []                 # 1.5 m from the manhole
    assert spacing.bends([(0, 0), (20, 0), (20, 20)], None) == []                 # switched off
    two = spacing.bends([(0, 0), (20, 0), (21, 1), (21, 20)], 10)                 # two bends 1.4 m apart: one
    assert len(two) == 1


def leg(deg, L=40.0):
    """Two straight legs of L m with a turn of deg at the joint."""
    import math
    return [(0.0, 0.0), (L, 0.0), (L + L * math.cos(math.radians(deg)), L * math.sin(math.radians(deg)))]


def test_twenty_degrees_or_more():
    crit = load_criteria()
    assert crit["sewer"]["bend_manhole_min_angle_deg"]["value"] == 20
    assert [spacing.bend_angle(crit, D) for D in (200, 600, 1200)] == [20, 20, 20]
    assert spacing.bends(leg(19.5), 20) == [] and [round(t) for _, t in spacing.bends(leg(20.0), 20)] == [20]
    by = {"sewer": dict(crit["sewer"], bend_manhole_min_angle_deg={"value": {"300": 5, "750": 3}})}   # by size
    assert [spacing.bend_angle(by, D) for D in (200, 450, 1200)] == [5, 3, 3]
    assert spacing.bend_angle({"sewer": dict(crit["sewer"], bend_manhole_min_angle_deg={"value": None})}, 200) is None


def net_of(conds, gl=None):
    nodes = {}
    for lab, a, b, pts in conds:
        nodes.setdefault(a, {"xy": pts[0], "ground": (gl or {}).get(a)})
        nodes.setdefault(b, {"xy": pts[-1], "ground": (gl or {}).get(b)})
    return {"nodes": nodes, "outfalls": ["MH-9"],
            "conduits": [{"label": lab, "start_node": a, "stop_node": b, "vertices": [list(p) for p in pts],
                          "length_m": sum(((q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2) ** 0.5 for p, q in zip(pts, pts[1:])),
                          "force_D": 300} for lab, a, b, pts in conds]}


def test_presplit_names_ground_and_pieces():
    crit = load_criteria()
    poly = [(0.0, 0.0), (20.0, 0.0), (20.0, 50.0)]                    # 20 m, a 90 deg bend, 50 m
    net = net_of([("CO-1", "MH-1", "MH-9", poly)], {"MH-1": 80.0, "MH-9": 79.3})
    out, rows = spacing.presplit(net, crit)
    assert [(r["label"], r["why"]) for r in rows] == [("MH-1-1", "bend 90 deg"), ("MH-1-2", "spacing")]
    assert out["nodes"]["MH-1-1"]["xy"] == (20.0, 0.0) and abs(out["nodes"]["MH-1-1"]["ground"] - (80.0 - 0.7 * 20 / 70)) < 1e-9
    assert "interpolated along the sewer" in out["nodes"]["MH-1-2"]["gl_source"]
    co = out["conduits"]
    assert [(k["label"], k["start_node"], k["stop_node"], round(k["length_m"], 3)) for k in co] == [
        ("CO-1", "MH-1", "MH-1-1", 20.0), ("CO-1-2", "MH-1-1", "MH-1-2", 25.0), ("CO-1-3", "MH-1-2", "MH-9", 25.0)]
    assert all(k["force_D"] == 300 and k["piece_of"] == "CO-1" for k in co)       # the table edits go to every piece
    assert net["conduits"][0]["label"] == "CO-1" and len(net["nodes"]) == 2      # the network given is not changed
    # the same network again: the same names (edits of a new manhole / piece keep their place)
    assert [r["label"] for r in spacing.presplit(net, crit)[1]] == ["MH-1-1", "MH-1-2"]
    # a trunk sewer: its spacing waits for the design (Table 3.31 by diameter) - only the bend now
    trunk = {"sewer": dict(crit["sewer"], trunk_conduits={"value": ["CO-1"]})}
    assert [r["why"] for r in spacing.presplit(net, trunk)[1]] == ["bend 90 deg"]
    # a straight conduit within the spacing: unchanged
    short = net_of([("CO-2", "MH-2", "MH-9", [(0, 0), (29, 0)])])
    assert spacing.presplit(short, crit)[1] == [] and spacing.presplit(short, crit)[0]["conduits"][0]["label"] == "CO-2"


def test_planned_after_the_design():
    """plan_new_manholes (after the design) still plans what it is given - with presplit before it, only trunk
    sewers are left to it."""
    crit = load_criteria()
    d = {"D": 200, "length": 70.0, "from": "A", "to": "B", "rev": False, "g_up": 80.0, "g_dn": 79.3, "up": 78.0,
         "slope": 0.004}
    poly = [(0.0, 0.0), (20.0, 0.0), (20.0, 50.0)]
    rows = spacing.plan_new_manholes({"CO-1": d}, crit, Rules(crit), {"CO-1": poly}, {})
    assert [(round(r["chainage"], 3), r["why"]) for r in rows] == [(20.0, "bend 90 deg"), (45.0, "spacing")]
    assert abs(rows[0]["invert"] - (78.0 - 0.004 * 20)) < 1e-9
    rows_r = spacing.plan_new_manholes({"CO-1": dict(d, rev=True)}, crit, Rules(crit), {"CO-1": poly[::-1]}, {})
    assert [(round(r["chainage"], 3), r["why"]) for r in rows_r] == [(20.0, "bend 90 deg"), (45.0, "spacing")]
    # a conduit presplit has already looked at: its bends are not looked for again after the design
    after = spacing.plan_new_manholes({"CO-1": d}, crit, Rules(crit), {"CO-1": poly}, {}, checked={"CO-1"})
    assert [r["why"] for r in after] == ["spacing", "spacing"]               # 70 m: the spacing only, no bend
    again = spacing.plan_new_manholes({"CO-1": dict(d, length=25.0)}, crit, Rules(crit), {"CO-1": [(0, 0), (12.5, 0), (12.5, 12.5)]},
                                      {}, checked={"CO-1"})
    assert again == []


def test_bend_angle_from_the_page():
    """The page's 'मोड़ पर manhole (इतने ° या ज़्यादा)' (default 20) reaches presplit; outside 1 - 90 deg: refused."""
    import pytest
    from sewer_app import ui
    assert ui.criteria_for()["sewer"]["bend_manhole_min_angle_deg"]["value"] == 20
    c45 = ui.criteria_for(bend_angle=45)
    assert c45["sewer"]["bend_manhole_min_angle_deg"]["value"] == 45.0
    assert "user input in the map UI" in c45["sewer"]["bend_manhole_min_angle_deg"]["note"]
    for deg, n in ((30, 0), (50, 1)):
        net = net_of([("CO-1", "MH-1", "MH-9", leg(deg, 14.0))])                 # 28 m: no spacing manhole
        assert len(spacing.presplit(net, c45)[1]) == n, deg
    assert len(spacing.presplit(net_of([("CO-1", "MH-1", "MH-9", leg(30, 14.0))]), ui.criteria_for())[1]) == 1
    for bad in (0, 95):
        with pytest.raises(ValueError):
            ui.criteria_for(bend_angle=bad)
