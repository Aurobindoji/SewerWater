"""netedit: the network as JSON for the page and the drawing's texts near the map's view."""
import json
import math
import os
from .common import SUGGEST_RADIUS_M, _TEXTS
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
                          "gl_source": v.get("gl_source") or "", **({"old": v["old"]} if v.get("old") else {})}
                      for n, v in net["nodes"].items()},
            "conduits": [{"label": k["label"], "start_node": k["start_node"], "stop_node": k["stop_node"],
                          "length_m": k["length_m"], "vertices": [list(p) for p in k.get("vertices") or []],
                          **({"id": k["id"]} if "id" in k else {}), **({"no_conn": True} if k.get("no_conn") else {}),
                          **({"auto_join": True} if k.get("auto_join") else {}),
                          **({"old": k["old"]} if k.get("old") else {})}
                         for k in net["conduits"]],
            "outfalls": list(net.get("outfalls") or [])}


def _texts(st):
    stem = st["stem"]
    if stem not in _TEXTS:
        p = os.path.join(st["_root"], stem, f"{stem}_dxf_texts.json")
        with open(p, encoding="utf-8") as fh:
            _TEXTS[stem] = json.load(fh)
    return _TEXTS[stem]


def _shown_by_page(t, near):
    """A drawing text the page writes itself next to its junction (user request 21-Oct-2026: GL not twice): the
    junction's own name, or a number equal to its GL (within 5 mm) - near = [(label, (x, y), GL)] around the text."""
    txt = str(t[2]).strip()
    try:
        num = float(txt)
    except ValueError:
        num = None
    for lab, (x, y), gl in near:
        if math.hypot(t[0] - x, t[1] - y) > SUGGEST_RADIUS_M:
            continue
        if txt.upper() == str(lab).upper() or (num is not None and gl is not None and abs(num - gl) < 0.005):
            return True
    return False


def texts_in(st, bbox, limit=3000, hide_shown=False):
    """Texts of the drawing inside bbox (south, west, north, east in lat / lon): [[lat, lon, text, layer]].
    hide_shown: not the names / GLs the page already writes next to the junctions (_shown_by_page)."""
    stem = st["stem"]
    _texts(st)
    s, w, n, e = bbox
    to_xy = converters(st)[1]
    (x0, y0), (x1, y1) = to_xy([[s, w], [n, e]])
    xa, xb, ya, yb = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
    sel = [t for t in _TEXTS[stem] if xa <= t[0] <= xb and ya <= t[1] <= yb]
    if hide_shown:
        r = SUGGEST_RADIUS_M
        near = [(lab, v["xy"], v.get("ground")) for lab, v in st["net"]["nodes"].items() if v.get("xy")
                and xa - r <= v["xy"][0] <= xb + r and ya - r <= v["xy"][1] <= yb + r]
        sel = [t for t in sel if not _shown_by_page(t, near)]
    sel = sel[:limit]
    ll = converters(st)[0]([[t[0], t[1]] for t in sel])
    return [[p[0], p[1], t[2], t[3]] for p, t in zip(ll, sel)]
