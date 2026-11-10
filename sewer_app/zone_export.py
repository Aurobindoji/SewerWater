"""Export of a zoning option as shown on the map of the UI (user request 13-Oct-2026): main zones (from the slope
of the ground) 1, 2, ... with thick boundaries, sub-zones (pumping station added for depth, and the rest of such a
main zone) 1-A, 1-B, ... with dashed boundaries, the STP / pumping stations and the sewers in the colour of their
main zone - as DXF (project coordinates, for the drawing), KML (Google Earth) and Excel (the table of the legend).

    files = zone_export.export(option, folder, base, to_ll, to_xy, net, info, design_dxf=None)

option = one option of the page's zoning result (ui.run_zoning: outlets, mains, subs, parent, conduit_zone, cuts);
to_ll / to_xy convert lists of points between the drawing's metres and [lat, lon]; net = the network of the zoning
(network CSV); info = {"project", "zoning time", inputs ...} for the Summary.

design_dxf (user request 20-Oct-2026): the plan DXF of this option's design (cad.design_drawing - pipe labels,
diameter / slope / length, flow arrows, manhole GL / IL / depth); the zones are then drawn into a copy of it, so the
exported drawing has the design too (the zone-coloured copies of the sewers on layers SEWER_ZONE_n, switched off).
Manholes on top of each other with no sewer between them (repair.overlaps) get a red cross (layer WARN_MH_OVERLAP).
"""
import collections
import math

ZCOL = ["#1f77b4", "#2ca02c", "#9467bd", "#ff7f0e", "#17becf", "#8c564b", "#e377c2", "#bcbd22",
        "#7f7f7f", "#393b79", "#637939", "#843c39", "#7b4173", "#3182bd", "#e6550d"]       # as map.html
STP_ROLE = "STP (gravity)"


def zone_names(o):
    """The page's names (map.html zoneNames): main zones numbered 1, 2, ... (the STP's first, then by number of
    manholes); in a main zone with pumping stations for depth those are n-A, n-B, ... and the rest of the zone
    (reaching the main outlet) gets the next letter. Returns (mains in order, {outlet: main}, {main: number},
    {outlet: sub-zone name})."""
    outlets = o["outlets"]
    parent = o.get("parent") or {x["manhole"]: x["manhole"] for x in outlets}
    by = {x["manhole"]: x for x in outlets}
    size = collections.Counter()
    for x in outlets:
        size[parent[x["manhole"]]] += x.get("manholes") or 0
    order = list(dict.fromkeys(parent.values()))
    mains = sorted(order, key=lambda m: (not (by.get(m, {}).get("role") == STP_ROLE), -size[m]))
    num = {m: i for i, m in enumerate(mains, start=1)}
    sub, letters = {}, collections.Counter()
    for x in outlets:
        m = parent[x["manhole"]]
        if x["manhole"] == m:
            continue
        letters[m] += 1
        sub[x["manhole"]] = f"{num[m]}-{chr(64 + letters[m])}"
    for m in mains:
        if letters[m]:
            sub[m] = f"{num[m]}-{chr(65 + letters[m])}"
    return mains, parent, num, sub


def _rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def _kml_color(h, alpha="ff"):
    r, g, b = h[1:3], h[3:5], h[5:7]
    return f"{alpha}{b}{g}{r}"


def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _role(x, sub_of_depth):
    if x.get("role") == STP_ROLE:
        return "STP"
    return "pumping station (for depth)" if sub_of_depth else "pumping station"


def export(o, folder, base, to_ll, to_xy, net, info, design_dxf=None):
    import os
    os.makedirs(folder, exist_ok=True)
    mains, parent, num, sub = zone_names(o)
    by = {x["manhole"]: x for x in o["outlets"]}
    col = {m: ZCOL[i % len(ZCOL)] for i, m in enumerate(mains)}
    cuts = set(o.get("cuts") or [])
    cz = o.get("conduit_zone") or {}
    xy = {n: v["xy"] for n, v in net["nodes"].items() if v.get("xy")}
    sewers = []                                              # (label, from, to, length, [xy], zone outlet, cut)
    for k in net["conduits"]:
        pts = k.get("vertices") or [xy[n] for n in (k["start_node"], k["stop_node"]) if n in xy]
        if len(pts) >= 2:
            sewers.append((k["label"], k["start_node"], k["stop_node"], k.get("length_m") or 0.0, [list(p) for p in pts],
                           cz.get(k["label"]), k["label"] in cuts))
    main_rings = {mz["outlet"]: mz["rings"] for mz in o.get("mains") or []}          # [lat, lon]
    # name points: one in every larger piece (ring_labels), else the zone's single label
    main_lab = {mz["outlet"]: ([p for p in mz.get("ring_labels") or [] if p] or [mz.get("label")])
                for mz in o.get("mains") or []}
    subs = o.get("subs") or {}

    def zname(z):
        if z is None:
            return "-", "-"
        return f"Zone {num.get(parent.get(z, z), '?')}", (sub.get(z) or "")

    files = {}
    files["dxf"] = _dxf(base + ".dxf", mains, parent, num, sub, col, main_rings, main_lab, subs, by, sewers, to_xy, net,
                        design_dxf)
    files["kml"] = _kml(base + ".kml", mains, parent, num, sub, col, main_rings, main_lab, subs, by, sewers, to_ll, info)
    files["xlsx"] = _xlsx(base + ".xlsx", o, mains, parent, num, sub, by, sewers, zname, info)
    return files


# ---------------------------------------------------------------- DXF (project coordinates)
def _dxf(path, mains, parent, num, sub, col, main_rings, main_lab, subs, by, sewers, to_xy, net, design_dxf=None):
    """Main zone boundary: a WIDE polyline in the zone colour (thick even with lineweights off); sub-zone boundary:
    yellow, dashed (linetype generated along the whole ring), narrower; names as MTEXT with a background mask so
    that they read over the sewers; the sub-zone name also at its pumping station."""
    import ezdxf
    from ezdxf.enums import MTextEntityAlignment
    from .cad import default_text_height
    h = default_text_height(net)
    pts = [v["xy"] for v in net["nodes"].values() if v.get("xy")]
    diag = math.dist((min(p[0] for p in pts), min(p[1] for p in pts)), (max(p[0] for p in pts), max(p[1] for p in pts))) if pts else 0
    h_main, h_sub = max(8 * h, diag / 70), max(4 * h, diag / 150)     # readable with the whole area on the screen
    w_main, w_sub = max(2 * h, diag / 1500), max(h, diag / 5000)       # polyline widths (m)
    lt_sub = max(5.0, diag / 250)                                       # dash length of the sub-zone boundary
    yellow = (255, 215, 0)
    doc = ezdxf.readfile(design_dxf) if design_dxf else ezdxf.new("R2010", setup=True)
    msp = doc.modelspace()
    for name, lw, lt in (("ZONE_NAME", 35, "CONTINUOUS"), ("SUBZONE_NAME", 25, "CONTINUOUS"), ("STP", 35, "CONTINUOUS"),
                         ("PS", 35, "CONTINUOUS"), ("SEWER_CUT", 18, "DASHED")):
        doc.layers.add(name, lineweight=lw, linetype=lt)
    doc.layers.add("WARN_MH_OVERLAP", color=1, lineweight=50)
    # every boundary on a layer with its name - AutoCAD shows it when the cursor is on the line
    for m in mains:
        doc.layers.add(f"ZONE_BOUNDARY_{num[m]}", lineweight=70, linetype="CONTINUOUS")
    for so in subs:
        doc.layers.add(f"SUBZONE_BOUNDARY_{sub.get(so, so)}", lineweight=35, linetype="DASHED")
    for m in mains:
        lay = doc.layers.add(f"SEWER_ZONE_{num[m]}", lineweight=18)
        if design_dxf:
            lay.off()                                           # the design's own sewers (SEW_PIPE) are shown
    PLINEGEN = 128

    def label(s_, xy, height, layer, rgb):
        t = msp.add_mtext(s_, dxfattribs={"layer": layer, "char_height": height, "insert": tuple(xy)})
        t.set_location(tuple(xy), attachment_point=MTextEntityAlignment.MIDDLE_CENTER)
        if not design_dxf:                                     # with the design: its pipes stay readable under it
            t.set_bg_color("canvas", scale=1.25)               # masks the sewers behind the name
        t.rgb = rgb
    below = []                                                 # drawn first: under the design's pipes, manholes, texts
    for m in mains:
        rgb = _rgb(col[m])
        for ring in main_rings.get(m, []):
            e = msp.add_lwpolyline(to_xy(ring), close=True, dxfattribs={"layer": f"ZONE_BOUNDARY_{num[m]}",
                                                                          "const_width": w_main})
            e.rgb = rgb
            below.append(e)
    for so, sz in subs.items():
        for ring in sz.get("rings", []):
            e = msp.add_lwpolyline(to_xy(ring), close=True, dxfattribs={"layer": f"SUBZONE_BOUNDARY_{sub.get(so, so)}",
                                                                          "const_width": w_sub, "ltscale": lt_sub})
            e.dxf.flags = e.dxf.flags | PLINEGEN
            e.rgb = yellow
            below.append(e)
    for lab, a, b, L, pts_, z, cut in sewers:
        if cut:
            e = msp.add_lwpolyline(pts_, dxfattribs={"layer": "SEWER_CUT", "ltscale": lt_sub / 3})
            e.dxf.flags = e.dxf.flags | PLINEGEN
            below.append(e)
        elif z is not None:
            m = parent.get(z, z)
            e = msp.add_lwpolyline(pts_, dxfattribs={"layer": f"SEWER_ZONE_{num.get(m, 0)}"})
            e.rgb = _rgb(col.get(m, "#808080"))
            below.append(e)
    if design_dxf and below:
        # user request 20-Oct-2026: the zone boundary (the wide band) under the conduits, manholes and texts - the
        # draw order (SORTENTS table): the lowest sort handle is drawn first
        msp.set_redraw_order({e.dxf.handle: "1" for e in below})
        doc.header["$SORTENTS"] = 127
    # names on top of the lines
    for m in mains:
        for p in main_lab.get(m) or []:
            if p:
                label(f"ZONE {num[m]}", to_xy([p])[0], h_main, "ZONE_NAME", _rgb(col[m]))
    for so, sz in subs.items():
        for p in [q for q in sz.get("ring_labels") or [] if q] or [sz.get("label")]:
            if p:
                label(f"SUB-ZONE {sub.get(so, so)}", to_xy([p])[0], h_sub, "SUBZONE_NAME", yellow)
    xy = {n: v["xy"] for n, v in net["nodes"].items() if v.get("xy")}
    for o_, x in by.items():
        if o_ not in xy:
            continue
        stp = x.get("role") == STP_ROLE
        lay = "STP" if stp else "PS"
        msp.add_circle(xy[o_], max(3 * h, h_sub / 2), dxfattribs={"layer": lay})
        name = "STP" if stp else f"PS {sub.get(o_) or num.get(parent.get(o_, o_))}"
        t = msp.add_mtext(f"{name} ({o_})", dxfattribs={"layer": lay, "char_height": h_sub * 0.7})
        t.set_location((xy[o_][0] + max(4 * h, h_sub * 0.7), xy[o_][1]), attachment_point=MTextEntityAlignment.MIDDLE_LEFT)
        if not design_dxf:
            t.set_bg_color("canvas", scale=1.2)
    from .repair import overlaps
    r_x = max(3 * h, h_sub / 3)
    for a, b, d in overlaps(net):
        x, y = xy[a]
        for sx in (-1, 1):
            msp.add_lwpolyline([(x - r_x, y - sx * r_x), (x + r_x, y + sx * r_x)],
                               dxfattribs={"layer": "WARN_MH_OVERLAP", "const_width": r_x / 6})
        t = msp.add_mtext(f"{a} / {b}: {d:.2f} m, not joined", dxfattribs={"layer": "WARN_MH_OVERLAP", "char_height": h})
        t.set_location((x + 1.2 * r_x, y + 1.2 * r_x), attachment_point=MTextEntityAlignment.BOTTOM_LEFT)
    doc.saveas(path)
    return path


# ---------------------------------------------------------------- KML (Google Earth)
def _kml(path, mains, parent, num, sub, col, main_rings, main_lab, subs, by, sewers, to_ll, info):
    def coords(lls, close=False):
        pts = [f"{p[1]:.7f},{p[0]:.7f},0" for p in lls]
        if close and pts and pts[0] != pts[-1]:
            pts.append(pts[0])
        return " ".join(pts)
    styles = []
    for m in mains:
        c = col[m]
        styles.append(f'<Style id="main{num[m]}"><LineStyle><color>{_kml_color(c)}</color><width>4</width></LineStyle>'
                      f'<PolyStyle><color>{_kml_color(c, "22")}</color></PolyStyle></Style>'
                      f'<Style id="sub{num[m]}"><LineStyle><color>{_kml_color(c, "bb")}</color><width>1.5</width></LineStyle>'
                      f'<PolyStyle><fill>0</fill></PolyStyle></Style>'
                      f'<Style id="sew{num[m]}"><LineStyle><color>{_kml_color(c, "cc")}</color><width>2</width></LineStyle></Style>')
    styles.append('<Style id="cut"><LineStyle><color>ff000000</color><width>2</width></LineStyle></Style>'
                  '<Style id="lab"><IconStyle><scale>0</scale></IconStyle><LabelStyle><scale>1.3</scale></LabelStyle></Style>'
                  '<Style id="slab"><IconStyle><scale>0</scale></IconStyle><LabelStyle><scale>0.9</scale></LabelStyle></Style>'
                  '<Style id="stp"><IconStyle><color>ffa04000</color><scale>1.3</scale></IconStyle></Style>'
                  '<Style id="ps"><IconStyle><color>ff0060ff</color><scale>1.0</scale></IconStyle></Style>')

    def poly(name, rings, style):
        return "".join(f"<Placemark><name>{_esc(name)}</name><styleUrl>#{style}</styleUrl><Polygon><outerBoundaryIs>"
                       f"<LinearRing><coordinates>{coords(r, True)}</coordinates></LinearRing></outerBoundaryIs></Polygon>"
                       f"</Placemark>" for r in rings)

    def point(name, ll, style, desc=""):
        if not ll:
            return ""
        return (f"<Placemark><name>{_esc(name)}</name>" + (f"<description>{_esc(desc)}</description>" if desc else "")
                + f"<styleUrl>#{style}</styleUrl><Point><coordinates>{coords([ll])}</coordinates></Point></Placemark>")
    parts = ['<Folder><name>Zones (from the ground slope)</name>']
    for m in mains:
        parts.append(poly(f"Zone {num[m]}", main_rings.get(m, []), f"main{num[m]}"))
    parts.append('</Folder><Folder><name>Sub-zones</name>')
    for so, sz in subs.items():
        parts.append(poly(f"Sub-zone {sub.get(so, so)}", sz.get("rings", []), f"sub{num[parent.get(so, so)]}"))
    parts.append('</Folder><Folder><name>Labels</name>')
    for m in mains:
        for p in main_lab.get(m) or []:
            parts.append(point(f"Zone {num[m]}", p, "lab"))
    for so, sz in subs.items():
        for p in [q for q in sz.get("ring_labels") or [] if q] or [sz.get("label")]:
            parts.append(point(f"Sub-zone {sub.get(so, so)}", p, "slab"))
    parts.append('</Folder><Folder><name>STP / pumping stations</name>')
    for o_, x in by.items():
        stp = x.get("role") == STP_ROLE
        name = "STP" if stp else f"PS {sub.get(o_) or num.get(parent.get(o_, o_))}"
        parts.append(point(name, x.get("latlng"), "stp" if stp else "ps",
                           f"Outlet {o_}; {x.get('manholes')} manholes; {x.get('flow_lps')} L/s; wet well {x.get('depth')} m"))
    parts.append('</Folder>')
    # sewers: one folder per main zone (all points converted in one go)
    lls = to_ll([p for s in sewers for p in s[4]])
    i = 0
    by_main = collections.defaultdict(list)
    for lab, a, b, L, pts, z, cut in sewers:
        seg = lls[i:i + len(pts)]
        i += len(pts)
        key = "cut" if cut else (num.get(parent.get(z, z)) if z is not None else None)
        by_main[key].append(f"<Placemark><name>{_esc(lab)}</name><styleUrl>#{'cut' if cut else f'sew{key}'}</styleUrl>"
                            f"<LineString><coordinates>{coords(seg)}</coordinates></LineString></Placemark>")
    for m in mains:
        parts.append(f"<Folder><name>Sewers - Zone {num[m]}</name><visibility>1</visibility>{''.join(by_main.get(num[m], []))}</Folder>")
    if by_main.get("cut"):
        parts.append(f"<Folder><name>Cut sewers (one end disconnected)</name>{''.join(by_main['cut'])}</Folder>")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write('<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
                 f"<name>{_esc(info.get('project', ''))} - zoning option {_esc(info.get('option', ''))}</name>"
                 + "".join(styles) + "".join(parts) + "</Document></kml>\n")
    return path


# ---------------------------------------------------------------- Excel (the legend as a table)
def _xlsx(path, o, mains, parent, num, sub, by, sewers, zname, info):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter
    bold, head = Font(bold=True), PatternFill("solid", fgColor="D9E1F2")
    zfill = PatternFill("solid", fgColor="EEF3FB")
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    for k, v in info.items():
        ws.append([k, v])
        ws.cell(row=ws.max_row, column=1).font = bold
    ws.append(["Names", "Zone n = zone made from the slope of the ground; n-A, n-B ... = its sub-zones: a pumping "
                       "station added where the sewer would go deeper than the depth limit, and the rest of the zone (reaching "
                       "the zone's own outlet) with the next letter"])
    ws.cell(row=ws.max_row, column=1).font = bold
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 110

    wz = wb.create_sheet("Zones")
    cols = ["Zone", "Sub-zone", "Outlet manhole", "Type", "Manholes", "Design flow at outlet (L/s)", "Area (ha)",
            "Wet well / outlet depth (m)", "Why this outlet"]
    wz.append(cols)
    for c in wz[1]:
        c.font, c.fill = bold, head
    for m in mains:
        allz = [x for x in o["outlets"] if parent.get(x["manhole"], x["manhole"]) == m]
        mo = by.get(m, {})
        tot_mh = sum(x.get("manholes") or 0 for x in allz)
        tot_ha = sum(x.get("area_ha") or 0 for x in allz)
        wz.append([f"Zone {num[m]}", f"{len(allz)} sub-zones" if len(allz) > 1 else "", m,
                   "STP" if mo.get("role") == STP_ROLE else "pumping station", tot_mh,
                   mo.get("flow_lps") if len(allz) == 1 else None, round(tot_ha, 2), mo.get("depth") if len(allz) == 1 else None,
                   mo.get("why")])
        for c in wz[wz.max_row]:
            c.font, c.fill = bold, zfill
        if len(allz) > 1:
            for x in sorted(allz, key=lambda x: sub.get(x["manhole"], "")):
                wz.append([f"Zone {num[m]}", sub.get(x["manhole"], ""), x["manhole"],
                           _role(x, x["manhole"] != m), x.get("manholes"), x.get("flow_lps"), x.get("area_ha"),
                           x.get("depth"), x.get("why")])
    for i, w in enumerate((10, 12, 16, 30, 10, 14, 10, 14, 34), start=1):
        wz.column_dimensions[get_column_letter(i)].width = w
    wz.freeze_panes = "A2"

    wsw = wb.create_sheet("Sewers")
    wsw.append(["Conduit", "From", "To", "Length (m)", "Zone", "Sub-zone", "Zone outlet", "Cut (one end disconnected)"])
    for c in wsw[1]:
        c.font, c.fill = bold, head
    for lab, a, b, L, pts, z, cut in sewers:
        zn, sz = zname(z)
        wsw.append([lab, a, b, round(L, 2), zn, sz, z or "", "yes" if cut else ""])
    for i, w in enumerate((12, 14, 14, 11, 10, 10, 14, 16), start=1):
        wsw.column_dimensions[get_column_letter(i)].width = w
    wsw.freeze_panes = "A2"
    wb.save(path)
    return path
