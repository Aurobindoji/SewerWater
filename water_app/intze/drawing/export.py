"""Intze drawings: the sheets made and exported - DXF, PDF, the design workbook."""
import os
import ezdxf
from water_app.intze import design as intze
from .base import LAYERS, SH, SW, WARN, _info
from .sheet_bbs import _sheets_bbs
from .sheet_container import _sheet_container
from .sheet_ga import _sheet_staging
from .sheet_stair import _sheet_stair


# --------------------------------------------------------------------------------------------------------- export
def _new_doc():
    doc = ezdxf.new("R2010", setup=True, units=4)
    for name, (col, lw, lt) in LAYERS.items():
        if name not in doc.layers:
            doc.layers.add(name, color=col, linetype=lt, lineweight=lw)
    doc.header["$LTSCALE"] = 1.0
    doc.header["$PSLTSCALE"] = 0
    return doc


class _DW:
    def __init__(self):
        self.doc = _new_doc()
        self.msp = self.doc.modelspace()


def make_sheets(res, meta=None):
    dw = _DW()
    info = _info(res, meta)
    sheets = [_sheet_staging(dw, res, info), _sheet_container(dw, res, info)]
    if res["members"].get("stair"):
        sheets.append(_sheet_stair(dw, res, info, len(sheets)))
    sheets += _sheets_bbs(dw, res, info, len(sheets))
    for e in dw.msp.query("TEXT"):           # the frames were drawn before the count was known
        t = e.dxf.text
        if t.startswith("Sheet ") and " of " in t:
            e.dxf.text = t.split(" of ")[0] + f" of {len(sheets)}"
    return dw, sheets


def export(res, out_dir, stem, meta=None, pdf=True, xlsx=True):
    """Write <stem>.dxf, <stem>.pdf, <stem>_calc.pdf (the design calculation) and <stem>_design.xlsx into out_dir;
    returns their paths."""
    os.makedirs(out_dir, exist_ok=True)
    dw, sheets = make_sheets(res, meta)
    paths = {}
    p = os.path.join(out_dir, stem + ".dxf")
    dw.doc.saveas(p)
    paths["dxf"] = p
    if pdf:
        paths["pdf"] = _pdf(dw, sheets, os.path.join(out_dir, stem + ".pdf"))
        from water_app.intze import calc as intze_calc  # the design calculation as a report (user request 10-Nov-2026)
        paths["calc"] = intze_calc.export_pdf(res, os.path.join(out_dir, stem + "_calc.pdf"), meta)
    if xlsx:
        paths["xlsx"] = export_xlsx(res, os.path.join(out_dir, stem + "_design.xlsx"), meta)
    return paths


def _pdf(dw, sheets, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.config import BackgroundPolicy, ColorPolicy, Configuration, LineweightPolicy
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    cfg = Configuration(background_policy=BackgroundPolicy.WHITE, color_policy=ColorPolicy.COLOR,
                        lineweight_policy=LineweightPolicy.ABSOLUTE, lineweight_scaling=0.6)
    with PdfPages(path) as pdf:
        for sh in sheets:
            fig = plt.figure(figsize=(SW / 25.4, SH / 25.4))
            ax = fig.add_axes([0, 0, 1, 1])
            ax.set_axis_off()
            ctx = RenderContext(dw.doc)
            be = MatplotlibBackend(ax, adjust_figure=False)
            hs = sh.handles
            Frontend(ctx, be, config=cfg).draw_layout(dw.msp, finalize=False, filter_func=lambda e: e.dxf.handle in hs)
            ax.set_xlim(sh.ox, sh.ox + SW)
            ax.set_ylim(sh.oy, sh.oy + SH)
            ax.set_aspect("equal")
            pdf.savefig(fig)
            plt.close(fig)
    return path


def export_xlsx(res, path, meta=None):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = "Design"
    bold = Font(bold=True)
    yellow = PatternFill("solid", fgColor="FFFF99")
    info = _info(res, meta)
    ws.append([f"Design of the R.C.C. Intze tank {info['name']}: {res['capacity_kl']:g} KL on {res['staging_m']:g} m staging"])
    ws["A1"].font = Font(bold=True, size=13)
    ws.append([WARN])
    ws["A2"].font = Font(bold=True, color="C00000")
    ws.append([])
    ws.append(["Part", "Item", "Value", "Unit", "Reference / formula"])
    for c in ws[4]:
        c.font = bold
    last = None
    for sec, item, val, unit, ref in res["calc"]:
        ws.append([sec if sec != last else "", item, val, unit, ref])
        last = sec
        if sec == "1 Data" and item.startswith(("Concrete", "Seismic", "Net bearing", "Basic wind", "Steel stress")):
            ws.cell(ws.max_row, 3).fill = yellow
    if res["warnings"]:
        ws.append([])
        for wtxt in res["warnings"]:
            ws.append(["Check", wtxt])
    for col, w in zip("ABCDE", (16, 58, 34, 14, 90)):
        ws.column_dimensions[col].width = w
    for row in ws.iter_rows(min_row=5):
        row[4].alignment = Alignment(wrap_text=True, vertical="top")
        row[2].alignment = Alignment(wrap_text=True, vertical="top", horizontal="left")
    ws2 = wb.create_sheet("BBS")
    ws2.append(["S.No", "Member", "Mark", "Description", "Dia mm", "Nos", "Length m", "Total m", "kg/m", "Weight kg", "Shape"])
    for c in ws2[1]:
        c.font = bold
    for i, r in enumerate(res["bbs"], 1):
        n = i + 1
        ws2.append([i, r["member"], r["mark"], r["desc"], r["dia"], r["no"], r["length"], f"=F{n}*G{n}",
                    f"=E{n}^2/162", f"=H{n}*I{n}", r["shape"]])
    n = len(res["bbs"]) + 1
    ws2.append(["", "Total", "", "", "", "", "", f"=SUM(H2:H{n})", "", f"=SUM(J2:J{n})"])
    for c in ws2[ws2.max_row]:
        c.font = bold
    for col, w in zip("ABCDEFGHIJK", (6, 22, 8, 66, 8, 8, 10, 10, 8, 12, 22)):
        ws2.column_dimensions[col].width = w
    ws3 = wb.create_sheet("Quantities")
    conc, steel = intze.quantities(res)
    ws3.append(["Member", "Concrete m3", "Steel kg (BBS)"])
    for c in ws3[1]:
        c.font = bold
    for k in dict.fromkeys(list(conc) + list(steel)):
        ws3.append([k, round(conc.get(k, 0.0), 2), round(steel.get(k, 0.0), 1)])
    m = ws3.max_row
    ws3.append(["Total", f"=SUM(B2:B{m})", f"=SUM(C2:C{m})"])
    for c in ws3[ws3.max_row]:
        c.font = bold
    ws3.column_dimensions["A"].width = 24
    ws3.column_dimensions["B"].width = 14
    ws3.column_dimensions["C"].width = 16
    wb.save(path)
    return path
