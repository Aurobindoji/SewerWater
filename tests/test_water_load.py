"""Water load options and the simulation (user request 16-Nov-2026): how the population is put on the junctions, the
peak factor of the page, the load cases and the 24 h run of the designed network."""
import pytest

from water_app.engine import demand as dm
from water_app.engine import design as wd
from water_app.engine import simulate as wsim
from water_app.data import wards as W
from water_app.run.zoning_run import _crit


def tee():
    """A T: A-B 100 m, B-C 100 m, B-D 300 m."""
    nodes = {"A": {"xy": (0, 0)}, "B": {"xy": (100, 0)}, "C": {"xy": (200, 0)}, "D": {"xy": (100, 300)}}
    cs = [{"start_node": "A", "stop_node": "B", "length_m": 100}, {"start_node": "B", "stop_node": "C", "length_m": 100},
          {"start_node": "B", "stop_node": "D", "length_m": 300}]
    return {"nodes": nodes, "conduits": cs}


def test_spread_by_length_area_equal():
    net = tee()
    by_len = W.spread_total(net, 1000, "length")
    assert by_len == pytest.approx({"A": 100, "B": 500, "C": 100, "D": 300})
    assert W.spread_total(net, 1000, "equal") == pytest.approx({n: 250 for n in "ABCD"})
    area = W.spread_total(net, 1000, "area")
    assert sum(area.values()) == pytest.approx(1000)
    assert area["A"] == pytest.approx(area["C"], rel=0.02)          # alike by the symmetry
    assert area["B"] < by_len["B"]                                   # the meeting point no longer takes half
    ward = [(-50, -50), (250, -50), (250, 350), (-50, 350)]
    for by in ("length", "area", "equal"):
        pop, rows = W.population_in_polygons(net, [(ward, 1000)], by)
        assert sum(pop.values()) == pytest.approx(1000) and rows[0]["manholes inside"] == 4
    pop, _ = W.population_in_polygons(net, [(ward, 1000)], "area")
    assert pop["D"] > pop["B"]                                       # D's land reaches to the ward's far edge
    no_conn = dict(net, conduits=[dict(c, no_conn=True) if c["stop_node"] == "D" else c for c in net["conduits"]])
    assert "D" not in W.spread_total(no_conn, 1000, "equal")         # a feeder main: no population on its end alone
    with pytest.raises(ValueError):
        W.load_by({"load_by": "volume"})
    assert W.load_by({}) == "length"


def test_peak_factor_of_the_page():
    assert _crit({})["peak_factor"]["value"] == 2.5
    c = _crit({"peak": "rural"})["peak_factor"]
    assert c["value"] == 3.0 and "S.No.7(c)" in c["ref"]
    assert _crit({"peak": "2.2"})["peak_factor"]["value"] == 2.2
    for bad in ("x", "9"):
        with pytest.raises(ValueError):
            _crit({"peak": bad})


def small_design():
    """An OHT (head 120 m) feeding a line of junctions at 100 m ground, designed with the app's design()."""
    crit = wd.load_criteria()
    nodes = {"OHT": {"elev": 100.0, "head": 122.0}}
    pipes = {}
    prev = "OHT"
    for i in range(1, 6):
        nodes[f"J{i}"] = {"elev": 100.0, "demand": 2.0, "avg": 2.0}
        pipes[f"P{i}"] = {"a": prev, "b": f"J{i}", "length": 200.0}
        prev = f"J{i}"
    nodes["J6"] = {"elev": 100.0, "demand": 2.0, "avg": 2.0}
    pipes["OHT outlet"] = {"a": "OHT", "b": "J1", "length": 20.0}
    pipes["P1"]["a"] = "J6"
    pipes["P6"] = {"a": "J1", "b": "J6", "length": 100.0}
    hnet = {"nodes": nodes, "pipes": pipes}
    r = wd.design(hnet, crit, log=lambda s: None)
    return hnet, crit, r["result"]


def test_load_cases():
    hnet, crit, res = small_design()
    oz = {n: "OHT" for n in hnet["nodes"] if n != "OHT"}
    rows, fires = wsim.cases(hnet, crit, [], res["pressure"], oz)
    by = {r["case"]: r for r in rows}
    assert set(by) == {"peak", "average", "night"} and not fires
    assert by["peak"]["min_p"] == pytest.approx(min(p for n, p in res["pressure"].items() if n != "OHT"), abs=0.01)
    assert by["peak"]["min_p"] < by["average"]["min_p"] < by["night"]["min_p"]      # less demand: more head
    assert by["night"]["factor"] == min(crit["draw_off_pattern"]["value"])
    assert by["average"]["demand_lps"] == pytest.approx(12.0)
    rows, fires = wsim.cases(hnet, crit, [], res["pressure"], oz, fire_lps=10, fire_min_m=50)
    f = fires[0]
    weakest = min((n for n in oz), key=lambda n: res["pressure"][n])
    assert len(fires) == 1 and f["node"] == weakest and f["ok"] is False and f["p"] < by["average"]["min_p"]
    assert next(r for r in rows if r["case"] == "fire")["demand_lps"] == pytest.approx(22.0)
    _, fires = wsim.cases(hnet, crit, [], res["pressure"], oz, fire_lps=10)
    assert fires[0]["ok"] is None                                                   # no head given: shown only


def test_day():
    hnet, crit, res = small_design()
    daily = 12.0 * 86.4                                                # 12 L/s average
    swing = dm.mass_balance(crit)["share"] * daily                     # what the day's swing needs
    tank = {"name": "OHT", "kl": swing + 30.0, "swd_m": 4.0, "fire_kl": 30.0, "daily_kl": daily}
    d = wsim.day(hnet, crit, [tank], [])
    assert len(d["hours"]) == 24
    t = d["tanks"]["OHT"]
    assert not t["empty_h"] and t["short_kl"] == 0 and t["spill_kl"] == 0
    assert t["min_pct"] == pytest.approx(0.0, abs=0.5)                 # just the swing: it touches 0 %
    assert t["min_pct"] < wsim.MARGIN_PCT                              # - no margin: the design warns of it
    assert t["end_pct"] == pytest.approx(t["start_pct"], abs=0.5)      # a day's inflow = a day's demand
    outs = sum(h["tanks"]["OHT"]["out_kl"] for h in d["hours"])
    assert outs == pytest.approx(daily, rel=0.01)
    assert all(h["low_n"] == 0 for h in d["hours"])                     # the water above the design's lowest level
    peak_h = max(d["hours"], key=lambda h: h["factor"])
    assert peak_h["min_p"] > res["pressure"][min(res["pressure"], key=res["pressure"].get)]
    # CPHEEO's 33 % (more than the swing): half the room beyond the swing at 0 h - as far from empty as from full
    big = wsim.day(hnet, crit, [dict(tank, kl=dm.storage_share(crit) * daily + 30.0)], [])["tanks"]["OHT"]
    room = 100.0 * (dm.storage_share(crit) - dm.mass_balance(crit)["share"]) / dm.storage_share(crit)
    assert big["min_pct"] == pytest.approx(room / 2, abs=1.0) and big["min_pct"] > wsim.MARGIN_PCT
    assert 100.0 - max(h["tanks"]["OHT"]["full_pct"] for h in wsim.day(hnet, crit, [dict(tank, kl=dm.storage_share(crit) * daily + 30.0)], [])["hours"])         == pytest.approx(room / 2, abs=2.0)
    half = wsim.day(hnet, crit, [dict(tank, kl=0.5 * swing + 30.0)], [])["tanks"]["OHT"]
    assert (half["full_h"] and half["spill_kl"] > 0) or half["empty_h"]           # too small: inflow lost or dry
    quarter = wsim.day(hnet, crit, [dict(tank, kl=0.25 * swing + 30.0)], [])["tanks"]["OHT"]
    assert quarter["empty_h"] and quarter["short_kl"] > 0


def test_storage_margin():
    crit = wd.load_criteria()
    base = dm.storage_share(crit)
    crit["oht_margin"] = {"value": 0.10, "ref": "-"}
    assert dm.storage_share(crit) == pytest.approx(base * 1.10)


def test_constraints_of_the_page():
    c = _crit({"cons": {"pmax": "35", "dmin": "140", "hdpe_max": "140", "hl": "10", "stg": "25", "margin": "10",
                        "cases": "1"}})
    assert c["max_pressure_m"]["value"] == 35 and c["max_hl_distribution_m_per_km"]["value"] == 10
    assert c["max_staging_m"]["value"] == 25 and c["oht_margin"]["value"] == pytest.approx(0.10)
    assert c["design_cases"]["value"] is True
    names = [s["name"] for s in wd.allowed_pipes(c)]
    assert names[0] == "HDPE 140" and "HDPE 160" not in names and "DI 600" in names
    assert not any(k in _crit({"cons": {"pmax": "", "cases": ""}}) for k in ("max_pressure_m", "design_cases"))
    for bad in ({"pmax": "5"}, {"dmin": "300", "dmax": "200"}, {"hl": "x"}):
        with pytest.raises(ValueError):
            _crit({"cons": bad})


def test_design_with_the_constraints():
    hnet, crit, res = small_design()
    base = {p: hnet["pipes"][p]["d_mm"] for p in hnet["pipes"]}
    # head loss: no pipe steeper than the limit at the peak
    crit["max_hl_distribution_m_per_km"] = {"value": 2.0, "ref": "-"}
    r = wd.design(hnet, crit, log=lambda s: None)
    assert max(r["result"]["hl_per_km"].values()) <= 2.0 + 1e-6
    assert any(hnet["pipes"][p]["d_mm"] > base[p] for p in base)
    # another load (a fresh design: the one above grew its pipes)
    hnet, crit, res = small_design()
    #: a fire flow at the end of the line, 10 m there - the pipes on its way grow
    oz = {n: "OHT" for n in hnet["nodes"] if n != "OHT"}
    far = min(oz, key=lambda n: res["pressure"][n])
    case = {"name": "fire", "factor": 1.0, "extra": {far: 15.0}, "min_head": 10.0}
    plain = wsim.cases(hnet, crit, [], res["pressure"], oz, fire_lps=15, fire_min_m=10)[1][0]
    assert plain["ok"] is False                                         # the peak design alone does not do it
    r = wd.design(hnet, crit, log=lambda s: None, cases=[case])
    assert not r["cases"]["fire"]["low"] and r["cases"]["fire"]["result"]["pressure"][far] >= 10.0 - 1e-6
    assert any(c["check"].startswith("fire: residual head >= 10") and c["ok"] for c in r["checks"])
