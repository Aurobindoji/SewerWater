"""The distribution system of the water DPR: pipes and roads, the DS estimate and summary, house connections, the
rate sheet, the unit estimates of the template and the schedule of rates (restructure stage 3, 15-Nov-2026: out of
dpr.py)."""
import math
from .base import HC_SHIFT, HC_TOTAL, ROADS, SHEET_REF, SOR_LOOKUP, SOR_RNG, TEMPLATE, TEMPLATE_NAMES, VALVES, _copy_cell, q, size_key


# ------------------------------------------------------------------------------------------------------------ RC, Summary DS
def rc(B):
    """Pipe lengths of the design by OZ and size, excavation and road cutting (Elmwood 'RC')."""
    PR, S, info = B.PR, B.S, B.info
    tr = S["trench"]
    ws = B.sheet("RC", "PIPE LENGTHS (DESIGN), EXCAVATION AND ROAD CUTTING OF EACH OPERATION ZONE", 15)
    widths = [6, 12, 10, 12, 13] + [11] * 10
    for c, w in enumerate(widths, 1):
        ws.column_dimensions[B.col(c)].width = w
    heads = ["S. No.", "Outer diameter (mm)", "Pipe material", "Total length (m)", "Excavation (cum)"]
    for k in ROADS:
        heads += [f"{k} length (m)", f"{k} cutting (sqm)"]
    r, ref = 5, {}
    for z in info["zones"]:
        ws.cell(r, 1, f"OPERATION ZONE {z['name']}").font = B.bold
        B.header(ws, r + 1, heads)
        ws.row_dimensions[r + 1].height = 45
        x0 = r + 2
        rows = {}
        for i, s in enumerate(info["sizes"]):
            x = x0 + i
            mat, d = size_key(s)
            B.cell(ws, x, 1, i + 1)
            B.cell(ws, x, 2, d)
            B.cell(ws, x, 3, mat)
            B.cell(ws, x, 4, round(info["length"][z["name"]].get(s, 0.0), 1), fmt="#,##0.0")
            B.cell(ws, x, 5, f"=D{x}*(B{x}/1000+{tr['width_add_m']})*(B{x}/1000+{tr['depth_add_m']})", fmt="#,##0.0")
            for j, k in enumerate(ROADS):
                c = 6 + 2 * j
                B.cell(ws, x, c, f"=ROUND(D{x}*{PR['road:' + k]},0)", fmt="#,##0")
                B.cell(ws, x, c + 1, f"=(B{x}/1000+{tr['width_add_m']})*{B.col(c)}{x}", fmt="#,##0.0")
            rows[s] = x
        t = x0 + len(info["sizes"])
        B.cell(ws, t, 1, "Total", bold=True)
        for c in range(4, 6 + 2 * len(ROADS)):
            B.cell(ws, t, c, f"=SUM({B.col(c)}{x0}:{B.col(c)}{t - 1})", fmt="#,##0", bold=True)
        ref[z["name"]] = {"rows": rows, "total": t}
        r = t + 3
    ws.cell(r, 1, f"Lengths: the pipes of the design (each pipe in the OZ of its start junction). Excavation L x "
                  f"(D + {tr['width_add_m']}) x (D + {tr['depth_add_m']}), road cutting (D + {tr['width_add_m']}) x "
                  f"length under the road - Elmwood 'RC'; road shares from sheet Project.").font = B.italic
    B.RC = ref


def summary_ds(B):
    info, S = B.info, B.S
    zs = info["zones"]
    n = len(zs)
    ws = B.sheet("Summary DS", "SUMMARY OF DISTRIBUTION SYSTEM", n + 3)
    tc = B.col(3 + n)                                         # the Total column
    ws.column_dimensions["A"].width, ws.column_dimensions["B"].width = 6, 30
    for c in range(3, 4 + n):
        ws.column_dimensions[B.col(c)].width = 12
    zh = [z["name"] for z in zs]
    ref = {"tc": tc}
    r = 5
    ws.cell(r, 1, "Summary of pipes (m)").font = B.bold
    B.header(ws, r + 1, ["Sr. No.", "Pipe"] + zh + ["Total"])
    ref["pipe"] = {}
    x = r + 2
    for i, s in enumerate(info["sizes"]):
        mat, d = size_key(s)
        B.cell(ws, x, 1, i + 1)
        B.cell(ws, x, 2, f"{d} {S['pipe_text'].get(mat, mat)}")
        for j, z in enumerate(zs):
            B.cell(ws, x, 3 + j, f"=RC!D{B.RC[z['name']]['rows'][s]}", fmt="#,##0")
        B.cell(ws, x, 3 + n, f"=SUM(C{x}:{B.col(2 + n)}{x})", fmt="#,##0", bold=True)
        ref["pipe"][s] = f"'Summary DS'!${tc}${x}"
        x += 1
    B.cell(ws, x, 2, "TOTAL", bold=True)
    for c in range(3, 4 + n):
        B.cell(ws, x, c, f"=SUM({B.col(c)}{r + 2}:{B.col(c)}{x - 1})", fmt="#,##0", bold=True)
    ref["pipe_total"] = f"'Summary DS'!${tc}${x}"
    ref["pipe_first"], ref["pipe_last"] = r + 2, x - 1
    r = x + 2
    ws.cell(r, 1, "Summary of excavation (cum)").font = B.bold
    B.header(ws, r + 1, ["Sr. No.", "Item"] + zh + ["Total"])
    x = r + 2
    B.cell(ws, x, 1, 1)
    B.cell(ws, x, 2, "Excavation")
    for j, z in enumerate(zs):
        B.cell(ws, x, 3 + j, f"=RC!E{B.RC[z['name']]['total']}", fmt="#,##0")
    B.cell(ws, x, 3 + n, f"=SUM(C{x}:{B.col(2 + n)}{x})", fmt="#,##0", bold=True)
    ref["exc"] = f"'Summary DS'!${tc}${x}"
    r = x + 2
    ws.cell(r, 1, "Summary of road cutting (sqm)").font = B.bold
    B.header(ws, r + 1, ["Sr. No.", "Road type"] + zh + ["Total", "Share of length"])
    ref["road"] = {}
    x = r + 2
    for i, k in enumerate(ROADS):
        B.cell(ws, x, 1, i + 1)
        B.cell(ws, x, 2, k)
        for j, z in enumerate(zs):
            B.cell(ws, x, 3 + j, f"=RC!{B.col(7 + 2 * i)}{B.RC[z['name']]['total']}", fmt="#,##0")
        B.cell(ws, x, 3 + n, f"=SUM(C{x}:{B.col(2 + n)}{x})", fmt="#,##0", bold=True)
        B.cell(ws, x, 4 + n, f"={B.PR['road:' + k]}", fmt="0%")
        ref["road"][k] = f"'Summary DS'!${tc}${x}"
        x += 1
    r = x + 1
    ws.cell(r, 1, "Summary of valves and hydrants (nos) - " + S["valves_rule"]).font = B.bold
    B.header(ws, r + 1, ["Sr. No.", "Dia / item"] + zh + ["Total"])
    ref["sv"] = {}
    x = r + 2
    for i, d in enumerate(VALVES):
        B.cell(ws, x, 1, i + 1)
        B.cell(ws, x, 2, f"{d} mm sluice valve")
        for j, z in enumerate(zs):
            B.cell(ws, x, 3 + j, info["valves"][z["name"]].get(d, 0), inp=True)
        B.cell(ws, x, 3 + n, f"=SUM(C{x}:{B.col(2 + n)}{x})", bold=True)
        ref["sv"][d] = f"'Summary DS'!${tc}${x}"
        x += 1
    ref["sv_rows"] = (r + 2, x - 1)
    for key, lab in (("hydrant", "Fire hydrant"), ("scour", "Scour valve (80 mm)"), ("air", "Air valve (50 mm)")):
        B.cell(ws, x, 2, lab)
        for j, z in enumerate(zs):
            B.cell(ws, x, 3 + j, S["valves_per_oz"][key], inp=True)
        B.cell(ws, x, 3 + n, f"=SUM(C{x}:{B.col(2 + n)}{x})", bold=True)
        ref[key] = f"'Summary DS'!${tc}${x}"
        x += 1
    ws.cell(x + 1, 1, "Valves: " + S["valves_rule"] + " (dpr_water.json); hydrant / scour / air valves per OZ as the "
                      "Elmwood 'Summary DS' - yellow, change to the drawings.").font = B.italic
    B.sign(ws, x + 3, 3 + n)
    B.SDS = ref


# ------------------------------------------------------------------------------------------------------------ DS
def ds(B):
    """Estimate & detailed measurement for the distribution system (Elmwood 'DS')."""
    S, SD, info = B.S, B.SDS, B.info
    ws = B.sheet("DS", "ESTIMATE & DETAILED MEASUREMENT FOR DISTRIBUTION SYSTEM", 11)
    B.header(ws, 5, ["Sl No", "SOR Ref.", "Item of work", "No.", "L", "B", "H/D", "Qty", "Rate", "Unit", "Amount",
                     "Rate from"], [6, 10, 60, 8, 10, 6, 6, 16, 12, 7, 15, 44])
    sv = "'SV Rate'"
    x = [6]
    lookup = lambda code: f"IFERROR(VLOOKUP({code},{SOR_RNG},4,0),0)"

    def title(no, text):
        r = x[0]
        B.cell(ws, r, 1, no)
        c = B.cell(ws, r, 3, text, bold=True)
        c.alignment = B.wrap
        ws.row_dimensions[r].height = max(15, 15 * math.ceil(len(text) / 75))
        x[0] += 1

    def item(no, ref, text, qty, rate, unit, src, rate_inp=False, qty_inp=False, no_=None):
        r = x[0]
        B.cell(ws, r, 1, no)
        B.cell(ws, r, 2, ref)
        B.cell(ws, r, 3, text).alignment = B.wrap
        if no_ is not None:
            B.cell(ws, r, 4, no_)
        B.cell(ws, r, 8, qty, fmt="#,##0.00", inp=qty_inp)
        B.cell(ws, r, 9, rate, fmt="#,##0.00", inp=rate_inp)
        B.cell(ws, r, 10, unit)
        B.cell(ws, r, 11, f"=H{r}*I{r}", fmt="#,##0")
        ws.cell(r, 12, src).font = B.italic
        x[0] += 1
        return r

    pipes = info["sizes"]
    title(1, "Supply of following sizes of pipes for the distribution system (DI to IS 8329, HDPE to IS 4984) including "
             "F.O.R. destination, all taxes and insurance, loading and unloading")
    sup = {}
    for s in pipes:
        mat, d = size_key(s)
        sup[s] = item("", "UPJN Rate", f"{d} {S['pipe_text'].get(mat, mat)}", f"={SD['pipe'][s]}",
                      S["pipe_supply"].get(s, 0), "Rmt", "Elmwood 'DS' I9:I20 (UPJN rate) - yellow", rate_inp=True)
    hd = [sup[s] for s in pipes if size_key(s)[0] == "HDPE"]
    di = [sup[s] for s in pipes if size_key(s)[0] == "DI"]
    title(1.2, "Supply of specials conforming to I.S.S. suitable for the above DI & HDPE pipes F.O.R. destination "
               "including all taxes and insurance")
    for mat, rows_ in (("HDPE", hd), ("DI", di)):
        if rows_:
            r = x[0]
            item("", "", f"{S['specials'][mat] * 100:g} % of the cost of the {mat} pipes",
                 "=" + "+".join(f"K{y}" for y in rows_), S["specials"][mat], "", "Elmwood 'DS' K21:K22", rate_inp=True)
            ws.cell(r, 9).number_format = "0%"
            ws.cell(r, 10).value = "Rs"
    item(2, "Quotation", "Supply of under ground sluice valve type fire hydrant (80 mm sluice valve, tail pieces, duck "
                         "foot bend, coupling with cap) complete", f"={SD['hydrant']}", 35000, "Nos",
         "Elmwood 'DS' I25 (quotation)", rate_inp=True)
    title(3, "Supply and carting up to site of work of the following dia DI sluice valves, class I, PN 10, IS 780, "
             "including valve fittings & dismantling joints")
    R = S["valve_rate_row"]
    svr = {}
    for d in reversed(VALVES):
        svr[d] = item("", "Quotation", f"{d} mm", f"={SD['sv'][d]}", f"={sv}!C{R[str(d)]}", "Nos", f"{sv} C{R[str(d)]}")
    item(4, "Quotation", "Scour valve 80 mm", f"={SD['scour']}", f"={sv}!C{R['80']}", "Nos", f"{sv} C{R['80']}")
    item(5, "Quotation", "Supply, installation and testing of single / double ball type air valve 50 mm with fittings",
         f"={SD['air']}", f"={sv}!C{R['air']}", "Nos", f"{sv} C{R['air']}")
    # the PRVs of the design (prv.py, user 30-Oct-2026), by valve size, built from UPJN items (user 31-Oct-2026): the
    # PRV valve itself at a yellow quotation rate, its two isolating sluice valves (UPJN M208 - sheet SV Rate) and its
    # masonry chamber (unit estimate SV M)
    prv = {}
    for p in info.get("prvs") or []:
        d = S["valve_of_pipe"].get(p.get("size"))
        if d:
            prv.setdefault(d, []).append(p)
    if prv:
        title(5.1, "Pressure reducing valves (PRV) on the distribution mains: the PRV, an isolating sluice valve on "
                   "each side and a chamber")
        for d in sorted(prv):
            n, rr = len(prv[d]), R.get(str(d))
            item("", "Quotation", f"{d} mm PRV (pilot operated, DI body, PN 10) with Y-strainer and pressure gauges, "
                                  f"supply, installation and testing - " +
                 ", ".join(f"{p['name']} on {p['pipe']} (setting {p['setting_m']:g} m)" for p in prv[d]),
                 n, S["prv_rate"].get(str(d), 0), "Nos",
                 "INDICATIVE rate (dpr_water.json prv_rate) - yellow, replace by a quotation", rate_inp=True)
            item("", "Quotation", f"{d} mm DI DF sluice valves to isolate the PRVs (two each) - supply", 2 * n,
                 f"={sv}!C{rr}" if rr else 0, "Nos", f"{sv} C{rr} (UPJN rate 2025-26 M208)")
            item("", "SOR", f"{d} mm sluice valves to isolate the PRVs - carting and fixing", 2 * n,
                 f"={sv}!E{rr}" if rr else 0, "Nos", f"{sv} E{rr}")
            item("", "Unit Est.", f"Chamber of a {d} mm PRV with its isolating valves (masonry type)", n,
                 f"={S['chambers']['masonry']}", "Nos", S["chambers"]["masonry"])
    exc = item(6, S["excavation_sor"], "Excavation of earth in ordinary soil for pipe line trenches including lift up to "
                                       "1.50 m and lead up to 50 m, refilling, watering, ramming and disposal of surplus "
                                       "earth", f"={SD['exc']}", "=" + lookup(S["excavation_sor"]), "Cum",
               f"SOR {S['excavation_sor']}")
    title(7, "Carting (up to 8 km) of the following pipes and specials to the site, lowering into trenches, laying true "
             "to alignment and gradient and testing")
    for s in pipes:
        mat, d = size_key(s)
        if mat == "HDPE":
            item("", "AOR", f"{d} {S['pipe_text']['HDPE']}", f"=H{sup[s]}", S["hdpe_carting"].get(s, 0), "Rmt",
                 "Elmwood 'DS' I48:I50 (AOR) - yellow", rate_inp=True)
        else:
            code = S["di_laying_sor"].get(s)
            item("", code, f"{d} {S['pipe_text']['DI']}", f"=H{sup[s]}", "=" + lookup(code) if code else 0, "Rmt",
                 f"SOR {code}")
    title(8, "Carting of D/F sluice valves to the site, lowering into trenches and fixing in position with jointing "
             "material and testing")
    for d in reversed(VALVES):
        item("", "SOR", f"{d} mm", f"=H{svr[d]}", f"={sv}!E{R[str(d)]}", "Nos", f"{sv} E{R[str(d)]}")
    item(9, "SOR", "Carting and fixing of scour valves 80 mm", f"={SD['scour']}", f"={sv}!E{R['80']}", "Nos",
         f"{sv} E{R['80']}")
    item(10, "SOR", "Carting and fixing of 50 mm air valves including boring and threading the main", f"={SD['air']}",
         f"={sv}!E{R['air']}", "Nos", f"{sv} E{R['air']}")
    item(11, "SOR", "Carting and fixing of 80 mm flanged fire hydrants with flanged tee", f"={SD['hydrant']}",
         f"={sv}!E{R['hydrant']}", "Nos", f"{sv} E{R['hydrant']}")
    title(12, "Crossings along the pipe line including supply of materials, labour, T&P complete")
    for key, lab in (("culvert", "Crossing of culvert (3.5 m wide)"), ("drain", "Crossing of nala / drain (1.5 - 3.0 m)")):
        rr, n0 = S["crossings"][key]
        item("", "AOR", lab, n0, f"={rr}", "Nos", f"{rr} - the number of crossings: fill in", qty_inp=True)
    title(13, "Supply of MS pipe (IS 3589) with anti-corrosive PU coating, installation by HDD (trenchless road crossing)")
    for d, row_ in ((200, 4), (250, 5), (300, 6), (350, 7), (400, 8), (450, 9), (600, 11)):
        item("", "AOR", f"{d} mm dia MS pipe", 0, f"=HDD!G{row_}", "Rmt", f"HDD G{row_} - lengths: fill in", qty_inp=True)
    title(14, "Dismantling of the following road surfaces for laying of pipe line including sorting, stacking and "
              "disposal up to 50 m")
    rr = {}
    for k in ROADS[:4]:
        rr[k] = item("", "AOR", k, f"={SD['road'][k]}", f"={S['road_rates'][k][0]}", "Sqm", S["road_rates"][k][0])
    title(15, "Reinstatement of the following road surfaces with old and new materials")
    for k in ROADS[:4]:
        item("", "AOR", k, f"=H{rr[k]}", f"={S['road_rates'][k][1]}", "Sqm", S["road_rates"][k][1])
    hc = item(16, "Estimate", "Provision of house connections including supply of all materials, labour, T&P and "
                              "road restoration (estimate attached, sheet NEW HC)", f"={B.PR['hc']}", 0, "Nos",
              "sheet NEW HC")
    ws.cell(hc, 9).value = f"=IFERROR({HC_TOTAL}*100000/H{hc},0)"
    ws.cell(hc, 11).value = f"={HC_TOTAL}*100000"
    # the existing connections shifted to the new pipes (Riverside water DPR p295, user decision 6-Nov-2026)
    hs = item(16.1, "Estimate", "Shifting of the existing house connections to the new pipe line including road "
                                "restoration (estimate attached, sheet Shif. HC)", f"={B.PR['hc_shift']}", 0, "Nos",
              "sheet Shif. HC")
    ws.cell(hs, 9).value = f"=IFERROR({HC_SHIFT}*100000/H{hs},0)"
    ws.cell(hs, 11).value = f"={HC_SHIFT}*100000"
    big = [SD["sv"][d] for d in VALVES if d > 125]
    small = [SD["sv"][d] for d in VALVES if d <= 125]
    ch = S["chambers"]
    item(17, "Unit Est.", "Sluice valve chamber (masonry type) - dia above 125 mm", "=" + "+".join(big),
         f"={ch['masonry']}", "Nos", ch["masonry"])
    item(18, "Unit Est.", "Sluice valve chamber (surface box type) - dia up to 125 mm", "=" + "+".join(small),
         f"={ch['surface_box']}", "Nos", ch["surface_box"])
    item(19, "Unit Est.", "Fire hydrant chamber", f"={SD['hydrant']}", f"={ch['hydrant']}", "Nos", ch["hydrant"])
    item(20, "Unit Est.", "Air valve chamber", f"={SD['air']}", f"={ch['air']}", "Nos", ch["air"])
    item(21, "Unit Est.", "Scour valve chamber (surface box rate)", f"={SD['scour']}", f"={ch['surface_box']}", "Nos",
         ch["surface_box"])
    th = S["thrust"]
    dis = [s for s in pipes if size_key(s)[0] == "DI" and s in th["sheets"]]
    if dis:
        title(22, "Design and construct RCC thrust blocks (1:1.5:3) for the pipe line including reinforcement, "
                  f"centering and shuttering - one per {th['spacing_m']} m of DI pipe")
        for s in dis:
            r = x[0]
            item("", th["rcc_sor"], f"{size_key(s)[1]} mm", f"=D{r}*E{r}", "=" + lookup(th["rcc_sor"]), "Cum",
                 f"SOR {th['rcc_sor']}; volume {th['sheets'][s]} D46", no_=f"=ROUNDUP({SD['pipe'][s]}/{th['spacing_m']},0)")
            ws.cell(r, 5, f"={q(th['sheets'][s])}!D46").border = B.box
        title(22.1, "Supply of MS reinforcement wrought to required shape, bending, fixing and binding")
        for s in dis:
            r = x[0]
            item("", th["steel_sor"], f"{size_key(s)[1]} mm", f"=D{r}*E{r}", "=" + lookup(th["steel_sor"]), "Kg",
                 f"SOR {th['steel_sor']}; steel {th['sheets'][s]} D47", no_=f"=ROUNDUP({SD['pipe'][s]}/{th['spacing_m']},0)")
            ws.cell(r, 5, f"={q(th['sheets'][s])}!D47").border = B.box
    r = x[0]
    B.cell(ws, r, 3, "Total", bold=True)
    B.cell(ws, r, 11, f"=SUM(K6:K{r - 1})", fmt="#,##0", bold=True)
    B.cell(ws, r + 1, 3, "Say (in lakh)", bold=True)
    B.cell(ws, r + 1, 11, f"=ROUND(K{r}/100000,2)", fmt="#,##0.00", bold=True)
    ws.freeze_panes = "D6"
    B.sign(ws, r + 4, 9)
    B.DS = {"lakh": f"DS!$K${r + 1}", "exc_rate": f"DS!$I${exc}",
            "road": {k: (f"DS!$I${rr[k]}", f"DS!$I${rr[k] + len(rr) + 1}") for k in rr}}


# ------------------------------------------------------------------------------------------------------------ NEW HC
def new_hc(B, shift=False):
    """House connections (Elmwood 'NEW HC'): connections shared by the pipe length of each band of main sizes,
    labour + material (more for a bigger main) + excavation per connection, road dismantling and reinstatement.
    shift: the existing connections shifted to the new pipes (Elmwood 'Shif. HC' = Riverside water DPR p295-300) - its
    own material and pit, the number of sheet Project."""
    S, SD, PR = B.S, B.SDS, B.PR
    H = dict(S["house_connection"], **(S["house_connection_shift"] if shift else {}))
    n_hc = PR["hc_shift" if shift else "hc"]
    ws = B.sheet("Shif. HC" if shift else "NEW HC",
                 f"ESTIMATE FOR {'SHIFTING OF' if shift else 'NEW'} HOUSE CONNECTION", 8)
    for c, w in zip("ABCDEFGH", (6, 52, 12, 12, 12, 14, 14, 12)):
        ws.column_dimensions[c].width = w
    # analysis of rate per connection (Elmwood rows 129-165) first: its cells are used above it
    a = 70
    ws.cell(a, 1, "Analysis of rate for " + ("shifting of an existing house connection to the new pipe line" if shift else
                                             "a water supply house connection on a new pipe line") +
            " (each connection)").font = B.bold
    B.header(ws, a + 1, ["S.N.", "Sub-head", "Unit", "Quantity", "Rate", "Amount"])
    x = a + 2
    l0 = x
    for lab, unit, qty, rate in H["labour"]:
        B.cell(ws, x, 2, lab)
        B.cell(ws, x, 3, unit)
        B.cell(ws, x, 4, qty if qty is not None else "L.S.")
        B.cell(ws, x, 5, rate, inp=True)
        B.cell(ws, x, 6, f"=D{x}*E{x}" if qty is not None else f"=E{x}", fmt="#,##0.00")
        x += 1
    B.cell(ws, x, 2, "Total")
    B.cell(ws, x, 6, f"=SUM(F{l0}:F{x - 1})", fmt="#,##0.00")
    B.cell(ws, x + 1, 2, "Add for contractor's profit")
    B.cell(ws, x + 1, 5, H["profit"], fmt="0%", inp=True)
    B.cell(ws, x + 1, 6, f"=F{x}*E{x + 1}", fmt="#,##0.00")
    B.cell(ws, x + 2, 2, "Labour charges for cutting, threading & fitting of GI pipe and specials")
    B.cell(ws, x + 2, 5, H["gi_labour"], inp=True)
    B.cell(ws, x + 2, 6, f"=E{x + 2}", fmt="#,##0.00")
    B.cell(ws, x + 3, 2, "Labour per connection", bold=True)
    B.cell(ws, x + 3, 6, f"=ROUND(F{x}+F{x + 1},0)+F{x + 2}", fmt="#,##0.00", bold=True)
    lab_cell = f"F{x + 3}"
    x += 5
    B.cell(ws, x, 2, "Excavation and back filling of pit and trenches (" +
           ("2.0 x 0.30 x 0.75 m" if shift else "1 x 4 x 0.30 x 0.75 m") + ")")
    B.cell(ws, x, 3, "cum")
    B.cell(ws, x, 4, H["pit_cum"], inp=True)
    B.cell(ws, x, 5, f"={B.DS['exc_rate']}", fmt="#,##0.00")
    B.cell(ws, x, 6, f"=ROUND(D{x}*E{x},0)", fmt="#,##0.00")
    exc_cell = f"F{x}"
    x += 2
    B.cell(ws, x, 2, "Material including C.P. on a 90 mm to 110 mm main", bold=True)
    x += 1
    m0 = x
    for lab, unit, qty, rate in H["material"]:
        B.cell(ws, x, 2, lab)
        B.cell(ws, x, 3, unit)
        B.cell(ws, x, 4, qty, inp=True)
        B.cell(ws, x, 5, rate, inp=True)
        B.cell(ws, x, 6, f"=D{x}*E{x}", fmt="#,##0.00")
        x += 1
    B.cell(ws, x, 2, "Total material (90 - 110 mm main)", bold=True)
    B.cell(ws, x, 6, f"=SUM(F{m0}:F{x - 1})", fmt="#,##0.00", bold=True)
    mat_cell = f"F{x}"
    B.sign(ws, x + 3, 5)
    # number of connections by band (Elmwood rows 89-100)
    r = 40
    ws.cell(r, 1, f"Calculation for number of {'shifted' if shift else 'new'} house connections (shared by the length "
                  "of each band of main sizes)").font = B.bold
    B.header(ws, r + 1, ["S.N.", "Dia of main", "Pipe length (m)", "Share", "Connections", "Material factor",
                         "Material per connection", ""])
    bands = H["bands"]
    b0 = r + 2
    for i, (lab, sizes, f) in enumerate(bands):
        y = b0 + i
        B.cell(ws, y, 1, i + 1)
        B.cell(ws, y, 2, f"For {lab} dia")
        ls = [SD["pipe"][s] for s in sizes if s in SD["pipe"]]
        B.cell(ws, y, 3, "=" + "+".join(ls) if ls else 0, fmt="#,##0")
        B.cell(ws, y, 4, f"=IFERROR(C{y}/$C${b0 + len(bands)},0)", fmt="0.0%")
        if i < len(bands) - 1:
            B.cell(ws, y, 5, f"=ROUND({n_hc}*D{y},0)", fmt="#,##0")
        else:                                              # the last band takes what rounding left
            B.cell(ws, y, 5, f"={n_hc}-SUM(E{b0}:E{y - 1})", fmt="#,##0")
        B.cell(ws, y, 6, f, fmt="0.00", inp=True)
        B.cell(ws, y, 7, f"={mat_cell}*F{y}", fmt="#,##0.00")
    tb = b0 + len(bands)
    B.cell(ws, tb, 2, "Total", bold=True)
    B.cell(ws, tb, 3, f"=SUM(C{b0}:C{tb - 1})", fmt="#,##0", bold=True)
    B.cell(ws, tb, 5, f"=SUM(E{b0}:E{tb - 1})", fmt="#,##0", bold=True)
    # unit estimate (Elmwood rows 21-51) and roads (rows 61-78)
    r = 11
    ws.cell(r, 1, f"Unit estimate of {'shifting of' if shift else 'new'} house connections").font = B.bold
    B.header(ws, r + 1, ["S.N.", "Description", "Qty.", "Unit", "Rate", "Amount (Rs)"])
    y = r + 2
    subs = []
    for i, (lab, _, _) in enumerate(bands):
        n_ = f"E{b0 + i}"
        B.cell(ws, y, 1, i + 1)
        B.cell(ws, y, 2, f"Connection on a pipe line of {lab} dia: labour + material + excavation")
        B.cell(ws, y, 3, f"={n_}", fmt="#,##0")
        B.cell(ws, y, 4, "Nos.")
        B.cell(ws, y, 5, f"={lab_cell}+G{b0 + i}+{exc_cell}", fmt="#,##0.00")
        B.cell(ws, y, 6, f"=C{y}*E{y}", fmt="#,##0")
        subs.append(y)
        y += 1
    B.cell(ws, y, 2, "Total house connections", bold=True)
    B.cell(ws, y, 3, f"=SUM(C{subs[0]}:C{subs[-1]})", fmt="#,##0", bold=True)
    B.cell(ws, y, 6, f"=SUM(F{subs[0]}:F{subs[-1]})", fmt="#,##0", bold=True)
    conn_tot = y
    y += 2
    ws.cell(y, 1, "Dismantling & permanent reinstatement of roads for the house connections").font = B.bold
    B.header(ws, y + 1, ["S.N.", "Description", "Per connection (sqm)", "Connections", "Qty (sqm)", "Rate", "Amount"])
    y += 2
    road0 = y
    for i, k in enumerate(ROADS[:4]):
        for j, (what, cell) in enumerate((("Dismantling", B.DS["road"][k][0]), ("Reinstatement", B.DS["road"][k][1]))):
            B.cell(ws, y, 2, f"{what} of {k}")
            B.cell(ws, y, 3, H["road_sqm"], inp=True)
            B.cell(ws, y, 4, f"=ROUND({n_hc}*{PR['road:' + k]},0)", fmt="#,##0")
            B.cell(ws, y, 5, f"=C{y}*D{y}", fmt="#,##0.0")
            B.cell(ws, y, 6, f"={cell}", fmt="#,##0.00")
            B.cell(ws, y, 7, f"=E{y}*F{y}", fmt="#,##0")
            y += 1
    B.cell(ws, y, 2, "Total roads", bold=True)
    B.cell(ws, y, 7, f"=SUM(G{road0}:G{y - 1})", fmt="#,##0", bold=True)
    road_tot = y
    # summary at the top (Elmwood rows 7-12): rows 5-8 (HC_TOTAL = F8)
    B.header(ws, 5, ["S.N.", "Components", "Unit", "Quantity", "", "Amount (Rs. lakh)"])
    for x, (no, lab, unit, qty, amt) in enumerate(((1, "House connections", "Nos", f"=C{conn_tot}",
                                                    f"=ROUND(F{conn_tot}/100000,4)"),
                                                   (2, "Dismantling & reinstatement of roads", "Sqm",
                                                    f"=SUM(E{road0}:E{road_tot - 1})/2", f"=ROUND(G{road_tot}/100000,4)"),
                                                   ("", "Total", "", "", "=F6+F7")), 6):
        for c, v in enumerate((no, lab, unit, qty, None, amt), 1):
            B.cell(ws, x, c, v, fmt="#,##0.00" if c == 6 else ("#,##0" if c == 4 else None), bold=x == 8)
    return ws


def rate_sheet(B):
    """The U.P. Jal Nigam standard cost of OHT (25 m staging) and UGR per litre (dpr_water.json oht_ugr_rates),
    escalated to the SOR year; B.RATE(cell, "B" OHT / "C" UGR) -> the formula of the rate of a tank whose capacity (KL)
    is in that cell."""
    R = B.S["oht_ugr_rates"]
    ws = B.sheet("OHT UGR rates", f"STANDARD COST OF OHT (25 M STAGING) AND UGR PER LITRE - U.P. JAL NIGAM, FY {R['year']}",
                 4)
    B.header(ws, 5, ["Capacity (KL)", f"OHT Rs/litre ({R['year']})", f"UGR Rs/litre ({R['year']})", ""],
             [14, 18, 18, 70])
    first = 6
    for i, (c, o, u) in enumerate(zip(R["capacity_kl"], R["oht_per_l"], R["ugr_per_l"])):
        B.cell(ws, first + i, 1, c)
        B.cell(ws, first + i, 2, o, fmt="0.00", inp=True)
        B.cell(ws, first + i, 3, u, fmt="0.00", inp=True)
    last = first + len(R["capacity_kl"]) - 1
    e = last + 2
    ws.cell(e, 1, "Escalation per year")
    B.cell(ws, e, 2, R["escalation"], fmt="0%", inp=True)
    ws.cell(e + 1, 1, f"Years after {R['year']}")
    B.cell(ws, e + 1, 2, R["years"], inp=True)
    ws.cell(e + 1, 4, "0: the FY 2022-23 rate as it is, as the Riverside water DPR (user decision 6-Nov-2026; before: "
                      "3 years to 2025-26)")
    ws.cell(e + 2, 1, "Factor")
    B.cell(ws, e + 2, 2, f"=(1+B{e})^B{e + 1}", fmt="0.0000", bold=True)
    for k, t in enumerate(("U.P. Jal Nigam: 'Standard Cost of Over Head Tank (OHT) of 25 M Staging' and 'of Under Ground "
                           "Water Reservoir (UGR)' for FY 2022-23 - average of UPJN order 1344/2042-0026/13 dt 23.11.2013, "
                           "Meerut Circle order 1710/615/13 dt 03.08.2019 and SWSM ('Say' rows); UGR = 3/4 of OHT.",
                           "GST and labour cess extra (Form J). A capacity between two of the table: linear between "
                           "them; below 200 KL / above 3000 KL: the end rate.")):
        ws.cell(e + 4 + k, 1, t).font = B.italic
    sh = "'OHT UGR rates'!"
    A = f"{sh}$A${first}:$A${last}"

    def rate(cell, col):
        V = f"{sh}${col}${first}:${col}${last}"
        i = f"MATCH({cell},{A},1)"
        lin = (f"INDEX({V},{i})+({cell}-INDEX({A},{i}))*(INDEX({V},{i}+1)-INDEX({V},{i}))"
               f"/(INDEX({A},{i}+1)-INDEX({A},{i}))")
        return (f"IF({cell}<={sh}$A${first},{sh}${col}${first},IF({cell}>={sh}$A${last},{sh}${col}${last},{lin}))"
                f"*{sh}$B${e + 2}")
    B.RATE = rate


def unit_estimates(B):
    """The unit estimates of the Elmwood estimate (dpr_template.xlsx), their SOR look-ups on this workbook's sor."""
    import openpyxl
    tpl = openpyxl.load_workbook(TEMPLATE)
    names = {n: TEMPLATE_NAMES.get(n, n) for n in tpl.sheetnames}

    def sub(m):
        s = (m.group(1) or m.group(2)).replace("''", "'")
        return q(names[s]) + "!" if s in names else m.group(0)
    for src in tpl.worksheets:
        ws = B.wb.create_sheet(names[src.title])
        for row in src.iter_rows():
            for c in row:
                v = c.value
                if isinstance(v, str) and v.startswith("="):
                    v = SHEET_REF.sub(sub, v)
                    v = SOR_LOOKUP.sub(lambda m: f"IFERROR(VLOOKUP({m.group(1)},{SOR_RNG},4,0),0)", v)
                if v is None and not c.has_style:
                    continue
                _copy_cell(c, ws.cell(c.row, c.column, v))
        for m in src.merged_cells.ranges:
            ws.merge_cells(str(m))
        for k, dim in src.column_dimensions.items():
            if dim.width:
                ws.column_dimensions[k].width = dim.width
            ws.column_dimensions[k].hidden = dim.hidden
        for k, dim in src.row_dimensions.items():
            if dim.height:
                ws.row_dimensions[k].height = dim.height
        for col in {c.column_letter for row in ws.iter_rows() for c in row
                    if isinstance(c.value, str) and c.value.startswith("=SUM(")}:     # a total: wide enough, not ###
            d = ws.column_dimensions[col]
            d.width = max(d.width or 8.43, 16.0)              # (their Bookman Old Style is wide)
        if ws.title.startswith("Thrust") and ws.title != "Thrust (2)":     # another project's name in the Elmwood copies
            ws["A1"], ws["A2"], ws["A3"], ws["A4"] = "ESTIMATE FOR", B.title, f'=""&{B.PR["under"]}', None
        elif ws.title in ("HT", "LT", "booster room"):
            ws["A1"], ws["A2"], ws["A3"] = B.title, f'="DISTRICT - "&{B.PR["district"]}', f'=""&{B.PR["under"]}'
    return list(names.values())


def sor_sheet(B):
    from water_app.data import rates
    sor = rates.sor()                          # with the user's imported rates (15-Nov-2026)
    ws = B.wb.create_sheet("sor")
    ws.cell(1, 1, sor.get("title") or "SCHEDULE OF RATES").font = B.bold
    B.header(ws, 3, ["Item No.", "Description of item", "Unit", "Rate"], [10, 90, 10, 12])
    for i, (code, desc, unit, rate) in enumerate(sor["items"]):
        x = 4 + i
        ws.cell(x, 1, int(code) if isinstance(code, str) and code.isdigit() else (code or None))
        ws.cell(x, 2, desc)
        ws.cell(x, 3, unit or None)
        ws.cell(x, 4, rate)
    ws.freeze_panes = "A4"
