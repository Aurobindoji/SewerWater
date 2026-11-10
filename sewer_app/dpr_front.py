"""The front sheets of the sewer DPR workbook (dpr.py) - user request 22-Oct-2026:

    project(B, ...)     sheet 'Project', the first sheet: every text that repeats or does not change (name of the scheme,
                        ULB, district, programme, offices, names of the officers, years) and the population inputs of
                        the page. Every other sheet takes them from here by formula, so a change here changes them all.
                        The texts the user typed into the Project sheet of the previous DPR of the project are kept.
    tech(B, ...)        Technical statement (Riverside 'T' / 'Tech '): design period, census, the three methods of
                        population projection, the adopted population, floating population, sewage, house connections,
                        the zones' flows and the sewer network
    coverage(B, ...), certificate(B), index(B, ...), bar_chart(B)     as the Riverside sheets of the same names
"""
import os

# the Project sheet: (key, label, default) - row = 4 + position; column C holds the value
TEXTS = [("title", "Name of the scheme", ""), ("ulb", "Name of the ULB / town", ""), ("district", "District", ""),
         ("under", "Programme (UNDER ...)", ""), ("office", "Office (division)", ""), ("circle", "Circle", ""),
         ("zone", "Zone (Chief Engineer's office)", ""),
         ("ae", "Assistant Engineer (Civil) - name", ""), ("ee", "Executive Engineer (Civil) - name", ""),
         ("se", "Superintending Engineer (Civil) - name", ""), ("ce", "Chief Engineer - name", ""),
         ("ae_em", "Assistant Engineer (E&M) - name", ""), ("ee_em", "Executive Engineer (E&M) - name", ""),
         ("se_em", "Superintending Engineer (E&M) - name", ""), ("computer", "Computer / checked by - name", "")]
COVER = [("hh_census", "Households of the city as per the last census", None),
         ("hh_base", "Households of the city in the base year", None),
         ("hh_before", "Households with sewer connections before AMRUT 1.0", None),
         ("hh_amrut1", "Households connected under AMRUT 1.0", None),
         ("hh_amrut2", "Households with connections already sanctioned under AMRUT 2.0", None)]
BAR = [("Bid Process Management (BPM)", 1, 3), ("Taking permissions from different departments", 3, 6),
       ("Laying of sewer lines", 4, 19), ("House sewer connections", 10, 21), ("Testing and trial run", 22, 24)]


def _previous(path):
    """{key: value} of the Project sheet of an earlier DPR (the texts the user typed there), or {}."""
    if not path or not os.path.isfile(path):
        return {}
    try:
        import openpyxl
        ws = openpyxl.load_workbook(path, read_only=True)["Project"]
        rows = {r[1]: r[2] for r in ws.iter_rows(min_row=1, max_row=80, max_col=3, values_only=True) if r[1]}
    except Exception:
        return {}
    out = {}
    for key, label, _ in TEXTS + COVER:
        v = rows.get(label)
        if v not in (None, "") and not (isinstance(v, str) and v.startswith("=")):
            out[key] = v
    return out


def project(B, f, inp, title, previous=None):
    """The Project sheet. f = population.forecast of the design (or None). Returns {key: absolute cell}."""
    S = B.S
    old = _previous(previous)
    ws = B.wb.create_sheet("Project")
    ws.cell(1, 1, "PROJECT - the texts and inputs used on every sheet of this DPR").font = B.big
    ws.cell(2, 1, "Fill / change here (yellow): every sheet takes these by formula. Texts typed here are kept when the "
                  "DPR is made again from the app.").font = B.italic
    for c, w in zip("ABCD", (6, 52, 46, 70)):
        ws.column_dimensions[c].width = w
    ref = {}
    defaults = {"title": title, "district": S.get("district") or "", "under": S.get("scheme_under") or "",
                "office": S.get("office") or ""}
    r = 4
    for key, label, _ in TEXTS:
        ws.cell(r, 2, label)
        c = ws.cell(r, 3, old.get(key, defaults.get(key, "")))
        c.fill = B.yellow
        if key == "title":
            c.font = B.bold
            if old.get("title") and old["title"] != title:
                ws.cell(r, 4, f"(name kept from the previous DPR; the app's project name is '{title}')")
        ref[key] = f"Project!$C${r}"
        r += 1
    r += 1
    ws.cell(r, 2, "Years and population (from the app's design)").font = B.bold
    r += 1
    y0 = (f or {}).get("base_year") or inp.get("base_year") or 2027
    rows = [("base_year", "Base year", int(y0), "page: आधार वर्ष"),
            ("mid_year", "Middle year (+15)", f"=C{r}+15", "CPHEEO Table 2.1 (p2-9)"),
            ("design_year", "Design year (+30)", f"=C{r}+30", "sewers: 30 years"),
            ("base_pop", "Population in the base year (without floating)",
             (f or {}).get("pop", {}).get("init") or inp.get("pop_initial") or inp.get("pop_total"), "page: आधार वर्ष की आबादी"),
            ("method", "Population forecast: method adopted", (f or {}).get("method") or "geometrical",
             "arithmetical / incremental / geometrical (Riverside: geometrical)"),
            ("default_rate", "Decadal growth rate when no census is given", S["forecast"]["default_decadal_rate"],
             "Riverside 'T' U55 (Springfield City Council)"),
            ("floating", "Floating and institutional population (share)", S["forecast"]["floating_share"],
             "Riverside 'Tech ' row 132"),
            ("floating_lpcd", "Floating population: water supply (lpcd)", S["forecast"]["floating_lpcd"],
             "Riverside 'Tech ' row 133 (45 / 150)"),
            ("sewage_lpcd", "Sewage (lpcd) - design", float(inp.get("sewage_lpcd") or 0), "page"),
            ("return_factor", "Return factor (sewage / water supply)", S["forecast"]["return_factor"],
             "Riverside 'Tech ' row 137"),
            ("water_lpcd", "Water supply (lpcd) = sewage / return factor", None, ""),
            ("hh_size", "Persons per household", S["population"]["persons_per_household"], "Riverside 'Tech ' X108")]
    for key, label, val, note in rows:
        ws.cell(r, 2, label)
        if key == "water_lpcd":
            val = f"={ref['sewage_lpcd'].replace('Project!', '')}/{ref['return_factor'].replace('Project!', '')}"
        c = ws.cell(r, 3, val)
        if key not in ("mid_year", "design_year", "water_lpcd"):
            c.fill = B.yellow
        if key == "default_rate" or key == "floating" or key == "return_factor":
            c.number_format = "0.00%"
        if key == "base_pop":
            c.number_format = "#,##0"
        ws.cell(r, 4, note)
        ref[key] = f"Project!$C${r}"
        r += 1
    ws.cell(r, 4, "The design ran on the population of the app (page): a change in the yellow population cells "
                  "changes the Technical statement and the economics here, not the design - make the design again "
                  "from the app for that.").font = B.red
    r += 2
    ws.cell(r, 2, "Census population of the town (page)").font = B.bold
    r += 1
    ws.cell(r, 2, "Year")
    ws.cell(r, 3, "Population")
    r += 1
    census = list((f or {}).get("census") or [])
    first = r
    for y, p in census:
        ws.cell(r, 2, int(y)).fill = B.yellow
        c = ws.cell(r, 3, p)
        c.fill, c.number_format = B.yellow, "#,##0"
        r += 1
    ref["census"] = (first, r - 1)
    if not census:
        ws.cell(r, 2, "no census given on the page - the default decadal rate is used")
        r += 1
    r += 1
    ws.cell(r, 2, "Coverage of the city (sheet Coverage)").font = B.bold
    r += 1
    for key, label, _ in COVER:
        ws.cell(r, 2, label)
        c = ws.cell(r, 3, old.get(key))
        c.fill, c.number_format = B.yellow, "#,##0"
        ref[key] = f"Project!$C${r}"
        r += 1
    for row in ws.iter_rows(min_row=4, max_row=r, max_col=3):
        for cell in row:
            if cell.value is not None or cell.fill == B.yellow:
                cell.border = B.box
    return ref


def tech(B, PR, f, inp, out, ps, ref, dias):
    """Technical statement. Returns the cells of the adopted population (without floating) and the households."""
    ws = B.sheet("Tech", "TECHNICAL STATEMENT", 9)
    for c, w in zip("ABCDEFGHI", (6, 30, 14, 14, 14, 14, 14, 14, 40)):
        ws.column_dimensions[c].width = w
    ws.cell(3, 1, f"=IF({PR['under']}=\"\",\"\",\"UNDER: \"&{PR['under']})&IF({PR['district']}=\"\",\"\",\"   DISTRICT- \"&{PR['district']})")
    r = 5
    ws.cell(r, 1, "1.").font = B.bold
    ws.cell(r, 2, "DESIGN PERIOD").font = B.bold
    r += 1
    ws.cell(r, 2, f'="Based on the prevalent norms (CPHEEO Manual, Table 2.1, p2-9) the design period has been adopted as '
                  f'30 years: the initial year is "&{PR["base_year"]}&", the prospective (middle) year "&{PR["mid_year"]}'
                  f'&" and the ultimate year "&{PR["design_year"]}&"."')
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=9)
    ws.cell(r, 2).alignment = B.wrap
    ws.row_dimensions[r].height = 30
    r += 2
    ws.cell(r, 1, "2.").font = B.bold
    ws.cell(r, 2, "POPULATION PROJECTION").font = B.bold
    r += 1
    c0, c1 = PR["census"]
    n = c1 - c0 + 1 if c1 >= c0 else 0
    B.header(ws, r, ["S.N.", "Census year", "Population", "Increase per decade", "Incremental increase",
                     "Decadal growth rate"])
    r += 1
    top = r
    for i in range(n):
        x = r + i
        ws.cell(x, 1, i + 1)
        ws.cell(x, 2, f"=Project!B{c0 + i}")
        ws.cell(x, 3, f"=Project!C{c0 + i}").number_format = "#,##0"
        if i:
            ws.cell(x, 4, f"=(C{x}-C{x - 1})/((B{x}-B{x - 1})/10)").number_format = "#,##0"
            ws.cell(x, 6, f"=(C{x}/C{x - 1})^(1/((B{x}-B{x - 1})/10))-1").number_format = "0.00%"
        if i > 1:
            ws.cell(x, 5, f"=D{x}-D{x - 1}").number_format = "#,##0"
    r += max(n, 1)
    bot = r - 1
    ws.cell(r, 2, "Average").font = B.bold
    X = f"D{r}"
    if n >= 2:
        ws.cell(r, 4, f"=AVERAGE(D{top + 1}:D{bot})").number_format = "#,##0.00"
        ws.cell(r, 5, f"=IFERROR(AVERAGE(E{top + 2}:E{bot}),0)" if n >= 3 else 0).number_format = "#,##0.00"
        ws.cell(r, 6, f"=IF(MIN(F{top + 1}:F{bot})>0,PRODUCT(F{top + 1}:F{bot})^(1/COUNT(F{top + 1}:F{bot})),"
                      f"AVERAGE(F{top + 1}:F{bot}))").number_format = "0.00%"
        ws.cell(r, 9, "X = average increase per decade, Y = average incremental increase, r = geometric mean of the "
                      "decadal rates (Riverside 'T' L54, P54, U54)")
    else:
        ws.cell(r, 4, "-")
        ws.cell(r, 5, 0)
        ws.cell(r, 6, f"={PR['default_rate']}").number_format = "0.00%"
        ws.cell(r, 9, "no census: default decadal rate (Project)")
    Xc, Yc, Rc = f"$D${r}", f"$E${r}", f"$F${r}"
    r += 2
    B.header(ws, r, ["", "Method", "", "Base year", "Middle year", "Design year", "", "", "Formula"])
    for j, key in enumerate(("base_year", "mid_year", "design_year")):
        ws.cell(r, 4 + j, f"={PR[key]}")
    r += 1
    mtop = r
    forms = [("arithmetical", "Arithmetical increase", "P0 + n X", lambda nn: f"CEILING({PR['base_pop']}+{nn}*{Xc},5)"),
             ("incremental", "Incremental increase", "P0 + n X + n (n+1) / 2 Y",
              lambda nn: f"CEILING({PR['base_pop']}+{nn}*{Xc}+{nn}*({nn}+1)*0.5*{Yc},5)"),
             ("geometrical", "Geometrical increase", "P0 (1 + r)^n", lambda nn: f"CEILING({PR['base_pop']}*(1+{Rc})^{nn},5)")]
    for key, name, txt, fn in forms:
        ws.cell(r, 1, key)
        ws.cell(r, 2, name)
        ws.cell(r, 4, f"={PR['base_pop']}").number_format = "#,##0"
        for j, yk in enumerate(("mid_year", "design_year")):
            nn = f"(({PR[yk]}-{PR['base_year']})/10)"
            ok = n >= 2 or key == "geometrical"
            ws.cell(r, 5 + j, f"={fn(nn)}" if ok else "-").number_format = "#,##0"
        ws.cell(r, 9, f"{txt}; n = decades after the base year")
        r += 1
    ws.cell(r, 2, "Adopted").font = B.bold
    ws.cell(r, 3, f"={PR['method']}")
    for j in range(3):
        c = B.col(4 + j)
        ws.cell(r, 4 + j, f"=INDEX({c}{mtop}:{c}{r - 1},MATCH({PR['method']},$A${mtop}:$A${r - 1},0))").number_format = "#,##0"
        ws.cell(r, 4 + j).font = B.bold
    adopted = r
    r += 2
    ws.cell(r, 1, "3.").font = B.bold
    ws.cell(r, 2, "FLOATING POPULATION AND SEWAGE").font = B.bold
    r += 1
    B.header(ws, r, ["S.N.", "Description", "", "Base year", "Middle year", "Design year"])
    for j, key in enumerate(("base_year", "mid_year", "design_year")):
        ws.cell(r, 4 + j, f"={PR[key]}")
    r += 1
    lines = [("Population (adopted)", lambda c: f"={c}{adopted}", "#,##0"),
             ("Floating and institutional population", lambda c: f"=ROUND({c}{{p}}*{PR['floating']},0)", "#,##0"),
             ("Equivalent floating population (x floating lpcd / water supply lpcd)",
              lambda c: f"=ROUND({c}{{fl}}*{PR['floating_lpcd']}/{PR['water_lpcd']},0)", "#,##0"),
             ("Total population for sewage (design)", lambda c: f"={c}{{p}}+{c}{{eq}}", "#,##0"),
             ("Sewage (lpcd)", lambda c: f"={PR['sewage_lpcd']}", "0"),
             ("Average sewage (MLD)", lambda c: f"=ROUND({c}{{tot}}*{c}{{lpcd}}/1000000,2)", "0.00")]
    at = {}
    keys = ["p", "fl", "eq", "tot", "lpcd", "mld"]
    for i, (name, fn, fmt) in enumerate(lines):
        ws.cell(r, 1, i + 1)
        ws.cell(r, 2, name)
        at[keys[i]] = r
        for j in range(3):
            c = B.col(4 + j)
            ws.cell(r, 4 + j, fn(c).format(**at)).number_format = fmt
        r += 1
    ws.cell(r, 2, "The design (sizes, flows) ran on these totals as computed by the app (population.py, same rules).")
    r += 2
    ws.cell(r, 1, "4.").font = B.bold
    ws.cell(r, 2, "HOUSEHOLDS AND HOUSE CONNECTIONS").font = B.bold
    r += 1
    ws.cell(r, 2, "Households = population / persons per household")
    for j in range(3):
        c = B.col(4 + j)
        ws.cell(r, 4 + j, f"=ROUND({c}{at['p']}/{PR['hh_size']},0)").number_format = "#,##0"
    hh = r
    r += 1
    ws.cell(r, 2, f'="Hence, sewer house connections = "&TEXT(D{hh},"#,##0")&" Nos (households of the base year)"')
    r += 2
    ws.cell(r, 1, "5.").font = B.bold
    ws.cell(r, 2, "ZONES (OUTFALLS) - FLOWS OF THE DESIGN").font = B.bold
    r += 1
    B.header(ws, r, ["S.N.", "Outfall", "Role", "Pop. base", "Pop. middle", "Pop. design", "Avg (MLD) design",
                     "Peak (L/s) design", "Note"])
    r += 1
    by = {st["stage"]: {o["outfall"]: o for o in st["outfalls"]} for st in out.get("stages") or []}
    sps = {s["outfall"]: n for s, n in zip((ps or {}).get("stations", []), (ps or {}).get("names", []))}
    for i, o in enumerate(sorted(by.get("ult", {}))):
        ws.cell(r, 1, i + 1)
        ws.cell(r, 2, o)
        ws.cell(r, 3, f"pumping station {sps[o]}" if o in sps else "STP / gravity")
        for j, tg in enumerate(("init", "mid", "ult")):
            x = by.get(tg, {}).get(o)
            ws.cell(r, 4 + j, x["pop"] if x else None).number_format = "#,##0"
        u = by["ult"][o]
        ws.cell(r, 7, u["avg_mld"]).number_format = "0.00"
        ws.cell(r, 8, u["peak_lps"]).number_format = "0.00"
        r += 1
    r += 1
    ws.cell(r, 1, "6.").font = B.bold
    ws.cell(r, 2, "SEWER NETWORK").font = B.bold
    r += 1
    B.header(ws, r, ["S.N.", "Diameter", "Length (m)"])
    r += 1
    for i, D in enumerate(dias):
        ws.cell(r, 1, i + 1)
        ws.cell(r, 2, f"{D} mm")
        ws.cell(r, 3, f"={ref['len'][D]}").number_format = "#,##0.0"
        r += 1
    ws.cell(r, 2, "Total").font = B.bold
    ws.cell(r, 3, f"={ref['len_total']}").number_format = "#,##0.0"
    r += 1
    ws.cell(r, 2, "Manholes (Nos)")
    ws.cell(r, 3, "=" + "+".join(ref["mh_n"])).number_format = "#,##0"
    r += 1
    ws.cell(r, 2, "Pumping stations (Nos)")
    ws.cell(r, 3, len((ps or {}).get("names", [])))
    return {"pop": [f"Tech!D{adopted}", f"Tech!E{adopted}", f"Tech!F{adopted}"],
            "hh": [f"Tech!D{hh}", f"Tech!E{hh}", f"Tech!F{hh}"], "design": [f"Tech!{c}{at['tot']}" for c in "DEF"]}


def coverage(B, PR, hc_count):
    ws = B.sheet("Coverage", "Sewer House Connections - Coverage Status of the City", 4)
    for c, w in zip("ABCD", (7, 80, 16, 10)):
        ws.column_dimensions[c].width = w
    B.header(ws, 4, ["S. No.", "Description", "Nos", "%"])
    rows = [("Total No. of households as per the last census", f"={PR['hh_census']}", False),
            ("Total No. of households in the base year", f"={PR['hh_base']}", False),
            ("Households with sewer connections before AMRUT 1.0", f"={PR['hh_before']}", True),
            ("No. of households having sewer connections sanctioned and completed under AMRUT 1.0", f"={PR['hh_amrut1']}", True),
            ("No. of households having sewer connections already sanctioned under AMRUT 2.0", f"={PR['hh_amrut2']}", True),
            ("No. of sewer connections proposed in this DPR", f"={hc_count}", True)]
    for i, (name, v, pct) in enumerate(rows):
        x = 5 + i
        ws.cell(x, 1, i + 1)
        ws.cell(x, 2, name)
        ws.cell(x, 3, v).number_format = "#,##0"
        if pct:
            ws.cell(x, 4, f"=IFERROR(C{x}/$C$6,0)").number_format = "0.00%"
    ws.cell(11, 1, 7)
    ws.cell(11, 2, "Households with sewer connections after execution of the AMRUT projects (S.No. 3+4+5+6)")
    ws.cell(11, 3, "=SUM(C7:C10)").number_format = "#,##0"
    ws.cell(11, 4, "=IFERROR(C11/$C$6,0)").number_format = "0.00%"
    ws.cell(12, 1, 8)
    ws.cell(12, 2, "Remaining households without sewer connections after execution of the AMRUT projects")
    ws.cell(12, 3, "=C6-C11").number_format = "#,##0"
    ws.cell(12, 4, "=IFERROR(C12/$C$6,0)").number_format = "0.00%"
    for row in ws.iter_rows(min_row=4, max_row=12, max_col=4):
        for cell in row:
            cell.border = B.box
    ws.cell(14, 2, "Figures of the city: sheet Project (yellow).").font = B.italic


def certificate(B, PR):
    ws = B.wb.create_sheet("Certificate")
    ws.column_dimensions["A"].width = 46
    ws.column_dimensions["C"].width = 46
    ws.cell(1, 1, f"={PR['title']}").font = B.big
    ws.cell(3, 1, f'=IF({PR["district"]}="","","DISTRICT- "&{PR["district"]})')
    ws.cell(5, 1, "Certificate").font = B.big
    ws.cell(7, 1, f'="          This is to certify that the provisions / works included under this detailed project report of '
                  f'"&{PR["title"]}&IF({PR["under"]}="",""," UNDER "&{PR["under"]})&" have neither been incorporated in any '
                  f'other DPR of the programme and have not been executed in part or in full under any other DPR / programme."')
    ws.merge_cells("A7:C8")
    ws.cell(7, 1).alignment = B.wrap
    ws.row_dimensions[7].height = 45
    for x, (a, b) in enumerate(((PR["ae"], PR["ee"]),), start=10):
        ws.cell(x, 1, f'=IF({a}="","","(Er. "&{a}&")")')
        ws.cell(x, 3, f'=IF({b}="","","(Er. "&{b}&")")')
    ws.cell(11, 1, "Assistant Engineer")
    ws.cell(11, 3, "Executive Engineer")
    ws.cell(12, 1, f'=""&{PR["office"]}')
    ws.cell(16, 1, f'=IF({PR["se"]}="","","(Er. "&{PR["se"]}&")")')
    ws.cell(17, 1, "Superintending Engineer")
    ws.cell(18, 1, f'=""&{PR["circle"]}')
    ws.cell(21, 1, "Countersigned")
    ws.cell(25, 1, f'=IF({PR["ce"]}="","","(Er. "&{PR["ce"]}&")")')
    ws.cell(26, 1, "Chief Engineer")
    ws.cell(27, 1, f'=""&{PR["zone"]}')


def index(B, entries):
    """entries = [(number, description, sheet name)] in the order of the workbook."""
    ws = B.sheet("Index", "INDEX", 5)
    for c, w in zip("ABCDE", (8, 70, 34, 10, 10)):
        ws.column_dimensions[c].width = w
    B.header(ws, 4, ["Sl. No.", "Particulars", "Sheet", "Page from", "Page to"])
    for i, (no, desc, name) in enumerate(entries):
        x = 5 + i
        ws.cell(x, 1, no)
        ws.cell(x, 2, desc)
        ws.cell(x, 3, name)
        ws.cell(x, 4).fill = B.yellow
        ws.cell(x, 5).fill = B.yellow
        for c in range(1, 6):
            ws.cell(x, c).border = B.box


def bar_chart(B):
    from openpyxl.styles import PatternFill
    ws = B.sheet("Bar Chart", "PROJECT IMPLEMENTATION SCHEDULE", 26)
    ws.column_dimensions["A"].width = 5
    ws.column_dimensions["B"].width = 44
    B.header(ws, 4, ["S N", "Name of Activity"] + [m for m in range(1, 25)])
    for c in range(3, 27):
        ws.column_dimensions[B.col(c)].width = 4
    ws.cell(3, 3, "MONTH").font = B.bold
    blue = PatternFill("solid", fgColor="5B9BD5")
    for i, (name, a, b) in enumerate(BAR):
        x = 5 + i
        ws.cell(x, 1, i + 1)
        ws.cell(x, 2, name)
        for m in range(a, b + 1):
            ws.cell(x, 2 + m).fill = blue
        for c in range(1, 27):
            ws.cell(x, c).border = B.box
    ws.cell(11, 2, "As the Riverside DPR (24 months: BPM 1-3, construction 4-21, trial run 22-24).").font = B.italic


def signatures(ws, x, PR, em=False):
    """The signature block of a Form J (names from the Project sheet): prepared / checked / recommended / approved."""
    def name(k, k2=None):
        f = f'IF({PR[k]}="","","("&{PR[k]}&")")'
        if k2:
            f = f'{f}&IF({PR[k2]}="","","/("&{PR[k2]}&")")'
        return "=" + f
    rows = [("Prepared by", None),
            (name("ae", "ae_em" if em else None), name("ee", "ee_em" if em else None)),
            ("Assistant Engineer" + (" (Civil) / (E&M)" if em else ""), "Executive Engineer" + (" (Civil) / (E&M)" if em else "")),
            ("", ""), ("Checked", "Recommended"),
            (name("computer"), name("se", "se_em" if em else None)),
            ("Computer", "Superintending Engineer" + (" (Civil) / (E&M)" if em else "")),
            ("", ""), ("Approved", None), (name("ce"), None), ("Chief Engineer", None), (f'=""&{PR["zone"]}', None)]
    for a, b in rows:
        ws.cell(x, 1, a)
        if b is not None:
            ws.cell(x, 4, b)
        x += 1
    return x
