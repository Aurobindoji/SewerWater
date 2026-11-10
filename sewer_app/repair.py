"""Check and repair a sewer network read from a drawing, before zoning / design (user decision 12-Oct-2026: start
the design work with the network problems of the DXF).

    issues = repair.check(net, ex, outfalls)          # every problem with its place, nothing changed
    net2, log = repair.repair(net, ex, outfalls)      # the automatic repairs, each one listed
    repair.write_check(issues, log, "x_check.xlsx", "x_check_markers.dxf")

Automatic repairs, in this order (each can be switched off):
  1. duplicate conduit labels      second one renamed <label>-D<n>
  2. near-miss gaps <= join_gap_m  the two line ends joined into one manhole (the one with a drawing label / GL kept);
                                    longer gaps (dxf_extract lists up to its search distance) are only reported
  3. T-joints                      a line that ends on another line within tjoint_m gets a manhole there: the other
                                    line is split at that point
  4. loops                         a gravity sewer is a tree: walking out from the outfalls (or the lowest manhole of
                                    a part without one), every conduit that closes a loop is disconnected at its
                                    HIGHER end, which gets a new head manhole <MH>-C<n> at the same place (as zoning)
  5. missing ground levels         filled along the sewers: each unknown GL = length-weighted mean of its neighbours
                                    (weight 1/L), solved for all unknowns together - a straight line between the
                                    known levels along a run of pipes; gl_source 'interpolated along the sewer'
Reported only (a person must look at the drawing): manholes without a drawing label (name generated), labels and
GLs matched in pass 2 of dxf_extract (nearest free text) - split into 'CHECK' and 'low risk' (number within 2 of a
neighbour's / GL within 1 m of the neighbours' mean), manholes found on a continuous line, GL spikes (> 2 m from
ALL neighbours), parts of the network without an outfall (lowest manhole + nearest manholes of other parts), gaps
longer than join_gap_m, very short conduits.
"""
import collections
import math

from .spacing import label_namer, plen_of

GL_SPIKE_M = 2.0
SHORT_CONDUIT_M = 0.5
OVERLAP_M = 1.0                 # two manholes this close (their symbols overlap) with no sewer between them: a warning
OVERLAP = "manholes overlap, not joined"
INTERP_SRC = "interpolated along the sewer (no level in the drawing)"


# ---------------------------------------------------------------- helpers
def _copy(net):
    return {"nodes": {n: dict(v) for n, v in net["nodes"].items()},
            "conduits": [dict(k, vertices=list(k.get("vertices") or [])) for k in net["conduits"]],
            "outfalls": list(net.get("outfalls") or [])}


def _adj(net):
    adj = collections.defaultdict(list)
    for k in net["conduits"]:
        adj[k["start_node"]].append((k["stop_node"], k))
        adj[k["stop_node"]].append((k["start_node"], k))
    return adj


def _parts(net):
    """{node: part number} (1 = largest part)."""
    adj, part, groups = _adj(net), {}, []
    for s in sorted(adj):
        if s in part:
            continue
        comp, st = [s], [s]
        part[s] = -1
        while st:
            n = st.pop()
            for m, _ in adj[n]:
                if m not in part:
                    part[m] = -1
                    comp.append(m)
                    st.append(m)
        groups.append(comp)
    groups.sort(key=len, reverse=True)
    for i, g in enumerate(groups, 1):
        for n in g:
            part[n] = i
    return part


def _ground(net, n):
    return (net["nodes"].get(n) or {}).get("ground")


def _xy(net, n):
    p = (net["nodes"].get(n) or {}).get("xy")
    return tuple(p) if p else None


def overlaps(net, tol=OVERLAP_M):
    """Pairs of manholes at most tol apart that no sewer joins directly: [(a, b, distance m)], closest first - a
    loop cut head <MH>-C<n> left at its manhole (cut_loops), or one manhole drawn twice. Either can split the network
    in two without it showing on the map (user request 20-Oct-2026: a red cross there)."""
    xy = {n: v["xy"] for n, v in net["nodes"].items() if v.get("xy")}
    joined = {frozenset((k["start_node"], k["stop_node"])) for k in net["conduits"]}
    cell = max(tol, 1e-6)
    grid = collections.defaultdict(list)
    for n, p in xy.items():
        grid[(math.floor(p[0] / cell), math.floor(p[1] / cell))].append(n)
    out = []
    for n, p in xy.items():
        cx, cy = math.floor(p[0] / cell), math.floor(p[1] / cell)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for m in grid.get((cx + dx, cy + dy), ()):
                    if m > n:
                        d = math.dist(p, xy[m])
                        if d <= tol and frozenset((n, m)) not in joined:
                            out.append((n, m, d))
    return sorted(out, key=lambda r: (r[2], r[0], r[1]))


def _point_seg(p, a, b):
    """(distance, t along a-b, foot point)."""
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if not L2 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L2))
    fx, fy = ax + t * dx, ay + t * dy
    return math.hypot(p[0] - fx, p[1] - fy), t, (fx, fy)


def _pts(net, k):
    pts = [tuple(p) for p in k.get("vertices") or []]
    if len(pts) < 2:
        a, b = _xy(net, k["start_node"]), _xy(net, k["stop_node"])
        pts = [a, b] if a and b else []
    return pts


# ---------------------------------------------------------------- 1 duplicate labels
def rename_duplicates(net, log):
    seen, names = collections.Counter(), {k["label"] for k in net["conduits"]}
    for k in net["conduits"]:
        seen[k["label"]] += 1
        if seen[k["label"]] > 1:
            i = 1
            while f"{k['label']}-D{i}" in names:
                i += 1
            new = f"{k['label']}-D{i}"
            names.add(new)
            log.append({"repair": "duplicate conduit label renamed", "item": f"{k['label']} -> {new}",
                        "x": None, "y": None, "detail": ""})
            k["label"] = new


# ---------------------------------------------------------------- 2 near-miss gaps
def join_gaps(net, gaps, max_m, log):
    """gaps = [(node a, node b, distance)]: join pairs not farther apart than max_m into one manhole."""
    for a, b, d in gaps:
        if d > max_m or a not in net["nodes"] or b not in net["nodes"] or a == b:
            continue
        # keep the node with a drawing label (not MH-G..), then the one with a GL
        keep, gone = sorted((a, b), key=lambda n: (str(n).startswith("MH-G"), _ground(net, n) is None, str(n)))
        for k in net["conduits"]:
            for end in ("start_node", "stop_node"):
                if k[end] == gone:
                    k[end] = keep
                    pts = k.get("vertices") or []
                    if pts and _xy(net, keep):
                        if end == "start_node":
                            pts[0] = _xy(net, keep)
                        else:
                            pts[-1] = _xy(net, keep)
        net["conduits"] = [k for k in net["conduits"] if k["start_node"] != k["stop_node"]]
        if gone in net["outfalls"]:
            net["outfalls"] = [keep if o == gone else o for o in net["outfalls"]]
        xy = _xy(net, gone)
        del net["nodes"][gone]
        log.append({"repair": "near-miss gap joined", "item": f"{gone} -> {keep}", "x": xy[0] if xy else None,
                    "y": xy[1] if xy else None, "detail": f"{d:.2f} m apart"})


# ---------------------------------------------------------------- 3 T-joints
def split_tjoints(net, tol, log):
    """A line end (manhole with one conduit) lying on the inside of another conduit within tol: that conduit is
    split there so the two sewers meet in the manhole."""
    deg = collections.Counter()
    for k in net["conduits"]:
        deg[k["start_node"]] += 1
        deg[k["stop_node"]] += 1
    ends = [n for n, c in deg.items() if c == 1 and _xy(net, n)]
    cell = max(tol * 4, 20.0)
    grid = collections.defaultdict(list)
    for i, k in enumerate(net["conduits"]):
        P = _pts(net, k)
        for s in range(len(P) - 1):
            (x1, y1), (x2, y2) = P[s], P[s + 1]
            for gx in range(int(math.floor((min(x1, x2) - tol) / cell)), int(math.floor((max(x1, x2) + tol) / cell)) + 1):
                for gy in range(int(math.floor((min(y1, y2) - tol) / cell)), int(math.floor((max(y1, y2) + tol) / cell)) + 1):
                    grid[(gx, gy)].append((i, s))
    namer = label_namer([k["label"] for k in net["conduits"]], "CO-")
    hits = {}
    for n in ends:
        p = _xy(net, n)
        best = None
        for i, s in grid.get((int(math.floor(p[0] / cell)), int(math.floor(p[1] / cell))), ()):
            k = net["conduits"][i]
            if n in (k["start_node"], k["stop_node"]):
                continue
            P = _pts(net, k)
            d, t, foot = _point_seg(p, P[s], P[s + 1])
            if d <= tol and (best is None or d < best[0]):
                best = (d, i, s, t, foot)
        if best is None:
            continue
        d, i, s, t, foot = best
        P = _pts(net, net["conduits"][i])
        ch = plen_of(P[:s + 1]) + t * math.dist(P[s], P[s + 1])
        if min(ch, plen_of(P) - ch) <= max(tol, 1.0):
            continue                                       # at the other line's end: a gap, not a T-joint
        hits.setdefault(i, []).append((ch, n, foot, d))
    new = []
    for i, k in enumerate(net["conduits"]):
        if i not in hits:
            new.append(k)
            continue
        P, L = _pts(net, k), k.get("length_m") or plen_of(_pts(net, k))
        tot = plen_of(P) or 1.0
        cuts = sorted(hits[i])
        chain = [k["start_node"]] + [n for _, n, _, _ in cuts] + [k["stop_node"]]
        chs = [0.0] + [c for c, _, _, _ in cuts] + [tot]
        for j in range(len(chain) - 1):
            pts = _sub(P, chs[j], chs[j + 1])
            pts[0] = _xy(net, chain[j]) or pts[0]
            pts[-1] = _xy(net, chain[j + 1]) or pts[-1]
            new.append(dict(k, label=k["label"] if j == 0 else namer(), start_node=chain[j], stop_node=chain[j + 1],
                            vertices=pts, length_m=L * (chs[j + 1] - chs[j]) / tot))
        for c, n, foot, d in cuts:
            log.append({"repair": "T-joint: line split at a manhole", "item": f"{k['label']} at {n}",
                        "x": foot[0], "y": foot[1], "detail": f"line end {d:.2f} m from the line"})
    net["conduits"] = new


def _sub(P, a, b):
    from .spacing import point_at
    out, run = [point_at(P, a)], 0.0
    for p, q in zip(P, P[1:]):
        run += math.dist(p, q)
        if a + 1e-6 < run < b - 1e-6:
            out.append(q)
    out.append(point_at(P, b))
    return out


# ---------------------------------------------------------------- 4 loops
def cut_loops(net, outfalls, log):
    """Breadth-first walk from the outfalls (a part without one: from its lowest manhole); every conduit that
    closes a loop is disconnected at its higher end - a new head manhole <MH>-C<n> at the same place."""
    adj, part = _adj(net), _parts(net)
    roots = [o for o in outfalls if o in adj]
    have = {part[o] for o in roots}
    for p in sorted(set(part.values()) - have):
        cand = [n for n in adj if part[n] == p]
        roots.append(min(cand, key=lambda n: (_ground(net, n) if _ground(net, n) is not None else 1e9, n)))
    seen, tree = set(roots), set()
    queue = collections.deque(roots)
    while queue:
        n = queue.popleft()
        for m, k in adj[n]:
            if m not in seen:
                seen.add(m)
                tree.add(id(k))
                queue.append(m)
    used = set(net["nodes"])
    for k in net["conduits"]:
        if id(k) in tree:
            continue
        a, b = k["start_node"], k["stop_node"]
        ga, gb = _ground(net, a), _ground(net, b)
        up = a if (ga if ga is not None else -1e9, a) > (gb if gb is not None else -1e9, b) else b
        i = 1
        while f"{up}-C{i}" in used:
            i += 1
        new = f"{up}-C{i}"
        used.add(new)
        net["nodes"][new] = dict(net["nodes"][up], cut_of=up)
        k["start_node" if a == up else "stop_node"] = new
        xy = _xy(net, up)
        log.append({"repair": "loop: conduit disconnected at its higher end", "item": f"{k['label']} from {up} -> {new}",
                    "x": xy[0] if xy else None, "y": xy[1] if xy else None, "detail": "a gravity sewer must be a tree"})


# ---------------------------------------------------------------- 5 ground levels
def fill_gl(net, log, iters=5000, tol=1e-6):
    """Unknown GLs = length-weighted (1/L) mean of the neighbours, all unknowns solved together (Gauss-Seidel):
    a straight line between known levels along a run. Nodes of a part with no known level stay empty."""
    nb = collections.defaultdict(list)
    for k in net["conduits"]:
        w = 1.0 / max(k.get("length_m") or 1.0, 0.1)
        nb[k["start_node"]].append((k["stop_node"], w))
        nb[k["stop_node"]].append((k["start_node"], w))
    unknown = [n for n in nb if _ground(net, n) is None]
    if not unknown:
        return
    part = _parts(net)
    known_parts = {part[n] for n in nb if _ground(net, n) is not None}
    solvable = [n for n in unknown if part[n] in known_parts]
    g = {n: _ground(net, n) for n in nb}
    for n in solvable:                                   # start from the mean of the part's known levels
        g[n] = 0.0
    kv = collections.defaultdict(list)
    for n in nb:
        if _ground(net, n) is not None:
            kv[part[n]].append(_ground(net, n))
    for n in solvable:
        g[n] = sum(kv[part[n]]) / len(kv[part[n]])
    for _ in range(iters):
        delta = 0.0
        for n in solvable:
            sw = sum(w for _, w in nb[n])
            v = sum(g[m] * w for m, w in nb[n]) / sw
            delta = max(delta, abs(v - g[n]))
            g[n] = v
        if delta < tol:
            break
    for n in solvable:
        net["nodes"][n]["ground"] = round(g[n], 3)
        net["nodes"][n]["gl_source"] = INTERP_SRC
        xy = _xy(net, n)
        log.append({"repair": "ground level interpolated along the sewer", "item": n, "x": xy[0] if xy else None,
                    "y": xy[1] if xy else None, "detail": f"GL {g[n]:.3f} m"})
    for n in unknown:
        if n not in solvable:
            xy = _xy(net, n)
            log.append({"repair": "NOT filled: no ground level anywhere in this part", "item": n,
                        "x": xy[0] if xy else None, "y": xy[1] if xy else None, "detail": ""})


# ---------------------------------------------------------------- check (report only)
def parts_report(net, outfalls, per_part=2):
    """Rows per part: manholes, length, outfalls, lowest manhole; for a part without an outfall also the nearest
    manholes of other parts (where a connecting sewer could go)."""
    part = _parts(net)
    rows = []
    length = collections.Counter()
    for k in net["conduits"]:
        length[part.get(k["start_node"])] += k.get("length_m") or 0.0
    members = collections.defaultdict(list)
    for n, p in part.items():
        members[p].append(n)
    xy = {n: _xy(net, n) for n in part if _xy(net, n)}
    cell = 50.0
    grid = collections.defaultdict(list)
    for n, p_ in xy.items():
        grid[(int(p_[0] // cell), int(p_[1] // cell))].append(n)
    for p in sorted(members):
        ms = members[p]
        outs = [o for o in outfalls if part.get(o) == p]
        low = min(ms, key=lambda n: (_ground(net, n) if _ground(net, n) is not None else 1e9, n))
        row = {"part": p, "manholes": len(ms), "sewer length (m)": round(length[p], 1),
               "outfalls": ", ".join(outs) or "NONE", "lowest manhole": low, "its GL": _ground(net, low),
               "nearest other parts": ""}
        if not outs and len(members) > 1:
            best = {}
            for n in ms:
                if n not in xy:
                    continue
                gx, gy = int(xy[n][0] // cell), int(xy[n][1] // cell)
                for i in range(gx - 4, gx + 5):
                    for j in range(gy - 4, gy + 5):
                        for m in grid.get((i, j), ()):
                            q = part[m]
                            if q == p:
                                continue
                            d = math.dist(xy[n], xy[m])
                            if q not in best or d < best[q][0]:
                                best[q] = (d, n, m)
            row["nearest other parts"] = "; ".join(
                f"part {q}: {n} - {m} {d:.1f} m (GL {_ground(net, n)} / {_ground(net, m)})"
                for q, (d, n, m) in sorted(best.items(), key=lambda kv: kv[1][0])[:per_part]) or "none within 200 m"
        rows.append(row)
    return rows


def check(net, ex=None, outfalls=(), gravity=True):
    """Every problem as {"type", "item", "x", "y", "detail"} - nothing is changed. gravity=False (a water main
    network): loops are wanted there and it has no outfalls - neither is a problem (user report 20-Oct-2026)."""
    out = []

    def add(t, item, xy, detail=""):
        out.append({"type": t, "item": item, "x": xy[0] if xy else None, "y": xy[1] if xy else None, "detail": detail})
    kind = {"no GL": "no ground level", "no MH label in the drawing": "no drawing label (name generated)",
            "label matched in pass 2 - number fits": "label matched in pass 2 - low risk",
            "label matched in pass 2 (nearest free text)": "label matched in pass 2 - CHECK",
            "GL matched in pass 2 - within 1 m": "GL matched in pass 2 - low risk",
            "GL matched in pass 2 (nearest free text)": "GL matched in pass 2 - CHECK",
            "manhole on a continuous line - line cut there (check in CAD)": "manhole on a continuous line - check",
            "near-miss gap (not joined)": "near-miss gap", "line ends on another line without a node": "T-joint",
            "MH label used by more than one node": "label used twice in the drawing",
            "IL not below the GL": "IL not below the GL - CHECK", "IL shallow": "IL shallow - CHECK"}
    if ex:
        for p in ex["problems"]:
            t = next((v for k, v in kind.items() if p["Problem"].startswith(k)), None)
            if t:
                add(t, p["Item"], (p["X"], p["Y"]) if p["X"] is not None else None, p.get("Detail") or "")
    else:
        for n, v in net["nodes"].items():
            if v.get("ground") is None:
                add("no ground level", n, _xy(net, n))
    cnt = collections.Counter(k["label"] for k in net["conduits"])
    for lab, c in cnt.items():
        if c > 1:
            add("conduit label used twice", lab, None, f"{c} conduits")
    adj = _adj(net)
    for n, nbs in adj.items():
        g = _ground(net, n)
        gn = [_ground(net, m) for m, _ in nbs if _ground(net, m) is not None]
        if g is not None and gn and (all(g - x > GL_SPIKE_M for x in gn) or all(x - g > GL_SPIKE_M for x in gn)):
            add("GL spike (> 2 m from all neighbours)", n, _xy(net, n),
                f"GL {g:.2f}, neighbours {', '.join(f'{x:.2f}' for x in gn)}")
    for k in net["conduits"]:
        if (k.get("length_m") or 0) < SHORT_CONDUIT_M:
            P = _pts(net, k)
            add("very short conduit", k["label"], P[0] if P else None, f"{k.get('length_m') or 0:.2f} m")
    for a, b, d in overlaps(net):
        cut = next((h for h, o in ((a, b), (b, a)) if h.startswith(o + "-C") and h[len(o) + 2:].isdigit()), None)
        add(OVERLAP, f"{a} - {b}", _xy(net, a),
            f"{d:.2f} m apart, no sewer between them" + (f" - {cut} is a loop cut head: join it with a sewer if the "
                                                          f"loop is real (or move it)" if cut else ""))
    if not gravity:
        return out
    # loops: conduits a BFS forest does not use
    tmp = _copy(net)
    log = []
    cut_loops(tmp, list(outfalls), log)
    for r in log:
        add("loop", r["item"].split(" from ")[0], (r["x"], r["y"]) if r["x"] is not None else None, r["item"])
    for r in parts_report(net, list(outfalls)):
        if r["outfalls"] == "NONE":
            add("part without an outfall", f"part {r['part']} ({r['manholes']} MH, {r['sewer length (m)']:.0f} m)",
                _xy(net, r["lowest manhole"]), f"lowest {r['lowest manhole']} (GL {r['its GL']}); {r['nearest other parts']}")
    return out


def repair(net, ex=None, outfalls=(), join_gap_m=1.0, tjoint_m=0.5, loops=True, gl=True):
    """(repaired copy of net, log rows {"repair", "item", "x", "y", "detail"})."""
    net = _copy(net)
    if outfalls:
        net["outfalls"] = list(outfalls)
    log = []
    rename_duplicates(net, log)
    if ex and join_gap_m:
        gaps = []
        for p in ex["problems"]:
            if p["Problem"].startswith("near-miss gap"):
                a, _, b = str(p["Item"]).partition(" - ")
                try:
                    d = float(str(p["Detail"]).split()[0])
                except (ValueError, IndexError):
                    continue
                gaps.append((a.strip(), b.strip(), d))
        join_gaps(net, gaps, join_gap_m, log)
    if tjoint_m:
        split_tjoints(net, tjoint_m, log)
    if loops:
        cut_loops(net, net["outfalls"], log)
    if gl:
        fill_gl(net, log)
    return net, log


# ---------------------------------------------------------------- output
MARK_LAYERS = {   # issue / repair type: (layer, AutoCAD colour)
    "no ground level": ("CHK_NO_GL", 1), "ground level interpolated along the sewer": ("CHK_GL_INTERPOLATED", 30),
    "NOT filled: no ground level anywhere in this part": ("CHK_NO_GL", 1),
    "no drawing label (name generated)": ("CHK_NO_LABEL", 2), "label matched in pass 2 - CHECK": ("CHK_LABEL_PASS2", 1),
    "label matched in pass 2 - low risk": ("CHK_LABEL_PASS2_LOWRISK", 8),
    "GL matched in pass 2 - CHECK": ("CHK_GL_PASS2", 1), "GL matched in pass 2 - low risk": ("CHK_GL_PASS2_LOWRISK", 8),
    "manhole on a continuous line - check": ("CHK_MIDLINE", 6),
    "near-miss gap": ("CHK_GAP", 1), "near-miss gap joined": ("CHK_GAP_JOINED", 3), "T-joint": ("CHK_TJOINT", 1),
    "T-joint: line split at a manhole": ("CHK_TJOINT_SPLIT", 3), "loop": ("CHK_LOOP", 1),
    "loop: conduit disconnected at its higher end": ("CHK_LOOP_CUT", 3),
    "GL spike (> 2 m from all neighbours)": ("CHK_GL_SPIKE", 1), "part without an outfall": ("CHK_PART", 1),
    "very short conduit": ("CHK_SHORT", 8), "label used twice in the drawing": ("CHK_LABEL_TWICE", 1),
}


def write_check(issues, log, xlsx_path, dxf_path=None, parts=None, text_h=1.0):
    """Excel (Summary, Issues, Repairs, Parts) and a marker DXF in the drawing's coordinates (XREF / INSERT it on the
    original drawing): a circle + short text per issue / repair, one layer per kind."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    wb = Workbook()
    bold, head = Font(bold=True), PatternFill("solid", fgColor="D9E1F2")
    ws = wb.active
    ws.title = "Summary"
    ws.append(["Kind", "Count", "What to do"])
    todo = {"no ground level": "filled along the sewer by the repair - check the drawing / survey",
            "label matched in pass 2 - CHECK": "check the label in CAD (its number does not fit its neighbours)",
            "label matched in pass 2 - low risk": "probably right: its number is within 2 of a neighbour's",
            "GL matched in pass 2 - CHECK": "check the GL in CAD (more than 1 m from its neighbours' mean)",
            "GL matched in pass 2 - low risk": "probably right: within 1 m of its neighbours' mean",
            "manhole on a continuous line - check": "a manhole label lay on a line: the line was cut there - check",
            "near-miss gap": "joined by the repair when short; else join or leave in CAD",
            "part without an outfall": "give it an outfall (lowest manhole / pumping) or join it to another part",
            "GL spike (> 2 m from all neighbours)": "probably a wrong level - check", "loop": "cut by the repair"}
    for k, n in collections.Counter(i["type"] for i in issues).most_common():
        ws.append([k, n, todo.get(k, "")])
    ws.append([])
    ws.append(["Repairs", "Count"])
    for k, n in collections.Counter(r["repair"] for r in log).most_common():
        ws.append([k, n])
    for c in ws[1]:
        c.font, c.fill = bold, head
    ws.column_dimensions["A"].width, ws.column_dimensions["C"].width = 48, 80
    for title, rows, cols in (("Issues", issues, ["type", "item", "x", "y", "detail"]),
                              ("Repairs", log, ["repair", "item", "x", "y", "detail"]),
                              ("Parts", parts or [], list((parts or [{}])[0].keys()))):
        sh = wb.create_sheet(title)
        sh.append(cols or ["(none)"])
        for c in sh[1]:
            c.font, c.fill = bold, head
        for r in rows:
            sh.append([r.get(c) for c in cols])
        sh.freeze_panes = "A2"
        for col, w in zip("ABCDE", (44, 30, 13, 13, 70)):
            sh.column_dimensions[col].width = w
    wb.save(xlsx_path)
    if dxf_path:
        import ezdxf
        doc = ezdxf.new("R2010", setup=True)
        msp = doc.modelspace()
        for kind, rows in (("issue", issues), ("repair", log)):
            for r in rows:
                t = r.get("type") or r.get("repair")
                if r.get("x") is None:
                    continue
                lay, col = MARK_LAYERS.get(t, ("CHK_OTHER", 7))
                if lay not in doc.layers:
                    doc.layers.add(lay, color=col)
                msp.add_circle((r["x"], r["y"]), 2.5 * text_h, dxfattribs={"layer": lay})
                msp.add_text(f"{t}: {r['item']}", height=text_h, dxfattribs={"layer": lay}).set_placement(
                    (r["x"] + 3 * text_h, r["y"] - 3 * text_h))
        try:
            from ezdxf import zoom
            doc.header["$TILEMODE"] = 1
            zoom.extents(msp)
        except Exception:
            pass
        doc.saveas(dxf_path)
    return xlsx_path
