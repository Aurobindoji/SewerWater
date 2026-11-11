"""Water DPR workbook (Excel) in the format of the Elmwood water supply estimate of U.P. Jal Nigam (Springfield City Council;
sample Elmwood_water_ Estimate.xlsx) - user decisions 26-Oct-2026: an own workbook with live
formulas, phase 1 = the sheets the network design gives (the rest - WTP, rising / feeder mains, E&M ... - as yellow lump
sums); SOR items from sor_2025_26.json, the other rates and unit estimates as in the Elmwood estimate (dpr_water.json,
yellow, to be confirmed); OHT capacity = max(33 %, mass balance) as in the zoning (CPHEEO Table 2.7 S.No.12 p175).

    info = dpr_info(zones, pipes, outlets, dmas, closed, stages, crit, title)      (ui_api.run_design builds it)
    write_dpr(info, path, previous=None)

The sheets, each computed from the ones before it by Excel formulas (Elmwood names):
    Project            every text and input used on the other sheets (yellow); texts typed there are kept next time
    T1                 OZ-wise population (base / +15 / +30 years) and demands
    Storage            mass balance of an OHT over a day (filling hours, draw-off pattern) -> its share of the demand
    T3 (k)             technical statement of OZ k: demand, pumps, OHT storage, fire, CWR, pumping head, chlorine
    Summary, TW        existing and proposed OHTs / CWRs / tube wells; tube wells needed
    RC, Summary DS, DS pipe lengths of the design by OZ and size, excavation, road cutting, valves; the estimate
    NEW HC             house connections
    Est. OHT, OHT (k), CWR
    + dpr_em.py: the E&M works and their O&M (EM rates W, EM TS, EM, EM O&M - U.P. Jal Nigam E&M estimate
      Riverside R3)
    + dpr_emd.py: the E&M design sheets of the Riverside water DPR p319-361 (EMD TW, EMD TW Est, EMD HP, EMD CWR,
      EMD PC, EMD TR) - the tube well, CWR transformers, trial runs and power connections of sheet EM
    + dpr_more.py: ABS Com, ABS Civil, Breakup, Form J Com., Form J Civil, O&M for 5 years, Economics and its
      statements, Certificate, Coverage, Index, Salient feature
    unit estimates (dpr_template.xlsx, from the Elmwood estimate) and sor
Yellow cells are inputs the user may change in Excel; the totals follow.
"""
import glob
import json
import math
import os
import re
from copy import copy

HERE = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(HERE, "dpr_water.json")
SOR_FILE = os.path.join(HERE, "sor_2025_26.json")
TEMPLATE = os.path.join(HERE, "dpr_template.xlsx")
SOR_RNG = "sor!$A$6:$D$1509"
SHEET_REF = re.compile(r"(?:'((?:[^']|'')+)'|([A-Za-z_][\w\.]*))!")
SOR_LOOKUP = re.compile(r"VLOOKUP\(([^,()]+),sor!\$A\$6:\$D\$1509,4,0\)")
TEMPLATE_NAMES = {"Thrust250.": "Thrust 250"}
HC_TOTAL = "'NEW HC'!$F$8"                  # total of the house connections (Rs lakh)
HC_SHIFT = "'Shif. HC'!$F$8"                # total of the shifted house connections (Rs lakh)
ROADS = ["B.O.E. surface", "Bituminous surface", "C.C. Road", "Interlocking Road", "Kaccha Road"]
VALVES = [80, 100, 125, 150, 200, 250, 300, 350, 400, 450, 500, 600]

# the Project sheet: (key, label) - texts the user types once
TEXTS = [("title", "Name of the scheme"), ("ulb", "Name of the ULB / town"), ("district", "District"),
         ("under", "Programme (UNDER ...)"), ("office", "Office (division)"), ("circle", "Circle"),
         ("zone", "Zone (Chief Engineer's office)"),
         ("ae", "Assistant Engineer (Civil) - name"), ("ee", "Executive Engineer (Civil) - name"),
         ("se", "Superintending Engineer (Civil) - name"), ("ce", "Chief Engineer - name"),
         ("ae_em", "Assistant Engineer (E&M) - name"), ("ee_em", "Executive Engineer (E&M) - name"),
         ("se_em", "Superintending Engineer (E&M) - name"), ("computer", "Computer / checked by - name"),
         # the signatures under Form J as the user's example (form j combined.xlsx, 7-Nov-2026)
         ("computer_em", "Computer (E&M) - name"), ("office_em", "Office (E&M division)"),
         ("circle_em", "Circle (E&M)"), ("place", "Town of the divisions and the circle (e.g. Springfield)"),
         ("place_em_circle", "Town of the E&M circle (e.g. Westbrook)"),
         ("place_zone", "Town of the Chief Engineer's office (e.g. Westbrook)")]
COVER = [("hh_census", "Households of the city as per the last census"),
         ("hh_base", "Households of the city in the base year"),
         ("hh_before", "Households with water connections before AMRUT 1.0"),
         ("hh_amrut1", "Households with water connections sanctioned under AMRUT 1.0"),
         ("hh_amrut2", "Households with water connections already sanctioned under AMRUT 2.0"),
         ("city_base", "Population of the city (ULB) in the base year - Salient features"),
         ("city_mid", "Population of the city (ULB) in the middle year (+15)"),
         ("city_design", "Population of the city (ULB) in the design year (+30)")]
DEFAULT_TEXTS = {"under": "AMRUT 2.0"}            # a new project's text (yellow, to change)
KEPT = [("hc_shift", "Existing house connections shifted to the new pipes (nos)")]     # other inputs kept the same way


def settings():
    with open(SETTINGS_FILE, encoding="utf-8") as fh:
        return {k: v["value"] for k, v in json.load(fh).items() if isinstance(v, dict) and "value" in v}


def standby(w, tab):
    """Standby for w working (a cell) as CPHEEO water manual Part A 5.7.5 p245-246 (criteria "standby_pumps", user
    decisions 7-Nov-2026): tab = [[working up to, standby], ...] (1-2: 1, 3-5: 2, 6-10: 3); more working than the
    table: its last; none: 0."""
    f = str(tab[-1][1])
    for up, s in reversed(tab[:-1]):
        f = f"IF({w}<={up},{s},{f})"
    return f"IF({w}<=0,0,{f})"


def motor_margin(P, kw):
    """The formula of the margin on a motor of kw (an Excel expression) - the CPHEEO table of the Riverside water DPR
    p360 (dpr_water.json pump.motor_margin: [[up to kW, margin]], the last open)."""
    *steps, (_, last) = P["motor_margin"]
    f = f"{last:g}"
    for upto, m in reversed(steps):
        f = f"IF({kw}<={upto:g},{m:g},{f})"
    return f


def q(name):
    """A sheet name as a formula needs it."""
    return "'" + name.replace("'", "''") + "'" if re.search(r"[^A-Za-z0-9_]", name) else name


def _natural(s):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", str(s))]


def size_key(name):
    """'HDPE 110' -> ('HDPE', 110)."""
    m = re.match(r"([A-Za-z]+)\s*(\d+)", name or "")
    return (m.group(1).upper(), int(m.group(2))) if m else ("", 0)


def dpr_info(zones, pipes, outlets, dmas, closed, stages, crit, title):
    """What write_dpr needs from a design: the OZs (zoning + the design's OHT outlets), the pipes by OZ and size and the
    sluice valves the network asks for (dpr_water.json valves_rule)."""
    S = settings()
    vop = S["valve_of_pipe"]
    by_lab = {p["label"]: p for p in pipes}
    out = {o["name"]: o for o in outlets}
    zs = []
    for z in zones:
        o = out.get(z["name"], {})
        zs.append({"name": z["name"], "population": z["population"], "connections": z["connections"],
                   "demand_kld": z["demand_kld"], "bulk_kld": z.get("bulk_kld") or 0.0,
                   "capacity_kl": z.get("capacity_kl"), "required_kl": z["required_kl"],
                   "cwr_kl": z.get("cwr_kl"), "tubewells": z.get("tubewells") or 0, "rebore": z.get("rebore") or 0,
                   "dmas": z.get("dma_count") or 1,
                   "existing": bool(z.get("capacity_kl")), "proposed": bool(o.get("proposed") or z.get("proposed")),
                   "staging_m": o.get("staging_m"), "vfd_head_m": o.get("vfd_head_m"), "vfd_kw": o.get("vfd_kw"),
                   "flow_lps": o.get("flow"),
                   "outlet": o.get("size"), "elev_min": z.get("elev_min"), "elev_max": z.get("elev_max")})
    names = [z["name"] for z in zs]
    length = {n: {} for n in names}
    for p in pipes:
        if p.get("size") and p.get("oz") in length:
            length[p["oz"]][p["size"]] = length[p["oz"]].get(p["size"], 0.0) + float(p["length"] or 0.0)
    valves = {n: {} for n in names}

    def add(oz, size):
        d = vop.get(size)
        if oz in valves and d:
            valves[oz][d] = valves[oz].get(d, 0) + 1
    for lab in closed:
        p = by_lab.get(lab)
        if p:
            add(p.get("oz"), p.get("size"))
    for d in dmas:
        p = by_lab.get(d.get("inlet_pipe") or "")
        if p:
            add(d.get("zone"), p.get("size"))
    for z in zs:
        add(z["name"], z["outlet"])
    return {"title": title, "zones": zs, "length": length, "valves": valves, "stages": stages,
            "pop": sum(z["population"] for z in zs), "crit": crit,
            "sizes": sorted({s for v in length.values() for s in v}, key=lambda s: (size_key(s)[0] != "HDPE",
                                                                                   size_key(s)[1]))}


def previous_dpr(folder, stem):
    """The newest earlier water DPR of the project (its Project texts are kept), or None."""
    xs = sorted(glob.glob(os.path.join(folder, f"{glob.escape(stem)}_water_design_*_DPR.xlsx")), key=os.path.getmtime)
    return xs[-1] if xs else None


def _previous(path):
    """{key: value} of the Project sheet of an earlier DPR (the texts the user typed there), or {}."""
    if not path or not os.path.isfile(path):
        return {}
    try:
        import openpyxl
        ws = openpyxl.load_workbook(path, read_only=True)["Project"]
        rows = {r[1]: r[2] for r in ws.iter_rows(min_row=1, max_row=120, max_col=3, values_only=True) if r[1]}
    except Exception:
        return {}
    out = {}
    for key, label in TEXTS + COVER + KEPT:
        v = rows.get(label)
        if v not in (None, "") and not (isinstance(v, str) and v.startswith("=")):
            out[key] = v
    return out


class Book:
    """The workbook and its styles; .cell(ws, r, c, v, ...) writes with a border, .yellow marks an input."""

    def __init__(self, info):
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        from openpyxl.utils import get_column_letter
        self.info, self.S, self.crit = info, settings(), info["crit"]
        self.wb = Workbook()
        self.wb.remove(self.wb.active)
        self.col = get_column_letter
        self.bold, self.big = Font(bold=True), Font(bold=True, size=12)
        self.italic, self.red = Font(italic=True, color="555555"), Font(color="C00000")
        self.head = PatternFill("solid", fgColor="D9E1F2")
        self.yellow = PatternFill("solid", fgColor="FFF2CC")
        thin = Side(style="thin", color="999999")
        self.box = Border(left=thin, right=thin, top=thin, bottom=thin)
        self.wrap = Alignment(wrap_text=True, vertical="top")
        self.center = Alignment(horizontal="center", vertical="center", wrap_text=True)
        self.hcenter = Alignment(horizontal="center")
        self.right = Alignment(horizontal="right")
        self.title = "=Project!$C$4"
        self.PR = {}

    def sheet(self, name, heading, ncols):
        ws = self.wb.create_sheet(name)
        ws.cell(1, 1, self.title).font = self.big
        ws.cell(2, 1, f'=""&{self.PR["office"]}' if "office" in self.PR else "").font = self.bold
        ws.cell(3, 1, heading).font = self.bold
        for r in (1, 2, 3):
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=ncols)
            ws.cell(r, 1).alignment = self.hcenter
        return ws

    def header(self, ws, r, names, widths=None):
        for c, h in enumerate(names, 1):
            x = ws.cell(r, c, h)
            x.font, x.fill, x.alignment, x.border = self.bold, self.head, self.center, self.box
        for c, w in enumerate(widths or [], 1):
            if w:
                ws.column_dimensions[self.col(c)].width = w

    def cell(self, ws, r, c, v, fmt=None, inp=False, bold=False):
        x = ws.cell(r, c, v)
        x.border = self.box
        if fmt:
            x.number_format = fmt
        if inp:
            x.fill = self.yellow
        if bold:
            x.font = self.bold
        return x

    def sign(self, ws, r, c=2):
        """'Assistant Engineer' under a sheet, as the Elmwood sheets."""
        ws.cell(r, c, "Assistant Engineer").font = self.bold


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
    from .dpr_front import head
    from .population import NAMES, METHODS
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
    from .population import NAMES
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
    from . import demand as dm
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
             f"=IF(F{r + 5}>0,0,CEILING(F{r + 4},{PR['round_kl']}))", "KL",
             "an existing OHT keeps the OZ its capacity serves (zoning); a new one rounded up")]
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
    ws.cell(x, 2, f'=IF(AND(F{ref["exist"]}>0,F{ref["exist"]}<F{ref["need"]}),"existing capacity less than required - '
                  f'its OZ is too big (zoning flags it)","")').font = B.red
    ws.cell(x + 1, 8, f"zoning: {z['required_kl']:,.0f} KL required ({'existing' if z['existing'] else 'new'} OHT)")
    r = x + 3

    # -------- CWR (UPJN rule), CPHEEO 2.8.1.17 p127
    ws.cell(r, 2, "CWR (U.P. Jal Nigam rule: mandatory when more than 3 new tube wells fill one OHT; CPHEEO 2.8.1.17 "
                  "p127: 25 % of the ESR)").font = B.bold
    r += 1
    cw0 = r
    cap = f"MAX(F{ref['exist']},F{ref['new']})"
    sw = B.S["swd"]

    def _cone_of(zz):          # the cone of a new Intze OHT below its wall's SWD (user decision 10-Nov-2026)
        if zz.get("existing") or not zz.get("required_kl"):
            return 0.0
        from . import intze
        kl = float(zz["required_kl"])            # the zoning's capacity, already rounded (criteria)
        return round(intze.cone_depth(kl, next(d for c, d in sw if c is None or kl <= c)), 3)
    swd_of = lambda kl: f"IF({kl}<={sw[0][0]},{sw[0][1]},IF({kl}<={sw[1][0]},{sw[1][1]},{sw[2][1]}))"
    swd = swd_of(cap)
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
            ("Depth of water in OHT", f"={swd}" + (f"+IF(F{ref['exist']}>0,0,{_cone_of(z)})" if _cone_of(z) else ""), "m",
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
                "=" + standby(f"L{x}", B.crit["standby_pumps"]["value"]), f"=L{x}+N{x}", z.get("rebore") or 0]
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


# ------------------------------------------------------------------------------------------------------------ OHT, CWR
def table_rate(cap, caps, rates):
    """Rs per litre of a tank of cap KL from a rate table: linear between its capacities, the end rate beyond them
    (user decision 26-Oct-2026) - what the formula of sheet 'OHT UGR rates' gives."""
    if cap <= caps[0]:
        return rates[0]
    if cap >= caps[-1]:
        return rates[-1]
    i = max(j for j, c in enumerate(caps) if c <= cap)
    return rates[i] + (cap - caps[i]) * (rates[i + 1] - rates[i]) / (caps[i + 1] - caps[i])


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


def ohts(B):
    """New OHTs (Elmwood 'OHT Z-7'): the U.P. Jal Nigam standard cost per litre at 25 m staging (sheet OHT UGR rates),
    +/- 15 % for every 25 m more / less, and their abstract."""
    O = B.S["oht"]
    made = []
    for k, t in enumerate(B.T3, 1):
        z = t["zone"]
        if z["existing"]:
            continue
        s, rf = q(t["sheet"]), t["ref"]
        name = f"OHT ({len(made) + 1})"
        ws = B.sheet(name, f"ESTIMATE FOR CONSTRUCTION OF RCC OVER HEAD TANK FOR OPERATION ZONE {z['name']}", 10)
        for c, w in zip("ABCDEFGHIJ", (6, 60, 6, 6, 6, 6, 14, 8, 12, 16)):
            ws.column_dimensions[c].width = w
        B.header(ws, 5, ["Sl. No.", "Description of work", "No.", "L", "B", "H", "Qty", "Unit", "Rate", "Amount (Rs)"])
        ws["L5"], ws["L6"], ws["L7"] = "Capacity (KL)", "Staging (m)", "Rs / litre at 25 m staging"
        ws["L8"], ws["L9"], ws["L10"] = "Base staging (m)", "Change per 25 m more / less", "Rate / litre"
        ws["M5"], ws["M6"] = f"={s}!F{rf['new']}", f"={s}!F{rf['head'] - 5}"
        ws["M7"], ws["M8"], ws["M9"] = "=" + B.RATE("M5", "B"), O["staging_base_m"], O["per_25m"]
        ws["M10"] = "=M7*(1+(M6-M8)/25*M9)"
        ws["M7"].number_format = ws["M10"].number_format = "0.00"
        for c in ("M8", "M9"):
            ws[c].fill = B.yellow
        ws.column_dimensions["L"].width = 26
        txt = ('="Supply of all materials, labour, T&P etc. and construction of RCC over head tank of "&M5&" KL '
               'capacity and "&M6&" m staging in M-30 concrete, with staircase, balcony, railing, ventilator, water '
               'level indicator, lightning conductor, CI manhole, CI D/F inlet / outlet / overflow / washout pipes and '
               'sluice valves, valve chambers, painting and gate - complete (departmental rate)"')
        B.cell(ws, 7, 1, 1)
        B.cell(ws, 7, 2, txt).alignment = B.wrap
        ws.row_dimensions[7].height = 90
        B.cell(ws, 7, 3, 1)
        B.cell(ws, 7, 7, "=M5*1000", fmt="#,##0")
        B.cell(ws, 7, 8, "litre")
        B.cell(ws, 7, 9, "=M10", fmt="#,##0.00")
        B.cell(ws, 7, 10, "=G7*I7", fmt="#,##0")
        for i, (lab, v) in enumerate((("Provision for theme painting on the OHT wall", O["theme_painting"]),
                                      ("Provision for soil testing", O["soil_testing"])), 2):
            x = 6 + i
            B.cell(ws, x, 1, i)
            B.cell(ws, x, 2, lab)
            B.cell(ws, x, 3, 1)
            B.cell(ws, x, 7, 1)
            B.cell(ws, x, 8, "job")
            B.cell(ws, x, 9, v, fmt="#,##0", inp=True)
            B.cell(ws, x, 10, f"=G{x}*I{x}", fmt="#,##0")
        B.cell(ws, 10, 9, "Total", bold=True)
        B.cell(ws, 10, 10, "=SUM(J7:J9)", fmt="#,##0", bold=True)
        B.cell(ws, 11, 9, "Say (lakh)", bold=True)
        B.cell(ws, 11, 10, "=ROUND(J10/100000,2)", fmt="#,##0.00", bold=True)
        ws.cell(13, 2, "Rate: U.P. Jal Nigam standard cost of OHT of 25 m staging, FY 2022-23, escalated (sheet OHT UGR "
                       "rates); +/- 15 % for every 25 m more / less staging (Elmwood 'OHT Z-7').").font = B.italic
        B.sign(ws, 16, 9)
        made.append((name, z, k))
    ws = B.sheet("Est. OHT", "ABSTRACT OF COST OF R.C.C. OVERHEAD TANKS", 5)
    B.header(ws, 5, ["S. No.", "Particulars", "Qty.", "Capacity of OHT and staging", "Amount (Rs. lakh)"],
             [6, 50, 8, 26, 16])
    x = 6
    for i, (name, z, k) in enumerate(made, 1):
        B.cell(ws, x, 1, i)
        B.cell(ws, x, 2, f"Construction of RCC OHT for operation zone {z['name']}")
        B.cell(ws, x, 3, "1 No.")
        B.cell(ws, x, 4, f'={q(name)}!M5&" KL / "&{q(name)}!M6&" m"')
        B.cell(ws, x, 5, f"={q(name)}!J11", fmt="#,##0.00")
        x += 1
    B.cell(ws, x, 2, "Total", bold=True)
    B.cell(ws, x, 5, f"=SUM(E6:E{x - 1})" if made else 0, fmt="#,##0.00", bold=True)
    tot = x
    # repairs of the existing OHTs (user decision 6-Nov-2026, in place of a share of a new one): the detailed estimate of
    # the Riverside water DPR (sheets Rep. OHT (k), dpr_civil.oht_repair)
    from . import dpr_civil
    ex = [z for z in B.info["zones"] if z.get("existing") and z.get("capacity_kl")]
    rep = None
    if ex:
        x = tot + 2
        ws.cell(x, 2, "Repairing of existing R.C.C. over head tanks including all materials, labour, T & P etc. complete "
                      "(as per estimate enclosed)").font = B.bold
        x += 1
        r0 = x
        for i, z in enumerate(ex, 1):
            B.cell(ws, x, 1, i)
            B.cell(ws, x, 2, f"For operation zone {z['name']}")
            B.cell(ws, x, 3, "1 No.")
            stg = f" / {z['staging_m']:g} M" if z.get("staging_m") is not None else ""
            B.cell(ws, x, 4, f"{z['capacity_kl']:,.0f} KL{stg}")
            B.cell(ws, x, 5, f"={dpr_civil.oht_repair(B, z, i)}", fmt="#,##0.00")
            x += 1
        B.cell(ws, x, 2, "Total (repairs)", bold=True)
        B.cell(ws, x, 5, f"=SUM(E{r0}:E{x - 1})", fmt="#,##0.00", bold=True)
        rep = f"'Est. OHT'!$E${x}"
        B.cell(ws, x + 1, 2, "Grand total (new + repairs)", bold=True)
        B.cell(ws, x + 1, 5, f"=E{tot}+E{x}", fmt="#,##0.00", bold=True)
        x += 2
    else:
        x = tot + 2
        ws.cell(x, 2, "No existing OHT on the map - no repairs.").font = B.italic
    B.sign(ws, x + 2, 4)
    B.OHT = {"lakh": f"'Est. OHT'!$E${tot}", "n": len(made), "sheets": [m[0] for m in made],
             "zones": [m[1]["name"] for m in made], "repair": rep, "n_repair": len(ex),
             "repair_sheets": [f"Rep. OHT ({i})" for i in range(1, len(ex) + 1)],
             "repair_zones": [z["name"] for z in ex]}


def cwr(B):
    """New CWRs at the U.P. Jal Nigam standard cost of UGR per litre (sheet OHT UGR rates) + soil testing."""
    C = B.S["cwr"]
    ws = B.sheet("CWR", "ESTIMATE OF C.W.R. (U.P. JAL NIGAM STANDARD COST OF UGR)", 6)
    B.header(ws, 5, ["S.N.", "Description", "Qty.", "Unit", "Rate", "Amount (Rs)"], [6, 56, 8, 8, 14, 16])
    ws["H6"], ws["I6"] = "Soil testing (Rs)", C["soil_testing"]
    ws["I6"].fill = B.yellow
    ws.column_dimensions["H"].width = 18
    x = 6
    for t in B.T3:
        s, rf = q(t["sheet"]), t["ref"]
        B.cell(ws, x, 2, f"Operation zone {t['zone']['name']}", bold=True)
        B.cell(ws, x + 1, 2, f'={s}!F{rf["cwr"]}&" KL CWR"')
        B.cell(ws, x + 1, 3, f"=IF({s}!F{rf['cwr']}>0,1,0)")
        B.cell(ws, x + 1, 4, "No")
        cap = f"{s}!F{rf['cwr']}"
        B.cell(ws, x + 1, 5, f"=IF({cap}>0,{B.RATE(cap, 'C')}*{cap}*1000,0)", fmt="#,##0")
        B.cell(ws, x + 1, 6, f"=C{x + 1}*E{x + 1}", fmt="#,##0")
        B.cell(ws, x + 2, 2, "Provision for soil testing")
        B.cell(ws, x + 2, 3, f"=C{x + 1}")
        B.cell(ws, x + 2, 4, "LS")
        B.cell(ws, x + 2, 5, "=$I$6", fmt="#,##0")
        B.cell(ws, x + 2, 6, f"=C{x + 2}*E{x + 2}", fmt="#,##0")
        x += 3
    B.cell(ws, x, 2, "Grand total", bold=True)
    B.cell(ws, x, 6, f"=SUM(F6:F{x - 1})", fmt="#,##0", bold=True)
    B.cell(ws, x + 1, 2, "Rs. in lakh", bold=True)
    B.cell(ws, x + 1, 6, f"=ROUND(F{x}/100000,2)", fmt="#,##0.00", bold=True)
    ws.cell(x + 3, 2, "Rate: U.P. Jal Nigam standard cost of UGR per litre, FY 2022-23, escalated (sheet OHT UGR "
                      "rates); soil testing as the Elmwood 'CWR'.").font = B.italic
    B.sign(ws, x + 5, 5)
    B.CWR = {"lakh": f"CWR!$F${x + 1}"}


# ------------------------------------------------------------------------------------------------------------ template, sor
def _copy_cell(c, d):
    if c.has_style:
        d.font, d.border, d.fill = copy(c.font), copy(c.border), copy(c.fill)
        d.number_format, d.alignment, d.protection = c.number_format, copy(c.alignment), copy(c.protection)


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
        if ws.title.startswith("Thrust") and ws.title != "Thrust (2)":     # another project's name in the Elmwood copies
            ws["A1"], ws["A2"], ws["A3"], ws["A4"] = "ESTIMATE FOR", B.title, f'=""&{B.PR["under"]}', None
        elif ws.title in ("HT", "LT", "booster room"):
            ws["A1"], ws["A2"], ws["A3"] = B.title, f'="DISTRICT - "&{B.PR["district"]}', f'=""&{B.PR["under"]}'
    return list(names.values())


def sor_sheet(B):
    with open(SOR_FILE, encoding="utf-8") as fh:
        sor = json.load(fh)
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


# ------------------------------------------------------------------------------------------------------------ the book
ORDER = ["Project", "Cover", "Checklist", "Certificate", "Coverage", "Title - Index", "Index", "Title - Salient",
         "Salient feature", "Title - Project Report", "Title - Financial", "Form J Com.", "ABS Com",
         "Form J Civil", "ABS Civil", "Form J E&M", "EM", "Breakup", "5Yr O&M Com", "5 Yr O&M Civil", "Title - Economics", "Economics", "Income", "Ann. Expe", "Electicity",
         "Chemical", "Repair on Works", "A.Ex. Staff", "Cess", "Title - Technical"]
# the technical sheets and those after them (user request 30-Oct-2026): a group letter + number + a short name -
# T technical statement, D distribution system, S storage structures, E E&M, U unit estimates, R the schedule of rates;
# the workbook is built with the Elmwood names and renamed at the end (rename_sheets), its formulas with it
# the technical statement in the example technical.xlsx's order (user decision 9-Nov-2026): T1 Population ('T'),
# T2 Town Wards ('Tech '), T3 Ward Projection ('Tech1'), T4 Zone Population ('Tech2'), T5-T9 ('Tech3'-'Tech7'), then
# the sheets of the Riverside water DPR T10-T21 (T14-xx: each OZ's statement)
TECH = {"T": "T1 Population", "Town Wards": "T2 Town Wards", "Ward Proj": "T3 Ward Projection",
        "Zone Pop": "T4 Zone Population",
        "T1": "T10 OZ Demand", "Storage": "T11 Mass Balance", "TW": "T12 Tube Wells",
        "Summary": "T13 OZ Summary", "RC": "D1 Pipe & Road", "DS": "D2 DS Estimate", "Summary DS": "D3 DS Summary",
        "NEW HC": "D4 House Conn", "RM Design": "T15 Rising Main", "RM": "D5 Rising Main", "Est. OHT": "S1 OHT Abstract", "CWR": "S2 CWR", "OHT UGR rates": "S3 OHT-UGR Rates",
        # the E&M abstract of cost: in the financial statement after Form J E&M, as the Riverside water DPR p48-56
        # (user 7-Nov-2026), named as the other abstracts; the E sheets numbered without it
        "EM TS": "E1 EM Tech Stmt", "EM": "ABS E&M", "EM O&M": "E2 EM O&M", "EM rates W": "E3 EM Rates",
        # E4-E9: the E&M design sheets of the Riverside water DPR (dpr_emd.py, user decision 6-Nov-2026)
        "EMD TW": "E4 TW Design", "EMD TW Est": "E5 TW Estimate", "EMD HP": "E6 HP & Transformer",
        "EMD CWR": "E7 CWR Electrical", "EMD PC": "E8 Power Connection", "EMD TR": "E9 Trial Run",
        "sor": "R SOR 2025-26", "Shif. HC": "D6 Shift HC",
        # C: the other civil works of the Riverside water DPR (dpr_civil.py, user decision 6-Nov-2026)
        "PH": "C1 Pump House", "BW": "C2 Site Development", "SQ": "C3 Staff Quarters", "GWR": "C4 GW Recharge",
        "MCS": "C5 MCS Building", "HT,LT": "C6 Panel Rooms",
        # T8-T13: the technical statement as the Riverside water DPR (dpr_tech.py, user decision 6-Nov-2026)
        "Wards": "T16 Ward Population", "DMA Pop": "T17 DMA Population", "Req": "T18 Water & Tube Wells",
        "MB OHT": "T19 OHT Mass Balance", "Static Head": "T20 Static Head", "Pipe Table": "T21 Pipe Table",
        # T14-T18: the example technical.xlsx 'Tech3'-'Tech7' (dpr_tech.py, user decision 9-Nov-2026)
        "DMA Demand": "T5 DMA Demand", "Zone Summary": "T6 Zone Summary", "OHT Details": "T7 OHT Details",
        "DMA HH": "T8 DMA Pop & HH", "Zone HH": "T9 Zone Households"}
# the example technical.xlsx's sheets (after T1 Population, in its order)
EXAMPLE_TECH = ("Town Wards", "Ward Proj", "Zone Pop", "DMA Demand", "Zone Summary", "OHT Details", "DMA HH", "Zone HH")
UNIT_NAMES = {"FH CHAMBER": "FH Chamber", "AV CHAMBER": "AV Chamber", "MS Pipe Rate": "MS Pipe",
              "Dismantling of Road": "Road Dismantle", "reins": "Road Reinstate",
              "Bituminous Reinstatement": "Bitumen Reinstate", "interlocking": "Interlocking",
              "Summary (2)": "Unit Rates", "Plinth Area Rate": "Plinth Area Rate", "PH 3.6x3.0": "Pump House",
              "ByPass": "Bypass Chamber", "BW (7)": "Boundary Wall", "Earth": "Earth Filling", "SQ (6)": "Staff Quarter",
              "MCS (2)": "MCS", "PH Repaire": "PH Repair", "BW Repaire": "BW Repair", "Girder pillar (2)": "Girder Pillar",
              "Thrust (2)": "Thrust Block", "GWR-Mes": "GWR Measurement", "GWR-Abs": "GWR Abstract",
              "Ground water": "GW Recharge", "HT": "HT Room", "LT": "LT Room", "booster room": "Booster Room"}
INDEX_GROUPS = {"TECHNICAL STATEMENT": "T", "ESTIMATES OF CIVIL WORKS": "DSC", "ESTIMATES OF E&M WORKS": "E",
                "UNIT ESTIMATES": "U", "SCHEDULE OF RATES": "R"}


def _title(s):
    """A sheet name Excel takes: none of []:*?/\\, at most 31 characters."""
    return re.sub(r"[\[\]:*?/\\]", "-", s).strip()[:31].rstrip()


def sheet_names(B, units):
    """{Elmwood name: new name} of the technical sheets and those after them, in their order."""
    m = {"T": TECH["T"]}
    made = getattr(B, "TECH", [])
    for old in EXAMPLE_TECH:                                    # the example technical.xlsx's, first (9-Nov-2026)
        if old in made:
            m[old] = TECH[old]
    for old in ("T1", "Storage", "TW", "Summary"):
        m[old] = TECH[old]
    for i, t in enumerate(B.T3, 1):                             # each OZ's statement: its OHT in the name
        m[t["sheet"]] = _title(f"T14-{i:02d} {t['zone']['name']}")
    m["RM Design"] = TECH["RM Design"]
    for old in made:
        if old not in m:
            m[old] = TECH[old]
    for old in ("RC", "DS", "Summary DS", "NEW HC", "RM", "Shif. HC", "Est. OHT"):
        m[old] = TECH[old]
    for i, (s, zn) in enumerate(zip(B.OHT["sheets"], B.OHT["zones"]), 1):
        m[s] = _title(f"S1-{i:02d} {zn}")
    for old in ("CWR", "OHT UGR rates"):
        m[old] = TECH[old]
    for i, (s, zn) in enumerate(zip(B.OHT.get("repair_sheets", []), B.OHT.get("repair_zones", [])), 1):
        m[s] = _title(f"S4-{i:02d} Rep {zn}")
    for old in ("PH", "BW", "SQ", "GWR", "MCS", "HT,LT", "EM TS", "EM", "EM O&M", "EM rates W", "EMD TW",
                "EMD TW Est", "EMD HP", "EMD CWR", "EMD PC", "EMD TR"):
        m[old] = TECH[old]
    for i, u in enumerate(units, 1):
        m[u] = _title(f"U{i:02d} {UNIT_NAMES.get(u, u)}")
    m["sor"] = TECH["sor"]
    return m


def rename_sheets(wb, names):
    """Rename the sheets ({old: new}, those in the workbook) and every reference to them: the formulas of all sheets,
    'sheet <name>' in their notes, the Index's lists of sheets."""
    names = {o: n for o, n in names.items() if o in wb.sheetnames and o != n}
    if len(set(names.values())) < len(names):
        raise ValueError("two sheets would get one name")

    def sub(m):
        s = (m.group(1) or m.group(2)).replace("''", "'")
        return q(names[s]) + "!" if s in names else m.group(0)
    note = re.compile(r"\bsheets? '?(" + "|".join(re.escape(o) for o in sorted(names, key=len, reverse=True)) +
                      r")'?(?![\w(])")
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                v = c.value
                if not isinstance(v, str):
                    continue
                if v.startswith("="):
                    c.value = SHEET_REF.sub(sub, v)
                elif "sheet" in v:
                    c.value = note.sub(lambda m: m.group(0).split(" ")[0] + " " + names[m.group(1)], v)
    for o, n in names.items():
        wb[o].title = n
    if "Index" in wb.sheetnames:                                   # the lists of sheets by group
        ix, all_ = wb["Index"], wb.sheetnames
        for r in range(1, ix.max_row + 1):
            g = INDEX_GROUPS.get(str(ix.cell(r, 2).value or "").strip())
            if g == "E":
                ix.cell(r, 5).value = ", ".join(s for s in all_ if s[:1] == "E" and s[1:2].isdigit())
            elif g:
                ix.cell(r, 5).value = ", ".join(s for s in all_ if s[:1] in g and s[1:2].isdigit() or
                                                (g == "R" and s.startswith("R ")))


def write_dpr(info, path, previous=None):
    """The water DPR workbook of a design (dpr_info) at path; previous = an earlier DPR of the project whose Project
    texts are kept. Returns path."""
    from . import dpr_em as em
    from . import dpr_more as more
    B = Book(info)
    B.T3 = []
    project(B, previous)
    t_projection(B)                                   # always: the technical statement starts with it (p68)
    t1(B)
    storage(B)
    for k, z in enumerate(info["zones"], 1):
        t3(B, k, z)
    tube_wells(B)
    summary(B)
    rc(B)
    summary_ds(B)
    units = unit_estimates(B)
    ds(B)
    new_hc(B)
    new_hc(B, shift=True)
    from . import dpr_rm as rm                        # phase 2: the rising mains of the new tube wells
    rm.design(B)
    rm.estimate(B)
    rate_sheet(B)
    ohts(B)
    cwr(B)
    em.write(B)
    from . import dpr_civil as civ                    # the other civil works of the Riverside water DPR (6-Nov-2026)
    B.CIV = {"ph": civ.pump_house(B), "bw": civ.site(B)}
    civ.buildings(B)
    from . import dpr_tech                            # the technical statement as the Riverside water DPR (6-Nov-2026)
    B.TECH = dpr_tech.write(B)
    more.abstracts(B)
    more.om_economics(B)
    from . import dpr_front                           # the front pages as the Riverside water DPR (7-Nov-2026)
    dpr_front.write(B)
    sor_sheet(B)
    by = {ws.title: ws for ws in B.wb.worksheets}
    names = sheet_names(B, units)                          # the technical sheets and after: in this order
    order = [n for n in ORDER if n in by] + [o for o in names if o in by and o not in ORDER]
    order += [n for n in by if n not in order]
    B.wb._sheets = [by[n] for n in order]
    B.wb.active = 0
    B.wb.calculation.fullCalcOnLoad = True
    from . import dpr_format
    dpr_format.apply(B.wb, copied=set(units) | B.keep_look, one_page=B.keep_look,   # the UPJN look, A4 pages
                     own=B.own_page)
    rename_sheets(B.wb, names)
    if TECH["T"] in B.wb.sheetnames:                  # the projection's graphs: on the sheet's final name (9-Nov-2026)
        projection_charts(B, B.wb[TECH["T"]])
    B.wb.save(path)
    return path
