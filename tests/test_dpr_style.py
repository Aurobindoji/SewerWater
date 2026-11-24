"""The water DPR's texts fitted to their cells (dpr/style.fit_texts, 24-Nov-2026: texts were cut in the printed DPR)."""
from openpyxl import Workbook
from openpyxl.styles import Border, Font, Side

from water_app.dpr import style


def test_texts_fitted_to_their_cells():
    wb = Workbook()
    ws = wb.active
    ws.title = "S"
    for c, w in zip("ABCDE", (6, 30, 12, 12, 12)):
        ws.column_dimensions[c].width = w
    box = Border(left=Side(style="thin"), right=Side(style="thin"))
    # a formula's text in a header cell: Excel does not fit its row when it opens the file - the height is set here
    ws["C5"] = '="Initial Stage Year "&Project!$C$5'
    ws["C5"].font = Font(name="Times New Roman", size=12, bold=True)
    ws["C5"].border = box
    ws["D5"] = 1
    # a long typed text with a value beside it: wrapped (Excel fits that row itself)
    ws["B6"] = "Total demand for Pumping Main from WTP / TW to OHT (11 %) of the zone"
    ws["B6"].font = Font(name="Times New Roman", size=12)
    ws["B6"].border = box
    ws["C6"] = 5
    # a short heading with nothing beside it: runs on over the empty cells, not wrapped
    ws["B8"] = "Operation zone Prop-OHT-1 (whole)"
    ws["B8"].border = box
    # a long note under the table, past the page's last column: over the cells to it, wrapped
    ws["A10"] = "Note: " + "the pipes of the design, each in the operation zone of its first junction; " * 3
    ws.print_area = "A1:E10"
    style.fit_texts(ws)
    assert ws["C5"].alignment.wrap_text and ws.row_dimensions[5].height >= 30
    assert ws["B6"].alignment.wrap_text and ws.row_dimensions[6].height is None
    assert not ws["B8"].alignment.wrap_text
    assert "A10:E10" in {str(m) for m in ws.merged_cells.ranges} and ws["A10"].alignment.wrap_text
    assert ws.row_dimensions[10].height > 30


def test_text_length_of_formulas():
    wb = Workbook()
    ws = wb.active
    ws.title = "ABS"
    ws["B12"] = "Site development works (boundary wall, gate, earth filling)"
    assert style.text_len("=ABS!B12", wb) == style.text_len(ws["B12"].value)
    assert style.text_len("=SUM(A1:A9)&\" Nos\"") < 15            # a number and its unit
    assert style.text_len('=IF(A1>0,"a long text here","x")') == style.wlen("a long text here")
    assert style.text_len("=A1+B2") is None                        # a number
