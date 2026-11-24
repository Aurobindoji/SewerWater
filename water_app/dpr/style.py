"""The look of the water DPR workbook as the U.P. Jal Nigam estimates it follows (user decision 26-Oct-2026: as the
uploaded estimates): Times New Roman, plain bold headers with borders (no colour), long texts in a table wrapped, every
sheet on A4 fitted to the page width with its header rows repeated, centred, printed in black and white - the yellow
input cells stay yellow on the screen only. Sheets copied from an estimate (copied) keep their own fonts and borders;
they get the page setup only.

    apply(wb, copied=(), one_page=())   just before the workbook is saved; formulas and values are not touched;
                                        one_page: sheets printed on one page each (the cover, the title pages);
                                        own: sheets left as written (fonts and page setup: the salient features)

    fit(wb)                             last, when the sheets have their names and texts: every sheet, the copied
                                        ones too, gets its long texts fitted (fit_texts, 24-Nov-2026: texts were cut
                                        in the printed DPR)

fit_texts: a text wider than its column or merged cells is wrapped where it would be cut (in a table, merged, or
with something beside it), and its row made tall enough - Excel fits a row to a typed text itself when it opens the
file, not to a formula's text (its value is not known then) nor to merged cells, so those rows get their height here.
"""
import math
import re

from openpyxl.cell.cell import MergedCell
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import column_index_from_string, get_column_letter

FONT = "Times New Roman"
HEAD_RGB = "D9E1F2"                      # the header fill of Book.header
WIDE = 150                               # wider than this (Excel width units): landscape (A4 portrait ~ 70 %)
TABLE_COLS = 12                          # more columns than this: body 11 pt, else 12 pt


def _font(cache, f, size):
    key = (size, bool(f.b), bool(f.i), f.u, f.color.rgb if f.color is not None and f.color.type == "rgb" else None)
    if key not in cache:
        cache[key] = Font(name=FONT, size=size, bold=key[1], italic=key[2], underline=key[3],
                          color=key[4] if isinstance(key[4], str) else None)
    return cache[key]


PRINT_COLS = "print_cols"                # a sheet's attribute: its printed columns end here (its working cells beyond)


def _table_cols(ws):
    """A copied estimate's printed columns: to its table's last ruled column and its signature - the SOR numbers its
    look-ups use, beside the table, not printed (24-Nov-2026)."""
    last = 0
    for row in ws.iter_rows():
        for c in row:
            b = c.border
            if b is not None and any(x is not None and x.style for x in (b.left, b.right, b.top, b.bottom)):
                last = max(last, c.column)
            elif isinstance(c.value, str) and "ENGINEER" in c.value.upper():
                last = max(last, c.column)
    if not 0 < last < ws.max_column:
        return
    inside = beyond = 0
    for row in ws.iter_rows():
        for c in row:
            if c.value in (None, ""):
                continue
            if c.column <= last:
                inside += 1
            elif isinstance(c.value, str) and (c.value.startswith("=") or len(c.value) > 12):
                return                                   # a working of the sheet beside it (a thrust block): printed
            else:
                beyond += 1
    if beyond <= 0.15 * inside:                          # a few short numbers / codes: the SOR look-up keys
        setattr(ws, PRINT_COLS, last)


def _page(ws, head):
    last_col, last_row = getattr(ws, PRINT_COLS, None) or ws.max_column, ws.max_row
    width = sum((ws.column_dimensions[get_column_letter(c)].width or 8.43)
                for c in range(1, last_col + 1) if not ws.column_dimensions[get_column_letter(c)].hidden)
    ps = ws.page_setup
    ps.paperSize = ws.PAPERSIZE_A4
    ps.orientation = "landscape" if width > WIDE else "portrait"
    ps.fitToWidth, ps.fitToHeight = 1, 0
    ps.blackAndWhite = True
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_options.horizontalCentered = True
    m = ws.page_margins
    m.left = m.right = 0.7
    m.top = m.bottom = 0.75
    m.header = m.footer = 0.3
    ws.print_area = f"A1:{get_column_letter(last_col)}{last_row}"
    if len(ws.row_breaks.brk):                          # Excel drops the page breaks of a sheet fitted to the page:
        page = (11.69 if ps.orientation == "landscape" else 8.27) - m.left - m.right     # its width by a scale
        cols = [ws.column_dimensions[get_column_letter(c)] for c in range(1, last_col + 1)]
        pt = sum(((d.width or 8.43) * 7 + 5) * 0.75 for d in cols if not d.hidden)
        ws.sheet_properties.pageSetUpPr.fitToPage = False
        ps.scale = max(10, min(100, int(page * 72 * 0.88 / max(pt, 1.0) * 100)))   # (a margin for the fonts)
    if head and head <= 8:
        ws.print_title_rows = f"1:{head}"


_REF1 = re.compile(r"^(?:'([^']+)'!|([A-Za-z_][A-Za-z0-9_.]*)!)?\$?([A-Z]{1,3})\$?([0-9]+)$")
_FUNC = re.compile(r"^([A-Z][A-Z0-9_.]*)\((.*)\)$", re.S)
NUM = 8                                  # characters of a number (or a cell whose text is not known)


def wlen(t):
    """Length of a text in average characters: a capital (or M, W, @, %) is about a third wider."""
    return len(t) + 0.3 * sum(1 for ch in t if ch.isupper() or ch in "MW@%")


def _split(expr, sep):
    """expr split at `sep` outside quotes and brackets."""
    out, depth, quote, cur = [], 0, False, ""
    for ch in expr:
        if ch == '"':
            quote = not quote
        elif not quote and ch == "(":
            depth += 1
        elif not quote and ch == ")":
            depth -= 1
        if ch == sep and not quote and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return out


def _est(expr, wb, depth, here=None):
    """(characters, whether a text) of a formula's expression."""
    e = expr.strip()
    parts = _split(e, "&")
    if len(parts) > 1:
        ests = [_est(x, wb, depth, here) for x in parts]
        return sum(n for n, _ in ests), True
    if len(e) >= 2 and e[0] == '"' and e[-1] == '"':
        return wlen(e[1:-1].replace('""', '"')), True
    m = _REF1.match(e)
    if m:
        name = m.group(1) or m.group(2)
        if wb is not None and depth < 5 and (name is None or name in wb.sheetnames):
            ws = wb[name] if name else here
            if ws is not None:
                n = text_len(ws[f"{m.group(3)}{m.group(4)}"].value, wb, depth + 1, ws)
                if n is not None:
                    return n, True
        return NUM, False
    m = _FUNC.match(e)
    if m:
        name, args = m.group(1).replace("_XLFN.", ""), _split(m.group(2), ",")
        if name in ("IF", "IFS"):
            args = args[1:]
        ests = [_est(x, wb, depth, here) for x in args if x.strip()]
        if not ests:
            return 0, False
        if name in ("CONCATENATE", "CONCAT", "TEXTJOIN", "REPT"):
            return sum(n for n, _ in ests), True
        if name in ("TEXT", "FIXED", "DOLLAR"):
            return NUM + 2, True
        if name in ("UPPER", "LOWER", "PROPER", "TRIM", "IF", "IFS", "IFERROR", "CHOOSE", "INDEX", "VLOOKUP"):
            return max(n for n, _ in ests), any(t for _, t in ests)
        return NUM, False
    if e.startswith("(") and e.endswith(")") and len(_split(e[1:-1], ")")) == 1:
        return _est(e[1:-1], wb, depth, here)
    return NUM, False


def text_len(v, wb=None, depth=0, here=None):
    """The longest line of the text a cell shows (characters): a typed text's own; a formula's estimated from its
    parts (quoted texts, NUM characters for a number, the text of a cell it takes when the workbook is given); None:
    no text in it - a number."""
    if not isinstance(v, str) or not v:
        return None
    if not v.startswith("="):
        return max(wlen(x) for x in v.split("\n"))
    try:
        n, is_text = _est(v[1:], wb, depth, here)
    except RecursionError:
        return None
    return n if is_text else None


WIDE_FONTS = {"bookman": 0.78, "verdana": 0.78, "arial": 0.88, "calibri": 0.95, "cambria": 0.92}


def _chars(width, size, bold, font=None):
    """Characters of Times New Roman (or of `font`: Bookman Old Style, the copied estimates', is wider) of `size` pt
    in `width` Excel units."""
    k = next((v for f, v in WIDE_FONTS.items() if f in str(font or "").lower()), 1.0)
    return max(1.0, (width - 0.7) * 1.18 * 11.0 / size * (0.9 if bold else 1.0) * k)


def fit_texts(ws):
    """Wrap the texts the sheet would cut and make their rows tall enough (see the module's note)."""
    cw = {}

    def width(c):
        if c not in cw:
            d = ws.column_dimensions.get(get_column_letter(c))
            cw[c] = 0.0 if d is not None and d.hidden else (d.width if d is not None and d.width else 8.43)
        return cw[c]
    merged, inside = {}, set()
    for m in ws.merged_cells.ranges:
        merged[(m.min_row, m.min_col)] = m
        inside.update((r, c) for r in range(m.min_row, m.max_row + 1) for c in range(m.min_col, m.max_col + 1))
    need, force = {}, set()
    last = ws.max_column                                 # the page's last column: of the print area when set
    pa = re.search(r"!?\$?[A-Z]+\$?[0-9]+:\$?([A-Z]+)\$?[0-9]+$", str(ws.print_area or ""))
    if pa:
        last = column_index_from_string(pa.group(1))
    for row in ws.iter_rows():
        for c in row:
            n = text_len(c.value, ws.parent, 0, ws)
            if n is None or c.alignment.textRotation:
                continue
            m = merged.get((c.row, c.column))
            if m is None and (c.row, c.column) in inside:
                continue
            c0, c1 = (m.min_col, m.max_col) if m else (c.column, c.column)
            r0, r1 = (m.min_row, m.max_row) if m else (c.row, c.row)
            size, bold, fname = c.font.sz or 11, bool(c.font.b), c.font.name
            fit = _chars(sum(width(k) for k in range(c0, c1 + 1)), size, bold, fname)
            formula = c.value.startswith("=")
            a = c.alignment
            if not a.wrap_text:
                if n <= fit + 1:
                    continue
                has_box = c.border is not None and c.border.left is not None and bool(c.border.left.style)
                beside = ws.cell(c.row, c1 + 1).value not in (None, "") or (c.row, c1 + 1) in inside
                if not (m is not None or beside):
                    # nothing beside it: Excel lets it run on over the empty cells - but not past the page's last
                    # column (the print area), where it is cut: a note outside a table then over the cells to the
                    # last column, wrapped
                    free = c1
                    while free < last and ws.cell(c.row, free + 1).value in (None, "") \
                            and (c.row, free + 1) not in inside:
                        free += 1
                    if n <= _chars(sum(width(k) for k in range(c0, free + 1)), size, bold, fname) + 1:
                        continue
                    if free == last and c1 < last and r0 == r1 and not has_box:   # (a table's cell: wrapped in it)
                        ws.merge_cells(start_row=c.row, start_column=c0, end_row=c.row, end_column=last)
                        inside.update((c.row, k) for k in range(c0, last + 1))
                        c1 = last
                        m = True
                        fit = _chars(sum(width(k) for k in range(c0, c1 + 1)), size, bold, fname)
                c.alignment = Alignment(horizontal=a.horizontal, vertical=a.vertical or "center", wrap_text=True,
                                        indent=a.indent)
            parts = c.value.split("\n") if not formula else [None]
            lines = sum(max(1, math.ceil((wlen(x) if x is not None else n) / fit)) for x in parts)
            h = lines * size * 1.3 + 2 if lines > 1 else size * 1.3
            per = h / (r1 - r0 + 1)
            for r in range(r0, r1 + 1):
                need[r] = max(need.get(r, 0.0), per)
            if formula or m is not None:
                force.update(range(r0, r1 + 1))
    for r, h in need.items():
        if h > 20:                                       # a taller row: its cells in its middle, as the DPR's tables
            for x in ws[r]:
                if x.value not in (None, "") and not x.alignment.vertical and not isinstance(x, MergedCell):
                    a = x.alignment
                    x.alignment = Alignment(horizontal=a.horizontal, vertical="center", wrap_text=a.wrap_text,
                                            indent=a.indent, textRotation=a.textRotation)
        d = ws.row_dimensions[r]
        if d.height is not None and d.height + 0.5 >= h:
            continue
        if d.height is None and r not in force:
            continue                                     # a typed text alone: Excel fits the row itself
        d.height = round(h, 1)
    return need


def fit(wb):
    """fit_texts on every sheet - the last thing before the workbook is saved."""
    for ws in wb.worksheets:
        fit_texts(ws)


def apply(wb, copied=(), one_page=(), own=()):
    cache = {}
    for ws in wb.worksheets:
        if ws.title in own:                              # laid out and set up by their writer (dpr_front)
            continue
        if ws.title in copied:
            _table_cols(ws)
            _page(ws, None)
            if ws.title in one_page:
                ws.page_setup.fitToHeight = 1
            continue
        size = 11 if ws.max_column > TABLE_COLS else 12
        starts = {(r.min_row, r.min_col) for r in ws.merged_cells.ranges}
        widths = {}
        heads, wrapped = set(), set()
        for row in ws.iter_rows():
            for c in row:
                if c.value is None and not c.has_style:
                    continue
                f = c.font
                title = bool(f.b) and (f.sz or 11) >= 12
                c.font = _font(cache, f, 14 if title else size)
                if c.fill is not None and c.fill.fill_type == "solid" and str(c.fill.fgColor.rgb)[-6:] == HEAD_RGB:
                    c.fill = PatternFill(fill_type=None)
                    heads.add(c.row)
                v = c.value
                if (isinstance(v, str) and not v.startswith("=") and c.border is not None and c.border.left is not None
                        and c.border.left.style and (c.row, c.column) not in starts):
                    w = widths.setdefault(c.column, ws.column_dimensions[get_column_letter(c.column)].width or 8.43)
                    if len(v) > w * 1.1 and ws.cell(c.row, c.column + 1).value not in (None, ""):   # else it runs on
                        a = c.alignment
                        c.alignment = Alignment(horizontal=a.horizontal, vertical=a.vertical or "center", wrap_text=True)
                        wrapped.add(c.row)
        for r in wrapped:                                # Excel sets their height to the wrapped text itself
            if r in ws.row_dimensions:
                ws.row_dimensions[r].height = None
        # the header rows printed on every page only when the sheet has one table (one block of them): a second
        # table's pages under the first one's header was wrong (24-Nov-2026)
        head = min(heads) if heads and max(heads) - min(heads) + 1 == len(heads) else None
        _page(ws, head)
