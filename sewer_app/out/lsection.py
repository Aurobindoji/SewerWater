"""Longitudinal sections (L-sections) of the designed sewer, as DXF.

User decision (12-Oct-2026): no department sample - a general form, option (a): for every outfall the MAIN TRUNK =
the longest sewer path from a head of sewer down to that outfall. The new manholes of the 30 m spacing are on it.

Drawing units = millimetres on paper, to be plotted at 1:1: horizontal 1:1000 (1 m = 1 mm), vertical 1:100
(1 m = 10 mm) by default. A trunk longer than max_sheet_m is drawn on several sheets (each starts at the last
manhole of the one before), stacked one below the other. Each sheet:
    profile  ground line, invert line, crown line (invert + diameter), manhole shafts, datum line
    table    MANHOLE NO. | CHAINAGE (m) | GROUND LEVEL (m) | INVERT LEVEL (m) | DEPTH TO INVERT (m) |
             PIPE DIA (mm) | SLOPE (1 in) | LENGTH (m) - manhole values at the manhole, pipe values mid-pipe,
             all written upright (rotated 90 deg) so that close manholes do not overlap
    title    outfall, sheet, chainage range, scales, data grade
Layers LS_GROUND, LS_INVERT, LS_CROWN, LS_MH, LS_DATUM, LS_TABLE, LS_TEXT, LS_DEEP (depth deeper than the CPHEEO
limit), LS_TITLE.
"""
import math

LAYERS = {"LS_GROUND": 3, "LS_INVERT": 5, "LS_CROWN": 4, "LS_MH": 7, "LS_DATUM": 8, "LS_TABLE": 8,
          "LS_TEXT": 7, "LS_DEEP": 1, "LS_TITLE": 7}
ROWS = ["MANHOLE NO.", "CHAINAGE (m)", "GROUND LEVEL (m)", "INVERT LEVEL (m)", "DEPTH TO INVERT (m)",
        "PIPE DIA (mm)", "SLOPE (1 in)", "LENGTH (m)"]
PIPE_ROWS = {"PIPE DIA (mm)", "SLOPE (1 in)", "LENGTH (m)"}
ROW_CHARS = {"MANHOLE NO.": 10, "CHAINAGE (m)": 7, "GROUND LEVEL (m)": 7, "INVERT LEVEL (m)": 15,
             "DEPTH TO INVERT (m)": 5, "PIPE DIA (mm)": 5, "SLOPE (1 in)": 5, "LENGTH (m)": 6}   # longest value


def trunks(out):
    """{outfall: (stations, segments)} for every outfall of a pipeline.run result.
    stations = [{"node", "ch", "gl", "il" (invert of the sewer leaving; at the outfall the incoming one),
                 "il_in" (incoming invert or None), "new" (spacing manhole)}]
    segments = [{"label", "parent", "D", "slope", "length"}] between consecutive stations."""
    res, made = out["res"], out.get("made") or {}
    nodes = out["net_split"]["nodes"]
    best, via = {}, {}
    for lab, d in res.items():                           # res is upstream-first: longest path from a head
        L = best.get(d["from"], 0.0) + (d["length"] or 0.0)
        if L > best.get(d["to"], -1.0):
            best[d["to"]], via[d["to"]] = L, lab
    result = {}
    for o in out["net_split"]["outfalls"]:
        if o not in via:
            continue
        path, n = [], o
        while n in via:
            path.append(via[n])
            n = res[via[n]]["from"]
        path.reverse()                                   # head of sewer first
        segs = []
        for lab in path:
            d = res[lab]
            pcs = made.get(lab)
            if pcs:
                seq = list(reversed(pcs)) if d["rev"] else pcs
                for p in seq:
                    a, b, up, dn = (p["stop"], p["start"], p["dn"], p["up"]) if d["rev"] else \
                                   (p["start"], p["stop"], p["up"], p["dn"])
                    segs.append({"label": p["label"], "parent": lab, "from": a, "to": b, "up": up, "dn": dn,
                                 "D": d["D"], "slope": d["slope"], "length": p["length"]})
            else:
                segs.append({"label": lab, "parent": lab, "from": d["from"], "to": d["to"], "up": d["up"],
                             "dn": d["dn"], "D": d["D"], "slope": d["slope"], "length": d["length"]})
        st, ch = [], 0.0
        for i, s in enumerate(segs):
            if i == 0:
                st.append({"node": s["from"], "ch": 0.0, "gl": nodes[s["from"]].get("ground"), "il": s["up"],
                           "il_in": None, "new": bool(nodes[s["from"]].get("new"))})
            else:
                st[-1]["il"] = s["up"]
            ch += s["length"] or 0.0
            st.append({"node": s["to"], "ch": ch, "gl": nodes[s["to"]].get("ground"), "il": s["dn"], "il_in": s["dn"],
                       "new": bool(nodes[s["to"]].get("new"))})
        result[o] = (st, segs)
    return result


def sheets_of(stations, max_m):
    """Index ranges [(i0, i1)] of the stations on each sheet; a sheet ends at the last manhole within max_m of
    its start (at least one pipe per sheet); the next starts at that manhole."""
    out, i0 = [], 0
    while i0 < len(stations) - 1:
        i1 = i0 + 1
        while i1 + 1 < len(stations) and stations[i1 + 1]["ch"] - stations[i0]["ch"] <= max_m:
            i1 += 1
        out.append((i0, i1))
        i0 = i1
    return out


def draw(out, path, h_scale=1000, v_scale=100, max_sheet_m=750.0, text_mm=2.5):
    """DXF of the trunk L-sections of a pipeline.run result. Returns {"outfalls", "sheets", "stations"}."""
    import ezdxf
    from ezdxf.enums import TextEntityAlignment
    doc = ezdxf.new("R2010", setup=True)
    for name, col in LAYERS.items():
        doc.layers.add(name, color=col)
    msp = doc.modelspace()
    fx, fy = 1000.0 / h_scale, 1000.0 / v_scale              # paper mm per m
    deep_m = out["rules"].max_depth
    grade = out.get("grade") or "DPR"
    th = 0.8 * text_mm                                   # table text height
    rows_h = [max(4.8 * text_mm, ROW_CHARS[r] * th * 0.95 + 2.5) for r in ROWS]   # upright values fit the row
    row_y = [sum(rows_h[:i]) for i in range(len(ROWS) + 1)]                    # top of each row below the table top
    label_w = 45.0
    y_top, n_sheets, n_st = 0.0, 0, 0
    tr = trunks(out)

    def text(s, x, y, lay="LS_TEXT", rot=0.0, h=text_mm, align=TextEntityAlignment.MIDDLE_CENTER):
        msp.add_text(str(s), height=h, rotation=rot, dxfattribs={"layer": lay}).set_placement((x, y), align=align)

    for o, (st, segs) in tr.items():
        parts = sheets_of(st, max_sheet_m)
        for k, (i0, i1) in enumerate(parts):
            ss, sg = st[i0:i1 + 1], segs[i0:i1]
            levels = [s["gl"] for s in ss if s["gl"] is not None] + [s["il"] for s in ss] + \
                     [s["il_in"] for s in ss if s["il_in"] is not None]
            datum = math.floor(min(levels) - 1.0)
            top = max(levels + [x["up"] + x["D"] / 1000.0 for x in sg])
            prof_h = (top - datum) * fy + 6 * text_mm
            tab_h = row_y[-1]
            y0 = y_top - prof_h                               # datum line of this sheet
            x0 = label_w
            X = lambda c: x0 + (c - ss[0]["ch"]) * fx           # noqa: E731
            Y = lambda lv: y0 + (lv - datum) * fy              # noqa: E731
            width = X(ss[-1]["ch"]) - x0
            # ---- title
            text(f"LONGITUDINAL SECTION - MAIN TRUNK SEWER TO {o}   (sheet {k + 1} of {len(parts)}, chainage "
                 f"{ss[0]['ch']:.1f} - {ss[-1]['ch']:.1f} m)", x0, y_top + 4 * text_mm, "LS_TITLE", h=1.6 * text_mm,
                 align=TextEntityAlignment.BOTTOM_LEFT)
            text(f"Horizontal 1:{h_scale}, vertical 1:{v_scale} (drawing units = mm on paper, plot 1:1)   |   data "
                 f"grade {grade}" + ("  - NOT VALID FOR A DPR" if grade != "DPR" else ""), x0, y_top + 1.2 * text_mm,
                 "LS_TITLE", align=TextEntityAlignment.BOTTOM_LEFT)
            # ---- datum and profile lines
            msp.add_line((x0, y0), (x0 + width, y0), dxfattribs={"layer": "LS_DATUM"})
            text(f"DATUM {datum:.3f}", x0 - 2, y0 + text_mm, "LS_DATUM", align=TextEntityAlignment.BOTTOM_RIGHT)
            gpts = [(X(s["ch"]), Y(s["gl"])) for s in ss if s["gl"] is not None]
            if len(gpts) > 1:
                msp.add_lwpolyline(gpts, dxfattribs={"layer": "LS_GROUND"})
            inv, crown = [], []
            for s_, g in zip(ss, sg):
                inv += [(X(s_["ch"]), Y(g["up"]))]
                inv += [(X(s_["ch"] + g["length"]), Y(g["dn"]))]
                crown += [(X(s_["ch"]), Y(g["up"] + g["D"] / 1000.0)),
                          (X(s_["ch"] + g["length"]), Y(g["dn"] + g["D"] / 1000.0))]
            msp.add_lwpolyline(inv, dxfattribs={"layer": "LS_INVERT"})          # drops show as vertical steps
            msp.add_lwpolyline(crown, dxfattribs={"layer": "LS_CROWN"})
            for s in ss:                                                       # manhole shafts
                if s["gl"] is None:
                    continue
                lo = min(s["il"], s["il_in"] if s["il_in"] is not None else s["il"])
                w = 0.6 * fx if not s["new"] else 0.45 * fx
                msp.add_lwpolyline([(X(s["ch"]) - w, Y(lo)), (X(s["ch"]) - w, Y(s["gl"])),
                                    (X(s["ch"]) + w, Y(s["gl"])), (X(s["ch"]) + w, Y(lo))],
                                   dxfattribs={"layer": "LS_MH"})
            # ---- table
            yt = y0 - 2.0
            for r in range(len(ROWS) + 1):
                msp.add_line((0, yt - row_y[r]), (x0 + width, yt - row_y[r]), dxfattribs={"layer": "LS_TABLE"})
            msp.add_line((0, yt), (0, yt - tab_h), dxfattribs={"layer": "LS_TABLE"})
            msp.add_line((x0, yt), (x0, yt - tab_h), dxfattribs={"layer": "LS_TABLE"})
            msp.add_line((x0 + width, yt), (x0 + width, yt - tab_h), dxfattribs={"layer": "LS_TABLE"})
            for r, name in enumerate(ROWS):
                text(name, 1.5, yt - (row_y[r] + row_y[r + 1]) / 2, "LS_TABLE", h=th,
                     align=TextEntityAlignment.MIDDLE_LEFT)
            for s in ss:
                x = X(s["ch"])
                dep = (s["gl"] - s["il"]) if s["gl"] is not None else None
                vals = {"MANHOLE NO.": s["node"], "CHAINAGE (m)": f"{s['ch']:.1f}",
                        "GROUND LEVEL (m)": f"{s['gl']:.3f}" if s["gl"] is not None else "-",
                        "INVERT LEVEL (m)": (f"{s['il_in']:.3f}/{s['il']:.3f}" if s["il_in"] is not None
                                             and abs(s["il_in"] - s["il"]) > 0.0005 else f"{s['il']:.3f}"),
                        "DEPTH TO INVERT (m)": f"{dep:.2f}" if dep is not None else "-"}
                for r, name in enumerate(ROWS):
                    if name in vals:
                        lay = "LS_DEEP" if (name == "DEPTH TO INVERT (m)" and dep is not None and deep_m is not None
                                            and dep > deep_m + 1e-6) else "LS_TEXT"
                        # upright, reading upwards, baseline just left of the manhole tick
                        text(vals[name], x - 0.4, yt - (row_y[r] + row_y[r + 1]) / 2, lay, rot=90.0, h=th,
                             align=TextEntityAlignment.BOTTOM_CENTER)
                msp.add_line((x, yt), (x, yt - tab_h), dxfattribs={"layer": "LS_TABLE"})   # manhole line through the table
            for s_, g in zip(ss, sg):
                xm = X(s_["ch"] + g["length"] / 2)
                vals = {"PIPE DIA (mm)": f"{g['D']:g}", "SLOPE (1 in)": f"{round(1 / g['slope'])}" if g["slope"] else "-",
                        "LENGTH (m)": f"{g['length']:.2f}"}
                for r, name in enumerate(ROWS):
                    if name in vals:
                        text(vals[name], xm + th / 2, yt - (row_y[r] + row_y[r + 1]) / 2, rot=90.0, h=th,
                             align=TextEntityAlignment.BOTTOM_CENTER)
            n_sheets += 1
            n_st += len(ss)
            y_top = yt - tab_h - 30.0                                       # next sheet below
    try:
        from ezdxf import zoom
        doc.header["$TILEMODE"] = 1
        zoom.extents(msp, factor=1.05)
    except Exception:
        pass
    doc.saveas(path)
    return {"outfalls": len(tr), "sheets": n_sheets, "stations": n_st}
