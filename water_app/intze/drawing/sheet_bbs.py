"""Intze drawings: the bar bending schedule sheets and the summary."""
from ezdxf.enums import TextEntityAlignment as TA
from water_app.intze import design as intze
from .base import B, Sheet


# ------------------------------------------------------------------------------------------------- bar schedule
def _sheets_bbs(dw, res, info, start):
    rows = res["bbs"]
    conc, steel = intze.quantities(res)
    per = 76                    # rows of 7 mm from y 563 down to ~24: clear of the note at the frame's foot
    chunks = [rows[i:i + per] for i in range(0, len(rows), per)] or [[]]
    sheets = []
    cols = [("S.No", 12), ("Member", 40), ("Mark", 14), ("Description", 126), ("Dia", 12), ("Nos", 16),
            ("Length m", 20), ("Total m", 22), ("Weight kg", 24), ("Shape", 34)]
    k = 0
    for ci, chunk in enumerate(chunks):
        sh = Sheet(dw, start + ci, "BAR BENDING SCHEDULE" + (f" ({ci + 1})" if len(chunks) > 1 else ""), start + ci + 1)
        x0, y = 20.0, 572.0
        sh.heading(sh.title, (x0 + 160, y), 3.4)
        y -= 9
        rh = 7.0
        tw = sum(w for _, w in cols)
        sh.rect(x0, y - rh * (len(chunk) + 1), x0 + tw, y, "THIN")
        xx = x0
        for name, w in cols:
            sh.text(name, (xx + w / 2, y - rh / 2), 2.2, TA.MIDDLE_CENTER, style=B)
            xx += w
            sh.line((xx, y), (xx, y - rh * (len(chunk) + 1)), "THIN")
        for r in chunk:
            k += 1
            y -= rh
            sh.line((x0, y), (x0 + tw, y), "THIN")
            vals = [k, r["member"], r["mark"], r["desc"][:78], r["dia"], r["no"], f"{r['length']:.2f}", f"{r['total_m']:.1f}",
                    f"{r['kg']:.1f}", r["shape"]]
            xx = x0
            for (name, w), val in zip(cols, vals):
                al = TA.MIDDLE_LEFT if name in ("Member", "Description", "Shape") else TA.MIDDLE_RIGHT
                sh.text(val, (xx + (1.5 if al == TA.MIDDLE_LEFT else w - 1.5), y - rh / 2), 1.9, al)
                xx += w
        if ci == len(chunks) - 1:
            _summary(sh, res, conc, steel, x0 + tw + 14, 560)
        sh.frame(info)
        sheets.append(sh)
    return sheets


def _summary(sh, res, conc, steel, x, y):
    by_dia = {}
    for r in res["bbs"]:
        by_dia[r["dia"]] = by_dia.get(r["dia"], 0.0) + r["kg"]
    sh.heading("STEEL BY DIA (kg)", (x + 45, y), 3.0)
    yy = y - 8
    for d in sorted(by_dia):
        sh.text(f"{d} mm", (x, yy), 2.3)
        sh.text(f"{by_dia[d]:,.0f}", (x + 90, yy), 2.3, TA.MIDDLE_RIGHT)
        yy -= 5
    sh.text("Total", (x, yy), 2.4, style=B)
    sh.text(f"{sum(by_dia.values()):,.0f}", (x + 90, yy), 2.4, TA.MIDDLE_RIGHT, style=B)
    yy -= 14
    sh.heading("QUANTITIES BY MEMBER", (x + 45, yy), 3.0)
    yy -= 8
    sh.text("Member", (x, yy), 2.2, style=B)
    sh.text("Conc. m3", (x + 65, yy), 2.2, TA.MIDDLE_RIGHT, style=B)
    sh.text("Steel kg", (x + 90, yy), 2.2, TA.MIDDLE_RIGHT, style=B)
    yy -= 5
    for n in dict.fromkeys(list(conc) + list(steel)):
        sh.text(n, (x, yy), 2.1)
        sh.text(f"{conc.get(n, 0):.1f}" if n in conc else "-", (x + 65, yy), 2.1, TA.MIDDLE_RIGHT)
        sh.text(f"{steel.get(n, 0):,.0f}" if n in steel else "-", (x + 90, yy), 2.1, TA.MIDDLE_RIGHT)
        yy -= 4.6
    sh.text("Total", (x, yy), 2.3, style=B)
    sh.text(f"{sum(conc.values()):.1f}", (x + 65, yy), 2.3, TA.MIDDLE_RIGHT, style=B)
    sh.text(f"{sum(steel.values()):,.0f}", (x + 90, yy), 2.3, TA.MIDDLE_RIGHT, style=B)
    yy -= 6
    sh.text(f"Steel {sum(steel.values()) / max(sum(conc.values()), 1):.0f} kg / m3 of concrete", (x, yy), 2.1)
    yy -= 12
    if res["warnings"]:
        sh.heading("CHECKS TO LOOK AT", (x + 45, yy), 3.0)
        rows = []
        for wtxt in res["warnings"]:
            words, line = wtxt.split(), ""
            for wd in words:
                if len(line) + len(wd) > 58:
                    rows.append(line)
                    line = ""
                line = (line + " " + wd).strip()
            rows.append(line)
            rows.append("")
        sh.lines(rows, x, yy - 8, 2.0, 3.6)
