"""The front pages of the water DPR workbook (dpr.py) laid out as the final approved Riverside water DPR (U.P. Jal
Nigam, AMRUT 2.0, the 443 scanned pages; user request 7-Nov-2026: page by page as that DPR):

    Cover                       p20   the title page: U.P. Jal Nigam (Urban), the scheme, the programme, estimated
                                      cost, O&M cost, the Executive Engineer
    Checklist                   p21-23 (dpr_more.checklist)
    Certificate                 p24
    Coverage                    p25
    Title - Index, Index        p35, p36
    Title - Salient, Salient feature   p37, p38-41: one sheet of four pages (user decision 7-Nov-2026), laid out
                                      as the user's example (the Elmwood DPR's salient features, 7-Nov-2026)
    Title - Project Report      p42
    Title - Financial           p43   (Form J Com. and the rest follow)

Each page heads with the scheme, DISTRICT- ..., UNDER ... PROGRAMME over a double rule (head); a title page is one
sheet with the part's name in a framed page (divider). The texts come from sheet Project by formula.

    write(B)    after the abstracts, O&M and economics (B.FJ, Economics) and the technical sheets
"""
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.worksheet.pagebreak import Break

from . import dpr_more
from .dpr import size_key

TITLES = [("Title - Index", "INDEX"), ("Title - Salient", "SALIENT FEATURES"),
          ("Title - Project Report", "PROJECT REPORT"), ("Title - Financial", "FINANCIAL STATEMENT"),
          ("Title - Economics", "ECONOMICS"), ("Title - Technical", "TECHNICAL STATEMENT")]     # p59, p67
PIPE_HEADS = {"HDPE": "HDPE (PE-100) PN-6", "DI": "D.I. K-7 Pipe", "DI K9": "D.I. K-9 Pipe"}    # p40
FONT = "Times New Roman"
THIN, THICK, DOUBLE = Side(style="thin"), Side(style="thick"), Side(style="double")


def _f(size, bold=False, italic=False, underline=None):
    return Font(name=FONT, size=size, bold=bold, italic=italic, underline=underline)


def head(B, ws, ncols, heading=None, r=1):
    """The page head of the DPR (p24, p38): the scheme, DISTRICT- ..., UNDER ... PROGRAMME over a double rule, the
    heading underlined. Returns the next free row."""
    PR = B.PR
    rows = [(f'=UPPER(""&{PR["title"]})', _f(14, True), 36),
            (f'="DISTRICT- "&UPPER(""&{PR["district"]})', _f(12, True), None),
            (f'=IF(""&{PR["under"]}="","","UNDER "&UPPER({PR["under"]})&" PROGRAMME")', _f(12, True), None)]
    for k, (v, font, h) in enumerate(rows):
        c = ws.cell(r + k, 1, v)
        c.font, c.alignment = font, Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.merge_cells(start_row=r + k, start_column=1, end_row=r + k, end_column=ncols)
        if h:
            ws.row_dimensions[r + k].height = h
    for c in range(1, ncols + 1):
        ws.cell(r + 2, c).border = Border(bottom=DOUBLE)
    x = r + 4
    if heading:
        c = ws.cell(x, 1, heading)
        c.font, c.alignment = _f(12, True, underline="single"), Alignment(horizontal="center")
        ws.merge_cells(start_row=x, start_column=1, end_row=x, end_column=ncols)
        x += 2
    return x


def _merge(ws, r, c0, c1, v=None, font=None, align=None, border=None):
    c = ws.cell(r, c0, v)
    if font:
        c.font = font
    c.alignment = align or Alignment(horizontal="center", vertical="center", wrap_text=True)
    if c1 > c0:
        ws.merge_cells(start_row=r, start_column=c0, end_row=r, end_column=c1)
    if border:
        for k in range(c0, c1 + 1):
            ws.cell(r, k).border = border
    return c


def divider(B, name, text):
    """A title page (p35, p37, p42, p43): the part's name, large, in a framed A4 page."""
    ws = B.wb.create_sheet(name)
    for k in range(1, 9):
        ws.column_dimensions[chr(64 + k)].width = 10
    for r in range(1, 53):
        ws.row_dimensions[r].height = 15
    top, bot = 3, 50
    for r in range(top, bot + 1):
        for c in range(1, 9):
            ws.cell(r, c).border = Border(left=THICK if c == 1 else None, right=THICK if c == 8 else None,
                                          top=THICK if r == top else None, bottom=THICK if r == bot else None)
    _merge(ws, 24, 1, 8, text, _f(36, True))
    ws.row_dimensions[24].height = 90
    B.keep_look.add(name)
    return ws


def cover(B):
    """The title page (p20)."""
    PR = B.PR
    ws = B.wb.create_sheet("Cover")
    for k in range(1, 9):
        ws.column_dimensions[chr(64 + k)].width = 11
    for r in range(1, 46):
        ws.row_dimensions[r].height = 16
    top, bot = 2, 44
    for r in range(top, bot + 1):
        for c in range(1, 9):
            ws.cell(r, c).border = Border(left=THICK if c == 1 else None, right=THICK if c == 8 else None,
                                          top=THICK if r == top else None, bottom=THICK if r == bot else None)
    _merge(ws, 4, 1, 8, "UTTAR PRADESH JAL NIGAM", _f(28, True))
    _merge(ws, 6, 1, 8, "(URBAN)", _f(28, True))
    ws.row_dimensions[4].height = ws.row_dimensions[6].height = 36
    _merge(ws, 14, 1, 8, f'="ESTIMATE FOR "&UPPER(""&{PR["title"]})', _f(18, True))
    ws.row_dimensions[14].height = 120
    _merge(ws, 17, 1, 8, "(VOLUME-I)", _f(16, True))
    _merge(ws, 19, 1, 8, f'=IF(""&{PR["under"]}="","","UNDER")', _f(16, italic=True))
    _merge(ws, 22, 1, 8, f'=IF(ISNUMBER(SEARCH("AMRUT",""&{PR["under"]})),"ATAL MISSION FOR REJUVENATION AND URBAN '
                         f'TRANSFORMATION "&TRIM(SUBSTITUTE(UPPER({PR["under"]}),"AMRUT",""))&" ("&UPPER({PR["under"]})&")",'
                         f'UPPER(""&{PR["under"]}))', _f(16, True))
    ws.row_dimensions[22].height = 44
    left = [("Estimate No.", None, True), ("Estimated cost", f'="Rs. "&TEXT({B.FJ["total"]},"0.00")&" Lakh"', False),
            ("O & M Cost", f'="Rs. "&TEXT({B.FJ["om"]},"0.00")&" Lakh"', False), ("Year", None, True)]
    right = ["Executive Engineer", f'=""&{PR["office"]}', "U.P. Jal Nigam (Urban)", f'=""&{PR["district"]}']
    for k, (lab, v, inp) in enumerate(left):
        r = 34 + k
        _merge(ws, r, 1, 2, lab, _f(13, True), Alignment(horizontal="left", vertical="center", indent=1))
        ws.cell(r, 3, ":").font = _f(13, True)
        c = _merge(ws, r, 4, 5, v, _f(13, True), Alignment(horizontal="left", vertical="center"))
        if inp:
            c.fill = B.yellow
        _merge(ws, r, 6, 8, right[k], _f(13, True))
    B.keep_look.add("Cover")
    return ws


def certificate(B):
    """The certificate (p24)."""
    PR = B.PR
    ws = B.wb.create_sheet("Certificate")
    for k in range(1, 7):
        ws.column_dimensions[chr(64 + k)].width = 14
    x = head(B, ws, 6)
    _merge(ws, x, 1, 6, "Certificate", _f(14, True, underline="single"))
    x += 2
    _merge(ws, x, 1, 6, f'="          This is to Certify that the provision/works included under this detailed '
                            f'project report of "&UPPER(""&{PR["title"]})&IF(""&{PR["under"]}="",""," UNDER "&UPPER('
                            f'{PR["under"]}))&" DISTRICT- "&UPPER(""&{PR["district"]})&" have neither been incorporated '
                            f'in any other DPR of the program and have not been executed in part or in full under any '
                            f'other DPR /Program."', _f(12),
               Alignment(horizontal="justify", vertical="top", wrap_text=True))
    ws.row_dimensions[x].height = 90
    x += 4
    name = lambda k: f'="(Er. "&{PR[k]}&")"'
    for c0, c1, k, post in ((1, 3, "ae", "Assistant Engineer"), (4, 6, "ee", "Executive Engineer")):
        _merge(ws, x, c0, c1, name(k), _f(12))
        _merge(ws, x + 1, c0, c1, post, _f(12))
    _merge(ws, x + 2, 1, 6, f'=""&{PR["office"]}', _f(12))
    x += 6
    for v in (name("se"), "Superintending Engineer", f'=""&{PR["circle"]}'):
        _merge(ws, x, 1, 6, v, _f(12))
        x += 1
    x += 2
    _merge(ws, x, 1, 6, "Countersigned", _f(12, italic=True))
    x += 4
    for v in (name("ce"), f'="Chief Engineer"&IF(""&{PR["zone"]}="",""," ("&{PR["zone"]}&")")',
              "U.P. Jal Nigam (Urban)"):
        _merge(ws, x, 1, 6, v, _f(12))
        x += 1
    return ws


def coverage(B):
    """Coverage status of the household water connections (p25)."""
    PR = B.PR
    cv = B.wb.create_sheet("Coverage")
    for c, w in zip("ABCD", (7, 62, 16, 12)):
        cv.column_dimensions[c].width = w
    x = head(B, cv, 4, "COVERAGE STATUS - WATER HOUSE CONNECTIONS")
    _merge(cv, x, 1, 4, f'="Construction of Household Water Connections for "&IF(""&{PR["ulb"]}="","the City",'
                        f'{PR["ulb"]})', _f(12, True))
    x += 1
    B.header(cv, x, ["S. No.", "Description", "Nos", "%"])
    h = x
    rows = [("Total households as per the last census", f"={PR['hh_census']}", False),
            ("Total households in the base year", f"={PR['hh_base']}", False),
            ("Households with water connections before AMRUT 1.0", f"={PR['hh_before']}", True),
            ("Households with water connections sanctioned under AMRUT 1.0", f"={PR['hh_amrut1']}", True),
            ("Households with water connections already sanctioned under AMRUT 2.0", f"={PR['hh_amrut2']}", True),
            ("Water connections proposed in this DPR", f"={PR['hc']}", True),
            ("Households with water connections after execution", f"=C{h + 3}+C{h + 4}+C{h + 5}+C{h + 6}", True),
            ("Households remaining without water connections", f"=C{h + 2}-C{h + 7}", True)]
    for i, (lab, v, pct) in enumerate(rows):
        x = h + 1 + i
        B.cell(cv, x, 1, i + 1)
        B.cell(cv, x, 2, lab)
        B.cell(cv, x, 3, v, fmt="#,##0")
        B.cell(cv, x, 4, f"=IFERROR(C{x}/$C${h + 2},0)" if pct else "-", fmt="0.0%")
    x += 2
    cv.cell(x, 2, "Numbers from sheet Project (yellow there).").font = B.italic
    cv.cell(x + 3, 1, "Assistant Engineer").font = B.bold
    cv.cell(x + 3, 3, "Executive Engineer").font = B.bold


def index(B):
    """The index (p36): the parts with their page numbers (to be filled on printing) and the sheets of each."""
    ix = B.wb.create_sheet("Index")
    for c, w in zip("ABCDE", (7, 36, 10, 10, 70)):
        ix.column_dimensions[c].width = w
    x = head(B, ix, 5, "INDEX")
    B.header(ix, x, ["S. No.", "Description", "Page No. From", "To", "Sheets of this workbook"])
    parts = [("SALIENT FEATURES", "Salient feature"), ("PROJECT REPORT", ""),
             ("FINANCIAL STATEMENT", "Form J Com., ABS Com, Form J Civil, ABS Civil, Form J E&M, ABS E&M, Breakup, "
              "5Yr O&M Com, 5 Yr O&M Civil, Economics, Income, Ann. Expe, Electicity, Chemical, Repair on Works, "
              "A.Ex. Staff, Cess"),
             ("TECHNICAL STATEMENT", ""), ("ESTIMATES OF CIVIL WORKS", ""), ("ESTIMATES OF E&M WORKS", ""),
             ("UNIT ESTIMATES", ""), ("SCHEDULE OF RATES", ""), ("ANNEXURES", ""), ("DRAWINGS", "")]
    for i, (lab, sh) in enumerate(parts, 1):
        r = x + i
        B.cell(ix, r, 1, i)
        B.cell(ix, r, 2, lab)
        B.cell(ix, r, 3, None, inp=True)
        B.cell(ix, r, 4, None, inp=True)
        B.cell(ix, r, 5, sh).alignment = B.wrap
    ix.cell(x + len(parts) + 2, 2, "Page numbers (yellow): fill in when the DPR is printed and bound.").font = B.italic


SAL_WIDTHS = {"A": 4.86, "B": 5.86, "C": 8.43, "D": 9.43, "E": 11.29, "F": 10.71, "G": 8.86, "H": 8.43, "I": 8.43,
              "J": 8.43, "K": 9.71, "L": 10.86, "M": 11.0}      # as the example (user 7-Nov-2026)


def _split(n, k):
    """k columns shared by n parts, the larger first: [2, 2, 2, 1, 1] for 5 in 8."""
    q_, r_ = divmod(k, n)
    return [q_ + (1 if i < r_ else 0) for i in range(n)]


def salient(B):
    """Salient features as the user's example (salient feature example.xlsx / .pdf of 7-Nov-2026, the Elmwood DPR's,
    and the Riverside water DPR p38-41): columns A-M, Times New Roman 12, the tables boxed and centred, a page break
    before 6 (clear water demand), the rest flowing; the rising main only for the zones with one."""
    PR, T1, info, S = B.PR, B.T1, B.info, B.S
    sf = B.wb.create_sheet("Salient feature")
    for c, w in SAL_WIDTHS.items():
        sf.column_dimensions[c].width = w
    N = 13
    thin = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
    zs = [z["name"] for z in info["zones"]]
    tot = T1["total"]
    yrs = [PR["base_year"], PR["mid_year"], PR["design_year"]]

    def m(r, c0, c1, v=None, bold=False, h="center", fmt=None, box=True, size=12, fill=None, r1=None):
        """A cell (merged c0..c1, rows r..r1) as the example: Times New Roman, centred, wrapped, boxed."""
        r1 = r1 or r
        c = sf.cell(r, c0, v)
        c.font = _f(size, bold)
        c.alignment = Alignment(horizontal=h, vertical="center", wrap_text=True)
        if fmt:
            c.number_format = fmt
        if fill:
            c.fill = fill
        if box:
            for rr in range(r, r1 + 1):
                for cc in range(c0, c1 + 1):
                    sf.cell(rr, cc).border = thin
        if c1 > c0 or r1 > r:
            sf.merge_cells(start_row=r, start_column=c0, end_row=r1, end_column=c1)
        return c

    def item(r, no, lab, v=None, sep=":", bold_v=False):
        m(r, 1, 1, f"{no}-", True, box=False)
        m(r, 2, 4 if v is not None or sep else N, lab, True, "left", box=False)
        if v is not None:
            m(r, 5, 5, sep, True, box=False)
            m(r, 6, N, v, bold_v, "left", box=False)
        elif sep:
            m(r, 5, 5, sep, True, box=False)

    def heading(r, no, lab):
        m(r, 1, 1, f"{no}-", True, box=False)
        m(r, 2, N, lab, True, "left", box=False)

    # ---------------------------------------------------------------- 1-5: project, population, rate of supply
    x = head(B, sf, N, "SALIENT FEATURES")
    item(x, 1, "Name of Project", f'=UPPER(""&{PR["title"]})')
    sf.row_dimensions[x].height = 51.6
    item(x + 1, 2, "District", f'=UPPER(""&{PR["district"]})')
    item(x + 2, 3, "Programme", f'=""&{PR["under"]}')
    item(x + 3, 4, "Population")
    x += 4
    fl = f'="Floating Population ("&TEXT({PR["floating"]},"0%")&")"'

    def stage_table(x, title, pops, inp=False):
        m(x, 1, N, title, True, "left", box=False)
        sf.row_dimensions[x].height = 19.15
        x += 1
        for c0, c1, v in ((1, 1, "S. No."), (2, 4, "Description"), (5, 5, "Year"), (6, 7, "Population"),
                          (8, 9, fl), (10, 11, "Total")):
            m(x, c0, c1, v, True)
        sf.row_dimensions[x].height = 46.15
        for i, lab in enumerate(("Initial stage", "Middle stage", "Design stage")):
            r = x + 1 + i
            p, f_ = pops(i)
            m(r, 1, 1, i + 1)
            m(r, 2, 4, lab)
            m(r, 5, 5, f"={yrs[i]}")
            m(r, 6, 7, p, fmt="0", fill=B.yellow if inp else None)
            m(r, 8, 9, f_, fmt="0")
            m(r, 10, 11, f"=F{r}+H{r}", fmt="0")
            sf.row_dimensions[r].height = 22.15
        return x + 5

    city = lambda i: (f"={PR[('city_base', 'city_mid', 'city_design')[i]]}",
                      f"=ROUND({PR[('city_base', 'city_mid', 'city_design')[i]]}*{PR['floating']},0)")
    x = stage_table(x, f'="Total Population of "&IF(""&{PR["ulb"]}="","the City",{PR["ulb"]})&" :-"', city, True)
    x = stage_table(x, "Total Population of the Project Area :-",
                    lambda i: (f"=T1!{'DEF'[i]}{tot}", f"=T1!{'GHI'[i]}{tot}"))

    def years(r, c0):
        for j in range(3):
            m(r, c0 + j, c0 + j, f'=""&{yrs[j]}', True)
    m(x, 1, 1, "S. No.", True, r1=x + 1)
    m(x, 2, 3, "Zone No.", True, r1=x + 1)
    m(x, 4, 6, "Population", True)
    m(x, 7, 9, f'="Floating Population @"&TEXT({PR["floating"]},"0%")', True)
    m(x, 10, 12, "Total Population", True)
    for c0 in (4, 7, 10):
        years(x + 1, c0)
    sf.row_dimensions[x].height, sf.row_dimensions[x + 1].height = 34.9, 20.45
    x += 2
    z0 = x
    for i, z in enumerate(zs):
        r = T1["rows"][z]
        m(x, 1, 1, i + 1)
        m(x, 2, 3, z)
        for j in range(3):
            m(x, 4 + j, 4 + j, f"=T1!{'DEF'[j]}{r}", fmt="0")
            m(x, 7 + j, 7 + j, f"=T1!{'GHI'[j]}{r}", fmt="0")
            m(x, 10 + j, 10 + j, f"={B.col(4 + j)}{x}+{B.col(7 + j)}{x}", fmt="0")
        x += 1
    m(x, 1, 3, "Total", True)
    for c in range(4, 13):
        m(x, c, c, f"=SUM({B.col(c)}{z0}:{B.col(c)}{x - 1})", True, fmt="0")
    x += 2
    heading(x, 5, "Rate of  Water Supply:")
    for k, (lab, v) in enumerate((("Domestic", f'={PR["lpcd"]}&" lpcd + "&TEXT({PR["losses"]},"0%")&" for unaccounted '
                                               f'for water"'), ("Floating", f'={PR["floating_lpcd"]}&" lpcd"'))):
        r = x + 1 + k
        m(r, 2, 2, "*", box=False)
        m(r, 3, 4, lab, h="left", box=False)
        m(r, 5, 5, ":", True, box=False)
        m(r, 6, N, v, h="left", box=False)
    x += 3
    sf.row_breaks.append(Break(id=x))                    # as the example: the demand on a page of its own
    # ---------------------------------------------------------------- 6-8: demand, source, rising main
    x += 1
    heading(x, 6, "Clear Water Demand:")
    x += 2
    m(x, 1, 1, "S. No.", True, r1=x + 1)
    m(x, 2, 3, "Zone No.", True, r1=x + 1)
    m(x, 4, 6, f'="Demand (in KLD) (@"&TEXT({PR["lpcd"]}*(1+{PR["losses"]}),"0.0")&" KLD including "&TEXT('
               f'{PR["losses"]},"0%")&" for losses)"', True)
    m(x, 7, 9, f'="Floating Demand (in KLD) (@"&{PR["floating_lpcd"]}&" LPCD)"', True)
    m(x, 10, 10, "Fire Demand (KLD)", True, r1=x + 1)
    m(x, 11, 13, "Total Demand (in KLD)", True)
    for c0 in (4, 7, 11):
        years(x + 1, c0)
    sf.row_dimensions[x].height, sf.row_dimensions[x + 1].height = 62.45, 23.45
    x += 2
    z0 = x
    fire = T1["fire_col"]
    for i, z in enumerate(zs):
        r = T1["rows"][z]
        m(x, 1, 1, i + 1)
        m(x, 2, 3, z)
        for j in range(3):
            m(x, 4 + j, 4 + j, f"=T1!{'DEF'[j]}{r}*{PR['lpcd']}*(1+{PR['losses']})/1000", fmt="0.00", size=11)
            m(x, 7 + j, 7 + j, f"=T1!{'GHI'[j]}{r}*{PR['floating_lpcd']}/1000", fmt="0.00", size=11)
            m(x, 11 + j, 11 + j, f"=T1!{'MNO'[j]}{r}+J{x}", fmt="0.00", size=11)
        m(x, 10, 10, f"=T1!{fire}{r}", fmt="0.00", size=11)
        x += 1
    m(x, 1, 3, "Total", True)
    for c in range(4, 14):
        m(x, c, c, f"=SUM({B.col(c)}{z0}:{B.col(c)}{x - 1})", True, fmt="0.00", size=11)
    if any(z.get("bulk_kld") for z in info["zones"]):
        m(x + 1, 2, N, "The total demand includes the bulk consumers (sheet T1) with their losses.", h="left",
          box=False, size=10)
        x += 1
    x += 2
    m(x, 1, 1, "7-", True, box=False)
    m(x, 2, 5, "Source of Water", True, "left", box=False)
    m(x, 6, 6, "-", True, box=False)
    m(x, 7, N, "Ground Water (Tube well)", True, "left", box=False, fill=B.yellow)
    x += 2
    heading(x, 8, "Rising Main")
    x += 2
    tws = [t for t in ((info.get("rising") or {}).get("tws") or []) if t.get("size")]
    rmt = getattr(B, "RMT_ROWS", None)
    if tws and rmt:
        sizes = sorted({t["size"] for t in tws}, key=lambda s: (size_key(s)[1], s))[:8]
        a, b = rmt
        bp = S["civil"]["rm_bypass_m"]
        spans, c0 = [], 5
        for w in _split(len(sizes), 8):
            spans.append((c0, c0 + w - 1))
            c0 += w
        cls = " / ".join(sorted({("DI K9" if t.get("cls") == "K9" else size_key(t["size"])[0] + (" K-7" if size_key(
            t["size"])[0] == "DI" else "")) for t in tws}))
        m(x, 2, 4, "Zone", True, r1=x + 1)
        m(x, 5, 13, f"Length of Rising Main (i/c bypass arrangement) ({cls}) (in m)", True)
        for (s0, s1), s in zip(spans, sizes):
            m(x + 1, s0, s1, f"{size_key(s)[1]}mm Dia", True, size=12 if s1 > s0 else 9)
        m(x + 1, 13, 13, "Total", True)
        sf.row_dimensions[x].height, sf.row_dimensions[x + 1].height = 22.15, 16.15
        x += 2
        z0 = x
        T7 = "'RM Design'"
        for z in [z for z in zs if any(t.get("oz") == z for t in tws)]:
            m(x, 2, 4, z)
            for (s0, s1), s in zip(spans, sizes):
                crit = f'{T7}!$C${a}:$C${b},"{z}",{T7}!$H${a}:$H${b},"{s}*"'
                m(x, s0, s1, f'=IF(COUNTIFS({crit})=0,"",SUMIFS({T7}!$E${a}:$E${b},{crit})+{bp}*COUNTIFS({crit}))',
                  fmt="0.00")
            m(x, 13, 13, f"=SUM(E{x}:L{x})", True, fmt="0.00")
            x += 1
        m(x, 2, 4, "Total", True)
        for s0, s1 in spans:
            m(x, s0, s1, f"=SUM({B.col(s0)}{z0}:{B.col(s1)}{x - 1})", True, fmt="0.00")
        m(x, 13, 13, f"=SUM(M{z0}:M{x - 1})", True, fmt="0.00")
        x += 1
    else:
        m(x, 2, N, "No new rising main is proposed in this DPR.", h="left", box=False)
        x += 1
    x += 2
    # ---------------------------------------------------------------- 9-10: storage, network, connections
    heading(x, 9, "Storage")
    m(x + 1, 2, N, f'="As per the design criteria for water supply schemes under "&{PR["under"]}&" programme, the storage '
                   f'capacity OHT has been calculated and proposed in this DPR."', h="justify", box=False)
    sf.row_dimensions[x + 1].height = 38.45
    x += 2
    for c0, c1, v in ((2, 3, "S. No."), (4, 5, "Zone No."), (6, 8, "Capacity of OHT (in KL)"),
                      (9, 11, "Capacity of CWR (in KL)"), (12, 13, "Staging (m)")):
        m(x, c0, c1, v, True)
    sf.row_dimensions[x].height = 22.9
    x += 1
    z0 = x
    s0 = B.SUM["first"]
    for i, z in enumerate(zs):
        y = s0 + i
        m(x, 2, 3, i + 1)
        m(x, 4, 5, z)
        m(x, 6, 8, f'=IF(Summary!G{y}>0,Summary!G{y},Summary!D{y}&" (Existing)")', fmt="0")
        m(x, 9, 11, f"=Summary!H{y}", fmt="0")
        m(x, 12, 13, f"=Summary!K{y}", fmt="0")
        x += 1
    m(x, 2, 5, "Total", True)
    m(x, 6, 8, f"=SUM(F{z0}:H{x - 1})", True, fmt="0")
    m(x, 9, 11, f"=SUM(I{z0}:K{x - 1})", True, fmt="0")
    x += 2
    heading(x, 10, "Distribution Network")
    x += 1
    m(x, 2, 5, "Type/Class/Size of Pipe (mm)", True, r1=x + 1)
    m(x, 6, 13, "Length (M)", True)
    m(x + 1, 6, 13, None)
    x += 2
    d0, last = x, None
    for s in info["sizes"]:
        mat, d = size_key(s)
        if mat != last:
            m(x, 2, 5, PIPE_HEADS.get(mat, mat), True)
            m(x, 6, 13, None)
            last = mat
            x += 1
        m(x, 2, 5, f"{d}mm")
        m(x, 6, 13, f"={B.SDS['pipe'][s]}", fmt="0")
        x += 1
    m(x, 2, 5, "Total", True)
    m(x, 6, 13, f"=SUM(F{d0}:F{x - 1})", True, fmt="0")
    x += 1
    bz = [z["name"] for z in info["zones"] if z.get("vfd_kw")]
    if bz:
        m(x, 2, N, "Booster pumps have been proposed for " + ", ".join(bz) + " to increase the pressure at the "
                   "consumer end as per latest guidelines of CPHEEO manual on water supply.", h="justify", box=False)
        sf.row_dimensions[x].height = 16 * (1 + len(", ".join(bz)) // 90) + 16
        x += 1
    m(x, 2, N, "House Connection:", True, "left", box=False)
    x += 1
    hc0 = x + 2
    m(x, 2, N, f'="Provision for "&TEXT(H{hc0 + len(zs)},"0")&" Nos. house connection is proposed in the DPR to meet '
               f'the mission objective."', h="justify", box=False)
    sf.row_dimensions[x].height = 20.45
    x += 1
    for c0, c1, v in ((2, 4, "Zone"), (5, 7, "Existing"), (8, 10, "Proposed"), (11, 13, "Total")):
        m(x, c0, c1, v, True)
    x += 1
    for z in zs:
        r = T1["rows"][z]
        m(x, 2, 4, z)
        m(x, 5, 7, 0, fmt="0", fill=B.yellow)
        m(x, 8, 10, f"=ROUND({PR['hc']}*T1!D{r}/T1!D{tot},0)", fmt="0")
        m(x, 11, 13, f"=E{x}+H{x}", fmt="0")
        x += 1
    m(x, 2, 4, "Total", True)
    for c0 in (5, 8, 11):
        m(x, c0, c0 + 2, f"=SUM({B.col(c0)}{hc0}:{B.col(c0)}{x - 1})", True, fmt="0")
    m(x + 1, 2, N, "Proposed: the connections of the DPR (sheet Project) shared by the base-year population of the "
                   "zones (sheet T1); existing (yellow): fill in.", h="left", box=False, size=10)
    x += 3
    # ---------------------------------------------------------------- 11-12: agency, economics
    m(x, 1, 1, "11-", True, box=False)
    m(x, 2, N, " Implementing Agency       -          U.P. Jal Nigam (Urban)", True, "left", box=False)
    heading(x + 1, 12, "Economics of the Scheme:")
    x += 2
    m(x, 2, 2, "S. No.", True, r1=x + 1)
    m(x, 3, 7, "Items", True, r1=x + 1)
    m(x, 8, 13, "Year", True)
    for j, c0 in enumerate((8, 10, 12)):
        m(x + 1, c0, c0 + 1, f'=""&{yrs[j]}', True)
    x += 2
    eco = [("Design Population", 6, "0"), ("Cost of Scheme (Rs. in lacs) without centage", 7, "0.00"),
           ("Per Capita Cost (Rs.)", 8, "0.00"), ("Annual Expenditure (Rs. in lacs)", 9, "0.00"),
           ("Per Capita Maintenance Expenditure (in Rs.)", 10, "0.00"), ("Annual Income (Rs. in lacs)", 11, "0.00"),
           ("Daily Production of Water (KL)", 12, "0.00"), ("Annual Production of Water (KL)", 13, "0.00"),
           ("Cost of production of Water / KL. (in Rs.)", 14, "0.00"),
           ("Net Profit (+) / Loss (-) (Rs. in lacs)", 15, "0.00"), ("Per capita maintenance cost (Rs.)", 10, "0.00"),
           ("Per Capita Income (Rs.)", 16, "0.00")]
    for i, (lab, er, fmt) in enumerate(eco, 1):
        m(x, 2, 2, i)
        m(x, 3, 7, lab, h="left")
        for c0, c in zip((8, 10, 12), "CDE"):
            m(x, c0, c0 + 1, f"=Economics!{c}{er}", i == 3, fmt=fmt)
        x += 1
    m(x + 2, 11, 13, "Assistant Engineer", True, box=False)
    last = x + 2
    # the page as the example: A4 portrait, its margins, centred, fitted to the width
    ps = sf.page_setup
    ps.paperSize, ps.orientation = sf.PAPERSIZE_A4, "portrait"
    ps.fitToWidth, ps.fitToHeight = 1, 0
    ps.blackAndWhite = True                              # the yellow inputs on the screen only
    sf.sheet_properties.pageSetUpPr.fitToPage = True
    sf.print_options.horizontalCentered = True
    mg = sf.page_margins
    mg.left, mg.right, mg.top, mg.bottom = 0.433, 0.236, 0.394, 0.354
    sf.print_area = f"A1:M{last}"
    B.own_page.add("Salient feature")


def write(B):
    """The front pages (see the module text); the sheets they need first (abstracts, economics, technical)."""
    B.keep_look = set()                               # sheets laid out here whose fonts dpr_format keeps
    B.own_page = set()                                # ... and their page setup too
    cover(B)
    dpr_more.checklist(B)
    certificate(B)
    coverage(B)
    for name, text in TITLES:
        divider(B, name, text)
    index(B)
    salient(B)
