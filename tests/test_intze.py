"""Intze OHT design and drawings (water_app/intze.py, intze_dwg.py, intze_api.py): the shape, sections and the
annular raft of the user's example of 10-Nov-2026 (Brookfield Consultants, 2700 KL on 24 m, zone 14 Greenfield, Springfield)."""
import math

import ezdxf
import pytest
from openpyxl import load_workbook

from water_app import intze, intze_api, intze_calc, intze_dwg


@pytest.mark.parametrize("cap,stg", [(150, 15), (500, 20), (1000, 22), (2700, 24)])
def test_design_holds_the_capacity(cap, stg):
    swd = intze_api.swd_of(cap)
    r = intze.design(cap, stg, swd)
    g, lev = r["geo"], r["levels"]
    assert g["cap"] >= cap - 1.0
    assert g["hc"] == swd                               # user 10-Nov-2026: the SWD at the wall, the cone below
    assert g["H"] == pytest.approx(swd + g["h0"])
    assert g["h0"] == pytest.approx(intze.cone_depth(cap, swd), abs=1e-6)
    assert g["h2"] < g["H"]
    assert lev["LWL"] == stg and lev["FSL"] == pytest.approx(stg + g["H"])
    assert g["n_col"] % 2 == 0 and g["n_col"] >= 4
    rf = r["members"]["raft"]
    assert rf["Ri"] < g["r0"] < rf["Ro"]                # the annular raft round the column circle
    conc, steel = intze.quantities(r)
    assert 70 < sum(steel.values()) / sum(conc.values()) < 220


def test_the_example_2700_kl():
    """The example's tank: D 25.47 m, column circle 20 m, cone 2.637, 20 columns 600, braces 250 x 600, annular raft
    R 4.3-14 m: the app's sizes near it."""
    r = intze.design(2700, 24, 5, {"cyl_depth_m": 4.434})
    g, M = r["geo"], r["members"]
    assert g["D"] == pytest.approx(25.47, abs=0.3)
    assert g["D0"] == pytest.approx(20.0, abs=0.3)
    assert g["h0"] == pytest.approx(2.637, abs=0.1)
    assert g["n_col"] == 20 and M["column"]["d"] == 600
    assert (M["brace"]["b"], M["brace"]["d"]) == (250, 600)
    assert M["raft"]["Ro"] == pytest.approx(14.0, abs=0.5)
    assert M["raft"]["Ri"] == pytest.approx(4.3, abs=0.6)
    assert 300 <= M["cone"]["t"] <= 450
    assert M["stair"]["n1"] + M["stair"]["n2"] == 14     # the example's 14 flights


def test_circular_beam_formulas():
    c = intze._circ_beam(1.0, 1.0, 4)
    assert c["Ms"] == pytest.approx(-0.2146, abs=1e-4)
    assert c["Mm"] == pytest.approx(0.1107, abs=1e-4)
    assert c["T"] > 0 and c["V"] == pytest.approx(math.pi / 4)


def test_column_interaction():
    curve = intze.col_curve(600, 12, 20, 60, 30, 500)
    p0 = max(p for p, _ in curve)
    # pure axial near 0.45 fck Ac + 0.75 fy As (IS 456 39.3: 0.4 / 0.67 is the design value with emin)
    assert 0.40 * 30 * math.pi * 300 ** 2 / 1e3 < p0 < 0.48 * 30 * math.pi * 300 ** 2 / 1e3 + 0.87 * 500 * 12 * 314 / 1e3
    assert intze.col_moment(curve, 1500) > intze.col_moment(curve, 4000) > 0


def test_settings_of_the_page():
    o, per = intze_api.settings({"intze": {"zone": "iv", "sbc": "120", "soil": "III", "vb": "", "fck": "35", "fckf": "25",
                                           "per": "Prop-OHT-1=90, X=5, OHT 2 = 150"}})
    assert o == {"zone": "IV", "sbc_kn_m2": 120.0, "soil_type": "III", "fck": 35, "fck_found": 25}
    assert per == {"Prop-OHT-1": 90.0, "OHT 2": 150.0}


def test_targets_are_new_ohts_only():
    d = {"outlets": [{"name": "A", "existing": True, "capacity_kl": 500, "staging_m": 18},
                     {"name": "B", "existing": False, "required_kl": 750, "staging_m": 21.5},
                     {"name": "C", "existing": False, "required_kl": 300, "staging_m": None}]}
    assert intze_api.targets(d) == [("B", 750.0, 21.5)]


def test_one_tank_at_a_time(tmp_path, monkeypatch):
    """The page's Design button of each tank (user decision 10-Nov-2026): the list of the new OHTs with their
    drawings' state, and only the tank asked drawn."""
    import json
    import os
    import time
    monkeypatch.setattr(intze_api.ui, "OUT_ROOT", str(tmp_path))
    d = {"outlets": [{"name": "A", "existing": True, "capacity_kl": 500, "staging_m": 18},
                     {"name": "Prop-OHT-1", "required_kl": 300, "staging_m": 15},
                     {"name": "Prop-OHT-2", "required_kl": 400, "staging_m": 16}]}
    (tmp_path / "p").mkdir()
    (tmp_path / "p" / "p_wdesign_ui.json").write_text(json.dumps(d), encoding="utf-8")
    t = intze_api.tanks("p")
    assert [(o["name"], o["made"]) for o in t["ohts"]] == [("Prop-OHT-1", ""), ("Prop-OHT-2", "")]
    drawn = []
    monkeypatch.setattr(intze_api.intze_dwg, "export", lambda res, out, stem, meta, pdf=True: (
        drawn.append(meta["name"]), os.makedirs(out, exist_ok=True),
        open(os.path.join(out, stem + ".dxf"), "w").close(), {"dxf": os.path.join(out, stem + ".dxf")})[-1])
    r = intze_api.export_all("p", {}, only="Prop-OHT-2")
    assert drawn == ["Prop-OHT-2"] and [o["name"] for o in r["ohts"]] == ["Prop-OHT-2"]
    t = {o["name"]: o for o in intze_api.tanks("p")["ohts"]}
    assert t["Prop-OHT-1"]["made"] == "" and t["Prop-OHT-2"]["made"] and not t["Prop-OHT-2"]["stale"]
    later = time.time() + 60                       # a design after the drawings: they are stale
    os.utime(tmp_path / "p" / "p_wdesign_ui.json", (later, later))
    assert intze_api.tanks("p")["ohts"][1]["stale"]
    with pytest.raises(ValueError):
        intze_api.export_all("p", {}, only="A")       # an existing tank is not drawn


def test_export_dxf_and_xlsx(tmp_path):
    r = intze.design(500, 18, 4)
    p = intze_dwg.export(r, str(tmp_path), "t_intze", {"name": "OHT-T"}, pdf=False)
    doc = ezdxf.readfile(p["dxf"])
    texts = " ".join(e.dxf.text for e in doc.modelspace().query("TEXT"))
    for s in ("STAGING AND FOUNDATION", "SECTION OF TANK", "STAIRCASE", "BAR BENDING SCHEDULE", "Sheet 4 of 4",
              "PART REINFORCEMENT PLAN OF RAFT SLAB", "structural engineer"):
        assert s in texts
    wb = load_workbook(p["xlsx"])
    assert wb.sheetnames == ["Design", "BBS", "Quantities"]
    assert wb["BBS"].max_row == len(r["bbs"]) + 2


def test_calculation_report(tmp_path):
    """The design calculation as a report (user request 10-Nov-2026): every part, formulas with the numbers, a PDF."""
    r = intze.design(2700, 24, 5, {"cyl_depth_m": 4.434})
    lines = intze_calc.report(r)
    heads = [t for k, t in lines if k == "h1"]
    for h in ("1.0 DESIGN DATA", "3.0 DESIGN OF TOP DOME", "7.0 DESIGN OF CONICAL DOME", "9.0 DESIGN OF BOTTOM RING BEAM",
              "12.0 DESIGN OF COLUMNS", "13.0 DESIGN OF BRACES", "15.0 STAIR CASE"):
        assert any(x.startswith(h) for x in heads), h
    text = " ".join(t for _, t in lines)
    assert "T1 = w R1 / (1 + cos θ1)" in text and "Mb = 0.5 Mo (Lc / Lb) sec (π/n)" in text
    assert f"Provide {r['members']['raft']['rad'][0]} - {r['members']['raft']['rad'][1]} φ" in text
    p = intze_calc.export_pdf(r, str(tmp_path / "c.pdf"), {"name": "OHT-T"})
    assert (tmp_path / "c.pdf").stat().st_size > 20000
