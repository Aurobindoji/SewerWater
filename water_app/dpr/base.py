"""What every sheet of the water DPR workbook shares: the settings (dpr_water.json, with the user's rates), the schedule
of rates' file, the Project texts, the workbook and its styles (Book), the small helpers (restructure stage 3,
15-Nov-2026: out of dpr.py).

Water DPR workbook (Excel) in the format of the Elmwood water supply estimate of U.P. Jal Nigam (Springfield City Council;
sample Elmwood_water_ Estimate.xlsx) - user decisions 26-Oct-2026: an own workbook with live
formulas, phase 1 = the sheets the network design gives (the rest - WTP, rising / feeder mains, E&M ... - as yellow lump
sums); SOR items from sor_2025_26.json, the other rates and unit estimates as in the Elmwood estimate (dpr_water.json,
yellow, to be confirmed); OHT capacity = max(33 %, mass balance) as in the zoning (CPHEEO Table 2.7 S.No.12 p175).

    info = dpr_info(zones, pipes, outlets, dmas, closed, stages, crit, title)      (design_run.run_design builds it)
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
    + em.py: the E&M works and their O&M (EM rates W, EM TS, EM, EM O&M - U.P. Jal Nigam E&M estimate
      Riverside R3)
    + emd.py: the E&M design sheets of the Riverside water DPR p319-361 (EMD TW, EMD TW Est, EMD HP, EMD CWR,
      EMD PC, EMD TR) - the tube well, CWR transformers, trial runs and power connections of sheet EM
    + more.py: ABS Com, ABS Civil, Breakup, Form J Com., Form J Civil, O&M for 5 years, Economics and its
      statements, Certificate, Coverage, Index, Salient feature
    unit estimates (dpr_template.xlsx, from the Elmwood estimate) and sor
Yellow cells are inputs the user may change in Excel; the totals follow."""
import glob
import json
import os
import re
from copy import copy


HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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
    """dpr_water.json's values, its UPJN rates by size with the user's imported ones (rates.py, 15-Nov-2026)."""
    from .. import rates
    with open(SETTINGS_FILE, encoding="utf-8") as fh:
        return rates.apply({k: v["value"] for k, v in json.load(fh).items() if isinstance(v, dict) and "value" in v})


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


# ------------------------------------------------------------------------------------------------------------ template, sor
def _copy_cell(c, d):
    if c.has_style:
        d.font, d.border, d.fill = copy(c.font), copy(c.border), copy(c.fill)
        d.number_format, d.alignment, d.protection = c.number_format, copy(c.alignment), copy(c.protection)
