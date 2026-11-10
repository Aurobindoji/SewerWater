"""CAD drawing (DXF) of a designed sewer, with the design values next to every element:
    manhole : label, GL (ground level), IL (invert level) and D (depth = GL - IL)
    conduit : label, diameter, slope (1:N) and length - along the pipe, and a flow arrow

Pipe text (user request 20-Oct-2026): "CO-11830/200mm/1:250 L=28.0" at the middle of the pipe, along the line from its
start to its stop manhole, so that it stays between the two manholes: one line when it fits there, else two -
"CO-11830/200mm" above the pipe and "1:250 L=28.0" below - and only then smaller (not below PIPE_TEXT_MIN x the
text height). The width is measured with ezdxf's metrics of the TXT font (the drawing's Standard style). A pipe so short
that even the smallest two lines would run over its manholes gets only its label (user request 21-Oct-2026: the
diameter, slope and length of such a pipe are in the report's pipe table). A pipe too short even for its label at
PIPE_TEXT_MIN (oakdale 21-Oct-2026: 646 of 13,776, 1-5 m between manhole centres - 522 pieces at bends near a manhole
or another bend, 124 short pipes of the drawing itself) gets the label at full size off the pipe, at the end of a
leader line LEADER x the text height long from the middle of the pipe, square to it and away from the manhole texts.

From the original scripts design_to_dxf.py: write_dxf, snap_ends, source_text_height, readable_angle, longest_segment, fmt
are unchanged. design_elements replaces read_model: the drawing is made from a pipeline.run result on the
SPLIT network (the new manholes for the 30 m spacing are drawn, as in the designed SewerGEMS model).

Each manhole (symbol + its 4 texts) and each conduit (polyline + its text) is one GROUP named after the label
(AutoCAD: group selection on = PICKSTYLE 1). Layers SEW_PIPE, SEW_PIPE_TEXT, SEW_MH, SEW_MH_DEEP, SEW_MH_TEXT,
SEW_OUTFALL, SEW_FLOW_ARROW. Same coordinates as the original drawing: XREF / INSERT it there.
"""
import functools
import math
import re
import statistics

MH_TEXT_RE = re.compile(r"^\s*MH\s*[-_ ]?\s*[A-Za-z]?\d+[A-Za-z]?\s*$", re.I)

LAYERS = {                      # name: AutoCAD colour index
    "SEW_PIPE": 5,              # blue
    "SEW_PIPE_TEXT": 4,         # cyan
    "SEW_MH": 3,                # green
    "SEW_MH_DEEP": 1,           # red
    "SEW_MH_TEXT": 7,           # white/black
    "SEW_OUTFALL": 6,           # magenta
    "SEW_FLOW_ARROW": 5,        # blue, like the pipe
}
PIPE_TEXT_MIN = 0.5             # a pipe text is made at most this much smaller to fit between its manholes
MH_CLEAR = 1.6                  # x the manhole symbol's radius: kept free of pipe text at both ends
LEADER = 3.0                    # x the text height: leader line of a label that does not fit on its pipe


@functools.lru_cache(maxsize=1)
def _txt_font():
    from ezdxf.fonts import fonts
    return fonts.make_font("txt", 1.0)


def text_width(s, h):
    """Width (drawing units) of s at height h in the TXT font (Standard style of ezdxf.new(setup=True))."""
    return _txt_font().text_width(s) * h


def point_along(pts, frac):
    """The point at this fraction of the polyline's length."""
    segs = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    goal, run = sum(segs) * frac, 0.0
    for i, L in enumerate(segs):
        if run + L >= goal and L > 0:
            t = (goal - run) / L
            return (pts[i][0] + t * (pts[i + 1][0] - pts[i][0]), pts[i][1] + t * (pts[i + 1][1] - pts[i][1]))
        run += L
    return tuple(pts[-1])


def pipe_text(label, D, s, length, chord, h, r_mh):
    """[(text, side)] and the text height for a pipe: side +1 above the pipe, -1 below, 0 off the pipe on a leader.
    One line if it fits between the manholes (chord - their symbols), else two lines, made smaller only if those do
    not fit either; a pipe too short for the two lines at PIPE_TEXT_MIN: its label only (as small as needed, not below
    PIPE_TEXT_MIN); a pipe too short for that too: its label at full size on a leader."""
    st = f"1:{round(1 / s)}" if s and s > 0 else ("FLAT" if s == 0 else ("ADVERSE" if s is not None else "-"))
    top, bottom = f"{label}/{('%g' % round(D)) if D else '-'}mm", f"{st} L={fmt(length, 1)}"
    room = chord - 2 * MH_CLEAR * r_mh
    one = f"{top}/{bottom}"
    if text_width(one, h) <= room:
        return [(one, 1)], h
    two = max(text_width(top, 1.0), text_width(bottom, 1.0))
    if two * PIPE_TEXT_MIN * h > room:
        w = text_width(label, 1.0)
        if w * PIPE_TEXT_MIN * h > room:
            return [(label, 0)], h
        return [(label, 1)], max(PIPE_TEXT_MIN * h, min(h, room / w))
    return [(top, 1), (bottom, -1)], max(PIPE_TEXT_MIN * h, min(h, room / two if room > 0 else 0.0))


def source_text_height(path):
    """Median height of the manhole-label texts of the original drawing (all texts if none match).
    Returns (height, how many texts it is based on, what). DXF, or DWG through the ODA File Converter."""
    from .dxf_inspect import load
    doc, _ = load(path)
    mh, allh = [], []
    for e in doc.modelspace().query("TEXT MTEXT"):
        try:
            if e.dxftype() == "TEXT":
                txt, h = e.dxf.text, e.dxf.height
            else:
                txt, h = e.plain_text(), e.dxf.char_height
        except Exception:
            continue
        if not h or h <= 0:
            continue
        allh.append(h)
        if MH_TEXT_RE.match(txt or ""):
            mh.append(h)
    if mh:
        return statistics.median(mh), len(mh), "manhole labels (MH-...)"
    if allh:
        return statistics.median(allh), len(allh), "all texts (no MH-... label found)"
    raise ValueError(f"no text found in {path} - give the text height instead")


def readable_angle(dx, dy):
    """Text angle along a segment, turned so that the text is never upside down."""
    a = math.degrees(math.atan2(dy, dx))
    if a > 90:
        a -= 180
    elif a <= -90:
        a += 180
    return a


def longest_segment(pts):
    best, k = -1.0, 0
    for i in range(len(pts) - 1):
        L = math.dist(pts[i], pts[i + 1])
        if L > best:
            best, k = L, i
    return pts[k], pts[k + 1]


def fmt(v, nd=3):
    return "-" if v is None else f"{v:.{nd}f}"


def write_dxf(out, nodes, conds, h, deep_m=None, extra=None):
    """nodes = {label: {"xy": (x, y), "gl": .., "il": .., "outfall": bool}};
    conds = [{"label", "pts": [(x, y), ...], "D": mm, "slope": m/m, "length": m}]. Returns counts.
    extra(doc, msp): optional - another script adds its own layers / entities (e.g. zoning: zone
    boundaries) before the view is set and the file saved."""
    import ezdxf
    import ezdxf.bbox
    from ezdxf.enums import TextEntityAlignment
    doc = ezdxf.new("R2010", setup=True)
    for name, col in LAYERS.items():
        if name not in doc.layers:
            doc.layers.add(name, color=col)
    msp = doc.modelspace()
    r_mh = 0.6 * h                                   # manhole symbol radius, in proportion to the text
    n_deep, n_grp, n_arrow, n_lead, used = 0, 0, 0, 0, set()

    def group(prefix, lab, ents):
        """Symbol + its texts as one named DXF GROUP: picking one selects all (AutoCAD PICKSTYLE 1)."""
        nonlocal n_grp
        name = re.sub(r"[^A-Za-z0-9_\-]", "_", str(lab))[:250]          # group name = element label
        base, k = name, 1
        while name.upper() in used:
            k += 1
            name = f"{base}_{k}"
        used.add(name.upper())
        g = doc.groups.new(name, description=f"{prefix} {lab}", selectable=True)
        g.extend(ents)
        n_grp += 1

    for lab, n in nodes.items():
        if n.get("xy") is None:
            continue
        x, y = n["xy"]
        depth = (n["gl"] - n["il"]) if (n.get("gl") is not None and n.get("il") is not None) else None
        is_deep = deep_m is not None and depth is not None and depth > deep_m + 1e-6
        n_deep += is_deep
        lay = "SEW_OUTFALL" if n.get("outfall") else ("SEW_MH_DEEP" if is_deep else "SEW_MH")
        ents = [msp.add_circle((x, y), r_mh * (1.6 if n.get("outfall") else 1.0), dxfattribs={"layer": lay})]
        lines = [lab, f"GL {fmt(n.get('gl'))}", f"IL {fmt(n.get('il'))}",
                 f"D {fmt(depth, 2)}"]              # depth = GL - IL, every manhole
        for i, t in enumerate(lines):           # four lines up-right of the symbol
            ents.append(msp.add_text(t, height=h, dxfattribs={"layer": "SEW_MH_TEXT"}).set_placement(
                (x + r_mh * 1.3, y + r_mh * 1.3 + (len(lines) - 1 - i) * h * 1.4),
                align=TextEntityAlignment.BOTTOM_LEFT))
        group("OF" if n.get("outfall") else "MH", lab, ents)
    for c in conds:
        pts = c["pts"]
        if not pts or len(pts) < 2:
            continue
        ents = [msp.add_lwpolyline(pts, dxfattribs={"layer": "SEW_PIPE"})]
        (x1, y1), (x2, y2) = longest_segment(pts)
        # the text: at the middle of the pipe, along the line between its manholes (pipe_text)
        chord = math.dist(pts[0], pts[-1])
        ta, tb = (pts[0], pts[-1]) if chord > 1e-6 else ((x1, y1), (x2, y2))
        ang = readable_angle(tb[0] - ta[0], tb[1] - ta[1])
        tx, ty = point_along(pts, 0.5)
        nx, ny = -math.sin(math.radians(ang)), math.cos(math.radians(ang))     # left normal of the text
        lines, th = pipe_text(c["label"], c.get("D"), c.get("slope"), c.get("length"), chord, h, r_mh)
        for txt, side in lines:
            if side == 0:                               # off the pipe: leader to the side away from the manhole texts
                if nx + ny > 0:                         # (they are up-right of every manhole)
                    nx, ny = -nx, -ny
                ex, ey = tx + nx * LEADER * h, ty + ny * LEADER * h
                ents.append(msp.add_line((tx, ty), (ex, ey), dxfattribs={"layer": "SEW_PIPE_TEXT"}))
                ents.append(msp.add_text(txt, height=th, dxfattribs={"layer": "SEW_PIPE_TEXT"}).set_placement(
                    (ex + (0.3 if nx >= 0 else -0.3) * h, ey),
                    align=TextEntityAlignment.MIDDLE_LEFT if nx >= 0 else TextEntityAlignment.MIDDLE_RIGHT))
                n_lead += 1
                continue
            off = side * h * 0.6                        # clear of the flow arrow (half width 0.45 h) at any size
            ents.append(msp.add_text(txt, height=th, rotation=ang, dxfattribs={"layer": "SEW_PIPE_TEXT"}).set_placement(
                (tx + nx * off, ty + ny * off),
                align=TextEntityAlignment.BOTTOM_CENTER if side > 0 else TextEntityAlignment.TOP_CENTER))
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        if c.get("dir"):                         # flow arrow on the pipe, middle of its longest segment
            L_ = math.dist((x1, y1), (x2, y2))
            if L_ > 0:
                ux, uy = (x2 - x1) / L_ * c["dir"], (y2 - y1) / L_ * c["dir"]
                al, aw = min(1.6 * h, 0.4 * L_), 0.45 * h            # length, half width
                tip = (mx + ux * al / 2, my + uy * al / 2)
                bx, by = mx - ux * al / 2, my - uy * al / 2
                p1, p2 = (bx - uy * aw, by + ux * aw), (bx + uy * aw, by - ux * aw)
                # SOLID vertex order 1-2-4-3: a triangle = last point repeated
                ents.append(msp.add_solid([tip, p1, p2, p2], dxfattribs={"layer": "SEW_FLOW_ARROW"}))
                n_arrow += 1
        group("CO", c["label"], ents)
    if extra is not None:
        extra(doc, msp)
    # open in MODEL space, zoomed to the network (a new DXF otherwise opens on Layout1 / at 0,0)
    try:
        from ezdxf import zoom
        doc.header["$TILEMODE"] = 1                  # AutoCAD opens on the Model tab
        zoom.extents(msp, factor=1.05)
        ext = ezdxf.bbox.extents(msp)
        if ext.has_data:
            doc.header["$EXTMIN"] = (ext.extmin.x, ext.extmin.y, 0)
            doc.header["$EXTMAX"] = (ext.extmax.x, ext.extmax.y, 0)
            doc.header["$LIMMIN"] = (ext.extmin.x, ext.extmin.y)
            doc.header["$LIMMAX"] = (ext.extmax.x, ext.extmax.y)
    except Exception as e:                           # only the opening view - the drawing itself is complete
        print(f"(note) opening view not set ({type(e).__name__}) - in AutoCAD: Model tab, then ZOOM E")
    doc.saveas(out)
    return {"nodes": len(nodes), "conduits": len(conds), "deep": n_deep, "groups": n_grp, "arrows": n_arrow,
            "leaders": n_lead}


def snap_ends(nodes, conds):
    """First / last vertex of every conduit = EXACTLY the centre of its start / stop manhole, so that
    the pipe and the manhole symbol meet at one point (endpoint / centre OSNAP, STRETCH together).
    The polyline is drawn start -> stop; if it was stored the other way round it is reversed.
    Returns (number of conduits changed, largest shift in drawing units, conduit with it)."""
    n_fix, worst, worst_lab = 0, 0.0, None
    for c in conds:
        pts = c.get("pts")
        a = (nodes.get(c.get("start")) or {}).get("xy")
        b = (nodes.get(c.get("stop")) or {}).get("xy")
        if not pts or len(pts) < 2 or a is None or b is None:
            continue
        pts = [tuple(p) for p in pts]
        if math.dist(pts[0], b) + math.dist(pts[-1], a) < math.dist(pts[0], a) + math.dist(pts[-1], b):
            pts.reverse()
        shift = max(math.dist(pts[0], a), math.dist(pts[-1], b))
        if shift > 1e-9:
            n_fix += 1
            if shift > worst:
                worst, worst_lab = shift, c["label"]
        pts[0], pts[-1] = tuple(a), tuple(b)
        c["pts"] = pts
    return n_fix, worst, worst_lab


def default_text_height(net):
    """Text height when there is no source drawing: median conduit length / 25, within 0.5 - 3 m (as zoning)."""
    Ls = sorted(k["length_m"] for k in net["conduits"] if k.get("length_m"))
    return min(3.0, max(0.5, round(Ls[len(Ls) // 2] / 25, 2))) if Ls else 1.0


def design_elements(out):
    """(nodes, conds) for write_dxf from a pipeline.run result: the split network (new manholes included),
    design invert of every node, each piece with the diameter and grade of its conduit; slope positive in the
    flow direction, dir = +1 when drawn in the flow direction."""
    net, res, info, made = out["net_split"], out["res"], out["node_info"], out.get("made") or {}
    outs = set(net["outfalls"])
    piece_of = {p["label"]: (lab, p) for lab, pcs in made.items() if pcs for p in pcs}
    new_inv = {m["label"]: m["invert"] for m in out.get("new_mh") or [] if m.get("in_model")}
    nodes = {}
    for n, v in net["nodes"].items():
        il = info.get(n, {}).get("invert") if n in info else new_inv.get(n)
        nodes[n] = {"xy": tuple(v["xy"]) if v.get("xy") else None, "gl": v.get("ground"), "il": il,
                    "outfall": n in outs}
    conds = []
    for k in net["conduits"]:
        lab = k["label"]
        if lab in piece_of:
            parent, p = piece_of[lab]
            up_drawn, dn_drawn = p["up"], p["dn"]                  # at start / stop node of the piece
        else:
            parent = lab
            d = res[lab]
            up_drawn, dn_drawn = (d["dn"], d["up"]) if d["rev"] else (d["up"], d["dn"])
        d = res[parent]
        L = k["length_m"]
        flows_with_drawing = not d["rev"]
        s = (up_drawn - dn_drawn) / L if L else None             # start -> stop
        conds.append({"label": lab, "pts": [tuple(p) for p in k.get("vertices") or []] or None, "D": d["D"],
                      "slope": s if flows_with_drawing else (-s if s is not None else None), "length": L,
                      "start": k["start_node"], "stop": k["stop_node"], "dir": 1 if flows_with_drawing else -1})
    for c in conds:
        if not c["pts"]:
            a, b = nodes.get(c["start"], {}).get("xy"), nodes.get(c["stop"], {}).get("xy")
            c["pts"] = [a, b] if a and b else None
    return nodes, conds


def design_drawing(out, path, text_height=None, deep_m=None):
    """Plan DXF of a pipeline.run result. text_height: from the original drawing (source_text_height x 0.67,
    as design_to_dxf) or default_text_height. deep_m: manholes deeper than this on SEW_MH_DEEP (default the
    CPHEEO max_depth_to_invert_m of the run). Returns counts (+ snap info)."""
    nodes, conds = design_elements(out)
    n_fix, worst, wlab = snap_ends(nodes, conds)
    h = text_height or default_text_height(out["net_split"])
    if deep_m is None:
        deep_m = out["rules"].max_depth
    grade = out.get("grade") or "DPR"

    def title(doc, msp):
        """Data grade above the top-left of the network (layer SEW_TITLE, red for a PFR)."""
        pts = [n["xy"] for n in nodes.values() if n.get("xy")]
        if not pts:
            return
        x0, y1 = min(p[0] for p in pts), max(p[1] for p in pts)
        doc.layers.add("SEW_TITLE", color=1 if grade != "DPR" else 7)
        txt = ("DATA GRADE: PFR - NOT VALID FOR A DPR (ground levels from DEM / assumed data)" if grade != "DPR"
               else "DATA GRADE: DPR (survey ground levels)")
        msp.add_text(txt, height=4 * h, dxfattribs={"layer": "SEW_TITLE"}).set_placement((x0, y1 + 8 * h))
    cnt = write_dxf(path, nodes, conds, h, deep_m, extra=title)
    cnt.update({"snapped": n_fix, "snap_worst_m": worst, "snap_worst": wlab, "text_height": h,
                "no_xy": [k for k, n in nodes.items() if n["xy"] is None],
                "no_pts": [c["label"] for c in conds if not c["pts"]]})
    return cnt
