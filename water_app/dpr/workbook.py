"""The water DPR workbook as a whole: the order and names of its sheets and write_dpr, which writes every sheet
(restructure stage 3, 15-Nov-2026: out of dpr.py)."""
import re
from .base import Book, SHEET_REF, q
from .technical import project, projection_charts, storage, summary, t1, t3, t_projection, tube_wells
from .distribution import ds, new_hc, rate_sheet, rc, sor_sheet, summary_ds, unit_estimates
from .tanks import cwr, ohts


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
        # E4-E9: the E&M design sheets of the Riverside water DPR (emd.py, user decision 6-Nov-2026)
        "EMD TW": "E4 TW Design", "EMD TW Est": "E5 TW Estimate", "EMD HP": "E6 HP & Transformer",
        "EMD CWR": "E7 CWR Electrical", "EMD PC": "E8 Power Connection", "EMD TR": "E9 Trial Run",
        "sor": "R SOR 2025-26", "Shif. HC": "D6 Shift HC",
        # C: the other civil works of the Riverside water DPR (civil.py, user decision 6-Nov-2026)
        "PH": "C1 Pump House", "BW": "C2 Site Development", "SQ": "C3 Staff Quarters", "GWR": "C4 GW Recharge",
        "MCS": "C5 MCS Building", "HT,LT": "C6 Panel Rooms",
        # T8-T13: the technical statement as the Riverside water DPR (tech.py, user decision 6-Nov-2026)
        "Wards": "T16 Ward Population", "DMA Pop": "T17 DMA Population", "Req": "T18 Water & Tube Wells",
        "MB OHT": "T19 OHT Mass Balance", "Static Head": "T20 Static Head", "Pipe Table": "T21 Pipe Table",
        # T14-T18: the example technical.xlsx 'Tech3'-'Tech7' (tech.py, user decision 9-Nov-2026)
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
    from . import em as em
    from . import more as more
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
    from . import rising_main as rm  # phase 2: the rising mains of the new tube wells
    rm.design(B)
    rm.estimate(B)
    rate_sheet(B)
    ohts(B)
    cwr(B)
    em.write(B)
    from . import civil as civ  # the other civil works of the Riverside water DPR (6-Nov-2026)
    B.CIV = {"ph": civ.pump_house(B), "bw": civ.site(B)}
    civ.buildings(B)
    from . import tech  # the technical statement as the Riverside water DPR (6-Nov-2026)
    B.TECH = tech.write(B)
    more.abstracts(B)
    more.om_economics(B)
    from . import front  # the front pages as the Riverside water DPR (7-Nov-2026)
    front.write(B)
    sor_sheet(B)
    by = {ws.title: ws for ws in B.wb.worksheets}
    names = sheet_names(B, units)                          # the technical sheets and after: in this order
    order = [n for n in ORDER if n in by] + [o for o in names if o in by and o not in ORDER]
    order += [n for n in by if n not in order]
    B.wb._sheets = [by[n] for n in order]
    B.wb.active = 0
    B.wb.calculation.fullCalcOnLoad = True
    from . import style
    style.apply(B.wb, copied=set(units) | B.keep_look, one_page=B.keep_look,   # the UPJN look, A4 pages
                     own=B.own_page)
    rename_sheets(B.wb, names)
    if TECH["T"] in B.wb.sheetnames:                  # the projection's graphs: on the sheet's final name (9-Nov-2026)
        projection_charts(B, B.wb[TECH["T"]])
    B.wb.save(path)
    return path
