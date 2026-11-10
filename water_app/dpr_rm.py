"""The water DPR's phase 2 sheets (user decisions 31-Oct-2026): the rising mains of the new tube wells (rising.py).

    RM Design  (renamed T7 Rising Main)   each new tube well's main: length, discharge, static head, the economical size
               and its surge (values of the design); then for each the candidate sizes with live formulas - pipe (+
               specials), pump sets (+ standby, replaced after 15 years), capitalised energy - so a change of the yellow
               parameters shows at once whether the size of the design is still the least (CPHEEO 6.7, Annexure 6.1)
    RM         (renamed D5 Rising Main)   the estimate: pipes, specials, excavation, laying, a sluice valve and a non
               return valve at each tube well, air valves (one a km), a scour valve each, thrust blocks of DI mains,
               road dismantling / reinstatement by the road shares of sheet Project - its total in ABS Com
"""
import json
import math

from . import design as wd
from .dpr import ROADS, SOR_FILE, SOR_RNG, q, size_key


def _done(B):
    R = B.info.get("rising") or {}
    return [t for t in R.get("tws") or [] if t.get("size")]


def laid_rate(S):
    """(size, class) -> Rs / m laid: the UPJN supply rate + carting / laying (HDPE AOR, DI SOR); a DI main in K9 at
    the K9 supply rate (M.193, pipe_supply_k9), the laying alike - for the economical size too (rising.economic;
    CPHEEO 6.7.4: the DSR price is good enough)."""
    with open(SOR_FILE, encoding="utf-8") as fh:
        sor = {str(c): r for c, _, _, r in json.load(fh)["items"] if c and r is not None}

    def rate(s, cls="K7"):
        sup = S["pipe_supply_k9"].get(s) if cls == "K9" else None
        lay = S["hdpe_carting"].get(s, 0.0) if s.startswith("HDPE") else sor.get(S["di_laying_sor"].get(s), 0.0)
        return float(sup if sup is not None else S["pipe_supply"].get(s, 0.0)) + float(lay or 0.0)
    return rate


def design(B):
    """Sheet RM Design (see the module text)."""
    tws = _done(B)
    B.RMT = None
    if not tws:
        return
    crit, S = B.crit, B.S
    X = crit["rising_main_economics"]["value"]
    sz = {s["name"]: s for s in wd.load_pipes()}
    ws = B.sheet("RM Design", "RISING MAINS OF THE NEW TUBE WELLS - ECONOMICAL SIZE AND SURGE", 17)
    widths = [6, 16, 14, 10, 10, 9, 10, 11, 8, 9, 9, 9, 9, 10, 9, 9, 10]
    for c, w in enumerate(widths, 1):
        ws.column_dimensions[B.col(c)].width = w
    ws.cell(5, 1, "A. Parameters (CPHEEO 6.7 p400-402, Annexure 6.1 p1157-1159; yellow - change to the project)").font = B.bold
    par = [("i", "MAAR (interest - inflation)", X["interest"], "0.0%"),
           ("n", "Life of the pump sets (years) - two stages in 30 years", X["pump_life"], "0"),
           ("kw", "Cost of pump sets (Rs / kW)", X["pump_rs_per_kw"], "#,##0"),
           ("sb", "Standby pump capacity", X["standby"], "0%"),
           ("eff", "Combined efficiency of the pump set", X["efficiency"], "0%"),
           ("mi", "Minor losses (share of the friction)", X["minor"], "0%"),
           ("sp", "Specials (share of the pipe cost)", X["specials"], "0%"),
           ("tar", "Energy (Rs / kWh, with duty)", X["energy_rs_per_kwh"], "0.000"),
           ("hrs", "Pumping hours a day", crit["tubewell_pumping_hours"]["value"], "0")]
    P = {}
    for i, (k, lab, v, fmt) in enumerate(par):
        r = 6 + i
        B.cell(ws, r, 2, lab)
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=5)
        B.cell(ws, r, 6, v, fmt=fmt, inp=True)
        P[k] = f"$F${r}"
    r = 6 + len(par) + 1
    ws.cell(r, 1, "B. The mains of the design - each tube well its own main along the roads to its OHT (user decision "
                  "31-Oct-2026); surge on a sudden pump stop h = c V / g, c = 1425 / sqrt(1 + k d / (E t)) (CPHEEO "
                  "6.16.4 p428) against the pipe's MOP (with surge; its head against the AOP) - IS 8329 Annex E "
                  "(Amendment 1): DI K-7 AOP 0.8 MPa, MOP 1.25 MPa").font = B.bold
    B.header(ws, r + 1, ["S.N.", "Tube well", "OZ", "Site", "Length (m)", "Q (L/s)", "Static head (m)", "Size", "V (m/s)",
                         "Friction (m)", "Head (m)", "kW", "c (m/s)", "Surge (m)", "Head + surge (m)", "MOP (m)",
                         "Surge"])
    ws.row_dimensions[r + 1].height = 45
    row_of = {}
    for i, t in enumerate(tws, 1):
        x = r + 1 + i
        vals = [i, t["name"], t["oz"], "map" if t.get("placed") else "suggested", t["length_m"], t["q_lps"], t["static_m"],
                t["size"] + (f" {t['cls']}" if t.get("cls") else ""), t["v"], t["hf_m"], t["head_m"], t["kw"], t["celerity"], t["surge_m"], t["max_m"], t["rating_m"],
                "OK" if t["surge_ok"] else "class / protection"]
        for c, v in enumerate(vals, 1):
            B.cell(ws, x, c, v, fmt="#,##0.00" if isinstance(v, float) else None)
        if not t["surge_ok"]:
            ws.cell(x, 17).font = B.red
        row_of[t["name"]] = x
    B.RMT_ROWS = (r + 2, r + 1 + len(tws))              # the mains' rows: OZ C, length E, size H (dpr_front)
    r = r + 2 + len(tws) + 1
    ws.cell(r, 1, "C. Candidate sizes of each main (live: the least total is the economical size)").font = B.bold
    B.header(ws, r + 1, ["S.N.", "Tube well", "Size", "ID (mm)", "C", "Rate laid (Rs/m)", "V (m/s)", "Friction (m)",
                         "Head (m)", "kW", "Pipe + specials (Rs lakh)", "Pump sets PW (Rs lakh)", "Energy PW (Rs lakh)",
                         "Total (Rs lakh)", "Least", "Design", ""])
    ws.row_dimensions[r + 1].height = 45
    rate = laid_rate(S)
    x = r + 2
    for i, t in enumerate(tws, 1):
        a0 = x
        src = row_of[t["name"]]
        for a in t["alts"]:
            s = sz[a["size"]]
            L, Q, H0 = f"$E${src}", f"($F${src}/1000)", f"$G${src}"
            d = f"(D{x}/1000)"
            pwf = f"(1+(1+{P['i']})^-{P['n']})"
            B.cell(ws, x, 1, i)
            B.cell(ws, x, 2, t["name"])
            B.cell(ws, x, 3, a["size"] + (" K9" if a.get("cls") == "K9" else ""))
            B.cell(ws, x, 4, s["id_mm"])
            B.cell(ws, x, 5, s["C"])
            B.cell(ws, x, 6, round(rate(a["size"], a.get("cls", "K7")), 2), fmt="#,##0.00", inp=True)
            B.cell(ws, x, 7, f"={Q}/(PI()*{d}^2/4)", fmt="0.00")
            B.cell(ws, x, 8, f"=10.67*{L}*{Q}^1.852/(E{x}^1.852*{d}^4.87)*(1+{P['mi']})", fmt="0.00")
            B.cell(ws, x, 9, f"={H0}+H{x}", fmt="0.00")
            B.cell(ws, x, 10, f"=9.81*{Q}*I{x}/{P['eff']}", fmt="0.00")
            B.cell(ws, x, 11, f"={L}*F{x}*(1+{P['sp']})/100000", fmt="#,##0.00")
            B.cell(ws, x, 12, f"=J{x}*(1+{P['sb']})*{P['kw']}*{pwf}/100000", fmt="#,##0.00")
            B.cell(ws, x, 13, f"=J{x}*{P['hrs']}*365*{P['tar']}*(1-(1+{P['i']})^-{P['n']})/{P['i']}*{pwf}/100000",
                   fmt="#,##0.00")
            B.cell(ws, x, 14, f"=K{x}+L{x}+M{x}", fmt="#,##0.00", bold=True)
            B.cell(ws, x, 16, "design" if a.get("best") else "")
            x += 1
        for y in range(a0, x):
            B.cell(ws, y, 15, f'=IF(N{y}=MIN($N${a0}:$N${x - 1}),"least","")')
    ws.cell(x + 1, 1, "Pipe: the UPJN supply rate + carting / laying (D5) - a DI size whose head / head + surge "
                      "exceeds K-7 (IS 8329 Annex E) at its K9 rate (M.193), so each size competes in the class it "
                      "needs; excavation and roads alike for every size (CPHEEO 6.7.4); pump sets PW = cost now + its replacement after 15 years at present worth; energy "
                      "= kW x hours x 365 x rate, capitalised over 15 years (Eq. 1) + the second 15 years at present worth "
                      "(Eq. 3); the tube well pumps its discharge in both stages.").font = B.italic
    B.sign(ws, x + 4, 12)
    B.RMT = True


def estimate(B):
    """Sheet RM (see the module text). B.RM = {"lakh": its total in lakh} or None."""
    tws = _done(B)
    B.RM = None
    if not tws:
        return
    S, PR = B.S, B.PR
    tr = S["trench"]
    by, n_by = {}, {}                                    # "DI 200" / "DI 200 K9" (class above K-7, user 31-Oct-2026)
    key = lambda t: t["size"] + (" K9" if t.get("cls") == "K9" else "")
    for t in tws:
        by[key(t)] = by.get(key(t), 0.0) + t["length_m"]
        n_by[key(t)] = n_by.get(key(t), 0) + 1
    sizes = sorted(by, key=lambda s: (size_key(s)[0] != "HDPE", size_key(s)[1], s))
    base = lambda s: s.replace(" K9", "")
    bp = S["civil"]["rm_bypass_m"]                       # bye pass at the OHT, each main (Riverside water DPR p205)
    ws = B.sheet("RM", "ESTIMATE OF THE RISING MAINS OF THE NEW TUBE WELLS", 12)
    # quantities by size (as sheet RC): length, excavation, road cutting
    heads = ["S.N.", "Size", "OD (mm)", "Mains (nos)", "Length (m)", "Air valves (nos)", "Excavation (cum)"] + \
            [f"{k} (sqm)" for k in ROADS[:4]]
    B.header(ws, 5, heads, [6, 12, 9, 9, 11, 9, 12] + [12] * 4)
    ws.row_dimensions[5].height = 45
    Q = {}
    for i, s in enumerate(sizes):
        x = 6 + i
        mat, d = size_key(s)
        B.cell(ws, x, 1, i + 1)
        B.cell(ws, x, 2, s)
        B.cell(ws, x, 3, d)
        B.cell(ws, x, 4, n_by[s])
        B.cell(ws, x, 5, round(by[s], 1), fmt="#,##0.0")
        B.cell(ws, x, 6, sum(math.ceil(t["length_m"] / 1000) for t in tws if key(t) == s))
        B.cell(ws, x, 7, f"=(E{x}+{bp}*D{x})*(C{x}/1000+{tr['width_add_m']})*(C{x}/1000+{tr['depth_add_m']})",
               fmt="#,##0.0")
        for j, k in enumerate(ROADS[:4]):
            B.cell(ws, x, 8 + j, f"=ROUND(E{x}*{PR['road:' + k]},0)*(C{x}/1000+{tr['width_add_m']})", fmt="#,##0.0")
        Q[s] = x
    q0, q1 = 6, 5 + len(sizes)
    tot = q1 + 1
    B.cell(ws, tot, 2, "Total", bold=True)
    for c in range(4, 12):
        B.cell(ws, tot, c, f"=SUM({B.col(c)}{q0}:{B.col(c)}{q1})", fmt="#,##0.0", bold=True)
    ws.cell(tot + 1, 1, f"Mains of sheet RM Design + a {bp:g} m bye pass at the OHT each (Riverside water DPR p205; "
                        f"pipes, laying and excavation); excavation L x (D + {tr['width_add_m']}) x (D + "
                        f"{tr['depth_add_m']}), road cutting (D + 0.6) x the length under each road (road shares of sheet "
                        "Project), as sheet RC; air valves one a km of each main.").font = B.italic
    h = tot + 3
    B.header(ws, h, ["Sl No", "SOR Ref.", "Item of work", "No.", "L", "B", "H/D", "Qty", "Rate", "Unit", "Amount",
                     "Rate from"])
    for c, w in zip("ABCDEFGHIJKL", (6, 10, 60, 8, 10, 6, 6, 16, 12, 7, 15, 44)):
        ws.column_dimensions[c].width = max(ws.column_dimensions[c].width or 0, w)
    sv = "'SV Rate'"
    R = S["valve_rate_row"]
    x = [h + 1]
    lookup = lambda code: f"IFERROR(VLOOKUP({code},{SOR_RNG},4,0),0)"

    def title(no, text):
        B.cell(ws, x[0], 1, no)
        B.cell(ws, x[0], 3, text, bold=True).alignment = B.wrap
        ws.row_dimensions[x[0]].height = max(15, 15 * math.ceil(len(text) / 75))
        x[0] += 1

    def item(no, ref, text, qty, rate, unit, src, rate_inp=False, no_=None):
        r = x[0]
        B.cell(ws, r, 1, no)
        B.cell(ws, r, 2, ref)
        B.cell(ws, r, 3, text).alignment = B.wrap
        if no_ is not None:
            B.cell(ws, r, 4, no_)
        B.cell(ws, r, 8, qty, fmt="#,##0.00")
        B.cell(ws, r, 9, rate, fmt="#,##0.00", inp=rate_inp)
        B.cell(ws, r, 10, unit)
        B.cell(ws, r, 11, f"=H{r}*I{r}", fmt="#,##0")
        ws.cell(r, 12, src).font = B.italic
        x[0] += 1
        return r
    first = x[0]
    title(1, "Supply of the following pipes for the rising mains (DI to IS 8329, HDPE to IS 4984) including F.O.R. "
             "destination, all taxes and insurance, loading and unloading")
    sup = {}
    for s in sizes:
        mat, d = size_key(s)
        if s.endswith(" K9"):
            sup[s] = item("", "UPJN Rate", f"{d} {S['pipe_text']['DI K9']}", f"=E{Q[s]}+{bp}*D{Q[s]}",
                          S["pipe_supply_k9"].get(base(s), 0), "Rmt", "UPJN rate 2025-26 M.193 (K-9) - yellow",
                          rate_inp=True)
            continue
        sup[s] = item("", "UPJN Rate", f"{d} {S['pipe_text'].get(mat, mat)}", f"=E{Q[s]}+{bp}*D{Q[s]}",
                      S["pipe_supply"].get(s, 0),
                      "Rmt", "Elmwood 'DS' I9:I20 (UPJN rate) - yellow", rate_inp=True)
    title(1.1, "Supply of specials for the above pipes")
    for mat in ("HDPE", "DI"):
        rows_ = [sup[s] for s in sizes if size_key(s)[0] == mat]
        if rows_:
            r = item("", "", f"{S['specials'][mat] * 100:g} % of the cost of the {mat} pipes",
                     "=" + "+".join(f"K{y}" for y in rows_), S["specials"][mat], "Rs", "Elmwood 'DS' K21:K22", rate_inp=True)
            ws.cell(r, 9).number_format = "0%"
    item(2, S["excavation_sor"], "Excavation of earth in ordinary soil for pipe line trenches including lift up to 1.50 m "
                                 "and lead up to 50 m, refilling, watering, ramming and disposal of surplus earth",
         f"=G{tot}", "=" + lookup(S["excavation_sor"]), "Cum", f"SOR {S['excavation_sor']}")
    title(3, "Carting (up to 8 km) of the following pipes and specials to the site, lowering into trenches, laying true "
             "to alignment and gradient and testing")
    for s in sizes:
        mat, d = size_key(s)
        if mat == "HDPE":
            item("", "AOR", f"{d} {S['pipe_text']['HDPE']}", f"=E{Q[s]}+{bp}*D{Q[s]}", S["hdpe_carting"].get(s, 0),
                 "Rmt", "Elmwood 'DS' I48:I50 (AOR) - yellow", rate_inp=True)
        else:
            code = S["di_laying_sor"].get(base(s))
            item("", code, f"{d} {S['pipe_text']['DI K9' if s.endswith(' K9') else 'DI']}", f"=E{Q[s]}+{bp}*D{Q[s]}",
                 "=" + lookup(code) if code else 0, "Rmt", f"SOR {code}")
    vop = S["valve_of_pipe"]
    dn = {}
    for s in sizes:
        d = vop.get(base(s))
        if d:
            dn[d] = dn.get(d, []) + [Q[s]]
    title(4, "Supply, carting and fixing of DI sluice valves (IS 780, PN 10) at the outlet of each tube well, with fittings")
    for d in sorted(dn):
        n = "=" + "+".join(f"D{y}" for y in dn[d])
        rr = R.get(str(d))
        item("", "Quotation", f"{d} mm - supply", n, f"={sv}!C{rr}" if rr else 0, "Nos", f"{sv} C{rr}")
        item("", "SOR", f"{d} mm - carting and fixing", n, f"={sv}!E{rr}" if rr else 0, "Nos", f"{sv} E{rr}")
    title(5, "Supply and fixing of DI DF non return valves (IS 5312 Part 1) at the outlet of each tube well "
             "(CPHEEO 6.16.10: an NRV against the return flow on a pump stop)")
    for d in sorted(dn):
        rr = R.get(str(d))
        item("", "UPJN Rate", f"{d} mm - supply", "=" + "+".join(f"D{y}" for y in dn[d]), S["nrv_rate"].get(str(d), 0),
             "Nos", "UPJN rate 2025-26 M209 (DI DF NRV) - yellow", rate_inp=True)
        item("", "SOR", f"{d} mm - carting and fixing", "=" + "+".join(f"D{y}" for y in dn[d]),
             f"={sv}!E{rr}" if rr else 0, "Nos", f"{sv} E{rr} (as a sluice valve of the size)")
    item(6, "Quotation", "Supply, installation and testing of single / double ball type air valves 50 mm with fittings "
                         "(one a km of each main, at its high points)", f"=F{tot}", f"={sv}!C{R['air']}+{sv}!E{R['air']}",
         "Nos", f"{sv} C{R['air']} + E{R['air']}")
    item(7, "Quotation", "Scour valve 80 mm at the low point of each main, supply and fixing", f"=D{tot}",
         f"={sv}!C{R['80']}+{sv}!E{R['80']}", "Nos", f"{sv} C{R['80']} + E{R['80']}")
    ch = S["chambers"]["masonry"]
    item(7.1, "AOR", "Sluice valve chamber (masonry type) for the sluice valve of each main (Riverside water DPR p209)",
         f"=D{tot}", f"={ch}", "Nos", ch)
    th = S["thrust"]
    dis = [s for s in sizes if size_key(s)[0] == "DI" and base(s) in th["sheets"]]
    if dis:
        title(8, f"RCC thrust blocks (1:1.5:3) for the DI mains including reinforcement, centering and shuttering - one "
                 f"per {th['spacing_m']} m")
        for s in dis:
            r = x[0]
            item("", th["rcc_sor"], f"{size_key(s)[1]} mm", f"=D{r}*E{r}", "=" + lookup(th["rcc_sor"]), "Cum",
                 f"SOR {th['rcc_sor']}; volume {th['sheets'][base(s)]} D46", no_=f"=ROUNDUP(E{Q[s]}/{th['spacing_m']},0)")
            ws.cell(r, 5, f"={q(th['sheets'][base(s)])}!D46").border = B.box
            r = x[0]
            item("", th["steel_sor"], f"{size_key(s)[1]} mm - MS reinforcement", f"=D{r}*E{r}",
                 "=" + lookup(th["steel_sor"]), "Kg", f"SOR {th['steel_sor']}; steel {th['sheets'][base(s)]} D47",
                 no_=f"=ROUNDUP(E{Q[s]}/{th['spacing_m']},0)")
            ws.cell(r, 5, f"={q(th['sheets'][base(s)])}!D47").border = B.box
    title(9, "Dismantling of the following road surfaces for laying the rising mains including sorting, stacking and "
             "disposal up to 50 m")
    rr = {}
    for j, k in enumerate(ROADS[:4]):
        rr[k] = item("", "AOR", k, f"={B.col(8 + j)}{tot}", f"={S['road_rates'][k][0]}", "Sqm", S["road_rates"][k][0])
    title(10, "Reinstatement of the following road surfaces with old and new materials")
    for k in ROADS[:4]:
        item("", "AOR", k, f"=H{rr[k]}", f"={S['road_rates'][k][1]}", "Sqm", S["road_rates"][k][1])
    r = x[0]
    B.cell(ws, r, 3, "Total", bold=True)
    B.cell(ws, r, 11, f"=SUM(K{first}:K{r - 1})", fmt="#,##0", bold=True)
    B.cell(ws, r + 1, 3, "Say (in lakh)", bold=True)
    B.cell(ws, r + 1, 11, f"=ROUND(K{r}/100000,2)", fmt="#,##0.00", bold=True)
    B.sign(ws, r + 4, 9)
    B.RM = {"lakh": f"RM!$K${r + 1}", "km": f'ROUND(RM!$E${tot}/1000,2)&" Km, {len(tws)} mains"'}
