"""The OHT and CWR estimates of the water DPR (restructure stage 3, 15-Nov-2026: out of dpr.py)."""
from .base import q


def ohts(B):
    """New OHTs (Elmwood 'OHT Z-7'): the U.P. Jal Nigam standard cost per litre at 25 m staging (sheet OHT UGR rates),
    +/- 15 % for every 25 m more / less, and their abstract."""
    O = B.S["oht"]
    made = []
    for k, t in enumerate(B.T3, 1):
        z = t["zone"]
        if not z["new_oht"]:                            # an estimate for each new OHT (also beside a short existing one)
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
    # the Riverside water DPR (sheets Rep. OHT (k), civil.oht_repair)
    from . import civil
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
            B.cell(ws, x, 5, f"={civil.oht_repair(B, z, i)}", fmt="#,##0.00")
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
