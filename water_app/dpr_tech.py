"""The technical statement of the water DPR beyond the OZ sums - in the format of the Riverside water DPR (U.P. Jal
Nigam, AMRUT 2.0, 2026; user decision 6-Nov-2026), each OZ a block of its own, from the design (B.info["tech"],
ui_api._tech) and the sheets before (T1 / TW / Storage / T3 (k) / EM TS):

    wards(B)        Wards        ward-wise population and its growth by the ward's character (p71-82), the zone-wise
                                 population by ward (p83-87)
    dmas(B)         DMA Pop      DMA-wise population and households (p88-91)
    requirement(B)  Req          requirement of water & tube wells (and CWR pumps) of each OZ, the three years (p92-113)
    mass_balance(B) MB OHT       mass balancing of each OHT, hour by hour in m3 (p114-128)
    static_head(B)  Static Head  static head of each tube well's rising main (and the CWR pumps') (p130-196)
    pipe_table(B)   Pipe Table   distribution design and pipe table of each OZ (p199-201)

and, as the example technical.xlsx (Elmwood) 'Tech3'-'Tech7' (user decision 9-Nov-2026):

    dma_demand(B)     DMA Demand    DMA (and ward in it) wise population, demand and households
    zone_summary(B)   Zone Summary  the same of each OZ
    oht_details(B)    OHT Details   existing / required OHT and CWR of each OZ
    dma_household(B)  DMA HH        DMA-wise population and households
    zone_household(B) Zone HH       zone-wise population and households

write(B) makes them all (a sheet with nothing to show is left out). B = dpr.Book after the E&M sheets.
"""
import re

from .dpr import q
from .ui_api import FAR_OPEN, WARD_DENS

DPR = "Riverside water DPR (U.P. Jal Nigam 2026)"
YEARS = (("init", "base_year"), ("mid", "mid_year"), ("ult", "design_year"))


def _heads(B, ws, r, first, extra=()):
    """A block's header row: first column titles, the three years, extra titles."""
    B.header(ws, r, list(first) + [f'=""&{B.PR[k]}' for _, k in YEARS] + list(extra))


def ward_table(B, ws, r, grow=None):
    """The wards of the page's table (user decision 7-Nov-2026; Riverside water DPR p71-75 'Wardwise population and
    area'): no., name, population of the year given and its households, area, the 2011 census, density, the share
    covered by the project, the population in it and in the base / middle / design years - by the factors of the
    ward's character (grow: {character: row of the growth table A}, its columns D-F; DPR p76) or else by the adopted
    projection (from that year) -, the character, whether a boundary with its number is on the map. Returns the next
    free row."""
    wt, PR, grow = B.info["ward_table"], B.PR, grow or {}
    f = B.info.get("projection") or {}
    rf = f.get("ratio_from") if f.get("from_year") == wt["year"] else None
    yr = wt["year"] or ""
    ws.cell(r, 2, "WARDWISE POPULATION AND AREA (the wards of the project)").font = B.bold
    B.header(ws, r + 1, ["Sl.No", "Name of ward", "Ward No.", f"Population {yr}", "House hold", "Area (ha)",
                         "Census population 2011", f"Density {yr} (per ha)", "% of ward covered",
                         f"Population in the project {yr}"] +
             [f'=""&{PR[k]}' for _, k in YEARS] + ["Character of ward", "Boundary on the map",
                                                   "Density in the design year (per ha)"] +
             (["Above the saturation density (CPHEEO)?"] if wt.get("sat") else []))
    ws.row_dimensions[r + 1].height = 45
    x0 = r + 2
    xs = x0 + len(wt["rows"])                        # the total row: the saturation density in P (8-Nov-2026)
    for i, w in enumerate(wt["rows"]):
        x = x0 + i
        vals = [i + 1, w["name"], w["no"], w["pop"], w["hh"], w["area"], w["census"],
                f"=IFERROR(D{x}/F{x},\"\")", w["cov"], f"=D{x}*I{x}"]
        for c, v in enumerate(vals, 1):
            B.cell(ws, x, c, v, fmt="0%" if c == 9 else "#,##0.00" if c == 8 else "#,##0" if c >= 4 else None,
                   inp=c in (4, 5, 6, 7, 9))
        g = grow.get(w.get("char") or "")
        for j, t in enumerate(("init", "mid", "ult")):
            v = (f"=ROUND(J{x}*${B.col(4 + j)}${g},0)" if g else f"=ROUND(J{x}*{rf[t]:.6f},0)" if rf else None)
            B.cell(ws, x, 11 + j, v, fmt="#,##0")
        B.cell(ws, x, 14, w.get("char") or "-")
        B.cell(ws, x, 15, "yes" if w.get("on_map") else "no - on the junctions in no ward")
        B.cell(ws, x, 16, f'=IFERROR(H{x}*M{x}/J{x},"")', fmt="#,##0")       # the density x the design factor
        if wt.get("sat"):
            B.cell(ws, x, 17, f'=IF(P{x}="","",IF(P{x}>$P${xs},"above saturation","ok"))')
    x1 = x0 + len(wt["rows"]) - 1
    B.cell(ws, x1 + 1, 2, "Total", bold=True)
    for c in (4, 5, 6, 7, 10, 11, 12, 13):
        B.cell(ws, x1 + 1, c, f"=SUM({B.col(c)}{x0}:{B.col(c)}{x1})", fmt="#,##0", bold=True)
    if wt.get("sat"):
        B.cell(ws, xs, 15, "Saturation density (per ha)", bold=True)
        B.cell(ws, xs, 16, wt["sat"], fmt="#,##0", inp=True)
    ws.cell(x1 + 2, 2, "The table of the page (yellow: as given). The base / middle / design years: the population in the "
                       f"project of {yr} x the factors of the ward's character (A below, {DPR} p76), a ward without "
                       f"a character x the adopted projection's ratio from {yr} (sheet T)" +
                       ("" if rf else " - no projection from this year: not computed") + "; a ward with a boundary of "
                       "its number on the map has its population on that boundary's junctions, the others on the "
                       "junctions in no ward. The density in the design year: the density x the design factor "
                       "(M / J); the saturation density (yellow) - the developed core's present density, a little "
                       "above - is the upper limit of a ward's future density (CPHEEO Manual on Water Supply 2024 "
                       "Part A, Annexure 2.7), a ward above it only marked.").font = B.italic
    return x1 + 4


def wards(B):
    T = B.info.get("tech") or {}
    W = T.get("wards") or []
    wt = B.info.get("ward_table")
    if not W and not wt:
        return None
    PR = B.PR
    G = B.crit["ward_growth"]
    ws = B.sheet("Wards", "WARD-WISE POPULATION AND ITS GROWTH BY THE CHARACTER OF THE WARD", 17)
    for c, w in zip("ABCDEFGHIJKLMNOPQ", (6, 26, 20, 13, 10, 12, 12, 12, 9, 12, 12, 12, 12, 18, 16, 12, 14)):
        ws.column_dimensions[c].width = w
    # the growth table also for the town's list of wards (T2 Town Wards, 9-Nov-2026)
    used = W or any(r.get("char") for r in (wt or {}).get("rows", [])) or bool((B.info.get("town") or {}).get("rows"))
    # the table first, the growth table A after it - its rows known beforehand, for the table's formulas
    r0 = 5 + (len(wt["rows"]) + 4 if wt else 0)
    g0 = r0 + 2
    grow = {k: g0 + i for i, k in enumerate(G["value"])} if used else {}
    B.WARDS = {"x0": 7 if wt else None, "n": len(wt["rows"]) if wt else 0, "grow": grow}   # for T2-T4 (9-Nov-2026)
    if wt:
        ward_table(B, ws, 5, grow)
    if not used:
        B.sign(ws, r0 + 1, 9)
        return ws
    ws.cell(r0, 2, "A. Growth of a ward by its character (density, road network, master plan, adjacent wards)").font = B.bold
    fo = (B.info.get("projection") or {}).get("far_open")     # Far-open balanced by the projection (7-Nov-2026)
    yr = f" {wt['year']}" if wt and wt['year'] else ""
    B.header(ws, r0 + 1, ["Sl.No", "Character of ward", f"Present{yr}", "Base year", "Middle year (+15)",
                          "Design year (+30)"] + ([f"Town population{yr} (all its wards)"] if fo else []))
    keys = list(G["value"])
    g1 = g0 + len(keys) - 1
    tg = g1 + 1                                      # the town of each stage by the adopted projection
    for i, (k, v) in enumerate(G["value"].items()):
        B.cell(ws, g0 + i, 1, i + 1)
        B.cell(ws, g0 + i, 2, k)
        B.cell(ws, g0 + i, 3, 1)
        if fo:
            B.cell(ws, g0 + i, 7, fo["city"].get(k), fmt="#,##0", inp=True)
        for j, f in enumerate(v):
            c = B.col(4 + j)
            if fo and k == FAR_OPEN:               # the balance: the town less the others, over Far-open's (T P470)
                o = "-".join(f"$G{g0 + n}*{c}{g0 + n}" for n, x in enumerate(keys) if x != k)
                B.cell(ws, g0 + i, 4 + j, f"=({c}{tg}-{o})/$G{g0 + i}", fmt="0.0000")
            else:
                B.cell(ws, g0 + i, 4 + j, f, fmt="0.0000", inp=True)
    if fo:
        B.cell(ws, tg, 2, "The town by the adopted projection", bold=True)
        B.cell(ws, tg, 3, f"=SUM(G{g0}:G{g1})", fmt="#,##0")
        for j, t in enumerate(("init", "mid", "ult")):
            B.cell(ws, tg, 4 + j, f"=ROUND(C{tg}*{fo['ratio'][t]:.6f},0)", fmt="#,##0")
        B.cell(ws, tg, 7, f"=SUM(G{g0}:G{g1})", fmt="#,##0", bold=True)
        g1 += 1
    ws.cell(g1 + 1, 2, f"{DPR} p76; a ward without a character grows by the one factor of the page / projection (sheet "
                       "Project)." + (" Far-open: the balancing factor - the town's population of each stage by the "
                       "adopted projection (its growth from the census, sheet T1) less the other characters x their "
                       "factors, over Far-open's population (example technical.xlsx T P470); the town's population "
                       "by character: yellow." if fo else " Far-open: the balancing value of the town's wards (the "
                       "example's).")).font = B.italic
    dn = (wt or {}).get("dens") or {}
    ws.cell(g1 + 2, 2, "The character by the density of the ward (persons / ha) above " +
            " / ".join(f"{dn.get(k, v):,.0f} {k}" for k, v in WARD_DENS.items()) +
            f", the rest {FAR_OPEN} (the example's limits and factors, not CPHEEO's; the names CPHEEO's categories with "
            "the Riverside water DPR p76's word, densest first). CPHEEO Manual on Water Supply 2024 "
            "Part A: 2.8.2.2 - the town's total distributed ward-wise by the trend of growth (ward-wise density, initial "
            "and ultimate); 2.8.1.24 (iii) - the ward's equivalent area (residential x 1, public x 0.25, industry / "
            "agriculture x 0.1); Annexure 2.7 p974-976 - the developed core near saturation (its density close to the "
            "present), the saturation density the upper limit of every ward, the wards near the core growing faster, "
            "beyond a barrier slower, the wards' total to tally with the town's projection, approved by the local "
            "body before the design; Annexure 2.8 p980 (Final Forecast).").font = B.italic
    g1 += 1
    if not W:
        B.sign(ws, g1 + 3, 9)
        return ws
    r = g1 + 3
    ws.cell(r, 2, "B. The projected population of the wards (on their junctions of this design)").font = B.bold
    B.header(ws, r + 1, ["Sl.No", "Ward", "Character", "Present population (map)", "Junctions"] +
             [f'=""&{PR[k]}' for _, k in YEARS] + ["x base", "x middle", "x design"])
    x0 = r + 2
    for i, w in enumerate(W):
        x = x0 + i
        for c, v in enumerate([i + 1, w["name"], w.get("character") or "-", w["population"], w["junctions"],
                               w["pop"]["init"], w["pop"]["mid"], w["pop"]["ult"]], 1):
            B.cell(ws, x, c, v, fmt="#,##0" if c >= 4 else None)
        for j, c in enumerate("FGH"):
            B.cell(ws, x, 9 + j, f"=IFERROR({c}{x}/D{x},0)", fmt="0.00")
    x1 = x0 + len(W) - 1
    B.cell(ws, x1 + 1, 2, "Total", bold=True)
    for c in "DEFGH":
        B.cell(ws, x1 + 1, " ABCDEFGH".index(c), f"=SUM({c}{x0}:{c}{x1})", fmt="#,##0", bold=True)
    ws.cell(x1 + 2, 2, "The population of each year on the ward's junctions (the design): present x the factor of its "
                       "character, or of the page; a ward drawn over another counts where it was drawn first.").font = B.italic
    # C. zone-wise population by ward (DPR p83)
    r = x1 + 4
    ws.cell(r, 2, "C. Zone-wise population (each operation zone: the wards in it)").font = B.bold
    r += 1
    for zn in [t["zone"]["name"] for t in B.T3]:
        parts = [(w, w["oz"][zn]) for w in W if zn in w["oz"]]
        if not parts:
            continue
        B.cell(ws, r, 2, f"Operation zone {zn}", bold=True)
        B.header(ws, r + 1, ["", "Ward", "Share of the ward (%)"] + [f"Population {k}" for k in ("base", "middle", "design")]
                 + [f"Floating {k}" for k in ("base", "middle", "design")] + ["Total design"])
        y0 = r + 2
        for k, (w, p) in enumerate(parts):
            y = y0 + k
            B.cell(ws, y, 2, w["name"])
            B.cell(ws, y, 3, round(p["ult"] / max(w["pop"]["ult"], 1), 4), fmt="0.0%")
            for j, t in enumerate(("init", "mid", "ult")):
                B.cell(ws, y, 4 + j, p[t], fmt="#,##0")
                B.cell(ws, y, 7 + j, f"={B.col(4 + j)}{y}*{PR['floating']}", fmt="#,##0")
            B.cell(ws, y, 10, f"=F{y}+I{y}", fmt="#,##0")
        y1 = y0 + len(parts) - 1
        B.cell(ws, y1 + 1, 2, "Total", bold=True)
        for c in range(4, 11):
            B.cell(ws, y1 + 1, c, f"=SUM({B.col(c)}{y0}:{B.col(c)}{y1})", fmt="#,##0", bold=True)
        r = y1 + 3
    B.sign(ws, r + 1, 9)
    return ws


def dmas(B):
    T = B.info.get("tech") or {}
    D = T.get("dmas") or []
    if not D:
        return None
    PR = B.PR
    ws = B.sheet("DMA Pop", "DMA-WISE POPULATION & HOUSEHOLD", 8)
    for c, w in zip("ABCDEFGH", (6, 26, 13, 13, 13, 12, 12, 12)):
        ws.column_dimensions[c].width = w
    B.header(ws, 5, ["S.No", "DMA No.", "Population base", "Population middle", "Population design", "Households base",
                     "Households middle", "Households design"])
    for c, (_, k) in zip("CDE", YEARS):
        ws.cell(4, " ABCDE".index(c), f'=""&{PR[k]}').font = B.bold
    r = 6
    own = T.get("own_stages")
    for t in B.T3:
        zn = t["zone"]["name"]
        ds = [d for d in D if d["zone"] == zn]
        if not ds:
            continue
        B.cell(ws, r, 2, f"Operation zone {zn}", bold=True)
        y0 = r + 1
        for i, d in enumerate(ds):
            y = y0 + i
            s = T["dma"].get(d["name"]) or {}
            B.cell(ws, y, 1, i + 1)
            B.cell(ws, y, 2, d["name"])
            B.cell(ws, y, 5, s.get("ult", d["population"]), fmt="#,##0")
            if own and s:
                B.cell(ws, y, 3, s["init"], fmt="#,##0")
                B.cell(ws, y, 4, s["mid"], fmt="#,##0")
            else:
                B.cell(ws, y, 3, f"=ROUND(E{y}*{PR['pop_base']}/{PR['pop_design']},0)", fmt="#,##0")
                B.cell(ws, y, 4, f"=ROUND(E{y}*{PR['pop_mid']}/{PR['pop_design']},0)", fmt="#,##0")
            for j, c in enumerate("CDE"):
                B.cell(ws, y, 6 + j, f"=ROUNDUP({c}{y}/{PR['ppc']},0)", fmt="#,##0")
        y1 = y0 + len(ds) - 1
        B.cell(ws, y1 + 1, 2, "Total", bold=True)
        for c in "CDEFGH":
            B.cell(ws, y1 + 1, " ABCDEFGH".index(c), f"=SUM({c}{y0}:{c}{y1})", fmt="#,##0", bold=True)
        r = y1 + 3
    ws.cell(r, 2, f"{DPR} p88-91: the DMAs of the zoning; households = population / persons per connection (sheet "
                  "Project).").font = B.italic
    B.sign(ws, r + 3, 7)
    return ws


def requirement(B):
    PR, T1 = B.PR, B.T1
    ws = B.sheet("Req", "REQUIREMENT OF WATER & TUBE WELLS (AND CWR PUMPS) OF EACH OPERATION ZONE", 6)
    for c, w in zip("ABCDEF", (7, 56, 13, 13, 13, 8)):
        ws.column_dimensions[c].width = w
    col, f0 = B.EMTS["col"], B.EMTS["first"]
    r = 5
    for i, t in enumerate(B.T3):
        z, s, rf = t["zone"], q(t["sheet"]), t["ref"]
        x2, tw = T1["rows"][z["name"]], 6 + i
        hrs = rf["q_pump"] - 3
        B.cell(ws, r, 2, f"Operation zone {z['name']}", bold=True)
        _heads(B, ws, r + 1, ["S.NO", "PARTICULARS"], ["Unit"])
        rows = []                                    # (no, label, [3 formulas] or one for all, unit)

        def add(no, lab, f, unit, bold=False):
            rows.append((no, lab, f, unit, bold))
        Y = lambda k: r + 2 + k                      # the row of the k-th line (k from 0)
        cols = "CDE"
        add("1", "Total population", [f"={c}{Y(1)}+{c}{Y(2)}" for c in cols], "souls", True)
        add("1 (a)", "Population", [f"=T1!{c}{x2}" for c in "DEF"], "souls")
        add("1 (b)", "Floating population", [f"=T1!{c}{x2}" for c in "GHI"], "souls")
        add("2", "Total daily requirement of water", [f"={c}{Y(4)}+{c}{Y(5)}+{c}{Y(6)}+{c}{Y(7)}" for c in cols], "KLD",
            True)
        add("2 (a)", f'="Water demand (@ "&TEXT({PR["lpcd"]}*(1+{PR["losses"]}),"0.0")&" LPCD with losses)"',
            [f"={c}{Y(1)}*{PR['lpcd']}*(1+{PR['losses']})/1000" for c in cols], "KLD")
        add("2 (b)", f'="Floating demand (@ "&{PR["floating_lpcd"]}&" LPCD)"',
            [f"={c}{Y(2)}*{PR['floating_lpcd']}/1000" for c in cols], "KLD")
        add("2 (c)", "Fire demand", [f"=T1!{T1['fire_col']}{x2}"] * 3, "KLD")
        add("2 (d)", "Bulk consumers with losses", [f"=T1!{T1['bulk_col']}{x2}*(1+{PR['losses']})"] * 3, "KLD")
        add("3", "Assuming hours of pumping", [f"={s}!{c}{hrs}" for c in "DEF"], "h")
        add("4", "Existing tube wells, rebored ones included (nos)", [f"=TW!C{tw}+TW!P{tw}"] * 3, "nos")
        add("4 (i)", "Discharge of an existing tube well", [f"=TW!D{tw}"] * 3, "LPM")
        add("4 (ii)", "Total discharge from existing tube wells", [f"={c}{Y(9)}*{c}{Y(10)}" for c in cols], "LPM")
        add("4 (iii)", "  in KLD", [f"={c}{Y(11)}*{c}{Y(8)}*60/1000" for c in cols], "KLD")
        add("5", "Net daily requirement of water", [f"=MAX(0,{c}{Y(3)}-{c}{Y(12)})" for c in cols], "KLD", True)
        add("6 (i)", "Anticipated discharge of a proposed tube well", [f"=TW!I{tw}"] * 3, "LPM")
        add("6 (ii)", "  in KLD", [f"={c}{Y(14)}*{c}{Y(8)}*60/1000" for c in cols], "KLD")
        add("7", "No. of tube wells required", [f"=IFERROR({c}{Y(13)}/{c}{Y(15)},0)" for c in cols], "nos")
        add("8", "No. of tube wells proposed (sheet TW: for +15 years)", [f"=TW!L{tw}"] * 3, "nos", True)
        add("9", "Total no. of tube wells (existing + proposed)", [f"={c}{Y(9)}+{c}{Y(17)}" for c in cols], "nos")
        add("10 (i)", "Total discharge (existing + proposed)", [f"={c}{Y(11)}+{c}{Y(17)}*{c}{Y(14)}" for c in cols],
            "LPM")
        add("10 (ii)", "  in KLD", [f"={c}{Y(19)}*{c}{Y(8)}*60/1000" for c in cols], "KLD")
        add("11", "Actual hours of pumping", [f"=IFERROR({c}{Y(3)}*1000/({c}{Y(19)}*60),0)" for c in cols], "h", True)
        if z.get("cwr_kl"):
            C = lambda k: f"'EM TS'!${col[k]}${f0 + i}"
            add("12", "CWR pumps - discharge of a pump", [f"={C('cq')}*60"] * 3, "LPM")
            add("13", "No. of CWR pumps required", [f"=IFERROR({c}{Y(3)}*1000/({c}{Y(22)}*{c}{Y(8)}*60),0)"
                                                    for c in cols], "nos")
            add("14", "No. of CWR pumps proposed (working; sheet EM TS)", [f"={C('cw')}"] * 3, "nos", True)
            add("15", "Total discharge of the CWR pumps", [f"={c}{Y(22)}*{c}{Y(24)}" for c in cols], "LPM")
            add("16", "Actual hours of pumping of the CWR pumps",
                [f"=IFERROR({c}{Y(3)}*1000/({c}{Y(25)}*60),0)" for c in cols], "h")
        n = 17 if z.get("cwr_kl") else 12
        add(str(n), "Standby tube wells (CPHEEO 5.7.5; sheet TW)", [f"=TW!N{tw}"] * 3, "nos")
        add(str(n + 1), "New tube wells to be constructed (proposed + standby)", [f"=TW!O{tw}"] * 3, "nos", True)
        for k, (no, lab, f, unit, bold) in enumerate(rows):
            y = Y(k)
            B.cell(ws, y, 1, no)
            B.cell(ws, y, 2, lab, bold=bold)
            for j, c in enumerate(cols):
                B.cell(ws, y, 3 + j, f[j], fmt="#,##0.00", bold=bold)
            B.cell(ws, y, 6, unit)
        r = Y(len(rows)) + 2
    ws.cell(r, 2, f"{DPR} p92-113 'Requirement of water & tube wells' / '& CWR pump': the daily requirement = the "
                  "distribution demand with losses + fire; the tube wells proposed as sheet TW (the +15 years "
                  "pumping main demand).").font = B.italic
    B.sign(ws, r + 3, 5)
    return ws


def mass_balance(B):
    ws = B.sheet("MB OHT", "MASS BALANCING OF OHT (EACH OPERATION ZONE)", 8)
    for c, w in zip("ABCDEFGH", (6, 10, 10, 13, 13, 14, 14, 13)):
        ws.column_dimensions[c].width = w
    r = 5
    for i, t in enumerate(B.T3):
        z, s, rf = t["zone"], q(t["sheet"]), t["ref"]
        B.cell(ws, r, 1, f"Operation zone {z['name']}", bold=True)
        lines = [("Considering rate of pumping (hours of filling, sheet Storage)", "=Storage!$C$31", "Hours"),
                 ("Demand for ultimate stage (without fire - its third is stored on top, T14 S.4)",
                  f"={s}!F{rf['need'] - 4}", "KLD"),
                 ("Ultimate demand in the hours of filling", f"=F{r + 2}/F{r + 1}", "m3/hr"),
                 ("Ultimate demand in 24 hrs", f"=F{r + 2}/24", "m3/hr")]
        for k, (lab, f, unit) in enumerate(lines):
            B.cell(ws, r + 1 + k, 1, lab)
            ws.merge_cells(start_row=r + 1 + k, start_column=1, end_row=r + 1 + k, end_column=5)
            B.cell(ws, r + 1 + k, 6, f, fmt="#,##0.00")
            B.cell(ws, r + 1 + k, 7, unit)
        h = r + 5
        B.header(ws, h, ["Hrs", "Multiplying inflow", "Multiplying outflow", "Inflow (m3/hr)", "Outflow 24 hrs (m3/hr)",
                         "Cumulative inflow (KL)", "Cumulative outflow (KL)", "Storage (KL)"])
        y0 = h + 1
        for k in range(24):
            y = y0 + k
            B.cell(ws, y, 1, k + 1)
            B.cell(ws, y, 2, f"=Storage!C{6 + k}", fmt="0.00")
            B.cell(ws, y, 3, f"=Storage!F{6 + k}", fmt="0.00")
            B.cell(ws, y, 4, f"=B{y}*$F${r + 3}", fmt="#,##0.00")
            B.cell(ws, y, 5, f"=C{y}*$F${r + 4}", fmt="#,##0.00")
            B.cell(ws, y, 6, f"=D{y}" + (f"+F{y - 1}" if k else ""), fmt="#,##0.00")
            B.cell(ws, y, 7, f"=E{y}" + (f"+G{y - 1}" if k else ""), fmt="#,##0.00")
            B.cell(ws, y, 8, f"=F{y}-G{y}", fmt="#,##0.00")
        y1 = y0 + 23
        res = [("Maximum cumulative surplus", f"=MAX(0,MAX(H{y0}:H{y1}))"),
               ("Maximum cumulative deficit", f"=MIN(0,MIN(H{y0}:H{y1}))"),
               ("Capacity of storage reservoir (mass balance)", f"=H{y1 + 1}-H{y1 + 2}"),
               ("33 % of the ultimate demand (CPHEEO Table 2.7 S.No.12)", f"={s}!F{rf['need'] - 3}"),
               ("Fire storage: a third of the fire demand", f"={s}!F{rf['need'] - 1}"),
               ("Required OHT capacity (the larger + fire)", f"={s}!F{rf['need']}"),
               ("Existing OHT capacity", f"={s}!F{rf['exist']}"),
               ("Provide OHT (new)", f"={s}!F{rf['new']}"),
               ("Total no. of tube wells (existing, rebored, new incl. standby)",
                f"=TW!C{6 + i}+TW!P{6 + i}+TW!O{6 + i}"),
               ("Capacity of CWR (new)", f"={s}!F{rf['cwr']}")]
        for k, (lab, f) in enumerate(res):
            y = y1 + 1 + k
            B.cell(ws, y, 1, lab, bold=k in (2, 5, 7))
            ws.merge_cells(start_row=y, start_column=1, end_row=y, end_column=7)
            B.cell(ws, y, 8, f, fmt="#,##0.00", bold=k in (2, 5, 7))
        r = y1 + len(res) + 3
    ws.cell(r, 1, f"{DPR} p114-128: the draw-off pattern and filling hours of sheet Storage on each OZ's ultimate "
                  "demand; the capacity proposed is that of its T14 (the larger of mass balance / 33 %, + a third of the "
                  "fire demand).").font = B.italic
    B.sign(ws, r + 3, 7)
    return ws


def static_head(B):
    R = B.info.get("rising") or {}
    tws = [t for t in R.get("tws") or [] if t.get("size")]
    if not tws:
        return None
    P = B.S["pump"]
    gl = R.get("gl") or {}
    ws = B.sheet("Static Head", "CALCULATION OF STATIC HEAD FOR THE DESIGN OF RISING MAIN (EACH OPERATION ZONE)", 10)
    ws.column_dimensions["A"].width, ws.column_dimensions["B"].width = 7, 46
    r = 5
    for t3 in B.T3:
        z, s, rf = t3["zone"], q(t3["sheet"]), t3["ref"]
        mine = [t for t in tws if t["oz"] == z["name"]]
        if not mine:
            continue
        cwr = bool(z.get("cwr_kl"))
        pp0 = rf["head"] - 8
        dest = "CWR" if cwr else "OHT"
        cols = [(f"{t['name']} to {dest}", t) for t in mine] + ([("CWR to OHT", None)] if cwr else [])
        B.cell(ws, r, 2, f"Operation zone {z['name']}", bold=True)
        B.header(ws, r + 1, ["S.NO", "DESCRIPTION"] + [c[0] for c in cols])
        ws.row_dimensions[r + 1].height = 30
        y = r + 2
        L = lambda k: y + k                          # the k-th line
        lines = ["Depth of water below G.L.", "Seasonal variation", "Depression due to pumping",
                 "Height of staging above ground", "Depth of water in tank", "GL at tube well", "GL at OHT / CWR",
                 "Difference in G.L. of OHT and T.W.", "Terminal head", "Depth of sump at CWR", "Total",
                 "Friction and other head loss (Hf, ultimate)", "Grand total", "Say", "Length of rising main (m)",
                 "Dia (mm)", "Head of the design (sheet T15 / T14 C.6)"]
        for k, lab in enumerate(lines):
            B.cell(ws, L(k), 1, k + 1)
            B.cell(ws, L(k), 2, lab, bold=lab in ("Total", "Grand total", "Say"))
        for j, (_, t) in enumerate(cols):
            c, C = 3 + j, B.col(3 + j)
            ws.column_dimensions[C].width = 14
            tot = f"=SUM({C}{L(0)}:{C}{L(4)})+{C}{L(7)}+{C}{L(8)}+{C}{L(9)}"
            if t is not None:
                vals = [f"={s}!F{pp0}", f"={s}!F{pp0 + 1}", f"={s}!F{pp0 + 2}",
                        f"={s}!F{rf['cwr_d']}" if cwr else f"={s}!F{pp0 + 3}", 0 if cwr else f"={s}!F{pp0 + 4}",
                        t.get("gl"), gl.get(z["name"]), f"={C}{L(6)}-{C}{L(5)}", f"={s}!F{pp0 + 6}", 0, tot,
                        t.get("hf_m"), f"={C}{L(10)}+{C}{L(11)}", f"=ROUNDUP({C}{L(12)},0)", t.get("length_m"),
                        int(t["size"].split()[-1]), t.get("head_m")]
            else:                                    # the CWR pumps to the OHT (T6 C.6)
                vals = [0, 0, 0, f"={s}!F{pp0 + 3}", f"={s}!F{pp0 + 4}", gl.get(z["name"]), gl.get(z["name"]),
                        f"={C}{L(6)}-{C}{L(5)}", f"={s}!F{pp0 + 6}", P["cwr_sump_m"], tot, P["cwr_main_hf_m"],
                        f"={C}{L(10)}+{C}{L(11)}", f"=ROUNDUP({C}{L(12)},0)", None, None, f"={s}!F{rf['cwr_head']}"]
            for k, v in enumerate(vals):
                B.cell(ws, L(k), c, v, fmt="0" if k == 15 else "#,##0.00", bold=k in (10, 12, 13))
        n = len(lines)
        B.cell(ws, L(n), 2, "OHT capacity (KL)")
        B.cell(ws, L(n), 3, f"=MAX({s}!F{rf['exist']},{s}!F{rf['new']})", fmt="#,##0")
        B.cell(ws, L(n + 1), 2, "CWR capacity (KL)")
        B.cell(ws, L(n + 1), 3, f"={s}!F{rf['cwr']}" if cwr else "Not required", fmt="#,##0")
        r = L(n + 1) + 3
    ws.cell(r, 2, f"{DPR} p130-196: the water level, seasonal variation and depression of the tube well and the "
                  "terminal head of its T14; in a CWR zone the tube wells lift to the ground at the CWR (T14 C.5) and "
                  "the CWR pumps to the OHT (T14 C.6); the friction and size of the economical main of the design (sheet "
                  "T7: the candidates, present worth, surge).").font = B.italic
    B.sign(ws, r + 3, 6)
    return ws


def pipe_table(B):
    T = B.info.get("tech") or {}
    pipes = T.get("pipes") or []
    if not pipes:
        return None
    from .design import load_pipes
    C = {s["name"]: s.get("C") for s in load_pipes()}
    T1 = B.T1
    ws = B.sheet("Pipe Table", "DISTRIBUTION DESIGN AND PIPE TABLE OF EACH OPERATION ZONE", 10)
    for c, w in zip("ABCDEFGHIJ", (14, 10, 12, 12, 10, 12, 10, 12, 16, 8)):
        ws.column_dimensions[c].width = w
    key = lambda p: [(0, int(x), "") if x.isdigit() else (1, 0, x) for x in re.split(r"(\d+)", str(p["label"]))]
    pf = B.crit["peak_factor"]["value"]
    rh = B.crit["residual_head_m"]["value"]
    r = 5
    for t3 in B.T3:
        z, s, rf = t3["zone"], q(t3["sheet"]), t3["ref"]
        mine = sorted((p for p in pipes if p["oz"] == z["name"]), key=key)
        if not mine:
            continue
        x2 = T1["rows"][z["name"]]
        pr = (T.get("press") or {}).get(z["name"]) or {}
        B.cell(ws, r, 1, f"Distribution design of operation zone {z['name']}", bold=True)
        head = [("Residual head at consumer tapping point not less than (m)", rh),
                ("Population covered (ultimate)", f"=T1!F{x2}"), ("OHT", z["name"]),
                ("OHT capacity (KL)", f"=MAX({s}!F{rf['exist']},{s}!F{rf['new']})"),
                ("Staging (m)", f"={s}!F{rf['head'] - 5}"), ("Hours of operation", 24),
                ("Lowest ground level (m)", z.get("elev_min")), ("Highest ground level (m)", z.get("elev_max")),
                ("Minimum residual head (m) / junction", f"{pr['min'][0]:.2f} / {pr['min'][1]}" if pr else "-"),
                ("Maximum residual head (m) / junction", f"{pr['max'][0]:.2f} / {pr['max'][1]}" if pr else "-"),
                ("Peak factor", pf), ("Material, Hazen-Williams C", "HDPE PE-100 PN-6 / DI K-7")]
        for k, (lab, v) in enumerate(head):
            y = r + 1 + k
            B.cell(ws, y, 1, lab)
            ws.merge_cells(start_row=y, start_column=1, end_row=y, end_column=4)
            B.cell(ws, y, 5, v, fmt="#,##0.00" if isinstance(v, float) else "#,##0")
            ws.merge_cells(start_row=y, start_column=5, end_row=y, end_column=7)
        h = r + 2 + len(head)
        B.header(ws, h, ["Pipe ID", "Length (m)", "Size", "Internal diameter (mm)", "H-W C", "Flow (LPM)",
                         "Velocity (m/s)", "Unit headloss (m/km)", "DMA", "Closed"])
        for k, p in enumerate(mine):
            y = h + 1 + k
            for c, v in enumerate([p["label"], p["length"], p["size"], p["id_mm"], C.get(p["size"]),
                                   round((p["flow"] or 0.0) * 60, 2), p["v"], p["hl_km"], p["dma"] or "",
                                   "yes" if p["closed"] else ""], 1):
                ws.cell(y, c, v)
        r = h + len(mine) + 3
    ws.cell(r, 1, f"{DPR} p199-201: the pipes of the design (peak flow, L/s x 60), each in the OZ of its start "
                  "junction.").font = B.italic
    B.sign(ws, r + 3, 8)
    return ws


# ------------------------------------------------------------------------ the example technical.xlsx Tech3-Tech7
# (user decision 9-Nov-2026: five sheets of their own, as the example's 'Tech3'-'Tech7' of the Elmwood technical
# statement; households = population / persons per connection, as T9)
EX = "example technical.xlsx (Elmwood)"


def _group_head(B, ws, r, groups):
    """A two-row header: [(title, n)] - n 1 merged over both rows, n 3 the title over the three years; the row of
    column numbers below it (as the example). Returns the last column."""
    yrs = [f'=""&{B.PR[k]}' for _, k in YEARS]
    c = 1
    for title, n in groups:
        if n == 1:
            ws.merge_cells(start_row=r, start_column=c, end_row=r + 1, end_column=c)
        else:
            ws.merge_cells(start_row=r, start_column=c, end_row=r, end_column=c + n - 1)
            for j in range(n):
                ws.cell(r + 1, c + j, yrs[j])
        ws.cell(r, c, title)
        c += n
    last = c - 1
    for y in (r, r + 1, r + 2):
        for x in range(1, last + 1):
            cell = ws.cell(y, x)
            if y == r + 2:
                cell.value = x
            cell.font, cell.alignment, cell.border = B.bold, B.center, B.box
            if y < r + 2:
                cell.fill = B.head
    ws.row_dimensions[r].height = 45
    return last


def _numbers(B, ws, r, last):
    """The row of column numbers repeated at the head of each block (as the example's Tech3)."""
    for x in range(1, last + 1):
        c = B.cell(ws, r, x, x)
        c.alignment = B.hcenter


def _note(B, ws, r, text, last):
    """The note under a sheet: over its width, wrapped, its height by its length."""
    c = ws.cell(r, 1, text)
    c.font, c.alignment = B.italic, B.wrap
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=last)
    width = sum(ws.column_dimensions[B.col(x)].width or 8.43 for x in range(1, last + 1))
    ws.row_dimensions[r].height = 15 * max(1, -(-len(text) // int(width * 1.1)))


def _block_title(B, ws, r, text, last):
    B.cell(ws, r, 1, text, bold=True)
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=last)


def dma_demand(B):
    """'Tech3' DMA WISE DEMAND: each OZ a block, a row for each DMA (for each ward in it, where the wards are on the
    map: its no. and the share of its design-year population) - population, floating, total, demand with losses,
    floating demand, fire (the OZ's of T2 by population), total demand and households in the three years; the
    junctions of the OZ in no DMA a row of their own (the OZ's population of T2 less the DMAs')."""
    T = B.info.get("tech") or {}
    D = T.get("dmas") or []
    PR, T1 = B.PR, B.T1
    own = T.get("own_stages")
    ws = B.sheet("DMA Demand", "DMA WISE DEMAND", 25)
    groups = [("DMA No.", 1), ("Ward No.", 1), ("Contribution (in % age)", 1), ("Population", 3),
              (f'="Floating Population @"&TEXT({PR["floating"]},"0%")', 3), ("Total Population", 3),
              (f'="Demand (in KLD) (@"&TEXT({PR["lpcd"]}*(1+{PR["losses"]}),"0.0")&" LPCD including "&'
               f'TEXT({PR["losses"]},"0%")&" for losses)"', 3),
              (f'="Floating Demand (in KLD) (@"&{PR["floating_lpcd"]}&" LPCD)"', 3), ("Fire Demand (KLD)", 1),
              ("Total Demand (in KLD)", 3), ("Household", 3)]
    last = _group_head(B, ws, 5, groups)
    for c, w in zip("ABC", (18, 9, 13)):
        ws.column_dimensions[c].width = w
    for c in range(4, last + 1):
        ws.column_dimensions[B.col(c)].width = 10
    r = 8
    tot, rows = {}, {}
    for t in B.T3:
        zn = t["zone"]["name"]
        x2 = T1["rows"][zn]
        _block_title(B, ws, r, f"Operation zone {zn}", last)
        _numbers(B, ws, r + 1, last)
        y = y0 = r + 2
        rows[zn] = []
        dsum = 0
        for d in (d for d in D if d["zone"] == zn):
            s = T["dma"].get(d["name"]) or {}
            parts = d.get("wards") or [dict(s or {"ult": d["population"]}, no=None, share=None)]
            a = y
            for p in parts:
                B.cell(ws, y, 1, d["name"])
                B.cell(ws, y, 2, p.get("no") or "-").alignment = B.hcenter
                B.cell(ws, y, 3, p["share"] if p.get("share") is not None else "-", fmt="0.0%").alignment = B.hcenter
                B.cell(ws, y, 6, p["ult"], fmt="#,##0")
                dsum += p["ult"]
                if own and "init" in p:
                    B.cell(ws, y, 4, p["init"], fmt="#,##0")
                    B.cell(ws, y, 5, p["mid"], fmt="#,##0")
                else:
                    B.cell(ws, y, 4, f"=ROUND(F{y}*{PR['pop_base']}/{PR['pop_design']},0)", fmt="#,##0")
                    B.cell(ws, y, 5, f"=ROUND(F{y}*{PR['pop_mid']}/{PR['pop_design']},0)", fmt="#,##0")
                y += 1
            rows[zn].append((d["name"], a, y - 1))
        # the OZ's junctions in no DMA (more than the rounding of the DMAs' and the OZ's populations)
        if not rows[zn] or abs(round(t["zone"]["population"]) - dsum) > 0.5 * (y - y0 + 1):
            B.cell(ws, y, 1, "Not in a DMA" if rows[zn] else "Whole zone (no DMA)")
            B.cell(ws, y, 2, "-").alignment = B.hcenter
            B.cell(ws, y, 3, "-").alignment = B.hcenter
            for j, c in enumerate("DEF"):
                less = f"-SUM({c}{y0}:{c}{y - 1})" if y > y0 else ""
                B.cell(ws, y, 4 + j, f"=T1!{c}{x2}{less}", fmt="#,##0")
            rows[zn].append((ws.cell(y, 1).value, y, y))
            y += 1
        for x in range(y0, y):
            for j in range(3):
                P = B.col(4 + j)
                B.cell(ws, x, 7 + j, f"={P}{x}*{PR['floating']}", fmt="#,##0")
                B.cell(ws, x, 10 + j, f"={P}{x}+{B.col(7 + j)}{x}", fmt="#,##0")
                B.cell(ws, x, 13 + j, f"={P}{x}*{PR['lpcd']}*(1+{PR['losses']})/1000", fmt="#,##0.00")
                B.cell(ws, x, 16 + j, f"={B.col(7 + j)}{x}*{PR['floating_lpcd']}/1000", fmt="#,##0.00")
                B.cell(ws, x, 20 + j, f"={B.col(13 + j)}{x}+{B.col(16 + j)}{x}+$S{x}", fmt="#,##0.00")
                B.cell(ws, x, 23 + j, f"=ROUNDUP({P}{x}/{PR['ppc']},0)", fmt="#,##0")
            B.cell(ws, x, 19, f"=IFERROR(T1!${T1['fire_col']}${x2}*F{x}/T1!$F${x2},0)", fmt="#,##0.00")
        B.cell(ws, y, 1, "Total", bold=True)
        ws.merge_cells(start_row=y, start_column=1, end_row=y, end_column=3)
        for c in range(4, last + 1):
            B.cell(ws, y, c, f"=SUM({B.col(c)}{y0}:{B.col(c)}{y - 1})",
                   fmt="#,##0.00" if 13 <= c <= 22 else "#,##0", bold=True)
        tot[zn] = y
        r = y + 2
    _note(B, ws, r, f"{EX} 'Tech3': the DMAs of the zoning (where the wards are on the map, a row for each ward in the "
                    "DMA, its contribution = the share of the ward's design-year population); the demand as sheet T1 - "
                    "the domestic with the distribution losses, floating without, fire of the OZ shared by the design-"
                    "year population (the same in every year); households = population / persons per connection "
                    "(sheet Project). Bulk consumers are not DMA-wise: in sheet T1.", last)
    B.sign(ws, r + 3, 21)
    ws.freeze_panes = "D8"
    B.DMAD = {"tot": tot, "rows": rows, "last": last}
    return ws


def zone_summary(B):
    """'Tech4' SUMMARY - ZONE WISE DETAILS OF POPULATION & DEMAND: the OZ totals of DMA Demand."""
    X = B.DMAD
    ws = B.sheet("Zone Summary", "SUMMARY - ZONE WISE DETAILS OF POPULATION & DEMAND", 24)
    dd = B.wb["DMA Demand"]
    groups = [("S. No.", 1), ("Zone No.", 1)] + [(dd.cell(5, c).value, 1 if c == 19 else 3) for c in
                                                   (4, 7, 10, 13, 16, 19, 20, 23)]
    last = _group_head(B, ws, 5, groups)
    ws.column_dimensions["A"].width, ws.column_dimensions["B"].width = 6, 18
    for c in range(3, last + 1):
        ws.column_dimensions[B.col(c)].width = 10
    y0 = 8
    for i, t in enumerate(B.T3):
        y, zn = y0 + i, t["zone"]["name"]
        B.cell(ws, y, 1, i + 1)
        B.cell(ws, y, 2, zn)
        for c in range(3, last + 1):
            B.cell(ws, y, c, f"='DMA Demand'!{B.col(c + 1)}{X['tot'][zn]}",
                   fmt="#,##0.00" if 12 <= c <= 21 else "#,##0")
    y1 = y0 + len(B.T3) - 1
    B.cell(ws, y1 + 1, 1, "Total", bold=True)
    ws.merge_cells(start_row=y1 + 1, start_column=1, end_row=y1 + 1, end_column=2)
    for c in range(3, last + 1):
        B.cell(ws, y1 + 1, c, f"=SUM({B.col(c)}{y0}:{B.col(c)}{y1})", fmt="#,##0.00" if 12 <= c <= 21 else "#,##0",
               bold=True)
    _note(B, ws, y1 + 3, f"{EX} 'Tech4': the totals of each operation zone of sheet DMA Demand.", last)
    B.sign(ws, y1 + 6, 20)
    B.ZSUM = {"first": y0, "last": y1}
    return ws


def oht_details(B):
    """'Tech5' EXISTING/REQUIRED DETAILS OF O.H.T: of each OZ's T6."""
    ws = B.sheet("OHT Details", "EXISTING/REQUIRED DETAILS OF O.H.T", 8)
    B.header(ws, 5, ["S.No", "Name of Zone", "Existing OHT Capacity (in KL)", "Existing Capacity of CWR (in KL)",
                     "Required Capacity of OHT (in KL)", "Staging (m)", "Required Capacity of CWR (in KL)", "Remarks"],
             [7, 20, 14, 14, 15, 9, 15, 28])
    ws.row_dimensions[5].height = 45
    y0 = 6
    dash = lambda f: f'=IF({f}=0,"-",{f})'
    for i, t in enumerate(B.T3):
        y, z, s, rf = y0 + i, t["zone"], q(t["sheet"]), t["ref"]
        vals = [i + 1, z["name"], dash(f"{s}!F{rf['exist']}"), dash(f"{s}!F{rf['cwr'] - 1}"), f"={s}!F{rf['need']}",
                f"={s}!F{rf['head'] - 5}", dash(f"{s}!F{rf['cwr'] - 2}"),
                f"Existing OHT at {z['name']}" if z.get("capacity_kl") else ""]
        for c, v in enumerate(vals, 1):
            x = B.cell(ws, y, c, v, fmt="#,##0.00" if c in (5, 7) else "#,##0" if c in (3, 4, 6) else None)
            if c in (3, 4, 7):                       # "-" where none, as the numbers
                x.alignment = B.right
    y1 = y0 + len(B.T3) - 1
    for k, (lab, f) in enumerate((("Required Capacity", f"=SUM(E{y0}:E{y1})"),
                                  ("Available Capacity", f"=SUM(C{y0}:C{y1})"))):
        y = y1 + 2 + k
        B.cell(ws, y, 2, lab, bold=True)
        ws.merge_cells(start_row=y, start_column=2, end_row=y, end_column=4)
        B.cell(ws, y, 5, f, fmt="#,##0.00", bold=True)
        B.cell(ws, y, 6, "KL")
    _note(B, ws, y1 + 5, f"{EX} 'Tech5': of each operation zone's T14 - the required OHT the larger of mass balance / "
                         "33 % + a third of the fire demand, the CWR by the U.P. Jal Nigam rule.", 8)
    B.sign(ws, y1 + 8, 7)
    return ws


def dma_household(B):
    """'Tech6' DMA WISE POPULATION & HOUSEHOLD: each DMA's rows of DMA Demand summed."""
    X = B.DMAD
    ws = B.sheet("DMA HH", "DMA WISE POPULATION & HOUSEHOLD", 7)
    last = _group_head(B, ws, 5, [("DMA No.", 1), ("Projected Population", 3), ("Household", 3)])
    ws.column_dimensions["A"].width = 20
    for c in range(2, last + 1):
        ws.column_dimensions[B.col(c)].width = 12
    r = 8
    for t in B.T3:
        zn = t["zone"]["name"]
        _block_title(B, ws, r, f"Operation zone {zn}", last)
        y0 = r + 1
        for k, (name, a, b) in enumerate(X["rows"][zn]):
            y = y0 + k
            B.cell(ws, y, 1, name)
            for j, c in enumerate("DEFWXY"):
                B.cell(ws, y, 2 + j, f"=SUM('DMA Demand'!{c}{a}:{c}{b})", fmt="#,##0")
        y1 = y0 + len(X["rows"][zn]) - 1
        B.cell(ws, y1 + 1, 1, "Total", bold=True)
        for c in range(2, last + 1):
            B.cell(ws, y1 + 1, c, f"=SUM({B.col(c)}{y0}:{B.col(c)}{y1})", fmt="#,##0", bold=True)
        r = y1 + 3
    _note(B, ws, r, f"{EX} 'Tech6': each DMA of sheet DMA Demand (its wards summed).", last)
    B.sign(ws, r + 3, 5)
    return ws


def zone_household(B):
    """'Tech7' ZONE WISE HOUSEHOLD NUMBER: the population and households of Zone Summary."""
    Z = B.ZSUM
    ws = B.sheet("Zone HH", "ZONE WISE HOUSEHOLD NUMBER", 8)
    last = _group_head(B, ws, 5, [("S.No", 1), ("Zone No.", 1), ("Population", 3), ("Household", 3)])
    ws.column_dimensions["A"].width, ws.column_dimensions["B"].width = 7, 20
    for c in range(3, last + 1):
        ws.column_dimensions[B.col(c)].width = 12
    y0 = 8
    for i, t in enumerate(B.T3):
        y = y0 + i
        B.cell(ws, y, 1, i + 1)
        B.cell(ws, y, 2, t["zone"]["name"])
        for j, c in enumerate("CDEVWX"):
            B.cell(ws, y, 3 + j, f"='Zone Summary'!{c}{Z['first'] + i}", fmt="#,##0")
    y1 = y0 + len(B.T3) - 1
    B.cell(ws, y1 + 1, 1, "Total", bold=True)
    ws.merge_cells(start_row=y1 + 1, start_column=1, end_row=y1 + 1, end_column=2)
    for c in range(3, last + 1):
        B.cell(ws, y1 + 1, c, f"=SUM({B.col(c)}{y0}:{B.col(c)}{y1})", fmt="#,##0", bold=True)
    _note(B, ws, y1 + 3, f"{EX} 'Tech7': of sheet Zone Summary.", last)
    B.sign(ws, y1 + 6, 6)
    return ws


# ----------------------------------------------- the example technical.xlsx 'Tech ', 'Tech1', 'Tech2' (9-Nov-2026)
STAGES = ("init", "mid", "ult")


def _factor(B, char, j):
    """A ward's growth factor of stage j (0 base, 1 middle, 2 design) on the ward table's year: its character's in the
    growth table A of sheet Wards (Far-open there balanced to the projection), else the adopted projection's."""
    g = (getattr(B, "WARDS", None) or {}).get("grow") or {}
    if char in g:
        return f"Wards!${B.col(4 + j)}${g[char]}"
    f = B.info.get("projection") or {}
    r = f.get("town_ratio_from") or f.get("ratio_from")
    return f"{r[STAGES[j]]:.6f}" if r else "1"


def town_wards(B):
    """'Tech ' Ward wise population of the town (and the example's 'T' WARDWISE POPULATION AND AREA): every ward of
    the town's list (city_wards, imported on the page) - its population and households of the list's year, Eq. area,
    the 2011 census, density, character (the list's, else by the density limits) - grown to the base / middle / design
    years by its character's factors (households in proportion); the total, 10 % floating, the grand total."""
    T = B.info.get("town") or {}
    rows = T.get("rows") or []
    if not rows:
        return None
    PR = B.PR
    yr = T.get("year") or ""
    ws = B.sheet("Town Wards", f"WARD WISE POPULATION OF {str(T.get('city') or 'THE TOWN').upper()}", 15)
    for c, w in zip("ABCDEFGHIJKLMNO", (6, 8, 24, 12, 10, 11, 12, 11, 22, 12, 10, 12, 10, 12, 10)):
        ws.column_dimensions[c].width = w
    heads = ["Sl. No.", "W. No.", "Ward Name", f"Population {yr}", f"H.H. {yr}", "Eq. area (ha)", "Census 2011",
             f"Density {yr} (per ha)", "Character of ward"]
    for _, k in YEARS:
        heads += [f'="Population "&{PR[k]}', f'="H.H. "&{PR[k]}']
    B.header(ws, 5, heads)
    ws.row_dimensions[5].height = 45
    x0 = 6
    for i, w in enumerate(rows):
        x = x0 + i
        vals = [i + 1, w.get("no"), w.get("name"), w.get("pop"), w.get("hh"), w.get("area"), w.get("census"),
                f'=IFERROR(D{x}/F{x},"")', w.get("char") or "-"]
        for c, v in enumerate(vals, 1):
            B.cell(ws, x, c, v, fmt="#,##0.00" if c in (6, 8) else "#,##0" if c in (4, 5, 7) else None)
        for j in range(3):
            p, h = 10 + 2 * j, 11 + 2 * j
            B.cell(ws, x, p, f"=ROUND(D{x}*{_factor(B, w.get('char'), j)},0)", fmt="#,##0")
            B.cell(ws, x, h, f"=IFERROR(ROUND(E{x}*{B.col(p)}{x}/D{x},0),\"\")", fmt="#,##0")
    x1 = x0 + len(rows) - 1
    t = x1 + 1
    B.cell(ws, t, 3, "Total", bold=True)
    for c in (4, 5, 6, 7, 10, 11, 12, 13, 14, 15):
        B.cell(ws, t, c, f"=SUM({B.col(c)}{x0}:{B.col(c)}{x1})", fmt="#,##0", bold=True)
    B.cell(ws, t + 1, 3, f'="Add "&TEXT({PR["floating"]},"0%")&" floating and institutional population"')
    for c in (4, 10, 12, 14):
        B.cell(ws, t + 1, c, f"=ROUND({B.col(c)}{t}*{PR['floating']},0)", fmt="#,##0")
    B.cell(ws, t + 2, 3, "G TOTAL", bold=True)
    for c in (4, 5, 10, 11, 12, 13, 14, 15):
        B.cell(ws, t + 2, c, f"={B.col(c)}{t}" + (f"+{B.col(c)}{t + 1}" if c in (4, 10, 12, 14) else ""),
               fmt="#,##0", bold=True)
    _note(B, ws, t + 4, f"{EX} 'Tech ' (and 'T' WARDWISE POPULATION AND AREA): the town's list of wards ({T.get('city')}, "
                        f"imported on the page); each ward x the factors of its character (sheet Wards, A - Far-open "
                        "balanced to the adopted projection, so the town's wards add up to it; CPHEEO Manual on Water "
                        "Supply 2024 Part A Annexure 2.7), a ward without a character by the adopted method; households "
                        "in proportion; the character by the list, else by the density on the Eq. area.", 15)
    ws.freeze_panes = "D6"
    B.sign(ws, t + 7, 13)
    B.TOWN = {"total": t, "floating": t + 1, "grand": t + 2}
    return ws


def ward_projection(B):
    """'Tech1' WARD WISE POPULATION PROJECTION: the project's wards (the page's table; sheet Wards) - % covered,
    population, floating, total of the three years; then the town's population (T2) and the project's with floating,
    and the water demand of both (the WTP's load left out - user decision 9-Nov-2026: the source is tube wells)."""
    WS = getattr(B, "WARDS", None) or {}
    wt = B.info.get("ward_table")
    if not wt or not WS.get("x0"):
        return None
    PR, T1 = B.PR, B.T1
    ws = B.sheet("Ward Proj", "WARD WISE POPULATION PROJECTION", 11)
    last = _group_head(B, ws, 5, [("Ward No.", 1), ("% of ward covered", 1), ("Population", 3),
                                  (f'="Floating Population @"&TEXT({PR["floating"]},"0%")', 3), ("Total Projected Population", 3)])
    for c, w in zip("ABCDEFGHIJK", (10, 11, 12, 12, 12, 11, 11, 11, 12, 12, 12)):
        ws.column_dimensions[c].width = w
    y0 = 8
    for i in range(WS["n"]):
        y, x = y0 + i, WS["x0"] + i
        B.cell(ws, y, 1, f"=Wards!C{x}")
        B.cell(ws, y, 2, f"=Wards!I{x}", fmt="0%")
        for j, c in enumerate("KLM"):
            B.cell(ws, y, 3 + j, f"=Wards!{c}{x}", fmt="#,##0")
            B.cell(ws, y, 6 + j, f"=ROUND({B.col(3 + j)}{y}*{PR['floating']},0)", fmt="#,##0")
            B.cell(ws, y, 9 + j, f"={B.col(3 + j)}{y}+{B.col(6 + j)}{y}", fmt="#,##0")
    y1 = y0 + WS["n"] - 1
    t = y1 + 1
    B.cell(ws, t, 1, "Total", bold=True)
    for c in range(3, last + 1):
        B.cell(ws, t, c, f"=SUM({B.col(c)}{y0}:{B.col(c)}{y1})", fmt="#,##0", bold=True)
    r = t + 2
    TW, town = getattr(B, "TOWN", None), B.info.get("town") or {}
    yrs = [PR["base_year"], PR["mid_year"], PR["design_year"]]

    def table(r, title, rows):
        """rows: [(description, year, population formula)] -> population, floating, total."""
        B.cell(ws, r, 1, title, bold=True)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=last)
        B.header(ws, r + 1, ["S. No.", "Description", "Year", "Population", f'="Floating Population ("&TEXT({PR["floating"]},"0%")&")"', "Total"])
        for i, (d, y, p) in enumerate(rows):
            z = r + 2 + i
            for c, v in enumerate([i + 1, d, y, p, f"=ROUND(D{z}*{PR['floating']},0)", f"=D{z}+E{z}"], 1):
                B.cell(ws, z, c, v, fmt="#,##0" if c >= 4 else None)
        return r + 2 + len(rows)
    stage = (("Initial stage", 0), ("Middle stage", 1), ("Design stage", 2))
    town_name = town.get("city") or "the town"
    rp = {}
    if TW:
        B.cell(ws, r, 1, f"TABLE SHOWING POPULATION OF {str(town_name).upper()}", bold=True)
        r = table(r + 1, f"Total population of {town_name}",
                  [("Present stage", town.get("year") or "", f"='Town Wards'!D{TW['total']}")] +
                  [(d, f"={yrs[j]}", f"='Town Wards'!{B.col(10 + 2 * j)}{TW['total']}") for d, j in stage]) + 1
        rp["town"] = r - 4                                     # its initial-stage row: r - 1 - 3
    r = table(r, "Total population of the project area",
              [(d, f"={yrs[j]}", f"={B.col(3 + j)}{t}") for d, j in stage]) + 1
    rp["proj"] = r - 4
    # the water demand (as sheet T1: the domestic with the distribution losses, floating without, fire)
    B.cell(ws, r, 1, "TABLE SHOWING WATER DEMAND", bold=True)
    r += 1
    heads = ["S. No.", "Description", "Year",
             f'="Demand (in KLD) (@"&TEXT({PR["lpcd"]}*(1+{PR["losses"]}),"0.0")&" LPCD including "&TEXT({PR["losses"]},"0%")&" for losses)"',
             f'="Floating Demand (@"&{PR["floating_lpcd"]}&" LPCD) (in KLD)"', "Fire Demand (KLD)", "Total Demand (in KLD)"]
    fire_t = f"T1!${T1['fire_col']}${T1['total']}"
    for key, title in (("town", f"Water demand for {town_name}"), ("proj", "Water demand for the project area")):
        if key not in rp:
            continue
        p0 = rp[key]
        B.cell(ws, r, 1, title, bold=True)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=last)
        B.header(ws, r + 1, heads)
        ws.row_dimensions[r + 1].height = 45
        for i, (d, j) in enumerate(stage):
            z, src = r + 2 + i, p0 + i
            fire = (f"=100*SQRT(D{p0 + 2}/1000)" if key == "town" else f"={fire_t}")
            for c, v in enumerate([i + 1, d, f"=C{src}", f"=D{src}*{PR['lpcd']}*(1+{PR['losses']})/1000",
                                   f"=E{src}*{PR['floating_lpcd']}/1000", fire, f"=D{z}+E{z}+F{z}"], 1):
                B.cell(ws, z, c, v, fmt="#,##0.00" if c >= 4 else None)
        r += 6
    _note(B, ws, r, f"{EX} 'Tech1': the project's wards of sheet Wards (each by its character, or the adopted method); "
                    "the town's population of sheet Town Wards; the demand as sheet T1 - the town's fire 100 sqrt(P) of "
                    "its design-year population (thousands, CPHEEO Table 2.7), the project's the fire of sheet T1; the "
                    "load on a WTP not shown (the source is tube wells).", last)
    B.sign(ws, r + 3, 9)
    return ws


def zone_population(B):
    """'Tech2' ZONE WISE POPULATION: each operation zone - the wards in it (their contribution: the share of the ward's
    design-year population in the zone), population, floating and total of the three years; a zone with no ward on
    the map one row of its own (sheet T1)."""
    T = B.info.get("tech") or {}
    W = T.get("wards") or []
    PR, T1 = B.PR, B.T1
    ws = B.sheet("Zone Pop", "ZONE WISE POPULATION", 11)
    last = _group_head(B, ws, 5, [("Ward No.", 1), ("Contribution (in %age)", 1), ("Population", 3),
                                  (f'="Floating Population @"&TEXT({PR["floating"]},"0%")', 3), ("Total Population", 3)])
    for c, w in zip("ABCDEFGHIJK", (14, 13, 12, 12, 12, 11, 11, 11, 12, 12, 12)):
        ws.column_dimensions[c].width = w
    r = 8
    for t in B.T3:
        zn = t["zone"]["name"]
        _block_title(B, ws, r, f"Operation zone {zn}", last)
        _numbers(B, ws, r + 1, last)
        y0 = y = r + 2
        parts = [(w, w["oz"][zn]) for w in W if zn in w["oz"]]
        for w, p in parts:
            no = str((w.get("table") or {}).get("no") or w["name"])
            B.cell(ws, y, 1, no)
            B.cell(ws, y, 2, round(p["ult"] / max(w["pop"]["ult"], 1), 4), fmt="0.0%")
            for j, k in enumerate(STAGES):
                B.cell(ws, y, 3 + j, p[k], fmt="#,##0")
            y += 1
        if not parts:                                          # no ward on the map: the zone itself (sheet T1)
            x2 = T1["rows"][zn]
            B.cell(ws, y, 1, "Whole zone")
            B.cell(ws, y, 2, "-")
            for j, c in enumerate("DEF"):
                B.cell(ws, y, 3 + j, f"=T1!{c}{x2}", fmt="#,##0")
            y += 1
        for x in range(y0, y):
            for j in range(3):
                B.cell(ws, x, 6 + j, f"=ROUND({B.col(3 + j)}{x}*{PR['floating']},0)", fmt="#,##0")
                B.cell(ws, x, 9 + j, f"={B.col(3 + j)}{x}+{B.col(6 + j)}{x}", fmt="#,##0")
        B.cell(ws, y, 1, "Total", bold=True)
        for c in range(3, last + 1):
            B.cell(ws, y, c, f"=SUM({B.col(c)}{y0}:{B.col(c)}{y - 1})", fmt="#,##0", bold=True)
        r = y + 2
    _note(B, ws, r, f"{EX} 'Tech2': the wards on the map in each operation zone (by their junctions), the contribution "
                    "the share of the ward's design-year population in the zone; a zone with no ward on the map from "
                    "sheet T1.", last)
    B.sign(ws, r + 3, 9)
    return ws


def write(B):
    """The sheets above; returns their (pre-rename) names, in order."""
    made = []
    for f in (wards, town_wards, ward_projection, zone_population, dmas, requirement, mass_balance, static_head,
              pipe_table, dma_demand, zone_summary, oht_details, dma_household, zone_household):
        ws = f(B)
        if ws is not None:
            made.append(ws.title)
    return made
