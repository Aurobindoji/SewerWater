"""dxf_inspect: ground-level texts - numbers, tags, the band of a drawing's levels, each junction's level."""
import re
import statistics
import collections
from .kinds import DEC_RE, LEVEL_FAR_M, LEVEL_SPREAD_M, LEVEL_TAG, NUM, Z_TEXT_AGREE_M, classify
from .matching import match_to_nodes, pair_with_labels
from .spatial import Grid


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
