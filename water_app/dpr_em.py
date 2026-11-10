"""E&M works of the water DPR (dpr.py) and their O&M, in the format of the U.P. Jal Nigam E&M estimate 'Riverside R3 dt
29.1.2026' (Construction Division E&M, Springfield; Riverside extended area, sub zones 1-15) - user decisions 26-Oct-2026:
for every OZ from the design, new tube wells from the +15 years pumping main demand (sheet TW), a size between two of
R3 linear between them (beyond: by the size ratio, the exponent of the end pair).

    EM rates W   R3's rates (yellow): tube well, TW pumping plant by motor HP, OHT automation by outlet diameter,
                 booster set by HP, CWR pump by HP, the fixed items
    EM TS        one row per OZ: new tube wells and their motor (sheets TW, T3), the OHT outlet, the booster (VFD pump
                 of the design at an existing OHT too low), the CWR pumps (flow, head, HP)
    EM           R3 'Gen Abs': per OZ tube wells, TW pumping plants, SCADA, OHT automation, booster, CWR pumping plant,
                 its SCADA and sub-station, trial run, power connections; LCS once; totals by part
    EM O&M       R3 '5year O&M revise': staff, electricity, chlorination, repair, 5 years

    write(B) -> B.EM = {"parts": [(label, lakh cell, breakup head, qty text)], "power": lakh cell, "om": lakh cell,
                        "elec_year": Rs cell}
"""
import re

from .dpr import motor_margin, standby

PARTS = [("tw", "Construction of new tube wells", "Miscellaneous"),
         ("tw_pp", "Tube well pumping plants", "Machinery works"),
         ("tw_scada", "SCADA automation of tube wells", "Machinery works"),
         ("oht_auto", "OHT automation", "Machinery works"),
         ("booster", "Booster pumping plants with VFD", "Machinery works"),
         ("cwr_pp", "CWR pumping plants", "Machinery works"),
         ("cwr_scada", "SCADA automation of CWR pumping plants", "Machinery works"),
         ("cwr_sub", "LT / HT panels with sub-stations for CWRs", "Machinery works"),
         ("lcs", "Local control station", "Machinery works"),
         ("dma", "DMA equipment (sluice valve, flow meter, dismantling joint)", "Machinery works"),
         ("tr", "Three months trial run", "Miscellaneous")]


def q(name):
    return "'" + name.replace("'", "''") + "'" if re.search(r"[^A-Za-z0-9_]", name) else name


def _rates(B, M):
    """Sheet EM rates W. Returns (interp(key, x) -> formula, fixed(key) -> cell)."""
    ws = B.sheet("EM rates W", "E&M RATES - U.P. JAL NIGAM E&M ESTIMATE RIVERSIDE R3 (29.1.2026)", 6)
    for c, w in zip("ABCDEF", (12, 70, 12, 14, 12, 70)):
        ws.column_dimensions[c].width = w
    r = 5
    tables = {}
    for key, t in M["tables"].items():
        ws.cell(r, 1, key).font = B.bold
        ws.cell(r, 2, f"{t['text']} - {t['unit']} by {t['size']}").font = B.bold
        ws.cell(r, 6, t["src"])
        r += 1
        B.header(ws, r, ["", "", t["size"], t["unit"], "", ""])
        r += 1
        first = r
        for x, y in t["points"]:
            B.cell(ws, r, 3, x, inp=True)
            B.cell(ws, r, 4, y, fmt="0.00", inp=True)
            r += 1
        last = r - 1
        ws.cell(r, 2, "Exponent below the first size / above the last (size ratio)")
        if len(t["points"]) > 1:
            lo = f"=LN(D{first + 1}/D{first})/LN(C{first + 1}/C{first})"
            hi = f"=LN(D{last}/D{last - 1})/LN(C{last}/C{last - 1})"
        else:
            lo = hi = t["exp"]
        B.cell(ws, r, 3, lo, fmt="0.000", inp=len(t["points"]) == 1)
        B.cell(ws, r, 4, hi, fmt="0.000", inp=len(t["points"]) == 1)
        tables[key] = (first, last, r)
        r += 2
    ws.cell(r, 1, "Fixed items").font = B.bold
    r += 1
    B.header(ws, r, ["Key", "Item", "Rs lakh", "", "", "Source"])
    r += 1
    fixed = {}
    for key, (v, text, src) in M["fixed"].items():
        B.cell(ws, r, 1, key)
        B.cell(ws, r, 2, text)
        B.cell(ws, r, 3, v, fmt="0.00", inp=True)
        ws.cell(r, 6, src)
        fixed[key] = f"'EM rates W'!$C${r}"
        r += 1
    ws.cell(r + 1, 1, "A size between two of a table: linear between them; below the first / above the last: the end "
                      "value x (size / end size) ^ exponent (user decision 26-Oct-2026).").font = B.italic
    sh = "'EM rates W'!"

    def interp(key, x):
        a, b, e = tables[key]
        A, V = f"{sh}$C${a}:$C${b}", f"{sh}$D${a}:$D${b}"
        lo = f"{sh}$D${a}*(({x})/{sh}$C${a})^{sh}$C${e}"
        hi = f"{sh}$D${b}*(({x})/{sh}$C${b})^{sh}$D${e}"
        if a == b:
            return f"IF(({x})>0,{lo},0)"
        m = f"MATCH({x},{A},1)"
        lin = f"INDEX({V},{m})+(({x})-INDEX({A},{m}))*(INDEX({V},{m}+1)-INDEX({V},{m}))/(INDEX({A},{m}+1)-INDEX({A},{m}))"
        return f"IF(({x})<=0,0,IF(({x})<={sh}$C${a},{lo},IF(({x})>={sh}$C${b},{hi},{lin})))"
    return interp, fixed


def _ts(B, M):
    """Sheet EM TS: one row per OZ. Returns {key: column letter}, first row, last row."""
    R, P = M["rules"], B.S["pump"]
    SB = B.crit["standby_pumps"]["value"]                 # CPHEEO 5.7.5 (user decisions 7-Nov-2026)
    ws = B.sheet("EM TS", "E&M TECHNICAL STATEMENT - TUBE WELLS, OHT AUTOMATION, BOOSTERS, CWR PUMPS (per operation zone)", 21)
    cols = [("oz", "Operation zone", 22), ("tw", "New tube wells incl. standby (sheet TW, O)", 10), ("hp", "TW motor HP (sheet T14 of the OZ)", 10),
            ("hrs", "Pumping hours (T14, +15)", 10), ("dia", "OHT outlet (mm) - design", 10),
            ("vh", "Booster (VFD) head (m) - design", 10), ("vq", "Booster flow, peak (L/s)", 10),
            ("vkw", "Booster (VFD) kW - design", 10), ("bw", "Booster pumps working", 9), ("bs", "Booster pumps standby", 9),
            ("bhp", "Booster motor HP each", 9), ("ckl", "New CWR (KL) - T3", 10), ("cw", "CWR pumps working", 9),
            ("cs", "CWR pumps standby", 9), ("cq", "CWR pump discharge (L/s)", 10), ("ch", "CWR pump head (m)", 10),
            ("chp", "CWR motor HP each", 9), ("q", "Discharge of a new TW (LPM) - sheet TW", 10),
            ("tws", "Standby tube wells of them (sheet TW, N)", 10), ("rb", "Rebored tube wells (sheet TW, P)", 10)]
    B.header(ws, 5, ["S.No."] + [c[1] for c in cols], [6] + [c[2] for c in cols])
    ws.row_dimensions[5].height = 60
    col = {k: B.col(2 + i) for i, (k, _, _) in enumerate(cols)}
    first = 6
    for i, t in enumerate(B.T3):
        x, s, rf, z = first + i, q(t["sheet"]), t["ref"], t["zone"]
        C = lambda k: f"{col[k]}{x}"
        hp = f"{C('cq')}*60*{C('ch')}/4500/{R['cwr_efficiency']}"          # a CWR pump's HP input
        d = re.search(r"(\d+)", z.get("outlet") or "")
        vals = {"oz": z["name"], "tw": f"=TW!O{6 + i}", "hp": f"={s}!F{rf['bhp']}", "hrs": f"={s}!E{rf['q_pump'] - 3}",
                "dia": int(d.group(1)) if d else 0, "vh": z.get("vfd_head_m") or 0,
                "vq": round(z.get("flow_lps") or 0.0, 2) if z.get("vfd_head_m") else 0,
                "vkw": z.get("vfd_kw") or 0,
                "bw": f"=IF({C('vkw')}>0,ROUNDUP({C('vq')}/{R['booster_lps_per_pump']},0),0)",
                "bs": f"={standby(C('bw'), SB)}",
                "bhp": f"=IF({C('bw')}>0,CEILING({C('vkw')}/0.746/{C('bw')}*"
                       f"(1+{motor_margin(P, C('vkw') + '/' + C('bw'))}),5),0)",
                "ckl": f"={s}!F{rf['cwr']}", "cw": f"=IF({C('ckl')}>0,{R['cwr_working']},0)",
                "cs": f"={standby(C('cw'), SB)}",
                "cq": f"=IF({C('cw')}>0,{s}!E{rf['pm']}*1000/({C('hrs')}*3600)/{C('cw')},0)",
                "ch": f"=IF({C('cw')}>0,{s}!F{rf['cwr_head']},0)",
                "chp": f"=IF({C('cw')}>0,CEILING({hp}*(1+{motor_margin(P, hp + '*0.746')}),5),0)",
                "q": f"=TW!I{6 + i}", "tws": f"=TW!N{6 + i}", "rb": f"=TW!P{6 + i}"}
        B.cell(ws, x, 1, i + 1)
        for k, v in vals.items():
            B.cell(ws, x, 2 + list(col).index(k), v, fmt="#,##0.0" if k in ("vq", "vkw", "cq", "vh") else "#,##0",
                   inp=k in ("dia", "vh", "vq", "vkw"))
    last = first + len(B.T3) - 1
    notes = ["Booster: the VFD pump of the design at an existing OHT whose staging cannot give 17 m (CPHEEO Table 2.7 "
             f"S.No.10); {R['booster_lps_per_pump']} L/s a working pump (R3: 1 W + 1 S at 37.5 LPS, 2 W + 1 S from 42.5 "
             f"LPS); HP = kW / 0.746 / pumps x (1 + the CPHEEO margin by kW, Riverside "
             "water DPR p360), to 5 HP.",
             f"CWR pumps (where the T3 asks for a CWR - more than 3 tube wells): {R['cwr_working']} working "
             f"for the +15 years pumping main demand in the pumping hours; head = the T3 CWR pumps' "
             f"head (staging + depth of water in OHT + terminal + sump of the CWR + friction, Riverside water DPR; the "
             f"tube wells fill the CWR); HP = Q x 60 x H / 4500 / {R['cwr_efficiency']} x (1 + the CPHEEO margin by kW), "
             "to 5 HP (R3 'R1 cwr HP calcu').",
             "Standby by the working ones as CPHEEO water manual Part A (2024) 5.7.5 p245-246: "
             + ", ".join(f"{(SB[k - 1][0] + 1) if k else 1}-{up} W + {s} S" for k, (up, s) in enumerate(SB))
             + " - the booster and CWR pumps, and the new tube wells of an OZ: standby tube wells, each built whole "
             "as a new one (a bore takes one submersible pump; user decision 7-Nov-2026). Rebored tube wells: as the "
             "Riverside R3 (boring, pumping plant, SCADA and trial run as a new one, the LT cable to the existing pump "
             "house; no new power connection)."]
    for k, t in enumerate(notes):
        ws.cell(last + 2 + k, 2, t).font = B.italic
    return col, first, last


def write(B):
    """The E&M sheets (see the module text); sets B.EM."""
    M = B.S["em"]
    interp, fixed = _rates(B, M)
    col, f0, f1 = _ts(B, M)
    B.EMTS = {"col": col, "first": f0}                  # for the panel and booster rooms (dpr_civil.buildings)
    T = lambda k, i: f"'EM TS'!${col[k]}${f0 + i}"
    from . import dpr_emd                               # the E&M design sheets give the cost (user decision 6-Nov-2026)
    X = dpr_emd.write(B, T)
    ws = B.sheet("EM", "ABSTRACT OF COST - E&M WORKS (TUBE WELLS, PUMPING PLANTS, AUTOMATION, CWR, POWER CONNECTIONS)", 8)
    B.header(ws, 5, ["Sl. No.", "Description of work", "Qty.", "Unit", "Rate (Rs lakh)", "Amount (Rs lakh)", "Part", ""],
             [7, 70, 9, 8, 14, 16, 10, 2])
    x = [6]
    works, power = [], []

    def line(no, text, qty, unit, rate, part):
        r = x[0]
        B.cell(ws, r, 1, no)
        B.cell(ws, r, 2, text)
        B.cell(ws, r, 3, qty, fmt="#,##0")
        B.cell(ws, r, 4, unit)
        B.cell(ws, r, 5, rate, fmt="#,##0.00")
        B.cell(ws, r, 6, f"=C{r}*E{r}", fmt="#,##0.00")
        ws.cell(r, 7, part)
        x[0] += 1
        return r
    for i, t in enumerate(B.T3):
        z = t["zone"]
        B.cell(ws, x[0], 2, f"Operation zone {z['name']}", bold=True)
        x[0] += 1
        a = x[0]
        has_b, has_c = f"IF({T('bw', i)}>0,1,0)", f"IF({T('ckl', i)}>0,1,0)"
        tw_rb = f"{T('tw', i)}+{T('rb', i)}"            # new (standby too) and rebored: a pumping plant each
        line(1, f'="Construction of tube well "&{X["hd"][i]}&" x "&{X["dia"][i]}&" mm ("&{T("tw", i)}&" new, "&'
                f'{T("tws", i)}&" of them standby)"',
             f"={T('tw', i)}", "Nos", f"={X['tw'][i]}", "tw")
        line(2, f'="Rebore of tube well "&{X["hd"][i]}&" x "&{X["dia"][i]}&" mm"', f"={T('rb', i)}", "Nos",
             f"={X['tw'][i]}", "tw")
        line(3, f'="TW pumping plant, "&{T("hp", i)}&" HP (new and rebored)"', f"={tw_rb}", "Nos",
             "=" + interp("tw_pp", T("hp", i)), "tw_pp")
        line(4, "SCADA automation of TW (new and rebored)", f"={tw_rb}", "Nos", f"={fixed['tw_scada']}", "tw_scada")
        line(5, "Connection, laying & replacement of old LT cable for rebored TW, submersible cable to the existing "
                "pump house", f"={T('rb', i)}", "Nos", f"={fixed['rebore_cable']}", "tw_pp")
        line(6, f'="Automation of OHT of "&{T("dia", i)}&" mm outlet"', 1, "Job", "=" + interp("oht_auto", T("dia", i)),
             "oht_auto")
        ws.cell(x[0] - 1, 3).fill = B.yellow
        n_b = f"({T('bw', i)}+{T('bs', i)})"
        line(7, f'="Booster pumping plant with VFD, "&{T("bw", i)}&" W + "&{T("bs", i)}&" S x "&{T("bhp", i)}&" HP"',
             f"={has_b}", "Job",
             f"={n_b}*{interp('booster', T('bhp', i))}+{fixed['booster_lot']}+{n_b}*{fixed['booster_pt']}", "booster")
        n_c = f"({T('cw', i)}+{T('cs', i)})"
        line(8, f'="CWR pumping plant, "&{T("cw", i)}&" W + "&{T("cs", i)}&" S x "&{T("chp", i)}&" HP"', f"={has_c}",
             "Job", f"={n_c}*{interp('cwr_pump', T('chp', i))}+{fixed['cwr_pp_rest']}", "cwr_pp")
        line(9, "SCADA automation of CWR pumping plant", f"={has_c}", "Job", f"={fixed['cwr_scada']}", "cwr_scada")
        line(10, f'="LT / HT panels with sub-station for CWR"&IF({X["tf_n"][i]}>0,", "&{X["tf_n"][i]}&" x "&'
                f'{X["tf_kva"][i]}&" kVA transformers","")',
             f"={has_c}", "Job", f"={fixed['cwr_sub']}+{X['tf_n'][i]}*{interp('transformer', X['tf_kva'][i])}",
             "cwr_sub")
        line(11, "Three months trial run of tube wells (new and rebored)", f"={tw_rb}", "Nos", f"={X['tr_tw'][i]}",
             "tr")
        line(12, "Three months trial run of booster pumping plant", f"={has_b}", "Job", f"={X['tr_b'][i]}", "tr")
        line(13, "Three months trial run of CWR pumping plant", f"={has_c}", "Job", f"={X['tr_c'][i]}", "tr")
        b = x[0]
        B.cell(ws, b, 2, "Total (works)", bold=True)
        B.cell(ws, b, 6, f"=SUM(F{a}:F{b - 1})", fmt="#,##0.00", bold=True)
        works.append(f"F{b}")
        x[0] += 1
        p1 = line(14, "New power connection with transmission line for new tube wells", f"={T('tw', i)}", "Nos",
                  f"={X['pc_tw'][i]}", "power")
        line(15, "New power connection with transmission line for CWR", f"={has_c}", "Job", f"={X['pc_c'][i]}",
             "power")
        line(16, "New power connection with transmission line for booster pumping plant", f"={has_b}", "Job",
             f"={X['pc_b'][i]}", "power")
        power.append(f"F{p1}:F{p1 + 2}")
        x[0] += 1
    B.cell(ws, x[0], 2, "Scheme", bold=True)
    x[0] += 1
    lr = line(1, "Local control station (LCS)", M["rules"]["lcs"], "Job", f"={fixed['lcs']}", "lcs")
    ws.cell(lr, 3).fill = B.yellow
    x[0] += 1
    # the DMA site equipment of every DMA, by its line size (Riverside water DPR p55, user decision 6-Nov-2026)
    dmas = [d for d in ((B.info.get("tech") or {}).get("dmas") or []) if d.get("line_mm")]
    d0 = x[0]
    if dmas:
        B.cell(ws, x[0], 2, "DMA equipment details in all zones", bold=True)
        x[0] += 1
        by = {}
        for d in dmas:
            by.setdefault(d["line_mm"], []).append(d["name"])
        for i, (mm, names) in enumerate(sorted(by.items()), 1):
            s = ", ".join(names[:12]) + (" ..." if len(names) > 12 else "")
            line(i, f"{mm} mm dia line size DMA equipment for {s}", len(names), "Job", "=" + interp("dma_auto", mm),
                 "dma")
    dm = f"+SUM(F{d0}:F{x[0] - 1})" if dmas else ""
    x[0] += 1
    g = x[0]
    B.cell(ws, g, 2, "Gross total of works (Rs lakh)", bold=True)
    B.cell(ws, g, 6, "=" + "+".join(works) + f"+F{lr}{dm}", fmt="#,##0.00", bold=True)
    B.cell(ws, g + 1, 2, "Gross total of power connections (Rs lakh)", bold=True)
    B.cell(ws, g + 1, 6, "=SUM(" + ",".join(power) + ")", fmt="#,##0.00", bold=True)
    r = g + 3
    ws.cell(r, 2, "By part (Rs lakh) - ABS Com").font = B.bold
    r += 1
    parts = []
    last_row = g - 1
    # the quantity of each part for ABS Com, as the Riverside water DPR p45 ("48 Nos", "15 Job", ...; user 7-Nov-2026)
    rng = lambda k: f"'EM TS'!${col[k]}${f0}:${col[k]}${f1}"
    q_em = lambda k: f'SUMIF(EM!$G$6:$G${last_row},"{k}",EM!$C$6:$C${last_row})'
    n_tw, n_c, n_b = (f"SUM({rng('tw')})+SUM({rng('rb')})", f'COUNTIF({rng("ckl")},">0")',
                      f'COUNTIF({rng("bw")},">0")')
    qty = {"tw": (n_tw, "Nos"), "tw_pp": (n_tw, "Job"), "tw_scada": (n_tw, "Job"), "oht_auto": (q_em("oht_auto"), "Job"),
           "booster": (n_b, "Nos"), "cwr_pp": (n_c, "Nos"), "cwr_scada": (n_c, "Jobs"), "cwr_sub": (n_c, "Job"),
           "lcs": (q_em("lcs"), "Job"), "dma": (q_em("dma"), "Nos"), "tr": (str(len(B.T3)), "Job")}
    for key, label, head in PARTS:
        B.cell(ws, r, 2, label)
        B.cell(ws, r, 6, f"=SUMIF($G$6:$G${last_row},\"{key}\",$F$6:$F${last_row})", fmt="#,##0.00")
        ws.cell(r, 7, key)
        n, unit = qty[key]
        parts.append((label, f"EM!$F${r}", head, f'=({n})&" {unit}"'))
        r += 1
    B.cell(ws, r, 2, "Total", bold=True)
    B.cell(ws, r, 6, f"=SUM(F{r - len(PARTS)}:F{r - 1})", fmt="#,##0.00", bold=True)
    ws.cell(r + 2, 2, "Rates: sheet EM rates W (U.P. Jal Nigam E&M estimate Riverside R3, 29.1.2026); quantities: sheet "
                      "EM TS from the design; tube well, sub-station transformers, trial runs and power connections "
                      "from the E&M design sheets E5 TW Estimate, E7 CWR Electrical, E9 Trial Run, E8 Power Connection "
                      "(Riverside water DPR p319-361)."
            ).font = B.italic
    ws.column_dimensions["G"].hidden = True
    ws.freeze_panes = "C6"
    B.sign(ws, r + 4, 5)
    em_works = f"EM!$F${g}"
    B.EM = {"parts": parts, "power": f"EM!$F${g + 1}", "works": em_works,
            "power_qty": f'=({q_em("power")})&" Nos"'}
    _om(B, M, col, f0, f1)


def _om(B, M, col, f0, f1):
    """Sheet EM O&M (R3 '5year O&M revise')."""
    O = M["om"]
    ws = B.sheet("EM O&M", "EXPENDITURE ON 5 YEAR OPERATION AND MAINTENANCE - E&M WORKS", 6)
    for c, w in zip("ABCDEF", (6, 66, 12, 10, 14, 16)):
        ws.column_dimensions[c].width = w
    B.header(ws, 5, ["S.N.", "Particulars", "Qty (Nos)", "Month", "Rate (Rs)", "Amount (Rs)"])
    rng = lambda k: f"'EM TS'!${col[k]}${f0}:${col[k]}${f1}"
    x = 6
    ws.cell(x, 2, "1. Staff (scheme)").font = B.bold
    x += 1
    s0 = x
    for lab, n, pay in O["staff"]:
        B.cell(ws, x, 2, lab)
        B.cell(ws, x, 3, n, inp=True)
        B.cell(ws, x, 4, 12)
        B.cell(ws, x, 5, pay, fmt="#,##0", inp=True)
        B.cell(ws, x, 6, f"=C{x}*D{x}*E{x}", fmt="#,##0")
        x += 1
    B.cell(ws, x, 2, "Staff for one year", bold=True)
    B.cell(ws, x, 6, f"=SUM(F{s0}:F{x - 1})", fmt="#,##0", bold=True)
    staff = x
    x += 2
    ws.cell(x, 2, f"2. Electricity (fixed Rs {O['fixed_rs_per_kva_month']} / kVA / month, Rs {O['tariff']} / kWh, "
                  f"duty {O['duty'] * 100:g} %)").font = B.bold
    x += 1
    tw_kw = f"({rng('hp')}*0.746+{O['tw_aux_kw']})"
    cwr_kw = f"(({rng('cw')}*{rng('chp')}*0.746+{O['cwr_aux_kw']})*({rng('ckl')}>0))"
    run = f"({rng('tw')}-{rng('tws')})"                   # the working ones (the standby ones do not run)
    rows = [("New tube wells (standby too): connected kW", f"=SUMPRODUCT({rng('tw')},{tw_kw})", "kW"),
            ("New tube wells (working): energy a year (kWh) - pumping hours of the OZ",
             f"=SUMPRODUCT({run},{tw_kw},{rng('hrs')})*365", "kWh"),
            ("CWR pumping plants: connected kW", f"=SUMPRODUCT({cwr_kw})", "kW"),
            ("CWR pumping plants: energy a year (kWh)", f"=SUMPRODUCT({cwr_kw},{rng('hrs')})*365", "kWh"),
            ("Booster pumping plants: kW (design)", f"=SUM({rng('vkw')})", "kW"),
            (f"Booster pumping plants: energy a year (kWh) - {O['booster_hours']} h a day",
             f"=SUM({rng('vkw')})*{O['booster_hours']}*365", "kWh"),
            ("Local control station: kW", f"={O['lcs_kw']}", "kW"),
            ("Local control station: energy a year (kWh) - 24 h", f"={O['lcs_kw']}*24*365", "kWh")]
    e0 = x
    for lab, f, unit in rows:
        B.cell(ws, x, 2, lab)
        B.cell(ws, x, 3, f, fmt="#,##0")
        B.cell(ws, x, 4, unit)
        x += 1
    kw = f"C{e0}+C{e0 + 2}+C{e0 + 4}+C{e0 + 6}"
    kwh = f"C{e0 + 1}+C{e0 + 3}+C{e0 + 5}+C{e0 + 7}"
    B.cell(ws, x, 2, "Fixed charges a year = kW / pf x rate x 12")
    B.cell(ws, x, 6, f"=({kw})/{O['pf']}*{O['fixed_rs_per_kva_month']}*12", fmt="#,##0")
    B.cell(ws, x + 1, 2, "Running charges a year = kWh x tariff")
    B.cell(ws, x + 1, 6, f"=({kwh})*{O['tariff']}", fmt="#,##0")
    B.cell(ws, x + 2, 2, "Electricity duty")
    B.cell(ws, x + 2, 6, f"=(F{x}+F{x + 1})*{O['duty']}", fmt="#,##0")
    B.cell(ws, x + 3, 2, "Electricity for one year", bold=True)
    B.cell(ws, x + 3, 6, f"=SUM(F{x}:F{x + 2})", fmt="#,##0", bold=True)
    elec = x + 3
    x += 5
    B.cell(ws, x, 2, f"3. Chlorination: Rs {O['chlorine_rs_per_tw_month']} a working new tube well a month (R3)")
    B.cell(ws, x, 3, f"=SUM({rng('tw')})-SUM({rng('tws')})")
    B.cell(ws, x, 4, 12)
    B.cell(ws, x, 5, O["chlorine_rs_per_tw_month"], fmt="#,##0", inp=True)
    B.cell(ws, x, 6, f"=C{x}*D{x}*E{x}", fmt="#,##0")
    chl = x
    x += 2
    B.cell(ws, x, 2, f"4. Repair and maintenance of pumping plants and SCADA: {O['repair'] * 100:g} % of the E&M works "
                     f"from year {O['repair_from_year']}")
    B.cell(ws, x, 6, f"={B.EM['works']}*100000*{O['repair']}", fmt="#,##0")
    rep = x
    x += 2
    ws.cell(x, 2, f"5. O&M for 5 years (inflation {O['inflation'] * 100:g} % a year)").font = B.bold
    x += 1
    y0 = x
    for k in range(5):
        B.cell(ws, x, 2, f"Year {k + 1}")
        f = (f"=F{staff}+F{chl}" if k == 0 else f"=F{x - 1}*(1+{O['inflation']})" +
             (f"+F{rep}" if k + 1 == O["repair_from_year"] else ""))
        B.cell(ws, x, 6, f, fmt="#,##0")
        x += 1
    # as the Riverside water DPR p57 (user 7-Nov-2026): labour cess, GST and centage on the O&M without electricity,
    # the electricity as it is
    B.cell(ws, x, 2, "Total 5 years without electricity")
    B.cell(ws, x, 6, f"=SUM(F{y0}:F{x - 1})", fmt="#,##0")
    B.cell(ws, x + 1, 2, f"Labour cess {O['labour_cess'] * 100:g} %")
    B.cell(ws, x + 1, 6, f"=F{x}*{O['labour_cess']}", fmt="#,##0")
    B.cell(ws, x + 2, 2, f"GST {O['gst'] * 100:g} %")
    B.cell(ws, x + 2, 6, f"=F{x}*{O['gst']}", fmt="#,##0")
    B.cell(ws, x + 3, 2, f"Centage {O['centage'] * 100:g} %")
    B.cell(ws, x + 3, 6, f"=F{x}*{O['centage']}", fmt="#,##0")
    B.cell(ws, x + 4, 2, "Electricity for 5 years")
    B.cell(ws, x + 4, 6, f"=F{elec}*5", fmt="#,##0")
    B.cell(ws, x + 5, 2, "Total 5 year O&M of the E&M works with electricity (Rs)", bold=True)
    B.cell(ws, x + 5, 6, f"=SUM(F{x}:F{x + 4})", fmt="#,##0", bold=True)
    B.cell(ws, x + 6, 2, "Say (Rs lakh)", bold=True)
    B.cell(ws, x + 6, 6, f"=ROUND(F{x + 5}/100000,2)", fmt="#,##0.00", bold=True)
    # for Form J (E&M works): the 5 years' O&M without electricity (with GST) and the electricity, Rs lakh
    B.EMOM = {"works": f"ROUND(('EM O&M'!$F${x}+'EM O&M'!$F${x + 2})/100000,2)",
              "elec": f"ROUND('EM O&M'!$F${x + 4}/100000,2)"}
    lk = lambda r: f"ROUND('EM O&M'!$F${r}/100000,2)"
    B.EM["om_rows"] = {"elec": lk(x + 4), "works": lk(x), "cess": lk(x + 1), "gst": lk(x + 2), "cent": lk(x + 3)}
    ws.cell(x + 8, 2, "R3 '5year O&M revise': staff of the scheme, electricity of tube wells, CWR, boosters and LCS, "
                      "chlorination, repair from the 3rd year; the electricity of the pumps follows the design "
                      "(motors of sheet EM TS, pumping hours of T3) - yellow, to be confirmed.").font = B.italic
    B.sign(ws, x + 11, 5)
    B.EM.update(om=f"'EM O&M'!$F${x + 6}", elec_year=f"'EM O&M'!$F${elec}")
