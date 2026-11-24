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
        ws.print_cols = 10                              # the rate's working (L:M) not printed (24-Nov-2026)
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
        # the main item and its specifications (i)-(xix), as the approved DPR's OHT estimate (p212-214, 24-Nov-2026):
        # texts under the item, its rate per litre covering them; the C.I. pipes measured (no rate of their own)
        txt = ('="Supply of all the materials, labour, T&P etc. complete and construction of a R.C.C. Over Head Tank of '
               'capacity of "&M5&" KL and staging of "&M6&" m above ground level with following main specifications '
               'and with main components."')
        B.cell(ws, 7, 1, 1)
        B.cell(ws, 7, 2, txt).alignment = B.wrap
        B.cell(ws, 7, 3, 1)
        B.cell(ws, 7, 7, "=M5*1000", fmt="#,##0")
        B.cell(ws, 7, 8, "litre")
        B.cell(ws, 7, 9, "=M10", fmt="#,##0.00")
        B.cell(ws, 7, 10, "=G7*I7", fmt="#,##0")
        x = 8
        for no, spec in _oht_specs(B, z):
            B.cell(ws, x, 1, no).alignment = B.center
            B.cell(ws, x, 2, spec).alignment = B.wrap
            for c in range(3, 11):
                B.cell(ws, x, c, None)
            x += 1
        for no, size, more in _oht_pipes(B, z):           # (a)-(d): inlet, outlet, overflow, washout
            B.cell(ws, x, 1, no).alignment = B.center
            B.cell(ws, x, 2, size)
            B.cell(ws, x, 3, 1)
            B.cell(ws, x, 4, f"=ROUND($M$6+{more},0)", fmt="0")
            B.cell(ws, x, 7, f"=C{x}*D{x}", fmt="0")
            B.cell(ws, x, 8, "m")
            for c in (5, 6, 9, 10):
                B.cell(ws, x, c, None)
            x += 1
        for no, spec in _oht_specs_after():
            B.cell(ws, x, 1, no).alignment = B.center
            B.cell(ws, x, 2, spec).alignment = B.wrap
            for c in range(3, 11):
                B.cell(ws, x, c, None)
            x += 1
        first = x
        for i, (lab, v) in enumerate((("Provision for theme painting on the OHT wall", O["theme_painting"]),
                                      ("Provision for soil testing", O["soil_testing"])), 2):
            B.cell(ws, x, 1, i)
            B.cell(ws, x, 2, lab)
            B.cell(ws, x, 3, 1)
            B.cell(ws, x, 7, 1)
            B.cell(ws, x, 8, "job")
            B.cell(ws, x, 9, v, fmt="#,##0", inp=True)
            B.cell(ws, x, 10, f"=G{x}*I{x}", fmt="#,##0")
            for c in (4, 5, 6):
                B.cell(ws, x, c, None)
            x += 1
        for c in range(1, 11):                          # the column numbers under the header, as the DPR (p212)
            B.cell(ws, 6, c, c, bold=True).alignment = B.center
        for c in (4, 5, 6):                             # the whole grid (L, B, H blank)
            B.cell(ws, 7, c, None)
        B.cell(ws, x, 9, "Total", bold=True)
        B.cell(ws, x, 10, f"=J7+SUM(J{first}:J{x - 1})", fmt="#,##0", bold=True)
        B.cell(ws, x + 1, 9, "Say (lakh)", bold=True)
        B.cell(ws, x + 1, 10, f"=ROUND(J{x}/100000,2)", fmt="#,##0.00", bold=True)
        say = f"J{x + 1}"
        ws.cell(x + 3, 2, "Rate: U.P. Jal Nigam standard cost of OHT of 25 m staging, FY 2022-23, escalated (sheet OHT UGR "
                          "rates); +/- 15 % for every 25 m more / less staging (Elmwood 'OHT Z-7').").font = B.italic
        B.sign(ws, x + 6, 9)
        made.append((name, z, k, say))
    ws = B.sheet("Est. OHT", "ABSTRACT OF COST OF R.C.C. OVERHEAD TANKS", 5)
    B.header(ws, 5, ["S. No.", "Particulars", "Qty.", "Capacity of OHT and staging", "Amount (Rs. lakh)"],
             [6, 50, 8, 26, 16])
    x = 6
    if made:                                            # as the DPR (p211): the item, then a line for each zone
        B.cell(ws, x, 1, 1)
        B.cell(ws, x, 2, "Construction of R.C.C. Over Head Tank including all materials, labour, T & P etc. complete "
                         "(as per estimate enclosed).").alignment = B.wrap
        for c in (3, 4, 5):
            B.cell(ws, x, c, None)
        x += 1
    for i, (name, z, k, say) in enumerate(made, 1):
        B.cell(ws, x, 1, f"1.{i:02d}")
        B.cell(ws, x, 2, f"For operation zone {z['name']}")
        B.cell(ws, x, 3, "1 No.")
        B.cell(ws, x, 4, f'={q(name)}!M5&" KL / "&{q(name)}!M6&" m"')
        B.cell(ws, x, 5, f"={q(name)}!{say}", fmt="#,##0.00")
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
    ws.print_cols = 6                                   # the soil testing input (H:I) not printed
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


def _oht_specs(B, z):
    """(i)-(xii): the main specifications of a new OHT, as the approved DPR's (p212-213); the bearing capacity the
    Intze design's (net, t/m2)."""
    from .. import intze
    sbc = intze.DEFAULTS["sbc_kn_m2"] / 10.0
    return [
        ("(i)", "All the components of O.H.T. will be casted in M30 concrete with cement, coarse sand and approved stone "
                "grit."),
        ("(ii)", "Minimum depth of foundation below original ground level will be 2.5 m."),
        ("(iii)", "Seismic effects should be taken into consideration."),
        ("(iv)", f"The assumed bearing capacity of soil has been taken as {sbc:g} M.T./sqm."),
        ("(v)", "1 m wide R.C.C. stair case from ground level to balcony."),
        ("(vi)", "M.S. ladder, made of 50 x 6 mm angle section and 20 mm plain M.S. bars with hand rails of 20 mm medium "
                 "quality G.I. pipes on both sides in 2 rows from balcony to top dome resting on an R.C.C. platform (75 x "
                 "75 cm and 10 cm thick) projecting from top ring beam and one ladder inside the tank body (from manhole "
                 "in top dome to bottom dome)."),
        ("(vii)", "1 m wide R.C.C. balcony around the tank at the junction point of vertical wall and conical wall."),
        ("(viii)", "Proper railing of 20 mm dia medium quality G.I. pipe (in 3 rows) on both sides of stair case, landing "
                   "from landing with top ring beam upto manhole on the top dome and at the periphery. The G.I. pipes "
                   "will be supported on R.C.C. posts of 100 mm dia or on the posts made of 50x50x6 mm M.S. angle "
                   "section, spaced at intervals not more than 1.5 m."),
        ("(ix)", "Proper ventilator at top dome in circular shape of 1.2 m dia along with an R.C.C. cover of min. 1.5 m "
                 "dia and 7.5 cm thickness supported on small R.C.C. pillar of min. 50 cm dia. The space between top "
                 "dome and R.C.C. cover should be covered with S.S. mosquito net of standard quality along with expanded "
                 "metal jali."),
        ("(x)", "Water level indicator fabricated with good quality min. 45x45x6 mm, 6 mm flat 3 mm thick M.S. sheet. The "
                "indicator board scale made of 3 mm thick M.S. plate should have a clear width of min 25 cm, painted "
                "with good paint. It should also consist of 3 mm brass wire rope, min. 4 smooth pulleys about 8 cm dia "
                "with guide, 15 cm dia copper ball float which shall be completely water tight, suitable pointer of "
                "brass etc."),
        ("(xi)", "Lightning conductor as per I.S.S. 2309 or its latest amendments or latest electricity rules. It should "
                 "consist of a proper elevation rod with 5 or more fork points, proper down conductors of prescribed "
                 "metal of proper size prescribed by I.S.S. 2309-1969 and I.S.S. 3013-1966."),
        ("(xii)", "C.I. manhole of min. 60x60 cm size made of M.S. channel section with adequate cover made of M.S. sheet "
                  "of min. 3 mm thickness, hinged with manhole, should be fixed in top of dome at proper place."),
        ("(xiii)", "Supply, fixing, jointing of following sizes of C.I. D/F pipes with C.I. D/F specials, as vertical "
                   "pipes for inlet, outlet, overflow and washout as per latest / relevant I.S. specifications with all "
                   "jointing materials for proper completion including other appurtenant works, and excavation in all "
                   "type of soil.")]


def _oht_pipes(B, z):
    """(a)-(d) of (xiii): the inlet (the largest main filling the OHT), the outlet (the design's), the overflow (as
    the outlet) and a 100 mm washout - each up the staging, the inlet and overflow 12 m more, the others 6 m (the DPR's
    38 / 32 m at 26 m staging)."""
    R = B.info.get("rising") or {}
    mm = lambda s: int("".join(ch for ch in str(s or "") if ch.isdigit()) or 0)
    ins = [t.get("size") for t in R.get("tws") or [] if t.get("oz") == z["name"] and t.get("size")]
    inlet = max((mm(x) for x in ins), default=0) or 200
    outlet = mm(z.get("outlet")) or 200
    return [("(a)", f"Inlet {inlet} mm", 12), ("(b)", f"Outlet {outlet} mm", 6), ("(c)", f"Overflow {outlet} mm", 12),
            ("(d)", "Washout 100 mm", 6)]


def _oht_specs_after():
    """(xiv)-(xix): the rest of the approved DPR's specifications (p214)."""
    return [
        ("(xiv)", "Construction of bed blocks in 1:2:4 P.C.C. with cement, coarse sand and approved stone grit under "
                  "each duck foot bend to support the vertical pipes. These bed blocks should be supported on the raft, "
                  "not the soil."),
        ("(xv)", "Construction of surface box type sluice valve chamber for above sluice valve (1 no.) as per "
                 "departmental type design & drawing including supply and fixing of 150 mm x 150 mm size C.I. surface "
                 "box including locking arrangement."),
        ("(xvi)", "Construction of 1 No. washout chamber as per departmental type design & drawing."),
        ("(xvii)", "Apply putty and theme based painting of all concrete surface and steel pipe works with three coats "
                   "of approved cement paint and anticorrosive paints."),
        ("(xviii)", "Provision for gate with locking arrangement on first landing of staircase."),
        ("(xix)", "Supply of the 160 mm dia P.V.C. pipe as per latest relevant I.S.S. including all taxes etc. F.O.R. "
                  "destination for disposal of overflow from overflow chamber to suitable point outside the water works "
                  "compound including excavation of trench, laying of pipe etc. complete.")]
