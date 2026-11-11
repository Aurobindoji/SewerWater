"""Sewer DPR workbook (Excel) in the format of the Riverside Zone Sewerage Scheme estimate of U.P. Jal Nigam (City Council
Springfield; sample hydraulic_design_data_sheet_sample\\Copy of Riverside SewerEstimate.xlsx) - user request 22-Oct-2026: the DPR
as Excel sheets, in that format with live formulas.

    dpr.write_dpr(out, path, title="...", inp=inp, stations=[{"outfall", "dist"}])   # out = pipeline.run result

Each sheet is computed from the one before it by Excel formulas, as in the sample:
    HY DESIGN STATEMENT_<k>  one per zone (outfall): every sewer between two manholes of the design
    Qty <k>                  quantities of each sewer: excavation by 1.5 m slice, road cutting, timbering, bedding
    Manholes                 every manhole with its depth, class (unit estimate) and extra depth
    Abstract                 (the sample's 'Sheet1') the totals of all zones
    BOQ                      the items, their rates and where each rate comes from (column 'Rate from')
    sor                      SOR 2025-26 (data/sor_2025_26.json), for reference and the items not in sewer_sor_rates.json
    Abstract comprehensive, ABS civil, Form j civil, Form j compre
    + dpr_more.py: Population, house connections (hcc2, hcc3, house connection, Table 160), per pumping station the
      Riverside SPS / rising main sheets, E&M SPS, O&M for 5 years, ECONOMICS and its statements
Rates (user, 22-Oct-2026: they were finalised already): those of data/sewer_sor_rates.json and the pipe catalog, as they
are. data/dpr_sewer.json holds the quantity rules and only the rates that file does not have (Riverside values - yellow,
to be confirmed). Yellow cells are inputs the user may change in Excel; the totals follow.
"""
import json
import math
import os

from . import DATA_DIR
from . import dpr_format
from . import dpr_front as front
from . import dpr_more as more

SETTINGS_FILE = os.path.join(DATA_DIR, "dpr_sewer.json")
SOR_FILE = os.path.join(DATA_DIR, "sor_2025_26.json")
RATES_FILE = os.path.join(DATA_DIR, "sewer_sor_rates.json")
BANDS = ["0-1.5 M", "1.5-3.0 M", "3.0-4.5 M", "4.5-6.0 M", "6.0-7.5 M", "7.5-9.0 M", "9.0-10.5 M", "10.5-12.0 M"]
FIRST = 6                       # first data row of the HY DESIGN / Qty sheets (rows 1-5: title and headers)


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def settings():
    """dpr_sewer.json as {key: value}."""
    return {k: v["value"] for k, v in _load(SETTINGS_FILE).items() if isinstance(v, dict) and "value" in v}


def nominal_mm(d):
    from .report import nominal_mm as nom
    return nom(d)


def _order(res):
    """Conduit labels upstream first (each sewer after every sewer that flows into it)."""
    inc = {}
    for lab, d in res.items():
        inc.setdefault(d["to"], []).append(lab)
    seen, order = set(), []
    for lab in res:
        stack = [(lab, False)]
        while stack:
            x, done = stack.pop()
            if done:
                if x not in seen:
                    seen.add(x)
                    order.append(x)
                continue
            if x in seen:
                continue
            stack.append((x, True))
            stack.extend((y, False) for y in inc.get(res[x]["from"], []) if y not in seen)
    return order


def zones_of(res):
    """{conduit: outfall it drains to} - one zone per outfall, as the sample's Zone 1 / Zone 2 / Zone IPS."""
    nxt = {d["from"]: lab for lab, d in res.items()}
    out = {}
    for lab in res:
        path, x = [], lab
        while x is not None and x not in out:
            path.append(x)
            x = nxt.get(res[x]["to"])
        end = out[x] if x is not None else res[path[-1]]["to"]
        for p in path:
            out[p] = end
    return out


def contributory_population(res, pop):
    """{conduit: persons upstream of it, its own upstream manhole included}."""
    inflow, out = {}, {}
    for lab in _order(res):
        d = res[lab]
        out[lab] = (pop or {}).get(d["from"], 0.0) + inflow.get(d["from"], 0.0)
        inflow[d["to"]] = inflow.get(d["to"], 0.0) + out[lab]
    return out


def full_flow_lpd(D_mm, slope, n):
    """Manning full-bore capacity of a circular sewer, L/day (CPHEEO eq. 3.16 p3-27)."""
    if not D_mm or not slope or slope <= 0 or not n:
        return None
    D = D_mm / 1000.0
    return (1.0 / n) * (math.pi * D * D / 4.0) * (D / 4.0) ** (2.0 / 3.0) * math.sqrt(slope) * 86400000.0


def design_rows(out):
    """Every sewer between two manholes of the design (the pieces the new manholes cut a designed conduit into, as in the
    plan DXF): label, from, to, GL and invert at both ends, length, zone, population and the designed conduit d."""
    res, made = out["res"], out.get("made") or {}
    gl = dict(out.get("ground") or {})
    gl.update({m["label"]: m.get("ground") for m in out.get("new_mh") or []})
    zone, pop = zones_of(res), contributory_population(res, out.get("pop"))
    rows = []
    for lab in _order(res):
        d = res[lab]
        pieces = made.get(lab) or []
        if len(pieces) >= 2:
            for p in (pieces[::-1] if d["rev"] else pieces):
                a, b, up, dn = ((p["stop"], p["start"], p["dn"], p["up"]) if d["rev"]
                                else (p["start"], p["stop"], p["up"], p["dn"]))
                rows.append({"label": p["label"], "from": a, "to": b, "g_up": gl.get(a), "g_dn": gl.get(b), "up": up,
                             "dn": dn, "length": p["length"], "zone": zone[lab], "pop": pop[lab], "d": d})
        else:
            rows.append({"label": lab, "from": d["from"], "to": d["to"], "g_up": d["g_up"], "g_dn": d["g_dn"],
                         "up": d["up"], "dn": d["dn"], "length": d["length"], "zone": zone[lab], "pop": pop[lab], "d": d})
    return rows


def manhole_rows(out):
    """Every manhole of the design: label, zone, GL, invert (the new manholes planned on the trunk sewers too)."""
    res = out["res"]
    zone = zones_of(res)
    nxt = {d["from"]: lab for lab, d in res.items()}
    rows = []
    for n, i in out["node_info"].items():
        z = zone[nxt[n]] if n in nxt else n
        rows.append({"label": n, "zone": z, "gl": i.get("ground"), "invert": i.get("invert")})
    for m in out.get("new_mh") or []:
        if m.get("conduit") in zone:
            rows.append({"label": m["label"], "zone": zone[m["conduit"]], "gl": m.get("ground"), "invert": m.get("invert")})
    return rows


def _natural(s):
    import re
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", str(s))]


def index_entries(names):
    """(number, description, sheet) of the DPR's sheets, for sheet Index."""
    desc = {"Project": "Project data (texts and inputs used on every sheet)", "Coverage": "Coverage status of the city",
            "Certificate": "Certificate", "Index": "Index", "Form j compre": "Form 'J' comprehensive (with centage)",
            "Form j civil": "Form 'J' (civil works)", "Abstract comprehensive": "General abstract of cost (comprehensive)",
            "ABS civil": "General abstract of cost (civil works)", "ABS (O&M)": "Abstract of 5 years O&M cost",
            "Sewer Lines and RM": "O&M of the civil works", "5 yr O&M": "O&M of the pumping stations for 5 years",
            "SPS O&M": "Annual O&M expenditure of the pumping stations", "ECONOMICS": "Abstract of economics",
            "INCOME": "Statement of annual income", "RECURRING EXP": "Annual recurring expenditure on maintenance",
            "REPAIR WORKS": "Annual expenditure on repair of works",
            "A.R. EXP ON M. STAFF": "Annual recurring expenditure on maintenance staff", "BREAKUP OF COST": "Break up of cost",
            "Bar Chart": "Project implementation schedule", "Tech": "Technical statement",
            "Population": "Population and households", "BOQ": "Estimate of the sewer network",
            "Abstract": "Abstract of quantities", "Manholes": "Detail of manholes", "hcc2": "Number of house connections",
            "hcc3": "Estimate of sewer house connections", "house connection": "Reinstatement of road (house connections)",
            "Table 160": "Cost of house connections", "E&M SPS": "E&M works of the pumping stations",
            "HT": "Unit estimate of HT panel room", "LT": "Unit estimate of LT panel room",
            "Plinth Area Rate": "Plinth area rate", "sor": "Schedule of rates 2025-26"}
    pre = [("HY DESIGN STATEMENT_", "Hydraulic design statement, zone "), ("Qty ", "Quantities, zone "),
           ("DESIGN DATA ", "Design data of "), ("INLET CHAMBER ", "Inlet chamber of "), ("WET WELL ", "Wet well of "),
           ("SCREEN CHANNEL ", "Screen channel of "), ("SCREEN ", "Screen of "),
           ("BOQ R.MAIN ", "Estimate of the rising main of "), ("BOQ ", "Estimate of "),
           ("RM ", "Design of the rising main of ")]
    out = []
    for i, n in enumerate(names, 1):
        d = desc.get(n)
        if d is None:
            d = next((new + n[len(old):] for old, new in pre if n.startswith(old)), n)
        out.append((i, d, n))
    return out


def _book(out, title, inp):
    """The empty workbook of a pipeline.run result and what every sheet of it is made with: the settings and rates
    read, the design rows, the styles, sheet() and header()."""
    from types import SimpleNamespace

    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter as col

    S = settings()
    sor = _load(SOR_FILE)
    rates = _load(RATES_FILE)
    inp = inp or {}
    title_text = title or "SEWERAGE SCHEME"
    title = "=Project!$C$4"                                # every sheet takes the scheme's name from sheet Project
    f_pop = inp.get("forecast") if inp else None
    y0 = int((f_pop or {}).get("base_year") or (inp or {}).get("base_year") or 2027)
    R = out["rules"]
    rows = design_rows(out)
    mhs = manhole_rows(out)
    zone_names = sorted({r["zone"] for r in rows}, key=_natural)
    sor_codes = {it[0] for it in sor["items"] if it[0] and isinstance(it[3], (int, float))}
    sor_desc = {it[0]: it[1] for it in sor["items"] if it[0]}

    bold, head = Font(bold=True), PatternFill("solid", fgColor="D9E1F2")
    yellow = PatternFill("solid", fgColor="FFF2CC")
    thin = Side(style="thin", color="999999")
    box = Border(left=thin, right=thin, top=thin, bottom=thin)
    wrap = Alignment(wrap_text=True, vertical="top")
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    wb = Workbook()
    wb.remove(wb.active)

    def sheet(name, heading, ncols):
        ws = wb.create_sheet(name)
        ws.cell(1, 1, title).font = Font(bold=True, size=12)
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncols)
        ws.cell(2, 1, heading).font = bold
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncols)
        for r in (1, 2):
            ws.cell(r, 1).alignment = Alignment(horizontal="center")
        return ws

    def header(ws, r, names, widths=None):
        for c, h in enumerate(names, 1):
            x = ws.cell(r, c, h)
            x.font, x.fill, x.alignment, x.border = bold, head, center, box
        for c, w in enumerate(widths or [], 1):
            if w:
                ws.column_dimensions[col(c)].width = w

    return SimpleNamespace(out=out, wb=wb, S=S, sor=sor, rates=rates, inp=inp, title=title, title_text=title_text,
                           f_pop=f_pop, y0=y0, R=R, rows=rows, mhs=mhs, zone_names=zone_names, sor_codes=sor_codes,
                           sor_desc=sor_desc, bold=bold, head=head, yellow=yellow, box=box, wrap=wrap, center=center,
                           sheet=sheet, header=header, col=col, tr=S["trench"], tb=S["timbering"], bd=S["bedding"],
                           dias=sorted({nominal_mm(rw["d"]) for rw in rows}), classes=S["manholes"])


def _zone_sheets(X):
    """HY DESIGN STATEMENT and Qty, one pair per zone -> X.zone_sheets = [(zone, HY sheet, Qty sheet, last data row,
    total row, {dia: laying row}, bedding row)]."""
    S, R, inp, rows, zone_names, dias = X.S, X.R, X.inp, X.rows, X.zone_names, X.dias
    sheet, header, col, bold, yellow, box, wrap = X.sheet, X.header, X.col, X.bold, X.yellow, X.box, X.wrap
    tr, tb, bd = X.tr, X.tb, X.bd
    zone_sheets = X.zone_sheets = []
    for k, z in enumerate(zone_names, 1):
        zr = [r for r in rows if r["zone"] == z]
        hy_name, q_name = f"HY DESIGN STATEMENT_{k}", f"Qty {k}"
        hy = sheet(hy_name, f"STATEMENT FOR HYDRAULIC DESIGN - Zone {k} (outfall {z})", 24)
        pz = max((r["pop"] for r in zr), default=0.0)
        hy.cell(3, 1, f"Contributory population at the outfall (design year): {pz:,.0f} persons;  sewage "
                      f"{inp.get('sewage_lpcd', '')} LPCD (CPHEEO 3.4.1 p3-3);  peak factor by contributory population "
                      f"(CPHEEO Table 3.2 p3-3);  Manning n by pipe material;  max depth of flow {R.ddmax:g} D;  "
                      f"Q = (1/n) A R^(2/3) S^(1/2) (CPHEEO 3.15-3.16 p3-27)")
        hy.merge_cells(start_row=3, start_column=1, end_row=3, end_column=24)
        hy.cell(3, 1).alignment = wrap
        hy.row_dimensions[3].height = 30
        header(hy, 5, ["Label", "Start Node", "Stop Node", "Elevation Ground (Start) (m)", "Elevation Ground (Stop) (m)",
                       "Invert (Start) (m)", "Invert (Stop) (m)", "Diff", "Length (m)", "ID Diameter (mm)",
                       "Diameter (mm)", "Material", "Manning's n", "Slope (1/S)", "Population (Souls)", "Flow (L/day)",
                       "Capacity (Full Flow) (L/day)", "Flow / Capacity (Design) (%)", "Depth/Rise (%)",
                       "Velocity (m/s)", "Depth of Cut U/S (m)", "Depth of Cut D/S (m)", "Average Conduit Depth (m)",
                       "Remarks"],
               [11, 11, 11, 11, 11, 10, 10, 8, 9, 9, 9, 18, 8, 9, 11, 13, 14, 10, 9, 9, 9, 9, 10, 80])
        hy.freeze_panes = "D6"
        for i, r in enumerate(zr):
            x = FIRST + i
            d = r["d"]
            cap = full_flow_lpd(d["D"], d["slope"], d["n"])
            q = (d["q"] or 0.0) * 86400.0
            vals = [r["label"], r["from"], r["to"], r["g_up"], r["g_dn"], r["up"], r["dn"], f"=F{x}-G{x}", r["length"],
                    d["D"], nominal_mm(d), d["size"].get("material"), d["n"],
                    round(1 / d["slope"]) if d["slope"] else None, round(r["pop"]), round(q, 2),
                    round(cap, 2) if cap else None, f"=IF(Q{x}>0,P{x}/Q{x}*100,0)",
                    round(d["dd"] * 100, 1) if d.get("dd") is not None else None,
                    round(d["v"], 2) if d.get("v") is not None else None,
                    f"=D{x}-F{x}", f"=E{x}-G{x}", f"=(U{x}+V{x})/2", "; ".join(d.get("flags") or [])]
            for c, v in enumerate(vals, 1):
                cell = hy.cell(x, c, round(v, 3) if isinstance(v, float) and c not in (16, 17) else v)
                cell.border = box
                if c in (4, 5, 6, 7, 8, 9, 21, 22, 23):
                    cell.number_format = "0.000" if c in (4, 5, 6, 7, 8) else "0.00"
                if c == 18:
                    cell.number_format = "0.0"
        last = FIRST + len(zr) - 1

        # Qty: the sample's formulas (sheet 'Qty' H6:BD6), excavation to 8 slices (12 m)
        qs = sheet(q_name, f"QUANTITIES OF EARTH WORK, ROAD CUTTING, TIMBERING AND BEDDING - Zone {k} (outfall {z})", 28)
        qs.cell(3, 9, "Quantity of earth work below G.L. (cum), by 1.5 m slice").font = bold
        qs.cell(3, 19, "Road cutting (sqm)").font = bold
        qs.cell(3, 22, "Timbering (sqm)").font = bold
        qs.cell(3, 25, "Bedding").font = bold
        header(qs, 5, ["Label", "From", "To", "Length in m", "Dia of sewer in mm", "Total depth (m)", "Gradient 1 in",
                       "Slices (nos)"] + BANDS + ["Top width of trench (m)",
                       "Type of road (1 Bitumen, 2 CC, 3 Interlocking)", "Bitumen", "CC", "Interlocking",
                       f"Open 0-{tb['open_upto_m']:g} M", "Close 3.0-6.0 M", "Close 6.0 M and deeper",
                       "Width (m)", "Quantity (cum)", "Depth band (1-8)", "Pipe volume (cum)"],
               [10, 10, 10, 9, 9, 9, 9, 7] + [10] * 8 + [9, 12, 10, 10, 10, 10, 10, 10, 8, 10, 8, 9])
        qs.freeze_panes = "D6"
        h = hy_name
        for i in range(len(zr)):
            x, y = FIRST + i, FIRST + i
            f = {1: f"='{h}'!A{y}", 2: f"='{h}'!B{y}", 3: f"='{h}'!C{y}", 4: f"='{h}'!I{y}", 5: f"='{h}'!K{y}",
                 6: f"='{h}'!W{y}", 7: f"='{h}'!N{y}", 8: f"=MAX(1,ROUNDUP(F{x}/{tr['slice_m']},0))"}
            for b in range(8):            # slice b: width D + 0.6 + 0.5 x (n - 1 - b), thickness up to 1.5 m (last: rest)
                th = (f"MIN({tr['slice_m']},F{x}-{tr['slice_m'] * b:g})" if b < 7 else f"F{x}-{tr['slice_m'] * b:g}")
                f[9 + b] = (f"=IF(F{x}>{tr['slice_m'] * b:g},(E{x}/1000+{tr['bottom_add_m']}+{tr['step_m']}*(H{x}-1-{b}))"
                            f"*{th}*D{x},0)")
            f[17] = f"=E{x}/1000+{tr['bottom_add_m']}+{tr['step_m']}*(H{x}-1)"
            f[18] = S["road"]["default_type"]
            f[19], f[20], f[21] = (f"=IF(R{x}={t},Q{x}*D{x},0)" for t in (1, 2, 3))
            mn = tb["min_depth_m"]
            f[22] = f"=IF(F{x}>{mn},MIN(F{x},{tb['open_upto_m']})*D{x},0)"
            f[23] = f"=IF(F{x}>{mn},MAX(0,MIN(F{x},6)-3)*D{x},0)"
            f[24] = f"=IF(F{x}>{mn},MAX(0,F{x}-6)*D{x},0)"
            f[25] = (f"=IF(E{x}<{bd['large_from_mm']},E{x}/1000+{bd['width_small_add_m']},"
                     f"{bd['width_large_factor']}*E{x}/1000)")
            f[26] = f"=Y{x}*({bd['thick_factor']}*E{x}+{bd['thick_add_mm']})/1000*D{x}"
            f[27] = f"=MIN(8,H{x})"
            f[28] = f"=PI()*(E{x}/1000)^2/4*D{x}"
            for c, v in f.items():
                cell = qs.cell(x, c, v)
                cell.border = box
                cell.number_format = "0" if c in (5, 7, 8, 18, 27) else "0.00"
                if c == 18:
                    cell.fill = yellow
        tot = last + 2
        qs.cell(tot, 1, "Total").font = bold
        for c in [4] + list(range(9, 17)) + list(range(19, 25)) + [26, 28]:
            cell = qs.cell(tot, c, f"=SUM({col(c)}{FIRST}:{col(c)}{last})" if last >= FIRST else 0)
            cell.font, cell.number_format = bold, "0.00"
        # by diameter and depth band (the sample's columns CI:GD), and the bedding by depth band
        x = tot + 2
        qs.cell(x, 1, "Depth wise pipe laying details (m)").font = bold
        for b, name in enumerate(BANDS):
            qs.cell(x, 9 + b, name).font = bold
        rng = lambda c: f"${c}${FIRST}:${c}${last}"                                              # noqa: E731
        lay_rows = {}
        for D in dias:
            x += 1
            qs.cell(x, 1, f"{D} mm")
            for b in range(8):
                qs.cell(x, 9 + b, f"=SUMIFS({rng('D')},{rng('E')},{D},{rng('AA')},{b + 1})").number_format = "0.00"
            lay_rows[D] = x
        x += 1
        qs.cell(x, 1, "Bedding by depth band (cum)").font = bold
        for b in range(8):
            qs.cell(x, 9 + b, f"=SUMIFS({rng('Z')},{rng('AA')},{b + 1})").number_format = "0.00"
        zone_sheets.append((z, hy_name, q_name, last, tot, lay_rows, x))


def _manholes(X):
    """Sheet Manholes: every manhole once, its class by depth -> X.mh_last (its last data row)."""
    from openpyxl.styles import Font

    mhs, zone_names, classes = X.mhs, X.zone_names, X.classes
    sheet, header, box = X.sheet, X.header, X.box
    mh = sheet("Manholes", "DETAIL OF MANHOLES (circular brick masonry, by depth - unit estimates)", 10)
    header(mh, 4, ["S.N.", "Manhole", "Zone (outfall)", "Ground level (m)", "Invert (m)", "Depth (m)",
                   "Class (1-%d)" % len(classes), "Extra depth over unit (m)", "Volume (cum)", "Type"],
           [6, 12, 14, 10, 10, 9, 8, 10, 10, 34])
    mh.freeze_panes = "C5"
    lim = ",".join(str(c["upto_m"]) for c in classes)
    cls = ("".join(f"IF(F{{x}}<={c['upto_m']},{i}," for i, c in enumerate(classes[:-1], 1)) + str(len(classes))
           + ")" * (len(classes) - 1))
    unit = "CHOOSE(G{x}," + ",".join(f"{c['unit_depth_m']}" for c in classes) + ")"
    dia = "CHOOSE(G{x}," + ",".join(f"{c['dia_m']}" for c in classes) + ")"
    names = "CHOOSE(G{x}," + ",".join(f'"{c["name"]}"' for c in classes) + ")"
    mh_rows = sorted(mhs, key=lambda m: (zone_names.index(m["zone"]) if m["zone"] in zone_names else 99, _natural(m["label"])))
    for i, m in enumerate(mh_rows):
        x = 5 + i
        vals = [i + 1, m["label"], m["zone"], m["gl"], m["invert"], f"=IF(AND(ISNUMBER(D{x}),ISNUMBER(E{x})),D{x}-E{x},0)",
                "=" + cls.format(x=x), f"=F{x}-{unit.format(x=x)}", f"=PI()*{dia.format(x=x)}^2/4*F{x}",
                "=" + names.format(x=x)]
        for c, v in enumerate(vals, 1):
            cell = mh.cell(x, c, round(v, 3) if isinstance(v, float) else v)
            cell.border = box
            if c in (4, 5, 6, 8, 9):
                cell.number_format = "0.000" if c in (4, 5) else "0.00"
    mh_last = 4 + max(1, len(mh_rows))
    mh.cell(mh_last + 2, 1, f"Class limits (depth up to, m): {lim} - data/dpr_sewer.json 'manholes' (Riverside DPR unit "
                            f"estimates). Depth = ground level - invert.").font = Font(italic=True)
    X.mh_last = mh_last


def _abstract(X):
    """Sheet Abstract (the sample's 'Sheet1'): the quantities of all zones -> X.ref, its cells by what they hold."""
    S, tb, dias, classes, zone_sheets, mh_last = X.S, X.tb, X.dias, X.classes, X.zone_sheets, X.mh_last
    sheet, col, bold, head, center = X.sheet, X.col, X.bold, X.head, X.center
    ab = sheet("Abstract", "ABSTRACT OF QUANTITIES", 14)
    ab.column_dimensions["A"].width = 6
    ab.column_dimensions["B"].width = 36
    ab.column_dimensions["C"].width = 16
    for c in range(4, 15):
        ab.column_dimensions[col(c)].width = 12
    ref = X.ref = {}
    r = 4

    def block(name, cols, cell_of, key):
        """One section: a row per zone (cell_of(sheet info, j) -> formula for column j), then the total row."""
        nonlocal r
        ab.cell(r, 2, name).font = bold
        for j, h in enumerate(cols):
            x = ab.cell(r, 4 + j, h)
            x.font, x.fill, x.alignment = bold, head, center
        r += 1
        top = r
        for k, zs in enumerate(zone_sheets, 1):
            ab.cell(r, 3, f"Zone {k} ({zs[0]})")
            for j in range(len(cols)):
                ab.cell(r, 4 + j, cell_of(zs, j)).number_format = "0.00"
            r += 1
        ab.cell(r, 3, "Total").font = bold
        ref[key] = []
        for j in range(len(cols)):
            cell = ab.cell(r, 4 + j, f"=SUM({col(4 + j)}{top}:{col(4 + j)}{r - 1})")
            cell.font, cell.number_format = bold, "0.00"
            ref[key].append(f"Abstract!{col(4 + j)}{r}")
        r += 2

    block("Quantity of earth work below G.L. (cum)", BANDS, lambda zs, j: f"='{zs[2]}'!{col(9 + j)}{zs[4]}", "exc")
    block("Timbering (sqm)", [f"Open 0-{tb['open_upto_m']:g} M", "Close 3.0-6.0 M", "Close 6.0 M +"],
          lambda zs, j: f"='{zs[2]}'!{col(22 + j)}{zs[4]}", "timb")
    block("Quantity of bedding (cum)", BANDS, lambda zs, j: f"='{zs[2]}'!{col(9 + j)}{zs[6]}", "bed")
    block("Road cutting quantity (sqm)", S["road"]["types"], lambda zs, j: f"='{zs[2]}'!{col(19 + j)}{zs[4]}", "road")

    # pipe laying length by diameter and depth band (all zones), length and volume by diameter
    ab.cell(r, 2, "Depth wise pipe laying details (m) - all zones").font = bold
    for j, hname in enumerate(BANDS + ["Total length (m)", "Pipe volume (cum)"]):
        x = ab.cell(r, 4 + j, hname)
        x.font, x.fill, x.alignment = bold, head, center
    r += 1
    ref["lay"], ref["len"] = {}, {}
    top = r
    for D in dias:
        ab.cell(r, 3, f"{D} mm")
        for j in range(8):
            f = "+".join(f"'{zs[2]}'!{col(9 + j)}{zs[5][D]}" for zs in zone_sheets)
            ab.cell(r, 4 + j, "=" + (f or "0")).number_format = "0.00"
            ref["lay"][(D, j)] = f"Abstract!{col(4 + j)}{r}"
        ab.cell(r, 12, f"=SUM(D{r}:K{r})").number_format = "0.00"
        ab.cell(r, 13, f"=PI()*({D}/1000)^2/4*L{r}").number_format = "0.00"
        ref["len"][D] = f"Abstract!L{r}"
        r += 1
    ab.cell(r, 3, "Total").font = bold
    for c in (12, 13):
        cell = ab.cell(r, c, f"=SUM({col(c)}{top}:{col(c)}{max(top, r - 1)})")
        cell.font, cell.number_format = bold, "0.00"
    ref["len_total"], ref["pipe_vol"] = f"Abstract!L{r}", f"Abstract!M{r}"
    r += 2

    # manholes by class
    ab.cell(r, 2, "Circular type manholes - all zones").font = bold
    for j, hname in enumerate(["No.", "Extra depth (m)", "Volume (cum)"]):
        x = ab.cell(r, 4 + j, hname)
        x.font, x.fill, x.alignment = bold, head, center
    r += 1
    ref["mh_n"], ref["mh_extra"] = [], []
    top = r
    for i, c in enumerate(classes, 1):
        ab.cell(r, 3, c["name"])
        ab.cell(r, 4, f"=COUNTIF(Manholes!$G$5:$G${mh_last},{i})")
        ab.cell(r, 5, f"=SUMIFS(Manholes!$H$5:$H${mh_last},Manholes!$G$5:$G${mh_last},{i})").number_format = "0.00"
        ab.cell(r, 6, f"=SUMIFS(Manholes!$I$5:$I${mh_last},Manholes!$G$5:$G${mh_last},{i})").number_format = "0.00"
        ref["mh_n"].append(f"Abstract!D{r}")
        ref["mh_extra"].append(f"Abstract!E{r}")
        r += 1
    ab.cell(r, 3, "Total").font = bold
    for c in (4, 6):
        cell = ab.cell(r, c, f"=SUM({col(c)}{top}:{col(c)}{r - 1})")
        cell.font, cell.number_format = bold, "0.00"
    ref["mh_vol"] = f"Abstract!F{r}"


def _boq(X):
    """Sheet BOQ, the estimate of the sewer network -> X.boq_total (its total's cell) and X.boq (its rates' cells
    the other sheets use)."""
    from openpyxl.styles import Font

    out, S, sor, rates, rows, dias, classes, ref = X.out, X.S, X.sor, X.rates, X.rows, X.dias, X.classes, X.ref
    sor_codes, sor_desc, tb, bd = X.sor_codes, X.sor_desc, X.tb, X.bd
    sheet, header, bold, yellow, box, wrap, center = X.sheet, X.header, X.bold, X.yellow, X.box, X.wrap, X.center
    # rates: the finalised ones of sewer_sor_rates.json and the pipe catalog; an SOR item not there from sheet 'sor';
    # the rest (Riverside DPR unit estimates / rate analyses) in yellow, named in column H - to be confirmed
    JSON, SORX = "sewer_sor_rates.json", "SOR 2025-26 (sheet sor) - not in sewer_sor_rates.json"
    LAH = "Riverside DPR - NOT in sewer_sor_rates.json, confirm"
    CAT = f"sewer_catalog.json ({out['catalog'][0]})"
    bq = sheet("BOQ", "Estimate for Sewer Network", 8)
    header(bq, 3, ["S. No.", "SOR Ref.", "Item of Work", "Unit", "Quantity", "Rate (Rs.)", "Amount (Rs.)", "Rate from"],
           [6, 12, 70, 7, 13, 12, 16, 34])
    for c in range(1, 8):
        bq.cell(4, c, c).alignment = center
    bq.freeze_panes = "A5"
    r = 5
    amounts = []
    sno = [0]

    def title_row(text, number=True):
        nonlocal r
        if number:
            sno[0] += 1
            bq.cell(r, 1, sno[0])
        bq.cell(r, 3, text).alignment = wrap
        r += 1

    def item(ref_, text, unit, qty, rate, source, qty_input=False):
        """One priced line. rate None and ref_ an SOR code -> VLOOKUP in sheet 'sor'. A rate that is not from
        sewer_sor_rates.json / the pipe catalog is yellow (to be confirmed)."""
        nonlocal r
        bq.cell(r, 2, int(ref_) if str(ref_).isdigit() else ref_)        # numeric codes as numbers, as in sheet sor
        bq.cell(r, 3, text).alignment = wrap
        bq.cell(r, 4, unit)
        q = bq.cell(r, 5, qty)
        q.number_format = "0.00"
        if rate is None and ref_ in sor_codes:
            rate = f"=VLOOKUP(B{r},sor!$A$4:$D${3 + len(sor['items'])},4,FALSE)"
        rt = bq.cell(r, 6, rate if rate is not None else 0)
        rt.number_format = "0.00"
        if rate is None or source not in (JSON, CAT):
            rt.fill = yellow
        if qty_input:
            q.fill = yellow
        bq.cell(r, 7, f"=E{r}*F{r}").number_format = "#,##0.00"
        bq.cell(r, 8, source if rate is not None else "NO RATE")
        amounts.append(f"G{r}")
        r += 1
        return r - 1

    ex = rates["excavation_ordinary_soil"]
    title_row(ex.get("desc") or "Excavation below G.L. for laying sewer and manholes")
    for j in range(8):
        item(ex["codes"][j], BANDS[j].replace(" M", " m"), "cum", f"={ref['exc'][j]}", ex["rates"][j], JSON)
    tc, to = rates["timbering_close"], rates["timbering_open"]
    title_row("Close timbering in trenches (SOR 3033-3034), the part of the trench deeper than 3.0 m")
    item(tc["codes"][1], "3.00 to 6.00 m", "sqm", f"={ref['timb'][1]}", tc["rates"][1], JSON)
    item(tc["codes"][2], "6.00 to 9.00 m (and deeper)", "sqm", f"={ref['timb'][2]}", tc["rates"][2], JSON)
    title_row(f"Close timbering left in the trench (unused timbering), {tb['unused_close_share'] * 100:g} % of the close "
              f"timbering")
    item("3036", "3.00 to 6.00 m", "sqm", f"={ref['timb'][1]}*{tb['unused_close_share']}", None, SORX)
    item("3037", "6.00 to 9.00 m (and deeper)", "sqm", f"={ref['timb'][2]}*{tb['unused_close_share']}", None, SORX)
    title_row(sor_desc.get(to["codes"][0], "Open timbering in trenches"))
    item(to["codes"][0], f"0.00 to {tb['open_upto_m']:.2f} m (trench deeper than {tb['min_depth_m']:g} m)", "sqm",
         f"={ref['timb'][0]}", to["rates"][0], JSON)
    title_row(f"Supply of sewer pipes ({out['catalog'][0]}) - rate of the design catalog")
    rate_of = {}
    for rw in rows:
        rate_of.setdefault(nominal_mm(rw["d"]), (rw["d"]["size"].get("rate_rs_per_m"), rw["d"]["size"].get("material")))
    for D in dias:
        rt, mat = rate_of[D]
        item("Catalog", f"{D} mm {mat or ''}".strip(), "m", f"={ref['len'][D]}", rt, CAT)
    laying = rates["laying_rcc_np3"]["by_nominal_mm"]
    title_row("Carting, lowering, laying and jointing R.C.C. NP3 pipes and specials from store to the work, true to "
              "alignment and gradient, by depth below G.L. (SOR 3196-3214)")
    for D in dias:
        spec = laying.get(str(D)) or {}
        codes, lrates = spec.get("codes") or [], spec.get("rates") or []
        main = codes[0].split(".")[0] if codes else ""
        title_row(sor_desc.get(main, f"{D} mm dia pipe"), number=False)
        for j in range(8):
            ok = j < len(codes)
            item(codes[j] if ok else "", BANDS[j].replace(" M", " m"), "m", f"={ref['lay'][(D, j)]}",
                 lrates[j] if ok else None, JSON)
    gb = rates["granular_bedding"]
    title_row((gb.get("desc") or "Bedding for sewer line") +
              f" (width D + {bd['width_small_add_m']} m below {bd['large_from_mm']} mm, else {bd['width_large_factor']} D;"
              f" thickness {bd['thick_factor']} D + {bd['thick_add_mm']} mm)")
    for j in range(8):
        item(gb["codes"][j], BANDS[j].replace(" M", " m"), "cum", f"={ref['bed'][j]}", gb["rates"][j], JSON)
    title_row("Construction of circular type brick masonry manhole (with extra heavy SFRC cover and frame), complete - "
              "unit estimate")
    for i, c in enumerate(classes):
        item("Unit Estimate", c["name"], "Nos.", f"={ref['mh_n'][i]}", c["rate"], LAH)
    title_row("Extra for every additional depth of 1 m or part thereof (less for a shallower manhole)")
    for i, c in enumerate(classes):
        item("Unit Estimate", c["name"], "m", f"={ref['mh_extra'][i]}", c["extra_rate"], LAH)
    rd = S["road"]
    title_row("Dismantling / cutting of the following type of road for laying sewers")
    cut_rows = [item("Rate Analysis", f"{name} road", "sqm", f"={ref['road'][t]}", rd["cut_rates"][t], LAH)
                for t, name in enumerate(rd["types"])]
    rr = rates["road_reinstatement"]
    title_row("Reinstatement of the following type of road for laying sewers")
    re_rows = [item(rr["BT"]["code"], "Bituminous road", "sqm", f"={ref['road'][0]}", rr["BT"]["rate"], JSON),
               item(rr["CC"]["code"], "CC road", "sqm", f"={ref['road'][1]}", rr["CC"]["rate"], JSON),
               item("Rate Analysis", "Interlocking tile road", "sqm", f"={ref['road'][2]}", rd["interlocking_reinstate_rate"],
                    LAH)]
    bar = S["barricading"]
    title_row(f"Providing and erecting temporary barricading at site ({bar['share_of_length'] * 100:g} % of the sewer "
              f"length)")
    item("Rate Analysis", "", "m", f"={ref['len_total']}*{bar['share_of_length']}", bar["rate"], LAH)
    title_row("Disposal of surplus earth (volume of the pipes and manholes)")
    disp_row = item("AOR", "", "cum", f"={ref['pipe_vol']}+{ref['mh_vol']}", S["disposal"]["rate"], LAH)
    dw = rates["dewatering"]
    title_row(dw.get("desc") or "Dewatering")
    item(dw["code"], "quantity per project (subsoil water level)", dw.get("unit", "cum"), 0, dw["rate"], JSON,
         qty_input=True)
    for li in S["lump_items"]:
        title_row(li["name"])
        code = li.get("code")
        item(code or li.get("ref", ""), "", li["unit"], li["qty"], None if code else li.get("rate"),
             SORX if code else LAH, qty_input=True)
    sub = r
    bq.cell(r, 3, "Sub Total").font = bold
    bq.cell(r, 7, "=" + "+".join(amounts) if amounts else 0).number_format = "#,##0.00"
    bq.cell(r, 7).font = bold
    r += 1
    sno[0] += 1
    bq.cell(r, 1, sno[0])
    bq.cell(r, 3, "Provision for shifting of electric and telephone cables, gas pipes etc. (share of the sub total)")
    bq.cell(r, 4, "LS")
    sh = bq.cell(r, 5, S["utility_shifting_share"])
    sh.fill, sh.number_format = yellow, "0.00%"
    bq.cell(r, 7, f"=E{r}*G{sub}").number_format = "#,##0.00"
    bq.cell(r, 8, LAH)
    r += 1
    bq.cell(r, 3, "TOTAL COST").font = bold
    bq.cell(r, 7, f"=G{sub}+G{r - 1}").number_format = "#,##0.00"
    bq.cell(r, 7).font = bold
    bq.cell(r + 2, 3, "Rates: sewer_sor_rates.json (the finalised SOR 2025-26 rates) and the pipe catalog. Yellow = not in "
                      "that file (Riverside DPR value or another SOR item) - to be confirmed, see column H.").font = \
        Font(italic=True)
    boq_total = f"BOQ!G{r}"
    for row in bq.iter_rows(min_row=5, max_row=r, max_col=8):
        for cell in row:
            cell.border = box
    X.boq_total = boq_total
    X.boq = {"bt_cut": f"BOQ!F{cut_rows[0]}", "cc_cut": f"BOQ!F{cut_rows[1]}", "il_cut": f"BOQ!F{cut_rows[2]}",
             "bt_re": f"BOQ!F{re_rows[0]}", "cc_re": f"BOQ!F{re_rows[1]}", "il_re": f"BOQ!F{re_rows[2]}",
             "disposal": f"BOQ!F{disp_row}"}


def _sor_sheet(X):
    """Sheet sor: the schedule of rates, for the look-ups of the BOQ and for reference."""
    from openpyxl.styles import Alignment, Font

    wb, sor, header = X.wb, X.sor, X.header
    so = wb.create_sheet("sor")
    so.cell(1, 1, sor.get("title") or "SCHEDULE OF RATES").font = Font(bold=True, size=12)
    header(so, 3, ["Item No.", "Description of item", "Unit", "Rate"], [12, 100, 8, 12])
    for i, (code, desc, unit_, rate) in enumerate(sor["items"]):
        x = 4 + i
        so.cell(x, 1, (int(code) if code.isdigit() else code) or None)       # numeric codes as numbers (as the SOR)
        so.cell(x, 2, desc).alignment = Alignment(wrap_text=False)
        so.cell(x, 3, unit_ or None)
        so.cell(x, 4, rate).number_format = "0.00"
    so.freeze_panes = "A4"


def _abstract_cost(X, ps, hc):
    """Sheets Abstract comprehensive and ABS civil (the sample's rows) -> the cells of the first by what they hold."""
    sheet, header, bold, box, ref, boq_total = X.sheet, X.header, X.bold, X.box, X.ref, X.boq_total
    ac = sheet("Abstract comprehensive", "Abstract Cost - Comprehensive", 4)
    header(ac, 3, ["Sl. No.", "Items", "Qty", "Amount (Rs. Lac)"], [7, 56, 18, 18])
    ac.cell(4, 1, "A").font = bold
    ac.cell(4, 2, "Civil Works").font = bold
    n_ps = len(ps["names"]) if ps else 0
    civil = [("Sewer Network", f'=TEXT({ref["len_total"]}/1000,"0.00")&" Km"', f"={boq_total}/100000"),
             ("Sewer house connection", f'=TEXT({hc["count"]},"0")&" Nos"', f"={hc['amount_lakh']}"),
             ("SPS", f"{n_ps} No." if n_ps else "-", ("=(" + "+".join(ps["civil"]) + ")/100000") if ps else 0),
             ("Rising Main", (f'=TEXT({"+".join(f"{more.q(s_)}!D21" for s_ in ps["rm_sheet"])},"0")&" m"' if ps else "-"),
              ("=" + "+".join(ps["rm"])) if ps else 0)]
    for i, (name, qty, amt) in enumerate(civil):
        x = 5 + i
        ac.cell(x, 1, i + 1)
        ac.cell(x, 2, name)
        ac.cell(x, 3, qty)
        ac.cell(x, 4, amt).number_format = "#,##0.00"
    ac.cell(9, 2, "Total (A)").font = bold
    ac.cell(9, 4, "=SUM(D5:D8)").number_format = "#,##0.00"
    ac.cell(10, 1, "B").font = bold
    ac.cell(10, 2, "E&M Works" + (f" ({', '.join(ps['names'])}: sheet E&M SPS)" if ps else "")).font = bold
    em_cells = []
    x = 11
    for i, (name, cell) in enumerate((ps or {}).get("em", {}).items()):
        ac.cell(x, 1, i + 1)
        ac.cell(x, 2, name[:1].upper() + name[1:])
        ac.cell(x, 3, "1 Job")
        ac.cell(x, 4, f"={cell}").number_format = "#,##0.00"
        em_cells.append((name, f"'Abstract comprehensive'!D{x}"))
        x += 1
    if not em_cells:
        ac.cell(x, 2, "no pumping station in this design")
        ac.cell(x, 4, 0)
        x += 1
    ac.cell(x, 2, "Total (B)").font = bold
    ac.cell(x, 4, f"=SUM(D11:D{x - 1})").number_format = "#,##0.00"
    tb_ = x
    ac.cell(x + 1, 2, "Total (A+B)").font = bold
    ac.cell(x + 1, 4, f"=D9+D{tb_}").number_format = "#,##0.00"
    ac.cell(x + 2, 1, "C").font = bold
    ac.cell(x + 2, 2, "Power Connection Charges for SPS")
    ac.cell(x + 2, 4, f"={ps['power_total']}" if ps else 0).number_format = "#,##0.00"
    ac.cell(x + 3, 2, "Total (A+B+C)").font = bold
    ac.cell(x + 3, 4, f"=D{x + 1}+D{x + 2}").number_format = "#,##0.00"
    for row in ac.iter_rows(min_row=3, max_row=x + 3, max_col=4):
        for cell in row:
            cell.border = box
    acr = {"sewer": "'Abstract comprehensive'!D5", "hc": "'Abstract comprehensive'!D6",
           "sps": "'Abstract comprehensive'!D7", "rm": "'Abstract comprehensive'!D8", "em": em_cells,
           "total_ab": f"'Abstract comprehensive'!D{x + 1}", "power": f"'Abstract comprehensive'!D{x + 2}"}

    ab_c = sheet("ABS civil", "Abstract Cost - Civil", 4)
    header(ab_c, 3, ["Sl. No.", "Items", "Qty", "Amount (Rs. Lac)"], [7, 50, 16, 18])
    ab_c.cell(4, 1, "A").font = bold
    ab_c.cell(4, 2, "Civil Works").font = bold
    for i in range(4):
        x = 5 + i
        ab_c.cell(x, 1, i + 1)
        ab_c.cell(x, 2, f"='Abstract comprehensive'!B{x}")
        ab_c.cell(x, 3, f"='Abstract comprehensive'!C{x}")
        ab_c.cell(x, 4, f"='Abstract comprehensive'!D{x}").number_format = "#,##0.00"
    ab_c.cell(9, 2, "Total (A)").font = bold
    ab_c.cell(9, 4, "=SUM(D5:D8)").number_format = "#,##0.00"
    return acr


def _form_j_civil(X, PR, omr):
    """Sheet Form j civil: the cost of the civil works with contingency, cess, GST, centage and the O&M."""
    from openpyxl.styles import Alignment, Font

    S, wb, title = X.S, X.wb, X.title
    header, col, bold, yellow, box = X.header, X.col, X.bold, X.yellow, X.box
    fj = S["form_j"]
    fo = wb.create_sheet("Form j civil")
    fo.cell(1, 1, f'=""&{PR["office"]}').font = bold
    fo.cell(2, 1, title).font = Font(bold=True, size=12)
    fo.cell(3, 1, "FORM - 'J' (Civil)").font = bold
    for x in (1, 2, 3):
        fo.merge_cells(start_row=x, start_column=1, end_row=x, end_column=8)
        fo.cell(x, 1).alignment = Alignment(horizontal="center")
    fo.cell(4, 7, "Rs. (in lakh)")
    shares = fj["shares"]
    header(fo, 5, ["Sl. No.", "Description", "Amount in Lakh", "Rate", "Cost"] + [s[0] for s in shares],
           [7, 40, 14, 8, 14, 14, 14, 14])
    for j, s in enumerate(shares):
        c = fo.cell(6, 6 + j, s[1])
        c.fill, c.number_format = yellow, "0%"
    sc = [col(6 + j) for j in range(len(shares))]

    def split(x):
        for j, c in enumerate(sc):
            fo.cell(x, 6 + j, f"=$E${x}*{c}$6").number_format = "#,##0.00"

    fo.cell(7, 1, 1)
    fo.cell(7, 2, "Total cost of work")
    fo.cell(7, 3, "='ABS civil'!D9")
    fo.cell(7, 5, "=C7")
    fo.cell(8, 1, 2)
    fo.cell(8, 2, "Contingency")
    fo.cell(8, 5, fj["contingency_lakh"]).fill = yellow
    fo.cell(9, 2, "Sub Total (1+2)")
    fo.cell(9, 5, "=E7+E8")
    fo.cell(10, 1, 3)
    fo.cell(10, 2, "Less due to efficiency")
    fo.cell(10, 3, "=E9")
    fo.cell(10, 4, fj["efficiency_less"]).fill = yellow
    fo.cell(10, 5, "=C10*D10")
    fo.cell(11, 1, 4)
    fo.cell(11, 2, "Sub Total (2-3)")
    fo.cell(11, 5, "=E9-E10")
    split(11)
    fo.cell(12, 1, 5)
    fo.cell(12, 2, 'Labour Cess on "(4)"')
    fo.cell(12, 3, "=E11")
    fo.cell(12, 4, fj["labour_cess"]).fill = yellow
    fo.cell(12, 5, "=C12*D12")
    split(12)
    fo.cell(13, 1, 6)
    fo.cell(13, 2, "GST")
    fo.cell(13, 3, "=C12")
    fo.cell(13, 4, fj["gst"]).fill = yellow
    fo.cell(13, 5, "=C13*D13")
    split(13)
    fo.cell(14, 1, 7)
    fo.cell(14, 2, "Centage (on '(4)', by slab)")
    x, lo = 15, 0
    for upto, pct in fj["centage"]:
        if upto is None:
            fo.cell(x, 2, f"Above {lo / 100:g} Cr.")
            fo.cell(x, 3, f"=MAX(0,$E$11-{lo})")
        else:
            fo.cell(x, 2, f"{lo / 100:g} Cr. to {upto / 100:g} Cr." if lo else f"Upto {upto / 100:g} Cr.")
            fo.cell(x, 3, f"=MAX(0,MIN($E$11,{upto})-{lo})")
        fo.cell(x, 4, pct).fill = yellow
        fo.cell(x, 5, f"=C{x}*D{x}")
        lo = upto or lo
        x += 1
    fo.cell(x, 2, "Total Centage")
    fo.cell(x, 5, f"=SUM(E15:E{x - 1})")
    fo.cell(x, 7 if len(shares) > 1 else 6, f"=E{x}")       # centage on the State share, as in the sample
    cent = x
    x += 1
    fo.cell(x, 1, 8)
    fo.cell(x, 2, "Total (4+5+6+7)")
    fo.cell(x, 5, f"=E11+E12+E13+E{cent}")
    for j, c in enumerate(sc):
        fo.cell(x, 6 + j, f"={c}11+{c}12+{c}13+{c}{cent}")
    tot8 = x
    x += 1
    fo.cell(x, 1, 9)
    fo.cell(x, 2, "Operation & maintenance of the civil works for 5 years with GST (sheet ABS (O&M))")
    fo.cell(x, 5, f"={omr['civil_om']}")
    fo.cell(x, 5 + len(shares), f"=E{x}")                  # O&M on the ULB share, as in the sample
    om = x
    x += 1
    fo.cell(x, 1, 10)
    fo.cell(x, 2, "Total Project Cost")
    fo.cell(x, 5, f"=E{tot8}+E{om}")
    for j, c in enumerate(sc):
        fo.cell(x, 6 + j, f"=SUM({c}{tot8},{c}{om})")
    for row in fo.iter_rows(min_row=7, max_row=x, min_col=3, max_col=5 + len(shares)):
        for cell in row:
            if cell.column != 4:
                cell.number_format = "#,##0.00"
            elif cell.value is not None:
                cell.number_format = "0.00%"
    for row in fo.iter_rows(min_row=5, max_row=x, max_col=5 + len(shares)):
        for cell in row:
            cell.border = box
    front.signatures(fo, x + 2, PR)


def write_dpr(out, path, title="", inp=None, stations=None, previous=None):
    """The DPR workbook of a pipeline.run result at path. stations = the pumping stations of the zoning option
    [{"outfall", "dist" (straight distance to the STP, m, or None)}]; previous = an earlier DPR of the project, whose
    Project sheet texts are kept. Returns path."""
    from types import SimpleNamespace

    from openpyxl.styles import Alignment, Font

    X = _book(out, title, inp)
    wb, inp, f_pop = X.wb, X.inp, X.f_pop
    _zone_sheets(X)
    _manholes(X)
    _abstract(X)
    _boq(X)
    _sor_sheet(X)

    # ------------------------------------------------------------------ the sheets of dpr_more (Riverside estimate)
    B = SimpleNamespace(wb=wb, copied=set(), title=X.title, years=[X.y0, X.y0 + 15, X.y0 + 30], S=X.S, inp=inp, out=out,
                        sheet=X.sheet, header=X.header, col=X.col, bold=X.bold, head=X.head, yellow=X.yellow, box=X.box,
                        wrap=X.wrap, center=X.center, big=Font(bold=True, size=12),
                        italic=Font(italic=True), red=Font(italic=True, color="C00000"),
                        hcenter=Alignment(horizontal="center"), sor_rng=f"sor!$A$4:$D${3 + len(X.sor['items'])}",
                        boq=X.boq)
    PR = front.project(B, f_pop, inp, X.title_text, previous)
    B.PR = PR
    ps = more.pumping_stations(B, more.station_data(out, stations or []))
    T = front.tech(B, PR, f_pop, inp, out, ps, X.ref, X.dias)
    P = more.population(B, T, PR)
    hc = more.house_connections(B, P)
    front.coverage(B, PR, hc["count"])
    front.certificate(B, PR)
    front.bar_chart(B)
    acr = _abstract_cost(X, ps, hc)
    omr = more.om(B, ps, acr)
    fjc = more.form_j_compre(B, acr, omr)
    eco = more.economics(B, P, acr, omr, fjc)
    _form_j_civil(X, PR, omr)

    # sheet order as in the sample: Form J, abstracts, O&M, economics, BOQ, quantities, design statements, SOR
    order = ["Project", "Coverage", "Certificate", "Index", "Form j compre", "Form j civil", "Abstract comprehensive",
             "ABS civil", "ABS (O&M)", "Sewer Lines and RM", "5 yr O&M", "SPS O&M"] + eco + \
        ["Bar Chart", "Tech", "Population", "BOQ", "Abstract", "Manholes"] + \
        [z[2] for z in X.zone_sheets] + [z[1] for z in X.zone_sheets] + \
        ["hcc2", "hcc3", "house connection", "Table 160", "E&M SPS"] + ((ps or {}).get("sheets") or []) + ["sor"]
    front.index(B, index_entries([n for n in order if n in wb.sheetnames or n == "Index"]))
    order = [n for n in order if n in wb.sheetnames]
    wb._sheets = [wb[n] for n in order] + [w for w in wb.worksheets if w.title not in order]
    wb.calculation.fullCalcOnLoad = True
    dpr_format.apply(wb, copied=B.copied)                  # the look of the UPJN estimates, A4 pages
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    wb.save(path)
    return path
