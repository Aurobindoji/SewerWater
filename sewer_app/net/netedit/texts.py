"""netedit: the network as JSON for the page and the drawing's texts near the map's view."""
import json
import os
from .common import _TEXTS
from .coords import converters


def _f(v):
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def _tuples(net):
    """The working network (JSON lists) in the form network.py / repair.py use (xy and vertices as tuples)."""
    return {"nodes": {n: dict(v, xy=tuple(v["xy"]) if v.get("xy") else None) for n, v in net["nodes"].items()},
            "conduits": [dict(k, vertices=[tuple(p) for p in k.get("vertices") or []]) for k in net["conduits"]],
            "outfalls": list(net["outfalls"])}


def _net_json(net):
    return {"nodes": {n: {"xy": list(v["xy"]) if v.get("xy") else None, "ground": v.get("ground"),
                          "gl_source": v.get("gl_source") or "",
                          **({"invert_drawing": v["invert_drawing"]} if v.get("invert_drawing") is not None else {})}
                      for n, v in net["nodes"].items()},
            "conduits": [{"label": k["label"], "start_node": k["start_node"], "stop_node": k["stop_node"],
                          "length_m": k["length_m"], "vertices": [list(p) for p in k.get("vertices") or []],
                          **({"id": k["id"]} if "id" in k else {})} for k in net["conduits"]],
            "outfalls": list(net.get("outfalls") or [])}


def _texts(st):
    stem = st["stem"]
    if stem not in _TEXTS:
        p = os.path.join(st["_root"], stem, f"{stem}_dxf_texts.json")
        with open(p, encoding="utf-8") as fh:
            _TEXTS[stem] = json.load(fh)
    return _TEXTS[stem]


def texts_in(st, bbox, limit=3000):
    """Texts of the drawing inside bbox (south, west, north, east in lat / lon): [[lat, lon, text, layer]]."""
    stem = st["stem"]
    _texts(st)
    s, w, n, e = bbox
    to_xy = converters(st)[1]
    (x0, y0), (x1, y1) = to_xy([[s, w], [n, e]])
    xa, xb, ya, yb = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
    sel = [t for t in _TEXTS[stem] if xa <= t[0] <= xb and ya <= t[1] <= yb][:limit]
    ll = converters(st)[0]([[t[0], t[1]] for t in sel])
    return [[p[0], p[1], t[2], t[3]] for p, t in zip(ll, sel)]
