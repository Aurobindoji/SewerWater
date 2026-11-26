"""The Simulation tab (17-Nov-2026): simulate.day with an own pattern, 48 / 72 h, a stage factor, extra loads and each
hour's detail; simulate.ssa; sim_run's checks of the page's inputs."""
import pytest

from test_water_load import small_design
from water_app.engine import demand as dm
from water_app.run import sim_run
from water_app.engine import simulate as wsim


def _tank(crit):
    daily = 12.0 * 86.4
    return {"name": "OHT", "kl": dm.storage_share(crit) * daily + 30.0, "swd_m": 4.0, "fire_kl": 30.0, "daily_kl": daily}


def test_day_as_before_without_the_new_options():
    hnet, crit, _ = small_design()
    a = wsim.day(hnet, crit, [_tank(crit)], [])
    b = wsim.day(hnet, crit, [_tank(crit)], [], pattern=crit["draw_off_pattern"]["value"], hours=24, factor=1.0)
    assert a == b and "P" not in a


def test_day_detail_and_more_days():
    hnet, crit, _ = small_design()
    d = wsim.day(hnet, crit, [_tank(crit)], [], hours=72, detail=True)
    assert len(d["hours"]) == 72 and len(d["P"]) == 72 and len(d["P"][0]) == len(d["nodes"]) == 6
    assert len(d["Q"][0]) == len(d["pipes"]) and "OHT" not in d["nodes"]
    pat = crit["draw_off_pattern"]["value"]
    assert [h["factor"] for h in d["hours"][24:48]] == pat                      # the pattern each day again
    for h in (0, 30, 71):                                                       # the detail = the hour's summary
        assert min(d["P"][h]) == pytest.approx(d["hours"][h]["min_p"], abs=0.01)
    t = d["tanks"]["OHT"]
    assert t["end_pct"] == pytest.approx(t["start_pct"], abs=1.0)             # a day's inflow = a day's demand


def test_day_flat_pattern_stage_and_extra():
    hnet, crit, _ = small_design()
    flat = wsim.day(hnet, crit, [_tank(crit)], [], pattern=[1.0] * 24)
    assert {h["demand_lps"] for h in flat["hours"]} == {12.0}
    half = wsim.day(hnet, crit, [_tank(crit)], [], factor=0.5)
    assert half["hours"][8]["demand_lps"] == pytest.approx(0.5 * 12.0 * crit["draw_off_pattern"]["value"][8])
    ex = wsim.day(hnet, crit, [_tank(crit)], [], pattern=[1.0] * 24, extra={"J5": 3.0}, detail=True)
    assert ex["hours"][0]["demand_lps"] == pytest.approx(15.0)                 # not multiplied by the pattern
    j5 = ex["nodes"].index("J5")
    assert ex["P"][0][j5] < flat["hours"][0]["max_p"]
    assert ex["tanks"]["OHT"]["end_pct"] < flat["tanks"]["OHT"]["end_pct"]     # the extra draw-off empties the tank


def test_ssa():
    hnet, crit, res = small_design()
    pf = crit["peak_factor"]["value"]
    r, s = wsim.ssa(hnet, crit, [], factor=pf)
    assert s["min_p"] == pytest.approx(min(p for n, p in res["pressure"].items() if n != "OHT"), abs=0.01)
    r1, s1 = wsim.ssa(hnet, crit, [])
    r2, s2 = wsim.ssa(hnet, crit, [], extra={"J5": 10.0})
    assert s2["min_p"] < s1["min_p"] and r2["pressure"]["J5"] < r1["pressure"]["J5"]


def _pack(monkeypatch):
    hnet, crit, res = small_design()
    pack = {"hnet": hnet, "prvs": [], "oz": {n: "OHT" for n in hnet["nodes"]}, "crit": crit, "tanks": [_tank(crit)],
            "windows": crit["oht_inflow_hours"]["value"], "stages": {"mid": {"year": 2041, "pop": 1, "factor": 0.8}},
            "fire_lps": None, "fire_min": None, "peak_p": res["pressure"]}
    monkeypatch.setattr(sim_run, "sim_pack", lambda stem: pack)
    return pack


def test_sim_run(monkeypatch):
    _pack(monkeypatch)
    a = sim_run.run("t", {"mode": "ssa"})
    assert a["mode"] == "ssa" and a["demand_lps"] == pytest.approx(12.0) and len(a["P"]) == 6
    m = sim_run.run("t", {"mode": "ssa", "stage": "mid", "base": "factor", "factor": 2})
    assert m["factor"] == pytest.approx(1.6) and m["demand_lps"] == pytest.approx(19.2)
    f = sim_run.run("t", {"mode": "ssa", "fires": [{"node": "J5", "lps": 10}], "min_m": 50})
    assert f["fires"][0]["ok"] is False and f["demand_lps"] == pytest.approx(22.0)
    assert f["worst"]["low"][0][0] == "J5"
    h = sim_run.run("t", {"mode": "ssa", "base": "hour", "hour": 7})
    assert "07:00" in h["load"]
    e = sim_run.run("t", {"mode": "eps", "hours": 48, "pattern": [1] * 24, "inflow": "0-24"})
    assert e["n_hours"] == 48 and len(e["P"]) == 48 and e["note"] is None and e["windows"] == [[0, 24]]
    w = sim_run.run("t", {"mode": "eps", "pattern": [2] * 24})
    assert w["note"] and "48" in w["note"]


@pytest.mark.parametrize("req", [
    {"mode": "ssa", "stage": "init"},                                  # no base-year population in the design
    {"mode": "ssa", "fires": [{"node": "OHT", "lps": 5}]},              # a tank is no junction
    {"mode": "ssa", "extra": [{"node": "J9", "lps": 5}]},               # not in the network
    {"mode": "ssa", "extra": [{"node": "J1", "lps": "x"}]},
    {"mode": "ssa", "base": "hour", "hour": 24},
    {"mode": "eps", "hours": 36},
    {"mode": "eps", "pattern": [1] * 23},
    {"mode": "eps", "pattern": [1] * 23 + [-1]},
    {"mode": "flood"},
])
def test_sim_run_refuses(monkeypatch, req):
    _pack(monkeypatch)
    with pytest.raises(ValueError):
        sim_run.run("t", req)


def test_no_design_no_simulation(monkeypatch):
    monkeypatch.setattr(sim_run, "sim_pack", lambda stem: None)
    with pytest.raises(ValueError):
        sim_run.run("t", {"mode": "ssa"})
