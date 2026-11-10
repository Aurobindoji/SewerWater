"""Pipe sizing to CPHEEO: every junction gets the residual head, no pipe too fast, the economy pass keeps it so, a
too-low OHT is reported with the head missing, an existing (fixed) pipe keeps its size."""
import copy
import itertools

from water_app import design as wd


def town(n=6, staging=24.0, demand=0.6):
    """n x n road grid (150 m blocks), a tank at one corner, flat ground at 80 m."""
    nodes = {"OHT": {"elev": 80.0, "head": 80.0 + staging}}
    pipes = {}
    for i, j in itertools.product(range(n), range(n)):
        nodes[f"J{i}{j}"] = {"elev": 80.0, "demand": demand}
    pipes["main"] = {"a": "OHT", "b": "J00", "length": 50}
    for i, j in itertools.product(range(n), range(n)):
        if i + 1 < n:
            pipes[f"v{i}{j}"] = {"a": f"J{i}{j}", "b": f"J{i+1}{j}", "length": 150}
        if j + 1 < n:
            pipes[f"h{i}{j}"] = {"a": f"J{i}{j}", "b": f"J{i}{j+1}", "length": 150}
    return {"nodes": nodes, "pipes": pipes}


def test_design_meets_residual_head_and_velocity():
    crit = wd.load_criteria()
    net = town()
    r = wd.design(net, crit)
    assert all(c["ok"] for c in r["checks"]), r["checks"]
    rh = crit["residual_head_m"]["value"]
    assert min(p for n, p in r["result"]["pressure"].items() if n != "OHT") >= rh - 1e-6
    assert max(r["result"]["velocity"].values()) <= crit["max_velocity_mps"]["value"]
    # the main from the tank carries everything and is the largest pipe
    assert r["size"]["main"]["id_mm"] == max(s["id_mm"] for s in r["size"].values())
    # peak flow out of the tank = 2.5 x average
    assert abs(r["result"]["flow"]["main"] - 2.5 * 36 * 0.6) < 1e-6
    assert r["summary"]["min_pressure"] >= rh - 1e-6 and r["missing_head_m"] is None


def test_economise_saves_pipe_and_still_passes():
    crit = wd.load_criteria()
    a = wd.design(town(), crit, economise=False)
    b = wd.design(town(), crit, economise=True)
    vol = lambda r, net: sum(r["size"][p]["id_mm"] ** 2 * net["pipes"][p]["length"] for p in r["size"])
    na, nb = town(), town()
    assert vol(b, nb) <= vol(a, na)
    assert all(c["ok"] for c in b["checks"])


def test_too_low_oht_reports_the_missing_head():
    r = wd.design(town(staging=12.0), economise=False)
    assert r["low"] and r["missing_head_m"] is not None
    assert r["missing_head_m"] > 5.0                     # 12 m staging cannot give 17 m at the far end
    assert not r["checks"][0]["ok"]


def test_existing_pipe_keeps_its_size():
    net = town()
    net["pipes"]["h00"].update({"fixed": True, "d_mm": 80.0, "C": 100})
    r = wd.design(copy.deepcopy(net))
    assert "h00" not in r["size"]
    assert "existing 80 mm" in r["summary"]["length_by_size"]
