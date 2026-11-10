"""E&M works of the pumping stations in the sewer DPR (dpr_more.pumping_stations) - user decisions 26-Oct-2026: the
format of the U.P. Jal Nigam E&M estimate 'R2 DISTRICT-Elmwood ZONE VNS SENDED TO cd' (Construction Division E/M,
Springfield), every station worked out from the design:

    EM rates            the estimate's rates (yellow) and how each grows with the size (rate x (size / size0)^exp),
                        the commercial ratings of motors, DG sets, transformers, pipes, cables, the efficiency and
                        motor margin tables of the estimate
    EM TS SPS-k         technical statement (the estimate's 'Revise c'): pumps for the +15 years peak of the design
                        (CPHEEO Table 2.1 p2-9), head from sheet RM SPS-k, motors, load, DG, transformer, column pipes,
                        header, cables - live formulas
    EM Est SPS-k        the estimate's sheets as sections: pumping plants, screens and sluice gates, DG sets,
                        automation, LT panel and cable, HT panel and sub-station, trial run, power connection
    Abstract E&M SPS-k  as the estimate's 'Abstract E&M'
    E&M SPS             all stations: each part (Rs lakh), the total E&M, the power connection

    write(B, stations) -> {"em": {part: cell}, "em_total": [cell per station], "power_total": cell, "sheets": [...]}
    stations = [{"tag", "outfall", "q_avg", "q_peak", "given", "rm_sheet"}]  (q in L/s, +15 years)
"""
import json
import os

from . import DATA_DIR

SETTINGS = os.path.join(DATA_DIR, "dpr_em_sps.json")
PARTS = ["Pumping plants, main piping, valves and accessories", "Bar screens and sluice gates", "D.G. sets",
         "Automation", "L.T. panel and cable", "H.T. panel, cable and sub-station", "Trial run for three months"]


def settings():
    with open(SETTINGS, encoding="utf-8") as fh:
        return {k: v["value"] for k, v in json.load(fh).items() if isinstance(v, dict) and "value" in v}


def q(name):
    return "'" + name.replace("'", "''") + "'"


def _rates_sheet(B, E):
    """Sheet EM rates; returns {"rate": {key: row}, "list": {name: range}, "eff": (keys, values), ...}."""
    ws = B.sheet("EM rates", "E&M RATES (U.P. JAL NIGAM E&M ESTIMATE R2, DISTRICT Elmwood ZONE SPRINGFIELD) AND RULES", 8)
    B.header(ws, 3, ["Key", "Item", "Size in R2", "Unit of size", "Rate in R2 (Rs)", "Exponent", "Source"],
             [12, 60, 11, 11, 14, 10, 90])
    out = {"rate": {}}
    r = 4
    for key, it in E["rates"].items():
        ws.cell(r, 1, key)
        ws.cell(r, 2, it["text"])
        for c, v in ((3, it["size"]), (5, it["rate"]), (6, it["exp"])):
            x = ws.cell(r, c, v)
            x.fill = B.yellow
        ws.cell(r, 4, it["unit_size"])
        ws.cell(r, 7, it["src"])
        out["rate"][key] = r
        r += 1
    ws.cell(r, 2, "A size not in R2: rate x (size / size in R2) ^ exponent (user decision 26-Oct-2026)").font = B.italic
    r += 2
    c0 = 9                                                     # the tables, from column I
    tables = [("Motor (HP)", E["motor_hp"], None), ("DG set (kVA)", E["dg_kva"], None),
              ("Transformer (kVA)", E["transformer_kva"], None), ("Pipe / valve (mm)", E["pipe_mm"], None),
              ("Cable (sq mm)", [a for a, _ in E["cable_sqmm"]], ("Current rating (A)", [b for _, b in E["cable_sqmm"]])),
              ("Discharge (LPM) from", [a for a, _ in E["efficiency"]], ("Pump efficiency", [b for _, b in E["efficiency"]])),
              ("Motor kW from", [a for a, _ in E["margin"]], ("Margin", [b for _, b in E["margin"]]))]
    c = c0
    for name, vals, second in tables:
        ws.cell(3, c, name).font = B.bold
        ws.column_dimensions[B.col(c)].width = 13
        for i, v in enumerate(vals):
            x = ws.cell(4 + i, c, v)
            x.fill = B.yellow
        rng = f"'EM rates'!${B.col(c)}$4:${B.col(c)}${3 + len(vals)}"
        out.setdefault("list", {})[name] = rng
        if second:
            ws.cell(3, c + 1, second[0]).font = B.bold
            ws.column_dimensions[B.col(c + 1)].width = 13
            for i, v in enumerate(second[1]):
                x = ws.cell(4 + i, c + 1, v)
                x.fill = B.yellow
            out["list"][second[0]] = f"'EM rates'!${B.col(c + 1)}$4:${B.col(c + 1)}${3 + len(vals)}"
            c += 1
        c += 2
    return out


def _next(x, rng):
    """Formula: the smallest value of the (ascending) list rng not below x (the largest when x is above all)."""
    m = f"MATCH({x},{rng},1)"
    return f"IFERROR(INDEX({rng},MIN({m}+(INDEX({rng},{m})<{x}),COUNT({rng}))),INDEX({rng},1))"


def _rate(R, key, size):
    """Formula of the rate of item key at size (a formula or cell)."""
    r = R["rate"][key]
    return f"'EM rates'!$E${r}*(({size})/'EM rates'!$C${r})^'EM rates'!$F${r}"


def _ts(B, E, R, s):
    """Technical statement of one station; returns {name: absolute cell}."""
    Z = E["sizing"]
    name = f"EM TS {s['tag']}"
    ws = B.sheet(name, f"TECHNICAL STATEMENT (E/M WORKS) - {s['tag']} at {s['outfall']}", 5)
    B.header(ws, 3, ["S.No.", "Description", "Value", "Unit", "Note"], [7, 62, 14, 10, 80])
    L = R["list"]
    c = {}
    rows = []                       # (key, label, value / formula with {key} for C<row>, unit, note, input?, format)

    def add(key, label, val, unit="", note="", inp=False, fmt="#,##0.00"):
        rows.append((key, label, val, unit, note, inp, fmt))
    add("qa", "Average flow, +15 years (L/s)", round(s["q_avg"], 2), "L/s",
        "design (stage table at the outfall)" + ("" if s["given"] else " - +15 years not given on the page: +30 years"),
        inp=not s["given"])
    add("qp", "Peak flow, +15 years (L/s)", round(s["q_peak"], 2), "L/s", "design: CPHEEO peak factor by population",
        inp=not s["given"])
    add("npf", "Non-peak flow / average", Z["np_share"], "", "R2 'Revise c' H10", inp=True)
    add("qn", "Non-peak flow (L/s)", "=C{qa}*C{npf}", "L/s")
    add("hc", "Civil head: static lift + rising main + fittings at the +15 years peak (m)",
        f"={q(s['rm_sheet'])}!I27", "m", f"sheet {s['rm_sheet']} I27")
    add("he", "E/M head: entry, pump, column pipe losses (m)", Z["em_head_m"], "m", "R2 'Revise c' H26 (27 + 3 m)",
        inp=True)
    add("h", "Total head (m)", "=ROUNDUP(C{hc}+C{he},0)", "m")
    add("sg", "Specific gravity of sewage", Z["specific_gravity"], "", "R2", inp=True)
    add("par", "Discharge in parallel operation (share of rated)", Z["parallel"], "", "R2: 95 %", inp=True)
    add("nb", "Big pumps working", Z["big_working"], "Nos", "R2: 2 working + 2 standby for (peak - non-peak)",
        inp=True, fmt="0")
    add("nbs", "Big pumps standby", Z["big_standby"], "Nos", "", inp=True, fmt="0")
    add("ns", "Small pumps working", Z["small_working"], "Nos", "R2: 1 working + 1 standby for the non-peak flow",
        inp=True, fmt="0")
    add("nss", "Small pumps standby", Z["small_standby"], "Nos", "", inp=True, fmt="0")
    for p, lab, qf in (("b", "big", "=CEILING((C{qp}-C{qn})/C{nb}/C{par},1)"), ("s", "small", "=CEILING(C{qn}/C{ns}/C{par},1)")):
        add(f"q{p}", f"Rated discharge of a {lab} pump (L/s)", qf, "L/s", "R2 'Revise c' H22 / H24")
        add(f"l{p}", f"Discharge of a {lab} pump (LPM)", f"=C{{q{p}}}*60", "LPM")
        add(f"w{p}", f"W.H.P. = LPM x H x SG / 4500 ({lab})", f"=C{{l{p}}}*C{{h}}*C{{sg}}/4500", "HP")
        add(f"e{p}", f"Efficiency of the {lab} pump", f"=LOOKUP(C{{l{p}}},{L['Discharge (LPM) from']},{L['Pump efficiency']})",
            "", "R2 'Revise c' K53:N57 by LPM")
        add(f"i{p}", f"B.H.P. input to the {lab} pump", f"=C{{w{p}}}/C{{e{p}}}", "HP")
        add(f"k{p}", f"B.kW to the {lab} pump", f"=C{{i{p}}}*0.746", "kW")
        add(f"m{p}", f"Margin on the {lab} motor", f"=LOOKUP(C{{k{p}}},{L['Motor kW from']},{L['Margin']})", "",
            "R2 'Revise c' K46:N51 by kW")
        add(f"r{p}", f"Required motor ({lab})", f"=C{{i{p}}}*(1+C{{m{p}}})", "HP")
        add(f"hp{p}", f"Motor provided ({lab}) - next commercial rating", "=" + _next(f"C{{r{p}}}", L["Motor (HP)"]),
            "HP", "", fmt="0.0")
        add(f"ok{p}", f"Check ({lab} motor)", f'=IF(C{{r{p}}}>MAX({L["Motor (HP)"]}),"ABOVE THE LARGEST RATING - '
            f'more pumps working (yellow above)","OK")', "", "", fmt="General")
    add("misc", "Miscellaneous load (kVA)", Z["misc_kva"], "kVA", "R2 'Revise c' H71", inp=True)
    add("pf", "Power factor", Z["pf"], "", "", inp=True)
    add("v", "Voltage (kV)", Z["volt_kv"], "kV", "", inp=True)
    add("load", "Total load at peak (kVA) = working motors x 0.746 / pf + miscellaneous",
        "=(C{nb}*C{hpb}+C{ns}*C{hps})*0.746/C{pf}+C{misc}", "kVA", "R2 'Revise c' H72")
    add("ab", "Full load current of a big motor (A)", "=C{hpb}*0.746/(C{v}*1.7321*C{pf}*0.95)", "A", "R2 H85")
    add("as", "Full load current of a small motor (A)", "=C{hps}*0.746/(C{v}*1.7321*C{pf}*0.95)", "A", "R2 H84")
    add("start", "Load when the 2nd big pump starts on soft starter (kVA)",
        "=1.7321*C{v}*(C{misc}/(1.7321*C{v})+2*1.5*C{ab})", "kVA", "R2 H90-H93")
    add("mg", "Margin on load (DG, transformer)", Z["load_margin"], "", "R2: 20 % margin", inp=True)
    add("ndg", "DG sets (nos)", Z["dg_sets"], "Nos", "", inp=True, fmt="0")
    add("dg", "DG set capacity - next commercial rating of max(load x margin, starting) / sets",
        "=" + _next("MAX(C{load}*C{mg},C{start})/C{ndg}", L["DG set (kVA)"]), "kVA", "R2 'Revise c' (I)")
    add("okdg", "Check (DG set)", f'=IF(MAX(C{{load}}*C{{mg}},C{{start}})/C{{ndg}}>MAX({L["DG set (kVA)"]}),'
        f'"ABOVE THE LARGEST RATING - more DG sets (yellow above)","OK")', "", "", fmt="General")
    add("ntr", "Transformers (1 working + 1 standby)", Z["transformers"], "Nos", "R2 Sub Station B8", inp=True, fmt="0")
    add("tr", "Transformer capacity - next commercial rating of load x margin",
        "=" + _next("C{load}*C{mg}", L["Transformer (kVA)"]), "kVA", "R2 'Revise c' (J)")
    add("oktr", "Check (transformer)", f'=IF(C{{load}}*C{{mg}}>MAX({L["Transformer (kVA)"]}),'
        f'"ABOVE THE LARGEST RATING - an HT supply of more transformers / higher voltage","OK")', "", "", fmt="General")
    add("vc", "Velocity in the column pipes (m/s)", Z["col_velocity"], "m/s", "R2 (K)", inp=True)
    add("vh", "Velocity in the common header (m/s)", Z["header_velocity"], "m/s", "R2 (L)", inp=True)
    add("db", "Column pipe of a big pump (mm)",
        "=" + _next("SQRT(C{qb}/1000*4/(PI()*C{vc}))*1000", L["Pipe / valve (mm)"]), "mm")
    add("ds", "Column pipe of a small pump (mm)",
        "=" + _next("SQRT(C{qs}/1000*4/(PI()*C{vc}))*1000", L["Pipe / valve (mm)"]), "mm")
    add("dh", "Common header (mm) for all working pumps",
        "=" + _next("SQRT((C{nb}*C{qb}+C{ns}*C{qs})/1000*4/(PI()*C{vh}))*1000", L["Pipe / valve (mm)"]), "mm")
    add("cf", "Cable: current / derating x this (voltage drop on long submersible cables)", Z["cable_factor"], "",
        "gives R2's 6 and 16 sq mm for 10 and 20 HP", inp=True)
    amps, sq = L["Current rating (A)"], L["Cable (sq mm)"]
    for p, lab in (("b", "big"), ("s", "small")):
        x = f"C{{a{p}}}/{Z['derating']}*C{{cf}}"
        add(f"c{p}", f"Cable of a {lab} pump (sq mm)",
            f"=INDEX({sq},MATCH({_next(x, amps)},{amps},0))", "sq mm", f"derating {Z['derating']}")
    add("lt", "L.T. incomer current = transformer kVA / (1.7321 x 0.415) (A)", "=C{tr}/(1.7321*0.415)", "A", "R2 (N)")
    add("kwp", "Power at the peak (kW) = load x pf", "=C{load}*C{pf}", "kW", "trial run, energy")
    add("kwa", "Power at the average flow (kW)", "=C{qa}*C{h}*C{sg}/(102*C{eb})+C{misc}*C{pf}", "kW")
    add("kwn", "Power at the non-peak flow (kW)", "=C{qn}*C{h}*C{sg}/(102*C{es})+C{misc}*C{pf}", "kW")
    for i, row in enumerate(rows):
        c[row[0]] = 4 + i
    for i, (key, label, val, unit, note, inp, fmt) in enumerate(rows):
        x = 4 + i
        if isinstance(val, str) and val.startswith("="):
            val = val.format(**{k: v for k, v in c.items()})
        ws.cell(x, 1, i + 1)
        ws.cell(x, 2, label)
        cell = ws.cell(x, 3, val)
        cell.number_format = fmt
        if inp:
            cell.fill = B.yellow
        ws.cell(x, 4, unit)
        ws.cell(x, 5, note)
        for cc in range(1, 6):
            ws.cell(x, cc).border = B.box
    for key in ("hpb", "hps", "load", "dg", "tr", "dh"):
        ws.cell(c[key], 3).font = B.bold
    for key in ("okb", "oks", "okdg", "oktr"):
        ws.cell(c[key], 3).font = B.red
    return name, {k: f"{q(name)}!$C${v}" for k, v in c.items()}


def _estimate(B, E, R, s, T):
    """The cost sheet of one station: the R2 estimates as sections. Returns {part: Rs cell}, power connection Rs cell."""
    F = E["fixed"]
    name = f"EM Est {s['tag']}"
    ws = B.sheet(name, f"COST ESTIMATE (E/M WORKS) - {s['tag']} at {s['outfall']}", 7)
    B.header(ws, 3, ["Sl.", "Description of work", "Qty.", "Unit", "Rate (Rs)", "Amount (Rs)", "Rate from"],
             [6, 66, 10, 9, 14, 15, 60])
    x = [4]
    out = {}

    def title(text):
        ws.cell(x[0], 2, text).font = B.bold
        x[0] += 1

    def item(text, qty, unit, rate, src, rate_inp=False, qty_inp=False):
        r = x[0]
        ws.cell(r, 2, text)
        a = ws.cell(r, 3, qty)
        a.number_format = "#,##0.00"
        ws.cell(r, 4, unit)
        b = ws.cell(r, 5, rate)
        b.number_format = "#,##0"
        ws.cell(r, 6, f"=C{r}*E{r}").number_format = "#,##0"
        ws.cell(r, 7, src)
        if rate_inp:
            b.fill = B.yellow
        if qty_inp:
            a.fill = B.yellow
        for cc in range(1, 8):
            ws.cell(r, cc).border = B.box
        x[0] += 1
        return r

    def total(part):
        r = x[0]
        ws.cell(r, 2, f"Total - {part}").font = B.bold
        ws.cell(r, 6, f"=SUM(F{first[0]}:F{r - 1})").number_format = "#,##0"
        ws.cell(r, 6).font = B.bold
        out[part] = f"{q(name)}!$F${r}"
        x[0] += 2
    first = [0]
    nb, ns = f"({T['nb']}+{T['nbs']})", f"({T['ns']}+{T['nss']})"
    npump = f"({nb}+{ns})"
    em = "sheet EM rates"

    # 1 pumping plants (R2 'Pumping Plants')
    title("1. PUMPING PLANTS, MAIN PIPING, VALVES AND ACCESSORIES (R2 'Pumping Plants')")
    first[0] = x[0]
    for p, n_ in (("b", nb), ("s", ns)):
        hp = T[f"hp{p}"]
        item(f'="Soft starter for "&{hp}&" HP pump set (fitted in the L.T. panel)"', f"={n_}", "Nos",
             "=" + _rate(R, "soft", hp), em)
        item(f'="Submersible sewage non-clog pump set, "&{T["q" + p]}&" LPS, "&{T["h"]}&" m head, "&{hp}&" HP, '
             f'with guide rail / auto-coupling system"', f"={n_}", "Nos", "=" + _rate(R, "pump", hp), em)
    item("Shunt type power factor improvement capacitor", 1, "Job", "=" + _rate(R, "capacitor", T["load"]), em)
    for key, lab in (("mov", "Motor operated sluice valve with actuator, CIDF"), ("reflux", "Reflux valve, DIDF"),
                     ("dj", "Dismantling joint")):
        for d, n_ in ((T["db"], nb), (T["ds"], ns), (T["dh"], 2)):
            item(f'="{lab} "&{d}&" mm"', f"={n_}", "No", "=" + _rate(R, key, d), em)
    for d, n_ in ((T["db"], f"4*{nb}"), (T["ds"], f"4*{ns}"), (T["dh"], 12)):
        item(f'="DIDF pipe "&{d}&" mm x 3 m"', f"={n_}", "No", "=" + _rate(R, "pipe3m", d), em + " (R2: 4 a pump, 12 header)")
    sf = f"{npump}/6*({T['dh']}/250)^1.5"
    item("CIDF specials (tees, bends, duck-foot bends, reducers, blind flanges)", f"=ROUND(5400*{sf},0)", "Kg",
         "=" + _rate(R, "specials", 1), "R2: 5400 kg for 6 pumps and a 250 mm header, by pumps and header^1.5")
    item("Nuts and bolts with washer (SS)", f"=ROUND(900*{sf},0)", "Kg", "=" + _rate(R, "bolts", 1), "R2: 900 kg, as above")
    item(f'="Electromagnetic flow meter "&{T["dh"]}&" mm with CVT and control cables"', 1, "No",
         "=" + _rate(R, "flowmeter", T["dh"]), em)
    for p, n_ in (("b", nb), ("s", ns)):
        item(f'="Copper XLPE submersible cable "&{T["c" + p]}&" sq mm"', f"={n_}*{E['sizing']['pump_cable_m']}", "m",
             "=" + _rate(R, "pumpcable", T["c" + p]), em + f" ({E['sizing']['pump_cable_m']} m a pump)")
    for text, unit, rate in F["pumping"]:
        per = unit.endswith("/pump")
        item(text, f"={npump}" if per else 1, unit.replace("/pump", ""), rate, "R2 'Pumping Plants'", rate_inp=True,
             qty_inp=not per)
    total(PARTS[0])
    # 2 screens and sluice gates (R2 'Screens')
    title("2. MECHANICAL / MANUAL BAR SCREENS AND SLUICE GATES (R2 'Screens')")
    first[0] = x[0]
    for text, unit, n_, rate in F["screens"]:
        item(text, n_, unit, rate, "R2 'Screens'", rate_inp=True, qty_inp=True)
    total(PARTS[1])
    # 3 DG sets (R2 'DG')
    title("3. D.G. SETS AND APPURTENANT WORKS (R2 'DG')")
    first[0] = x[0]
    item(f'="DG set "&{T["dg"]}&" kVA, 1500 RPM, acoustic enclosure, AMF panel"', f"={T['ndg']}", "Nos",
         "=" + _rate(R, "dg", T["dg"]), em)
    item("Power cable 1.1 kV, DG to panel", F["dg_cable_m"], "m", "=" + _rate(R, "dgcable", T["dg"]), em, qty_inp=True)
    for text, rate in F["dg_other"]:
        item(text, 1, "Job", rate, "R2 'DG'", rate_inp=True)
    total(PARTS[2])
    # 4 automation (R2 'Automation')
    title("4. AUTOMATION (R2 'Automation')")
    first[0] = x[0]
    for text, rate in F["automation"]:
        item(text, 1, "Job", rate, "R2 'Automation'", rate_inp=True)
    total(PARTS[3])
    # 5 LT panel and cable (R2 'Panel')
    title("5. L.T. PANEL AND CABLE (R2 'Panel')")
    first[0] = x[0]
    item(f'="L.T. panel for "&ROUND({T["load"]},0)&" kVA load, incomer / outgoing MCCBs, bus coupler"', 1, "Set",
         "=" + _rate(R, "ltpanel", T["load"]), em)
    item(f'="Power cable 1.1 kV, transformer to L.T. panel ("&ROUND({T["lt"]},0)&" A)"', F["lt_cable_m"], "m",
         "=" + _rate(R, "ltcable", T["lt"]), em, qty_inp=True)
    for text, rate in F["lt_other"]:
        item(text, 1, "Job", rate, "R2 'Panel'", rate_inp=True)
    total(PARTS[4])
    # 6 HT panel and sub-station (R2 'Sub Station')
    title("6. H.T. PANEL, CABLE AND SUB-STATION (R2 'Sub Station')")
    first[0] = x[0]
    item(f'="11 kV / 0.4 kV outdoor step-down transformer "&{T["tr"]}&" kVA"', f"={T['ntr']}", "Nos",
         "=" + _rate(R, "transformer", T["tr"]), em)
    for text, rate in F["ht"]:
        item(text, 1, "Job", rate, "R2 'Sub Station'", rate_inp=True)
    total(PARTS[5])
    # 7 trial run (R2 'Trial Run')
    t = F["trial"]
    days = 30 * t["months"]
    title(f"7. TRIAL RUN FOR {t['months']} MONTHS (R2 'Trial Run')")
    first[0] = x[0]
    for text, n_, rate in t["staff"]:
        item(f"{text} ({n_} x {t['months']} months)", n_ * t["months"], "month", rate, "R2 'Trial Run'", rate_inp=True)
    fx = item(f"Electricity: fixed charges, load x pf x Rs {t['fixed_rs_per_kva_month']} / kVA / month",
              f"={T['load']}*{T['pf']}*{t['months']}", "kVA-month", t["fixed_rs_per_kva_month"], "R2", rate_inp=True)
    hp_, ha, hn = t["hours"]
    run = item(f"Electricity: energy, {hp_} h at peak + {ha} h average + {hn} h non-peak a day, {days} days",
               f"=({T['kwp']}*{hp_}+{T['kwa']}*{ha}+{T['kwn']}*{hn})*{days}", "kWh", t["tariff"], "R2: Rs 8.30 / kWh",
               rate_inp=True)
    item(f"Regulatory surcharge {t['surcharge'] * 100:g} % + electricity duty {t['duty'] * 100:g} %", f"=F{fx}+F{run}",
         "Rs", t["surcharge"] + t["duty"], "R2")
    item(f"DG: diesel {t['diesel_l_per_kva_hour']} l / kVA / h x {t['dg_hours_per_day']} h a day",
         f"={T['dg']}*{T['ndg']}*{t['diesel_l_per_kva_hour']}*{t['dg_hours_per_day']}*{days}", "litre", t["diesel_rs"],
         "R2: 10 l/h for 125 kVA", rate_inp=True)
    item("DG: lubricant", days, "day", t["lubricant_rs_per_day"], "R2", rate_inp=True)
    total(PARTS[6])
    # 8 power connection (R2 'Power Connection')
    P = F["power"]
    title("8. NEW 11 KV POWER CONNECTION (R2 'Power Connection')")
    first[0] = x[0]
    item("11 kV underground XLPE 3 x 120 sq mm double cable line from the sub-station", P["line_km"], "km",
         P["line_rate_per_km"], "R2: 3 km - the distance to the feeding sub-station, fill in", rate_inp=True,
         qty_inp=True)
    item("Processing fee", 1, "Job", P["processing"], "R2", rate_inp=True)
    item("Security charges on the load", f"=ROUND({T['load']},0)", "kVA", P["security_per_kva"], "R2", rate_inp=True)
    item("Energy meter", 1, "Job", P["meter"], "R2", rate_inp=True)
    total("power")
    ws.freeze_panes = "C4"
    return name, out


def write(B, stations):
    """All the E&M sheets of the stations (see the module text)."""
    E = settings()
    R = _rates_sheet(B, E)
    made, per = ["EM rates"], []
    for s in stations:
        tname, T = _ts(B, E, R, s)
        ename, cost = _estimate(B, E, R, s, T)
        ab = B.sheet(f"Abstract E&M {s['tag']}", f"ABSTRACT OF COST (E/M) - {s['tag']} at {s['outfall']}", 4)
        B.header(ab, 3, ["Sl. No.", "Description", "Amount (Rs)", "Rs. lakh"], [7, 60, 16, 12])
        for i, p in enumerate(PARTS):
            x = 4 + i
            ab.cell(x, 1, i + 1)
            ab.cell(x, 2, p)
            ab.cell(x, 3, f"={cost[p]}").number_format = "#,##0"
            ab.cell(x, 4, f"=C{x}/100000").number_format = "#,##0.00"
        x = 4 + len(PARTS)
        ab.cell(x, 2, "Sub Total (A) - E&M works").font = B.bold
        ab.cell(x, 3, f"=SUM(C4:C{x - 1})").number_format = "#,##0"
        ab.cell(x, 4, f"=C{x}/100000").number_format = "#,##0.00"
        ab.cell(x + 2, 2, "(B) New 11 kV power connection").font = B.bold
        ab.cell(x + 2, 3, f"={cost['power']}").number_format = "#,##0"
        ab.cell(x + 2, 4, f"=C{x + 2}/100000").number_format = "#,##0.00"
        for row in ab.iter_rows(min_row=3, max_row=x + 2, max_col=4):
            for cell in row:
                cell.border = B.box
        per.append({"tag": s["tag"], "outfall": s["outfall"], "abs": ab.title, "rows": 4, "sub": x, "power": x + 2})
        made += [tname, ename, ab.title]

    # E&M SPS: all stations (Rs lakh)
    n = len(per)
    em = B.sheet("E&M SPS", "E&M WORKS OF THE PUMPING STATIONS (Rs. lakh) - R2 format, sheets Abstract E&M", 3 + n)
    B.header(em, 3, ["S.No.", "Item"] + [f"{p['tag']} ({p['outfall']})" for p in per] + ["Total"],
             [6, 52] + [16] * n + [16])
    ref = {"em": {}, "em_total": [], "sheets": made}
    tc = B.col(3 + n)
    for i, part in enumerate(PARTS):
        x = 4 + i
        em.cell(x, 1, i + 1)
        em.cell(x, 2, part)
        for j, p in enumerate(per):
            em.cell(x, 3 + j, f"={q(p['abs'])}!D{p['rows'] + i}").number_format = "#,##0.00"
        em.cell(x, 3 + n, f"=SUM(C{x}:{B.col(2 + n)}{x})").number_format = "#,##0.00"
        ref["em"][part] = f"'E&M SPS'!{tc}{x}"
    x = 4 + len(PARTS)
    em.cell(x, 2, "Total E&M").font = B.bold
    for j in range(n + 1):
        c = B.col(3 + j)
        em.cell(x, 3 + j, f"=SUM({c}4:{c}{x - 1})").number_format = "#,##0.00"
        if j < n:
            ref["em_total"].append(f"'E&M SPS'!{c}{x}")
    x += 1
    em.cell(x, 2, "Power connection charges")
    for j, p in enumerate(per):
        em.cell(x, 3 + j, f"={q(p['abs'])}!D{p['power']}").number_format = "#,##0.00"
    em.cell(x, 3 + n, f"=SUM(C{x}:{B.col(2 + n)}{x})").number_format = "#,##0.00"
    ref["power_total"] = f"'E&M SPS'!{tc}{x}"
    em.cell(x + 2, 2, "Each station's E&M from its technical statement (sheets EM TS) and estimate (EM Est) in the "
                      "format of the U.P. Jal Nigam E&M estimate R2 (District Elmwood zone, Springfield); rates in sheet "
                      "EM rates - yellow, to be confirmed.").font = B.italic
    return ref
