"""Water DPR workbook in the format of the Elmwood estimate (user decisions 26-Oct-2026): made with every water design,
every formula's sheet exists, the OHT / CWR of the technical statement as the zoning (max(33 %, mass balance)), the
SOR codes are in sheet sor, the unit estimates of the template are in, the Project texts are kept the next time."""
import os
import re

import openpyxl
import pytest

from water_app import dpr as wdpr
from water_app import server as wserver
from water_app import ui_api

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE = os.path.join(HERE, "samples", "sample_area.kml")
REF = re.compile(r"(?:'((?:[^']|'')+)'|([A-Za-z_][\w\.]*))!")


@pytest.fixture
def design(tmp_path, monkeypatch):
    monkeypatch.setattr(wserver, "PROJECTS", str(tmp_path / "p"))
    monkeypatch.setattr(wserver, "OUT_ROOT", str(tmp_path / "o"))
    with open(SAMPLE, encoding="utf-8") as fh:
        kml = fh.read()
    r = wserver.run_layout("wdpr", kml, gl_mode="spots", snap=1, spacing=100)
    m = min(r["manholes"], key=lambda x: x["latlng"][0] + x["latlng"][1])          # a corner
    old = {"name": "OLD-1", "lat": m["latlng"][0], "lng": m["latlng"][1], "capacity_kl": 300, "staging_m": 22,
           "tubewells": 4, "rebore": 1}

    def run(**kw):
        req = dict({"name": "wdpr", "ohts": [old], "pop_factor": 3, "base_year": 2027, "pop_initial": 20000,
                    "pop_mid": 24000}, **kw)
        d = ui_api.run_design("wdpr", req)
        assert d["ok"] and d["files"].get("dpr"), d.get("log")
        return d
    return run


def test_dpr_sheets_and_formulas(design):
    d = design()
    path = d["files"]["dpr"]
    assert path.endswith("_DPR.xlsx") and os.path.isfile(path)
    wb = openpyxl.load_workbook(path)
    names = set(wb.sheetnames)
    assert wb.sheetnames[0] == "Project" and wb.sheetnames[-1] == "R SOR 2025-26"
    for n in ("T10 OZ Demand", "T11 Mass Balance", "T12 Tube Wells", "T13 OZ Summary", "D1 Pipe & Road", "D2 DS Estimate",
              "D3 DS Summary", "D4 House Conn", "S1 OHT Abstract", "S2 CWR", "ABS Com", "ABS Civil", "Breakup",
              "Form J Com.", "Form J Civil", "5Yr O&M Com", "Economics", "Salient feature", "U01 SV Rate",
              "U12 Road Reinstate", "U16 Thrust 250"):
        assert n in names, n
    # the technical sheets and after (user request 30-Oct-2026): group letter + number + name, in that order, the
    # front sheets (up to Cess) as the Elmwood
    # the title pages ECONOMICS and TECHNICAL STATEMENT (Riverside water DPR p59, p67; user 7-Nov-2026)
    assert wb.sheetnames.index("Title - Economics") == wb.sheetnames.index("Economics") - 1
    assert wb.sheetnames.index("Title - Technical") == wb.sheetnames.index("Cess") + 1
    tech = wb.sheetnames[wb.sheetnames.index("Title - Technical") + 1:]
    # the technical statement starts with the population projection (p68), made with no census given too
    # the example technical.xlsx's order first (user decision 9-Nov-2026): T1 Population, its T2-T9, then T10-T21
    nums = [int(re.match(r"T(\d+)", s).group(1)) for s in tech if s[0] == "T"]
    assert tech[0] == "T1 Population" and nums == sorted(nums) and tech[1] == "T4 Zone Population"
    tp = wb["T1 Population"]
    assert tp["A5"].value == "TECHNICAL STATEMENT" and any(
        c.value == "DESIGN PERIOD:" for c in tp["A"]) and any(str(c.value).startswith("=IFERROR(") for c in tp["K"])
    groups = [s[0] for s in tech]
    assert groups == sorted(groups, key="TDSCEUR".index) and tech[-1] == "R SOR 2025-26"
    ix = {wb["Index"].cell(r, 2).value: wb["Index"].cell(r, 5).value for r in range(6, 22)}
    assert ix["TECHNICAL STATEMENT"].startswith("T1 Population, T4 Zone Population, T5 DMA Demand") and "T10 OZ Demand, T11 Mass Balance" in ix["TECHNICAL STATEMENT"] and "T14-01 " in ix["TECHNICAL STATEMENT"]
    assert ix["SCHEDULE OF RATES"] == "R SOR 2025-26" and ix["UNIT ESTIMATES"].startswith("U01 SV Rate")
    oht1 = next(n for n in wb.sheetnames if n.startswith("S1-01 "))
    sor = {str(c.value) for c in wb["R SOR 2025-26"]["A"] if c.value is not None}
    for ws in wb:
        for row in ws.iter_rows():
            for c in row:
                v = c.value
                if not (isinstance(v, str) and v.startswith("=")):
                    continue
                assert "#REF" not in v and "[" not in v, (ws.title, c.coordinate, v)
                for a, b in REF.findall(v):
                    assert (a or b).replace("''", "'") in names, (ws.title, c.coordinate, v)
                for code in re.findall(r"VLOOKUP\((\d+),'R SOR 2025-26'!", v):
                    assert code in sor, (ws.title, c.coordinate, code)
    # every OZ of the design has its technical statement, an existing OHT no new one, the new one an estimate
    out = {o["name"]: o for o in d["outlets"]}
    t3 = {wb[n]["D5"].value: wb[n] for n in names if n.startswith("T14-")}
    assert set(t3) == set(out)
    # storage: the larger of 33 % / mass balance on the demand without fire + a third of the fire (S.No.13)
    assert t3["OLD-1"]["F30"].value.endswith("*Project!$C$" + t3["OLD-1"]["F30"].value.rsplit("$", 1)[1])
    assert t3["OLD-1"]["F31"].value == "=MAX(F28,F29)+F30"
    assert t3["OLD-1"]["F32"].value == 300 and "IF(F32>0,0," in t3["OLD-1"]["F33"].value
    # CWR by the UPJN rule on the NEW tube wells only, the proposed of sheet TW (user decision 27-Oct-2026: the
    # existing ones - 4 given on the page - stay with the existing structures)
    k_old = int(t3["OLD-1"].title[4:6])                                   # "T14-01 OLD-1"
    assert t3["OLD-1"]["F38"].value == f"='T12 Tube Wells'!L{5 + k_old}"
    assert wb["T12 Tube Wells"][f"C{5 + k_old}"].value == 4 and wb["T12 Tube Wells"][f"B{5 + k_old}"].value == "OLD-1"
    assert t3["OLD-1"]["F39"].value.startswith("=IF(F38>Project!")
    # where a CWR (C.2) the tube wells fill it, lifting to the ground level (Riverside water DPR p136-195: TW to CWR
    # staging 0, depth 0 - user decision 6-Nov-2026); its own pumps lift to the OHT (R3 'H P Calculation pp': tube
    # wells of its CWR zones 37 m, of the others 64-72 m)
    T = t3["OLD-1"]
    assert T["B42"].value.startswith("Water level of the CWR above ground") and T["F42"].value == "=IF(F39>0,0,0)"
    tot = next(r for r in range(44, 70) if T.cell(r, 2).value == "Total head")
    assert T["B43"].value == "Head of the CWR pumps (to the OHT)"
    # staging + OHT depth + terminal + the CWR's sump 7 m + friction of the CWR - OHT main (DPR 'CWR to OHT', 6-Nov-2026)
    assert T["F43"].value == f"=IF(F39>0,ROUNDUP(F{tot - 4}+F{tot - 3}+F{tot - 1}+7+0.5,0),0)"
    assert T.cell(tot - 4, 2).value == "Staging of OHT" and T.cell(tot - 4, 6).value == 22
    # the tube well's water 15 m below GL + seasonal 5 m + depression 4.5 m, the motor margin by its kW (CPHEEO table
    # of the Riverside water DPR p360) - user decisions 6-Nov-2026
    assert [T.cell(tot - k, 6).value for k in (7, 6, 5)] == [15, 5, 4.5]
    mg = next(r for r in range(tot, tot + 12) if T.cell(r, 2).value == "Margin on the motor")
    assert T.cell(mg, 6).value == (f"=IF(F{mg - 1}*0.746<=1.5,0.5,IF(F{mg - 1}*0.746<=3.7,0.4,IF(F{mg - 1}*0.746<=7.5,"
                                   f"0.3,IF(F{mg - 1}*0.746<=15,0.2,IF(F{mg - 1}*0.746<=75,0.15,0.1)))))")
    # the technical statement as the Riverside water DPR (p88-201): DMAs, water & tube wells, mass balance of each OHT,
    # the pipe table (no ward on this layout: no T8)
    for n in ("T17 DMA Population", "T18 Water & Tube Wells", "T19 OHT Mass Balance", "T21 Pipe Table"):
        assert n in names, n
    assert "T16 Ward Population" not in names
    # the example technical.xlsx 'Tech3'-'Tech7' (user decision 9-Nov-2026: five sheets of their own, households =
    # population / persons per connection): DMA-wise demand, its zone totals, OHT details, DMA / zone households
    for n in ("T5 DMA Demand", "T6 Zone Summary", "T7 OHT Details", "T8 DMA Pop & HH", "T9 Zone Households"):
        assert n in names, n
    assert tech.index("T5 DMA Demand") == tech.index("T4 Zone Population") + 1
    dd = wb["T5 DMA Demand"]
    assert dd["A3"].value == "DMA WISE DEMAND" and dd["A8"].value == "Operation zone OLD-1"
    assert dd["A10"].value == "OLD-1/DMA-1" and dd["B10"].value == "-" and dd["A11"].value == "Total"
    assert dd["M10"].value.startswith("=D10*Project!") and dd["T10"].value == "=M10+P10+$S10"
    assert dd["S10"].value == "=IFERROR('T10 OZ Demand'!$Y$6*F10/'T10 OZ Demand'!$F$6,0)"
    assert dd["W10"].value.startswith("=ROUNDUP(D10/Project!")
    zs = wb["T6 Zone Summary"]
    assert zs["B8"].value == "OLD-1" and zs["C8"].value == "='T5 DMA Demand'!D11" and zs["X8"].value == "='T5 DMA Demand'!Y11"
    od = wb["T7 OHT Details"]
    assert od["B6"].value == "OLD-1" and od["C6"].value.startswith("=IF('T14-01 OLD-1'!F32=0,") and od["H6"].value == "Existing OHT at OLD-1"
    assert od["E6"].value == "='T14-01 OLD-1'!F31"
    assert wb["T8 DMA Pop & HH"]["B9"].value == "=SUM('T5 DMA Demand'!D10:D10)"
    assert wb["T9 Zone Households"]["F8"].value == "='T6 Zone Summary'!V8"
    t10 = wb["T18 Water & Tube Wells"]
    assert k_old == 1 and t10["B5"].value == "Operation zone OLD-1"                   # the first block: OLD-1
    req = {}
    for r in t10.iter_rows(min_row=5, max_row=29, values_only=True):
        req.setdefault(r[1], r)
    assert req["Population"][2:5] == (f"='T10 OZ Demand'!D{6 + k_old - 1}", f"='T10 OZ Demand'!E{6 + k_old - 1}",
                                      f"='T10 OZ Demand'!F{6 + k_old - 1}")
    assert req["No. of tube wells proposed (sheet T12 Tube Wells: for +15 years)"][2] == f"='T12 Tube Wells'!L{5 + k_old}"
    assert T.cell(tot, 6).value == (f"=IF(F39>0,F{tot - 7}+F{tot - 6}+F{tot - 5}+F42+F{tot - 2}+F{tot - 1},"
                                    f"SUM(F{tot - 7}:F{tot - 1}))")
    assert wb[oht1]["M5"].value.endswith("!F33")
    # OHT / CWR rate: U.P. Jal Nigam standard cost FY 2022-23 per litre, linear between capacities, escalated
    assert "'S3 OHT-UGR Rates'!" in wb[oht1]["M7"].value and "MATCH(M5," in wb[oht1]["M7"].value
    assert any(isinstance(c.value, str) and "'S3 OHT-UGR Rates'!$C$" in c.value for c in wb["S2 CWR"]["E"])
    R = wdpr.settings()["oht_ugr_rates"]
    assert wdpr.table_rate(850, R["capacity_kl"], R["oht_per_l"]) == 15.625
    assert wdpr.table_rate(100, R["capacity_kl"], R["ugr_per_l"]) == 18.0
    assert wdpr.table_rate(5000, R["capacity_kl"], R["oht_per_l"]) == 12.0
    # the pipe lengths of the design, by OZ and size, in sheet RC
    total = sum(p["length"] for p in d["pipes"] if p["size"])
    rc = sum(c.value for c in wb["D1 Pipe & Road"]["D"] if isinstance(c.value, (int, float)))      # 80.0 m is read back as 80
    assert abs(rc - total) < 1.0
    # house connections, DS and the abstracts tied together
    assert wb["D2 DS Estimate"].cell(6, 3).value.startswith("Supply of following sizes of pipes")
    assert any(isinstance(c.value, str) and "'D4 House Conn'!$F$8" in c.value for c in wb["D2 DS Estimate"]["K"])
    assert any(isinstance(c.value, str) and "'D2 DS Estimate'!$K$" in c.value for c in wb["ABS Com"]["D"])
    # maintenance staff: CPHEEO Part C Table 3.5 p32, valve men with assistant 1 per 2000 connections of the stage
    st = wb["A.Ex. Staff"]
    assert [st[c].value for c in ("C6", "F6", "I6")] == [f"=ROUNDUP(Income!{c}10/2000,0)" for c in "CDE"]
    assert wb["Income"]["B10"].value == "No. of household connections"
    # E&M in the format of the U.P. Jal Nigam E&M estimate Riverside R3 (user decisions 26-Oct-2026): per OZ from the
    # design (new tube wells of sheet TW, motors of T3, the outlet, the VFD booster, CWR pumps), into ABS Com,
    # the power line, the 5 year O&M and the electricity of the economics
    for n in ("E3 EM Rates", "E1 EM Tech Stmt", "ABS E&M", "E2 EM O&M"):
        assert n in names, n
    ts = wb["E1 EM Tech Stmt"]
    row = next(r for r in range(6, 6 + len(out)) if ts.cell(r, 2).value == "OLD-1")
    k = row - 6
    assert ts.cell(row, 3).value == f"='T12 Tube Wells'!O{6 + k}" and ts.cell(row, 4).value.endswith("!F61")
    # standby tube wells (CPHEEO 5.7.5) and rebored ones (user decisions 7-Nov-2026): sheet TW N = standby of the
    # working L, O = L + N built, P = rebored (from the map), giving as existing ones
    tw4, y = wb["T12 Tube Wells"], 6 + k
    assert tw4[f"N{y}"].value == f"=IF(L{y}<=0,0,IF(L{y}<=2,1,IF(L{y}<=5,2,3)))" and tw4[f"O{y}"].value == f"=L{y}+N{y}"
    assert tw4[f"P{y}"].value == 1 and tw4[f"F{y}"].value.startswith(f"=(C{y}+P{y})*D{y}")
    assert (ts.cell(row, 20).value, ts.cell(row, 21).value) == (f"='T12 Tube Wells'!N{y}", f"='T12 Tube Wells'!P{y}")
    em2 = [r for r in wb["ABS E&M"].iter_rows(values_only=True) if isinstance(r[1], str)]
    assert any(r[1].startswith('="Rebore of tube well "') for r in em2)
    assert any(r[1].startswith("Connection, laying & replacement of old LT cable for rebored TW") for r in em2)
    c1 = [str(c.value) for c in wb["C1 Pump House"]["C"] if c.value]
    assert any("GIRDER PILLAR FOR REBORED TUBE WELL" in v for v in c1)
    assert any(isinstance(c.value, str) and c.value == f"='T12 Tube Wells'!P{y}" for c in wb["C1 Pump House"]["D"])
    assert ts.cell(row, 13).value.endswith("!F41")                        # new CWR of the T3 (4 tube wells)
    assert ts.cell(row, 17).value.endswith("!F43,0)")                     # CWR pump head: T3 C.6
    # standby pumps by the working ones as CPHEEO 5.7.5 (user decision 7-Nov-2026): 1-2 W + 1, 3-5 + 2, 6-10 + 3
    for w, s in (("J", 11), ("N", 15)):                                   # booster J -> K, CWR N -> O
        assert ts.cell(row, s).value == f"=IF({w}{row}<=0,0,IF({w}{row}<=2,1,IF({w}{row}<=5,2,3)))"
    abs_d = [c.value for c in wb["ABS Com"]["D"] if isinstance(c.value, str)]
    # the quantities as the Riverside water DPR p45 ("48 Nos", "15 Job"; user 7-Nov-2026), no "as sheet ..."
    abs_c = [str(c.value) for c in wb["ABS Com"]["C"] if c.value is not None]
    assert not any("as sheet" in v for v in abs_c) and any(v.endswith('&" Nos"') and "'E1 EM Tech Stmt'!" in v
                                                            for v in abs_c)
    assert sum(1 for v in abs_d if v.startswith("='ABS E&M'!$F$")) == 12     # 11 parts + the power connections
    # Riverside water DPR (6-Nov-2026): the DMA equipment of every DMA by its line size (p55), Form J (E&M works) (p48),
    # the checklist for submission (p21-23)
    em = list(wb["ABS E&M"].iter_rows(values_only=True))
    dma = [r for r in em if r[1] and "line size DMA equipment for" in str(r[1])]
    assert sum(r[2] for r in dma) == sum(o["dmas"] for o in d["outlets"])           # one a DMA
    assert all("'E3 EM Rates'!" in r[4] for r in dma)
    # contingency: a lump sum, Rs 50 lakh as the DPR p44 / p46 (yellow), the same in Form J Civil
    fc = {r[1]: r for r in wb["Form J Com."].iter_rows(min_row=7, max_row=16, values_only=True) if r[1]}
    assert fc["Contingency (lump sum)"][2] == 50 and fc["Contingency (lump sum)"][3] is None
    cr = next(r for r in range(7, 17) if wb["Form J Com."].cell(r, 2).value == "Contingency (lump sum)")
    civ = {r[1]: r for r in wb["Form J Civil"].iter_rows(min_row=6, max_row=12, values_only=True) if r[1]}
    assert civ["Contingency (lump sum, Form J Com.)"][2] == f"='Form J Com.'!$E${cr}"
    fe = {r[1]: r for r in wb["Form J E&M"].iter_rows(min_row=6, values_only=True) if r[1]}
    assert fe["Total cost of works"][2].startswith("='ABS Com'!$D$")
    assert fe["Centage on total"][3] == 0.08 and fe["Departmental proficiency on sub total"][3] == 0.05
    assert fe["New power connections"][2].startswith("='ABS Com'!$D$")
    assert fe["5 year electricity charges during O&M"][4].startswith("=ROUND('E2 EM O&M'!$F$")
    assert wb.sheetnames.index("Form J E&M") == wb.sheetnames.index("ABS Civil") + 1
    # the E&M abstract of cost after Form J E&M, then the breakup (Riverside water DPR p48-56, user 7-Nov-2026)
    assert wb.sheetnames.index("ABS E&M") == wb.sheetnames.index("Form J E&M") + 1 == wb.sheetnames.index("Breakup") - 1
    # the front pages as the final Riverside water DPR (user request 7-Nov-2026): cover p20, checklist p21-23,
    # certificate p24, coverage p25, title pages p35 / p37 / p42 / p43, salient features p38-41 on four pages
    assert wb.sheetnames[1:12] == ["Cover", "Checklist", "Certificate", "Coverage", "Title - Index", "Index",
                                   "Title - Salient", "Salient feature", "Title - Project Report", "Title - Financial",
                                   "Form J Com."]
    sal = wb["Salient feature"]
    # laid out as the user's example (salient feature example.xlsx, 7-Nov-2026): columns A-M, a break before 6
    assert len(sal.row_breaks.brk) == 1 and sal["A5"].value == "SALIENT FEATURES" and sal.print_area == f"'Salient feature'!$A$1:$M${sal.max_row}"
    assert wb["Title - Salient"]["A24"].value == "SALIENT FEATURES" and wb["Cover"].page_setup.fitToHeight == 1
    assert any(isinstance(c.value, str) and c.value.startswith("=IF(COUNTIFS('T15 Rising Main'!$C$")
               for row in sal.iter_rows() for c in row)
    ck = {r[0]: r[2] for r in wb["Checklist"].iter_rows(min_row=6, values_only=True) if r[0]}
    assert ck["6.3"] == "=Project!$C$" + ck["6.3"].rsplit("$", 1)[1] and ck["16.0"] == "=Economics!C8"
    assert ck["10.0"].startswith("='T14-") and ck["1.5"] == "2025-26"
    # the O&M for 5 years as the Riverside water DPR p57: electricity, O&M without it, cess, GST, centage 7 %
    assert wb["5Yr O&M Com"]["D17"].value.startswith("=ROUND('E2 EM O&M'!$F$") and wb["5Yr O&M Com"]["B21"].value == "Centage@7%"
    assert wb["5 Yr O&M Civil"]["B19"].value == "Centage @ 7 %" and wb["5Yr O&M Com"]["D23"].value == "=D13+D22"
    assert wb["Electicity"]["C6"].value.startswith("='E2 EM O&M'!$F$")
    assert any(isinstance(c.value, str) and "'E3 EM Rates'!" in c.value and "MATCH(" in c.value for c in wb["ABS E&M"]["E"])
    # the E&M design sheets of the Riverside water DPR p319-361 give the cost (user decision 6-Nov-2026): the tube
    # well, the CWR's transformers, the trial runs and the power connections of sheet ABS E&M from them
    e_sheets = ["E4 TW Design", "E5 TW Estimate", "E6 HP & Transformer", "E7 CWR Electrical", "E8 Power Connection",
                "E9 Trial Run"]
    assert [s for s in wb.sheetnames if s[:1] == "E" and s[1:2].isdigit()][3:] == e_sheets
    assert all(s in ix["ESTIMATES OF E&M WORKS"] for s in e_sheets)
    col = 5 + k                                                        # OZ OLD-1's column of the design sheets
    tw = {wb["E4 TW Design"].cell(r, 2).value: wb["E4 TW Design"].cell(r, col).value for r in range(6, 70)}
    assert tw["Discharge required of a tube well (sheet T12 Tube Wells)"] == f"='E1 EM Tech Stmt'!$S${row}"
    assert ts.cell(row, 19).value == f"='T12 Tube Wells'!I{6 + k}"
    est = list(wb["E5 TW Estimate"].iter_rows(values_only=True))
    gravel = next(r for r in est if r[1] and str(r[1]).startswith("1.60 mm to 4.80 mm"))
    assert gravel[3] == 7000 and str(gravel[col - 1]).startswith("='E4 TW Design'!")
    assert any(r[0] == "1.2.3" and r[3] == 5386.5 for r in est)                        # 300 mm M.S. pipe
    lines = {str(r[1]): r for r in em[:30] if r[1]}
    tw_line = next(v for t, v in lines.items() if "Construction of tube well" in t)
    assert tw_line[4].startswith("='E5 TW Estimate'!$") and "'E4 TW Design'!" in tw_line[1]
    assert lines["Three months trial run of tube wells (new and rebored)"][4].startswith("='E9 Trial Run'!$")
    assert lines["New power connection with transmission line for CWR"][4].startswith("='E8 Power Connection'!$")
    assert "New power connection with transmission line for booster pumping plant" in lines
    sub = next(v for t, v in lines.items() if t.startswith('="LT / HT panels with sub-station for CWR"'))
    assert "'E7 CWR Electrical'!$" in sub[4] and "'E3 EM Rates'!" in sub[4]
    # the look of the UPJN estimates (user decision 26-Oct-2026): Times New Roman, plain headers, yellow inputs on the
    # screen only (printed black and white), A4 fitted to the width with the header rows repeated
    fj = wb["Form J Com."]
    assert fj["B7"].font.name == "Times New Roman" and fj["B5"].fill.fill_type is None and fj["B5"].font.b
    assert str(fj["F6"].fill.fgColor.rgb).endswith("FFF2CC")
    ps = fj.page_setup
    assert ps.paperSize == 9 and ps.blackAndWhite and ps.fitToWidth == 1 and fj.print_title_rows == "$1:$5"
    assert wb["U01 SV Rate"]["B3"].font.name != "Times New Roman" and wb["U01 SV Rate"].page_setup.paperSize == 9
    # the other civil works of the Riverside water DPR (user decision 6-Nov-2026): their sheets (group C), the
    # repairs of the existing OHT, the shifted house connections, the unit estimates of the Elmwood after the old ones
    for n in ("C1 Pump House", "C2 Site Development", "C3 Staff Quarters", "C4 GW Recharge", "C5 MCS Building",
              "C6 Panel Rooms", "S4-01 Rep OLD-1", "D6 Shift HC", "U23 Unit Rates", "U25 Pump House", "U41 GW Recharge",
              "U44 Booster Room"):
        assert n in names, n
    assert "C1 Pump House" in ix["ESTIMATES OF CIVIL WORKS"] and "S4-01 Rep OLD-1" in ix["ESTIMATES OF CIVIL WORKS"]
    civ = [r[1] for r in wb["ABS Com"].iter_rows(min_row=7, max_row=19, values_only=True)]
    assert civ[:3] == ["Pump house cum chlorination room", "Construction of new RCC overhead tanks",
                       "Repairing of existing RCC overhead tanks"] and civ[-2:] == ["Water Treatment Plant",
                                                                                     "Feeder Main and appurtenant works"]
    abs_c = {r[1]: r for r in wb["ABS Com"].iter_rows(values_only=True) if r[1]}
    assert abs_c["Repairing of existing RCC overhead tanks"][3].startswith("='S1 OHT Abstract'!$E$")
    assert abs_c["Pump house cum chlorination room"][3] == "='C1 Pump House'!$K$" + \
        abs_c["Pump house cum chlorination room"][3].rsplit("$", 1)[1]
    ph = list(wb["C1 Pump House"].iter_rows(values_only=True))
    assert any(r[3] == f"='T12 Tube Wells'!C{5 + k_old}" and r[8] == "='U34 PH Repair'!K181*100000" for r in ph)
    rep = next(r for r in wb["S1 OHT Abstract"].iter_rows(values_only=True) if r[1] == "For operation zone OLD-1")
    assert rep[3] == "300 KL / 22 M" and rep[4].startswith("='S4-01 Rep OLD-1'!$K$")
    assert "750 KL / 20 m" in str(wb["S4-01 Rep OLD-1"].cell(wb["S4-01 Rep OLD-1"].max_row - 2, 2).value)
    assert any(isinstance(c.value, str) and "'D6 Shift HC'!$F$8" in c.value for c in wb["D2 DS Estimate"]["K"])
    assert wb["C6 Panel Rooms"]["C7"].value.startswith("=COUNTIF('E1 EM Tech Stmt'!$M$")


def test_tube_well_estimate_as_the_riverside_dpr():
    """The unit estimate of a tube well of the Riverside water DPR p319-320, its quantities (housing 60 m, assembly 190
    m, drilling 210 m, pea gravel 67 m3) at the rates of the settings: Rs 23,79,962. The DPR's own total (23,73,962)
    adds item 4.2 as Rs 1,22,880 (44,880 + 6,000 + 78,000 = 1,28,880). The design (sheet E5) gives 68 m3 of gravel."""
    R = wdpr.settings()["em_design"]["tw_rates"]
    fixed = sum(q * r for *_, q, r in R["items"])
    pipes = 60 * R["pipe"]["300"] + 130 * R["pipe"]["200"]
    drill = 65 * R["drill"]["upto 100 m"]["600"] + 35 * R["drill"]["upto 100 m"]["500"] +         110 * R["drill"]["below 100 m"]["500"]
    lower = 60 * R["lower"]["upto 100 m"]["300"] + 40 * R["lower"]["upto 100 m"]["200"] +         90 * R["lower"]["below 100 m"]["200"]
    assert (pipes, drill + 24300 + 30000, lower + 60000) == (807570, 519300, 120100)       # DPR sub totals
    assert round(fixed + pipes + drill + lower + 67 * R["gravel"], 2) == 2373962 + 6000


def test_oht_repair_measurements_as_the_riverside_dpr():
    """The two repair estimates of the Riverside water DPR (p256-262), summed item by item: 750 KL Rs 15,18,569.53,
    1500 KL Rs 16,56,480.69. The DPR's own totals (16.32 / 17.71 lakh) count the sealing of the joints (Rs 1,10,307.63)
    and the acrylic grout (Rs 3,599.75 / 4,114.00) twice - its plaster sub total adds the joints' sub total."""
    from math import prod
    S = wdpr.settings()["oht_repair"]
    rt = S["rates"]
    for k, want, dpr in (("750", 1518569.53, 1632476.92), ("1500", 1656480.69, 1770902.32)):
        T = S[k]
        m = lambda rows: sum(prod(v for v in r[1:5] if v is not None) for r in rows)
        sc = m(T["scrape"])
        tot = (m(T["scaffold"]) * rt["scaffold"] + m(T["joints"]) * rt["joints"] + m(T["plaster"]) * rt["plaster"] +
               sum(kg * r for kg, r in zip(T["grout_kg"], rt["grout"])) +
               sum(prod(r[1:5]) * r[5] for r in T["slurry_v"] + T["slurry_h"]) + T["ladder_qtl"] * rt["ladder"] +
               sum(rt[j] for j in ("balcony", "railing", "ventilator", "wli", "manhole", "sv_chamber_repair",
                                   "sv_chamber", "cleaning", "pipe_paint")) +
               sum(L * r for _, L, r in T["pipes"]) + sc * (rt["scrape"] + rt["paint"]))
        assert tot == pytest.approx(want, abs=0.01)
        assert dpr - tot == pytest.approx(m(T["joints"]) * rt["joints"] + T["grout_kg"][0] * rt["grout"][0], abs=0.02)


def test_dpr_as_the_example_technical_statement(design):
    """The technical statement in the example technical.xlsx's order (user decisions 9-Nov-2026): T1 Population with
    four Excel charts (census bars, simple graph, semi-log, the methods compared), T2 Town Wards from the town's list of
    the page, T3 Ward Projection, T4 Zone Population, T5-T9, then T10-T21; the WTP's load left out."""
    import zipfile
    from water_app import city_wards as cw
    town = [{"no": "1", "name": "Riverside", "pop": 37040, "hh": 4645, "area": 132.0, "census": 17204, "char": ""},
            {"no": "3", "name": "Ashford", "pop": 41898, "hh": 5966, "area": 356.58, "census": 22096, "char": ""},
            {"no": "77", "name": "Exeter", "pop": 19467, "hh": 3603, "area": 21.69, "census": 13345, "char": ""}]
    cw.save({"city": "Springfield City Council", "year": 2025, "rows": town}, "t.xlsx")
    # a character with no ward in the town: its 0 is a number - Far-open still balanced
    wt = {"year": 2025, "citylist": "Springfield City Council",
          "rows": [{"no": "1", "name": "Riverside", "pop": "37040", "cov": "50", "area": "132"},
                   {"no": "3", "name": "Ashford", "pop": "41898", "cov": "20", "area": "356.58"}],
          "city": {"Saturated (Core)": 19467, "High (Proximal Developed)": 0, "Medium (Proximal Developing)": 37040,
                   "Low (Far-open)": 41898}}
    census = "1951 376534, 1961 498567, 1971 672634, 1981 825717, 1991 1139236, 2001 1374963, 2011 1636569"
    d = design(ward_table=wt, projection={"base_pop": "", "census": census, "method": "geometrical"})
    assert d["projection"]["far_open"]["factors"][2] > 1
    path = d["files"]["dpr"]
    wb = openpyxl.load_workbook(path)
    n = wb.sheetnames
    i = n.index("Title - Technical")
    assert n[i + 1:i + 6] == ["T1 Population", "T2 Town Wards", "T3 Ward Projection", "T4 Zone Population", "T5 DMA Demand"]
    assert n.index("T9 Zone Households") < n.index("T10 OZ Demand") < n.index("T21 Pipe Table") < n.index("D1 Pipe & Road")
    tw = wb["T2 Town Wards"]
    assert tw["A3"].value == "WARD WISE POPULATION OF SPRINGFIELD CITY COUNCIL"
    rows = {r[2]: r for r in tw.iter_rows(min_row=6, max_row=8, values_only=True)}
    # the character by the density on the Eq. area: Riverside 280.6 Medium, Ashford 117.5 Low, Exeter 897.5 Saturated
    assert {k: v[8] for k, v in rows.items()} == {"Riverside": "Medium (Proximal Developing)",
                                                   "Ashford": "Low (Far-open)", "Exeter": "Saturated (Core)"}
    g = wb["T16 Ward Population"]
    fo = next(c.row for c in g["B"] if c.value == "Low (Far-open)")
    assert rows["Ashford"][13] == f"=ROUND(D7*'T16 Ward Population'!$F${fo},0)"
    assert str(g.cell(fo, 6).value).startswith("=(F")                       # balanced to the adopted projection
    assert any(c.value == "G TOTAL" for c in tw["C"])
    wp = wb["T3 Ward Projection"]
    assert wp["A3"].value == "WARD WISE POPULATION PROJECTION" and wp["C8"].value == "='T16 Ward Population'!K7"
    txt = {str(c.value) for row in wp.iter_rows() for c in row if c.value}
    assert "TABLE SHOWING POPULATION OF SPRINGFIELD CITY COUNCIL" in txt and not any("WTP" in t and "LOAD" in t for t in txt)
    zp = wb["T4 Zone Population"]
    assert zp["A3"].value == "ZONE WISE POPULATION" and zp["A8"].value == "Operation zone OLD-1"
    # the four charts, on T1 Population's data (added after the sheets are renamed)
    with zipfile.ZipFile(path) as z:
        charts = sorted(x for x in z.namelist() if x.startswith("xl/charts/chart"))
        xml = [z.read(x).decode("utf-8") for x in charts]
    assert len(charts) == 4 and all("'T1 Population'!" in x for x in xml)
    assert sum("barChart>" in x for x in xml) == 1 and sum("scatterChart>" in x for x in xml) == 3
    assert any('logBase val="10"' in x for x in xml)


def test_dpr_storage_as_zoning(design):
    """The Storage sheet: the page's filling hours, its result the share the zoning used (38.5 % for 8 h)."""
    from water_app import demand as dm
    d = design(oht_inflow="4-8, 16-20")
    wb = openpyxl.load_workbook(d["files"]["dpr"])
    st = wb["T11 Mass Balance"]
    fill = [st.cell(6 + h, 3).value for h in range(24)]
    assert sum(fill) == 8 and fill[4] == 1 and fill[3] == 0 and fill[16] == 1
    crit = ui_api._crit({"oht_inflow": "4-8, 16-20"})
    share = dm.storage_share(crit)
    assert round(share, 3) == 0.385
    city = sum(o["population"] for o in d["outlets"])
    new = next(o for o in d["outlets"] if o["proposed"])
    d_ = dm.daily_kl(new["population"], crit, city)
    need = share * (d_["total"] - d_["fire"]) + d_["fire"] / 3          # + a third of the fire (S.No.13)
    assert new["required_kl"] % 50 == 0 and need - 1 <= new["required_kl"] < need + 50


def test_dpr_project_texts_kept(design):
    d = design()
    wb = openpyxl.load_workbook(d["files"]["dpr"])
    ws = wb["Project"]
    row = next(r for r in range(1, 40) if ws.cell(r, 2).value == "Name of the ULB / town")
    ws.cell(row, 3, "Springfield City Council")
    wb.save(d["files"]["dpr"])
    d2 = design()                               # (the same file name within a minute: read before it is written)
    ws2 = openpyxl.load_workbook(d2["files"]["dpr"])["Project"]
    assert ws2.cell(row, 3).value == "Springfield City Council"


def test_dpr_info_valves():
    """Sluice valves of the network: every closed boundary pipe and DMA inlet of its size, one at each OHT outlet."""
    from water_app.design import load_criteria
    zones = [{"name": "A", "population": 1000, "connections": 167, "demand_kld": 200, "capacity_kl": None,
              "required_kl": 100, "cwr_kl": None, "tubewells": 0, "dma_count": 2}]
    pipes = [{"label": "P-1", "size": "HDPE 110", "length": 100, "oz": "A"},
             {"label": "P-2", "size": "DI 200", "length": 50.5, "oz": "A"},
             {"label": "P-3", "size": "HDPE 110", "length": 20, "oz": "A"}]
    outlets = [{"name": "A", "size": "DI 250", "proposed": True, "staging_m": 18, "flow": 5}]
    info = wdpr.dpr_info(zones, pipes, outlets, [{"name": "A/DMA-2", "zone": "A", "inlet_pipe": "P-2"}], ["P-1"],
                         {}, load_criteria(), "x")
    assert info["valves"]["A"] == {100: 1, 200: 1, 250: 1}
    assert info["length"]["A"] == {"HDPE 110": 120, "DI 200": 50.5} and info["sizes"] == ["HDPE 110", "DI 200"]
    assert info["zones"][0]["proposed"] and not info["zones"][0]["existing"]
