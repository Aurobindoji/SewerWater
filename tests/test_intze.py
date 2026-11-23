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
    intze_calc.export_pdf(r, str(tmp_path / "c.pdf"), {"name": "OHT-T"})
    assert (tmp_path / "c.pdf").stat().st_size > 20000


def test_small_tank_ring_beam_in_the_raft_depth():
    """A 150 KL tank got a 350 raft whose foundation ring beam needed 11 million bars (ast_flex beyond its limit) and
    the drawing hung drawing them (21-Nov-2026): the raft's depth now holds the ring beam's moments too."""
    for cap, stg, swd in ((150, 15, 3), (100, 12, 3), (2500, 24, 5)):
        rr = intze.design(cap, stg, swd)["members"]["raft_ring"]
        assert rr["top"][0] <= 16 and rr["bot"][0] <= 16, (cap, rr)


def _text_faults(dxf):
    """Texts over texts, texts over the drawn lines and texts off the frame, sheets 1 - 3 (the real font's widths)."""
    from ezdxf.fonts import fonts
    font = fonts.make_font("LiberationSans-Regular.ttf", 1.0)
    msp = ezdxf.readfile(dxf).modelspace()
    sw, gap = intze_dwg.SW, intze_dwg.GAP

    def box(t, k=0.0):
        h, w = t.dxf.height, font.text_width(t.dxf.text) * t.dxf.height
        al, p = t.get_placement()[:2]
        n = al.name
        fx = 0.0 if "LEFT" in n else 0.5 if "CENTER" in n else 1.0
        fy = 0.0 if n.startswith("BOTTOM") else 0.5 if n.startswith("MIDDLE") else 1.0
        a = math.radians(t.dxf.rotation or 0.0)
        c = [(-fx * w, -fy * h), ((1 - fx) * w, -fy * h), ((1 - fx) * w, (1 - fy) * h), (-fx * w, (1 - fy) * h)]
        c = [(x * math.cos(a) - y * math.sin(a) + p[0], x * math.sin(a) + y * math.cos(a) + p[1]) for x, y in c]
        mx, my = sum(x for x, _ in c) / 4, sum(y for _, y in c) / 4
        return [(mx + (x - mx) * (1 - k), my + (y - my) * (1 - k)) for x, y in c]

    def apart(A, B):
        for P in (A, B):
            for i in range(4):
                (x1, y1), (x2, y2) = P[i], P[(i + 1) % 4]
                nx, ny = y1 - y2, x2 - x1
                pa, pb = [nx * x + ny * y for x, y in A], [nx * x + ny * y for x, y in B]
                if max(pa) < min(pb) or max(pb) < min(pa):
                    return True
        return False

    def crosses(a, b, P):
        t0, t1 = 0.0, 1.0
        dx, dy = b[0] - a[0], b[1] - a[1]
        cx, cy = sum(x for x, _ in P) / 4, sum(y for _, y in P) / 4
        for i in range(4):
            (x1, y1), (x2, y2) = P[i], P[(i + 1) % 4]
            nx, ny = y1 - y2, x2 - x1
            if nx * (cx - x1) + ny * (cy - y1) < 0:
                nx, ny = -nx, -ny
            num, den = nx * (a[0] - x1) + ny * (a[1] - y1), nx * dx + ny * dy
            if abs(den) < 1e-12:
                if num < 0:
                    return False
                continue
            t = -num / den
            t0, t1 = (max(t0, t), t1) if den > 0 else (t0, min(t1, t))
            if t0 > t1:
                return False
        return (t1 - t0) * math.hypot(dx, dy) > 0.4

    segs = [((e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)) for e in msp.query("LINE")
            if e.dxf.layer in ("OUTLINE", "REBAR", "DIM", "LEVEL", "WATER", "FRAME")]
    for e in msp.query("LWPOLYLINE"):
        if e.dxf.layer in ("OUTLINE", "REBAR", "DIM", "LEVEL", "WATER", "FRAME"):
            pts = [(x, y) for x, y, *_ in e.get_points()] + ([tuple(e.get_points()[0][:2])] if e.closed else [])
            segs += list(zip(pts, pts[1:]))
    texts = [(t, box(t, 0.03), box(t, 0.15)) for t in msp.query("TEXT") if t.dxf.text.strip()]
    bad = []
    for k in range(3):
        ox = k * (sw + gap)
        mine = [x for x in texts if ox - gap / 2 <= sum(p[0] for p in x[1]) / 4 < ox + sw + gap / 2]
        for i, (t, b, bi) in enumerate(mine):
            if any(x < ox + 10 or x > ox + sw - 10 or y < 10 or y > intze_dwg.SH - 10 for x, y in b):
                bad.append(("off", k + 1, t.dxf.text))
            if any(crosses(a, c, bi) for a, c in segs):
                bad.append(("line", k + 1, t.dxf.text))
            bad += [("text", k + 1, t.dxf.text, t2.dxf.text) for t2, b2, _ in mine[i + 1:] if not apart(b, b2)]
    return bad


@pytest.mark.parametrize("cap,stg,swd", [(2500, 24, 5), (150, 15, 3)])
def test_drawing_texts_clear(tmp_path, cap, stg, swd):
    """No text over another, over a drawn line or off the frame on sheets 1 - 3 (user 21-Nov-2026: the drawing as the
    example's, checked), a large tank and a small one."""
    r = intze.design(cap, stg, swd)
    p = intze_dwg.export(r, str(tmp_path), "t", {"name": "OHT-T"}, pdf=False)
    assert _text_faults(p["dxf"]) == []


def test_top_ring_nominal_rest_in_the_wall_top():
    """The top ring beam nominal, 4 - 12 # (as the example), the rest of the dome's pull in the wall's top band of
    hoops (user 22-Nov-2026): beam + band carry the whole pull."""
    r = intze.design(2500, 24, 5)
    tr_, z0 = r["members"]["top_ring"], r["members"]["wall"]["zones"][0]
    assert (tr_["n"], tr_["dia"]) == (4, 12) and tr_["b"] >= 250
    assert tr_["P_ring"] + tr_["P_band"] >= tr_["P"] - 1e-6
    water = intze.GAMMA_W * max(0.0, z0["len"] - r["geo"]["fb"]) * r["geo"]["R"]
    steel = 2 * z0["n"] * intze.area(z0["dia"]) / z0["len"]                  # both faces, mm2 per m
    assert steel * float(r["opt"]["sst_water"]) / 1e3 >= water + tr_["P_band"] / z0["len"] - 1e-6


@pytest.mark.parametrize("cap,stg", [(2500, 24), (150, 12), (1000, 18)])
def test_stair_landing_beams_rest_on_what_is_there(cap, stg):
    """Each landing beam on what it can rest on (user 23-Nov-2026): B1 on a column of the staging only below the
    columns' top, B3 on the cone / balcony up to the balcony, B4 above it on the staircase column alone (never
    through the wall that holds the water), B5 at the roof from the top ring beam; the roof's landing carried on
    flat to the ring beam."""
    r = intze.design(cap, stg, 4)
    st, lev, g = r["members"]["stair"], r["levels"], r["geo"]
    kinds = [x["type"] for x in st["landings"]]
    assert kinds[0] == "B1" and kinds[-1] == "B5" and kinds.count("B5") == 1
    for x in st["landings"]:
        if x["type"] == "B1":
            assert x["z"] - st["beams"]["B1"]["d"] / 2e3 <= lev["B3_bot"]
        if x["type"] == "B4":
            assert st["bal"] < x["z"] < st["roof"]
            assert st["xs"] - st["lc"] > g["R"] + g["th"]["tw"]          # its inner end short of the wall
        if x["type"] == "B3":
            assert lev["B3_bot"] < x["z"] <= st["bal"] + 1e-6 and 0 < x["L"] < st["L1"] + 1e-6
    assert st["beams"]["B5"]["L"] > 0 and st["bridge"]["span"] > 0
    assert kinds == sorted(kinds, key="B1B3B4B5".index)                    # in that order up the staircase
    # every beam in the bar schedule, and the column carries the heavier side
    marks = {row["mark"] for row in r["bbs"]}
    assert all(f"S3-{k}" in marks for k in st["beams"]) and "S9" in marks
    assert st["col"]["P"] < st["col"]["Pcap"] / 1.5
