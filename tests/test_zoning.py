"""Zoning on a synthetic network (the comparison with the SewerGEMS-era oakdale_B zoning run is
tools/compare_with_agent_zoning.py - it needs the original scripts)."""
import copy

import openpyxl

from sewer_app import zoning
from sewer_app.criteria import load_criteria

from synthetic import INP, synth


def test_options_ranked_and_written(tmp_path):
    z = zoning.run(synth(), INP, log=lambda s: None)
    rank = z["rank"]
    assert any(ev["m"]["option"] == "CURRENT" for ev in rank)          # the network's own outfall is an option
    assert [ev["m"]["rank"] for ev in rank] == list(range(1, len(rank) + 1))
    for ev in rank:                                   # every node in exactly one zone, every zone has an outlet
        assert set(ev["zone"]) == set(z["adj"])
        assert set(ev["zone"].values()) <= set(z["adj"])
    p = zoning.write_workbook(z, str(tmp_path / "zoning.xlsx"), source="synthetic")
    c = zoning.cost_workbook(z, str(tmp_path / "zoning_costs.xlsx"), source="synthetic")
    assert "Options" in openpyxl.load_workbook(p, read_only=True).sheetnames
    assert "Comparison" in openpyxl.load_workbook(c, read_only=True).sheetnames


def test_apply_option_then_design():
    """The chosen option applied to the network: outlets = outfalls, cut conduits start at new head manholes; the
    design then agrees with the zoning (same depths, every manhole within the project limit)."""
    from sewer_app import network, pipeline
    crit = copy.deepcopy(load_criteria())
    crit["sewer"]["lift_stations_allowed"]["value"] = False
    crit["sewer"]["max_depth_project_m"]["value"] = 3.0
    net = synth()
    z = zoning.run(net, INP, crit=crit, stp="OUT", log=lambda s: None)
    ev = next(e for e in z["rank"] if e["m"]["option"] == "CURRENT")
    net2, rows = zoning.apply_option(net, ev)
    assert net2["outfalls"] == sorted(set(ev["zone"].values())) and len(net2["outfalls"]) >= 2
    assert len(rows) == len(ev["cuts"])
    for r in rows:
        assert r["new head manhole"].startswith(r["disconnected from"] + "-C")
        assert net2["nodes"][r["new head manhole"]]["xy"] == net["nodes"][r["disconnected from"]]["xy"]
    assert not network.validate(net2)
    assert net["outfalls"] == ["OUT"]                                  # the given network is not changed
    out = pipeline.run(net2, INP, crit, log=lambda s: None)
    deps = [i["depth"] for i in out["node_info"].values() if i.get("depth") is not None]
    assert max(deps) <= 3.0 + 1e-6
    assert abs(max(deps) - ev["m"]["max depth (m)"]) < 0.1


def test_pumping_station_added_where_too_deep():
    """With a 3 m project depth limit the 1.2 km flat main sewer goes too deep: a pumping station (new zone
    outlet) is added above that point, and no manhole stays deeper than the limit."""
    crit = copy.deepcopy(load_criteria())
    crit["sewer"]["lift_stations_allowed"]["value"] = False
    crit["sewer"]["max_depth_project_m"]["value"] = 3.0
    z = zoning.run(synth(), INP, crit=crit, log=lambda s: None)
    cur = next(ev for ev in z["rank"] if ev["m"]["option"] == "CURRENT")
    assert cur["m"]["of these added for depth"] >= 1
    assert cur["m"]["manholes deeper than project limit"] == 0
    assert all(d is None or d <= 3.0 + 1e-6 for n, i in cur["info"].items() if n not in cur["vnodes"]
               for d in [i.get("depth")])
    # option GIVEN: only the network's own outfall - no pumping station, the sewer may go deeper than the limit;
    # listed last (not ranked), and it designs like any option
    giv = z["rank"][-1]
    assert giv["m"]["option"] == "GIVEN" and giv["m"]["rank"] == len(z["rank"])
    assert giv["m"]["of these added for depth"] == 0 and sorted(set(giv["zone"].values())) == sorted(cur_outs(z))
    assert giv["m"]["manholes deeper than project limit"] >= 1
    from sewer_app import pipeline
    net, _ = zoning.apply_option(synth(), giv)
    assert net["outfalls"] == sorted(cur_outs(z))
    out = pipeline.run(net, INP, crit=crit, log=lambda s: None)
    assert any("project limit" in f for d in out["res"].values() for f in d["flags"])      # flagged, not stopped
    assert "GIVEN" not in [ev["m"]["option"] for ev in zoning.run(synth(), INP, crit=crit, log=lambda s: None,
                                                                    given_only=False)["rank"]]


def cur_outs(z):
    return sorted(set(z["model_outs"]) | set(z["fixed"]))


def test_gl_band_map(tmp_path):
    """GL band map (from the original scripts zoning.py): ranges above a reference GL; every manhole and every metre of sewer
    falls in exactly one row (below / range / gap)."""
    import pytest
    assert zoning.parse_bands("0-1.5, 1.5-3, 3-4.5, 4.5+") == [(0.0, 1.5), (1.5, 3.0), (3.0, 4.5), (4.5, None)]
    with pytest.raises(ValueError):
        zoning.parse_bands("1.5-0")
    z = zoning.run(synth(), INP, log=lambda s: None)
    ref = round(min(z["gl"].values()) + 0.4, 2)
    png, rows, text = zoning.band_outputs(z, str(tmp_path / "bands.png"), ref, "0-0.5, 0.7+")
    assert png and (tmp_path / "bands.png").is_file() and f"{ref:.2f}" in text
    assert [r["kind"] for r in rows] == ["below", "range", "gap", "range"]
    assert sum(r["manholes"] for r in rows) == len(z["gl"])
    total = sum(e["L"] for e in z["E"].values())
    assert abs(sum(r["sewer length (m)"] for r in rows) - total) < 0.5
    p = zoning.write_workbook(z, str(tmp_path / "zoning.xlsx"), source="synthetic")
    assert "GL bands" in openpyxl.load_workbook(p, read_only=True).sheetnames
