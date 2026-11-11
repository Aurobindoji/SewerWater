"""The abstracts, Form J, O&M, economics and front sheets of the water DPR workbook (dpr.py), in the format of the Elmwood
water estimate (user decision 26-Oct-2026):

    abstracts(B)       ABS Com (civil + E&M), ABS Civil, Breakup, Form J Com. (comprehensive), Form J Civil
    om_economics(B)    Repair on Works, A.Ex. Staff, Chemical, Electicity, Cess, Ann. Expe, Income, Economics,
                       5 Yr O&M Civil, 5Yr O&M Com
    checklist(B)       Checklist (the other front pages: dpr_front.py)

The parts of the project the design does not give (WTP, feeder main) are yellow lump sums (0 lakh) in ABS Com, to be
filled in; the civil lines in the order of the Riverside water DPR's abstract, the pump houses, site development,
staff quarters, GW recharge, MCS, panel rooms and repairs of OHTs from their estimates (dpr_civil.py); the E&M works,
power connections and their O&M from sheets EM and EM O&M (dpr_em.py). B = dpr.Book after the network, civil and E&M
sheets.
"""
from .dpr import q, size_key

HH_ROW = 10                 # sheet Income: the row of the household connections of each stage
OMC_CIVIL, OMC_TOTAL = 13, 23   # sheet 5Yr O&M Com: the civil works' total, the total (Riverside water DPR p57)
STAGES = (("Initial Stage", "base_year"), ("Middle Stage", "mid_year"), ("Ultimate Stage", "design_year"))
# breakup columns (Elmwood 'Breakup'): pipe line, building, RCC, machinery, miscellaneous
BREAK = ["Pipe line works", "Building works", "R.C.C. works", "Machinery works", "Miscellaneous"]
LUMP_BREAK = {"Water Treatment Plant": "R.C.C. works", "Feeder Main and appurtenant works": "Pipe line works"}


def _stage_heads(B, ws, r, c0=3):
    for j, (lab, key) in enumerate(STAGES):
        B.cell(ws, r, c0 + j, f'="{lab} Year "&{B.PR[key]}', bold=True).alignment = B.center


def signatures(B, ws, r, em=False):
    """The signatures under a Form J as the user's example (form j combined.xlsx, 7-Nov-2026): Prepared By (the
    Assistant Engineers) and Checked by (the Computers), then the Executive Engineers and Recommended By (the
    Superintending Engineers), Approved By the Chief Engineer across; each a block of name, post, office, U.P. Jal
    Nigam (Urban), town - civil, and E&M beside it (em). The texts from sheet Project."""
    from openpyxl.styles import Alignment
    PR, n = B.PR, ws.max_column
    k = 4 if em else 2                                   # blocks across: [civil, E&M] x [left, right]
    rest = list(range(3, n + 1))                         # the first block: S. No. and description
    per, extra = divmod(len(rest), k - 1)
    groups, c0 = [(1, 2)], 3
    for i in range(k - 1):
        w = per + (1 if i < extra else 0)
        groups.append((c0, c0 + w - 1))
        c0 += w
    left, right = (groups[:2], groups[2:]) if em else (groups[:1], groups[1:])

    def put(row, g, v, bold=False):
        c = ws.cell(row, g[0], v)
        if bold:
            c.font = B.bold
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        if g[1] > g[0]:
            ws.merge_cells(start_row=row, start_column=g[0], end_row=row, end_column=g[1])

    def block(row, g, key, post, office, place):
        put(row, g, f'=IF(""&{PR[key]}="","","("&{PR[key]}&")")', True)      # a name not given: blank, not ()
        put(row + 1, g, post)
        put(row + 2, g, f'=""&{PR[office]}')
        put(row + 3, g, "U.P. Jal Nigam (Urban)")
        put(row + 4, g, f'=""&{PR[place]}')
    span = lambda gs: (gs[0][0], gs[-1][1])
    put(r, span(left), "Prepared By", True)
    put(r, span(right), "Checked by", True)
    people = [("ae", "Assistant Engineer", "office", "place")] + \
        ([("ae_em", "Assistant Engineer", "office_em", "place")] if em else [])
    checks = [("computer", "Computer", "office", "place")] + ([("computer_em", "Computer", "office_em", "place")]
                                                              if em else [])
    for g, p in zip(left + right, people + checks):
        block(r + 3, g, *p)
    r += 9
    put(r, span(right), "Recommended By", True)
    ees = [("ee", "Executive Engineer", "office", "place")] + \
        ([("ee_em", "Executive Engineer", "office_em", "place")] if em else [])
    ses = [("se", "Superintending Engineer", "circle", "place")] + \
        ([("se_em", "Superintending Engineer", "circle_em", "place_em_circle")] if em else [])
    for g, p in zip(left + right, ees + ses):
        block(r + 3, g, *p)
    r += 9
    whole = (1, n)
    put(r, whole, "Approved By", True)
    put(r + 4, whole, f'=IF(""&{PR["ce"]}="","","("&{PR["ce"]}&")")', True)
    put(r + 5, whole, f'="Chief Engineer"&IF(""&{PR["zone"]}="",""," ("&{PR["zone"]}&")")')
    put(r + 6, whole, f'="U.P. Jal Nigam (Urban)"&IF(""&{PR["place_zone"]}="","",", "&{PR["place_zone"]})')
    return r + 7


def signatures_em(B, ws, r):
    """The text under Form J E&M as the Riverside water DPR's page (p51 of 790, user 7-Nov-2026; no names - the
    officers sign there): PREPARED BY / CHECKED BY / CHECKED BY over Assistant Engineer / Computer / Executive Engineer,
    the E&M division across; Recommended By the Superintending Engineer (E&M) with the circle, Approved By the Chief
    Engineer with the zone. The offices and towns from sheet Project, a blank one left out."""
    from openpyxl.styles import Alignment
    PR, n = B.PR, ws.max_column
    thirds = [(1, 2), (3, n - 1), (n, n)]                # under the description, the amounts, the last amount
    halves = [(1, 2), (3, n)]

    def put(row, g, v, bold=False):
        c = ws.cell(row, g[0], v)
        if bold:
            c.font = B.bold
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        if g[1] > g[0]:
            ws.merge_cells(start_row=row, start_column=g[0], end_row=row, end_column=g[1])
    join = lambda *parts: "=_xlfn.TEXTJOIN(\", \",TRUE," + ",".join(parts) + ")"
    for g, head, post in zip(thirds, ("PREPARED BY", "CHECKED BY", "CHECKED BY"),
                             ("Assistant Engineer", "Computer", "Executive Engineer")):
        put(r, g, head, True)
        put(r + 3, g, post, True)
    put(r + 4, (1, n), "=UPPER(" + join(PR["office_em"], '"U.P. Jal Nigam (Urban)"', PR["place"])[1:] + ")")
    r += 6
    put(r, halves[0], "Recommended By", True)
    put(r, halves[1], "Approved By", True)
    put(r + 3, halves[0], "Superintending Engineer (E&M)", True)
    put(r + 4, halves[0], join(PR["circle_em"], '"U.P. Jal Nigam (Urban)"', PR["place_em_circle"]))
    put(r + 3, halves[1], f'="Chief Engineer"&IF(""&{PR["zone"]}="",""," ("&{PR["zone"]}&")")', True)
    put(r + 4, halves[1], join('"U.P. Jal Nigam (Urban)"', PR["place_zone"]))
    ws.row_dimensions[r + 4].height = 32
    return r + 5


# ------------------------------------------------------------------------------------------------------------ abstracts
def abstracts(B):
    """The abstracts of cost and the Forms J: ABS Com, ABS Civil, Breakup, Form J Com., Form J Civil, Form J E&M."""
    _abs_com(B)
    _abs_civil(B)
    _breakup(B)
    _form_j_com(B)
    _form_j_civil(B)
    form_j_em(B)


def _abs_com(B):
    """Sheet ABS Com: the civil and the E&M works -> B.AC, its cells by what they hold."""
    S = B.S
    L = S["lump_sums"]
    ws = B.sheet("ABS Com", "COMBINED GENERAL ABSTRACT OF COST", 4)
    B.header(ws, 5, ["Sl. No.", "Description of work", "Qty.", "Total (Rs. in lakh)", "Breakup head"],
             [7, 70, 22, 18, 18])
    x = 6
    B.cell(ws, x, 1, "A")
    B.cell(ws, x, 2, "CIVIL WORKS", bold=True)
    x += 1
    civ0 = x
    rows = []                                                   # (row, breakup head)
    n_new, n_oz = B.OHT["n"], len(B.T3)
    km = f'=ROUND({B.SDS["pipe_total"]}/1000,2)&" Km"'
    tw = lambda c: f"SUM(TW!{c}6:{c}{5 + n_oz})"
    rm = getattr(B, "RM", None) or {}
    C = B.CIV
    # the civil works in the order of the Riverside water DPR's abstract (p45, user decision 6-Nov-2026); a part the
    # design gives no estimate of: a yellow lump sum (0)
    lines = [("Pump house cum chlorination room", f'={tw("L")}&" New + "&{tw("C")}&" Repair"', f"={C['ph']}",
              "Building works"),
             ("Construction of new RCC overhead tanks", f"{n_new} New", f"={B.OHT['lakh']}", "R.C.C. works"),
             ("Repairing of existing RCC overhead tanks", f"{B.OHT.get('n_repair', 0)} Repair",
              f"={B.OHT['repair']}" if B.OHT.get("repair") else "=0", "R.C.C. works"),
             ("Rising Main and appurtenant works", f"={rm['km']}" if rm else "1 Job",
              f"={rm['lakh']}" if rm else None, "Pipe line works"),
             ("Distribution network and appurtenant works with house water tap connections", km, f"={B.DS['lakh']}",
              "Pipe line works"),
             ("Site development works (boundary wall, gate, earth filling, internal road, landscaping and boundary wall "
              "repairing works)", "1 Job", f"={C['bw']}", "Miscellaneous"),
             # the quantities as the Riverside water DPR p45 ("7 New", "15 Nos", "11 Nos", "7 No."; 7-Nov-2026)
             ("Construction of new CWRs", f'={C["cwr_n"]}&" New"', f"={B.CWR['lakh']}", "R.C.C. works"),
             ("Construction of ground water recharge mechanism", f'={C["gwr_n"]}&" Nos"', f"={C['gwr']}",
              "Miscellaneous"),
             ("Construction of MCS building", f'={C["mcs_n"]}&" Nos"', f"={C['mcs']}", "Building works"),
             ("Construction of staff quarters", f'={C["sq_n"]}&" Nos"', f"={C['sq']}", "Building works"),
             ("Construction of HT panel room, LT panel room and booster pump room", f'=({C["rooms_n"]})&" No."',
              f"={C['rooms']}", "Building works")]
    lines += [(lab, "1 Job", None, LUMP_BREAK.get(lab, "Miscellaneous")) for lab in L["civil"]]
    for i, (lab, qty, val, head) in enumerate(lines, 1):
        B.cell(ws, x, 1, i)
        B.cell(ws, x, 2, lab).alignment = B.wrap
        B.cell(ws, x, 3, qty)
        B.cell(ws, x, 4, val if val else 0, fmt="#,##0.00", inp=not val)
        ws.cell(x, 5, head).font = B.italic
        rows.append((x, head))
        x += 1
    B.cell(ws, x, 2, "Total (Civil Works)", bold=True)
    B.cell(ws, x, 4, f"=SUM(D{civ0}:D{x - 1})", fmt="#,##0.00", bold=True)
    civ = x
    x += 1
    B.cell(ws, x, 1, "B")
    B.cell(ws, x, 2, "E & M WORKS", bold=True)
    x += 1
    em0 = x
    for i, (lab, cell, head, qty) in enumerate(B.EM["parts"], 1):    # sheet EM (dpr_em.py, R3 format)
        B.cell(ws, x, 1, i)
        B.cell(ws, x, 2, lab)
        B.cell(ws, x, 3, qty)
        B.cell(ws, x, 4, f"={cell}", fmt="#,##0.00")
        ws.cell(x, 5, head).font = B.italic
        rows.append((x, head))
        x += 1
    B.cell(ws, x, 2, "Total (E&M Works)", bold=True)
    B.cell(ws, x, 4, f"=SUM(D{em0}:D{x - 1})", fmt="#,##0.00", bold=True)
    em = x
    B.cell(ws, x + 1, 2, "Total (A + B)", bold=True)
    B.cell(ws, x + 1, 4, f"=D{civ}+D{em}", fmt="#,##0.00", bold=True)
    B.cell(ws, x + 2, 2, "New power connections with transmission lines (sheet EM)")
    B.cell(ws, x + 2, 3, B.EM["power_qty"])
    B.cell(ws, x + 2, 4, f"={B.EM['power']}", fmt="#,##0.00")
    ws.cell(x + 4, 2, "Yellow: parts of the project not made from the network design (phase 1) - fill in (Rs lakh), "
                      "or replace by their estimates.").font = B.italic
    B.sign(ws, x + 6, 3)
    B.AC = {"civil": f"'ABS Com'!$D${civ}", "em": f"'ABS Com'!$D${em}", "ab": f"'ABS Com'!$D${x + 1}",
            "power": f"'ABS Com'!$D${x + 2}", "rows": rows, "civ_rows": (civ0, civ - 1)}


def _abs_civil(B):
    """Sheet ABS Civil: the civil rows of ABS Com."""
    civ0, civ = B.AC["civ_rows"][0], B.AC["civ_rows"][1] + 1
    wc = B.sheet("ABS Civil", "GENERAL ABSTRACT OF COST (CIVIL)", 4)
    B.header(wc, 5, ["Sl. No.", "Description of work", "Qty.", "Total (Rs. in lakh)"], [7, 70, 22, 18])
    y = 6
    for r in range(civ0, civ):
        for c in range(1, 5):
            B.cell(wc, y, c, f"='ABS Com'!{B.col(c)}{r}", fmt="#,##0.00" if c == 4 else None)
        y += 1
    B.cell(wc, y, 2, "Total", bold=True)
    B.cell(wc, y, 4, f"=ROUND(SUM(D6:D{y - 1}),2)", fmt="#,##0.00", bold=True)
    B.sign(wc, y + 3, 3)
    B.AC["civil_abs"] = f"'ABS Civil'!$D${y}"


def _breakup(B):
    """Sheet Breakup: every row of ABS Com under its head -> B.BR, the totals of the heads."""
    rows = B.AC["rows"]
    wb_ = B.sheet("Breakup", "BREAKUP OF COST", 8)
    B.header(wb_, 5, ["Sl. No.", "Description of works", "Total (Rs. lakh)"] + [f"{h} (Rs. lakh)" for h in BREAK],
             [7, 60, 14, 14, 14, 14, 14, 14])
    y = 6
    for i, (r, head) in enumerate(rows, 1):
        B.cell(wb_, y, 1, i)
        B.cell(wb_, y, 2, f"='ABS Com'!B{r}")
        B.cell(wb_, y, 3, f"='ABS Com'!D{r}", fmt="#,##0.00")
        for j, h in enumerate(BREAK):
            B.cell(wb_, y, 4 + j, f"=C{y}" if h == head else None, fmt="#,##0.00")
        y += 1
    B.cell(wb_, y, 2, "Total (works)", bold=True)
    for c in range(3, 9):
        B.cell(wb_, y, c, f"=SUM({B.col(c)}6:{B.col(c)}{y - 1})", fmt="#,##0.00", bold=True)
    B.sign(wb_, y + 3, 6)
    B.BR = {h: f"Breakup!${B.col(4 + j)}${y}" for j, h in enumerate(BREAK)}


def _form_j_com(B):
    """Sheet Form J Com. (comprehensive) -> B.FJ, its cells by what they hold."""
    fj = B.S["form_j"]
    fo = B.sheet("Form J Com.", 'FORM - "J" (Comprehensive)', 5 + len(fj["shares"]))
    B.header(fo, 5, ["S. No.", "Description", "Amount (Rs. in lakh)", "Percentage %", "Total (Rs. in lakh)"] +
             [f"{s[0]} (Rs. lakh)" for s in fj["shares"]], [7, 50, 16, 12, 16, 15, 15, 15])
    sc = [B.col(6 + j) for j in range(len(fj["shares"]))]
    for j, s in enumerate(fj["shares"]):
        B.cell(fo, 6, 6 + j, s[1], fmt="0%", inp=True)

    def split(x_):
        for c in sc:
            fo[f"{c}{x_}"] = f"=$E${x_}*{c}$6"
            fo[f"{c}{x_}"].number_format = "#,##0.00"

    lines = [(1, "Total cost of work (Civil)", f"={B.AC['civil']}", 1, "=ROUND(C{x}*D{x},2)"),
             (2, "Total cost of work (E&M)", f"={B.AC['em']}", 1, "=ROUND(C{x}*D{x},2)"),
             (3, "Sub Total (1 + 2)", None, None, "=E{a}+E{b}"),
             (4, "Contingency (lump sum)", fj["contingency_lakh"], None, "=C{x}"),     # DPR p44 (6-Nov-2026)
             (5, "Sub Total (3 + 4)", None, None, "=E{p2}+E{p}"),
             (6, "Less due to efficiency", "=E{p}", fj["efficiency_less"], "=ROUND(C{x}*D{x},2)"),
             (7, "Sub Total (5 - 6)", None, None, "=E{p2}-E{p}"),
             (8, "Labour cess", "=E{p}", fj["labour_cess"], "=ROUND(C{x}*D{x},2)"),
             (9, "GST", "=E{p2}", fj["gst"], "=ROUND(C{x}*D{x},2)")]
    x = 7
    rowno = {}
    for no, lab, amt, pct, tot in lines:
        p, p2 = x - 1, x - 2
        fmt_ = dict(x=x, p=p, p2=p2, a=rowno.get(1), b=rowno.get(2))
        B.cell(fo, x, 1, no)
        B.cell(fo, x, 2, lab, bold=amt is None)
        if isinstance(amt, (int, float)):                  # a lump sum (Rs lakh, yellow)
            B.cell(fo, x, 3, amt, fmt="#,##0.00", inp=True)
        elif amt:
            B.cell(fo, x, 3, amt.format(**fmt_), fmt="#,##0.00")
        if pct is not None:
            B.cell(fo, x, 4, pct, fmt="0.00%", inp=no > 2)
        B.cell(fo, x, 5, tot.format(**fmt_), fmt="#,##0.00", bold=amt is None)
        split(x)
        rowno[no] = x
        x += 1
    net = rowno[7]
    fo.cell(rowno[9], 3).value = f"=E{net}"
    B.cell(fo, x, 1, 10)
    B.cell(fo, x, 2, "Centage (on 7, by slab)", bold=True)
    x += 1
    c0, lo = x, 0
    for upto, pct in fj["centage"]:
        lab = (f"Above {lo / 100:g} Cr" if upto is None else
               (f"{lo / 100:g} Cr to {upto / 100:g} Cr" if lo else f"Up to {upto / 100:g} Cr"))
        B.cell(fo, x, 2, lab)
        B.cell(fo, x, 3, f"=MAX(0,$E${net}-{lo})" if upto is None else f"=MAX(0,MIN($E${net},{upto})-{lo})",
               fmt="#,##0.00")
        B.cell(fo, x, 4, pct, fmt="0.00%", inp=True)
        B.cell(fo, x, 5, f"=ROUND(C{x}*D{x},2)", fmt="#,##0.00")
        lo = upto or lo
        x += 1
    B.cell(fo, x, 2, "Total Centage", bold=True)
    B.cell(fo, x, 5, f"=SUM(E{c0}:E{x - 1})", fmt="#,##0.00", bold=True)
    fo[f"{sc[1]}{x}"] = f"=E{x}"                                    # centage: Govt. of U.P. (Elmwood M19:M23)
    cent = x
    x += 1
    for no, lab, f in ((11, "Sub Total (8 + 9 + 10)", f"=E{rowno[8]}+E{rowno[9]}+E{cent}"),
                       (12, "Sub Total (7 + 11)", f"=E{net}+E{x}")):
        B.cell(fo, x, 1, no)
        B.cell(fo, x, 2, lab, bold=True)
        B.cell(fo, x, 5, f, fmt="#,##0.00", bold=True)
        x += 1
    s11, s12 = x - 2, x - 1
    for c in sc:
        fo[f"{c}{s11}"] = f"={c}{rowno[8]}+{c}{rowno[9]}+{c}{cent}"
        fo[f"{c}{s12}"] = f"={c}{net}+{c}{s11}"
    B.cell(fo, x, 1, 13)
    B.cell(fo, x, 2, "Power transmission line")
    B.cell(fo, x, 3, f"={B.AC['power']}", fmt="#,##0.00")
    B.cell(fo, x, 4, 1, fmt="0%")
    B.cell(fo, x, 5, f"=C{x}*D{x}", fmt="#,##0.00")
    split(x)
    pw = x
    x += 1
    B.cell(fo, x, 1, 14)
    B.cell(fo, x, 2, "Sub Total (12 + 13)", bold=True)
    B.cell(fo, x, 5, f"=E{s12}+E{pw}", fmt="#,##0.00", bold=True)
    for c in sc:
        fo[f"{c}{x}"] = f"={c}{s12}+{c}{pw}"
    tot = x
    x += 1
    B.cell(fo, x, 1, 15)
    B.cell(fo, x, 2, "Total O&M cost for 05 years (Civil + E&M) with 18 % GST & labour cess")
    B.cell(fo, x, 3, f"='5Yr O&M Com'!D{OMC_TOTAL}", fmt="#,##0.00")
    B.cell(fo, x, 4, 1, fmt="0%")
    B.cell(fo, x, 5, f"=C{x}*D{x}", fmt="#,##0.00")
    fo[f"{sc[-1]}{x}"] = f"=E{x}"                                    # O&M: the U.L.B (Elmwood O28)
    omx = x
    x += 1
    B.cell(fo, x, 2, "GRAND TOTAL (14 + 15)", bold=True)
    B.cell(fo, x, 5, f"=E{tot}+E{omx}", fmt="#,##0.00", bold=True)
    for c in sc:
        fo[f"{c}{x}"] = f"=SUM({c}{tot},{c}{omx})"
    for row in fo.iter_rows(min_row=7, max_row=x, min_col=6, max_col=5 + len(sc)):
        for cell in row:
            cell.number_format, cell.border = "#,##0.00", B.box
    grand = x
    signatures(B, fo, x + 3, em=True)
    B.FJ = {"net": f"'Form J Com.'!$E${net}", "centage": f"'Form J Com.'!$E${cent}", "cont": f"'Form J Com.'!$E${rowno[4]}",
            "sub3": f"'Form J Com.'!$E${rowno[3]}", "total": f"'Form J Com.'!$E${tot}",
            "grand": f"'Form J Com.'!$E${grand}", "om": f"'Form J Com.'!$E${omx}"}


def _form_j_civil(B):
    """Sheet Form J Civil."""
    fj = B.S["form_j"]
    fc = B.sheet("Form J Civil", 'FORM - "J" (Civil works)', 5)
    B.header(fc, 5, ["Sl. No.", "Description", "Amount (Rs. in lakh)", "Percentage %", "Total (Rs. in lakh)"],
             [7, 56, 16, 12, 16])
    rows_ = [(1, "Total cost of work", f"={B.AC['civil_abs']}", 1, "=ROUND(C{x}*D{x},2)"),
             (2, "Contingency (lump sum, Form J Com.)", f"={B.FJ['cont']}", None, "=C{x}"),
             (3, "Sub Total (1 + 2)", None, None, "=E{p2}+E{p}"),
             (4, "Less due to efficiency", "=E{p}", fj["efficiency_less"], "=C{x}*D{x}"),
             (5, "Sub Total (3 - 4)", None, None, "=E{p2}-E{p}"),
             (6, "Labour cess", "=E{p}", fj["labour_cess"], "=C{x}*D{x}"),
             (7, "GST", "=E{p2}", fj["gst"], "=C{x}*D{x}")]
    x = 6
    rn = {}
    for no, lab, amt, pct, tot_ in rows_:
        fm = dict(x=x, p=x - 1, p2=x - 2)
        B.cell(fc, x, 1, no)
        B.cell(fc, x, 2, lab, bold=amt is None)
        if amt:
            B.cell(fc, x, 3, amt.format(**fm), fmt="#,##0.00")
        if pct is not None:
            B.cell(fc, x, 4, pct, fmt="0.00%")
        B.cell(fc, x, 5, tot_.format(**fm), fmt="#,##0.00", bold=amt is None)
        rn[no] = x
        x += 1
    fc.cell(rn[7], 3).value = f"=E{rn[5]}"
    B.cell(fc, x, 1, 8)
    B.cell(fc, x, 2, "Centage (share of the comprehensive centage: civil / (civil + E&M))")
    B.cell(fc, x, 5, f"=IFERROR({B.FJ['centage']}/{B.FJ['sub3']}*C{rn[1]},0)", fmt="#,##0.00")
    ce = x
    x += 1
    B.cell(fc, x, 1, 9)
    B.cell(fc, x, 2, "Sub Total (5 + 6 + 7)", bold=True)
    B.cell(fc, x, 5, f"=E{rn[5]}+E{rn[6]}+E{rn[7]}", fmt="#,##0.00", bold=True)
    x += 1
    B.cell(fc, x, 1, 10)
    B.cell(fc, x, 2, "Sub Total (8 + 9)", bold=True)
    B.cell(fc, x, 5, f"=E{ce}+E{x - 1}", fmt="#,##0.00", bold=True)
    x += 1
    B.cell(fc, x, 1, 11)
    B.cell(fc, x, 2, "O&M cost for 05 years (civil) with 18 % GST, 1 % labour cess & 7 % centage")
    B.cell(fc, x, 5, f"='5Yr O&M Com'!D{OMC_CIVIL}", fmt="#,##0.00")
    x += 1
    B.cell(fc, x, 2, "Grand Total", bold=True)
    B.cell(fc, x, 5, f"=E{x - 2}+E{x - 1}", fmt="#,##0.00", bold=True)
    signatures(B, fc, x + 3)


def form_j_em(B):
    """Form J (E&M works) of the Riverside water DPR p48 (user decision 6-Nov-2026): the E&M works of ABS Com less the
    departmental proficiency, centage on that, labour cess and GST on it, the new power connections; the 5 years' O&M
    without electricity (with GST) and the electricity (sheet EM O&M)."""
    fj = B.S["form_j"]
    ws = B.sheet("Form J E&M", 'FORM - "J" (E&M WORKS)', 5)
    B.header(ws, 5, ["Sl. No.", "Description of item", "Amount (Rs. in lakh)", "Percentage", "Amount (Rs. in lakh)"],
             [7, 60, 16, 12, 20])
    rows = [("A", "Total cost of works", f"={B.AC['em']}", 1, "=ROUND(C{x}*D{x},2)"),
            ("2", "Sub Total", None, None, "=E{a}"),
            ("3", "Departmental proficiency on sub total", "=E{a}", fj["efficiency_less"], "=ROUND(C{x}*D{x},2)"),
            ("B", "Total work cost", None, None, "=E{a}-E{p}"),
            ("4", "Centage on total", "=E{p}", fj["em_centage"], "=ROUND(C{x}*D{x},2)"),
            ("C", "Total capital cost", None, None, "=E{p2}+E{p}"),
            ("5", "Labour cess on the total work cost (B)", "=E{b}", fj["labour_cess"], "=ROUND(C{x}*D{x},2)"),
            ("6", "GST on the total work cost (B)", "=E{b}", fj["gst"], "=ROUND(C{x}*D{x},2)"),
            ("D", "New power connections", f"={B.AC['power']}", 1, "=ROUND(C{x}*D{x},2)"),
            ("7", "Total cost of scheme (C + 5 + 6 + D)", None, None, "=E{c}+E{c1}+E{c2}+E{d}"),
            ("8", "5 year O&M works without electricity charges (with GST)", None, None, f"={B.EMOM['works']}"),
            ("9", "5 year electricity charges during O&M", None, None, f"={B.EMOM['elec']}"),
            ("10", "Total O&M cost including electricity charges", None, None, "=E{o8}+E{o9}"),
            ("11", "Grand total (project cost + 5 year O&M cost)", None, None, "=E{t7}+E{o10}")]
    x0 = 6
    at = {no: x0 + i for i, (no, *_) in enumerate(rows)}
    for i, (no, lab, amt, pct, tot) in enumerate(rows):
        x = x0 + i
        f = dict(x=x, p=x - 1, p2=x - 2, a=at["A"], b=at["B"], c=at["C"], c1=at["5"], c2=at["6"], d=at["D"],
                 o8=at["8"], o9=at["9"], t7=at["7"], o10=at["10"])
        big = no in ("B", "C", "7", "10", "11")
        B.cell(ws, x, 1, no)
        B.cell(ws, x, 2, lab, bold=big)
        if amt:
            B.cell(ws, x, 3, amt.format(**f), fmt="#,##0.00")
        if pct is not None:
            B.cell(ws, x, 4, pct, fmt="0.0%", inp=no in ("3", "4", "5", "6"))
        B.cell(ws, x, 5, tot.format(**f), fmt="#,##0.00", bold=big)
    x = x0 + len(rows) + 1
    c = ws.cell(x, 2, "Riverside water DPR p48 (Construction Division E&M): proficiency, centage, labour cess and GST "
                      "of the E&M works; the works and power connections of sheet EM, the O&M of sheet EM O&M.")
    c.font, c.alignment = B.italic, B.wrap
    ws.merge_cells(start_row=x, start_column=2, end_row=x, end_column=5)    # within the page
    ws.row_dimensions[x].height = 30
    signatures_em(B, ws, x + 3)
    B.FJE = {"total": f"'Form J E&M'!$E${at['7']}", "grand": f"'Form J E&M'!$E${at['11']}"}


# ------------------------------------------------------------------------------------------------------------ O&M, economics
REP_MACH = 9                    # row of the machinery works in sheet Repair on Works


def om_economics(B):
    """The annual O&M and the economics: Repair on Works, A.Ex. Staff, Chemical, Electicity, Income, Cess,
    Ann. Expe, Economics, and the O&M of 5 years (civil; civil and E&M)."""
    rep_tot = _repair_on_works(B)
    staff = _staff_sheet(B)
    _stage_sheets(B, rep_tot, staff)
    _om_5_years(B, rep_tot, staff)


def _repair_on_works(B):
    """Sheet Repair on Works (Elmwood): a share of each breakup head, by stage -> its total row."""
    O = B.S["om"]
    rw = B.sheet("Repair on Works", "ANNUAL REPAIR CHARGES", 9)
    B.header(rw, 5, ["S. No.", "Description", "Cost (in lakh)", "Initial %", "Amount", "Middle %", "Amount",
                     "Ultimate %", "Amount"], [7, 30, 14, 10, 12, 10, 12, 10, 12])
    heads = {"OHT/Reservoir": "R.C.C. works", "Pipeline works": "Pipe line works", "Building works": "Building works",
             "Machinery works": "Machinery works"}
    x = 6
    for i, (lab, head) in enumerate(heads.items(), 1):
        B.cell(rw, x, 1, i)
        B.cell(rw, x, 2, lab)
        B.cell(rw, x, 3, f"={B.BR[head]}", fmt="#,##0.00")
        for j, pct in enumerate(O["repair"][lab]):
            B.cell(rw, x, 4 + 2 * j, pct, fmt="0.00%", inp=True)
            B.cell(rw, x, 5 + 2 * j, f"=C{x}*{B.col(4 + 2 * j)}{x}", fmt="#,##0.00")
        x += 1
    B.cell(rw, x, 1, 5)
    B.cell(rw, x, 2, "Miscellaneous")
    B.cell(rw, x, 3, f"={B.BR['Miscellaneous']}", fmt="#,##0.00")
    x += 1
    B.cell(rw, x, 2, "TOTAL (Rs. in lakh)", bold=True)
    for c in (3, 5, 7, 9):
        B.cell(rw, x, c, f"=SUM({B.col(c)}6:{B.col(c)}{x - 1})", fmt="#,##0.00", bold=True)
    B.sign(rw, x + 3, 7)
    return x


def _staff_sheet(B):
    """Sheet A.Ex. Staff: the maintenance staff of the civil works, by stage -> its row of the totals in lakh."""
    O = B.S["om"]
    sf = B.sheet("A.Ex. Staff", "ANNUAL EXPENDITURE ON MAINTENANCE STAFF FOR CIVIL WORKS", 11)
    B.header(sf, 5, ["Sl. No", "Particulars", "Initial: No.", "Pay & allowance (Rs/month)", "Amount (Rs)",
                     "Middle: No.", "Pay & allowance", "Amount (Rs)", "Ultimate: No.", "Pay & allowance",
                     "Amount (Rs)"], [7, 30, 10, 14, 14, 10, 14, 14, 10, 14, 14])
    x = 6
    per = O["staff_per_connections"]
    for i, (lab, pay) in enumerate(O["staff"], 1):
        B.cell(sf, x, 1, i)
        B.cell(sf, x, 2, lab)
        B.cell(sf, x, 4, pay, fmt="#,##0", inp=True)
        B.cell(sf, x, 7, f"=CEILING(D{x}*(1+{O['staff_rise']}),50)", fmt="#,##0")
        B.cell(sf, x, 10, f"=CEILING(G{x}*(1+{O['staff_rise']}),50)", fmt="#,##0")
        for c, cc in ((3, "C"), (6, "D"), (9, "E")):        # 1 per 2000 connections of the stage (Income)
            B.cell(sf, x, c, f"=ROUNDUP(Income!{cc}{HH_ROW}/{per},0)", inp=True)
            B.cell(sf, x, c + 2, f"={B.col(c)}{x}*{B.col(c + 1)}{x}*12", fmt="#,##0")
        x += 1
    B.cell(sf, x, 2, "Total", bold=True)
    for c in (5, 8, 11):
        B.cell(sf, x, c, f"=SUM({B.col(c)}6:{B.col(c)}{x - 1})", fmt="#,##0", bold=True)
    B.cell(sf, x + 1, 2, "Say (lakh)", bold=True)
    for c in (5, 8, 11):
        B.cell(sf, x + 1, c, f"={B.col(c)}{x}/100000", fmt="#,##0.00", bold=True)
    staff = x + 1
    for k, t in enumerate((
            f"Number: CPHEEO Manual on Water Supply and Treatment, Part C (Management), Table 3.5 p32 - valve men / "
            f"plumber with assistant, 1 per {per:,} connections (connections of each stage: sheet Income). Part B "
            f"2.5.1 (a) p18: O&M staffing is site-specific - change the numbers to the project's.",
            "Pay: Elmwood 'A.Ex. Staff' (fitter / beldar), +20 % a stage. Pump-house staff (pump operator, electrician, "
            "watchman: Table 3.5) belong to the O&M of the pumping plants (E&M, sheet 5Yr O&M Com).",
            "Check: Part B 1.2 p4 - in pumping schemes 20 % to 40 % of the annual O&M cost goes to the staff, "
            "30 % to 50 % to power.")):
        sf.cell(x + 3 + k, 2, t).font = B.italic
    return staff


def _stage_sheet(B, name, heading, rows, note=None):
    """A sheet of rows by stage (initial / middle / ultimate): rows = [(key, label, the three values or makers of
    them, number format, an input?)] -> {key: its row}."""
    ws = B.sheet(name, heading, 5)
    B.header(ws, 5, ["S. No.", "Description", "", "", ""], [7, 56, 18, 18, 18])
    _stage_heads(B, ws, 5)
    x_ = 6
    out = {}
    for i, (key, lab, vals, fmt, inp) in enumerate(rows, 1):
        B.cell(ws, x_, 1, i)
        B.cell(ws, x_, 2, lab, bold=key in ("total", "say"))
        for j, v in enumerate(vals):
            if callable(v):
                v = v(x_, B.col(3 + j))
            B.cell(ws, x_, 3 + j, v, fmt=fmt, inp=inp, bold=key in ("total", "say"))
        out[key] = x_
        x_ += 1
    if note:
        ws.cell(x_ + 1, 2, note).font = B.italic
    B.sign(ws, x_ + 3, 4)
    return out


def _stage_sheets(B, rep_tot, staff):
    """Sheets Chemical, Electicity, Income, Cess, Ann. Expe and Economics."""
    PR, T1 = B.PR, B.T1
    O = B.S["om"]
    tot = T1["total"]
    st3 = lambda f: [f.replace("#", c) for c in "CDE"]
    pm = T1["pm"]
    ch = _stage_sheet(B, "Chemical", "ANNUAL EXPENDITURE ON LIQUID CHLORINE (SODIUM HYPOCHLORITE)", [
        ("q", "Total discharge (KL/day) - pumping main demand (T10)", [f"=T1!{c}{tot}" for c in pm], "#,##0", False),
        ("ann", "Total annual production of water (KL)", st3("=#6*365.25"), "#,##0", False),
        ("dose", "Dosing rate of chlorine (ppm)", [0.5, 0.5, 0.5], "0.00", True),
        ("kg", "Required quantity of chlorine (kg)", st3("=#7*#8/1000"), "#,##0", False),
        ("str", "Solution strength of the chemical (% w/v)", [O["hypo_strength"]] * 3, "0%", True),
        ("lit", "Quantity of hypochlorite (litre)", st3("=#9/#10"), "#,##0", False),
        ("rate", "Rate of hypochlorite (Rs per litre)", O["hypo_rate"], "#,##0", True),
        ("amt", "Amount of hypochlorite (Rs)", st3("=#11*#12"), "#,##0", False),
        ("test", "Cost of testing water samples for quality control (Rs)", O["testing"], "#,##0", True),
        ("total", "TOTAL (Rs)", st3("=#13+#14"), "#,##0", False),
        ("say", "SAY (in lakh)", st3("=#15/100000"), "#,##0.00", False)])
    el = _stage_sheet(B, "Electicity", "ANNUAL EXPENDITURE ON ELECTRICITY FOR PUMPING PLANTS & MCS", [
        ("pw", "Power consumption on tube wells, CWR, booster pumps & LCS (Rs)", [f"={B.EM['elec_year']}", "=C6", "=D6"],
         "#,##0", False),
        ("say", "SAY (in lakh)", st3("=#6/100000"), "#,##0.00", False)],
        note="Sheet EM O&M (the pumps of the design, U.P. Jal Nigam E&M estimate Riverside R3) - the same in every stage.")
    inc = _stage_sheet(B, "Income", "STATEMENT OF ANNUAL INCOME", [
        ("pop", "Design population (residential)", [f"=T1!{c}{tot}" for c in "DEF"], "#,##0", False),
        ("lpcd", "Rate of water supply (lpcd) incl. losses", [f"={PR['lpcd']}*(1+{PR['losses']})"] * 3, "0.0", False),
        ("kl", "Average daily water requirement (KL) - distribution network (T10)", [f"=T1!{c}{tot}" for c in "MNO"],
         "#,##0", False),
        ("ann", "Annual water requirement (KL)", st3("=#8*365.25"), "#,##0", False),
        ("hh", "No. of household connections", st3(f"=ROUND(#6/{PR['ppc']},0)"), "#,##0", False),
        ("tax", "No. of taxable houses", st3("=#10"), "#,##0", False),
        ("chg", "Monthly charges per household (Rs)", O["monthly_charge"], "#,##0", True),
        ("inc", "Total income (annual, Rs)", st3("=#11*#12*12"), "#,##0", False),
        ("exp", "Annual maintenance expenditure (Rs)", st3("='Ann. Expe'!#11*100000"), "#,##0", False),
        ("net", "Net profit (+) / loss (-) (Rs)", st3("=#13-#14"), "#,##0", False),
        ("say", "Net profit (+) / loss (-) (Rs. lakh)", st3("=#15/100000"), "#,##0.00", False)])
    cs = _stage_sheet(B, "Cess", "ANNUAL EXPENDITURE ON WATER CESS", [
        ("d", "Daily water drawn (KL)", st3(f"=Income!#{inc['kl']}"), "#,##0", False),
        ("a", "Annual water drawn (KL)", st3(f"=Income!#{inc['ann']}"), "#,##0", False),
        ("c", f"Cess @ Rs {O['cess_per_kl']:g} per KL (Rs)", st3(f"=#7*{O['cess_per_kl']}"), "#,##0", False),
        ("say", "Say (lakh)", st3("=#8/100000"), "#,##0.00", False)])
    ae = _stage_sheet(B, "Ann. Expe", "ANNUAL EXPENDITURE ON OPERATION & MAINTENANCE OF THE PROJECT", [
        ("el", "Electricity charges", st3(f"=Electicity!#{el['say']}"), "#,##0.00", False),
        ("ch", "Liquid chlorine", st3(f"=Chemical!#{ch['say']}"), "#,##0.00", False),
        ("rep", "Repair of works", [f"='Repair on Works'!{c}{rep_tot}" for c in "EGI"], "#,##0.00", False),
        ("st", "Maintenance staff", [f"='A.Ex. Staff'!{c}{staff}" for c in "EHK"], "#,##0.00", False),
        ("cess", f"Cess charges @ Rs {O['cess_per_kl']:g}/K.L.", st3(f"=Cess!#{cs['say']}"), "#,##0.00", False),
        ("total", "TOTAL (Rs. in lakh)", st3("=SUM(#6:#10)"), "#,##0.00", False)])
    assert ae["total"] == 11 and inc["kl"] == 8 and inc["inc"] == 13 and inc["hh"] == HH_ROW
    _stage_sheet(B, "Economics", "ABSTRACT OF ECONOMICS", [
        ("pop", "Design population", st3(f"=Income!#{inc['pop']}"), "#,##0", False),
        ("cost", "Cost of scheme (Rs. in lakh) without centage", [f"={B.FJ['total']}-{B.FJ['centage']}"] * 3,
         "#,##0.00", False),
        ("pcc", "Per capita cost (Rs)", st3("=ROUND(#7/#6*100000,2)"), "#,##0.00", False),
        ("ae", "Annual expenditure (Rs. in lakh)", st3(f"='Ann. Expe'!#{ae['total']}"), "#,##0.00", False),
        ("pcm", "Per capita maintenance expenditure (Rs)", st3("=#9/#6*100000"), "#,##0.00", False),
        ("inc", "Annual income (Rs. in lakh)", st3(f"=Income!#{inc['inc']}/100000"), "#,##0.00", False),
        ("d", "Daily production of water (KL)", st3(f"=Income!#{inc['kl']}"), "#,##0", False),
        ("a", "Annual production of water (KL)", st3(f"=Income!#{inc['ann']}"), "#,##0", False),
        ("cpk", "Cost of production of water per KL (Rs)", st3("=#9*100000/#13"), "#,##0.00", False),
        ("net", "Net profit (+) / loss (-) (Rs. in lakh)", st3("=#11-#9"), "#,##0.00", False),
        ("pci", "Per capita income (Rs)", st3("=#11/#6*100000"), "#,##0.00", False)])


def _om_5_years(B, rep_tot, staff):
    """Sheets 5 Yr O&M Civil and 5Yr O&M Com."""
    O = B.S["om"]
    rep_mach = REP_MACH
    oc = B.sheet("5 Yr O&M Civil", "OPERATION & MAINTENANCE COST FOR 5 YEARS FOR CIVIL WORKS", 5)
    for c, w in zip("ABCDE", (8, 50, 4, 16, 16)):
        oc.column_dimensions[c].width = w
    oc.cell(5, 1, "Operation and maintenance for the 1st year on civil works").font = B.bold
    B.cell(oc, 6, 2, "Repair of works (without machinery)")
    B.cell(oc, 6, 4, f"='Repair on Works'!E{rep_tot}-'Repair on Works'!E{rep_mach}", fmt="#,##0.00")
    B.cell(oc, 7, 2, "Maintenance staff")
    B.cell(oc, 7, 4, f"='A.Ex. Staff'!E{staff}", fmt="#,##0.00")
    B.cell(oc, 8, 2, "Total for the 1st year", bold=True)
    B.cell(oc, 8, 4, "=SUM(D6:D7)", fmt="#,##0.00", bold=True)
    oc.cell(10, 1, f"O&M cost for 5 years with {O['inflation'] * 100:g} % inflation per year").font = B.bold
    for i, lab in enumerate(("First", "Second", "Third", "Fourth", "Fifth")):
        x = 11 + i
        B.cell(oc, x, 2, f"{lab} year")
        B.cell(oc, x, 5, "=D8" if i == 0 else f"=ROUND(E{x - 1}*(1+{O['inflation']}),2)", fmt="#,##0.00")
    B.cell(oc, 16, 2, "TOTAL COST OF O & M for 5 years", bold=True)
    B.cell(oc, 16, 5, "=SUM(E11:E15)", fmt="#,##0.00", bold=True)
    B.cell(oc, 17, 2, f"Labour cess @ {O['labour_cess'] * 100:g} %")
    B.cell(oc, 17, 5, f"=ROUND(E16*{O['labour_cess']},2)", fmt="#,##0.00")
    B.cell(oc, 18, 2, f"GST @ {O['gst'] * 100:g} %")
    B.cell(oc, 18, 5, f"=ROUND(E16*{O['gst']},2)", fmt="#,##0.00")
    B.cell(oc, 19, 2, f"Centage @ {O['centage'] * 100:g} %")
    B.cell(oc, 19, 5, f"=ROUND(E16*{O['centage']},2)", fmt="#,##0.00")
    B.cell(oc, 20, 2, "TOTAL COST OF O&M (for 5 years) with GST and centage", bold=True)
    B.cell(oc, 20, 5, "=SUM(E16:E19)", fmt="#,##0.00", bold=True)
    B.sign(oc, 23, 4)
    om = B.sheet("5Yr O&M Com", "OPERATION & MAINTENANCE COST FOR 5 YEARS (CIVIL AND E&M WORKS)", 5)
    for c, w in zip("ABCDE", (6, 64, 6, 16, 8)):
        om.column_dimensions[c].width = w
    # as the Riverside water DPR p57 (user 7-Nov-2026): labour cess, GST and centage on each; the electricity as it is
    pc = lambda k: f"{O[k] * 100:g}%"
    E = B.EM["om_rows"]

    def line(x, lab, f, bold=False):
        B.cell(om, x, 2, lab, bold=bold)
        B.cell(om, x, 3, "Rs.")
        B.cell(om, x, 4, f, fmt="#,##0.00", bold=bold)
        B.cell(om, x, 5, "Lakh")
    om.cell(7, 1, "A.").font = B.bold
    om.cell(7, 2, "Civil Works").font = B.bold
    for x, lab, src in ((9, "Total cost of O & M for 5 years", "E16"), (10, f"Labour Cess @{pc('labour_cess')}", "E17"),
                        (11, f"GST @{pc('gst')}", "E18"), (12, f"Centage@{pc('centage')}", "E19"),
                        (OMC_CIVIL, "Total cost of O & M for 5 years", "E20")):
        line(x, lab, f"='5 Yr O&M Civil'!{src}", x == OMC_CIVIL)
    om.cell(15, 1, "B.").font = B.bold
    om.cell(15, 2, "E&M Works").font = B.bold
    EO = B.S["em"]["om"]
    for x, lab, k in ((17, "Total expenditure of electricity for 5 year", "elec"),
                      (18, "Total expenditure on O&M without electricity for 5 year", "works"),
                      (19, f"Labour Cess @{EO['labour_cess'] * 100:g}%", "cess"), (20, f"GST @{EO['gst'] * 100:g}%", "gst"),
                      (21, f"Centage@{EO['centage'] * 100:g}%", "cent")):
        line(x, lab, f"={E[k]}")
    line(22, "Total cost of O & M for 5 years", "=SUM(D17:D21)", True)
    line(OMC_TOTAL, "Total (Civil and E&M) cost of O & M for 5 years", f"=D{OMC_CIVIL}+D22", True)
    om.cell(OMC_TOTAL + 1, 2, "The E&M lines from sheet EM O&M (Rs / 100000); its say total may differ by a few "
                              "paise.").font = B.italic
    B.sign(om, OMC_TOTAL + 4, 4)


# ------------------------------------------------------------------------------------------------------------ front
def checklist(B):
    """Checklist for submission of DPR of water supply (Riverside water DPR p21-23, user decision 6-Nov-2026): the
    comments the design and the sheets give by formula, the others yellow as that DPR's (change to the project's)."""
    PR, info, T = B.PR, B.info, B.info.get("tech") or {}
    ws = B.sheet("Checklist", "CHECKLIST FOR SUBMISSION OF DPR OF WATER SUPPLY", 4)
    B.header(ws, 5, ["Sl. No.", "Description", "Comments (30 to 50 words)", "Page no. of DPR"], [7, 80, 34, 12])
    sizes = info.get("sizes") or []
    small = min(sizes, key=lambda s: size_key(s)[1]) if sizes else None
    mats = sorted({size_key(s)[0] for s in sizes})
    ex = [z for z in info["zones"] if z.get("existing")]
    pj = info.get("projection")
    method = (pj["names"][pj["adopted"]][0] if pj else "as given on the page (the design population)")
    new = [t for t in B.T3 if not t["zone"]["existing"]]
    oht = "&\", \"&".join(f"{q(t['sheet'])}!F{t['ref']['new']}&\" KL\"" for t in new) if new else '"-"'
    rows = [
        ("1.1", "Name and designation of competent authority giving technical and financial sanction",
         f'="Chief Engineer ("&{PR["zone"]}&")"', False),
        ("1.2", "Whether project necessity has been furnished in project report. Please mention key points",
         "OHT, PH, SQ and D/S", True),
        ("1.3", "Certificate of Zonal Chief Engineer showing \"The works proposed in this project have not been taken "
                "in any other estimate\" appended or not", "Yes (sheet Certificate)", False),
        ("1.4", "Index plan of whole town in A4 size showing zones already covered, in other sanctioned DPRs, and zones "
                "covered in this project, appended or not", "Yes", True),
        ("1.5", "The detailed estimates are as per the scheduled analysis of rates (SOR) of the year (yyyy-yy)",
         "2025-26", False),
        ("1.6", "The designs and drawings have been approved by the competent authority. Designation of the authority; "
                "whether as per norms and economical", "Superintending Engineer", True),
        ("2.0", "Whether the map showing project area / zone wise maps have been given in DPR", "Yes", True),
        ("3.1", "Whether area within municipal limit shown in index map", "Yes", True),
        ("3.2", "Whether additional area (beyond municipal limit) considered in the DPR (if yes, reasons)", "No", True),
        ("3.3", "Whether the land use pattern of the city / town / project area is as per the approved master plan",
         "Yes", True),
        ("3.4", "Whether the proposals for setting up WTP received clearance / consent from the State Pollution Control "
                "Board", "N.A.", True),
        ("3.5", "If the transmission main / water supply line is crossing railway line / highway & their bridge, whether "
                "the clearance from the concerned authority has been obtained and their estimate provided in DPR",
         "N.A.", True),
        ("3.5.1", "If no, the present status of action initiated", "N.A.", True),
        ("4.1", "Whether consent from the ULB for providing F.O.C. land for water works, T.W.s etc. is enclosed",
         "Yes", True),
        ("4.2", "Whether resolution of ULB enclosed or not / proposals have been countersigned or not", "Yes", True),
        ("4.2.1", "If yes, please mention present and proposed tariff",
         "=\"Rs \"&Income!C12&\" / \"&Income!D12&\" / \"&Income!E12&\" a household a month\"", False),
        ("5.0", "Proposed source: ground water or surface water or partially both", "Ground water (tube wells)", True),
        ("5.1", "For surface water: certificate of water availability / yield / reservation for 30 years", "N.A.", True),
        ("5.2", "For ground water: whether opinion of the SGWB / CGWB has been obtained on quantity and quality",
         "No", True),
        ("6.1", "No. of households as per last census", f"={PR['hh_census']}", False),
        ("6.2", "Existing number of house connections", f"={PR['hc_shift']}", False),
        ("6.3", "Proposed no. of house connections", f"={PR['hc']}", False),
        ("6.4", "Percent coverage of households with house connections after implementation of this scheme", "100%",
         True),
        ("6.5", "Whether list of proposed house service connections enclosed; source of the list", "Yes", True),
        ("7.1", "Whether population projection has been made as per CPHEEO Manual in different stages",
         "Yes" if pj else "Stages as given on the page", False),
        ("7.2", "Please mention method adopted and reason in its favour", method, False),
        ("7.3", "Whether the population projection has been made in consonance with the developmental master plan",
         "N.A.", True),
        ("7.4", "Whether ward wise and zone wise population given",
         "Yes (T2-T4, T16, T10, T17)" if T.get("wards") else "Zone wise and DMA wise (T10, T17)", False),
        ("8.1", "Whether existing details of water supply have been furnished in DPR",
         "Yes, old OHTs repairable (S4)" if ex else "No existing structures in the area", False),
        ("8.2", "Whether the existing water supply infrastructure has been taken into consideration in DPR",
         "Yes, old OHTs repairable" if ex else "N.A.", False),
        ("8.3", "Reasons for not utilising existing infrastructure like OHT / pipe network", "As per CPHEEO Manual", True),
        ("8.4", "% of population coverage (including existing and proposed) of the town / city",
         "=TEXT(Coverage!D12,\"0.00%\")", False),
        ("8.5", "% of population coverage in the zone / area considered in this project", "100%", True),
        ("8.6", "Average per capita water supply level (existing) in city in lpcd / % coverage after this scheme",
         f'=TEXT({PR["lpcd"]}*(1+{PR["losses"]}),"0.00")&" LPCD"', False),
        ("8.7", "Average per capita water supply level in the project area in lpcd / % coverage after this scheme",
         f'=TEXT({PR["lpcd"]}*(1+{PR["losses"]}),"0.00")&" LPCD"', False),
        ("9.1", "Whether the design of intake, WTP, pumping main and distribution system has been provided in DPR",
         "Pumping mains and distribution system: yes (T15, T20, T21); intake / WTP: N.A.", False),
        ("9.2", "If applicable, whether the raw water characteristics of source have been tested", "N.A.", True),
        ("9.3", "Whether treated water shall conform to the standards of drinking water as per CPHEEO Manual", "N.A.",
         True),
        ("10.0", "Mention capacity of service reservoir worked out in KL", "=" + oht, False),
        ("11.1", "Whether old pipe lines are proposed to be replaced or duplicated or discarded, reasons",
         "All be replaced", True),
        ("11.2", "Minimum diameter pipe as per criterion and proposed minimum diameter",
         f"{size_key(small)[1]} mm dia {size_key(small)[0]}" if small else "-", False),
        ("11.3", "Pipe material as per criterion and as per proposal in DPR", " / ".join(mats) + " pipe", False),
        ("11.4", "Reasons for any deviation from criterion with regard to min. dia. or material", "N.A.", True),
        ("12.1", "If applicable, whether hydraulic flow diagram (HFD) with head loss calculation for WTP and layout plan "
                 "of WTP have been furnished", "N.A.", True),
        ("12.2", "Whether maps of the proposed distribution system indicating RL, node no., link no., available head etc. "
                 "for all the zones are enclosed", "Yes (design report, T13)", False),
        ("12.3", "Whether L sections of the proposed pumping main / transmission main have been furnished", "N.A.", True),
        ("13.0", "Whether lump sum provision for any item has been made, specify the maximum amount",
         "WTP / feeder main (ABS Com, yellow)", True),
        ("14.0", "Whether operation & maintenance cost and revenue generation details have been furnished",
         "Yes (5Yr O&M Com, Economics)", False),
        ("15.0", "Please mention period of completion of the project / base year / mid year / design year",
         f'="24 Months (21+3 T/R); "&{PR["base_year"]}&"/"&{PR["mid_year"]}&"/"&{PR["design_year"]}', False),
        ("16.0", "Per capita cost of project at base year Rs. / capita", "=Economics!C8", False),
        ("17.0", "Whether unit estimates of all type designs are sanctioned at circle level", "Yes", True),
        ("18.0", "Any anticipated bottlenecks and possible solutions", "No.", True),
        ("19.0", "If any trenchless technology is proposed for laying of pipe line", "No", True),
        ("19.1", "If yes, mention diameter and length proposed and reasons there off", "N.A.", True),
        ("19.2", "Has location of trenchless laying been shown on index map", "N.A.", True),
        ("19.3", "Please mention SOR for trenchless laying / basis of rates proposed", "IndSTT-2020 (U08 HDD)", True),
        ("20.0", "Rain water harvesting proposed", '=IF(GWR!D6>0,"Yes","No")', False),
        ("21.0", "To minimise operating expenses, development of alternative energy (solar) proposed", "No", True),
        ("22.0", "SCADA and digital tools for performance indicators proposed", "Yes", False),
        ("23.1", "To achieve minimum service bench marks bulk water meters at generation and supply proposed", "Yes",
         False),
        ("23.2", "Whether existing / proposed no. of house service connections with domestic meters", "No", True),
        ("23.3", "Whether list of proposed house service connections with meters enclosed", "No", True),
        ("24.0", "Final outcome of project (project cost, population served and increase in coverage post execution)",
         f'="Rs "&TEXT({B.FJ["grand"]},"#,##0.00")&" lakh; "&TEXT({PR["pop_design"]},"#,##0")&" persons (design '
         f'year); coverage "&TEXT(Coverage!D12,"0.00%")', False)]
    for i, (no, lab, com, inp) in enumerate(rows):
        x = 6 + i
        B.cell(ws, x, 1, no)
        B.cell(ws, x, 2, lab).alignment = B.wrap
        B.cell(ws, x, 3, com, inp=inp).alignment = B.wrap
        B.cell(ws, x, 4, None)
    x = 6 + len(rows) + 1
    ws.cell(x, 2, "Riverside water DPR p21-23: the comments by formula from the sheets of this DPR; yellow - as that "
                  "DPR, change to the project's.").font = B.italic
    B.sign(ws, x + 3, 3)
