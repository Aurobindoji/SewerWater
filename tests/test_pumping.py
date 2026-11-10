"""Approximate pumping-station cost (user decision 12-Oct-2026: logical approximate cost from civil, mechanical
and electrical parts; checked in the DPR) - fitted to the three stations of the user's DPRs (Riverside SPS-1,
Lakeside SPS-1 and SPS-2) - and the rising main (Springfield SOR 2025-26)."""
import copy

import openpyxl

from sewer_app import pumping, rising_main, zoning

from synthetic import INP, synth


def test_model_reproduces_the_three_dpr_stations():
    """Civil and E&M of Riverside SPS-1 and of Lakeside SPS-1 + SPS-2 within 4 %."""
    for station, part, dpr, model in pumping.fit_check():
        assert abs(model / dpr - 1) < 0.04, (station, part, dpr, model)


def test_cost_grows_with_flow_and_depth():
    caps = [pumping.sps_cost(q, q / 2.25, 6.0)["capex"] for q in (5, 20, 50, 100, 300, 600)]
    assert caps == sorted(caps)
    assert pumping.sps_cost(100, 44, 9.0)["capex"] > pumping.sps_cost(100, 44, 4.0)["capex"]
    assert pumping.sps_cost(5, 2.2, 3.0)["ht"]                     # all three DPR stations have an HT supply


def test_lt_connection_below_a_threshold():
    P = copy.deepcopy(pumping.load_params())
    P["ht_threshold_kw"]["value"] = 75.0
    small = pumping.sps_cost(5, 2.2, 3.0, P)
    assert not small["ht"] and any(name.startswith("LT connection") for _, name, _, _ in small["components"])


def test_stp_rate():
    assert abs(pumping.stp_cost_lakh(1e6 / 86400.0) - 150.0) < 1e-9          # 1 MLD -> Rs 1.5 crore


def test_rising_main():
    K = rising_main.load_rates()
    r = rising_main.rising_main(300.0, 1000.0, K)
    assert r["n"] == 1 and r["velocity"] <= 1.8 and abs(r["length"] - 1300.0) < 1e-9
    assert r["parts"]["laying (SOR)"] == K["laying_di"]["by_dia_mm"][str(r["dia"])]["rate"]
    big = rising_main.rising_main(1500.0, 1000.0, K)               # beyond 600 mm: parallel mains
    assert big["n"] >= 2 and big["dia"] <= 600


def test_zoning_costs_include_pumping_stations_and_rising_mains(tmp_path):
    """A 3 m depth limit makes the flat main sewer need pumping stations; with the STP given they get rising mains."""
    from sewer_app.criteria import load_criteria
    crit = copy.deepcopy(load_criteria())
    crit["sewer"]["lift_stations_allowed"]["value"] = False
    crit["sewer"]["max_depth_project_m"]["value"] = 3.0
    z = zoning.run(synth(), INP, crit=crit, stp="OUT", max_zones=3, log=lambda s: None)
    assert any(ev["m"]["pumping stations"] for ev in z["rank"])
    p = zoning.cost_workbook(z, str(tmp_path / "costs.xlsx"))
    wb = openpyxl.load_workbook(p, read_only=True)
    assert "Pumping stations" in wb.sheetnames and "SPS components" in wb.sheetnames
    groups = {str(r[2]) for r in list(wb["Items"].iter_rows(values_only=True))[1:]}
    assert any(g.startswith("5 pumping") for g in groups) and any(g.startswith("7 rising") for g in groups)
    rows = list(wb["Pumping stations"].iter_rows(values_only=True))
    hdr = rows[0]
    assert all(r[hdr.index("rising main (Rs lakh)")] for r in rows[1:])
