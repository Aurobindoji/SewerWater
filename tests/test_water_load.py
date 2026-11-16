"""Water load options and the simulation (user request 16-Nov-2026): how the population is put on the junctions, the
peak factor of the page, the load cases and the 24 h run of the designed network."""
import pytest

from water_app import demand as dm
from water_app import design as wd
from water_app import simulate as wsim
from water_app import wards as W
from water_app.zoning_run import _crit


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
    need = dm.storage_share(crit) * daily
    tank = {"name": "OHT", "kl": need + 30.0, "swd_m": 4.0, "fire_kl": 30.0, "daily_kl": daily}
    d = wsim.day(hnet, crit, [tank], [])
    assert len(d["hours"]) == 24
    t = d["tanks"]["OHT"]
    assert not t["empty_h"] and t["short_kl"] == 0 and t["spill_kl"] == 0
    assert t["min_pct"] == pytest.approx(0.0, abs=0.5)                 # sized by the mass balance: it touches 0 %
    assert t["min_pct"] < wsim.MARGIN_PCT                              # - no margin: the design warns of it
    assert t["end_pct"] == pytest.approx(t["start_pct"], abs=0.5)      # a day's inflow = a day's demand
    outs = sum(h["tanks"]["OHT"]["out_kl"] for h in d["hours"])
    assert outs == pytest.approx(daily, rel=0.01)
    assert all(h["low_n"] == 0 for h in d["hours"])                     # the water above the design's lowest level
    peak_h = max(d["hours"], key=lambda h: h["factor"])
    assert peak_h["min_p"] > res["pressure"][min(res["pressure"], key=res["pressure"].get)]
    half = wsim.day(hnet, crit, [dict(tank, kl=0.5 * need + 30.0)], [])["tanks"]["OHT"]
    assert half["full_h"] and half["spill_kl"] > 0 and half["end_pct"] < half["start_pct"]   # full: inflow lost
    quarter = wsim.day(hnet, crit, [dict(tank, kl=0.25 * need + 30.0)], [])["tanks"]["OHT"]
    assert quarter["empty_h"] and quarter["short_kl"] > 0                                  # and then runs dry
