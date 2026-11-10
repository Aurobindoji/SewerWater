"""The look of the sewer DPR workbook as the U.P. Jal Nigam estimates it follows (user decision 26-Oct-2026: as the
uploaded estimates): Times New Roman, plain bold headers with borders (no colour), long texts in a table wrapped, every
sheet on A4 fitted to the page width with its header rows repeated, centred, printed in black and white - the yellow
input cells stay yellow on the screen only. Sheets copied from an estimate (copied) keep their own fonts and borders;
they get the page setup only.

    apply(wb, copied=())     just before the workbook is saved; formulas and values are not touched
"""
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

FONT = "Times New Roman"
HEAD_RGB = "D9E1F2"                      # the header fill of header() in dpr.write_dpr
WIDE = 150                               # wider than this (Excel width units): landscape (A4 portrait ~ 70 %)
TABLE_COLS = 12                          # more columns than this: body 11 pt, else 12 pt


def _font(cache, f, size):
    key = (size, bool(f.b), bool(f.i), f.u, f.color.rgb if f.color is not None and f.color.type == "rgb" else None)
    if key not in cache:
        cache[key] = Font(name=FONT, size=size, bold=key[1], italic=key[2], underline=key[3],
                          color=key[4] if isinstance(key[4], str) else None)
    return cache[key]


def _page(ws, head):
    last_col, last_row = ws.max_column, ws.max_row
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
    if head and head <= 8:
        ws.print_title_rows = f"1:{head}"


def apply(wb, copied=()):
    cache = {}
    for ws in wb.worksheets:
        if ws.title in copied:
            _page(ws, None)
            continue
        size = 11 if ws.max_column > TABLE_COLS else 12
        starts = {(r.min_row, r.min_col) for r in ws.merged_cells.ranges}
        widths = {}
        head, wrapped = None, set()
        for row in ws.iter_rows():
            for c in row:
                if c.value is None and not c.has_style:
                    continue
                f = c.font
                title = bool(f.b) and (f.sz or 11) >= 12
                c.font = _font(cache, f, 14 if title else size)
                if c.fill is not None and c.fill.fill_type == "solid" and str(c.fill.fgColor.rgb)[-6:] == HEAD_RGB:
                    c.fill = PatternFill(fill_type=None)
                    head = c.row if head is None else min(head, c.row)
                v = c.value
                if (isinstance(v, str) and not v.startswith("=") and c.border is not None and c.border.left is not None
                        and c.border.left.style and (c.row, c.column) not in starts):
                    w = widths.setdefault(c.column, ws.column_dimensions[get_column_letter(c.column)].width or 8.43)
                    if len(v) > w * 1.1:
                        a = c.alignment
                        c.alignment = Alignment(horizontal=a.horizontal, vertical=a.vertical or "top", wrap_text=True)
                        wrapped.add(c.row)
        for r in wrapped:                                # Excel sets their height to the wrapped text itself
            if r in ws.row_dimensions:
                ws.row_dimensions[r].height = None
        _page(ws, head)
