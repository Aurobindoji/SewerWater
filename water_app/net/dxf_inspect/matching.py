"""dxf_inspect: texts matched to junctions - optimal pairs, labels near nodes, labels paired in a second pass."""
import re
import collections
from .kinds import classify
from .spatial import Grid


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
