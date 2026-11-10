"""Water zoning: OZ per OHT by the nearest pipe path, OZ limits (population, existing OHT capacity) moving the border,
DMAs of 500-3000 connections each with one inlet, boundary pipes to close, CWR rule, flags."""
import itertools
import math

from water_app import demand as dm
from water_app import hydraulics as hy
from water_app import zoning as wz
from water_app.design import load_criteria


def grid(n=12, pop=400.0, spacing=100.0, elev=lambda i, j: 80.0):
    nodes, pipes = {}, {}
    for i, j in itertools.product(range(n), range(n)):
        nodes[(i, j)] = {"xy": (j * spacing, i * spacing), "elev": elev(i, j), "pop": pop}
    for i, j in itertools.product(range(n), range(n)):
        if i + 1 < n:
            pipes[f"v{i}_{j}"] = {"a": (i, j), "b": (i + 1, j), "length": spacing}
        if j + 1 < n:
            pipes[f"h{i}_{j}"] = {"a": (i, j), "b": (i, j + 1), "length": spacing}
    return {"nodes": nodes, "pipes": pipes}


def connected(net, members):
    members = set(members)
    start = next(iter(members))
    seen, stack = {start}, [start]
    while stack:
        u = stack.pop()
        for p in net["pipes"].values():
            for a, b in ((p["a"], p["b"]), (p["b"], p["a"])):
                if a == u and b in members and b not in seen:
                    seen.add(b)
                    stack.append(b)
    return seen == members


def test_nearest_oht_and_new_oht_sizing():
    crit = load_criteria()
    net = grid(n=8, pop=300)
    z = wz.make_zones(net, [{"name": "A", "node": (0, 0)}, {"name": "B", "node": (7, 7)}], crit)
    assert z["oz"][(1, 1)] == "A" and z["oz"][(6, 6)] == "B"
    assert not z["unserved"] and z["moved"] == 0
    a = next(x for x in z["zones"] if x["name"] == "A")
    kl = sum(dm.daily_kl(300, crit, 64 * 300)["total"] for n, k in z["oz"].items() if k == "A")
    assert a["demand_kld"] == round(kl, 1)
    assert a["required_kl"] >= 0.33 * kl and a["required_kl"] % 50 == 0 and a["required_kl"] - 0.33 * kl < 50
    assert not a["existing"] and a["cwr_kl"] is None


def test_storage_mass_balance_or_33_percent():
    """CPHEEO Table 2.7 S.No.12 p175: mass balance or 33 % of the ultimate demand, not less than 33 % (user decision
    26-Oct-2026: the larger). Elmwood draw-off pattern: 16 h filling 18.3 % -> 33 %; 8 h (4-8, 16-20) 38.5 %."""
    crit = load_criteria()
    mb = dm.mass_balance(crit)
    assert mb["hours"] == 16 and round(mb["share"] * 100, 1) == 18.3 and dm.storage_share(crit) == 0.33
    assert round(mb["excess"], 2) == 3.05 and round(mb["deficit"], 2) == -1.35 and abs(mb["rows"][-1]["diff"]) < 1e-9
    assert round(dm.mass_balance(crit, [[0, 24]])["share"] * 100, 1) == 29.6
    eight = dm.parse_windows("4-8, 16-20")
    assert round(dm.storage_share(crit, eight) * 100, 1) == 38.5
    assert round(dm.storage_share(crit, dm.parse_windows("22-6")) * 100, 1) == 95.0      # past midnight
    for bad in ("", "5", "5-5", "5-30"):
        try:
            dm.parse_windows(bad)
            assert False, bad
        except ValueError:
            pass
    # the zoning sizes a new OHT on it
    net = grid(n=8, pop=300)
    crit8 = dict(crit, oht_inflow_hours=dict(crit["oht_inflow_hours"], value=eight))
    a = next(x for x in wz.make_zones(net, [{"name": "A", "node": (0, 0)}], crit8)["zones"] if x["name"] == "A")
    share = dm.storage_share(crit8)
    # balancing on the demand without fire + one third of the fire (CPHEEO S.No.13, user decision 30-Oct-2026)
    need = share * (a["demand_kld"] - a["fire_kld"]) + a["fire_kld"] / 3
    assert a["fire_kld"] > 0 and a["required_kl"] >= need - 0.1 and a["required_kl"] - need < 50.1
    assert a["balancing_kl"] == round(share * (a["demand_kld"] - a["fire_kld"]), 1)
    assert abs(a["fire_store_kl"] - a["fire_kld"] / 3) < 0.1


def test_small_existing_oht_gives_nodes_to_its_neighbour():
    crit = load_criteria()
    net = grid(n=10, pop=300)
    total_kl = sum(dm.daily_kl(300, crit, 100 * 300)["total"] for _ in range(100))
    cap_a = 0.33 * total_kl * 0.25                                  # A can serve only a quarter of the town
    z = wz.make_zones(net, [{"name": "A", "node": (0, 0), "capacity_kl": cap_a},
                            {"name": "B", "node": (9, 9)}], crit)
    a = next(x for x in z["zones"] if x["name"] == "A")
    assert z["moved"] > 0
    assert a["demand_kld"] <= cap_a / 0.33 + 1e-6
    assert not [f for f in z["flags"] if f["level"] == "error"]
    for k in ("A", "B"):                                            # each OZ still one connected piece
        assert connected(net, [n for n, o in z["oz"].items() if o == k])


def test_no_room_anywhere_is_an_error():
    crit = load_criteria()
    net = grid(n=6, pop=3000)                                       # 108,000 people, two OHTs of 50,000
    z = wz.make_zones(net, [{"name": "A", "node": (0, 0)}, {"name": "B", "node": (5, 5)}], crit)
    assert any(f["level"] == "error" and "population" in f["text"] for f in z["flags"])


def test_dmas_one_inlet_each_and_closed_boundaries_keep_supply():
    crit = load_criteria()
    net = grid(n=12, pop=150)                                       # 144 x 150 = 21,600 people = 3600 connections
    z = wz.make_zones(net, [{"name": "A", "node": (0, 0)}], crit)
    oz = z["zones"][0]
    assert oz["connections"] == math.ceil(21600 / 6) and oz["dma_count"] == 2
    names = {d["name"] for d in z["dmas"]}
    assert names == {"A/DMA-1", "A/DMA-2"}
    for d in z["dmas"]:
        members = [n for n, k in z["dma"].items() if k == d["name"]]
        assert connected(net, members)
        assert 500 <= d["connections"] <= 3000 * 1.05
    assert sum(1 for d in z["dmas"] if d["inlet_pipe"] is not None) == 1
    # close the boundary pipes: the DMAs are discrete but every node is still fed from the OHT
    for pid in z["closed_pipes"]:
        net["pipes"][pid]["closed"] = True
    hnet = {"nodes": {n: {"elev": 80.0, "demand": 0.1, "head": 100.0 if n == (0, 0) else None} for n in net["nodes"]},
            "pipes": {pid: dict(p, d_mm=150, C=140) for pid, p in net["pipes"].items()}}
    assert not hy.solve(hnet)["unsupplied"]
    crossing = [pid for pid, p in net["pipes"].items() if not p.get("closed")
                and z["dma"][p["a"]] != z["dma"][p["b"]]]
    assert len(crossing) == 1                                        # the one inlet of DMA-2


def test_cwr_rule_and_slope_flag():
    crit = load_criteria()
    net = grid(n=6, pop=1000, elev=lambda i, j: 80.0 + 1.5 * i)     # 7.5 m rise across the OZ; 36,000 persons
    z = wz.make_zones(net, [{"name": "A", "node": (0, 0), "capacity_kl": 1000, "tubewells": 1}], crit)
    assert z["zones"][0]["tubewells_new"] == 4
    assert z["zones"][0]["cwr_kl"] == 250                            # 25 % of 1000 KL (more than 3 new tube wells)
    z3 = wz.make_zones(net, [{"name": "A", "node": (0, 0), "capacity_kl": 1000, "tubewells": 2}], crit)
    assert z3["zones"][0]["tubewells_new"] == 3 and z3["zones"][0]["cwr_kl"] is None    # 2 + 3 = 5, but 3 new
    f = next(f for f in z["flags"] if f["level"] == "warn" and "ground varies" in f["text"])
    # the two junctions it is between, with their GL (user request 30-Oct-2026)
    assert f["low"] == (0, 0) and f["high"][0] == 5 and "lowest (0, 0) GL 80.00 m, highest" in f["text"]
    assert "सबसे नीचा (0, 0) GL 80.00 m, सबसे ऊँचा" in f["hi"]


def test_plan_proposes_new_ohts_for_what_the_old_ones_cannot_serve():
    """An existing OHT of a quarter of the town's need: it keeps the nearest part it can serve, the rest gets a new
    OHT (sized at 33 % of its OZ) - no zone above its capacity."""
    crit = load_criteria()
    net = grid(n=12, pop=200, elev=lambda i, j: 80.0 + 0.1 * j)
    total_kl = sum(dm.daily_kl(200, crit, 144 * 200)["total"] for _ in range(144))
    cap = round(0.33 * total_kl * 0.3)
    z = wz.plan(net, [{"name": "OLD-1", "node": (0, 0), "capacity_kl": cap, "staging_m": 20}], crit)
    assert len(z["proposed"]) == 1
    new = z["proposed"][0]
    assert new["capacity_kl"] is None and new["name"] == "Prop-OHT-1"
    old = next(x for x in z["zones"] if x["name"] == "OLD-1")
    assert old["demand_kld"] <= cap / 0.33 + 1e-6
    assert not [f for f in z["flags"] if f["level"] == "error"]
    nz = next(x for x in z["zones"] if x["name"] == "Prop-OHT-1")
    assert nz["required_kl"] >= 0.33 * nz["demand_kld"] and old["population"] + nz["population"] == 144 * 200
    assert z["oz"][(11, 11)] == "Prop-OHT-1" and z["oz"][(0, 0)] == "OLD-1"


def test_plan_without_any_oht_proposes_all_of_them():
    crit = load_criteria()
    net = grid(n=20, pop=300)                                       # 120,000 people
    z = wz.plan(net, [], crit)
    assert len(z["proposed"]) == 3                                  # ceil(120,000 / (0.95 x 50,000))
    assert all(x["population"] <= 50000 for x in z["zones"])
    assert sum(x["population"] for x in z["zones"]) == 120000
    assert not z["unserved"] and not [f for f in z["flags"] if f["level"] == "error"]
    for x in z["zones"]:
        assert connected(net, [n for n, o in z["oz"].items() if o == x["name"]])


def test_plan_gives_ground_too_high_for_an_existing_oht_to_a_new_one():
    """An existing OHT (staging 18 m, GL 80: 17 m only up to GL ~81) set to give its higher ground to a new OHT: a
    high area of a DMA or more gets a new OHT, a high node the water passes through to lower ground beyond stays, a
    high piece too small for an OHT stays (flagged); a node the design left below 17 m (bar) goes too. By default
    (VFD at its outlet, CPHEEO Table 2.7 S.No.10) it keeps all of it."""
    crit = load_criteria()
    net = grid(n=12, pop=300, elev=lambda i, j: 82.0 if j == 5 else 78.0)
    net["nodes"][(0, 0)]["elev"] = 80.0
    prev = (0, 11)
    for k in range(6):                                                 # a high branch off the corner: 300 connections
        net["nodes"][("s", k)] = {"xy": (1100 + 100 * (k + 1), 0.0), "elev": 85.0, "pop": 300.0}
        net["pipes"][f"s{k}"] = {"a": prev, "b": ("s", k), "length": 100.0}
        prev = ("s", k)
    old = {"name": "OLD", "node": (0, 0), "capacity_kl": 5000, "staging_m": 18.0, "tubewells": 0, "low_head": "new_oht"}
    z = wz.plan(net, [old], crit)
    assert all(z["oz"][(i, j)] == "OLD" for i in range(12) for j in range(12) if j != 5)
    assert z["oz"][(0, 5)] == "OLD"                                    # the water to j > 5 passes through it
    strip = {z["oz"][(i, 5)] for i in range(1, 12)}                    # 550 connections, not needed: a new OHT
    assert len(strip) == 1 and next(iter(strip)).startswith("Prop-OHT-")
    assert all(z["oz"][("s", k)] == "OLD" for k in range(6))           # too small for an OHT: stays, flagged
    assert z["too_high"]["OLD"]["to"] and any("too high" in f["text"] and "stay" in f["text"] for f in z["flags"])
    zb = wz.plan(net, [old], crit, bar={"OLD": {(11, 11)}})           # the design: below 17 m - no pipe helps
    assert zb["oz"][(11, 10)] == "OLD"
    assert zb["too_high"]["OLD"]["nodes"] > z["too_high"]["OLD"]["nodes"]
    # default: a VFD pump at its outlet - the OZ is what its capacity serves
    zv = wz.plan(net, [dict(old, low_head="vfd")], crit)
    assert set(zv["oz"].values()) == {"OLD"} and not zv["proposed"]
    assert any("VFD" in f["text"] for f in zv["flags"])


def test_oz_above_capacity_gives_whole_branches_to_a_neighbour():
    """OZs as given (assign) with the existing OHT's far above its capacity: it gives branches (subtrees hanging on
    its border nodes, not only leaves) to the neighbour with room until within its capacity; both stay connected."""
    crit = load_criteria()
    net = grid(n=10, pop=300)
    assign = {n: ("A" if n[1] < 9 else "B") for n in net["nodes"]}               # B: only the last column
    city = 100 * 300
    kl_a = sum(dm.daily_kl(300, crit, city)["total"] for n, k in assign.items() if k == "A")
    cap = round(0.6 * kl_a * 0.33)                                               # room for 60 % of what A has
    z = wz.make_zones(net, [{"name": "A", "node": (0, 0), "capacity_kl": cap}, {"name": "B", "node": (9, 9)}], crit,
                      city, assign=assign)
    a = next(x for x in z["zones"] if x["name"] == "A")
    assert a["demand_kld"] <= cap / 0.33 + 1e-6 and a["demand_kld"] >= 0.8 * cap / 0.33      # not much given away
    assert not any(f["level"] == "error" for f in z["flags"]) and z["moved"] > 0
    for k in ("A", "B"):
        assert connected(net, [n for n, kk in z["oz"].items() if kk == k])


def comb(teeth=60, tooth=15, pop=300.0, spacing=50.0):
    """A spine with long side streets (teeth) on both sides - like a town along a main road."""
    nodes, pipes = {}, {}
    for i in range(teeth):
        nodes[("s", i)] = {"xy": (i * spacing, 0.0), "elev": 80.0, "pop": pop}
        if i:
            pipes[f"s{i}"] = {"a": ("s", i - 1), "b": ("s", i), "length": spacing}
        side = 1 if i % 2 else -1
        prev = ("s", i)
        for j in range(1, tooth + 1):
            nodes[("t", i, j)] = {"xy": (i * spacing, side * j * spacing), "elev": 80.0, "pop": pop}
            pipes[f"t{i}_{j}"] = {"a": prev, "b": ("t", i, j), "length": spacing}
            prev = ("t", i, j)
    return {"nodes": nodes, "pipes": pipes}


def test_plan_parts_equal_and_within_50000():
    """User report 21-Oct-2026 (network_utm): proposed OZs of 69,074 and 68,397 beside one of 12,063 - the parts grown
    from far-apart seeds left the middle over, given in whole pieces to full neighbours (here: 78,750), and gave more
    OHTs than needed (a 40 x 40 grid: 18 for 14). Now: halved along the pipes, about equal."""
    crit = load_criteria()
    for net, total in ((comb(teeth=120, tooth=20, pop=250.0), 630000), (grid(n=40, pop=400.0), 640000)):
        z = wz.plan(net, [], crit)
        pops = [x["population"] for x in z["zones"]]
        assert len(pops) == 14 and sum(pops) == total                  # ceil(total / 47,500)
        assert max(pops) <= 50000 and min(pops) >= 0.85 * total / 14   # about equal
        assert not z["unserved"] and not [f for f in z["flags"] if f["level"] == "error"]
        for x in z["zones"]:
            assert connected(net, [n for n, o in z["oz"].items() if o == x["name"]])


def test_cwr_counts_the_new_tube_wells():
    """UPJN CWR rule on the NEW tube wells that fill the OHT: those the +15 years demand of the pumping main needs
    beyond the ones given on the map (as sheet TW of the DPR; user, 26-Oct-2026); the existing ones stay with the
    existing structures, not counted (user decision 27-Oct-2026)."""
    crit = load_criteria()
    # 1500 LPM x 16 h = 1440 KLD a tube well; pumping main = (150 + 0.1 x 45) x 1.11 = 171.5 L a person
    assert dm.tubewells_new(25674, crit) == 4 and dm.tubewells_new(24961, crit) == 3
    assert dm.tubewells_new(3365, crit, existing=1) == 0                     # 1152 KLD of the existing one is enough
    net = grid(n=8, pop=500)                                                  # 32,000 persons, no tube well given
    z = wz.make_zones(net, [{"name": "A", "node": (0, 0)}], crit)["zones"][0]
    assert z["tubewells"] == 0 and z["tubewells_new"] == dm.tubewells_new(32000, crit) > 3
    assert z["cwr_kl"] == math.ceil(0.25 * z["required_kl"] / 50) * 50
    # with the +15 years population of the page (here half): fewer new tube wells, no CWR
    half = dict(crit, stage_mid_share={"value": 0.5})
    z2 = wz.make_zones(net, [{"name": "A", "node": (0, 0)}], half)["zones"][0]
    assert z2["tubewells_new"] == dm.tubewells_new(16000, crit) <= 3 and z2["cwr_kl"] is None
    # 2 given + 3 new = 5 fill the OHT, but only 3 new: no CWR; 1 given + 4 new: a CWR
    z3 = wz.make_zones(net, [{"name": "A", "node": (0, 0), "tubewells": 2}], crit)["zones"][0]
    assert z3["tubewells"] == 2 and z3["tubewells_new"] == 3 and z3["cwr_kl"] is None
    z4 = wz.make_zones(net, [{"name": "A", "node": (0, 0), "tubewells": 1}], crit)["zones"][0]
    assert z4["tubewells_new"] == 4 and z4["cwr_kl"] is not None
    # standby tube wells as CPHEEO 5.7.5 (user decision 7-Nov-2026): 3 working + 2, 4 + 2; the CWR rule counts the
    # working ones; a rebored tube well gives as an existing one (1 + 1 rebored = 2 existing: 3 new, no CWR)
    assert (z3["tubewells_standby"], z4["tubewells_standby"]) == (2, 2)
    assert [dm.standby(w, crit) for w in (0, 1, 2, 3, 5, 6, 10, 12)] == [0, 1, 1, 2, 2, 3, 3, 3]
    z5 = wz.make_zones(net, [{"name": "A", "node": (0, 0), "tubewells": 1, "rebore": 1}], crit)["zones"][0]
    assert z5["rebore"] == 1 and z5["tubewells_new"] == 3 and z5["cwr_kl"] is None
