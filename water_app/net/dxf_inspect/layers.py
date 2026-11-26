"""dxf_inspect: the drawing's inventory - layers split by colour, its scale, which lines carry pipe labels."""
import re
import statistics
import collections
from .reading import polyline_points, pos_of, seg_len, text_height, text_of
from .spatial import Grid, point_seg_dist


# ---------------------------------------------------------------- analysis
SPLIT_SHARE = 0.8          # a layer with this share of a drawing's lines and texts ...


SPLIT_COLOURS = 3          # ... in at least this many colours is split by colour (a drawing converted from a PDF)


LENGTH_TEXT = re.compile(r"^\s*(?:L\s*[-=:]?\s*)?(\d+(?:\.\d+)?)\s*m\s*$", re.I)


SCALE_AGREE = 0.5          # the drawing is scaled when this share of its length texts give one ratio (within 10 %)


def _colour(e):
    """The entity's own colour number (ACI), None when it takes the layer's (BYLAYER 256, BYBLOCK 0)."""
    c = e.dxf.get("color", 256)
    return None if c in (0, 256) else int(c)


def split_layer(ents):
    """The layer to be split by colour, else None (17-Nov-2026: a drawing converted from a PDF has everything on
    layer 0 - pipes, roads, buildings told apart only by their colour): one layer holding SPLIT_SHARE of the drawing's
    lines and texts, in SPLIT_COLOURS or more colours (each at least 1 % of it)."""
    kinds = ("LINE", "LWPOLYLINE", "POLYLINE", "TEXT", "MTEXT")
    on = collections.Counter(e.dxf.get("layer", "0") for e in ents if e.dxftype() in kinds)
    total = sum(on.values())
    if not total:
        return None
    lay, n = on.most_common(1)[0]
    if n < max(200, SPLIT_SHARE * total):
        return None
    cols = collections.Counter(_colour(e) for e in ents if e.dxftype() in kinds and e.dxf.get("layer", "0") == lay)
    big = [c for c, k in cols.items() if c is not None and k >= max(10, 0.01 * n)]
    return lay if len(big) >= SPLIT_COLOURS else None


def drawing_scale(lines, texts):
    """(metres per drawing unit, length texts agreeing, length texts read) when the drawing is not in metres, else
    None (17-Nov-2026: a drawing converted from a PDF is at paper size - a real one: 1 unit = 1.79 m). Each length text
    ("L-5m", "12.3 m") is set against the nearest line longer than two text heights; when SCALE_AGREE of them give one
    ratio (within 10 %) and it is not 1 (more than 10 % off), that ratio is the scale."""
    lt = [(t, float(m.group(1))) for t in texts for m in [LENGTH_TEXT.match(t["text"] or "")] if m and float(m.group(1)) > 0]
    if len(lt) < 20:
        return None
    hs = sorted(t.get("h") or 0.0 for t, _ in lt)
    h = hs[len(hs) // 2] or 1.0
    cell = 2 * h
    g = Grid(cell)
    for k, ln in enumerate(lines):
        if ln["len"] < 2 * h:
            continue
        for a, b in zip(ln["pts"], ln["pts"][1:]):
            n = max(1, int(seg_len(a, b) / cell))
            for i in range(n + 1):
                g.add(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n, (k, a, b))
    rat = []
    for t, v in lt:
        best = None
        for _, _, _, (k, a, b) in g.near(t["x"], t["y"], 4 * h):
            d = point_seg_dist((t["x"], t["y"]), a, b)[0]
            if best is None or d < best[0]:
                best = (d, k)
        if best:
            rat.append(v / lines[best[1]]["len"])
    if len(rat) < 20:
        return None
    med = statistics.median(rat)
    agree = sum(1 for r in rat if abs(r / med - 1) <= 0.1)
    if agree < SCALE_AGREE * len(rat) or abs(med - 1) <= 0.1:
        return None
    return med, agree, len(lt)


PIPE_LABEL = re.compile(r"^\s*(?:P|PIPE|L|D|DIA)\s*[-_ /]\s*\d", re.I)     # P-142, L-5m, D-110mm


LABELLED_SHARE = 0.4       # a colour whose lines carry pipe labels this often is a pipe colour as a whole


def pipe_label_hits(lines, texts):
    """{index of a line: pipe labels next to it} - each pipe label (P-142, L-5m, D-110mm) given to the nearest line
    longer than two text heights, within four (17-Nov-2026: a drawing from a PDF, where only the labels say which
    lines are pipes)."""
    lab = [t for t in texts if PIPE_LABEL.match(t["text"] or "")]
    if not lab:
        return {}
    hs = sorted(t.get("h") or 0.0 for t in lab)
    h = hs[len(hs) // 2] or 1.0
    g = Grid(2 * h)
    for k, ln in enumerate(lines):
        if ln["len"] < 2 * h:
            continue
        for a, b in zip(ln["pts"], ln["pts"][1:]):
            n = max(1, int(seg_len(a, b) / (2 * h)))
            for i in range(n + 1):
                g.add(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n, (k, a, b))
    hit = collections.Counter()
    for t in lab:
        best = None
        for _, _, _, (k, a, b) in g.near(t["x"], t["y"], 4 * h):
            d = point_seg_dist((t["x"], t["y"]), a, b)[0]
            if best is None or d < best[0]:
                best = (d, k)
        if best:
            hit[best[1]] += 1
    return hit


def _labelled_apart(layers, lines, texts, split):
    """In a drawing split by colour: the labelled lines of a colour that also holds much else (black: buildings,
    roads and some pipes) moved to a layer of their own "<layer> labelled" - the pipe colours keep all their lines
    (a short pipe may have no label). Returns the new layers' names."""
    hit = pipe_label_hits(lines, texts)
    if not hit:
        return []
    hs = sorted(t.get("h") or 0.0 for t in texts if PIPE_LABEL.match(t["text"] or ""))
    h = hs[len(hs) // 2] or 1.0
    n_long = collections.Counter(ln["layer"] for ln in lines if ln["len"] >= 2 * h)
    n_hit = collections.Counter(lines[k]["layer"] for k in hit)
    mixed = {lay for lay, n in n_hit.items() if lay.startswith(f"{split} colour ") and n >= 5
             and n < LABELLED_SHARE * n_long[lay]}
    made = set()
    for k in hit:
        ln = lines[k]
        if ln["layer"] in mixed:
            old, ln["layer"] = ln["layer"], f"{ln['layer']} labelled"
            L, N = layers[old], layers[ln["layer"]]
            L["types"]["LWPOLYLINE" if len(ln["pts"]) > 2 else "LINE"] -= 1
            N["types"]["LWPOLYLINE" if len(ln["pts"]) > 2 else "LINE"] += 1
            L["length"] -= ln["len"]
            N["length"] += ln["len"]
            made.add(ln["layer"])
    return sorted(made)


def _scale_all(s, layers, lines, texts, inserts, points):
    for ln in lines:
        ln["pts"] = [(p[0] * s, p[1] * s, p[2]) for p in ln["pts"]]
        ln["len"] *= s
    for t in texts:
        t["x"], t["y"], t["h"] = t["x"] * s, t["y"] * s, (t.get("h") or 0.0) * s
    for b in inserts:
        b["x"], b["y"] = b["x"] * s, b["y"] * s
    for p in points:
        p["x"], p["y"], p["r"] = p["x"] * s, p["y"] * s, p["r"] * s
    for L in layers.values():
        L["length"] *= s


def inventory(msp):
    """(layers, lines, texts, inserts, points) of the drawing. A drawing with everything on one layer in many colours
    gets a layer per colour ("0 colour 82" - split_layer); a drawing not in metres is scaled to metres when its length
    texts say how (drawing_scale); in a split drawing the labelled pipes of a mixed colour get a layer of their own
    (_labelled_apart). What was done: inventory.info {"split": layer or None, "scale": (s, agree, n) or None,
    "labelled": [layers made]}."""
    layers = collections.defaultdict(lambda: {"types": collections.Counter(), "length": 0.0, "z": set(),
                                              "color": collections.Counter()})
    lines, texts, inserts, points = [], [], [], []
    ents = list(msp)
    split = split_layer(ents)
    for e in ents:
        t = e.dxftype()
        lay = e.dxf.get("layer", "0")
        if lay == split and _colour(e) is not None:
            lay = f"{lay} colour {_colour(e)}"
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
    scale = drawing_scale(lines, texts)
    if scale:
        _scale_all(scale[0], layers, lines, texts, inserts, points)
    apart = _labelled_apart(layers, lines, texts, split) if split else []
    inventory.info = {"split": split, "scale": scale, "labelled": apart}
    return layers, lines, texts, inserts, points


inventory.info = {"split": None, "scale": None, "labelled": []}
