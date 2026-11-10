"""The DPR workbook in the Riverside format (dpr.py): its sheets, one design row per sewer between two manholes, every
manhole once, SOR rates by VLOOKUP, the zone / population / capacity helpers. (The formulas were checked against the
Riverside estimate itself in Excel, 22-Oct-2026: excavation by slice, road cutting, close timbering, bedding and laying
length by diameter and depth band of its Zone IPS agree to the last digit.)"""
import json
import math

import openpyxl

from sewer_app import dpr, pipeline

from synthetic import INP, synth

quiet = lambda s: None                                                  # noqa: E731


def test_workbook_sheets_rows_and_rates(tmp_path):
    out = pipeline.run(synth(seed=1), INP, log=quiet)
    path = dpr.write_dpr(out, str(tmp_path / "d_DPR.xlsx"), title="TEST SCHEME", inp=INP)
    wb = openpyxl.load_workbook(path)
    zones = sorted(set(dpr.zones_of(out["res"]).values()))
    assert wb.sheetnames == (["Project", "Coverage", "Certificate", "Index", "Form j compre", "Form j civil",
                              "Abstract comprehensive", "ABS civil", "ABS (O&M)", "Sewer Lines and RM", "5 yr O&M",
                              "ECONOMICS", "INCOME", "RECURRING EXP", "REPAIR WORKS", "A.R. EXP ON M. STAFF",
                              "BREAKUP OF COST", "Bar Chart", "Tech", "Population", "BOQ", "Abstract", "Manholes"]
                             + [f"Qty {k}" for k in range(1, len(zones) + 1)]
                             + [f"HY DESIGN STATEMENT_{k}" for k in range(1, len(zones) + 1)]
                             + ["hcc2", "hcc3", "house connection", "Table 160", "sor"])
    rows = dpr.design_rows(out)
    hy = [r for ws in wb.worksheets if ws.title.startswith("HY DESIGN") for r in ws.iter_rows(min_row=dpr.FIRST, values_only=True)
          if r[0]]
    assert len(hy) == len(rows) and abs(sum(r[8] for r in hy) - sum(d["length"] for d in out["res"].values())) < 0.01
    # every manhole of the design once
    mh = [r[1] for r in wb["Manholes"].iter_rows(min_row=5, values_only=True) if isinstance(r[0], int)]
    assert sorted(mh) == sorted(out["node_info"])
    # Qty row = formulas on the HY sheet; road type an input (CC)
    q = wb["Qty 1"]
    assert q.cell(dpr.FIRST, 4).value == "='HY DESIGN STATEMENT_1'!I6" and q.cell(dpr.FIRST, 18).value == 2
    # the finalised rates of sewer_sor_rates.json as they are (user, 22-Oct-2026); an SOR item not there from sheet 'sor'
    with open(dpr.RATES_FILE, encoding="utf-8") as fh:
        sr = json.load(fh)
    bq = wb["BOQ"]
    line = {str(bq.cell(r, 2).value): r for r in range(5, bq.max_row + 1) if bq.cell(r, 2).value}
    for code, rate in [(sr["excavation_ordinary_soil"]["codes"][0], sr["excavation_ordinary_soil"]["rates"][0]),
                       (sr["timbering_open"]["codes"][0], sr["timbering_open"]["rates"][0]),
                       (sr["granular_bedding"]["codes"][1], sr["granular_bedding"]["rates"][1]),
                       (sr["laying_rcc_np3"]["by_nominal_mm"]["200"]["codes"][0],
                        sr["laying_rcc_np3"]["by_nominal_mm"]["200"]["rates"][0]),
                       (sr["road_reinstatement"]["CC"]["code"], sr["road_reinstatement"]["CC"]["rate"])]:
        x = line[code]
        assert bq.cell(x, 6).value == rate and bq.cell(x, 8).value == "sewer_sor_rates.json"
    assert bq.cell(line["3001"], 7).value == f"=E{line['3001']}*F{line['3001']}"
    assert bq.cell(line["3036"], 6).value.startswith("=VLOOKUP(B")
    assert "NOT in sewer_sor_rates.json" in bq.cell(line["Unit Estimate"], 8).value
    sor = {str(r[0]): r[3] for r in wb["sor"].iter_rows(min_row=4, values_only=True) if r[0]}
    assert isinstance(wb["sor"]["A6"].value, int)                  # numeric codes as numbers (template look-ups)
    assert sor["3001"] == 307.02 and abs(sor["106.2"] - 2840.88 * 1.03) < 0.01
    assert wb["Form j civil"]["C7"].value == "='ABS civil'!D9"


def test_settings_have_sources():
    with open(dpr.SETTINGS_FILE, encoding="utf-8") as fh:
        raw = json.load(fh)
    assert all("_source" in v for k, v in raw.items() if not k.startswith("_"))
    s = dpr.settings()
    assert [c["upto_m"] for c in s["manholes"]] == sorted(c["upto_m"] for c in s["manholes"])


def test_zones_population_capacity():
    res = {"a": {"from": "1", "to": "3"}, "b": {"from": "2", "to": "3"}, "c": {"from": "3", "to": "O"},
           "d": {"from": "4", "to": "P"}}
    assert dpr.zones_of(res) == {"a": "O", "b": "O", "c": "O", "d": "P"}
    pop = dpr.contributory_population(res, {"1": 10, "2": 20, "3": 5, "4": 7, "O": 99})
    assert pop == {"a": 10, "b": 20, "c": 35, "d": 7}
    # Manning full bore: 200 mm, 1 in 250, n 0.013 -> 0.0164 m3/s (CPHEEO eq. 3.16)
    q = dpr.full_flow_lpd(200, 1 / 250, 0.013) / 86400000
    assert math.isclose(q, (1 / 0.013) * math.pi * 0.04 / 4 * 0.05 ** (2 / 3) * math.sqrt(1 / 250), rel_tol=1e-9)


def test_pumping_station_sheets(tmp_path):
    """A pumping station gets the Riverside SPS / rising main sheets, with this design's flows, levels and rising main put
    in, its formulas pointing at its own sheets and the SOR look-ups at sheet 'sor'; the abstract sums them."""
    inp = dict(INP, base_year=2027, pop_initial=INP["pop_total"] * 0.5, pop_mid=INP["pop_total"] * 0.75)
    out = pipeline.run(synth(seed=1), inp, log=quiet)
    o = next(iter({d["to"] for d in out["res"].values()} - {d["from"] for d in out["res"].values()}))
    wb = openpyxl.load_workbook(dpr.write_dpr(out, str(tmp_path / "s_DPR.xlsx"), inp=inp,
                                              stations=[{"outfall": o, "dist": 1000}]))
    for n in ("E&M SPS", "SPS O&M", "DESIGN DATA SPS-1", "INLET CHAMBER SPS-1", "WET WELL SPS-1", "SCREEN CHANNEL SPS-1",
              "SCREEN SPS-1", "BOQ SPS-1", "RM SPS-1", "BOQ R.MAIN SPS-1", "HT", "LT", "Plinth Area Rate"):
        assert n in wb.sheetnames
    ult = next(x for s in out["stages"] if s["stage"] == "ult" for x in s["outfalls"] if x["outfall"] == o)
    dd = wb["DESIGN DATA SPS-1"]
    assert dd["D9"].value == round(ult["avg_mld"], 3) and dd["D7"].value == ult["pop"]
    assert wb["INLET CHAMBER SPS-1"]["D11"].value == round(out["node_info"][o]["invert"], 3)
    assert wb["RM SPS-1"]["K5"].value == "='DESIGN DATA SPS-1'!D9*1000" and wb["RM SPS-1"]["D21"].value == 1300.0
    formulas = [c.value for ws in wb.worksheets for row in ws.iter_rows() for c in row
                if isinstance(c.value, str) and c.value.startswith("=")]
    assert not [f for f in formulas if "'Tech '" in f or "MPS'!" in f or "sor!$A$6" in f or "[" in f.split('"')[0]]
    assert "IFERROR(VLOOKUP(N7,sor!" in wb["BOQ SPS-1"]["K7"].value
    assert wb["Abstract comprehensive"]["D7"].value == "=('BOQ SPS-1'!L179)/100000"
    # E&M in the format of the U.P. Jal Nigam E&M estimate R2 (user decision 26-Oct-2026): technical statement on the
    # +15 years flows and the head of sheet RM, estimate, abstract; E&M SPS and the abstract take them by formula
    for n in ("EM rates", "EM TS SPS-1", "EM Est SPS-1", "Abstract E&M SPS-1"):
        assert n in wb.sheetnames
    mid = next(x for s in out["stages"] if s["stage"] == "mid" for x in s["outfalls"] if x["outfall"] == o)
    ts = wb["EM TS SPS-1"]
    assert ts["C4"].value == round(mid["avg_lps"], 2) and ts["C5"].value == round(mid["peak_lps"], 2)
    assert ts["C8"].value == "='RM SPS-1'!I27"
    em = wb["E&M SPS"]
    assert em["B4"].value.startswith("Pumping plants") and em["C4"].value == "='Abstract E&M SPS-1'!D4"
    assert any(isinstance(c.value, str) and c.value.startswith("='E&M SPS'!") for c in wb["Abstract comprehensive"]["D"])
    est = [c.value for c in wb["EM Est SPS-1"]["E"] if isinstance(c.value, str)]
    assert any("'EM rates'!$E$" in v and "'EM TS SPS-1'!" in v for v in est)
    # the look of the UPJN estimates (user decision 26-Oct-2026): Times New Roman, plain headers, A4 printed in black
    # and white with the header rows repeated; the sheets copied from the Riverside estimate keep their fonts
    hy = wb["HY DESIGN STATEMENT_1"]
    assert hy["A6"].font.name == "Times New Roman" and hy["A5"].fill.fill_type is None and hy["A5"].font.b
    ps = hy.page_setup
    assert ps.paperSize == 9 and ps.orientation == "landscape" and ps.blackAndWhite and hy.print_title_rows == "$1:$5"
    assert "BOQ SPS-1" in wb.sheetnames and wb["BOQ SPS-1"].page_setup.paperSize == 9


def test_project_sheet_texts_kept(tmp_path):
    """Every sheet takes the scheme's name from sheet Project; the texts typed there are kept in the next DPR."""
    from sewer_app import population
    f = population.forecast(2027, 5000, [(2001, 3000), (2011, 3800)], sewage_lpcd=INP["sewage_lpcd"])
    inp = dict(INP, base_year=2027, pop_initial=f["design"]["init"], pop_mid=f["design"]["mid"],
               pop_total=f["design"]["ult"], forecast=f)
    out = pipeline.run(synth(seed=1), inp, log=quiet)
    first = dpr.write_dpr(out, str(tmp_path / "a_DPR.xlsx"), title="A SCHEME", inp=inp)
    wb = openpyxl.load_workbook(first)
    assert wb["BOQ"]["A1"].value == "=Project!$C$4" and wb["Project"]["C4"].value == "A SCHEME"
    assert any(r[1] == 2001 for r in wb["Project"].iter_rows(values_only=True))           # the census of the page
    wb["Project"]["C4"] = "MY SCHEME"
    wb["Project"]["C6"] = "SPRINGFIELD"
    wb.save(first)
    second = openpyxl.load_workbook(dpr.write_dpr(out, str(tmp_path / "b_DPR.xlsx"), title="A SCHEME", inp=inp,
                                                  previous=first))
    assert second["Project"]["C4"].value == "MY SCHEME" and second["Project"]["C6"].value == "SPRINGFIELD"
    tech = [c.value for row in second["Tech"].iter_rows() for c in row if isinstance(c.value, str)]
    assert any("CEILING(" in v and "^" in v for v in tech)                  # the geometrical method as a formula
