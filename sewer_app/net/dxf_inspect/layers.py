"""dxf_inspect: the drawing's inventory - its layers, lines, texts, blocks and points."""
import collections
from .reading import polyline_points, pos_of, seg_len, text_height, text_of


# ---------------------------------------------------------------- analysis
def inventory(msp):
    layers = collections.defaultdict(lambda: {"types": collections.Counter(), "length": 0.0, "z": set(),
                                              "color": collections.Counter()})
    lines, texts, inserts, points = [], [], [], []
    for e in msp:
        t = e.dxftype()
        lay = e.dxf.get("layer", "0")
        L = layers[lay]
        L["types"][t] += 1
        L["color"][e.dxf.get("color", 256)] += 1
        pp = polyline_points(e)
        if pp is not None:
            pts, closed = pp
            if len(pts) >= 2:
                ln = sum(seg_len(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
                L["length"] += ln
                for p in pts:
                    L["z"].add(round(p[2], 3))
                lines.append({"layer": lay, "pts": pts, "closed": closed, "len": ln, "handle": e.dxf.handle})
            continue
        if t in ("TEXT", "MTEXT"):
            p = pos_of(e)
            if p:
                texts.append({"layer": lay, "text": (text_of(e) or "").strip(), "x": p[0], "y": p[1], "src": t,
                              "h": text_height(e)})
            continue
        if t == "INSERT":
            p = pos_of(e)
            attrs = {}
            try:
                for a in e.attribs:
                    attrs[str(a.dxf.tag).upper()] = str(a.dxf.text).strip()
                    ap = pos_of(a) or p
                    texts.append({"layer": a.dxf.get("layer", lay), "text": str(a.dxf.text).strip(),
                                  "x": ap[0], "y": ap[1], "src": f"ATTRIB {a.dxf.tag}", "h": text_height(a)})
            except Exception:
                pass
            if p:
                inserts.append({"layer": lay, "name": e.dxf.name, "x": p[0], "y": p[1], "z": p[2], "attrs": attrs})
            continue
        if t in ("CIRCLE", "POINT"):
            p = pos_of(e)
            if p:
                # POINT has no radius attribute; ezdxf raises on dxf.get("radius") for it
                r = float(e.dxf.get("radius", 0) or 0) if t == "CIRCLE" else 0.0
                points.append({"layer": lay, "kind": t, "x": p[0], "y": p[1], "z": p[2], "r": r})
    return layers, lines, texts, inserts, points
