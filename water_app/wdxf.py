"""DXF of a water network's zoning and design (user request 21-Oct-2026: 'dxf फाइल export, zoning और design का').

    path, counts = wdxf.export(stem)        # output\\<stem>\\<stem>_water_<date>_<time>.dxf

One drawing, in the drawing's own coordinates (a DXF network: those of the original drawing - XREF / INSERT it there;
a layout: UTM metres), its layers switched on / off in AutoCAD:
    zoning (the last zoning kept for the page):
        W_OZ_<n>         boundary of OZ n (one colour each; a thick dash-dot line) and its name, population, OHT
                         capacity
        W_DMA_BOUNDARY   DMA boundaries (a thin dashed line) and names, population, connections
        W_VALVE          the pipes closed at OZ / DMA boundaries: a valve symbol (circle with a cross) on the pipe
        W_DMA_INLET      the one inlet of a DMA: bulk meter + FCV + isolation valve (CPHEEO Table 2.7 S.No.21, 24, 26)
        W_OHT            the OHTs (a square) with name, capacity, staging
        W_BARRIER        the barrier lines of the page (highway / railway ...: no pipe crosses one) and their names
    design (the last design, when it was made on this zoning):
        W_PIPE, W_PIPE_CLOSED   pipes (closed ones: the boundary pipes)
        W_PIPE_TEXT      "P-17111/110mm" above, "L=21.0" below - or one line, smaller, label only, or on a leader,
                         as the sewer's plan drawing (pipe_text)
        W_FLOW_ARROW     the direction of the peak flow
        W_JUNCTION, W_JUNCTION_LOW (residual head below 17 m), W_JUNCTION_TEXT: name, GL, HGL, residual head
        W_PRV            the PRVs (a triangle on the pipe) with their setting
        W_TUBEWELL, W_RISING_MAIN   the new tube wells (a circle) and each one's rising main along the roads
    without a design: the network's pipes and junctions only (W_PIPE, W_JUNCTION, W_JUNCTION_TEXT: name, GL).
Text height: 0.67 x the median text height of the original drawing (as the sewer's plan drawing), else from the
pipe lengths (cad.default_text_height).
"""
import json
import math
import os
import time

from . import cad
from . import server as ui

LAYERS = {"W_PIPE": 5, "W_PIPE_CLOSED": 1, "W_PIPE_TEXT": 4, "W_FLOW_ARROW": 5, "W_JUNCTION": 3, "W_JUNCTION_LOW": 1,
          "W_JUNCTION_TEXT": 7, "W_OHT": 6, "W_VALVE": 1, "W_DMA_INLET": 2, "W_DMA_BOUNDARY": 8, "W_TITLE": 7,
          "W_BARRIER": 250, "W_PRV": 30, "W_TUBEWELL": 130, "W_RISING_MAIN": 130}
OZ_COLOURS = [1, 3, 5, 6, 30, 4, 2, 140, 200, 40, 90, 170, 230, 10, 110, 60, 250]     # AutoCAD colour index per OZ
LEADER = 3.0                  # x the text height: leader line of a pipe label that does not fit on its pipe
RESIDUAL_HEAD_M = 17.0        # below this a junction is drawn on W_JUNCTION_LOW (CPHEEO Table 2.7 S.No.4)
# the boundaries told apart at a glance (user request 14-Nov-2026): an OZ boundary thick and dash-dot, a DMA
# boundary thin and dashed. Patterns in units of BOUNDARY_LT_SCALE x the text height (the drawing is in metres:
# AutoCAD's own DASHED, 1.3 m long, looks like a full line there); lineweights in 1/100 mm, shown on the screen too
OZ_LINETYPE, DMA_LINETYPE = "W_OZ_DASHDOT", "W_DMA_DASHED"
LINETYPES = {OZ_LINETYPE: ("OZ boundary ____ . ____ . ____ .", [10.0, 6.0, -2.0, 0.0, -2.0]),
             DMA_LINETYPE: ("DMA boundary __ __ __ __ __ __", [4.5, 3.0, -1.5])}
BOUNDARY_LT_SCALE = 6.0
OZ_LINEWEIGHT, DMA_LINEWEIGHT = 80, 25
PLINEGEN = 128                # LWPOLYLINE flag: the pattern runs on through the corners


def pipe_text(label, nominal, length, chord, h, r):
    """[(text, side)] and the height: side +1 above, -1 below, 0 off the pipe on a leader - as sewer_app.cad.pipe_text
    (one line if it fits between the junctions, else two, smaller down to PIPE_TEXT_MIN, else the label only, else
    the label on a leader), the water's text: no slope."""
    top, bottom = f"{label}/{('%g' % nominal) if nominal else '-'}mm", f"L={cad.fmt(length, 1)}"
    room = chord - 2 * cad.MH_CLEAR * r
    one = f"{top} {bottom}"
    if cad.text_width(one, h) <= room:
        return [(one, 1)], h
    two = max(cad.text_width(top, 1.0), cad.text_width(bottom, 1.0))
    if two * cad.PIPE_TEXT_MIN * h > room:
        w = cad.text_width(label, 1.0)
        if w * cad.PIPE_TEXT_MIN * h > room:
            return [(label, 0)], h
        return [(label, 1)], max(cad.PIPE_TEXT_MIN * h, min(h, room / w))
    return [(top, 1), (bottom, -1)], max(cad.PIPE_TEXT_MIN * h, min(h, room / two))


def _kept(stem):
    """(zoning, design or None) kept for the page; the design only when it is newer than the zoning and of the same
    network. A zoning of another state of the network than the one now: an error (zoning again first)."""
    from . import ui_api
    last = ui_api.last_results(stem)
    z = last.get("zoning")
    if not z:
        raise ValueError("पहले Zoning चलाएँ")
    if z.get("stale"):
        raise ValueError("Network zoning के बाद बदला है - पहले Zoning दोबारा चलाएँ")
    d = last.get("design")
    if d and (d.get("stale") or d.get("net_rev") != z.get("net_rev")):
        d = None
    return z, d


def _text_height(stem, net):
    if ui.is_dxf(stem):
        try:
            with open(os.path.join(ui.proj_dir(), stem + ".dxf.json"), encoding="utf-8") as fh:
                src = json.load(fh).get("dxf")
            if src and os.path.isfile(src):
                return round(cad.source_text_height(src)[0] * 0.67, 3), "0.67 x the original drawing's texts"
        except Exception:
            pass
    return cad.default_text_height(net), "from the pipe lengths"


def export(stem, path=None):
    """Writes the DXF (see the module text). Returns (path, counts)."""
    import ezdxf
    from ezdxf.enums import TextEntityAlignment
    from . import ui_api
    z, d = _kept(stem)
    net = ui_api.cut_net(stem, z.get("req"))                 # the pipes as cut at the barrier lines
    nodes = {n: v for n, v in net["nodes"].items() if v.get("xy")}
    to_xy = ui.converters_for(stem)[1]
    h, h_src = _text_height(stem, net)
    r = 0.6 * h                                               # junction symbol radius, in proportion to the text
    doc = ezdxf.new("R2010", setup=True)
    for name, col in LAYERS.items():
        doc.layers.add(name, color=col)
    for name, (desc, pattern) in LINETYPES.items():
        doc.linetypes.add(name, pattern=pattern, description=desc)
    dma_layer = doc.layers.get("W_DMA_BOUNDARY")
    dma_layer.dxf.linetype, dma_layer.dxf.lineweight = DMA_LINETYPE, DMA_LINEWEIGHT
    doc.header["$LWDISPLAY"] = 1                             # the lineweights seen on the screen, not only plotted
    msp = doc.modelspace()
    n = {"oz": 0, "dma": 0, "valves": 0, "inlets": 0, "ohts": 0, "pipes": 0, "junctions": 0, "leaders": 0, "low": 0,
         "barriers": 0}

    def text(t, at, layer, height=h, align=TextEntityAlignment.MIDDLE_CENTER, rot=0.0):
        msp.add_text(t, height=height, rotation=rot, dxfattribs={"layer": layer}).set_placement(at, align=align)

    def ring_xy(ring):
        return [tuple(p) for p in to_xy(ring)]

    def boundary(ring, layer, linetype, lineweight):
        """A closed boundary line in its own line style (set on the line itself too: seen in any viewer)."""
        pl = msp.add_lwpolyline(ring_xy(ring), close=True,
                                dxfattribs={"layer": layer, "linetype": linetype, "lineweight": lineweight,
                                            "ltscale": round(BOUNDARY_LT_SCALE * h, 3)})
        pl.dxf.flags |= PLINEGEN

    # ---- zoning: OZ and DMA boundaries and names
    # the DMA boundaries first: where one runs along an OZ boundary, the OZ's thick line lies over it
    for x in z["dmas"]:
        for ring in x.get("rings") or []:
            boundary(ring, "W_DMA_BOUNDARY", DMA_LINETYPE, DMA_LINEWEIGHT)
        if x.get("label"):
            at = to_xy([x["label"]])[0]
            text(x["name"].split("/")[-1], (at[0], at[1] - 1.6 * h), "W_DMA_BOUNDARY", 1.6 * h)
            text(f"pop {x['population']:,}, {x['connections']:,} conn", (at[0], at[1] - 3.2 * h), "W_DMA_BOUNDARY", h)
        n["dma"] += 1
    for i, x in enumerate(z["zones"]):
        lay = f"W_OZ_{i + 1}"
        doc.layers.add(lay, color=OZ_COLOURS[i % len(OZ_COLOURS)])
        for ring in x.get("rings") or []:
            boundary(ring, lay, OZ_LINETYPE, OZ_LINEWEIGHT)
        if x.get("label"):
            at = to_xy([x["label"]])[0]
            kl = f"{x['capacity_kl']:g} KL" if x.get("capacity_kl") else f"new {x['required_kl']:g} KL"
            text(x["name"], (at[0], at[1] + 2.2 * h), lay, 2.5 * h)
            text(f"pop {x['population']:,}, {x['connections']:,} conn, OHT {kl}, {x['dma_count']} DMA", at, lay, 1.2 * h)
        n["oz"] += 1

    # ---- the pipes: as drawn (vertices), else straight between their junctions
    def pts_of(c):
        P = [tuple(p) for p in (c.get("vertices") or [])]
        if len(P) < 2:
            P = [tuple(nodes[c["start_node"]]["xy"]), tuple(nodes[c["stop_node"]]["xy"])] \
                if c["start_node"] in nodes and c["stop_node"] in nodes else []
        return P
    geo = {c["label"]: c for c in net["conduits"]}

    def valve(at, layer, label):
        s = 0.9 * h
        msp.add_circle(at, s, dxfattribs={"layer": layer})
        msp.add_line((at[0] - s * 0.7, at[1] - s * 0.7), (at[0] + s * 0.7, at[1] + s * 0.7), dxfattribs={"layer": layer})
        msp.add_line((at[0] - s * 0.7, at[1] + s * 0.7), (at[0] + s * 0.7, at[1] - s * 0.7), dxfattribs={"layer": layer})
        text(label, (at[0] + 1.3 * s, at[1] - 1.3 * s), layer, 0.8 * h, TextEntityAlignment.TOP_LEFT)

    # ---- boundary valves (closed pipes) and the DMA inlets
    for c in z["closed"]:
        k = geo.get(c["pipe"])
        P = pts_of(k) if k else []
        at = cad.point_along(P, 0.5) if P else tuple(to_xy([c["latlng"]])[0])
        valve(at, "W_VALVE", f"{c['pipe']} closed")
        n["valves"] += 1
    for x in z["dmas"]:
        k = geo.get(x.get("inlet_pipe") or "")
        if not k:
            continue
        P = pts_of(k)
        if not P:
            continue
        at = cad.point_along(P, 0.5)
        s = 0.9 * h
        msp.add_lwpolyline([(at[0] - s, at[1] - s), (at[0] + s, at[1] - s), (at[0] + s, at[1] + s), (at[0] - s, at[1] + s)],
                           close=True, dxfattribs={"layer": "W_DMA_INLET"})
        text(f"{x['name']} INLET {k['label']}: isolation valve + bulk meter + FCV", (at[0] + 1.4 * s, at[1]),
             "W_DMA_INLET", 0.8 * h, TextEntityAlignment.MIDDLE_LEFT)
        n["inlets"] += 1
    # ---- the PRVs of the design (prv.py): a triangle on the pipe, its setting
    n["prvs"] = 0
    for x in (d or {}).get("prvs") or []:
        k = geo.get(x.get("pipe") or "")
        if not k or not x.get("active"):
            continue
        P = pts_of(k)
        if not P:
            continue
        at, s = cad.point_along(P, 0.5), 1.1 * h
        msp.add_lwpolyline([(at[0] - s, at[1] - s), (at[0] + s, at[1] - s), (at[0], at[1] + s)], close=True,
                           dxfattribs={"layer": "W_PRV"})
        text(f"{x['name']} {k['label']}: PRV, setting {x['setting_m']:g} m", (at[0] + 1.4 * s, at[1]), "W_PRV",
             0.8 * h, TextEntityAlignment.MIDDLE_LEFT)
        n["prvs"] += 1
    # ---- the new tube wells and their rising mains (rising.py): a circle, the main along the roads, size and length
    n["tubewells"] = 0
    for x in ((d or {}).get("rising") or {}).get("tws") or []:
        at, s = tuple(to_xy([x["latlng"]])[0]), 1.2 * h
        msp.add_circle(at, s, dxfattribs={"layer": "W_TUBEWELL"})
        text(f"{x['name']}" + (f" ({x['lpm']:g} LPM)" if x.get("lpm") else ""), (at[0] + 1.4 * s, at[1]), "W_TUBEWELL",
             0.9 * h, TextEntityAlignment.MIDDLE_LEFT)
        if x.get("path"):
            P = [tuple(p) for p in to_xy(x["path"])]
            msp.add_lwpolyline(P, dxfattribs={"layer": "W_RISING_MAIN"})
            mid = cad.point_along(P, 0.5)
            text(f"RM {x['size']}{' ' + x['cls'] if x.get('cls') == 'K9' else ''} L={x['length_m']:.0f}", (mid[0], mid[1] + 1.2 * h), "W_RISING_MAIN", 0.8 * h)
        n["tubewells"] += 1

    # ---- the OHTs (at the junction they were snapped to)
    outl = {o["name"]: o for o in (d or {}).get("outlets", [])}
    for x in z["zones"]:
        if x.get("node") not in nodes:
            continue
        at, s = nodes[x["node"]]["xy"], 1.8 * h
        msp.add_lwpolyline([(at[0] - s, at[1] - s), (at[0] + s, at[1] - s), (at[0] + s, at[1] + s), (at[0] - s, at[1] + s)],
                           close=True, dxfattribs={"layer": "W_OHT"})
        o = outl.get(x["name"], {})
        kl = f"{x['capacity_kl']:g} KL" if x.get("capacity_kl") else f"new {x['required_kl']:g} KL"
        lines = [x["name"], kl + (f", staging {o['staging_m']:g} m" if o.get("staging_m") is not None else "")]
        if o.get("vfd_head_m"):
            lines.append(f"VFD pump +{o['vfd_head_m']:g} m, {o['vfd_kw']:g} kW")
        for j, t in enumerate(lines):
            text(t, (at[0] + 1.3 * s, at[1] + s - j * 1.5 * h), "W_OHT", 1.2 * h, TextEntityAlignment.TOP_LEFT)
        n["ohts"] += 1

    # ---- the barrier lines (no pipe crosses one) with their names at the middle
    from . import barriers as wb
    for b in net.get("barriers", []):
        msp.add_lwpolyline(b["xy"], dxfattribs={"layer": "W_BARRIER", "lineweight": 70})
        m = b["xy"][len(b["xy"]) // 2]
        text(f"{b['name']} ({wb.TYPES[b['type']]})", (m[0], m[1] + 1.5 * h), "W_BARRIER", 1.5 * h)
        n["barriers"] += 1

    # ---- the network: designed pipes (size, flow) and junctions (GL, HGL, residual head)
    dp = {p["label"]: p for p in (d or {}).get("pipes", [])}
    dn = {x["label"]: x for x in (d or {}).get("nodes", [])}
    for c in net["conduits"]:
        P = pts_of(c)
        if len(P) < 2:
            continue
        p = dp.get(c["label"], {})
        msp.add_lwpolyline(P, dxfattribs={"layer": "W_PIPE_CLOSED" if p.get("closed") else "W_PIPE"})
        n["pipes"] += 1
        chord = math.dist(P[0], P[-1])
        (x1, y1), (x2, y2) = cad.longest_segment(P)
        ta, tb = (P[0], P[-1]) if chord > 1e-6 else ((x1, y1), (x2, y2))
        ang = cad.readable_angle(tb[0] - ta[0], tb[1] - ta[1])
        tx, ty = cad.point_along(P, 0.5)
        nx, ny = -math.sin(math.radians(ang)), math.cos(math.radians(ang))
        lines, th = pipe_text(c["label"], p.get("nominal"), c.get("length_m"), chord, h, r)
        for t, side in lines:
            if side == 0:                                   # off the pipe: away from the junction texts (up-right)
                if nx + ny > 0:
                    nx, ny = -nx, -ny
                ex, ey = tx + nx * LEADER * h, ty + ny * LEADER * h
                msp.add_line((tx, ty), (ex, ey), dxfattribs={"layer": "W_PIPE_TEXT"})
                text(t, (ex + (0.3 if nx >= 0 else -0.3) * h, ey), "W_PIPE_TEXT", th,
                     TextEntityAlignment.MIDDLE_LEFT if nx >= 0 else TextEntityAlignment.MIDDLE_RIGHT)
                n["leaders"] += 1
                continue
            off = side * h * 0.6
            text(t, (tx + nx * off, ty + ny * off), "W_PIPE_TEXT", th,
                 TextEntityAlignment.BOTTOM_CENTER if side > 0 else TextEntityAlignment.TOP_CENTER, ang)
        q = p.get("flow")
        L_ = math.dist((x1, y1), (x2, y2))
        if q and abs(q) > 1e-6 and not p.get("closed") and L_ > 0:   # flow arrow: + = drawn start -> stop
            sgn = 1 if q > 0 else -1
            if p.get("from") and p["from"] != c["start_node"]:
                sgn = -sgn
            ux, uy = (x2 - x1) / L_ * sgn, (y2 - y1) / L_ * sgn
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            al, aw = min(1.6 * h, 0.4 * L_), 0.45 * h
            tip, bx, by = (mx + ux * al / 2, my + uy * al / 2), mx - ux * al / 2, my - uy * al / 2
            p1, p2 = (bx - uy * aw, by + ux * aw), (bx + uy * aw, by - ux * aw)
            msp.add_solid([tip, p1, p2, p2], dxfattribs={"layer": "W_FLOW_ARROW"})
    for lab, v in nodes.items():
        x, y = v["xy"]
        e = dn.get(lab, {})
        low = e.get("p") is not None and e["p"] < RESIDUAL_HEAD_M - 1e-6
        n["low"] += low
        msp.add_circle((x, y), r, dxfattribs={"layer": "W_JUNCTION_LOW" if low else "W_JUNCTION"})
        gl = e.get("gl", v.get("ground"))
        lines = [lab, f"GL {cad.fmt(gl, 2)}"] + ([f"HGL {cad.fmt(e.get('head'), 2)}", f"P {cad.fmt(e.get('p'), 2)}"]
                                                if d else [])
        for j, t in enumerate(lines):
            text(t, (x + r * 1.3, y + r * 1.3 + (len(lines) - 1 - j) * h * 1.4), "W_JUNCTION_TEXT", h,
                 TextEntityAlignment.BOTTOM_LEFT)
        n["junctions"] += 1

    # ---- title, opening view
    xs = [v["xy"][0] for v in nodes.values()]
    ys = [v["xy"][1] for v in nodes.values()]
    what = "zoning (OZ / DMA) and design (PFR)" if d else "zoning (OZ / DMA) - no design of this zoning yet"
    text(f"Water distribution network {stem}: {what} - zoning {z.get('time')}" + (f", design {d.get('time')}" if d else ""),
         (min(xs), max(ys) + 10 * h), "W_TITLE", 4 * h, TextEntityAlignment.BOTTOM_LEFT)
    try:
        from ezdxf import zoom
        doc.header["$TILEMODE"] = 1
        zoom.extents(msp, factor=1.05)
    except Exception:
        pass
    if path is None:
        folder = os.path.join(ui.out_root(), stem)
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"{stem}_water_{time.strftime('%Y%m%d_%H%M')}.dxf")
    doc.saveas(path)
    n.update(text_height=h, text_height_from=h_src, design=bool(d))
    return path, n
