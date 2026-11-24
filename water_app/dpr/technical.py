"""The Project sheet and the technical statement of the water DPR: population projection, demand, storage, each OZ's
statement (T3), the summary and the tube wells (restructure stage 3, 15-Nov-2026: out of dpr.py)."""
import math
from .base import COVER, DEFAULT_TEXTS, KEPT, ROADS, TEXTS, _previous, motor_margin, q, standby


# ------------------------------------------------------------------------------------------------------------ Project
def project(B, previous=None):
    info, crit, S = B.info, B.crit, B.S
    old = _previous(previous)
    ws = B.wb.create_sheet("Project")
    ws.cell(1, 1, "PROJECT - the texts and inputs used on every sheet of this DPR").font = B.big
    ws.cell(2, 1, "Fill / change here (yellow): every sheet takes these by formula. Texts typed here are kept when the "
                  "DPR is made again from the app.").font = B.italic
    for c, w in zip("ABCD", (6, 56, 30, 90)):
        ws.column_dimensions[c].width = w
    PR, r = B.PR, 4
    for key, label in TEXTS:
        ws.cell(r, 2, label)
        c = B.cell(ws, r, 3, old.get(key, info["title"] if key == "title" else DEFAULT_TEXTS.get(key, "")),
                   inp=True)
        if key == "title":
            c.font = B.bold
            if old.get("title") and old["title"] != info["title"]:
                ws.cell(r, 4, f"(name kept from the previous DPR; the app's project name is '{info['title']}')")
        PR[key] = f"Project!$C${r}"
        r += 1
    r += 1
    ws.cell(r, 2, "Years and population (from the app's design)").font = B.bold
    r += 1
    st = info["stages"]
    y0 = st.get("base_year") or 2027
    v = lambda k: crit[k]["value"]
    rows = [("base_year", "Base year", int(y0), "page: आधार वर्ष", None),
            ("mid_year", "Middle year (+15)", f"=C{r}+15", "CPHEEO Table 2.7 S.No.1 p168: pumps for +15 years", None),
            ("design_year", "Design year (+30)", f"=C{r}+30", "pipes and ESRs for +30 years (S.No.1 p168)", None),
            ("pop_design", "Population in the design year (+30) - the design's", round(info["pop"]),
             "sum of the junctions' population of the design (zoning)", "#,##0"),
            ("pop_base", "Population in the base year", st.get("pop_initial") or round(info["pop"]),
             ("projection (sheet T): the junctions' base-year population" if info.get("projection") else
              "page: आधार वर्ष की आबादी" + ("" if st.get("pop_initial") else " - not given: the design's population")),
             "#,##0"),
            ("pop_mid", "Population in the middle year (+15)", st.get("pop_mid") or round(info["pop"]),
             ("projection (sheet T): base year x the adopted method's +15 / base" if info.get("projection") else
              "page: +15 वर्ष की आबादी" + ("" if st.get("pop_mid") else " - not given: the design's population")), "#,##0"),
            ("lpcd", "Water supply (lpcd)", v("lpcd"), crit["lpcd"]["ref"], None),
            ("losses", "Distribution losses (share)", v("distribution_losses"), crit["distribution_losses"]["ref"], "0%"),
            ("floating", "Floating population (share of the population)", v("floating_share"),
             crit["floating_share"]["ref"], "0%"),
            ("floating_lpcd", "Floating population: water supply (lpcd)", v("floating_lpcd"),
             crit["floating_lpcd"]["ref"], None),
            ("peak", "Peak factor", v("peak_factor"), crit["peak_factor"]["ref"], None),
            ("ppc", "Persons per connection (household)", v("persons_per_connection"),
             crit["persons_per_connection"]["ref"], "0.00"),
            ("min_share", "OHT: minimum storage (share of the ultimate daily demand)", v("esr_capacity_share"),
             crit["esr_capacity_share"]["ref"], "0%"),
            ("fire_share", "OHT: fire storage (share of the OZ's fire demand)", v("fire_storage_share"),
             crit["fire_storage_share"]["ref"], "0.0%"),
            ("round_kl", "OHT / CWR capacity rounded up to (KL)", v("oht_capacity_round_kl"),
             crit["oht_capacity_round_kl"]["ref"], None),
            ("cwr_tw", "CWR when more tube wells than this fill one OHT", v("cwr_when_tubewells_over"),
             crit["cwr_when_tubewells_over"]["ref"], None),
            ("cwr_share", "CWR capacity (share of the OHT)", v("cwr_capacity_share"), crit["cwr_capacity_share"]["ref"],
             "0%")]
    for key, label, val, note, fmt in rows:
        ws.cell(r, 2, label)
        B.cell(ws, r, 3, val, fmt=fmt, inp=key not in ("mid_year", "design_year", "pop_design"))
        ws.cell(r, 4, note)
        PR[key] = f"Project!$C${r}"
        r += 1
    ws.cell(r, 4, "The design ran on the population of the app (page): a change in the yellow cells changes the "
                  "statements and the estimate here, not the pipe sizes - make the design again from the app for "
                  "that.").font = B.red
    r += 2
    ws.cell(r, 2, "Road surface along the pipes (share of the pipe length) - sheet RC").font = B.bold
    r += 1
    for k in ROADS:
        ws.cell(r, 2, k)
        B.cell(ws, r, 3, S["road_share"][k], fmt="0%", inp=True)
        PR["road:" + k] = f"Project!$C${r}"
        r += 1
    ws.cell(r, 2, "Total (should be 100 %)")
    B.cell(ws, r, 3, f"=SUM(C{r - len(ROADS)}:C{r - 1})", fmt="0%")
    ws.cell(r, 4, "Elmwood 'RC' F5:N5 - change to the project's roads")
    r += 2
    ws.cell(r, 2, "House connections (sheet NEW HC)").font = B.bold
    r += 1
    ws.cell(r, 2, "New house connections proposed (nos)")
    B.cell(ws, r, 3, f"=ROUND({PR['pop_base'].replace('Project!', '')}/{PR['ppc'].replace('Project!', '')},0)",
           fmt="#,##0", inp=True)
    ws.cell(r, 4, "default: base-year population / persons per connection (all households) - put the households "
                  "still without a connection")
    PR["hc"] = f"Project!$C${r}"
    r += 1
    ws.cell(r, 2, KEPT[0][1])
    B.cell(ws, r, 3, old.get("hc_shift", 0), fmt="#,##0", inp=True)
    ws.cell(r, 4, "sheet Shif. HC (Riverside water DPR p295: the existing connections of the area) - fill in")
    PR["hc_shift"] = f"Project!$C${r}"
    r += 2
    ws.cell(r, 2, "Coverage of the city (sheet Coverage)").font = B.bold
    r += 1
    for key, label in COVER:
        ws.cell(r, 2, label)
        B.cell(ws, r, 3, old.get(key), fmt="#,##0", inp=True)
        PR[key] = f"Project!$C${r}"
        r += 1
    return PR


# ------------------------------------------------------------------------------------------------------------ T
def t_projection(B):
    """Population projection - the start of the technical statement as the Riverside water DPR p68-71 (user request
    7-Nov-2026; the methods as the Elmwood 'T', 30-Oct-2026): design period, the census of the town (horizontal and with
    the increase per decade, incremental increase and decadal rate, averages X, Y, r), the five methods worked out for
    the base, middle and design years (say: CEILING 5), their table, the adopted method; then the project area's
    population: P0 x the adopted projection's ratios. Made always - with no census given on the page its years and
    populations are yellow blanks to fill (the design's population then as the page's)."""
    from .front import head
    from ..population import NAMES, METHODS
    from openpyxl.styles import Alignment, Font
    f, PR = B.info.get("projection"), B.PR
    cs = f["census"] if f else [(y, None) for y in range(1951, 2021, 10)]
    adopted = f["adopted"] if f else "geometrical"
    safe = (lambda v: v) if f else (lambda v: f"IFERROR({v},0)")          # blank census: no #DIV/0
    ws = B.wb.create_sheet("T")
    for c, w in zip("ABCDEFGHIJKL", (6, 30, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12)):
        ws.column_dimensions[c].width = w
    N = 12

    def text(r, v, bold=False, h=None, size=None):
        c = ws.cell(r, 1, v)
        if bold:
            c.font = B.bold
        c.alignment = Alignment(horizontal="justify", vertical="top", wrap_text=True)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=N)
        if h:
            ws.row_dimensions[r].height = h
        return c
    x = head(B, ws, N, "TECHNICAL STATEMENT")
    ws.cell(x, 1, "DESIGN PERIOD:").font = B.bold
    text(x + 1, f'="          Based on latest prevalent norms, the design period has been adopted as 30 years. The '
                f'initial year taken as "&{PR["base_year"]}&", prospective year taken as "&{PR["mid_year"]}&", and the '
                f'Ultimate year taken as "&{PR["design_year"]}&"."', h=32)
    ws.cell(x + 3, 1, "POPULATION PROJECTION:").font = B.bold
    ulb = f'IF(""&{PR["ulb"]}="","the town",{PR["ulb"]})'
    # ---- the census, across (p68)
    h = x + 6
    n_c = len(cs)
    B.cell(ws, h, 1, "Sl. No.", bold=True)
    B.cell(ws, h, 2, "Name of ULB", bold=True)
    B.cell(ws, h, 3, "Census Code", bold=True)
    B.cell(ws, h, 4, "Population in different census year", bold=True)
    for c in range(5, 4 + n_c + 1):
        B.cell(ws, h, c, None)
    ws.merge_cells(start_row=h, start_column=4, end_row=h, end_column=3 + n_c + 1)
    for c in (1, 2, 3):
        B.cell(ws, h + 1, c, None)
        ws.merge_cells(start_row=h, start_column=c, end_row=h + 1, end_column=c)
    # ---- the census, down (p68): the inputs (yellow), the increase per decade, incremental, decadal rate
    v0 = h + 8
    ws.cell(v0 - 2, 1, "The population projection for different stages of the design period is proposed to be done by "
                       "the different standard prescribed methods: " +
                       ", ".join(f"{i} {NAMES[m][0].replace(' (straight line fitted)', '')}"
                                 for i, m in enumerate(METHODS, 1)) +
                       ". Based on the census figures, the decadal growth, incremental increase and percentage increase "
                       "in population are tabulated below:")
    ws.merge_cells(start_row=v0 - 2, start_column=1, end_row=v0 - 2, end_column=N)
    ws.cell(v0 - 2, 1).alignment = Alignment(horizontal="justify", vertical="top", wrap_text=True)
    ws.row_dimensions[v0 - 2].height = 48
    B.header(ws, v0 - 1, ["S.N.", "Year", "Census population", "Increased population per decade",
                          "Incremental increased population", "Decadal percentage increased population",
                          "ln (population)"])
    ws.row_dimensions[v0 - 1].height = 45
    r0 = v0
    for i, (y, p) in enumerate(cs):
        r = r0 + i
        B.cell(ws, r, 1, i + 1)
        B.cell(ws, r, 2, y, inp=True)
        B.cell(ws, r, 3, p, fmt="#,##0", inp=True)
        if i:
            B.cell(ws, r, 4, "=" + safe(f"(C{r}-C{r - 1})/((B{r}-B{r - 1})/10)"), fmt="#,##0")
            B.cell(ws, r, 6, "=" + safe(f"(C{r}/C{r - 1})^(1/((B{r}-B{r - 1})/10))-1"), fmt="0.00%")
        if i > 1:
            B.cell(ws, r, 5, f"=D{r}-D{r - 1}", fmt="#,##0")
        B.cell(ws, r, 7, "=" + safe(f"LN(C{r})"), fmt="0.0000")
    r1 = r0 + n_c - 1
    a = r1 + 1
    B.cell(ws, a, 2, "Average", bold=True)
    B.cell(ws, a, 4, "=" + safe(f"AVERAGE(D{r0 + 1}:D{r1})"), fmt="#,##0.00", bold=True)            # X
    if n_c > 2:
        B.cell(ws, a, 5, "=" + safe(f"AVERAGE(E{r0 + 2}:E{r1})"), fmt="#,##0.00", bold=True)        # Y
    rates = [f"F{r}" for r in range(r0 + 1, r1 + 1)]
    gm = (f"PRODUCT(F{r0 + 1}:F{r1})^(1/{len(rates)})" if f and all(g["rate"] > 0 for g in f["growth"])
          else "(" + "*".join(f"(1+{c})" for c in rates) + f")^(1/{len(rates)})-1")
    B.cell(ws, a, 6, "=" + safe(gm), fmt="0.00%", bold=True)                                          # r
    ws.cell(a + 1, 2, "X = average increase per decade, Y = average incremental increase, r = decadal growth rate "
                      "(the geometric mean of the decades', as Elmwood T U54)").font = B.italic
    # the census across, now that its rows are known
    for i in range(n_c):
        c = 4 + i
        B.cell(ws, h + 1, c, f"=B{r0 + i}", bold=True)
        B.cell(ws, h + 2, c, f"=C{r0 + i}", fmt="#,##0")
    c_hh = 4 + n_c
    B.cell(ws, h + 1, c_hh, "Households (census)", bold=True)
    B.cell(ws, h + 2, c_hh, f"={PR['hh_census']}", fmt="#,##0")
    B.cell(ws, h + 2, 1, 1)
    B.cell(ws, h + 2, 2, f"={ulb}")
    B.cell(ws, h + 2, 3, None, inp=True)
    ws.row_dimensions[h + 1].height = 30
    years = "&\", \"&".join(f"B{r0 + i}" for i in range(n_c))
    text(x + 4, f'="The population figures based on census records are available for "&{ulb}&" for the census years "&'
                f'{years}&". The details of population are tabulated as below:"', h=32)
    # ---- the graph lines, the methods worked out (p69-70)
    s = a + 3
    ws.cell(s, 2, "Straight lines fitted to the census (least squares, for the graph methods)").font = B.bold
    B.cell(ws, s + 1, 2, "Simple graph: b (persons per year)")
    B.cell(ws, s + 1, 4, "=" + safe(f"SLOPE(C{r0}:C{r1},B{r0}:B{r1})"), fmt="#,##0.00")
    B.cell(ws, s + 2, 2, "Semi-log graph: c (per year, of ln population)")
    B.cell(ws, s + 2, 4, "=" + safe(f"SLOPE(G{r0}:G{r1},B{r0}:B{r1})"), fmt="0.000000")
    # the decreasing rate of growth (CPHEEO Manual on Water Supply 2024 Part A Annexure 2.8 Eq. 2.5, user request
    # 9-Nov-2026): S, the average change of the decadal rate, and the town decade by decade from the last census
    B.cell(ws, s + 3, 2, "Decreasing rate: S (average change of the decadal rate per decade)")
    B.cell(ws, s + 3, 4, "=" + safe(f"(F{r1}-F{r0 + 1})/{n_c - 2}") if n_c > 2 else None, fmt="0.00%")
    hs, K = s + 5, 8
    ws.cell(hs, 2, "Decreasing rate of growth: the town decade by decade from the last census - r(k) = r(k-1) + S "
                   "(not below 0), P(k) = P(k-1) x (1 + r(k)) (CPHEEO Manual on Water Supply 2024 Part A Annexure 2.8 "
                   "Eq. 2.5)").font = B.bold
    B.header(ws, hs + 1, ["k", "Year", "Rate of growth r(k)", "Population P(k)"])
    for k in range(K + 1):
        y, p = hs + 2 + k, hs + 1 + k
        B.cell(ws, y, 1, k)
        B.cell(ws, y, 2, f"=B{r1}" if k == 0 else f"=B{p}+10")
        B.cell(ws, y, 3, f"=F{r1}" if k == 0 else "=" + safe(f"MAX(0,C{p}+$D${s + 3})"), fmt="0.00%")
        B.cell(ws, y, 4, f"=C{r1}" if k == 0 else "=" + safe(f"D{p}*(1+C{y})"), fmt="#,##0")
    dP, dR = f"$D${hs + 2}:$D${hs + 2 + K}", f"$C${hs + 2}:$C${hs + 2 + K}"
    s = hs + 2 + K - 2                                       # the methods below the table
    b_, c_ = f"$D${hs - 4}", f"$D${hs - 3}"
    X, Y, R = f"$D${a}", f"$E${a}", f"$F${a}"
    Yc, Pc = f"$B${r1}", f"$C${r1}"                                    # the last census year and its population
    yrs = [PR["base_year"], PR["mid_year"], PR["design_year"]]
    stage_lab = ("base", "Middle", "Design")
    n = lambda j: f"(({yrs[j]}-{Yc})/10)"
    T = lambda v: f'TEXT({v},"0")'
    T1_ = lambda v: f'TEXT({v},"0.0")'
    forms = {"arithmetical": ("Pn = Pc + n X", "Pc = population of the last census, n = no. of decades, X = average "
                                                "population increase per decade",
                              lambda j: f"{Pc}+{n(j)}*{X}",
                              lambda j: f'"= "&{T(Pc)}&" + "&{T1_(n(j))}&" x "&{T(X)}'),
             "incremental": ("Pn = Pc + n X + n (n+1)/2 Y", "n = no. of decades, X = average population increase per "
                                                             "decade, Y = average incremental increase per decade",
                             lambda j: f"{Pc}+{n(j)}*{X}+{n(j)}*({n(j)}+1)/2*{Y}",
                             lambda j: f'"= "&{T(Pc)}&" + "&{T1_(n(j))}&" x "&{T(X)}&" + "&{T1_(n(j))}&" x "&'
                                       f'{T1_(n(j) + "+1")}&" x 0.5 x "&{T(Y)}'),
             "geometrical": ("Pn = Pc x (1 + r)^n", "Pc = population of the last census, n = no. of decades, r = rate "
                                                    "of growth per decade",
                             lambda j: f"{Pc}*(1+{R})^{n(j)}",
                             lambda j: f'"= "&{T(Pc)}&" x (1 + "&TEXT({R}*100,"0.00")&" / 100)^"&{T1_(n(j))}'),
             "decreasing": ("Pn = P(n-1) x (1 + r(n-1) + S), decade by decade",
                            "r = the decadal growth rate, S = its average change per decade (negative where it falls); "
                            "a part of a decade at its rate - the table above",
                            lambda j: f"INDEX({dP},INT({n(j)})+1)*(1+INDEX({dR},INT({n(j)})+2))^({n(j)}-INT({n(j)}))",
                            lambda j: f'"= "&{T(f"INDEX({dP},INT({n(j)})+1)")}&" x (1 + "&'
                                      f'TEXT(INDEX({dR},INT({n(j)})+2)*100,"0.00")&" / 100)^"&TEXT({n(j)}-INT({n(j)}),"0.0")'),
             "graph": ("Pn = Pc + b (year - census year)", "b = the slope of the straight line fitted to the census "
                                                           "(persons per year)",
                       lambda j: f"{Pc}+{b_}*({yrs[j]}-{Yc})",
                       lambda j: f'"= "&{T(Pc)}&" + "&TEXT({b_},"0.00")&" x "&{T(yrs[j] + "-" + Yc)}'),
             "semilog": ("Pn = Pc x e^(c (year - census year))", "c = the slope of the straight line fitted to ln "
                                                                 "(population)",
                         lambda j: f"{Pc}*EXP({c_}*({yrs[j]}-{Yc}))",
                         lambda j: f'"= "&{T(Pc)}&" x e^("&TEXT({c_},"0.000000")&" x "&{T(yrs[j] + "-" + Yc)}&")"')}
    m0 = s + 4
    say = {}
    for k, m in enumerate(METHODS, 1):
        name, where, val, shown = forms[m][0], forms[m][1], forms[m][2], forms[m][3]
        c = ws.cell(m0, 1, f"{k}. {NAMES[m][0].upper()}:")
        c.font = Font(name="Times New Roman", bold=True, underline="single")
        ws.cell(m0 + 1, 2, name).font = B.bold
        ws.cell(m0 + 2, 2, f"where {where}").font = B.italic
        say[m] = []
        for j in range(3):
            r = m0 + 3 + j
            ws.cell(r, 2, f'="Population in {stage_lab[j]} Year "&{yrs[j]}')
            ws.cell(r, 3, "=" + shown(j))
            ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=8)
            B.cell(ws, r, 9, "=" + safe(val(j)), fmt="#,##0.00")
            ws.cell(r, 10, "say")
            B.cell(ws, r, 11, "=" + safe(f"CEILING(I{r},5)"), fmt="#,##0", bold=True)
            say[m].append(f"$K${r}")
        m0 += 7
    # ---- the methods' table and the adopted one (p71)
    t = m0 + 1
    ws.cell(t - 1, 1, "The projected population as computed by different standard prescribed methods at initial, "
                      "middle and design stage are tabulated below:").font = B.bold
    B.header(ws, t, ["Sl. No.", "Method", "Population (last census)", "Initial Stage", "Middle Stage",
                     "Ultimate Stage"])
    ws.row_dimensions[t].height = 30
    town = {}
    for i, m in enumerate(METHODS, 1):
        r = t + i
        town[m] = r
        B.cell(ws, r, 1, i)
        B.cell(ws, r, 2, NAMES[m][0], bold=m == adopted)
        B.cell(ws, r, 3, f"={Pc}", fmt="#,##0")
        for j in range(3):
            B.cell(ws, r, 4 + j, f"={say[m][j]}", fmt="#,##0")
    j0 = t + len(METHODS) + 2
    text(j0, f'="          After the judgment of the population figures projected by the {len(METHODS)} different methods, '
             f'considering the trend of growth of "&{ulb}&", the population projection by the {NAMES[adopted][0]} '
             f'for the design year "&{PR["design_year"]}&" seems to be justified and hence adopted for the design '
             f'purposes."', h=48)
    z = j0 + 2
    B.header(ws, z, ["Sl. No.", "Adopted Method", "Population (last census)", "Initial Year", "Middle Year",
                     "Design Year", "Design / base"])
    x_ad = town[adopted]
    B.cell(ws, z + 1, 1, 1)
    B.cell(ws, z + 1, 2, NAMES[adopted][0], bold=True)
    for c in (3, 4, 5, 6):
        B.cell(ws, z + 1, c, f"={B.col(c)}{x_ad}", fmt="#,##0", bold=True)
    B.cell(ws, z + 1, 7, "=" + safe(f"F{z + 1}/D{z + 1}"), fmt="0.000", bold=True)
    ws.cell(z + 2, 2, "chosen on the page (default geometrical, as the Elmwood and Riverside DPRs)" +
            ("" if f else "; no census given on the page - fill in the yellow census (the design's population is then "
                          "the page's, not this projection's)")).font = B.italic
    # ---- the project area's population (the census may be the town's, the project a part of it)
    p = z + 4
    ws.cell(p, 1, "POPULATION OF THE PROJECT AREA:").font = B.bold
    if f and f.get("from_year"):                       # the ward table's (7-Nov-2026): grown from its year
        ws.cell(p, 4, f"the wards' population in the project in {f['from_year']}: {f['from_pop']:,.0f} (sheet Wards), "
                      f"grown to the base year by the adopted method").font = B.italic
    B.cell(ws, p + 1, 2, "Population in the base year (P0) - the project area")
    B.cell(ws, p + 1, 4, f["base_pop"] if f else f"={PR['pop_base']}", fmt="#,##0",
           inp=bool(f) and not f.get("from_year"))
    P0 = f"$D${p + 1}"
    t2 = p + 3
    B.header(ws, t2, ["S.N.", "Method", "", "Base year", "Middle year (+15)", "Design year (+30)", "Design / base"])
    rows = {}
    for i, m in enumerate(METHODS, 1):
        r, s_ = t2 + i, town[m]
        rows[m] = r
        B.cell(ws, r, 1, i)
        B.cell(ws, r, 2, NAMES[m][0], bold=m == adopted)
        B.cell(ws, r, 4, f"={P0}", fmt="#,##0")
        B.cell(ws, r, 5, "=" + safe(f"CEILING({P0}*E{s_}/D{s_},5)"), fmt="#,##0")
        B.cell(ws, r, 6, "=" + safe(f"CEILING({P0}*F{s_}/D{s_},5)"), fmt="#,##0")
        B.cell(ws, r, 7, "=" + safe(f"F{r}/D{r}"), fmt="0.000")
    za = t2 + len(METHODS) + 2
    ws.cell(za, 2, "Adopted method").font = B.bold
    B.cell(ws, za + 1, 2, NAMES[adopted][0], bold=True)
    for c in (4, 5, 6, 7):
        B.cell(ws, za + 1, c, f"={B.col(c)}{rows[adopted]}", fmt="0.000" if c == 7 else "#,##0", bold=True)
    ws.cell(za + 2, 2, "P0 x the projection of the year / of the base year (CEILING 5); the design's population on the "
                       "junctions (wards / the total) is the base year's, grown by the adopted ratios - Project rows "
                       "of the population" + ("" if f else " (no census: the page's)")).font = B.italic
    if f and f.get("wards"):                           # wards with a character (7-Nov-2026): their own factors
        w = f["wards"]
        n = sum(1 for x in w["rows"] if x["char"])
        fo = f.get("far_open")
        ws.cell(za + 3, 2, f"{n} of the {len(w['rows'])} wards grow by the factors of their character (Riverside water DPR p76; "
                           f"sheet Wards), the others by the adopted method: the project area base / middle / design "
                           f"{w['init']:,.0f} / {w['mid']:,.0f} / {w['ult']:,.0f}" +
                           ("; Far-open balanced to the adopted method: x " + " / ".join(f"{x:.4f}" for x in fo["factors"])
                            if fo else "")).font = B.italic
        za += 1
    # ---- the graphs (example technical.xlsx 'T': the census bar chart, the simple graph and semi-log plots; and the
    # methods compared - user decision 9-Nov-2026): their data here, the charts added after the sheets are renamed
    # (projection_charts - a chart's references carry the sheet's name)
    d0 = za + 6
    ws.cell(d0 - 1, 1, "GRAPHS: the census and the projection of the town by each method").font = B.bold
    B.header(ws, d0, ["", "Year", "Census population"] + [NAMES[m][0].replace(" (straight line fitted)", "")
                                                         for m in METHODS])
    ws.row_dimensions[d0].height = 45
    for i in range(n_c):
        B.cell(ws, d0 + 1 + i, 2, f"=B{r0 + i}")
        B.cell(ws, d0 + 1 + i, 3, f"=C{r0 + i}", fmt="#,##0")
    for k, m in enumerate(METHODS):
        B.cell(ws, d0 + n_c, 4 + k, f"=C{r1}", fmt="#,##0")          # each method's line from the last census
        for j in range(3):
            B.cell(ws, d0 + n_c + 1 + j, 4 + k, f"={say[m][j]}", fmt="#,##0")
    for j in range(3):
        B.cell(ws, d0 + n_c + 1 + j, 2, f"={yrs[j]}")
    ch0 = d0 + n_c + 6
    from openpyxl.worksheet.pagebreak import Break
    ws.row_breaks.append(Break(id=d0 - 2))            # the graphs' data and the graphs: pages of their own
    ws.row_breaks.append(Break(id=ch0 - 1))
    B.TCHART = {"d0": d0, "nc": n_c, "methods": list(METHODS), "at": ch0, "adopted": adopted,
                "low": min(p for _, p in f["census"]) if f else None}
    B.sign(ws, ch0 + 40, 10)
    B.TPROJ = {"adopted_row": za + 1}


def projection_charts(B, ws):
    """The graphs of sheet T1 Population (user decision 9-Nov-2026; example technical.xlsx 'T' charts 1-3): the census
    as bars, the simple graph method and the semi-log graph method (log scale) each with the census, and all the
    methods compared - Excel charts on the data block of t_projection, in the page's colours."""
    from openpyxl.chart import BarChart, Reference, ScatterChart, Series
    from ..population import NAMES
    C = getattr(B, "TCHART", None)
    if not C:
        return
    d0, nc, ms = C["d0"], C["nc"], C["methods"]
    col = {"arithmetical": "2A78D6", "incremental": "EB6834", "geometrical": "1BAF7A", "decreasing": "7E57C2",
           "graph": "EDA100", "semilog": "E87BA4"}
    # the DPR prints in black and white (dpr_format): each method its own marker and dash too
    mark = {"arithmetical": "square", "incremental": "triangle", "geometrical": "circle", "decreasing": "diamond",
            "graph": "x", "semilog": "star"}
    dash = {"arithmetical": "solid", "incremental": "dash", "geometrical": "solid", "decreasing": "sysDot",
            "graph": "lgDash", "semilog": "dashDot"}
    xs_c = Reference(ws, min_col=2, min_row=d0 + 1, max_row=d0 + nc)
    ys_c = Reference(ws, min_col=3, min_row=d0 + 1, max_row=d0 + nc)

    def axes(ch, title, log=False):
        ch.title = title
        ch.x_axis.title, ch.y_axis.title = "Year", "Population"
        ch.x_axis.delete = ch.y_axis.delete = False
        ch.y_axis.number_format = "#,##0"
        ch.width, ch.height = 13, 7.5
        if log:
            ch.y_axis.scaling.logBase = 10
            if C.get("low"):                              # from the decade below the smallest census
                ch.y_axis.scaling.min = 10 ** int(math.floor(math.log10(C["low"])))
        if ch.legend is not None:                         # below the plot, not over it
            ch.legend.position, ch.legend.overlay = "b", False
        return ch

    def census():
        s = Series(ys_c, xs_c, title="Census")
        s.marker.symbol, s.marker.size = "circle", 6
        s.marker.graphicalProperties.solidFill = "757575"
        s.graphicalProperties.line.noFill = True
        return s

    short = {"arithmetical": "Arithmetical", "incremental": "Incremental", "geometrical": "Geometrical",
             "decreasing": "Decreasing rate", "graph": "Simple graph", "semilog": "Semi-log graph"}

    def method(m, brief=False):
        k = ms.index(m)
        x = Reference(ws, min_col=2, min_row=d0 + nc, max_row=d0 + nc + 3)
        y = Reference(ws, min_col=4 + k, min_row=d0 + nc, max_row=d0 + nc + 3)
        s = Series(y, x, title=short[m] if brief else NAMES[m][0].replace(" (straight line fitted)", ""))
        s.marker.symbol, s.marker.size = mark[m], 6
        s.marker.graphicalProperties.solidFill = col[m]
        s.graphicalProperties.line.dashStyle = dash[m]
        s.smooth = False                                  # straight between the stages
        s.graphicalProperties.line.solidFill = col[m]
        s.graphicalProperties.line.width = 38100 if m == C["adopted"] else 19050
        return s
    bar = BarChart()
    bar.add_data(ys_c)
    bar.set_categories(xs_c)
    bar.legend = None
    bar.series[0].graphicalProperties.solidFill = "4F81BD"
    charts = [axes(bar, "Census population")]
    for m, title, log in (("graph", "Simple graph method", False), ("semilog", "Semi-log graph method", True)):
        ch = ScatterChart()
        ch.series.append(census())
        ch.series.append(method(m))
        charts.append(axes(ch, title, log))
    cmp = ScatterChart()
    cmp.series.append(census())
    for m in ms:
        cmp.series.append(method(m, True))
    charts.append(axes(cmp, "Projection of the town by each method"))
    cmp.height, cmp.legend.position = 9, "r"                   # six methods: the legend beside
    a = C["at"]
    for ch, cell in zip(charts, (f"B{a}", f"G{a}", f"B{a + 16}", f"G{a + 16}")):
        ws.add_chart(ch, cell)


# ------------------------------------------------------------------------------------------------------------ T1
def t1(B):
    """OZ-wise population and demand (Elmwood 'T1'), demand as the design (demand.py): domestic x (1 + losses) +
    floating; fire 100 sqrt(P) shared by population (CPHEEO Table 2.7 S.No.13). The bulk consumers of each OZ (user
    30-Oct-2026): a yellow column of their own at the end (KLD, the same every year), in the demand without losses and,
    with the losses, in the distribution's - so in the pumping main, the tube wells and the OHT too; their list below."""
    PR, zs = B.PR, B.info["zones"]
    ws = B.sheet("T1", "THE PROJECTED POPULATION & DEMAND AS PER OPERATION ZONE (OZ) IN BASE, MIDDLE AND DESIGN YEAR", 25)
    heads = ["Sl. No.", "Operation Zone (OHT)", "DMAs", "Population base year", "Population middle year",
             "Population design year", "Floating base", "Floating middle", "Floating design",
             "Demand without losses base (KLD)", "middle (KLD)", "design (KLD)",
             "Distribution network (10 % losses on domestic) base (KLD)", "middle (KLD)", "design (KLD)"]
    fac = list(B.S["demand_factors"].items())
    for lab, _ in fac:
        heads += [f"{lab} base", "middle", "design"]
    heads += ["Fire demand design year (KLD)", "Total for OHT storage design year (KLD)",
              "Bulk consumers (KLD without losses, every year)"]
    cb = len(heads)                                            # the bulk column: its letter in the demand formulas
    B.header(ws, 5, heads, [6, 22, 7] + [12] * (len(heads) - 3))
    ws.row_dimensions[5].height = 75
    first = 6
    ref = {}
    yr = lambda k: f'=""&{PR[k]}'
    for c, k in ((4, "base_year"), (5, "mid_year"), (6, "design_year")):
        ws.cell(4, c, yr(k)).font = B.bold
    for i, z in enumerate(zs):
        x = first + i
        P = lambda c: f"{B.col(c)}{x}"
        B.cell(ws, x, 1, i + 1)
        B.cell(ws, x, 2, z["name"])
        B.cell(ws, x, 3, z["dmas"])
        B.cell(ws, x, 6, round(z["population"]), fmt="#,##0")
        own = ((B.info.get("tech") or {}).get("own_stages") and (B.info["tech"]["oz"].get(z["name"])))
        if own:                       # wards with a character (6-Nov-2026): the OZ's own base / +15 years, by junction
            B.cell(ws, x, 4, own["init"], fmt="#,##0")
            B.cell(ws, x, 5, own["mid"], fmt="#,##0")
        else:
            B.cell(ws, x, 4, f"=ROUND(F{x}*{PR['pop_base']}/{PR['pop_design']},0)", fmt="#,##0")
            B.cell(ws, x, 5, f"=ROUND(F{x}*{PR['pop_mid']}/{PR['pop_design']},0)", fmt="#,##0")
        B.cell(ws, x, cb, round(z.get("bulk_kld") or 0.0, 1), fmt="#,##0.0", inp=True)
        bk = f"${B.col(cb)}{x}"
        for j in range(3):
            B.cell(ws, x, 7 + j, f"={P(4 + j)}*{PR['floating']}", fmt="#,##0")
            B.cell(ws, x, 10 + j, f"=({P(4 + j)}*{PR['lpcd']}+{P(7 + j)}*{PR['floating_lpcd']})/1000+{bk}", fmt="#,##0.0")
            B.cell(ws, x, 13 + j, f"=({P(4 + j)}*{PR['lpcd']}*(1+{PR['losses']})+{P(7 + j)}*{PR['floating_lpcd']})/1000"
                                  f"+{bk}*(1+{PR['losses']})", fmt="#,##0.0")
            for k, (_, f) in enumerate(fac):
                B.cell(ws, x, 16 + 3 * k + j, f"={P(10 + j)}*{f}", fmt="#,##0.0")
        cf = 16 + 3 * len(fac)
        city = f"SUM($F${first}:$F${first + len(zs) - 1})"
        B.cell(ws, x, cf, f"=IF({city}>=50000,100*SQRT({city}/1000)*F{x}/{city},100*SQRT(50)*F{x}/50000)", fmt="#,##0.0")
        B.cell(ws, x, cf + 1, f"=O{x}+{P(cf)}", fmt="#,##0.0")
        ref[z["name"]] = x
    last = first + len(zs) - 1
    tot = last + 1
    B.cell(ws, tot, 2, "Total", bold=True)
    for c in range(3, len(heads) + 1):
        B.cell(ws, tot, c, f"=SUM({B.col(c)}{first}:{B.col(c)}{last})", fmt="#,##0", bold=True)
    ws.cell(tot + 2, 2, "Demand as the design (demand.py, CPHEEO Table 2.7 S.No.4-6, 13): domestic x lpcd x (1 + losses) "
                        "+ floating x floating lpcd; pumping main / WTP / raw water on the demand without losses x the "
                        "Elmwood factors; fire 100 sqrt(P) of the town in the design year, shared by population "
                        "(P below 50,000: computed for 50,000).").font = B.italic
    ws.cell(tot + 3, 2, f"Bulk consumers (column {B.col(cb)}, yellow): KLD as given on the map, the same in every year; "
                        "in the demand without losses (J-L) and, with the distribution losses, in M-O - each at its own "
                        "peak factor in the design.").font = B.italic
    bulk = B.info.get("bulk") or []
    if bulk:
        r0 = tot + 5
        ws.cell(r0, 2, "BULK / INSTITUTIONAL CONSUMERS").font = B.bold
        B.header(ws, r0 + 1, ["Sl. No.", "Consumer", "Operation Zone", "Junction", "Demand (KLD)",
                              "With losses (KLD)", "Peak factor", "Distance to junction (m)"])
        for i, b in enumerate(bulk, 1):
            for c, v in enumerate([i, b["name"], b.get("oz") or "-", b["node"], b["kld"], b["kl"], b["peak"],
                                   b["dist_m"]], 1):
                B.cell(ws, r0 + 1 + i, c, v, fmt="#,##0.0" if c in (5, 6, 8) else ("0.00" if c == 7 else None))
    ws.freeze_panes = "D6"
    B.T1 = {"rows": ref, "total": tot, "fire_col": B.col(16 + 3 * len(fac)), "store_col": B.col(17 + 3 * len(fac)),
            "pm": [B.col(16 + j) for j in range(3)], "bulk_col": B.col(cb)}
    return B.T1


# ------------------------------------------------------------------------------------------------------------ Storage
def storage(B):
    """Mass balance of an OHT over a day (Elmwood 'T3' A.2): inflow while filling (yellow 0-1 for each hour, from the
    page's filling hours) at 24 / pumping hours, draw-off by the pattern; balancing capacity = max excess - max
    deficit, in hours of the average demand -> share of the daily demand; the larger of it and 33 % is taken."""
    from .. import demand as dm
    crit, PR = B.crit, B.PR
    ws = B.sheet("Storage", "CAPACITY OF OHT: MASS BALANCE (DRAW-OFF PATTERN) OR 33 % OF THE ULTIMATE DEMAND, THE LARGER", 9)
    B.header(ws, 5, ["From (h)", "To (h)", "Filling (share of the hour)", "Rate of inflow (x average)",
                     "Cumulative inflow", "Rate of draw-off (x average)", "Cumulative draw-off",
                     "Excess (+) / deficit (-)"], [9, 9, 12, 12, 12, 12, 12, 14])
    win = crit["oht_inflow_hours"]["value"]
    first = 6
    last = first + 23
    for h in range(24):
        x = first + h
        B.cell(ws, x, 1, h)
        B.cell(ws, x, 2, h + 1)
        B.cell(ws, x, 3, round(dm._on(win, h), 4), inp=True, fmt="0.00")
        B.cell(ws, x, 4, f"=C{x}*24/SUM($C${first}:$C${last})", fmt="0.00")
        B.cell(ws, x, 5, f"=D{x}" + (f"+E{x - 1}" if h else ""), fmt="0.00")
        B.cell(ws, x, 6, crit["draw_off_pattern"]["value"][h], inp=True, fmt="0.00")
        B.cell(ws, x, 7, f"=F{x}" + (f"+G{x - 1}" if h else ""), fmt="0.00")
        B.cell(ws, x, 8, f"=E{x}-G{x}", fmt="0.00")
    r = last + 2
    rows = [("Hours of filling", f"=SUM(C{first}:C{last})", "0.0"),
            ("Maximum excess (x average hourly demand)", f"=MAX(0,MAX(H{first}:H{last}))", "0.00"),
            ("Maximum deficit (x average hourly demand)", f"=MIN(0,MIN(H{first}:H{last}))", "0.00"),
            ("Balancing capacity = excess - deficit (hours of average demand)", f"=C{r + 1}-C{r + 2}", "0.00"),
            ("Mass balance: share of the daily demand", f"=C{r + 3}/24", "0.0%"),
            ("Minimum (33 % of the ultimate demand)", f"={PR['min_share']}", "0.0%"),
            ("Adopted share (the larger)", f"=MAX(C{r + 4},C{r + 5})", "0.0%")]
    for i, (lab, f, fmt) in enumerate(rows):
        ws.cell(r + i, 1, lab)
        ws.merge_cells(start_row=r + i, start_column=1, end_row=r + i, end_column=2)
        B.cell(ws, r + i, 3, f, fmt=fmt, bold=i == len(rows) - 1)
    ws.cell(r + len(rows) + 1, 1, crit["esr_capacity_share"]["ref"]).font = B.italic
    ws.cell(r + len(rows) + 2, 1, crit["oht_inflow_hours"]["ref"] + "; " + crit["draw_off_pattern"]["ref"]).font = B.italic
    B.share = f"Storage!$C${r + 6}"
    B.mass = f"Storage!$C${r + 4}"
    return B.share


# ------------------------------------------------------------------------------------------------------------ T3 (k)
def t3(B, k, z):
    """Technical statement of one OZ (Elmwood 'T3 (k)')."""
    PR, T1, P, S = B.PR, B.T1, B.S["pump"], B.S
    name = f"T3 ({k})"
    ws = B.sheet(name, f"TECHNICAL STATEMENT - OPERATION ZONE {z['name']}", 8)
    for c, w in zip("ABCDEFGH", (6, 54, 4, 14, 14, 14, 10, 60)):
        ws.column_dimensions[c].width = w
    x1 = T1["rows"][z["name"]]
    r = 5
    ws.cell(r, 2, "Name of the operation zone (OHT)")
    B.cell(ws, r, 4, z["name"], bold=True)
    ws.cell(r, 5, f"DMAs: {z['dmas']}")
    r += 2
    B.header(ws, r, ["Sl.No", "Description", "", "Base Year", "Middle Year", "Design Year", "Unit", "Note"])
    for c, kk in ((4, "base_year"), (5, "mid_year"), (6, "design_year")):
        B.cell(ws, r + 1, c, f'=""&{PR[kk]}', bold=True)
    r += 2
    ref = {}
    fac = list(S["demand_factors"])
    lines = [("pop", "Population", "D", "#,##0", "souls"),
             ("float", "Floating population", "G", "#,##0", "souls"),
             ("dem", "Total demand without losses", "J", "#,##0.0", "KLD"),
             ("dist", "Total demand for distribution network (10 % losses)", "M", "#,##0.0", "KLD"),
             ("pm", f"Total demand for {fac[0]}", "P", "#,##0.0", "KLD")]
    for i, (key, lab, c0, fmt, unit) in enumerate(lines, 1):
        B.cell(ws, r, 1, i)
        B.cell(ws, r, 2, lab)
        c0i = ord(c0) - 64
        for j in range(3):
            B.cell(ws, r, 4 + j, f"=T1!{B.col(c0i + j)}{x1}", fmt=fmt)
        B.cell(ws, r, 7, unit)
        ref[key] = r
        r += 1
    B.cell(ws, r, 1, len(lines) + 1)
    B.cell(ws, r, 2, "Fire demand of the OZ (design year)")
    B.cell(ws, r, 6, f"=T1!{T1['fire_col']}{x1}", fmt="#,##0.0")
    B.cell(ws, r, 7, "KLD")
    ws.cell(r, 8, B.crit["fire_formula"]["ref"])
    ref["fire"] = r
    r += 2

    # -------- pumps (+15 years), Elmwood rows 35-45
    ws.cell(r, 2, "REQUIREMENT OF PUMPS (CPHEEO Table 2.7 S.No.1 p168: pumping machinery for +15 years)").font = B.bold
    r += 1
    pr0 = r
    rows = [("Water demand for the pumping main", [f"=D{ref['pm']}", f"=E{ref['pm']}", f"=F{ref['pm']}"], "KLD", None),
            ("Pumping hours", [B.crit["tubewell_pumping_hours"]["value"], f"=D{r + 1}", f"=D{r + 1}"], "h",
             B.crit["tubewell_pumping_hours"]["ref"]),
            ("Required discharge of pumps", [f"=ROUND({c}{r}*1000/({c}{r + 1}*60),2)" for c in "DEF"], "LPM", None),
            ("Existing discharge of pumps", [0, f"=D{r + 3}", f"=D{r + 3}"], "LPM", "existing tube wells / pumps - fill in"),
            ("Proposed discharge of a pump", [B.crit["tubewell_discharge_lpm"]["value"], f"=D{r + 4}", f"=D{r + 4}"], "LPM",
             B.crit["tubewell_discharge_lpm"]["ref"]),
            ("Number of pumps needed", [f"=MAX(0,ROUNDUP(({c}{r + 2}-{c}{r + 3})/{c}{r + 4},0))" for c in "DEF"], "nos", None),
            ("Pumps proposed (middle year)", [f"=E{r + 6}", f"=E{r + 5}", f"=E{r + 6}"], "nos", "for +15 years"),
            ("Actual hours of pumping", [f"=IFERROR(ROUND({c}{r}*1000/(({c}{r + 6}*{c}{r + 4}+{c}{r + 3})*60),2),0)"
                                         for c in "DEF"], "h", None)]
    for i, (lab, vals, unit, note) in enumerate(rows):
        x = pr0 + i
        B.cell(ws, x, 1, i + 1)
        B.cell(ws, x, 2, lab)
        for j, v in enumerate(vals):
            B.cell(ws, x, 4 + j, v, fmt="#,##0.00", inp=(j == 0 and i in (1, 3, 4)))
        B.cell(ws, x, 7, unit)
        if note:
            ws.cell(x, 8, note)
    ref["q_pump"], ref["n_pump"], ref["hours"] = pr0 + 4, pr0 + 6, pr0 + 7
    r = pr0 + len(rows) + 1

    # -------- storage, Elmwood rows 48-118
    ws.cell(r, 2, "STORAGE (OHT) - CPHEEO Table 2.7 S.No.12 p175: mass balance or 33 % of the ultimate demand, the "
                  "larger; + one third of the fire demand (S.No.13 p176)").font = B.bold
    r += 1
    st0 = r
    rows = [("Ultimate demand of the OZ without fire (distribution network)", f"=F{ref['dist']}", "KLD",
             "the design's OZ demand (zoning) less its fire demand"),
            ("A.1  33 % of the ultimate demand", f"=F{r}*{PR['min_share']}", "KL", None),
            ("A.2  Mass balance (sheet Storage)", f"=F{r}*{B.mass}", "KL", "draw-off pattern and filling hours"),
            ("B    Fire storage: one third of the fire demand", f"=F{ref['fire']}*{PR['fire_share']}", "KL",
             "CPHEEO Table 2.7 S.No.13 p176-177: kept in the tank, the normal outlet just above it"),
            ("Capacity required = the larger of A.1 / A.2 + B", f"=MAX(F{r + 1},F{r + 2})+F{r + 3}", "KL", None),
            ("Existing capacity of OHT", z["capacity_kl"] or 0, "KL", "page (OHT on the map)"),
            ("Capacity of new OHT proposed",
             f"=IF(F{r + 5}>=F{r + 4},0,CEILING(F{r + 4}-F{r + 5},{PR['round_kl']}))", "KL",
             "the shortfall, rounded up: an existing OHT is kept, a new one makes up the rest (user 23-Nov-2026)")]
    for i, (lab, v, unit, note) in enumerate(rows):
        x = st0 + i
        B.cell(ws, x, 1, f"S.{i + 1}")
        B.cell(ws, x, 2, lab, bold=i == len(rows) - 1)
        B.cell(ws, x, 6, v, fmt="#,##0.0", inp=i == 5, bold=i == len(rows) - 1)
        B.cell(ws, x, 7, unit)
        if note:
            ws.cell(x, 8, note)
    ref["need"], ref["exist"], ref["new"] = st0 + 4, st0 + 5, st0 + 6
    x = st0 + len(rows)
    ws.cell(x, 2, f'=IF(AND(F{ref["exist"]}>0,F{ref["new"]}>0),"the existing OHT kept; the new one makes up the rest - '
                  f'both fill the OZ","")')
    ws.cell(x + 1, 8, f"zoning: {z['required_kl']:,.0f} KL required ({'existing' if z['existing'] else 'new'} OHT)")
    r = x + 3

    # -------- CWR (UPJN rule), CPHEEO 2.8.1.17 p127
    ws.cell(r, 2, "CWR (U.P. Jal Nigam rule: mandatory when more than 3 new tube wells fill one OHT; CPHEEO 2.8.1.17 "
                  "p127: 25 % of the ESR)").font = B.bold
    r += 1
    cw0 = r
    cap = f"(F{ref['exist']}+F{ref['new']})"          # the OZ's storage: the existing and the new OHT together
    cap1 = f"IF(F{ref['new']}>0,F{ref['new']},F{ref['exist']})"   # the tank the pumps fill: the new one where there is
    sw = B.S["swd"]

    def _cone_of(zz):          # the cone of a new Intze OHT below its wall's SWD (user decision 10-Nov-2026)
        from .. import intze
        kl = intze.new_kl(zz.get("required_kl"), zz.get("capacity_kl"),
                           B.crit["oht_capacity_round_kl"]["value"])   # the need, or the
        if not kl:                                     # shortfall rounded up (as S.7)
            return 0.0
        return round(intze.cone_depth(kl, next(d for c, d in sw if c is None or kl <= c)), 3)
    swd_of = lambda kl: f"IF({kl}<={sw[0][0]},{sw[0][1]},IF({kl}<={sw[1][0]},{sw[1][1]},{sw[2][1]}))"
    swd = swd_of(cap1)
    stg = z["staging_m"] if z["staging_m"] is not None else 0
    tw = 5 + k                     # this OZ's row of sheet TW: the proposed (L) tube wells
    rows = [("New tube wells filling the OHT (proposed)", f"=TW!L{tw}", "nos",
             "sheet TW: proposed (working) for +15 years; the existing ones stay with the existing structures, not "
             "counted (user decision 27-Oct-2026); the standby ones (sheet TW N) not counted - one of them fills "
             "the OHT only when a working one is out"),
            ("CWR required", f"=IF(F{r}>{PR['cwr_tw']},CEILING({cap}*{PR['cwr_share']},{PR['round_kl']}),0)", "KL", None),
            ("Existing capacity of CWR", 0, "KL", "fill in"),
            ("Capacity of new CWR proposed", f"=MAX(0,F{r + 1}-F{r + 2})", "KL", None),
            ("Water level of the CWR above ground - the tube wells fill it",
             f"=IF(F{r + 1}>0,{P['cwr_water_above_gl_m']},0)", "m",
             "a ground reservoir at the OHT; Riverside water DPR p136-195 'Calculation of static head': TW to CWR - "
             "staging 0, depth of water in tank 0 (user decision 6-Nov-2026); R3 'H P Calculation pp': tube wells of "
             "its CWR zones 37 m, of the others 64-72 m"),
            ("Head of the CWR pumps (to the OHT)", 0, "m",                 # its formula below (the T3 rows)
             f"staging + depth of water in OHT + terminal head + depth of the sump at the CWR {P['cwr_sump_m']:g} m + "
             f"friction of the CWR - OHT main {P['cwr_main_hf_m']:g} m (Riverside water DPR p136-196 'CWR to OHT', "
             "user decision 6-Nov-2026) - sheet EM TS")]
    for i, (lab, v, unit, note) in enumerate(rows):
        x = cw0 + i
        B.cell(ws, x, 1, f"C.{i + 1}")
        B.cell(ws, x, 2, lab, bold=i in (3, 5))
        B.cell(ws, x, 6, v, fmt="#,##0", inp=i == 2, bold=i in (3, 5))
        B.cell(ws, x, 7, unit)
        if note:
            ws.cell(x, 8, note)
    ref["cwr"], ref["cwr_d"], ref["cwr_head"] = cw0 + 3, cw0 + 4, cw0 + 5
    r = cw0 + len(rows) + 1

    # -------- pumping plant, Elmwood rows 139-166
    ws.cell(r, 2, "DESIGN OF PUMPING PLANT").font = B.bold
    r += 1
    pp0 = r
    # the friction of its new tube wells' rising mains (the highest, + minor losses - sheet RM Design), else the allowance
    rm = ((B.info.get("rising") or {}).get("oz") or {}).get(z["name"])
    fr = math.ceil(rm["friction_m"] * 2) / 2 if rm else P["friction_m"]
    fr_note = ("rising mains of the new tube wells: the highest friction (+ minor losses), sheet RM Design" if rm else
               "allowance - no new tube well (existing rising mains)")
    rows = [("Depth of water below ground level", P["water_below_gl_m"], "m",
             "of the tube well - Riverside water DPR p130-196 (user decision 6-Nov-2026)"),
            ("Seasonal variation", P["seasonal_m"], "m", None),
            ("Depression during pumping", P["depression_m"], "m", None),
            ("Staging of OHT", stg, "m", "the design" + (f" (+{z['vfd_head_m']:g} m VFD pump at the outlet)"
                                                        if z.get("vfd_head_m") else "")),
            ("Depth of water in OHT", f"={swd}" + (f"+IF(F{ref['new']}>0,{_cone_of(z)},0)" if _cone_of(z) else ""), "m",
             "CPHEEO Table 2.7 S.No.12 p175 (side water depth at the wall)" + (
                 f" + {_cone_of(z):.2f} m cone below it of a new Intze OHT (intze.py, user decision 10-Nov-2026)"
                 if _cone_of(z) else "")),
            ("Frictional losses in rising main and pumping plant", fr, "m", fr_note),
            ("Terminal head", P["terminal_m"], "m", None),
            ("Total head", f"=IF(F{cw0 + 1}>0,F{r}+F{r + 1}+F{r + 2}+F{ref['cwr_d']}+F{r + 5}+F{r + 6},SUM(F{r}:F{r + 6}))",
             "m", "where a CWR (C.2): to the CWR (C.5) in place of the staging and the OHT's depth - its pumps lift "
                  "to the OHT (C.6)"),
            ("Say", f"=ROUNDUP(F{r + 7},0)", "m", None),
            ("Recommended discharge of a pump", f"=D{ref['q_pump']}", "LPM", None),
            ("H.P. of pumping plant = Q x H / 4500", f"=ROUND(F{r + 9}*F{r + 8}/4500,2)", "HP", None),
            ("Efficiency of pump", P["efficiency"], "", "Elmwood 'T3 (1)' Q159"),
            ("H.P. input to pump", f"=ROUND(F{r + 10}/F{r + 11},2)", "HP", None),
            ("Margin on the motor", f"={motor_margin(P, f'F{r + 12}*0.746')}", "",
             "by the motor's kW, the CPHEEO table of the Riverside water DPR p360 (user decision 6-Nov-2026)"),
            ("Required capacity of the motor", f"=ROUND(F{r + 12}*(1+F{r + 13}),2)", "HP", None),
            ("Motor provided", f"=CEILING(F{r + 14},5)", "BHP", None)]
    for i, (lab, v, unit, note) in enumerate(rows):
        x = pp0 + i
        B.cell(ws, x, 1, i + 1)
        B.cell(ws, x, 2, lab, bold=i in (8, 15))
        fmt = "0%" if i in (11, 13) else "#,##0.00"
        B.cell(ws, x, 6, v, fmt=fmt, inp=i in (0, 1, 2, 5, 6, 11), bold=i in (8, 15))
        B.cell(ws, x, 7, unit)
        if note:
            ws.cell(x, 8, note)
    ref["head"], ref["bhp"] = pp0 + 8, pp0 + 15
    B.cell(ws, ref["cwr_head"], 6, f"=IF(F{cw0 + 1}>0,ROUNDUP(F{pp0 + 3}+F{pp0 + 4}+F{pp0 + 6}+{P['cwr_sump_m']}"
                                   f"+{P['cwr_main_hf_m']},0),0)", fmt="#,##0", bold=True)
    r = pp0 + len(rows) + 1

    # -------- chlorine, Elmwood rows 170-185
    ws.cell(r, 2, "REQUIREMENT OF CHLORINE (middle year)").font = B.bold
    r += 1
    c0 = r
    rows = [("Discharge of the pumps", f"=E{ref['n_pump']}*E{ref['q_pump']}", "LPM"),
            ("Hours of pumping", f"=E{ref['hours']}", "h"),
            ("Average dose of chlorine", P["chlorine_ppm"], "ppm"),
            ("Chlorine required per day", f"=ROUND(F{r}*F{r + 1}*60*F{r + 2}/1000000,2)", "kg"),
            ("Strength of sodium hypochlorite solution", P["hypo_strength"], ""),
            ("Sodium hypochlorite required per day", f"=ROUND(F{r + 3}/F{r + 4},2)", "litre")]
    for i, (lab, v, unit) in enumerate(rows):
        x = c0 + i
        B.cell(ws, x, 1, i + 1)
        B.cell(ws, x, 2, lab)
        B.cell(ws, x, 6, v, fmt="0%" if i == 4 else "#,##0.00", inp=i in (2, 4))
        B.cell(ws, x, 7, unit)
    r = c0 + len(rows) + 1
    B.sign(ws, r + 1, 6)
    B.T3.append({"sheet": name, "zone": z, "ref": ref})
    return ref


# ------------------------------------------------------------------------------------------------------------ Summary, TW
def summary(B):
    ws = B.sheet("Summary", "SUMMARY - EXISTING & PROPOSED DETAILS OF O.H.T., C.W.R. AND TUBE WELLS", 13)
    B.header(ws, 5, ["S. No.", "Operation zone", "Existing T.W. (nos)", "Existing OHT (KL)", "Existing CWR (KL)",
                     "Proposed T.W. incl. standby (nos)", "Proposed OHT (KL)", "Proposed CWR (KL)", "OHT existing + proposed (KL)",
                     "CWR existing + proposed (KL)", "Staging (m)", "T.W. total incl. rebore (nos)"],
             [6, 22, 11, 11, 11, 11, 11, 11, 13, 13, 10, 11])
    ws.row_dimensions[5].height = 45
    first = 6
    for i, t in enumerate(B.T3):
        x, s, rf = first + i, q(t["sheet"]), t["ref"]
        cw = rf["cwr"]
        vals = [i + 1, t["zone"]["name"], f"=TW!C{6 + i}", f"={s}!F{rf['exist']}", f"={s}!F{cw - 1}", f"=TW!O{6 + i}",
                f"={s}!F{rf['new']}", f"={s}!F{cw}", f"=D{x}+G{x}", f"=E{x}+H{x}", f"={s}!F{rf['head'] - 5}",
                f"=C{x}+F{x}+TW!P{6 + i}"]
        for c, v in enumerate(vals, 1):
            B.cell(ws, x, c, v, fmt="#,##0" if c > 2 else None)
    last = first + len(B.T3) - 1
    B.cell(ws, last + 1, 2, "Total", bold=True)
    for c in range(3, 13):
        if c != 11:
            B.cell(ws, last + 1, c, f"=SUM({B.col(c)}{first}:{B.col(c)}{last})", fmt="#,##0", bold=True)
    B.sign(ws, last + 4, 10)
    B.SUM = {"first": first, "last": last}


def tube_wells(B):
    """Tube wells needed for +15 years (Elmwood 'TW'): requirement of the pumping main less what the existing tube
    wells give, by tube wells of the proposed discharge."""
    ws = B.sheet("TW", "REQUIREMENT OF WATER & TUBE WELLS (middle year, +15)", 16)
    B.header(ws, 5, ["S. No.", "Operation zone", "Existing T.W. (nos)", "Discharge of an existing T.W. (LPM)",
                     "Pumping hours", "Available from existing T.W. (KLD)", "Requirement, pumping main +15 (KLD)",
                     "Net requirement (KLD)", "Discharge of a proposed T.W. (LPM)", "T.W. required",
                     "", "T.W. proposed (nos)", "Actual hours of pumping", "Standby T.W. (CPHEEO 5.7.5)",
                     "T.W. to be constructed (proposed + standby)", "Rebore T.W. (nos) - map"],
             [6, 22, 11, 13, 9, 13, 14, 13, 13, 11, 2, 11, 12, 12, 14, 11])
    ws.row_dimensions[5].height = 60
    for i, t in enumerate(B.T3):
        x, s, rf = 6 + i, q(t["sheet"]), t["ref"]
        z = t["zone"]
        vals = [i + 1, z["name"], z["tubewells"],
                B.crit["existing_tubewell_lpm"]["value"] if z["tubewells"] or z.get("rebore") else 0,
                f"={s}!E{rf['q_pump'] - 3}", f"=(C{x}+P{x})*D{x}*E{x}*60/1000", f"={s}!E{rf['q_pump'] - 4}",
                f"=MAX(0,G{x}-F{x})", B.crit["tubewell_discharge_lpm"]["value"], f"=H{x}*1000/(I{x}*E{x}*60)", None,
                f"=ROUNDUP(J{x},0)", f"=IFERROR(G{x}*1000/(((C{x}+P{x})*D{x}+L{x}*I{x})*60),0)",
                "=" + standby(f"L{x}", (B.crit.get("standby_tubewells") or B.crit["standby_pumps"])["value"]),
                f"=L{x}+N{x}", z.get("rebore") or 0]
        for c, v in enumerate(vals, 1):
            if c == 11:
                continue
            B.cell(ws, x, c, v, fmt="#,##0.00" if c in (10, 13) else ("#,##0" if c > 2 else None),
                   inp=c in (3, 4, 9, 16))
    x = 6 + len(B.T3) + 1
    ws.cell(x, 2, f"Existing tube wells: the number given on the map, {B.crit['existing_tubewell_lpm']['value']:g} LPM "
                  f"each ({B.crit['existing_tubewell_lpm']['ref']}) - fill in; proposed tube well "
                  f"{B.crit['tubewell_discharge_lpm']['value']:g} LPM. CWR: only the proposed ones counted (T14 C.1), as the "
                  "zoning.").font = B.italic
    ws.cell(x + 1, 2, "Standby tube wells (N) as CPHEEO water manual Part A 5.7.5 p245-246 for the working ones (L): "
                      "1-2 + 1, 3-5 + 2, 6-10 + 3 (user decision 7-Nov-2026) - each built whole as a new one (boring, "
                      "pump house, pumping plant, power connection, its rising main); the pumping hours (M), the CWR "
                      "rule and the energy count the working ones. Rebore (P, from the map): an existing tube well "
                      "rebored, giving as an existing one; no pump house (a girder pillar, sheet C1) and no new power "
                      "connection (its LT cable to the existing pump house, sheet E2) - user 7-Nov-2026, as the "
                      "Riverside R3 (40 new / 2 rebore).").font = B.italic
    B.sign(ws, x + 4, 12)
