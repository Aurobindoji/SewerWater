"""WATER MODULE COPY of sewer_app/dxf_inspect.py (isolation of sewer and water, user request 21-Oct-2026): changes here do not\nreach the sewer module, nor the reverse. Water rules are written in directly (a water main network keeps its loops\nand has no outfalls)."""
"""
dxf_inspect.py - reading a CAD drawing (DXF / DWG) for the water network import (dxf_extract, netedit): entities,
text kinds, joining lines into a network, its checks, ground levels per junction.
The command-line check of a drawing (console + Excel report) is in the sewer copy only - python -m
sewer_app.dxf_inspect (17-Nov-2026: the water copy of it was not reachable from the water app and was removed).
A DWG is read through the free ODA File Converter when it is installed; nothing is written into the drawing.
"""

import os
import re
import statistics
import sys
import math
import collections


PIPE_NAME = re.compile(r"pipe|sewer|\bsw\b|^sw|main|line|nala|drain", re.I)
# 16-Nov-2026 (a survey drawing): its power line "Ex-Utility-HT Line" and the road "CENTER LINE" were taken for pipes
NOT_PIPE_NAME = re.compile(r"rail|road|boundary|electric|canal|pond|text|contour|building|plot|wall|"
                           r"tree|school|temple|well|site|hatch|grid|frame|title|dim|utility|\bht\b|\blt\b|power|"
                           r"telephone|cable|\bofc\b|cent(er|re)\s*line", re.I)
Z_TEXT_AGREE_M = 1.0     # WATER: Z of the lines is the ground only if within this of the GL texts (median)
LEVEL_TAG = re.compile(r"^(GL|G\.L|RL|R\.L|GROUND|ELEV|ELEVATION|LEVEL|NGL|EGL|LVL|Z)\b", re.I)
NUM = re.compile(r"[-+]?\d+(?:\.\d+)?")
# a name: MH-12, J-7A, and in two parts MH-3-441 (zone 3, manhole 441 - 16-Nov-2026, a key plan's every name)
ID_RE = re.compile(r"^\s*([A-Za-z]{1,8})\s*[-_ /]\s*(\d+(?:-\d+)?[A-Za-z]?)\s*$")
# a level, bare or with its tag - E-77.31 m and EL-77.87 m too (16-Nov-2026: two index plans and a key plan write
# the ground level so; it was not read at all)
DEC_RE = re.compile(r"^\s*(?:(GL|G\.L\.?|RL|R\.L\.?|NGL|EGL|EL|ELEV|LEVEL|TBM|E)\s*[:=.\-]?\s*)?(\d{1,4}\.\d{1,4})\s*(m|M)?\s*$")
LEVEL_SPREAD_M = 50.0    # the ground levels of one drawing lie within this (5 % to 95 %): pipe lengths do not
LEVEL_FAR_M = 25.0       # a level this far from the drawing's middle level is a typing error (777.08 for 77.708)
IL_RE = re.compile(r"^\s*(IL|I\.L\.?|INV|INVERT)\s*[:=.\-]?\s*(\d{1,4}(?:\.\d{1,3})?)\s*(m|M)?\s*$", re.I)
DIA_RE = re.compile(r"^\s*(?:dia\.?\s*|%%c\s*|\u00d8\s*)?([\d,]+(?:\.\d+)?)\s*mm\s*(?:dia\.?)?\s*$", re.I)
SLOPE_RE = re.compile(r"^\s*([\d,]+(?:\.\d+)?)\s*1\s*/\s*S\s*$|^\s*1\s*(?:in|:)\s*([\d,]+(?:\.\d+)?)\s*$", re.I)


def classify(text):
    """Kinds found in a (multi-line) text: list of (kind, value) with kind in
    id / level / invert / dia / slope_1in. 'level' = a decimal number (1-3 decimals, optional m)."""
    out = []
    for ln in re.split(r"[\r\n]+|\\P", text or ""):
        ln = ln.strip()
        if not ln:
            continue
        m = ID_RE.match(ln)
        if m:
            out.append(("id", f"{m.group(1).upper()}-{m.group(2)}"))
            continue
        m = IL_RE.match(ln)
        if m:
            out.append(("invert", float(m.group(2))))
            continue
        m = DEC_RE.match(ln)
        if m:
            out.append(("level", float(m.group(2))))
            continue
        m = DIA_RE.match(ln)
        if m:
            out.append(("dia", float(m.group(1).replace(",", ""))))
            continue
        m = SLOPE_RE.match(ln)
        if m:
            out.append(("slope_1in", float((m.group(1) or m.group(2)).replace(",", ""))))
    return out


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


# ---------------------------------------------------------------- spatial helpers
class Grid:
    """Simple hash grid for nearest-point queries."""
    def __init__(self, cell):
        self.cell, self.d = max(cell, 1e-6), collections.defaultdict(list)

    def key(self, x, y):
        return (int(math.floor(x / self.cell)), int(math.floor(y / self.cell)))

    def add(self, x, y, item):
        self.d[self.key(x, y)].append((x, y, item))

    def near(self, x, y, r):
        kx, ky = self.key(x, y)
        n = int(math.ceil(r / self.cell))
        out = []
        for i in range(kx - n, kx + n + 1):
            for j in range(ky - n, ky + n + 1):
                for px, py, it in self.d.get((i, j), ()):
                    dd = math.hypot(px - x, py - y)
                    if dd <= r:
                        out.append((dd, px, py, it))
        out.sort(key=lambda t: t[0])
        return out


def point_seg_dist(p, a, b):
    ax, ay, bx, by = a[0], a[1], b[0], b[1]
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(p[0] - ax, p[1] - ay), 0.0
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L2))
    return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy)), t


def seg_cross(a, b, c, d):
    """Proper crossing of segments ab and cd (not touching at the ends)."""
    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    o1, o2, o3, o4 = orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)
    return (o1 * o2 < 0) and (o3 * o4 < 0)


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


def parse_number(s):
    """(prefix, number) from a label such as 'GL 82.350', 'IL=79.6', '82.350'; (None, None) if none."""
    s = (s or "").strip()
    k = classify(s)
    for kind, v in k:
        if kind in ("level", "invert", "dia", "slope_1in"):
            return kind.upper(), v
    if k and all(kind == "id" for kind, _ in k):
        return None, None
    m = NUM.search(s)
    if not m:
        return None, None
    try:
        v = float(m.group(0))
    except ValueError:
        return None, None
    prefix = s[:m.start()].strip(" :=-").upper()
    return prefix, v


def is_tagged_level(text):
    """True when the text is a level WITH its tag (GL-77.81 m, EL-77.87 m, E-79.70m), not a bare number."""
    m = DEC_RE.match((text or "").strip())
    return bool(m and m.group(1))


def level_texts_of_layer(texts):
    """The texts of ONE layer that are its levels: when the layer writes its levels with a tag (GL / EL / E ...), only
    those - the bare numbers beside them are depths, lengths (16-Nov-2026: a key plan's node layer has EL-77.87 m, IL
    and the depth 1.20 m at every node). Returns [(text, value)]."""
    lv = [(t, v) for t in texts for kind, v in classify(t["text"]) if kind == "level"]
    tagged = [(t, v) for t, v in lv if is_tagged_level(t["text"])]
    return tagged if len(tagged) >= 5 and len(tagged) >= 0.2 * len(lv) else lv


def level_band(values):
    """(low, high) of the ground levels: the middle level +- LEVEL_FAR_M; a level outside it is a typing error."""
    vs = sorted(values)
    med = vs[len(vs) // 2] if vs else 0.0
    return med - LEVEL_FAR_M, med + LEVEL_FAR_M


def level_candidates(texts, min_n=5):
    """{layer: [(x, y, value), ...]} of level-like values (decimal numbers, 1-4 decimals; only the tagged ones when the
    layer tags its levels - level_texts_of_layer) per layer, kept only when at least 80 % of them lie within 15 m of
    the layer median, the median is above 10 (terrain levels, not pipe lengths or depths), 90 % of them lie within
    LEVEL_SPREAD_M (16-Nov-2026: pipe lengths 7 - 93 m on a pipe layer were taken for its GL) and, bare numbers, most
    are written to 2 decimals or more."""
    by_layer = collections.defaultdict(list)
    for t in texts:
        by_layer[t["layer"]].append(t)
    out = {}
    for lay, ts in by_layer.items():
        lv = level_texts_of_layer(ts)
        vals = [(t["x"], t["y"], v) for t, v in lv]
        if len(vals) < min_n:
            continue
        # bare numbers: a level is written to 2 - 3 decimals (77.338, 77.81), a length to one (26.8 m) - 16-Nov-2026,
        # the lengths left beside the pipes of a drawing without any GL were taken for its GL
        if not any(is_tagged_level(t["text"]) for t, _ in lv) and \
                sum(1 for t, _ in lv if re.search(r"\.\d{2,}", t["text"])) < 0.6 * len(lv):
            continue
        vs = sorted(v for _, _, v in vals)
        med = vs[len(vs) // 2]
        p5, p95 = vs[int(0.05 * (len(vs) - 1))], vs[int(round(0.95 * (len(vs) - 1)))]
        if med > 10 and sum(1 for v in vs if abs(v - med) <= 15) >= 0.8 * len(vs) and p95 - p5 <= LEVEL_SPREAD_M:
            out[lay] = vals
    return out


def optimal_pairs(pairs, unmatched_cost, max_cells=4_000_000):
    """Minimum-cost one-to-one matching of (cost, text k, node id) pairs, solved per connected group of candidates
    (scipy linear_sum_assignment); leaving a text unmatched costs unmatched_cost. Returns [(k, nid)]. A group too big
    for a dense matrix (more than max_cells) is matched greedily (shortest first)."""
    parent = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for _, k, nid in pairs:
        parent[find(("t", k))] = find(("n", nid))
    groups = collections.defaultdict(list)
    for pr in pairs:
        groups[find(("t", pr[1]))].append(pr)
    out = []
    try:
        import numpy as np
        from scipy.optimize import linear_sum_assignment
    except ImportError:
        np = None
    for grp in groups.values():
        ks = sorted({k for _, k, _ in grp})
        ns = sorted({n for _, _, n in grp}, key=str)
        if np is None or len(ks) * (len(ns) + len(ks)) > max_cells:
            used_k, used_n = set(), set()
            for d, k, nid in sorted(grp, key=lambda t: (t[0], t[1], str(t[2]))):
                if k not in used_k and nid not in used_n:
                    used_k.add(k)
                    used_n.add(nid)
                    out.append((k, nid))
            continue
        ki, ni = {k: i for i, k in enumerate(ks)}, {n: j for j, n in enumerate(ns)}
        BIG = 1e9
        C = np.full((len(ks), len(ns) + len(ks)), BIG)
        for d, k, nid in grp:
            C[ki[k], ni[nid]] = min(C[ki[k], ni[nid]], d)
        for i in range(len(ks)):
            C[i, len(ns) + i] = unmatched_cost                 # 'no partner' column of this text
        rows, cols = linear_sum_assignment(C)
        for r, c in zip(rows, cols):
            if c < len(ns) and C[r, c] < BIG:
                out.append((ks[r], ns[c]))
    return out


def match_to_nodes(nodes, items, radius, tight=1.5, prior=None):
    """One-to-one matching of texts to nodes. items = [(x, y, value)] or [(x, y, value, text height)].
    1. Placement offsets: CAD labels usually sit at one of a few fixed offsets from their symbol. They are
       learnt from texts whose nearest node is unambiguous (second nearest node more than 3x as far). When every
       text has a height, the offsets are learnt IN TEXT HEIGHTS (sewer_app, 12-Oct-2026): a smaller label sits
       proportionally closer (oakdale.dxf: 1.92 h for both 1.27 m and 0.89 m texts); else in metres (0.5 m grid).
       Every offset used by at least 3 % of those texts is kept (up to 8).
    2. Pass 1: each text, moved back by each learnt offset, is paired with the nodes within `tight` m;
       pairs sorted by distance and taken greedily (each text and each node once).
    3. Pass 2: texts and nodes still free are paired within `radius` m (raw or offset-corrected distance) by the
       minimum-cost one-to-one matching (optimal_pairs) - not greedily, so one wrong pair does not push the
       next text onto the wrong manhole. prior(text index, node id, pass-1 result) -> metres taken off the
       distance of a candidate (labels: the manhole numbering along the sewers, see labels_near_nodes).
       These matches are less certain and are reported as 'pass 2'.
    Returns ({node id: value}, info) with info['pass2'] = set of node ids matched in pass 2 and info['text_at'] =
    {node id: (text x, text y, text height or 1)}."""
    used = [n for n in nodes if n["deg"] > 0]
    g = Grid(max(radius, 1.0))
    for n in used:
        g.add(n["x"], n["y"], n["id"])
    hs = [float(it[3]) if len(it) > 3 and it[3] else 0.0 for it in items]
    norm = bool(items) and all(h > 0 for h in hs)
    unit = hs if norm else [1.0] * len(items)
    cell = 0.25 if norm else 0.5
    samples = []
    for k, it in enumerate(items):
        x, y = it[0], it[1]
        h = g.near(x, y, radius)
        if h and (len(h) == 1 or h[1][0] > 3 * max(h[0][0], 1e-6)):
            samples.append(((x - h[0][1]) / unit[k], (y - h[0][2]) / unit[k]))
    offsets = []
    if len(samples) >= 20:
        cl = collections.Counter((round(dx / cell) * cell, round(dy / cell) * cell) for dx, dy in samples)
        for (cx, cy), c in cl.most_common(8):
            if c < 0.03 * len(samples):
                break
            near = [(dx, dy) for dx, dy in samples if abs(dx - cx) <= cell / 2 and abs(dy - cy) <= cell / 2]
            offsets.append((float(sorted(p[0] for p in near)[len(near) // 2]),
                            float(sorted(p[1] for p in near)[len(near) // 2]), c))
    shifts = [(ox, oy) for ox, oy, _ in offsets] or [(0.0, 0.0)]

    out, used_t, text_at = {}, set(), {}

    def take(k, nid):
        out[nid] = items[k][2]
        used_t.add(k)
        text_at[nid] = (items[k][0], items[k][1], unit[k])

    pairs = []
    for k, it in enumerate(items):
        x, y, u = it[0], it[1], unit[k]
        best = {}
        for ox, oy in shifts:
            for d, _, _, nid in g.near(x - ox * u, y - oy * u, tight):
                if d < best.get(nid, 1e9):
                    best[nid] = d
        pairs += [(d, k, nid) for nid, d in best.items()]
    pairs.sort(key=lambda t: (t[0], t[1], str(t[2])))
    for d, k, nid in pairs:
        if k not in used_t and nid not in out:
            take(k, nid)
    n1 = len(out)
    pairs = []
    for k, it in enumerate(items):
        if k in used_t:
            continue
        x, y, u = it[0], it[1], unit[k]
        best = {}
        for ox, oy in shifts + [(0.0, 0.0)]:
            for d, _, _, nid in g.near(x - ox * u, y - oy * u, radius):
                if nid not in out and d < best.get(nid, 1e9):
                    best[nid] = d
        pairs += [(d - (prior(k, nid, out) if prior else 0.0), k, nid) for nid, d in best.items()]
    before = set(out)
    for k, nid in optimal_pairs(pairs, unmatched_cost=radius * 1.01):
        take(k, nid)
    pass2 = set(out) - before
    # where do the texts that are still unused lie, relative to their nearest node?
    left = collections.Counter()
    for k, it in enumerate(items):
        if k in used_t:
            continue
        x, y = it[0], it[1]
        h = g.near(x, y, 3 * radius)
        if h:
            left[(round((x - h[0][1]) / 2) * 2, round((y - h[0][2]) / 2) * 2)] += 1
        else:
            left["no node within %g m" % (3 * radius)] += 1
    return out, {"offsets": [(round(a, 2), round(b, 2), c) for a, b, c in offsets], "offset_samples": len(samples),
                 "offset_unit": "text height" if norm else "m",
                 "texts": len(items), "matched": len(out), "pass1": n1, "pass2_n": len(pass2), "pass2": pass2,
                 "texts_unused": len(items) - len(used_t), "unused_offsets": left.most_common(6),
                 "offset": (round(shifts[0][0], 3), round(shifts[0][1], 3)), "text_at": text_at}


NUMBER_BONUS_M = {1: 3.0, 2: 2.0}      # pass-2 label prior: number differs by 1 / 2 from a labelled neighbour


def labels_near_nodes(nodes, texts, radius, layers=None, adj=None):
    """Nearest ID text (e.g. MH-1173) within radius of each used node; only texts on `layers` (the manhole
    symbol layer) when given, so that a pipe label next to a node is not taken as the manhole name.
    adj = {node id: set of node ids joined by a pipe}: in pass 2 a label whose number differs by 1 or 2 from the
    pass-1 label of a neighbour along the sewer counts NUMBER_BONUS_M closer (sewer_app, 12-Oct-2026 - on
    oakdale.dxf 74 % of the pipes with both ends labelled in pass 1 join numbers 1 or 2 apart)."""
    items = []
    for t in texts:
        if layers and t["layer"] not in layers:
            continue
        for kind, v in classify(t["text"]):
            if kind == "id":
                items.append((t["x"], t["y"], v, t.get("h") or 0.0))
    prior = None
    if adj:
        def num(v):
            m_ = re.search(r"(\d+)$", str(v))
            return int(m_.group(1)) if m_ else None
        nums = [num(it[2]) for it in items]

        def prior(k, nid, out):
            a = nums[k]
            if a is None:
                return 0.0
            best = 0.0
            for nb in adj.get(nid, ()):
                b = num(out[nb]) if nb in out else None
                if b is not None:
                    best = max(best, NUMBER_BONUS_M.get(abs(a - b), 0.0))
            return best
    m, info = match_to_nodes(nodes, items, radius, prior=prior)
    labels_near_nodes.info = info
    return {n["id"]: m.get(n["id"]) for n in nodes if n["deg"] > 0}


def build_network(lines, tol):
    """Join line ends within tol -> nodes; each polyline = one edge between its end nodes; interior
    vertices kept for T-joint / crossing checks."""
    grid, nodes = Grid(max(tol, 0.01) * 2), []

    def node_at(x, y, z):
        hit = grid.near(x, y, tol)
        if hit:
            return hit[0][3]
        nid = len(nodes)
        nodes.append({"id": nid, "x": x, "y": y, "z": [z], "deg": 0, "edges": []})
        grid.add(x, y, nid)
        return nid

    edges = []
    for ln in lines:
        p = ln["pts"]
        if ln["closed"]:
            continue
        a = node_at(p[0][0], p[0][1], p[0][2])
        b = node_at(p[-1][0], p[-1][1], p[-1][2])
        nodes[b]["z"].append(p[-1][2])
        e = {"id": len(edges), "a": a, "b": b, "len": ln["len"], "pts": p, "layer": ln["layer"],
             "handle": ln["handle"]}
        edges.append(e)
        for n in (a, b):
            nodes[n]["deg"] += 1
            nodes[n]["edges"].append(e["id"])
    return nodes, edges, grid


def components(nodes, edges):
    parent = list(range(len(nodes)))

    def f(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for e in edges:
        ra, rb = f(e["a"]), f(e["b"])
        if ra != rb:
            parent[ra] = rb
    comp = collections.Counter(f(n["id"]) for n in nodes if n["deg"] > 0)
    return comp, f


def network_checks(nodes, edges, tol, gap_factor=10.0, spacing=30.0):
    comp, find = components(nodes, edges)
    used = [n for n in nodes if n["deg"] > 0]
    loops = len([e for e in edges if e["a"] != e["b"]]) - len(used) + len(comp)
    self_loops = sum(1 for e in edges if e["a"] == e["b"])
    dead = [n for n in used if n["deg"] == 1]
    # near-miss gaps: dead ends that almost touch another node (tol < d <= gap_factor*tol) in another part
    g = Grid(tol * gap_factor)
    for n in used:
        g.add(n["x"], n["y"], n["id"])
    gaps, seen_pairs = [], set()
    for n in dead:
        for dd, _, _, other in g.near(n["x"], n["y"], tol * gap_factor):
            if other != n["id"] and dd > tol and find(other) != find(n["id"]):
                pair = frozenset((n["id"], other))
                if pair not in seen_pairs:            # one gap seen from both ends counts once
                    seen_pairs.add(pair)
                    gaps.append((n["id"], other, dd))
                break
    # T-joints: a dead end lying on the interior of another edge (no node there)
    sg = Grid(25.0)
    for e in edges:
        p = e["pts"]
        for i in range(len(p) - 1):
            mx, my = (p[i][0] + p[i + 1][0]) / 2, (p[i][1] + p[i + 1][1]) / 2
            sg.add(mx, my, (e["id"], i))
    tjoints = []
    for n in dead:
        best = None
        for _, _, _, (eid, i) in sg.near(n["x"], n["y"], 25.0 + 1e6 * 0):
            e = edges[eid]
            if n["id"] in (e["a"], e["b"]):
                continue
            a, b = e["pts"][i], e["pts"][i + 1]
            if seg_len(a, b) > 50:      # long segments: check directly below
                continue
            d, t = point_seg_dist((n["x"], n["y"]), a, b)
            if d <= tol and 0.0 < t < 1.0:
                best = (n["id"], e["id"], d)
                break
        if best is None:
            for e in edges:
                if n["id"] in (e["a"], e["b"]):
                    continue
                p = e["pts"]
                for i in range(len(p) - 1):
                    if seg_len(p[i], p[i + 1]) <= 50:
                        continue
                    d, t = point_seg_dist((n["x"], n["y"]), p[i], p[i + 1])
                    if d <= tol and 0.0 < t < 1.0:
                        best = (n["id"], e["id"], d)
                        break
                if best:
                    break
        if best:
            tjoints.append(best)
    # crossings without a node (same set of pipe layers)
    crossings = 0
    cg = Grid(50.0)
    segs = []
    for e in edges:
        p = e["pts"]
        for i in range(len(p) - 1):
            segs.append((e["id"], p[i], p[i + 1]))
    if len(segs) <= 60000:
        for k, (eid, a, b) in enumerate(segs):
            cg.add((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, k)
        seen = set()
        for k, (eid, a, b) in enumerate(segs):
            r = seg_len(a, b) / 2 + 50
            for _, _, _, j in cg.near((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, r):
                if j <= k or (k, j) in seen:
                    continue
                seen.add((k, j))
                e2, c, d = segs[j]
                if e2 == eid:
                    continue
                if seg_cross(a, b, c, d):
                    crossings += 1
    else:
        crossings = None
    long_segs = []
    for e in edges:
        # straight run between vertices longer than the spacing: a manhole is needed in between anyway
        if e["len"] > spacing + 0.5:
            long_segs.append(e["id"])
    return {"parts": len(comp), "part_sizes": sorted(comp.values(), reverse=True)[:10], "loops": max(loops, 0),
            "self_loops": self_loops, "nodes": len(used), "edges": len(edges), "dead_ends": len(dead),
            "junctions": sum(1 for n in used if n["deg"] >= 3), "gaps": gaps, "tjoints": tjoints,
            "crossings": crossings, "long": long_segs,
            "length": sum(e["len"] for e in edges)}


def pair_with_labels(items, anchors, pass2_labels):
    """GL texts that belong to a manhole's LABEL text (sewer_app, 12-Oct-2026): in many drawings the level is written
    at a fixed offset from the label (oakdale.dxf: 1.5 x 1.5 m from a 1.27 m label, 1.0 x 1.0 m from a 0.89 m one -
    the same 1.18 label heights). The offset is learnt in label heights from labels with one GL text clearly
    nearest; then every labelled manhole takes the GL text at that offset (within 0.3 label heights), one to one.
    anchors = {node: (label x, label y, label height)}. Returns ({node: value}, {node: item index}, info)."""
    if not items or not anchors:
        return {}, {}, {}
    gi = Grid(4.0)
    for k, it in enumerate(items):
        gi.add(it[0], it[1], k)
    samples = []
    for nid, (lx, ly, u) in anchors.items():
        if nid in pass2_labels:
            continue
        h = gi.near(lx, ly, 4.0 * u)
        if h and (len(h) == 1 or h[1][0] > 2 * max(h[0][0], 1e-6)):
            samples.append(((h[0][1] - lx) / u, (h[0][2] - ly) / u))
    offs = []
    if len(samples) >= 20:
        cl = collections.Counter((round(dx / 0.25) * 0.25, round(dy / 0.25) * 0.25) for dx, dy in samples)
        for (cx, cy), c in cl.most_common(4):
            if c < 0.05 * len(samples):
                break
            near = [(dx, dy) for dx, dy in samples if abs(dx - cx) <= 0.125 and abs(dy - cy) <= 0.125]
            offs.append((sorted(p[0] for p in near)[len(near) // 2], sorted(p[1] for p in near)[len(near) // 2], c))
    if not offs:
        return {}, {}, {"pair_offsets": [], "pair_samples": len(samples)}
    pairs = []
    for nid, (lx, ly, u) in anchors.items():
        for ox, oy, _ in offs:
            for d, _, _, k in gi.near(lx + ox * u, ly + oy * u, 0.3 * u):
                pairs.append((d / u, k, nid))
    pairs.sort(key=lambda t: (t[0], t[1], str(t[2])))
    got, idx, used_k = {}, {}, set()
    for d, k, nid in pairs:
        if nid not in got and k not in used_k:
            got[nid], idx[nid] = items[k][2], k
            used_k.add(k)
    return got, idx, {"pair_offsets": [(round(a, 2), round(b, 2), c) for a, b, c in offs], "pair_samples": len(samples)}


def node_levels(nodes, texts, inserts, level_layers, radius, anchors=None, pass2_labels=(), z_mode="auto", points=()):
    """Ground level per node from (in this order - water, 22-Oct-2026): block attributes, the GL text paired with the
    manhole's label (anchors - see pair_with_labels) or the nearest numeric text, the Z of the nearest survey point
    (POINT, 16-Nov-2026), Z of line ends (only when Z agrees with the GL texts). z_mode (the user's choice on the page,
    22-Oct-2026): "auto" as said; "first" - Z of the line ends before all else, whether it agrees or not (the texts
    where there is no Z); "off" - Z not at all.
    16-Nov-2026 (real drawings): a level far from the drawing's others (level_band - 777.08 among 76s) is not used but
    listed (info "far"); the Z of the lines is the ground only when it has many values (one value at every line end
    is the elevation the drawing was made at, not the ground)."""
    used = [n for n in nodes if n["deg"] > 0]
    res = {"z": 0, "attr": 0, "text": 0, "point": 0, "none": 0}
    # Z
    zs = [z for n in used for z in n["z"]]
    z_useful = zs and (max(zs) - min(zs) > 0.01) and sum(1 for z in zs if abs(z) > 0.001) > 0.5 * len(zs)
    z_few = None
    nz = len({round(z, 2) for z in zs if abs(z) > 0.001})
    if z_useful and nz < max(5, 0.05 * len(used)):
        z_useful = False                         # a few values only: the lines' elevations, not the ground
        z_few = (f"Z of the lines not used: only {nz} different value(s) at {len(used)} line ends - the elevation the "
                 f"lines were drawn at, not the ground")
    # attributes
    ag = Grid(max(radius, 1.0))
    for i, b in enumerate(inserts):
        for tag, val in b["attrs"].items():
            if LEVEL_TAG.match(tag):
                _, v = parse_number(val)
                if v is not None:
                    ag.add(b["x"], b["y"], v)
                    break
    by_layer = collections.defaultdict(list)
    for t in texts:
        if t["layer"] in level_layers:
            by_layer[t["layer"]].append(t)
    items = [(t["x"], t["y"], v, t.get("h") or 0.0) for ts in by_layer.values() for t, v in level_texts_of_layer(ts)]
    # survey points with their height (POINT entities; 16-Nov-2026: an index plan has 3,390 of them and no GL text)
    pts = [(p["x"], p["y"], p["z"]) for p in points if p.get("kind") == "POINT" and abs(p.get("z") or 0) > 0.001]
    lo, hi = level_band([v for _, _, v, _ in items] or [z for _, _, z in pts])
    far = [(x, y, v, "text") for x, y, v, _ in items if not lo <= v <= hi] + \
          [(x, y, z, "survey point") for x, y, z in pts if not lo <= z <= hi]
    items = [it for it in items if lo <= it[2] <= hi]
    pts = [p for p in pts if lo <= p[2] <= hi]
    if len({round(z, 2) for _, _, z in pts}) < 5:
        pts = []                                 # not a survey: a few points at one height
    pg = Grid(max(radius, 1.0))
    for x, y, z in pts:
        pg.add(x, y, z)
    paired, pidx, pinfo = pair_with_labels(items, anchors or {}, set(pass2_labels))
    rest = [it for k, it in enumerate(items) if k not in set(pidx.values())]
    free_nodes = [dict(n, deg=0) if n["id"] in paired else n for n in nodes]
    tmatch, tinfo = match_to_nodes(free_nodes, rest, radius) if rest else ({}, {})
    tinfo = dict(tinfo or {"pass2": set(), "pass2_n": 0, "pass1": 0, "matched": 0, "texts_unused": 0, "offsets": [],
                           "offset_samples": 0, "unused_offsets": []})
    # a GL paired with a label matched only in pass 2 is as uncertain as that label
    p2 = set(tinfo.get("pass2", set())) | {n for n in paired if n in set(pass2_labels)}
    tinfo.update({"texts": len(items), "paired": len(paired), "matched": tinfo.get("matched", 0) + len(paired),
                  "pass1": tinfo.get("pass1", 0) + sum(1 for n in paired if n not in p2), "pass2": p2,
                  "pass2_n": len(p2), **pinfo})
    tmatch = {**tmatch, **paired}
    # WATER (user request 22-Oct-2026, chit5: every GL taken from the lines' Z - 74.533, -4.617, 26.8 - though the
    # node layer has its GL texts): the drawing's GL first - a block attribute, else the GL text - and Z of the line
    # ends only where there is none, and only when Z is the ground: at the nodes having both, Z within Z_TEXT_AGREE_M
    # of the GL text (median). A Z far from the texts (a polyline's elevation, not a level) is not used at all.
    zt = [abs(max(n["z"]) - tmatch[n["id"]]) for n in used
          if n["id"] in tmatch and any(abs(z) > 0.001 for z in n["z"])]
    z_off = statistics.median(zt) if zt else None
    if z_mode == "off":
        z_useful = False
    elif z_mode == "first":
        z_useful = any(abs(z) > 0.001 for z in zs)
    elif z_useful and z_off is not None and z_off > Z_TEXT_AGREE_M:
        z_useful = False
        tinfo["z_ignored"] = (f"Z of the lines not used: {statistics.median(zt):.2f} m from the GL texts (median of "
                              f"{len(zt)} nodes having both) - a line's elevation, not the ground")
    if z_few and z_mode == "auto" and not tinfo.get("z_ignored"):
        tinfo["z_ignored"] = z_few
    tinfo["far"] = far
    tinfo["points"] = len(pts)
    node_levels.info = tinfo
    per_node = {}
    for n in used:
        if z_mode == "first" and z_useful and any(abs(z) > 0.001 for z in n["z"]):
            per_node[n["id"]] = ("Z", max(n["z"]))
            res["z"] += 1
            continue
        h = ag.near(n["x"], n["y"], radius)
        if h:
            per_node[n["id"]] = ("attribute", h[0][3])
            res["attr"] += 1
            continue
        if n["id"] in tmatch:
            per_node[n["id"]] = ("text", tmatch[n["id"]])
            res["text"] += 1
            continue
        h = pg.near(n["x"], n["y"], radius) if pts else None
        if h:
            per_node[n["id"]] = ("survey point", h[0][3])
            res["point"] += 1
            continue
        if z_useful and any(abs(z) > 0.001 for z in n["z"]):
            per_node[n["id"]] = ("Z", max(n["z"]))
            res["z"] += 1
            continue
        per_node[n["id"]] = (None, None)
        res["none"] += 1
    return res, per_node, bool(z_useful)
