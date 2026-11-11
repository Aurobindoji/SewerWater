"""
dxf_inspect.py - READ-ONLY check of a CAD drawing (DXF / DWG) before a sewer design.
Tells what a sewer design needs, what the drawing has, and what is missing.
From the original scripts dxf_inspect.py, logic unchanged (output folder: sewer_app\\output; DWG read through ODA).

    python -m sewer_app.dxf_inspect "oakdale.dxf"
    python -m sewer_app.dxf_inspect "...\\oakdale.dxf" --pipe-layers PIPE0,PIPE1 --mh-layers TWO_CONCENTRIC_CIRCLES
    python -m sewer_app.dxf_inspect "...\\oakdale.dxf" --tol 0.5 --level-radius 10

A DWG is read through the free ODA File Converter when it is installed; otherwise save it as DXF
(AutoCAD: SAVEAS -> DXF). Nothing is written into the drawing.

What it reports (console + Excel 'output\\dxf_inspect\\<name>_dxf_inspect_<time>.xlsx')
  1. Drawing  : DXF version, units ($INSUNITS), extents, coordinate size (projected metres or not).
  2. Layers   : every layer with its entity types and counts, colour, total line length.
  3. Texts    : TEXT / MTEXT / block attributes per layer - how many are numbers, their range and
                common prefixes (GL, IL, RL, MH, mm ...) -> candidate ground-level / invert / diameter layers.
  4. Blocks   : block references per name and layer, with attribute tags and sample values.
  5. Network  : for the pipe layers (given, or guessed from the layer name: pipe / sewer / sw / main /
                line), lines are joined end to end within --tol: nodes, connected parts, loops, dead
                ends, near-miss gaps (ends that almost touch), T-joints without a node, segments longer
                than 30 m (CPHEEO manhole spacing), crossings without a node.
  6. Manholes : for point-like layers (block / circle / point) - how many network nodes have a symbol
                within --tol; the best match is proposed as the manhole layer.
  7. Levels   : ground level per node from (a) Z of the line vertices, (b) block attributes such as
                GL / RL / GROUND / ELEV, (c) the nearest numeric text within --level-radius m.
                Coverage per source is reported.
  8. Outfall  : texts such as STP / OUTFALL / SPS / IPS / PS / DISPOSAL and the nearest dead end.
  9. Checklist: REQUIRED item -> FOUND / PARTIAL / MISSING, with what to do.
"""

import os
import re
import statistics
import sys
import math
import time
import argparse
import collections

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))      # the sewer_app folder
OUT_DIR = os.path.join(BASE, "output", "dxf_inspect")

PIPE_NAME = re.compile(r"pipe|sewer|\bsw\b|^sw|main|line|nala|drain", re.I)
NOT_PIPE_NAME = re.compile(r"rail|road|boundary|electric|canal|pond|text|contour|building|plot|wall|"
                           r"tree|school|temple|well|site|hatch|grid|frame|title|dim", re.I)
OUTFALL_WORD = re.compile(r"\bSTP\b|OUT\s*FALL|\bSPS\b|\bIPS\b|\bMPS\b|\bPS\b|DISPOSAL|PUMPING|TREATMENT|"
                          r"EXIST(ING)?\s*(SEWER|MH|MANHOLE)|TRUNK", re.I)
# SEWER: an invert level (IL) is always below the GL at its manhole (user remark 22-Oct-2026: '0.05 m केवल 5 cm?
# न्यूनतम पाइप व्यास ही 15 cm है') -
IL_MIN_DEPTH_M = 0.15    # at least the smallest sewer (150 mm internal, CPHEEO; design_criteria min_diameter_mm) - less:
                         # its crown would be above the ground, so no IL (not taken);
IL_SHALLOW_M = 1.05      # less than the cover 0.9 m (CPHEEO p3-124, mandatory) + that pipe: taken, but a CHECK;
IL_MAX_DEPTH_M = 15.0    # at most this (deeper: not this manhole's IL, or a wrong text)
Z_TEXT_AGREE_M = 1.0     # Z of the lines is the ground only if within this of the GL texts (median)
LEVEL_TAG = re.compile(r"^(GL|G\.L|RL|R\.L|GROUND|ELEV|ELEVATION|LEVEL|NGL|EGL|LVL|Z)\b", re.I)
INVERT_TAG = re.compile(r"^(IL|I\.L|INV|INVERT)\b", re.I)
NUM = re.compile(r"[-+]?\d+(?:\.\d+)?")
ID_RE = re.compile(r"^\s*([A-Za-z]{1,8})\s*[-_ /]\s*(\d+[A-Za-z]?)\s*$")
DEC_RE = re.compile(r"^\s*(?:(GL|G\.L\.?|RL|R\.L\.?|NGL|EGL|EL|ELEV|LEVEL|TBM)\s*[:=.\-]?\s*)?(\d{1,4}\.\d{1,3})\s*(m|M)?\s*$")
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
UNITS = {0: "unitless", 1: "inches", 2: "feet", 4: "mm", 5: "cm", 6: "m", 7: "km"}


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


def text_summary(texts):
    by = collections.defaultdict(list)
    for t in texts:
        by[t["layer"]].append(t)
    rows = []
    for lay, ts in sorted(by.items()):
        nums, prefixes, decs = [], collections.Counter(), 0
        kinds = collections.Counter(kd for t in ts for kd, _ in classify(t["text"]))
        for t in ts:
            pre, v = parse_number(t["text"])
            if v is None:
                continue
            nums.append(v)
            if pre:
                prefixes[pre[:8]] += 1
            if re.search(r"\d\.\d{2,3}\b", t["text"]):
                decs += 1
        nums.sort()
        med = nums[len(nums) // 2] if nums else None
        band = sum(1 for v in nums if med is not None and abs(v - med) <= 15) if nums else 0
        rows.append({"layer": lay, "n": len(ts), "numeric": len(nums), "decimal_2_3": decs,
                     "min": nums[0] if nums else None, "max": nums[-1] if nums else None, "median": med,
                     "within_15m_of_median": band, "prefixes": ", ".join(f"{k}({c})" for k, c in prefixes.most_common(5)),
                     "kinds": ", ".join(f"{k}:{c}" for k, c in kinds.most_common()),
                     "samples": " | ".join(t["text"][:25] for t in ts[:6])})
    return rows


def level_candidates(texts, min_n=5):
    """{layer: [(x, y, value), ...]} of level-like values (decimal numbers, 1-3 decimals) per layer,
    kept only when at least 80 % of them lie within 15 m of the layer median and the median is above
    10 (terrain levels, not pipe lengths or depths)."""
    by = collections.defaultdict(list)
    for t in texts:
        for kind, v in classify(t["text"]):
            if kind == "level":
                by[t["layer"]].append((t["x"], t["y"], v))
    out = {}
    for lay, vals in by.items():
        if len(vals) < min_n:
            continue
        vs = sorted(v for _, _, v in vals)
        med = vs[len(vs) // 2]
        if med > 10 and sum(1 for v in vs if abs(v - med) <= 15) >= 0.8 * len(vs):
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


def pipe_annotations(edges, texts, layers, radius):
    """Per edge: nearest label / diameter / slope / length text of the same layer around the middle of the
    line (within radius of any vertex or the midpoint)."""
    g = Grid(max(radius, 1.0))
    for t in texts:
        if t["layer"] not in layers:
            continue
        for kind, v in classify(t["text"]):
            g.add(t["x"], t["y"], (kind, v, t["layer"]))
    out = {}
    for e in edges:
        p = e["pts"]
        half, acc, mid = e["len"] / 2, 0.0, p[0]
        for i in range(len(p) - 1):
            L = seg_len(p[i], p[i + 1])
            if acc + L >= half and L > 0:
                f = (half - acc) / L
                mid = (p[i][0] + f * (p[i + 1][0] - p[i][0]), p[i][1] + f * (p[i + 1][1] - p[i][1]))
                break
            acc += L
        r = min(radius, max(e["len"] / 2 + 2.0, 3.0))
        got = {}
        for dd, _, _, (kind, v, lay) in g.near(mid[0], mid[1], r):
            if lay != e["layer"]:
                continue
            key = "length" if kind == "level" else kind      # 'x.x m' next to a pipe = its length
            if key not in got:
                got[key] = v
        out[e["id"]] = got
    return out


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


def match_points(nodes, pts, tol):
    """Fraction of used nodes that have a point (block / circle / point) within tol."""
    g = Grid(max(tol, 0.01) * 2)
    for i, p in enumerate(pts):
        g.add(p["x"], p["y"], i)
    used = [n for n in nodes if n["deg"] > 0]
    hit = sum(1 for n in used if g.near(n["x"], n["y"], tol))
    return hit, len(used)


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


def split_gl_il(nodes, texts, layers, radius):
    """SEWER (user request 22-Oct-2026: 'IL सदैव GL से कम'): texts of `layers` written without 'IL' (plain "84.12 m")
    near one manhole with two or more level values - name, GL, IL, depth at every manhole: the highest is its GL, the
    lower ones IL_MIN_DEPTH_M .. IL_MAX_DEPTH_M below it are its IL (a depth "3.64 m" is far lower: neither). Each
    text goes to its nearest manhole within radius. Only when the layer is drawn so - two values at at least half of
    its manholes (oakdale MH-: 251 of 7,183 manholes have a neighbour's GL text near too - no IL there). Returns the
    indexes of the IL texts."""
    g = Grid(max(radius, 1.0))
    for n in nodes:
        if n["deg"] > 0:
            g.add(n["x"], n["y"], n["id"])
    by = collections.defaultdict(list)
    for i, t in enumerate(texts):
        if t["layer"] not in layers:
            continue
        v = next((v for kind, v in classify(t["text"]) if kind == "level"), None)
        h = g.near(t["x"], t["y"], radius) if v is not None else None
        if h:
            by[h[0][3]].append((v, i))
    out = set()
    if sum(1 for vals in by.values() if len(vals) >= 2) < 0.5 * len(by):
        return out
    for vals in by.values():
        if len(vals) >= 2:
            top = max(v for v, _ in vals)
            out |= {i for v, i in vals if IL_MIN_DEPTH_M <= top - v <= IL_MAX_DEPTH_M}
    return out


def node_inverts(nodes, texts, il_layers, gl_layers, radius, gl_of, split=(), skip=()):
    """SEWER: the IL of each manhole from the drawing - the texts marked IL / INV on il_layers, the plain levels of an
    il_layer that is no GL layer, and the IL texts split_gl_il found - matched one to one to the manholes as the GLs
    (match_to_nodes). An IL not IL_MIN_DEPTH_M .. IL_MAX_DEPTH_M below the manhole's GL (gl_of) is not taken.
    skip: indexes of texts that are no level (the lengths of their pipes). Returns ({node: IL}, [(node, IL, GL) not
    taken])."""
    items = []
    for i, t in enumerate(texts):
        if i in skip or (t["layer"] not in il_layers and i not in split):
            continue
        for kind, v in classify(t["text"]):
            if kind == "invert" or (kind == "level" and (i in split or t["layer"] not in gl_layers)):
                items.append((t["x"], t["y"], v, t.get("h") or 0.0))
                break
    if not items:
        return {}, []
    got, _ = match_to_nodes(nodes, items, radius)
    il, bad = {}, []
    for nid, v in got.items():
        gl = gl_of.get(nid)
        if gl is None or IL_MIN_DEPTH_M <= gl - v <= IL_MAX_DEPTH_M:
            il[nid] = v
        else:
            bad.append((nid, v, gl))
    return il, bad


def node_levels(nodes, texts, inserts, level_layers, radius, anchors=None, pass2_labels=(), z_mode="auto"):
    """Ground level per node from (in this order - water and sewer, 22-Oct-2026): block attributes, the GL text paired with the
    manhole's label (anchors - see pair_with_labels) or the nearest numeric text, Z of line ends (only when Z agrees
    with the GL texts). z_mode (the user's choice on the page, 22-Oct-2026): "auto" as said; "first" - Z of the line
    ends before all else, whether it agrees or not (the texts where there is no Z); "off" - Z not at all."""
    used = [n for n in nodes if n["deg"] > 0]
    res = {"z": 0, "attr": 0, "text": 0, "none": 0}
    # Z
    zs = [z for n in used for z in n["z"]]
    z_useful = zs and (max(zs) - min(zs) > 0.01) and sum(1 for z in zs if abs(z) > 0.001) > 0.5 * len(zs)
    # attributes
    ag = Grid(max(radius, 1.0))
    for i, b in enumerate(inserts):
        for tag, val in b["attrs"].items():
            if LEVEL_TAG.match(tag):
                _, v = parse_number(val)
                if v is not None:
                    ag.add(b["x"], b["y"], v)
                    break
    items = [(t["x"], t["y"], v, t.get("h") or 0.0) for t in texts if t["layer"] in level_layers
             for kind, v in classify(t["text"]) if kind == "level"]
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
    # (user request 22-Oct-2026 - water, then sewer - chit5: every GL taken from the lines' Z - 74.533, -4.617, 26.8 - though the
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
        if z_useful and any(abs(z) > 0.001 for z in n["z"]):
            per_node[n["id"]] = ("Z", max(n["z"]))
            res["z"] += 1
            continue
        per_node[n["id"]] = (None, None)
        res["none"] += 1
    return res, per_node, bool(z_useful)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Read-only DXF check for building a sewer model.")
    ap.add_argument("dxf")
    ap.add_argument("--pipe-layers", default="", help="comma separated; default: guessed from layer names")
    ap.add_argument("--mh-layers", default="", help="comma separated manhole symbol layers; default: best match")
    ap.add_argument("--level-layers", default="", help="comma separated ground-level text layers; default: guessed")
    ap.add_argument("--tol", type=float, default=0.5, help="snap tolerance for joining line ends (m), default 0.5")
    ap.add_argument("--level-radius", type=float, default=10.0, help="max distance node -> level text (m), default 10")
    a = ap.parse_args()
    path = os.path.abspath(a.dxf.strip('"'))
    t0 = time.time()
    doc, auditor = load(path)
    msp = doc.modelspace()
    hdr = doc.header
    ins = hdr.get("$INSUNITS", 0)
    layers, lines, texts, inserts, points = inventory(msp)
    print(f"File: {path}\nDXF {doc.dxfversion}, units {UNITS.get(ins, ins)}, entities read in {time.time() - t0:.1f} s; "
          f"audit: {len(auditor.errors)} error(s), {len(auditor.fixes)} fix(es)")
    allx = [p[0] for ln in lines for p in ln["pts"]] + [t["x"] for t in texts]
    ally = [p[1] for ln in lines for p in ln["pts"]] + [t["y"] for t in texts]
    if allx:
        w, h = max(allx) - min(allx), max(ally) - min(ally)
        big = max(abs(min(allx)), abs(max(allx)), abs(min(ally)), abs(max(ally)))
        print(f"Extent of data: {w:,.0f} x {h:,.0f} (drawing units); coordinates up to {big:,.0f} -> "
              + ("looks like projected metres (e.g. UTM)" if big > 100000 else "local / unknown coordinates"))

    # ---- layers
    lrows = []
    for lay, L in sorted(layers.items()):
        lrows.append({"layer": lay, "types": ", ".join(f"{k}:{v}" for k, v in L["types"].most_common()),
                      "entities": sum(L["types"].values()), "line_length": round(L["length"], 1),
                      "z_values": len(L["z"]), "z_range": (f"{min(L['z']):g} - {max(L['z']):g}" if L["z"] else ""),
                      "colour": L["color"].most_common(1)[0][0] if L["color"] else ""})
    print(f"\nLAYERS: {len(lrows)}")
    for r in sorted(lrows, key=lambda r: -r["line_length"])[:40]:
        print(f"   {r['layer'][:28]:<28} {r['entities']:>7}  length {r['line_length']:>11,.1f}  {r['types'][:70]}")

    # ---- texts
    trows = text_summary(texts)
    lvl_given = [s.strip() for s in a.level_layers.split(",") if s.strip()]
    lvl_cands = level_candidates(texts)
    print(f"\nTEXTS: {len(texts)} (incl. block attributes) on {len(trows)} layer(s)")
    for r in sorted(trows, key=lambda r: -r["numeric"])[:15]:
        print(f"   {r['layer'][:24]:<24} {r['n']:>6} texts; kinds {r['kinds'][:60] or '-'}; e.g. "
              f"{r['samples'][:60].replace(chr(10), ' ')}")
    print(f"   layers with level-like values (narrow band, > 10): "
          f"{', '.join(f'{k} ({len(v)})' for k, v in lvl_cands.items()) or 'none'}")

    # ---- blocks
    brows = collections.defaultdict(lambda: {"n": 0, "tags": collections.Counter(), "sample": ""})
    for b in inserts:
        k = (b["name"], b["layer"])
        brows[k]["n"] += 1
        for tg, v in b["attrs"].items():
            brows[k]["tags"][tg] += 1
            if not brows[k]["sample"]:
                brows[k]["sample"] = f"{tg}={v}"
    print(f"\nBLOCK REFERENCES: {len(inserts)}")
    for (nm, lay), v in sorted(brows.items(), key=lambda kv: -kv[1]["n"])[:20]:
        print(f"   {nm[:26]:<26} on {lay[:22]:<22} x{v['n']:<6} attributes: {', '.join(v['tags']) or '-'}")

    # ---- pipe layers
    linear = [r["layer"] for r in lrows if r["line_length"] > 0]
    pipe_layers = [s.strip() for s in a.pipe_layers.split(",") if s.strip()]
    guessed = not pipe_layers
    if not pipe_layers:
        pipe_layers = [l for l in linear if PIPE_NAME.search(l) and not NOT_PIPE_NAME.search(l)]
    pl = [ln for ln in lines if ln["layer"] in pipe_layers]
    print(f"\nPIPE LAYERS {'(guessed from names - check!)' if guessed else '(given)'}: {', '.join(pipe_layers) or 'NONE'}")
    net_rows = []
    per_layer = {}
    for lay in pipe_layers:
        ls = [ln for ln in lines if ln["layer"] == lay]
        nd, ed, _ = build_network(ls, a.tol)
        chk = network_checks(nd, ed, a.tol)
        per_layer[lay] = chk
        net_rows.append({"set": lay, **{k: (len(v) if isinstance(v, list) else v) for k, v in chk.items()
                                         if k not in ("part_sizes",)}, "part_sizes": str(chk["part_sizes"])})
    nodes, edges, _ = build_network(pl, a.tol)
    chk = network_checks(nodes, edges, a.tol) if edges else None
    if chk:
        net_rows.append({"set": "ALL PIPE LAYERS TOGETHER",
                         **{k: (len(v) if isinstance(v, list) else v) for k, v in chk.items() if k != "part_sizes"},
                         "part_sizes": str(chk["part_sizes"])})
        for lay, c in list(per_layer.items()) + [("ALL", chk)]:
            print(f"   {lay[:22]:<22} length {c['length']:>10,.1f} m, {c['edges']:>5} lines, {c['nodes']:>5} nodes, "
                  f"{c['parts']:>3} part(s), {c['loops']:>3} loop(s), {c['dead_ends']:>4} dead ends, "
                  f"{len(c['gaps']):>3} near-miss gaps, {len(c['tjoints']):>3} T-joints w/o node, "
                  f"crossings {c['crossings'] if c['crossings'] is not None else 'not checked'}, "
                  f"{len(c['long'])} lines > 30 m")

    # ---- manhole symbols
    cands, cand_layer = collections.defaultdict(list), {}
    for b in inserts:
        for k in (f"{b['layer']} / block {b['name']}", f"{b['layer']} (all blocks)"):
            cands[k].append(b)
            cand_layer[k] = b["layer"]
    for p in points:
        k = f"{p['layer']} / {p['kind']}"
        cands[k].append(p)
        cand_layer[k] = p["layer"]
    mh_given = [s.strip() for s in a.mh_layers.split(",") if s.strip()]
    mrows = []
    if edges:
        for k, pts in cands.items():
            lay = cand_layer[k]
            if mh_given and lay not in mh_given:
                continue
            hit, tot = match_points(nodes, pts, a.tol)
            if hit:
                mrows.append({"candidate": k, "layer": lay, "symbols": len(pts), "nodes_with_symbol": hit, "nodes": tot,
                              "share": round(hit / tot, 3) if tot else 0})
        mrows.sort(key=lambda r: -r["share"])
    print("\nMANHOLE SYMBOLS at network nodes:")
    for r in mrows[:8]:
        print(f"   {r['candidate'][:50]:<50} {r['nodes_with_symbol']:>5} of {r['nodes']} nodes ({r['share']:.0%}), "
              f"{r['symbols']} symbols in all")
    if not mrows:
        print("   none - no point / block / circle lies on the line ends (manholes would be created at line ends)")

    # ---- levels: the given layer(s), else the candidate layer that covers most nodes
    cover = []
    if edges:
        used_nodes = [n for n in nodes if n["deg"] > 0]
        for lay, vals in lvl_cands.items():
            g = Grid(max(a.level_radius, 1.0))
            for x, y, v in vals:
                g.add(x, y, v)
            hit = sum(1 for n in used_nodes if g.near(n["x"], n["y"], a.level_radius))
            cover.append((hit, lay))
        cover.sort(reverse=True)
    lvl_layers = lvl_given or ([cover[0][1]] if cover and cover[0][0] else [])
    print("\nLEVEL TEXT LAYERS by node coverage (within %g m): " % a.level_radius
          + (", ".join(f"{lay} {hit}" for hit, lay in cover) or "none") + f" -> using: {', '.join(lvl_layers) or 'none'}")
    lres, per_node, z_useful = (node_levels(nodes, texts, inserts, lvl_layers, a.level_radius)
                                if edges else ({"z": 0, "attr": 0, "text": 0, "none": 0}, {}, False))
    nn = sum(lres.values())
    mh_lay = set(mh_given) or ({mrows[0]["layer"]} if mrows else set())
    mh_labels = labels_near_nodes(nodes, texts, a.level_radius, mh_lay) if edges else {}
    if edges and mh_lay and not any(mh_labels.values()):
        mh_labels = labels_near_nodes(nodes, texts, a.level_radius)      # no IDs on the symbol layer
    n_lab = sum(1 for v in mh_labels.values() if v)
    dup = [k for k, c in collections.Counter(v for v in mh_labels.values() if v).items() if c > 1]
    print(f"MANHOLE LABELS (ID text within {a.level_radius:g} m): {n_lab} of {len(mh_labels)} nodes"
          + (f"; {len(dup)} label(s) used by more than one node, e.g. {', '.join(dup[:5])}" if dup else ""))
    ann = pipe_annotations(edges, texts, set(pipe_layers), 20.0) if edges else {}
    cnt = collections.Counter(k for v in ann.values() for k in v)
    ratios = sorted(e["len"] / v["length"] for e in edges for v in [ann.get(e["id"], {})]
                    if v.get("length") and v["length"] > 1 and e["len"] > 1)
    unit_ok = None
    if ratios:
        med = ratios[len(ratios) // 2]
        unit_ok = abs(med - 1.0) < 0.02
        print(f"PIPE TEXTS: label {cnt['id']}, diameter {cnt['dia']}, slope {cnt['slope_1in']}, length {cnt['length']} "
              f"of {len(edges)} lines; drawn / written length median {med:.3f} -> "
              + ("drawing units = METRES (confirmed)" if unit_ok else "units differ - check"))
    else:
        print(f"PIPE TEXTS: label {cnt['id']}, diameter {cnt['dia']}, slope {cnt['slope_1in']}, length {cnt['length']} "
              f"of {len(edges)} lines")
    print(f"\nGROUND LEVEL at network nodes ({nn} nodes): from Z {lres['z']}, from block attributes {lres['attr']}, "
          f"from text within {a.level_radius:g} m {lres['text']}, none {lres['none']}")
    vals = [v for s, v in per_node.values() if v is not None]
    if vals:
        print(f"   levels found: {min(vals):.3f} - {max(vals):.3f}")

    # ---- outfall
    orows = []
    used = [n for n in nodes if n["deg"] == 1]
    og = Grid(50.0)
    for n in used:
        og.add(n["x"], n["y"], n["id"])
    for t in texts:
        if OUTFALL_WORD.search(t["text"] or ""):
            h = og.near(t["x"], t["y"], 300.0)
            orows.append({"text": t["text"][:60], "layer": t["layer"], "x": round(t["x"], 2), "y": round(t["y"], 2),
                          "nearest_dead_end_m": round(h[0][0], 1) if h else None})
    print(f"\nOUTFALL hints (STP / outfall / SPS / IPS / existing sewer texts): {len(orows)}")
    for r in orows[:10]:
        print(f"   '{r['text']}' on {r['layer']} - nearest dead end of the pipes {r['nearest_dead_end_m']} m")

    # ---- checklist
    chkl = []

    def item(need, status, found, todo):
        chkl.append({"required": need, "status": status, "found": found, "to do": todo})
    if not pipe_layers or not edges:
        item("Network lines (sewer alignment)", "MISSING", "no pipe layer recognised",
             "give the layer(s) with --pipe-layers (see LAYERS above)")
    else:
        item("Network lines (sewer alignment)", "FOUND" if not guessed else "CHECK",
             f"{', '.join(pipe_layers)}: {chk['length']:,.0f} m, {chk['edges']} lines",
             "confirm these are the PROPOSED sewer lines (PIPE0/1/2 may be existing / proposed / water)" if guessed else "")
        ok = chk["parts"] == 1 and not chk["gaps"] and not chk["tjoints"]
        item("Connected network (one tree per outfall)", "FOUND" if ok and not chk["loops"] else "PARTIAL",
             f"{chk['parts']} part(s) {chk['part_sizes']}, {len(chk['gaps'])} near-miss gaps, "
             f"{len(chk['tjoints'])} T-joints without node, {chk['loops']} loop(s), crossings {chk['crossings']}",
             "join the gaps / break lines at T-joints in CAD, or use a larger --tol; a sewer must have no loops "
             "(each loop needs one line removed or split)" if not ok or chk["loops"] else "")
        best = mrows[0] if mrows else None
        item("Manhole positions", "FOUND" if best and best["share"] >= 0.9 else ("PARTIAL" if best else "MISSING"),
             f"best match {best['candidate']}: {best['share']:.0%} of nodes" if best else "no symbols on the nodes",
             "manholes can be created at every line end / junction (ModelBuilder 'create nodes'); "
             f"{len(chk['long'])} line(s) are longer than 30 m - the design adds manholes there")
        st = "FOUND" if lres["none"] == 0 else ("PARTIAL" if lres["none"] < nn else "MISSING")
        item("Ground level at every manhole", st,
             f"Z {lres['z']}, attributes {lres['attr']}, texts {lres['text']}, none {lres['none']} of {nn}",
             "" if st == "FOUND" else "give the level text layer (--level-layers), or a survey CSV (MH, GL), "
             "or a DEM / TIN for SewerGEMS TRex")
    if edges:
        item("Manhole labels (MH-...)", "FOUND" if n_lab >= 0.95 * len(mh_labels) else ("PARTIAL" if n_lab else "NOT GIVEN"),
             f"{n_lab} of {len(mh_labels)} nodes" + (f", {len(dup)} duplicate label(s)" if dup else ""),
             "" if n_lab else "names will be generated (MH-1, MH-2 ...)")
        item("Existing pipe data (diameter / slope) - for checking an existing design",
             "FOUND" if cnt["dia"] >= 0.95 * len(edges) else ("PARTIAL" if cnt["dia"] else "NOT GIVEN"),
             f"diameter {cnt['dia']}, slope {cnt['slope_1in']}, length {cnt['length']} of {len(edges)} lines",
             "inverts are not in the drawing: slopes alone fix inverts only relative to one known invert per line")
    item("Outfall location", "FOUND" if orows else "MISSING",
         f"{len(orows)} text hint(s)" if orows else "no STP / outfall text",
         "tell which dead end is the outfall (MH label or X, Y)")
    item("Outfall level fixed? (existing sewer / STP inlet)", "ASK", "not in a drawing", "answer in sewer_design.py --ask (question 3)")
    item("Population / sewage load", "ASK", "not in a drawing",
         "design population and per capita water supply - sewer_design.py --ask (questions 5-6)")
    inv_texts = sum(1 for t in texts if INVERT_TAG.match(t["text"] or ""))
    item("Invert levels (only for checking an EXISTING design)", "FOUND" if inv_texts else "NOT GIVEN",
         f"{inv_texts} IL text(s)", "not needed for a new design - the design fixes the inverts")
    units_found = ins == 6 or bool(edges and unit_ok)
    item("Drawing units = metres", "FOUND" if units_found else "CHECK",
         f"{UNITS.get(ins, str(ins))}" + (" ; written pipe lengths = drawn lengths" if edges and unit_ok else ""),
         "" if units_found else "lengths must be in metres - check a known distance in CAD")
    print("\n================ CHECKLIST ================")
    for c in chkl:
        print(f"   [{c['status']:<9}] {c['required']}: {c['found']}" + (f"\n               -> {c['to do']}" if c["to do"] else ""))

    # ---- Excel
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
    except ImportError:
        print("(openpyxl not installed - Excel report skipped)")
        return
    os.makedirs(OUT_DIR, exist_ok=True)
    stem = os.path.splitext(os.path.basename(path))[0]
    out = os.path.join(OUT_DIR, f"{stem}_dxf_inspect_{time.strftime('%Y%m%d_%H%M')}.xlsx")
    wb = Workbook()
    bold, head = Font(bold=True), PatternFill("solid", fgColor="D9E1F2")
    colours = {"FOUND": "C6EFCE", "PARTIAL": "FFEB9C", "CHECK": "FFEB9C", "ASK": "DDEBF7", "MISSING": "F8CBAD",
               "NOT GIVEN": "EDEDED"}

    def sheet(ws, rows, cols=None):
        if not rows:
            ws.append(["(none)"])
            return
        cols = cols or list(rows[0].keys())
        ws.append(cols)
        for c in ws[1]:
            c.font, c.fill = bold, head
        for r in rows:
            ws.append([r.get(c) for c in cols])
        for i, c in enumerate(cols, start=1):
            ws.column_dimensions[ws.cell(1, i).column_letter].width = min(60, max(12, len(c) + 2))
    ws = wb.active
    ws.title = "Checklist"
    sheet(ws, chkl)
    for r in range(2, ws.max_row + 1):
        st = ws.cell(r, 2).value
        if st in colours:
            ws.cell(r, 2).fill = PatternFill("solid", fgColor=colours[st])
    ws.append([])
    ws.append(["File", path])
    ws.append(["Options", f"tol {a.tol} m, level radius {a.level_radius} m, pipe layers {', '.join(pipe_layers)}"])
    sheet(wb.create_sheet("Layers"), sorted(lrows, key=lambda r: -r["line_length"]))
    sheet(wb.create_sheet("Texts by layer"), trows)
    sheet(wb.create_sheet("Blocks"), [{"block": k[0], "layer": k[1], "count": v["n"], "attribute tags": ", ".join(v["tags"]),
                                      "sample": v["sample"]} for k, v in brows.items()])
    sheet(wb.create_sheet("Network"), net_rows)
    sheet(wb.create_sheet("Manhole symbols"), mrows)
    ws = wb.create_sheet("Nodes")
    rows = []
    for n in nodes:
        if n["deg"] == 0:
            continue
        src, v = per_node.get(n["id"], (None, None))
        rows.append({"node": n["id"], "label": mh_labels.get(n["id"]), "x": round(n["x"], 3), "y": round(n["y"], 3),
                     "lines": n["deg"],
                     "type": "dead end" if n["deg"] == 1 else ("junction" if n["deg"] >= 3 else "through"),
                     "ground level": v, "level from": src})
    sheet(ws, rows)
    if edges:
        prow = []
        for e in edges:
            v = ann.get(e["id"], {})
            prow.append({"line": e["id"], "handle": e["handle"], "layer": e["layer"], "label": v.get("id"),
                         "from node": e["a"], "to node": e["b"],
                         "from MH": mh_labels.get(e["a"]), "to MH": mh_labels.get(e["b"]),
                         "drawn length": round(e["len"], 2), "written length": v.get("length"),
                         "dia (mm)": v.get("dia"), "slope 1 in": v.get("slope_1in")})
        sheet(wb.create_sheet("Pipes"), prow)
    if chk:
        ws = wb.create_sheet("Problems")
        prob = []
        for nid, other, d in chk["gaps"]:
            prob.append({"problem": "near-miss gap", "x": round(nodes[nid]["x"], 3), "y": round(nodes[nid]["y"], 3),
                         "detail": f"end {nid} is {d:.2f} m from node {other} (not joined)"})
        for nid, eid, d in chk["tjoints"]:
            prob.append({"problem": "T-joint without node", "x": round(nodes[nid]["x"], 3), "y": round(nodes[nid]["y"], 3),
                         "detail": f"end {nid} lies on line handle {edges[eid]['handle']} ({d:.2f} m) - break that line here"})
        for eid in chk["long"]:
            e = edges[eid]
            prob.append({"problem": "line longer than 30 m", "x": round(e["pts"][0][0], 3), "y": round(e["pts"][0][1], 3),
                         "detail": f"handle {e['handle']}, {e['len']:.1f} m (manholes will be added by the design)"})
        sheet(ws, prob)
    sheet(wb.create_sheet("Outfall hints"), orows)
    wb.save(out)
    print(f"\nExcel report: {out}  ({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()
