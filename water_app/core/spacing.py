"""WATER MODULE COPY of sewer_app/spacing.py (isolation of sewer and water, user request 21-Oct-2026): changes here do not\nreach the sewer module, nor the reverse. Water rules are written in directly (a water main network keeps its loops\nand has no outfalls)."""
import collections
import math
import re


def plen_of(poly):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(poly, poly[1:]))


def point_at(poly, ch):
    """Point at chainage ch (m) along a polyline (coordinate units = model units, assumed m)."""
    run = 0.0
    for (x1, y1), (x2, y2) in zip(poly, poly[1:]):
        seg = math.hypot(x2 - x1, y2 - y1)
        if seg and run + seg >= ch:
            t = (ch - run) / seg
            return x1 + t * (x2 - x1), y1 + t * (y2 - y1)
        run += seg
    return poly[-1]


def sub_poly(poly, a, b):
    """Part of a polyline between distances a and b along it (vertices in between kept)."""
    pts, run = [point_at(poly, a)], 0.0
    for p, q in zip(poly, poly[1:]):
        run += math.hypot(q[0] - p[0], q[1] - p[1])
        if a + 1e-6 < run < b - 1e-6:
            pts.append(q)
    pts.append(point_at(poly, b))
    return pts


def label_namer(labels, fallback_prefix):
    """Returns a function giving the next free label in the network's own naming style: the most common
    '<prefix><number>' pattern among the existing labels (e.g. MH-253 -> MH-254, CO-254 -> CO-255),
    zero-padding kept; fallback_prefix if no label has that form."""
    pat = re.compile(r"^(.*?)(\d+)$")
    existing, count, top, pad = set(), collections.Counter(), {}, {}
    for lab in labels:
        existing.add(lab)
        m = pat.match(lab)
        if m:
            p, digits = m.group(1), m.group(2)
            count[p] += 1
            top[p] = max(top.get(p, 0), int(digits))
            if digits.startswith("0") and len(digits) > 1:
                pad[p] = max(pad.get(p, 0), len(digits))
    prefix = count.most_common(1)[0][0] if count else fallback_prefix
    state = {"n": top.get(prefix, 0)}
    width = pad.get(prefix, 0)

    def nxt():
        while True:
            state["n"] += 1
            lab = f"{prefix}{str(state['n']).zfill(width)}"
            if lab not in existing:
                existing.add(lab)
                return lab
    return nxt
