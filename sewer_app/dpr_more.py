"""The rest of the sewer DPR workbook (dpr.py) as in the Riverside estimate - user, 22-Oct-2026: house connections, the
SPS, the rising main, O&M for 5 years and the economics are all in that estimate; take them from there.

    population(B)            sheet Population: the stages' population and households (Riverside 'Tech ' rows 113-126)
    house_connections(B)     hcc2, hcc3, house connection, Table 160
    pumping_stations(B, st)  per pumping station the Riverside sheets DESIGN DATA SPS, INLET CHAMBER, WET WELL, SCREEN
                             CHANNEL, SCREEN, BOQ SPS, RM SPS, BOQ R.MAIN (data/dpr_sps_template.xlsx - their formulas
                             and layout, with this design's flows, levels and rising main put in) + HT, LT, Plinth Area
                             Rate once; the E&M of each station in the format of the U.P. Jal Nigam E&M estimate R2
                             (dpr_em.py: technical statement, estimate, abstract) and sheet 'E&M SPS' of all
    om(B, ...)               SPS O&M, 5 yr O&M, Sewer Lines and RM, ABS (O&M)
    economics(B)             ECONOMICS, INCOME, RECURRING EXP, REPAIR WORKS, A.R. EXP ON M. STAFF, BREAKUP OF COST
    form_j_compre(B)         Form j compre
B = the workbook context of dpr.write_dpr (wb, title, styles, settings S, out, inp, cells of the BOQ rates, ...).
"""
import os
import re
from copy import copy

from . import DATA_DIR, dpr_em, rising_main

TEMPLATE = os.path.join(DATA_DIR, "dpr_sps_template.xlsx")
STAGES = ("init", "mid", "ult")
ROADS = ["B.O.E", "C.C Roads", "Bitumin road", "Bitumin road pwd", "Interlocking tiles", "Kaccha Road"]
SHEET_REF = re.compile(r"(?:'((?:[^']|'')+)'|([A-Za-z_][\w\.]*))!")
SOR_LOOKUP = re.compile(r"VLOOKUP\(([^,()]+),sor!\$A\$6:\$D\$1509,4,0\)")


def q(name):
    """A sheet name as written in a formula."""
    return "'" + name.replace("'", "''") + "'"


# ---------------------------------------------------------------------------------------------------------- population
def population(B, T, PR):
    """Population and households of the stages, from the Technical statement (T = dpr_front.tech cells, PR = Project
    cells) - for the house connections and the economics."""
    ws = B.sheet("Population", "POPULATION AND HOUSEHOLDS (stages: CPHEEO Table 2.1, p2-9)", 6)
    B.header(ws, 4, ["S.No.", "Description", "Base year", "Middle year (+15)", "Design year (+30)", "Note"],
             [6, 48, 15, 15, 15, 60])
    rows = [("Year", [f"={PR[k]}" for k in ("base_year", "mid_year", "design_year")], "0", "sheet Project"),
            ("Population (adopted, without floating)", [f"={c}" for c in T["pop"]], "#,##0", "sheet Tech"),
            ("Persons per household", [f"={PR['hh_size']}"] * 3, "0.00", "sheet Project"),
            ("Households", [f"={c}" for c in T["hh"]], "#,##0", "sheet Tech")]
    for i, (name, vals, fmt, note) in enumerate(rows):
        x = 5 + i
        ws.cell(x, 1, i + 1)
        ws.cell(x, 2, name)
        for j, v in enumerate(vals):
            ws.cell(x, 3 + j, v).number_format = fmt
        ws.cell(x, 6, note)
    ws.cell(9, 1, 5)
    ws.cell(9, 2, "Sewer house connections (households of the base year)").font = B.bold
    ws.cell(9, 3, "=C8").number_format = "#,##0"
    ws.cell(9, 6, "as Riverside 'Tech ' L126 -> hcc2")
    for row in ws.iter_rows(min_row=4, max_row=9, max_col=6):
        for cell in row:
            cell.border = B.box
    return {"pop": ["Population!C6", "Population!D6", "Population!E6"],
            "hh": ["Population!C8", "Population!D8", "Population!E8"], "hc": "Population!C9",
            "years": ["Population!C5", "Population!D5", "Population!E5"]}


# ---------------------------------------------------------------------------------------------------- house connections
def house_connections(B, P):
    H = B.S["house_connection"]
    shares = H["road_shares"]
    cut = [str(H["boe_cut_rate"]), f"={B.boq['cc_cut']}", f"={B.boq['bt_cut']}", f"={B.boq['bt_cut']}",
           f"={B.boq['il_cut']}", "0"]
    reinst = [str(H["boe_reinstate_rate"]), f"={B.boq['cc_re']}", f"={B.boq['bt_re']}", f"={B.boq['bt_re']}",
              f"={B.boq['il_re']}", "0"]

    # hcc2: number of connections by road type
    h2 = B.sheet("hcc2", "Calculation for Number of House connections.", 6)
    h2.cell(3, 1, "Total number of households sewer connection in this estimate").font = B.bold
    h2.cell(3, 4, f"={P['hc']}").number_format = "#,##0"
    h2.cell(3, 5, "Nos")
    B.header(h2, 5, ["Type of Road", "Share", "Connections (110 mm HDPE)"], [40, 12, 24])
    for i, (name, sh) in enumerate(shares):
        x = 6 + i
        h2.cell(x, 1, name)
        c = h2.cell(x, 2, sh)
        c.fill, c.number_format = B.yellow, "0.00%"
        h2.cell(x, 3, f"=$D$3*B{x}").number_format = "#,##0.00"
    t = 6 + len(shares)
    h2.cell(t, 1, "Total House Connections").font = B.bold
    h2.cell(t, 2, f"=SUM(B6:B{t - 1})").number_format = "0.00%"
    h2.cell(t, 3, f"=SUM(C6:C{t - 1})").number_format = "#,##0"
    h2.cell(t + 1, 1, "No. of direct house sewer connections")
    h2.cell(t + 1, 3, 0)
    h2.cell(t + 2, 1, "No. of connections through H.C.C.")
    h2.cell(t + 2, 3, f"=C{t}").number_format = "#,##0"
    share = {i: f"hcc2!$B${6 + i}" for i in range(len(shares))}

    # hcc3: dismantling, H.C.C. and the connection items
    h3 = B.sheet("hcc3", "SEWER HOUSE CONNECTION", 9)
    B.header(h3, 3, ["S. No.", "Name of Work", "Nos.", "", "Unit", "Qty. for each", "Total Qty.", "Rate", "Amount in Rs."],
             [6, 46, 12, 6, 8, 10, 12, 10, 16])
    r = 4
    h3.cell(r, 1, 1)
    h3.cell(r, 2, "Dismantling of different type of road surfaces:-")
    r += 1
    sections = [("A", "For sewer connection by 110 mm dia pipe from house to H.C.C.", "=hcc2!$D$3", H["area_house_to_hcc_sqm"]),
                ("B", "For construction of H.C.C.", f"=hcc2!$D$3/{H['connections_per_hcc']}", H["area_hcc_sqm"]),
                ("C", "For sewer line from H.C.C. to M.H.", None, H["area_hcc_to_mh_sqm"])]
    first_amt, count_row = r, {}
    for tag, name, cnt, area in sections:
        h3.cell(r, 1, tag)
        h3.cell(r, 2, name)
        h3.cell(r, 3, cnt if cnt else f"=C{count_row['B']}").number_format = "#,##0"
        h3.cell(r, 4, "Nos.")
        count_row[tag] = r
        top = r
        r += 1
        for i, rn in enumerate(ROADS):
            h3.cell(r, 2, f"{rn} ({shares[i][1] * 100:g} %)")
            h3.cell(r, 3, f"=$C${top}*{share[i]}").number_format = "#,##0.00"
            h3.cell(r, 4, "Nos.")
            h3.cell(r, 5, "sqm")
            a = h3.cell(r, 6, area)
            a.fill = B.yellow
            h3.cell(r, 7, f"=F{r}*C{r}").number_format = "#,##0.00"
            rt = h3.cell(r, 8, cut[i])
            if not cut[i].startswith("="):
                rt.value = float(cut[i])
                rt.fill = B.yellow
            h3.cell(r, 9, f"=H{r}*G{r}").number_format = "#,##0.00"
            r += 1
    items = [(2, f"Construction of house connecting chambers for {H['connections_per_hcc']} connections of size "
                 f"0.6 x 0.6 x 0.75 m", f"=C{count_row['B']}", H["hcc_rate"]),
             (3, "Making domestic sewer connection using 110 mm HDPE pipe PN-6, PE-100", f"=C{count_row['A']}",
              H["domestic_connection_rate"]),
             (4, "Laying of sewer line from house connecting chambers to M.H. using 160 mm HDPE pipe PN-6, PE-100",
              f"=C{count_row['B']}", H["line_160_rate"]),
             (5, f"Sewer inter connecting chamber to intercept the waste water from toilet, kitchen and bathroom "
                 f"0.3 x 0.3 x 0.45 m ({H['interceptor_share'] * 100:g} % of the connections)",
              f"=C{count_row['A']}*{H['interceptor_share']}", H["interceptor_rate"])]
    for sn, name, qty, rate in items:
        h3.cell(r, 1, sn)
        h3.cell(r, 2, name).alignment = B.wrap
        h3.cell(r, 5, "No.")
        h3.cell(r, 7, qty).number_format = "#,##0"
        c = h3.cell(r, 8, rate)
        c.fill = B.yellow
        h3.cell(r, 9, f"=G{r}*H{r}").number_format = "#,##0.00"
        r += 1
    h3.cell(r, 2, "Total").font = B.bold
    h3.cell(r, 9, f"=SUM(I{first_amt}:I{r - 1})").number_format = "#,##0.00"
    hcc3_total = f"hcc3!I{r}"
    h3.cell(r + 2, 2, "Yellow: Riverside DPR values (hcc3 unit rates, areas, road shares; B.O.E rate) - not in "
                      "sewer_sor_rates.json, to be confirmed. Other rates: sheet BOQ.").font = B.italic

    # house connection: reinstatement of the roads
    hr = B.sheet("house connection", "Reinstatement of road", 10)
    B.header(hr, 3, ["S. no", "Name of Work", "Nos.", "", "Unit", "Qty. for each", "Total Qty.", "Rate per sqm",
                     "Amount in Rs.", ""], [6, 46, 12, 6, 8, 10, 12, 12, 16, 4])
    hr.cell(4, 1, 1)
    hr.cell(4, 2, "Permanent reinstatement of road required for making house connections as per the road types:-")
    r = 5
    first = r
    for tag, name, cnt, area in (("A", "For sewer connection from house to H.C.C.", "=hcc2!$D$3", H["area_house_to_hcc_sqm"]),
                                 ("B", "For sewer line from H.C.C. to M.H.", f"=hcc3!C{count_row['C']}",
                                  H["area_hcc_to_mh_sqm"])):
        hr.cell(r, 1, tag)
        hr.cell(r, 2, name)
        hr.cell(r, 3, cnt).number_format = "#,##0"
        top = r
        r += 1
        for i, rn in enumerate(ROADS):
            hr.cell(r, 2, f"{rn} ({shares[i][1] * 100:g} %)")
            hr.cell(r, 3, f"=$C${top}*{share[i]}").number_format = "#,##0.00"
            hr.cell(r, 4, "Nos.")
            hr.cell(r, 5, "sqm")
            hr.cell(r, 6, area).fill = B.yellow
            hr.cell(r, 7, f"=C{r}*F{r}").number_format = "#,##0.00"
            rt = hr.cell(r, 8, reinst[i])
            if not reinst[i].startswith("="):
                rt.value = float(reinst[i])
                rt.fill = B.yellow
            hr.cell(r, 9, f"=G{r}*H{r}").number_format = "#,##0.00"
            r += 1
    hr.cell(r, 8, "Total").font = B.bold
    hr.cell(r, 9, f"=SUM(I{first}:I{r - 1})").number_format = "#,##0.00"
    hr.cell(r + 1, 8, "Total (in lakhs)").font = B.bold
    hr.cell(r + 1, 9, f"=I{r}/100000").number_format = "#,##0.00"
    reinst_lakh = f"'house connection'!I{r + 1}"

    # Table 160: the cost
    tb = B.sheet("Table 160", "COST OF HOUSE CONNECTION", 3)
    B.header(tb, 3, ["S.No.", "Description of work", "Amount (Rs. in Lacs)"], [6, 70, 18])
    tb.cell(4, 1, 1)
    tb.cell(4, 2, "Sewer house connections including one H.C.C for two domestic connections for sewer house "
                  "connections to M.H.").alignment = B.wrap
    tb.cell(4, 3, f"={hcc3_total}/100000").number_format = "#,##0.00"
    tb.cell(5, 1, 2)
    tb.cell(5, 2, "Reinstatement of Road")
    tb.cell(5, 3, f"={reinst_lakh}").number_format = "#,##0.00"
    tb.cell(6, 2, "Total").font = B.bold
    tb.cell(6, 3, "=SUM(C4:C5)").number_format = "#,##0.00"
    return {"amount_lakh": "'Table 160'!C6", "count": "hcc2!D3"}


# ---------------------------------------------------------------------------------------------------- pumping stations
def station_data(out, stations):
    """Per pumping station: its outfall, GL, invert, depth, diameter of the incoming sewer, and per stage (base / +15 /
    +30) the population, average flow (MLD) and peak flow (L/s) at that outfall (pipeline.stage_table)."""
    res, info = out["res"], out["node_info"]
    by = {st["stage"]: {o["outfall"]: o for o in st["outfalls"]} for st in out.get("stages") or []}
    rows = []
    for s in stations:
        o = s["outfall"]
        i = info.get(o, {})
        inc = [d["D"] for d in res.values() if d["to"] == o]
        st = {}
        for tag in STAGES:
            x = by.get(tag, {}).get(o) or by.get("ult", {}).get(o)
            st[tag] = {"pop": x["pop"], "avg_mld": x["avg_mld"], "avg_lps": x["avg_lps"], "peak_lps": x["peak_lps"],
                       "given": o in by.get(tag, {})} if x else None
        if not st["ult"]:
            continue
        rows.append({"outfall": o, "gl": i.get("ground"), "invert": i.get("invert"), "depth": i.get("depth"),
                     "dia": max(inc) if inc else 300, "dist": s.get("dist"), "stages": st})
    return rows


def _copy_cell(c, d):
    if c.has_style:
        d.font, d.border, d.fill = copy(c.font), copy(c.border), copy(c.fill)
        d.number_format, d.alignment, d.protection = c.number_format, copy(c.alignment), copy(c.protection)


def _copy_sheet(B, src, name, names):
    """Template sheet src -> new sheet `name`; formulas with the sheet names mapped (names) and the SOR look-ups on this
    workbook's sheet 'sor' (a code not in the SOR counts 0, as the blank look-ups of the template)."""
    ws = B.wb.create_sheet(name)
    B.copied.add(name)                                  # keeps the estimate's fonts (dpr_format: page setup only)

    def sub(m):
        s = (m.group(1) or m.group(2)).replace("''", "'")
        return q(names[s]) + "!" if s in names else m.group(0)

    for row in src.iter_rows():
        for c in row:
            v = c.value
            if isinstance(v, str) and v.startswith("="):
                v = SHEET_REF.sub(sub, v)
                v = SOR_LOOKUP.sub(lambda m: f"IFERROR(VLOOKUP({m.group(1)},{B.sor_rng},4,0),0)", v)
            elif isinstance(v, str) and v.strip() == "#REF!":
                v = None
            if v is None and not c.has_style:
                continue
            d = ws.cell(c.row, c.column, v)
            _copy_cell(c, d)
    for m in src.merged_cells.ranges:
        ws.merge_cells(str(m))
    for k, dim in src.column_dimensions.items():
        if dim.width:
            ws.column_dimensions[k].width = dim.width
        ws.column_dimensions[k].hidden = dim.hidden
    for k, dim in src.row_dimensions.items():
        if dim.height:
            ws.row_dimensions[k].height = dim.height
    return ws


def pumping_stations(B, stations):
    """The pumping-station sheets for every station (station_data). Returns {"civil": [Rs cells], "rm": [Rs lakh
    cells], "em": {component: [Rs lakh cells]}, "power": [Rs lakh cells], "names": [...], "sheets": [...], ...}."""
    import openpyxl
    if not stations:
        return None
    tpl = openpyxl.load_workbook(TEMPLATE)
    shared = {"HT": "HT", "LT": "LT", "Plinth Area Rate": "Plinth Area Rate"}
    for n in shared:
        _copy_sheet(B, tpl[n], n, shared)
    K = rising_main.load_rates()
    ref = {"civil": [], "civil_lakh": [], "rm": [], "power": [], "em": {}, "names": [], "sheets": [], "stations": [],
           "rm_sheet": [], "ww_sheet": [], "em_total": []}
    y0 = B.inp.get("base_year")
    years = [int(y0) + a if y0 else None for a in (0, 15, 30)]
    em_in = []
    for k, s in enumerate(stations, 1):
        tag = f"SPS-{k}"
        names = {"DESIGN DATA SPS": f"DESIGN DATA {tag}", "INLET CHAMBER SPS": f"INLET CHAMBER {tag}",
                 "WET WELL MPS": f"WET WELL {tag}", "SPS Screen Channel ": f"SCREEN CHANNEL {tag}",
                 "SCREEN": f"SCREEN {tag}", "BOQ SPS1": f"BOQ {tag}", "RM SPS - 1": f"RM {tag}",
                 "BOQ R.MAIN": f"BOQ R.MAIN {tag}", **shared}
        made = {old: _copy_sheet(B, tpl[old], new, names) for old, new in names.items() if old not in shared}
        st = s["stages"]
        dd, ic, ww = made["DESIGN DATA SPS"], made["INLET CHAMBER SPS"], made["WET WELL MPS"]
        rm, br, bs = made["RM SPS - 1"], made["BOQ R.MAIN"], made["BOQ SPS1"]
        # design data: this station's flows (pipeline.stage_table) in place of the 'Tech ' sheet
        for x, lab, tg in ((5, "base year", "init"), (6, "+15 years", "mid"), (7, "+30 years (design)", "ult")):
            dd.cell(x, 2, f"Population ({lab})")
            c = dd.cell(x, 4, st[tg]["pop"])
            c.number_format = "#,##0"
            if not st[tg]["given"]:
                c.fill = B.yellow
        dd.cell(8, 2, f"Design Year- {years[2]}" if years[2] else "Design Year (+30)")
        dd.cell(18, 2, f"Middle Year- {years[1]}" if years[1] else "Middle Year (+15)")
        dd.cell(28, 2, f"Base Year- {years[0]}" if years[0] else "Base Year")
        for x, tg in ((9, "ult"), (19, "mid"), (29, "init")):
            c = dd.cell(x, 4, round(st[tg]["avg_mld"], 3))
            if not st[tg]["given"]:
                c.fill = B.yellow
        pf = st["ult"]["peak_lps"] / st["ult"]["avg_lps"] if st["ult"]["avg_lps"] else 2.25
        dd.cell(13, 4, round(pf, 2))
        dd.cell(13, 6, "peak / average at this outfall in the design (CPHEEO Table 3.2 by contributory population)")
        for x in (9, 10, 11, 12, 13, 14, 15, 16, 17, 19, 20, 21, 22, 23, 24, 25, 26, 27, 29, 30, 31, 32, 33, 34, 35, 36,
                  37):
            for cc in (8, 10, 12, 13):                     # the template's checks against an older version
                dd.cell(x, cc).value = None
        dd.cell(2, 1, f"{tag} at {s['outfall']}").font = B.bold
        for x in range(7, 12):                             # wet well: the years of this design, not the sample's
            v = ww.cell(x, 2).value
            if isinstance(v, str):
                ww.cell(x, 2, v.replace("2056", str(years[2] or "+30")).replace("2041", str(years[1] or "+15")))
        # inlet chamber: the incoming sewer of the design
        ic.cell(9, 4, int(round(s["dia"])))
        ic.cell(11, 4, round(s["invert"], 3) if s["invert"] is not None else 0)
        ic.cell(11, 6, f"invert of the incoming sewer at {s['outfall']} (design)")
        ic.cell(12, 4, round(s["gl"], 3) if s["gl"] is not None else 0)
        # rising main: flows from the design data, size and length of this design
        qp = st["ult"]["peak_lps"]
        n_rm, dia, _v = rising_main.size(qp, K)
        L = (s["dist"] or 0) * K["design"]["route_factor"]["value"]
        rm.cell(1, 2, f"Design/Sizing of Rising Main from {tag} ({s['outfall']}) to STP")
        for col_, src in (("E", "D29"), ("H", "D19"), ("K", "D9")):
            rm[f"{col_}5"] = f"={q(dd.title)}!{src}*1000"
        for col_ in ("F", "I", "L"):
            rm[f"{col_}6"] = f"={q(dd.title)}!$D$13"
        c = rm.cell(13, 4, dia)
        c.fill = B.yellow
        c = rm.cell(21, 4, round(L, 1))
        c.fill = B.yellow
        rm.cell(21, 13, ("straight distance to the STP x route factor "
                         f"{K['design']['route_factor']['value']} (rising_main_rates.json)") if s["dist"] else
                "STP not given - put the length of the rising main in")
        if n_rm > 1:
            rm.cell(13, 13, f"{n_rm} parallel mains needed at {K['design']['max_velocity_mps']['value']} m/s "
                            f"(rising_main_rates.json) - one main of this size here")
        # BOQ of the rising main: the finalised DI rates of rising_main_rates.json
        br["A1"] = B.title
        br["A2"] = f"Cost estimate for R.M. FROM {tag} ({s['outfall']}) TO STP"
        sup = K["pipe_supply_di_k7"]["by_dia_mm"][str(dia)]["rate"]
        lay = (K["laying_di"]["by_dia_mm"].get(str(dia)) or {}).get("rate", 0)
        sf = K["specials_fraction"]["value"]
        br["J13"] = f"={sup}+{lay}+{sf}*{sup}"
        for cc in ("L13", "M13", "N13", "O13"):
            br[cc] = None
        br["C13"] = (f"Providing, supplying, laying, jointing and field testing {dia} mm D.I. K-7 pressure pipes (IS 8329) "
                     f"with specials - supply M.193, laying SOR, specials {sf * 100:g} % (rising_main_rates.json)")
        br["J10"] = f"={B.boq['disposal']}"
        br["J15"] = f"={B.boq['bt_re']}+{B.boq['bt_cut']}"
        bs["A2"] = f" Estimate for PROPOSED {tag} at {s['outfall']}"
        # E&M (dpr_em.py, R2 format): pumps on the +15 years flows (CPHEEO Table 2.1 p2-9), head from sheet RM
        em_in.append({"tag": tag, "outfall": s["outfall"], "q_avg": st["mid"]["avg_lps"], "q_peak": st["mid"]["peak_lps"],
                      "given": st["mid"]["given"], "rm_sheet": rm.title})
        ref["civil"].append(f"{q(bs.title)}!L179")
        ref["civil_lakh"].append(f"{q(bs.title)}!L180")
        ref["rm"].append(f"{q(br.title)}!K18")
        ref["names"].append(tag)
        ref["stations"].append(s)
        ref["rm_sheet"].append(rm.title)
        ref["ww_sheet"].append(ww.title)
        ref["sheets"] += [made[o].title for o in ("DESIGN DATA SPS", "INLET CHAMBER SPS", "WET WELL MPS",
                                                  "SPS Screen Channel ", "SCREEN", "BOQ SPS1", "RM SPS - 1", "BOQ R.MAIN")]
    ref["sheets"] += list(shared)

    # E&M of the stations: technical statement, estimate and abstract of each (dpr_em.py), sheet E&M SPS
    er = dpr_em.write(B, em_in)
    ref.update(em=er["em"], em_total=er["em_total"], power_total=er["power_total"])
    ref["sheets"] += er["sheets"]
    return ref


# ------------------------------------------------------------------------------------------------------------------ O&M
def om(B, ps, ac):
    """SPS O&M, 5 yr O&M, Sewer Lines and RM, ABS (O&M). ac = cells of Abstract comprehensive. Returns the cells Form J
    and the economics use."""
    blocks, sps_elec = _sps_om(B, ps)
    tot = _om_5_years(B, ps, blocks)
    _om_civil(B, ac)
    _om_abstract(B, tot)
    out = {"sps_elec": sps_elec} if ps else {}
    out.update({"civil_om": "'ABS (O&M)'!E13", "total_om": "'ABS (O&M)'!G19"})
    return out


def _sps_om(B, ps):
    """Sheet SPS O&M: the yearly electricity, D.G. set and operation of each pumping station -> (the rows of each
    station by what they hold, the cells of the electricity by stage); ([], None) with no pumping station."""
    O = B.S["om"]
    blocks = []
    if not ps:
        return blocks, None
    so = B.sheet("SPS O&M", "EXPENDITURE ON OPERATION AND MAINTENANCE OF THE PUMPING STATIONS (per year)", 6)
    B.header(so, 3, ["", "Particulars", "Base year", "Middle year (+15)", "Design year (+30)", "Note"],
             [4, 56, 15, 15, 15, 60])
    r = 4
    for k, (tag, rmn, wwn) in enumerate(zip(ps["names"], ps["rm_sheet"], ps["ww_sheet"])):
        so.cell(r, 2, f"{tag} ({ps['stations'][k]['outfall']})").font = B.bold
        r += 1
        b = {}
        rows = [("kw", "Pumps working at the average flow (kW)", [f"={q(rmn)}!{c}31" for c in "EHK"],
                 "sheet RM: kW at the average flow of the stage (efficiency there)"),
                ("kwh", "Energy (kWh / year) = kW x 24 x 365", None, ""),
                ("conn", "Connected load (kW) = pumps at peak x installed / working",
                 [f"={q(rmn)}!{c}31*{q(wwn)}!$D$39/{q(wwn)}!$D$40" for c in "FIL"], "sheet WET WELL D39 / D40"),
                ("fixed", f"Fixed charges (Rs lakh) = connected kW x Rs {O['power_fixed_rs_per_kw_month']} x 12", None,
                 "Riverside 'STP (O&M)' row 24"),
                ("run", f"Running charges (Rs lakh) = kWh x Rs {O['power_rate_rs_per_kwh']}", None, "Riverside 'STP (O&M)' rows 29-35"),
                ("duty", f"Electricity duty {O['electricity_duty'] * 100:g} % + regulatory surcharge "
                         f"{O['regulatory_surcharge'] * 100:g} %", None, "Riverside 'STP (O&M)' rows 38-39"),
                ("elec", "Electricity (Rs lakh / year)", None, ""),
                ("dg", f"D.G. set: diesel {O['dg_litre_per_kva_hour']} l / kVA / h x {O['dg_hours_per_day']} h x 365 x "
                       f"Rs {O['diesel_rs_per_litre']} (kVA = connected kW / 0.8) + lubricant "
                       f"{O['lubricant_share'] * 100:g} % + servicing Rs {O['dg_servicing_lakh']} lakh", None,
                 "Riverside 'STP (O&M)' rows 43-47"),
                ("op", "Operation (staff) (Rs lakh / year)", None, "Riverside SPS-1 '5 yr O&M' C22 - to be confirmed")]
        for key, name, vals, note in rows:
            so.cell(r, 2, name)
            so.cell(r, 6, note)
            for j in range(3):
                c = B.col(3 + j)
                f = {"kw": vals[j] if vals else None, "conn": vals[j] if vals else None,
                     "kwh": f"={c}{b.get('kw')}*24*365",
                     "fixed": f"={c}{b.get('conn')}*{O['power_fixed_rs_per_kw_month']}*12/100000",
                     "run": f"={c}{b.get('kwh')}*{O['power_rate_rs_per_kwh']}/100000",
                     "duty": f"=({c}{b.get('fixed')}+{c}{b.get('run')})*({O['electricity_duty']}+{O['regulatory_surcharge']})",
                     "elec": f"={c}{b.get('fixed')}+{c}{b.get('run')}+{c}{b.get('duty')}",
                     "dg": (f"={c}{b.get('conn')}/0.8*{O['dg_litre_per_kva_hour']}*{O['dg_hours_per_day']}*365*"
                            f"{O['diesel_rs_per_litre']}/100000*(1+{O['lubricant_share']})+{O['dg_servicing_lakh']}"),
                     "op": O["sps_operation_lakh_per_year"] if j == 0 else f"=$C{r}"}[key]
                cell = so.cell(r, 3 + j, f)
                cell.number_format = "#,##0.00"
                if key == "op" and j == 0:
                    cell.fill = B.yellow
            b[key] = r
            r += 1
        blocks.append(b)
        r += 1
    return blocks, ["+".join(f"'SPS O&M'!{c}{b['elec']}" for b in blocks) for c in "CDE"]


def _om_5_years(B, ps, blocks):
    """Sheet 5 yr O&M of the E&M (Rs lakh) -> the cells of its 5-year totals by kind."""
    O = B.S["om"]
    fy = B.sheet("5 yr O&M", "OPERATION AND MAINTENANCE OF THE PUMPING STATIONS FOR 5 YEARS (Rs. lakh)", 10)
    B.header(fy, 3, ["S.No.", "Particulars", "Basic cost", "1st year", "2nd year", "3rd year", "4th year", "5th year",
                     "Total of 5 years", "Remark"], [6, 40, 12, 11, 11, 11, 11, 11, 14, 52])
    r = 4
    tot = {"mach": [], "elec": [], "dg": [], "op": []}
    for k, b in enumerate(blocks):
        fy.cell(r, 1, ps["names"][k]).font = B.bold
        r += 1
        specs = [("mach", "Cost of machinery and SCADA automation", f"={ps['em_total'][k]}",
                  f"=ROUND(C{{r}}*{O['machinery_maintenance']},2)", f"*(1+{O['inflation']})",
                  f"maintenance {O['machinery_maintenance'] * 100:g} % of the machinery, inflation "
                  f"{O['inflation'] * 100:g} %; total from year {O['dlp_years'] + 1} (defect liability)"),
                 ("elec", "Cost of electric bills per year", f"='SPS O&M'!C{b['elec']}", "=C{r}", "", "no inflation"),
                 ("dg", "Cost of diesel and lubrication for D.G. set", f"='SPS O&M'!C{b['dg']}", "=C{r}", "",
                  "no inflation"),
                 ("op", "Operation cost", f"='SPS O&M'!C{b['op']}", "=C{r}", f"*(1+{O['operation_increase']})",
                  f"+{O['operation_increase'] * 100:g} % a year")]
        for key, name, basic, y1, grow, note in specs:
            fy.cell(r, 2, name)
            fy.cell(r, 3, basic).number_format = "#,##0.00"
            fy.cell(r, 4, y1.format(r=r)).number_format = "#,##0.00"
            for j in range(1, 5):
                fy.cell(r, 4 + j, f"={B.col(3 + j)}{r}{grow}").number_format = "#,##0.00"
            first = B.col(4 + O["dlp_years"]) if key == "mach" else "D"
            fy.cell(r, 9, f"=SUM({first}{r}:H{r})").number_format = "#,##0.00"
            fy.cell(r, 10, note)
            tot[key].append(f"'5 yr O&M'!I{r}")
            r += 1
        r += 1
    return tot


def _om_civil(B, ac):
    """Sheet Sewer Lines and RM: the O&M of the civil works (Rs lakh)."""
    O = B.S["om"]
    sl = B.sheet("Sewer Lines and RM", "Cost of Annual O&M Cost for CIVIL WORKS (Rs. lakh)", 6)
    B.header(sl, 4, ["S.N", "District", "Estimated Cost", f"Annual repairs of RM & sewer @ {O['sewer_rm_repair'] * 100:g} %",
                     f"Annual repairs of C.W. @ {O['civil_works_repair'] * 100:g} %", "Total"], [6, 44, 16, 18, 18, 14])
    items = [("Sewer Network", ac["sewer"], "D"), ("House Connection", ac["hc"], "D"), ("Rising Main", ac["rm"], "D"),
             ("SPS", ac["sps"], "E")]
    for i, (name, cell, which) in enumerate(items):
        x = 5 + i
        sl.cell(x, 1, i + 1)
        sl.cell(x, 2, name)
        sl.cell(x, 3, f"={cell}").number_format = "#,##0.00"
        sl.cell(x, 4 if which == "D" else 5,
                f"=C{x}*{O['sewer_rm_repair'] if which == 'D' else O['civil_works_repair']}").number_format = "#,##0.00"
        sl.cell(x, 6, f"=D{x}+E{x}").number_format = "#,##0.00"
    sl.cell(9, 2, "Cost of O&M of civil works for 1st year").font = B.bold
    sl.cell(9, 6, "=SUM(F5:F8)").number_format = "#,##0.00"
    sl.cell(10, 2, f"Inflation is taken @ {O['inflation'] * 100:g} % per year")
    sl.cell(10, 3, "Sewer, RM & house connections")
    sl.cell(10, 4, "SPS")
    for y in range(5):
        x = 11 + y
        sl.cell(x, 1, f"Year {y + 1}")
        if y == 0:
            sl.cell(x, 3, "=F5+F6+F7")
            sl.cell(x, 4, "=F8")
        else:
            sl.cell(x, 2, O["inflation"] * 100)
            sl.cell(x, 3, f"=C{x - 1}*(1+B{x}%)")
            sl.cell(x, 4, f"=D{x - 1}*(1+B{x}%)")
        sl.cell(x, 6, f"=C{x}+D{x}")
        for c in (3, 4, 6):
            sl.cell(x, c).number_format = "#,##0.00"
    sl.cell(16, 3, "=SUM(C11:C15)").number_format = "#,##0.00"
    sl.cell(16, 4, "=SUM(D12:D15)").number_format = "#,##0.00"
    sl.cell(16, 6, "=C16+D16").number_format = "#,##0.00"
    sl.cell(17, 2, "Cost of O&M for civil works for 5 years in Rs lakh (SPS from the 2nd year, as Riverside)").font = B.bold
    sl.cell(17, 6, "=F16").number_format = "#,##0.00"


def _om_abstract(B, tot):
    """Sheet ABS (O&M): the O&M of 5 years, civil and E&M."""
    O = B.S["om"]
    ab = B.sheet("ABS (O&M)", "Abstract of 5 Years O&M Cost (CIVIL + E&M) (Rs. lakh)", 7)
    B.header(ab, 4, ["S.N", "", "Description", "", "CIVIL", "E&M", "O&M cost for 5 years"], [6, 14, 30, 10, 14, 14, 18])
    sm = lambda cells: ("=" + "+".join(cells)) if cells else 0                      # noqa: E731
    lines = [(1, "Maintenance", "Sewer, RM & house connections", "='Sewer Lines and RM'!C16", 0),
             (2, "", "SPS", "='Sewer Lines and RM'!D16", sm(tot["mach"])),
             (3, "", "Staff (operation)", None, sm(tot["op"])),
             (4, "Operation", "Power (SPS)", None, sm(tot["elec"])),
             (5, "", "Diesel (SPS)", None, sm(tot["dg"]))]
    for i, (sn, grp, name, civ, em) in enumerate(lines):
        x = 5 + i
        ab.cell(x, 1, sn)
        ab.cell(x, 2, grp)
        ab.cell(x, 3, name)
        if civ:
            ab.cell(x, 5, civ).number_format = "#,##0.00"
        ab.cell(x, 6, em).number_format = "#,##0.00"
        ab.cell(x, 7, f"=E{x}+F{x}").number_format = "#,##0.00"
    ab.cell(10, 1, "Total").font = B.bold
    for c in "EFG":
        ab[f"{c}10"] = f"=SUM({c}5:{c}9)"
        ab[f"{c}10"].number_format = "#,##0.00"
    ab["D11"], ab["E11"] = f"GST @ {O['gst'] * 100:g} %", f"=E10*{O['gst']}"
    ab["D12"], ab["E12"] = f"Centage @ {O['centage'] * 100:g} %", f"=ROUND(E10*{O['centage']},2)"
    ab["D13"], ab["E13"] = "Total civil O&M", "=E10+E11+E12"
    ab["A14"], ab["G14"] = "Total civil & E/M cost for 5 years excl. power & diesel", "=G10-G8-G9"
    ab["A15"], ab["G15"] = "Power and diesel for 5 years", "=G8+G9"
    ab["A16"], ab["G16"] = "Total O&M cost for 5 years", "=G14+G15"
    ab["A17"], ab["G17"] = f"GST @ {O['gst'] * 100:g} %", f"=G16*{O['gst']}"
    ab["A18"], ab["G18"] = f"Centage @ {O['centage'] * 100:g} % (excl. power & diesel)", f"=ROUND(G14*{O['centage']},2)"
    ab["A19"], ab["G19"] = "Total O&M cost for 5 years with GST", "=G16+G17+G18"
    for x in range(11, 20):
        for c in "EG":
            ab[f"{c}{x}"].number_format = "#,##0.00"
    ab["A19"].font = ab["G19"].font = B.bold


# ------------------------------------------------------------------------------------------------------------ economics
def economics(B, P, ac, omr, fj):
    """ECONOMICS and its statements. ac = Abstract comprehensive cells, omr = om() cells, fj = Form j compre cells."""
    bc, t = _eco_breakup(B, ac)
    rw = _eco_repair(B, t)
    sf, st = _eco_staff(B)
    re_ = _eco_recurring(B, omr, st)
    inc = _eco_income(B, P)
    ec = _eco_sheet(B, P, fj)
    for wsx in (bc, rw, sf, re_, inc, ec):
        for row in wsx.iter_rows(min_row=4, max_row=wsx.max_row, max_col=wsx.max_column):
            for cell in row:
                cell.border = B.box
    return ["ECONOMICS", "INCOME", "RECURRING EXP", "REPAIR WORKS", "A.R. EXP ON M. STAFF", "BREAKUP OF COST"]


def _stages(B):
    """The three stages' years as texts, and their names."""
    yrs = [str(y) for y in B.years]
    return yrs, [f"Base year {yrs[0]}", f"Middle year {yrs[1]}", f"Design year {yrs[2]}"]


def _eco_breakup(B, ac):
    """Sheet BREAKUP OF COST (Rs lakh) -> (the sheet, its sub total row)."""
    bc = B.sheet("BREAKUP OF COST", "BREAKUP OF COST (Rs. lakh)", 8)
    B.header(bc, 4, ["S.N.", "Sub Head", "Total cost of work", "Building", "R.C.C.", "Pipe Line", "Machinery", "Misc."],
             [6, 52, 16, 13, 13, 13, 13, 13])
    rows = [("Sewer Network", ac["sewer"], "F"), ("Sewer house connection", ac["hc"], "F"), ("SPS", ac["sps"], "E"),
            ("Rising Main", ac["rm"], "F")] + [(n, c, "H" if "trial" in n.lower() else "G") for n, c in ac["em"]]
    for i, (name, cell, where) in enumerate(rows):
        x = 5 + i
        bc.cell(x, 1, i + 1)
        bc.cell(x, 2, name)
        bc.cell(x, 3, f"={cell}").number_format = "#,##0.00"
        bc[f"{where}{x}"] = f"=C{x}"
        bc[f"{where}{x}"].number_format = "#,##0.00"
    t = 5 + len(rows)
    bc.cell(t, 2, "SUB TOTAL").font = B.bold
    for c in "CDEFGH":
        bc[f"{c}{t}"] = f"=SUM({c}5:{c}{t - 1})"
        bc[f"{c}{t}"].number_format = "#,##0.00"
    return bc, t


def _eco_repair(B, t):
    """Sheet REPAIR WORKS (Rs); t = the sub total row of BREAKUP OF COST."""
    E = B.S["economics"]
    yrs = _stages(B)[0]
    rw = B.sheet("REPAIR WORKS", "ANNUAL MAINTENANCE EXPENDITURE ON REPAIR WORKS (Rs.)", 9)
    B.header(rw, 4, ["S.N.", "Particulars", "Total cost of work (Rs.)", f"% {yrs[0]}", "Amount", f"% {yrs[1]}", "Amount",
                     f"% {yrs[2]}", "Amount"], [6, 30, 18, 8, 16, 8, 16, 8, 16])
    heads = [("Sewer Network", "F"), ("Building Work", "D"), ("RCC Work", "E"), ("Machinery", "G"), ("Misc.", "H")]
    for i, (name, c) in enumerate(heads):
        x = 5 + i
        rw.cell(x, 1, i + 1)
        rw.cell(x, 2, name)
        rw.cell(x, 3, f"='BREAKUP OF COST'!{c}{t}*100000").number_format = "#,##0"
        pc = E["repair_percent"].get(name, [0, 0, 0])
        for j in range(3):
            p = rw.cell(x, 4 + 2 * j, pc[j])
            p.fill = B.yellow
            rw.cell(x, 5 + 2 * j, f"=ROUND(C{x}*{B.col(4 + 2 * j)}{x}/100,2)").number_format = "#,##0"
    rw.cell(10, 2, "Total").font = B.bold
    for c in "CEGI":
        rw[f"{c}10"] = f"=SUM({c}5:{c}9)"
        rw[f"{c}10"].number_format = "#,##0"
    return rw


def _eco_staff(B):
    """Sheet A.R. EXP ON M. STAFF (Rs) -> (the sheet, its total row)."""
    E = B.S["economics"]
    sf = B.sheet("A.R. EXP ON M. STAFF", "ANNUAL RECURRING EXPENDITURE ON MAINTENANCE STAFF (Rs.)", 11)
    B.header(sf, 4, ["S.N.", "Particulars", "No.", "Average pay", "Annual pay", "No.", "Average pay", "Annual pay", "No.",
                     "Average pay", "Annual pay"], [6, 40, 6, 12, 14, 6, 12, 14, 6, 12, 14])
    for i, (name, n, pays) in enumerate(E["staff"]):
        x = 5 + i
        sf.cell(x, 1, i + 1)
        sf.cell(x, 2, name)
        for j in range(3):
            c0 = 3 + 3 * j
            sf.cell(x, c0, n).fill = B.yellow
            sf.cell(x, c0 + 1, pays[j]).fill = B.yellow
            sf.cell(x, c0 + 2, f"={B.col(c0)}{x}*{B.col(c0 + 1)}{x}*12").number_format = "#,##0"
    st = 5 + len(E["staff"])
    sf.cell(st, 2, "TOTAL").font = B.bold
    for c in "EHK":
        sf[f"{c}{st}"] = f"=SUM({c}5:{c}{st - 1})"
        sf[f"{c}{st}"].number_format = "#,##0"
    return sf, st


def _eco_recurring(B, omr, st):
    """Sheet RECURRING EXP (Rs); st = the total row of the staff sheet."""
    stage = _stages(B)[1]
    re_ = B.sheet("RECURRING EXP", "ANNUAL RECURRING EXPENDITURE ON MAINTENANCE (Rs.)", 5)
    B.header(re_, 4, ["S.N.", "Particulars"] + stage, [6, 52, 18, 18, 18])
    elec = omr.get("sps_elec") or ["0", "0", "0"]
    lines = [("Expenditure on maintenance staff", [f"='A.R. EXP ON M. STAFF'!{c}{st}" for c in "EHK"]),
             ("Expenditure on chemicals", [0, 0, 0]),
             ("Expenditure on electricity (pumping stations: sheet SPS O&M)", [f"=({e})*100000" for e in elec]),
             ("Expenditure on annual maintenance and repair charges", [f"='REPAIR WORKS'!{c}10" for c in "EGI"]),
             ("Cess charges", [0, 0, 0])]
    for i, (name, vals) in enumerate(lines):
        x = 5 + i
        re_.cell(x, 1, i + 1)
        re_.cell(x, 2, name)
        for j, v in enumerate(vals):
            c = re_.cell(x, 3 + j, v)
            c.number_format = "#,##0"
            if v == 0:
                c.fill = B.yellow
    re_.cell(10, 2, "TOTAL").font = B.bold
    for c in "CDE":
        re_[f"{c}10"] = f"=SUM({c}5:{c}9)"
        re_[f"{c}10"].number_format = "#,##0"
    return re_


def _eco_income(B, P):
    """Sheet INCOME (Rs)."""
    E = B.S["economics"]
    stage = _stages(B)[1]
    inc = B.sheet("INCOME", "STATEMENT OF ANNUAL INCOME (Rs.)", 5)
    B.header(inc, 4, ["S.N.", "Particulars"] + stage, [6, 70, 18, 18, 18])
    tar = E["tariff_per_month"]
    items = [("Population served", P["pop"], "#,##0"), ("Number of households (sewer connections)", P["hh"], "#,##0"),
             (f"Number of taxable houses ({(1 - E['nontaxable_share']) * 100:g} % of households)",
              [f"={h}*{1 - E['nontaxable_share']}" for h in P["hh"]], "#,##0"),
             (f"Number of non-taxable houses ({E['nontaxable_share'] * 100:g} % of households)",
              [f"={h}*{E['nontaxable_share']}" for h in P["hh"]], "#,##0")]
    for i, (name, vals, fmt) in enumerate(items):
        x = 5 + i
        inc.cell(x, 1, i + 1)
        inc.cell(x, 2, name)
        for j, v in enumerate(vals):
            inc.cell(x, 3 + j, v if str(v).startswith("=") else f"={v}").number_format = fmt
    inc.cell(9, 1, 5)
    inc.cell(9, 2, "Sewer charges per house per month (Rs.) - taxable")
    for j in range(3):
        inc.cell(9, 3 + j, tar[j]).fill = B.yellow
    inc.cell(10, 1, 6)
    inc.cell(10, 2, "Sewer charges per house per month (Rs.) - poor family (half)")
    for j in range(3):
        c = B.col(3 + j)
        inc.cell(10, 3 + j, f"=ROUND({c}9/2,-1)")
    inc.cell(11, 1, 7)
    inc.cell(11, 2, "Hence total income (Rs. / year)").font = B.bold
    inc.cell(12, 1, 8)
    inc.cell(12, 2, "Annual recurring expenditure (Rs.)")
    inc.cell(13, 2, "Net profit (+) / loss (-)").font = B.bold
    for j in range(3):
        c = B.col(3 + j)
        inc.cell(11, 3 + j, f"=ROUND(({c}7*{c}9+{c}8*{c}10)*12,-3)").number_format = "#,##0"
        inc.cell(12, 3 + j, f"='RECURRING EXP'!{c}10").number_format = "#,##0"
        inc.cell(13, 3 + j, f"={c}11-{c}12").number_format = "#,##0"
    return inc


def _eco_sheet(B, P, fj):
    """Sheet ECONOMICS (Rs lakh)."""
    yrs = _stages(B)[0]
    ec = B.sheet("ECONOMICS", "ECONOMICS", 5)
    B.header(ec, 4, ["S.No.", "Description"] + yrs, [6, 60, 16, 16, 16])
    lines = [("Project cost without centage (Rs. lakh)", [f"={fj['total']}-{fj['centage']}"] * 3, "#,##0.00"),
             ("Population covered", [f"={p}" for p in P["pop"]], "#,##0"),
             ("No. of households", [f"={h}" for h in P["hh"]], "#,##0"),
             ("Per capita cost (Rs.)", [f"={B.col(3 + j)}5*100000/{B.col(3 + j)}6" for j in range(3)], "#,##0"),
             ("Annual expenditure (Rs. lakh)", [f"=INCOME!{B.col(3 + j)}12/100000" for j in range(3)], "#,##0.00"),
             ("Proposed tariff per household per month (Rs.)", [f"=INCOME!{B.col(3 + j)}9" for j in range(3)], "#,##0"),
             ("Income as per the proposed tariff (Rs. lakh)", [f"=INCOME!{B.col(3 + j)}11/100000" for j in range(3)],
              "#,##0.00"),
             ("Net profit / loss (Rs. lakh)", [f"={B.col(3 + j)}11-{B.col(3 + j)}9" for j in range(3)], "#,##0.00")]
    for i, (name, vals, fmt) in enumerate(lines):
        x = 5 + i
        ec.cell(x, 1, i + 1)
        ec.cell(x, 2, name)
        for j, v in enumerate(vals):
            ec.cell(x, 3 + j, v).number_format = fmt
    return ec


# -------------------------------------------------------------------------------------------------------- Form j compre
def form_j_compre(B, ac, omr):
    """Form J (comprehensive) as the sample: on Abstract comprehensive Total (A+B), power connection, O&M 5 years."""
    fj = B.S["form_j"]
    fo = B.wb.create_sheet("Form j compre")
    fo.cell(1, 1, f'=""&{B.PR["office"]}').font = B.bold
    fo.cell(2, 1, B.title).font = B.big
    fo.cell(3, 1, "FORM - 'J' (Comprehensive)").font = B.bold
    shares = fj["shares"]
    for x in (1, 2, 3):
        fo.merge_cells(start_row=x, start_column=1, end_row=x, end_column=5 + len(shares))
        fo.cell(x, 1).alignment = B.hcenter
    fo.cell(4, 7, "Rs. (in lakh)")
    B.header(fo, 5, ["Sl. No.", "Description", "Amount in Lakh", "Rate", "Cost"] + [s[0] for s in shares],
             [7, 44, 14, 8, 14, 14, 14, 14])
    sc = [B.col(6 + j) for j in range(len(shares))]
    for j, s in enumerate(shares):
        c = fo.cell(6, 6 + j, s[1])
        c.fill, c.number_format = B.yellow, "0%"

    def split(x):
        for c in sc:
            fo[f"{c}{x}"] = f"=$E${x}*{c}$6"

    fo["A7"], fo["B7"], fo["C7"], fo["E7"] = 1, "Total cost of work", f"={ac['total_ab']}", "=C7"
    fo["A8"], fo["B8"], fo["E8"] = 2, "Contingency", fj["contingency_lakh"]
    fo["E8"].fill = B.yellow
    fo["B9"], fo["E9"] = "Sub Total (1+2)", "=E7+E8"
    fo["A10"], fo["B10"], fo["C10"], fo["D10"], fo["E10"] = 3, "Less due to efficiency", "=E9", fj["efficiency_less"], "=C10*D10"
    fo["B11"], fo["A11"], fo["E11"] = "Sub Total (2-3)", 4, "=E9-E10"
    split(11)
    fo["A12"], fo["B12"], fo["C12"], fo["D12"], fo["E12"] = 5, 'Labour Cess on "(4)"', "=E11", fj["labour_cess"], "=C12*D12"
    split(12)
    fo["A13"], fo["B13"], fo["C13"], fo["D13"], fo["E13"] = 6, "GST", "=C12", fj["gst"], "=C13*D13"
    split(13)
    fo["A14"], fo["B14"] = 7, "Centage (on '(4)', by slab)"
    x, lo = 15, 0
    for upto, pct in fj["centage"]:
        fo.cell(x, 2, f"Above {lo / 100:g} Cr." if upto is None else
                (f"{lo / 100:g} Cr. to {upto / 100:g} Cr." if lo else f"Upto {upto / 100:g} Cr."))
        fo.cell(x, 3, f"=MAX(0,$E$11-{lo})" if upto is None else f"=MAX(0,MIN($E$11,{upto})-{lo})")
        fo.cell(x, 4, pct).fill = B.yellow
        fo.cell(x, 5, f"=C{x}*D{x}")
        lo = upto or lo
        x += 1
    fo.cell(x, 2, "Total Centage")
    fo.cell(x, 5, f"=SUM(E15:E{x - 1})")
    fo.cell(x, 7, f"=E{x}")
    cent = x
    x += 1
    fo.cell(x, 1, 8)
    fo.cell(x, 2, "Power Connection Charges for SPS")
    fo.cell(x, 5, f"={ac['power']}")
    split(x)
    pw = x
    x += 1
    fo.cell(x, 1, 9)
    fo.cell(x, 2, "Total (4+5+6+7+8)")
    fo.cell(x, 5, f"=E11+E12+E13+E{cent}+E{pw}")
    for c in sc:
        fo[f"{c}{x}"] = f"={c}11+{c}12+{c}13+{c}{cent}+{c}{pw}"
    tot = x
    x += 1
    fo.cell(x, 1, 10)
    fo.cell(x, 2, "Operation & maintenance for 5 years with GST")
    fo.cell(x, 5, f"={omr['total_om']}")
    fo[f"{sc[-1]}{x}"] = f"=E{x}"
    omx = x
    x += 1
    fo.cell(x, 1, 11)
    fo.cell(x, 2, "Total Project Cost").font = B.bold
    fo.cell(x, 5, f"=E{tot}+E{omx}")
    for c in sc:
        fo[f"{c}{x}"] = f"=SUM({c}{tot},{c}{omx})"
    for row in fo.iter_rows(min_row=7, max_row=x, min_col=3, max_col=5 + len(shares)):
        for cell in row:
            cell.number_format = "0.00%" if cell.column == 4 else "#,##0.00"
    for row in fo.iter_rows(min_row=5, max_row=x, max_col=5 + len(shares)):
        for cell in row:
            cell.border = B.box
    x += 2
    from .dpr_front import signatures
    signatures(fo, x, B.PR, em=True)
    return {"total": f"'Form j compre'!E{tot}", "centage": f"'Form j compre'!E{cent}"}
