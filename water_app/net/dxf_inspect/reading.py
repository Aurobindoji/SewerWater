"""dxf_inspect: reading the drawing (DXF, or DWG through the ODA converter) and its entities' texts, points, lines."""
import os
import sys
import math


# ---------------------------------------------------------------- reading
def load(path):
    try:
        from ezdxf import recover
    except ImportError:
        sys.exit("ezdxf is not installed: pip install ezdxf")
    ext = os.path.splitext(path)[1].lower()
    if not os.path.isfile(path):
        sys.exit(f"File not found: {path}")
    if ext == ".dwg":
        # sewer_app: a DWG is read through the free ODA File Converter (ezdxf odafc add-on) when it is installed
        from ezdxf.addons import odafc
        if not odafc.is_installed():
            sys.exit("This is a DWG and the ODA File Converter (free, opendesign.com) is not installed. Install it, or "
                     "save the drawing as DXF (AutoCAD: SAVEAS -> DXF) and run on the .dxf.")
        doc = odafc.readfile(path)
        return doc, doc.audit()
    doc, auditor = recover.readfile(path)
    return doc, auditor


def text_of(e):
    t = e.dxftype()
    try:
        if t == "TEXT":
            return e.dxf.text
        if t == "MTEXT":
            return e.plain_text()
        if t in ("ATTRIB", "ATTDEF"):
            return e.dxf.text
    except Exception:
        return ""
    return ""


def text_height(e):
    """Text height (drawing units) of a TEXT / ATTRIB / MTEXT; 0.0 when not readable."""
    try:
        h = e.dxf.get("char_height") if e.dxftype() == "MTEXT" else e.dxf.get("height")
        return float(h or 0.0)
    except Exception:
        return 0.0


def pos_of(e):
    """Anchor point of an entity. For TEXT / ATTRIB that is NOT left-aligned (halign or valign set) the
    anchor is the alignment point - the insert point is then the left end of the text, which lies one
    text-width away from where the text was placed (seen in oakdale.dxf: labels about 10 m to the left)."""
    if e.dxftype() in ("TEXT", "ATTRIB", "ATTDEF"):
        try:
            h, v = int(e.dxf.get("halign", 0) or 0), int(e.dxf.get("valign", 0) or 0)
            ap = e.dxf.get("align_point")
            if (h or v) and ap is not None:
                return (float(ap[0]), float(ap[1]), float(ap[2]) if len(ap) > 2 else 0.0)
        except Exception:
            pass
    for k in ("insert", "location", "center", "align_point"):
        try:
            p = e.dxf.get(k)
            if p is not None:
                return (float(p[0]), float(p[1]), float(p[2]) if len(p) > 2 else 0.0)
        except Exception:
            pass
    return None


def polyline_points(e):
    """Vertices (x, y, z) of LINE / LWPOLYLINE / POLYLINE; None for other types. Arcs (bulges) are
    taken as straight chords - enough for connectivity and length checks."""
    t = e.dxftype()
    try:
        if t == "LINE":
            s, en = e.dxf.start, e.dxf.end
            return [(s[0], s[1], s[2]), (en[0], en[1], en[2])], False
        if t == "LWPOLYLINE":
            z = float(e.dxf.get("elevation", 0.0) or 0.0)
            pts = [(p[0], p[1], z) for p in e.get_points("xy")]
            return pts, bool(e.closed)
        if t == "POLYLINE":
            pts = [(v.dxf.location[0], v.dxf.location[1], v.dxf.location[2]) for v in e.vertices]
            return pts, bool(e.is_closed)
    except Exception:
        return None
    return None


def seg_len(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])
