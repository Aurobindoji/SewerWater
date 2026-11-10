"""The town's wards, once for all its projects (user decisions 9-Nov-2026): an xlsx in the format of the user's
'WARDWISE POPULATION AND AREA' table - Sl. No, Name of ULB, No of ward, name of ward, population of a year (total,
households), Eq. area (ha), Census 2011, density, character of ward - exported (the town's list, or the page's
table to begin with, or empty) and imported; the imported list kept by town in the master folder (cities\\<town>.json)
for every project of that town: a project's wards (from the KML) matched to it by Ward No. / name, their population,
households, Eq. area, census and character taken from it (the xlsx's over the KML's), the density on the Eq. area
(CPHEEO Manual on Water Supply 2024 Part A, 2.8.1.24 (iii)), the town's population by character from it.

    export_xlsx(city, year, rows) -> bytes       import_xlsx(data, fname) -> {city, year, rows, notes}
    save(d, fname) / load(city) / cities()
"""
import base64
import collections
import datetime
import io
import json
import os
import re

# the characters of a ward, densest first (CPHEEO Annexure 2.7's categories with the DPR's word, 9-Nov-2026; as
# ui_api.WARD_CHARS) and the old names (a list / xlsx of before) read as them
CHARS = ("Saturated (Core)", "High (Proximal Developed)", "Medium (Proximal Developing)", "Low (Far-open)")
OLD = dict(zip(("Proximal Developed", "Core", "Proximal Developing", "Far-open"), CHARS))
TITLE = "WARDWISE POPULATION AND AREA"
FIRST = 5                                    # the first ward's row of the exported sheet
BLANK = 150                                  # rows of an empty list
EXTRA = 100                                  # empty rows below the wards given, for more
# the tables beside the wards (columns L-M): the criteria of the character, the town's census by decade
CRIT_TITLE = "CRITERIA OF CHARACTER OF WARD"
DENS_DEF = {CHARS[0]: 585, CHARS[1]: 310, CHARS[2]: 170}
CEN_TITLE = "CENSUS POPULATION OF THE WHOLE TOWN"
CEN_ROW = 11


def folder():
    """<the module's data folder>\\cities - beside projects\\ (the master folder's Water, as the projects)."""
    from . import server
    return os.path.join(os.path.dirname(server.PROJECTS), "cities")


def _slug(city):
    s = re.sub(r"[^\w\- ]", "", str(city or "")).strip()
    return re.sub(r"\s+", "_", s)[:60] or "town"


def _num(v):
    """A number of a cell ("37,040", 37040.0) or None; ValueError for text that is not one."""
    if v is None or str(v).strip() in ("", "-", "None"):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return float(str(v).replace(",", "").strip())


def _char(v):
    """The character of ward by its letters ("Proximal  developing", "FAR OPEN"): one of CHARS, "" or None (unknown)."""
    k = re.sub(r"[^a-z]", "", str(v or "").lower())
    if not k:
        return ""
    key = lambda c: re.sub(r"[^a-z]", "", c.lower())
    for o, c in OLD.items():                     # an old name (a list of before 9-Nov-2026): its new one
        if key(o) == k:
            return c
    return next((c for c in CHARS if key(c) == k or key(c.split(" (")[0]) == k), None)


def _clean(n):
    """A ward no. as text: 21.0 -> "21"."""
    if isinstance(n, float) and n.is_integer():
        n = int(n)
    return str(n if n is not None else "").strip()


# ------------------------------------------------------------------------------------------------------------ export
def export_xlsx(city, year, rows, dens=None, census=None):
    """The sheet of the user's table, all in English (user 9-Nov-2026): title, two header rows, a row for each ward
    (density = population / Eq. area; J the character by the density criteria - no column to choose it, the user
    removed it 9-Nov-2026) - the rows given and EXTRA empty ones below, else BLANK; beside it (L-M) the criteria of
    the character (the density above which, dens: {character: persons / ha}, default the example's 585 / 310 / 170)
    and the whole town's census population by decade (census: [[year, population]], default 1951-2011 empty).
    -> the xlsx's bytes."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    wb = Workbook()
    ws = wb.active
    ws.title = "Wards"
    yr = year or ""
    thin = Side(style="thin", color="000000")
    box = Border(left=thin, right=thin, top=thin, bottom=thin)
    mid = Alignment(horizontal="center", vertical="center", wrap_text=True)
    head = PatternFill("solid", fgColor="D9E1F2")
    yellow = PatternFill("solid", fgColor="FFF2CC")
    bold = Font(bold=True)

    def hcell(ref, text):
        x = ws[ref]
        x.value, x.font, x.alignment, x.border, x.fill = text, bold, mid, box, head
    ws["A1"] = TITLE
    ws["A1"].font, ws["A1"].alignment = Font(bold=True, size=14), Alignment(horizontal="center")
    ws.merge_cells("A1:J1")
    ws["A2"] = ("One row per ward of the whole town (fill in the yellow cells). The character of a ward: by its density "
                "and the criteria (columns L-M). Eq. area = residential x 1 + public x 0.25 + industrial / agricultural "
                "x 0.1 + roads / water x 0 (CPHEEO Manual on Water Supply 2024, Part A, 2.8.1.24).")
    ws["A2"].font, ws["A2"].alignment = Font(italic=True, size=9, color="555555"), Alignment(wrap_text=True)
    ws.merge_cells("A2:J2")
    ws.row_dimensions[2].height = 30
    heads = {"A": "Sl. No", "B": "Name of ULB", "C": "No of ward", "D": "name of ward", "E": f"population in Year {yr}",
             "G": "Eq.area (IN HECTARE)", "H": "Census Population 2011", "I": f"Population Density in Year {yr}",
             "J": "Character by the density criteria"}
    for c in "ABCDEFGHIJ":
        hcell(f"{c}3", heads.get(c))
        hcell(f"{c}4", None)
        if c not in "EF":
            ws.merge_cells(f"{c}3:{c}4")
    ws.merge_cells("E3:F3")
    ws["E4"], ws["F4"] = "Total", "house hold"
    ws.row_dimensions[3].height = 45
    for c, w in zip("ABCDEFGHIJKLM", (6, 20, 9, 22, 11, 11, 12, 12, 12, 21, 3, 38, 24)):
        ws.column_dimensions[c].width = w
    # the criteria of the character: the density (persons / ha) above which (example technical.xlsx 'T' X346)
    D = dict(DENS_DEF, **{OLD.get(k, k): v for k, v in (dens or {}).items()
                          if OLD.get(k, k) in DENS_DEF and v not in (None, "")})
    ws.merge_cells("L3:M3")
    hcell("L3", CRIT_TITLE)
    hcell("L4", "Character of Ward")
    hcell("M4", "Population density above (persons / ha)")
    ws.row_dimensions[4].height = 45
    for k, ch in enumerate(CHARS):
        a, b = ws.cell(5 + k, 12, ch), ws.cell(5 + k, 13, D.get(ch, "the rest"))
        a.border = b.border = box
        if ch in D:
            b.fill, b.number_format = yellow, "#,##0"
        else:
            b.alignment = Alignment(horizontal="center")
    # the whole town's census population by decade (for the projection: the page's census table)
    ws.merge_cells(f"L{CEN_ROW}:M{CEN_ROW}")
    hcell(f"L{CEN_ROW}", CEN_TITLE)
    hcell(f"L{CEN_ROW + 1}", "Year")
    hcell(f"M{CEN_ROW + 1}", "Population")
    cen = [list(x) for x in census or [] if x and str(x[0]).strip()] or [[y, None] for y in range(1951, 2012, 10)]
    for k in range(len(cen) + 4):
        y, p = cen[k] if k < len(cen) else (None, None)
        a, b = ws.cell(CEN_ROW + 2 + k, 12, y), ws.cell(CEN_ROW + 2 + k, 13, p)
        a.border = b.border = box
        a.fill = b.fill = yellow
        b.number_format = "#,##0"
    rows = list(rows or [])
    n = len(rows) + EXTRA if rows else BLANK
    for i in range(n):
        w = rows[i] if i < len(rows) else {}
        x = FIRST + i
        kx = (f'=IF(I{x}="","",IF(I{x}>$M$5,"{CHARS[0]}",IF(I{x}>$M$6,"{CHARS[1]}",IF(I{x}>$M$7,"{CHARS[2]}",'
              f'"{CHARS[3]}"))))')
        vals = [i + 1, w.get("ulb", city) or city or "", w.get("no", ""), w.get("name", ""), w.get("pop"), w.get("hh"),
                w.get("area"), w.get("census"), f'=IFERROR(ROUND(E{x}/G{x},2),"")', kx]
        for j, v in enumerate(vals):
            c = ws.cell(x, j + 1, v if v != "" else None)
            c.border = box
            if j in (1, 2, 3, 4, 5, 6, 7):
                c.fill = yellow
            if j in (4, 5, 7):
                c.number_format = "#,##0"
            elif j in (6, 8):
                c.number_format = "#,##0.00"
    ws.freeze_panes = f"A{FIRST}"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = "3:4"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _side_tables(wb):
    """The criteria of the character ({character: density above}) and the town's census ([[year, population]]) of
    the tables beside the wards, found by their titles."""
    dens, census = {}, []
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                t = str(c.value or "").strip().lower()
                if t == CRIT_TITLE.lower() and not dens:
                    for k in range(2, 12):
                        ch = _char(ws.cell(c.row + k, c.column).value)
                        if ch in DENS_DEF:
                            try:
                                v = _num(ws.cell(c.row + k, c.column + 1).value)
                            except ValueError:
                                v = None
                            if v is not None and v >= 0:
                                dens[ch] = v
                elif t == CEN_TITLE.lower() and not census:
                    for r in range(c.row + 2, c.row + 40):
                        try:
                            y, p = _num(ws.cell(r, c.column).value), _num(ws.cell(r, c.column + 1).value)
                        except ValueError:
                            continue
                        if y and p and 1800 < y < 2200:
                            census.append([int(y), round(p)])
    return dens, census


# ------------------------------------------------------------------------------------------------------------ import
def _role(top, sub):
    """The column's role by its header texts (the merged one above, the one below): key or None."""
    t, s = str(top or "").lower(), str(sub or "").lower()
    if t.strip() in (CRIT_TITLE.lower(), CEN_TITLE.lower()):        # the tables beside the wards
        return None
    b = f"{t} {s}"
    if "census" in b:
        return "census"
    if "density" in b:
        return "density"
    if "character" in b or "char" in b.split():
        return "char"
    if "house" in b or re.search(r"\bhh\b", b):
        return "hh"
    if "ulb" in b or "city" in b or "town" in b:
        return "ulb"
    if re.search(r"\bsl\b|s\.\s*no|serial", b):
        return "sl"
    if "area" in b:
        return "area"
    if "ward" in b and ("name" in b):
        return "name"
    if "ward" in b and re.search(r"\bno\b|number|num", b):
        return "no"
    if "total" in s or "population" in b:
        return "pop"
    return None


def _merged_value(ws, r, c):
    for m in ws.merged_cells.ranges:
        if m.min_row <= r <= m.max_row and m.min_col <= c <= m.max_col:
            return ws.cell(m.min_row, m.min_col).value
    return ws.cell(r, c).value


def import_xlsx(data, fname=""):
    """The wards of an xlsx in the format of export_xlsx (or the user's own table of those columns): the header found
    by its texts in the first 20 rows of any sheet; the year from the population's header ("population in Year 2025");
    the town from Name of ULB (the most common), else the file's name. -> {"city", "year", "rows": [{no, name, pop,
    hh, area, census, char}], "notes": [(hi, en)]}; ValueError when no ward is found."""
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(data), data_only=True)
    for ws in wb.worksheets:
        top = None
        for r in range(1, min(ws.max_row, 20) + 1):
            own = {_role(_merged_value(ws, r, c), None) for c in range(1, min(ws.max_column, 40) + 1)} - {None}
            if not ({"name", "pop"} <= own and len(own) >= 4):          # the header row by its own texts
                continue
            roles = {}                                                 # the columns, by the row below too
            for c in range(1, min(ws.max_column, 40) + 1):
                k = _role(_merged_value(ws, r, c), ws.cell(r + 1, c).value if r < ws.max_row else None)
                if k and k not in roles.values():
                    roles[c] = k
            top = (r, roles)
            break
        if top:
            break
    else:
        raise ValueError("xlsx में वार्ड की तालिका नहीं मिली (शीर्षक: name of ward, population ...)")
    r0, roles = top
    col = {k: c for c, k in roles.items()}
    ptext = f"{_merged_value(ws, r0, col['pop'])} {ws.cell(r0 + 1, col['pop']).value or ''}"
    m = re.search(r"\b(19|20)\d\d\b", ptext)
    year = int(m.group(0)) if m else None
    rows, notes, ulbs, seen = [], [], collections.Counter(), set()
    last_ulb = ""
    # the data below the header's merged cells (its second row: Total / house hold)
    end = max([m.max_row for m in ws.merged_cells.ranges if m.min_row == r0] + [r0])
    for r in range(end + 1, ws.max_row + 1):
        val = lambda k: ws.cell(r, col[k]).value if k in col else None
        name, no = str(val("name") or "").strip(), _clean(val("no"))
        if "ulb" in col:
            u = str(_merged_value(ws, r, col["ulb"]) or "").strip()
            last_ulb = u or last_ulb
        if not name and not no:
            continue
        if name.lower() in ("total", "house hold", "name of ward") or str(val("pop") or "").strip().lower() == "total":
            continue
        w = {"no": no, "name": name or f"Ward {no}"}
        bad = []
        for k in ("pop", "hh", "area", "census"):
            try:
                v = _num(val(k))
            except ValueError:
                v = None
                bad.append(k)
            w[k] = round(v, 2) if v is not None and k == "area" else (round(v) if v is not None else None)
        ch = _char(val("char"))
        if ch is None:
            notes.append((f"पंक्ति {r} ({w['name']}): चरित्र '{val('char')}' पहचाना नहीं - खाली माना (density से)",
                          f"row {r} ({w['name']}): character '{val('char')}' not known - taken as empty (by the density)"))
            ch = ""
        w["char"] = ch
        if bad:
            notes.append((f"पंक्ति {r} ({w['name']}): {', '.join(bad)} संख्या नहीं - खाली माना",
                          f"row {r} ({w['name']}): {', '.join(bad)} not a number - taken as empty"))
        key = no or name.lower()
        if key in seen:
            notes.append((f"Ward No. {no or name} दो बार - दूसरी पंक्ति {r} भी रखी", f"Ward No. {no or name} twice - "
                          f"the second (row {r}) kept too"))
        seen.add(key)
        if last_ulb:
            ulbs[last_ulb] += 1
        rows.append(w)
    if not rows:
        raise ValueError("xlsx की तालिका में कोई वार्ड नहीं")
    city = ulbs.most_common(1)[0][0] if ulbs else os.path.splitext(os.path.basename(fname or ""))[0] or "town"
    if not year:
        notes.append(("आबादी के शीर्षक में वर्ष नहीं मिला (जैसे 'population in Year 2025')",
                      "no year in the population's header (as 'population in Year 2025')"))
    if n := sum(1 for w in rows if w["pop"] is None):
        notes.append((f"{n} वार्डों की आबादी खाली", f"{n} ward(s) without population"))
    dens, census = _side_tables(wb)
    return {"city": city, "year": year, "rows": rows, "notes": notes, "dens": dens, "census": census}


# ------------------------------------------------------------------------------------------------------------ keep
def _path(city):
    return os.path.join(folder(), _slug(city) + ".json")


def save(d, fname=""):
    """The imported list of a town -> cities\\<town>.json (replacing its earlier one); returns what is kept."""
    os.makedirs(folder(), exist_ok=True)
    keep = {"city": d["city"], "year": d["year"], "rows": d["rows"], "dens": d.get("dens") or {},
            "census": d.get("census") or [], "file": os.path.basename(fname or ""),
            "imported": datetime.datetime.now().strftime("%d-%m-%Y %H:%M")}
    with open(_path(d["city"]) + ".part", "w", encoding="utf-8") as fh:
        json.dump(keep, fh, ensure_ascii=False, indent=1)
    os.replace(_path(d["city"]) + ".part", _path(d["city"]))
    return keep


def load(city):
    p = _path(city)
    if not os.path.isfile(p):
        raise ValueError(f"शहर '{city}' की वार्ड सूची नहीं मिली")
    with open(p, encoding="utf-8") as fh:
        d = json.load(fh)
    for w in d.get("rows") or []:                # a list kept before 9-Nov-2026: the characters' new names
        w["char"] = OLD.get(w.get("char"), w.get("char") or "")
    d["dens"] = {OLD.get(k, k): v for k, v in (d.get("dens") or {}).items()}
    return d


def cities():
    """The towns' lists kept: [{city, year, n, file, imported}]."""
    out = []
    if os.path.isdir(folder()):
        for f in sorted(os.listdir(folder())):
            if f.endswith(".json"):
                try:
                    with open(os.path.join(folder(), f), encoding="utf-8") as fh:
                        d = json.load(fh)
                    out.append({"city": d["city"], "year": d.get("year"), "n": len(d.get("rows") or []),
                                "file": d.get("file", ""), "imported": d.get("imported", "")})
                except (OSError, ValueError, KeyError):
                    continue
    return out


def export_b64(req):
    """The xlsx for the page: the town's kept list (req city), else the page's rows (req rows), else empty; also
    written to cities\\<town>_wards.xlsx. -> {path, file, b64}."""
    city, year, rows = str(req.get("city") or "").strip(), req.get("year"), None
    dens, census = req.get("dens") or {}, req.get("census") or []          # the page's, else the list's
    if city and os.path.isfile(_path(city)):
        d = load(city)
        rows, year = d["rows"], d.get("year") or year
        dens, census = d.get("dens") or dens, d.get("census") or census
    elif req.get("rows"):
        rows = [{k: r.get(k) for k in ("no", "name", "pop", "hh", "area", "census", "char")} for r in req["rows"]]
        for r in rows:
            for k in ("pop", "hh", "area", "census"):
                try:
                    r[k] = _num(r[k])
                except ValueError:
                    r[k] = None
    data = export_xlsx(city, year, rows, dens, census)
    os.makedirs(folder(), exist_ok=True)
    # one "wards" in the name (user 9-Nov-2026: a town named after its file 'town_wards' gave town_wards_wards)
    name = re.sub(r"(?i)[_ -]*wards?$", "", _slug(city or "town")) or "town"
    name = f"{name}_wards.xlsx"
    path = os.path.join(folder(), name)
    try:
        with open(path, "wb") as fh:
            fh.write(data)
    except OSError:                              # open in Excel: the download still goes
        path = ""
    return {"path": path, "file": name, "b64": base64.b64encode(data).decode("ascii")}
