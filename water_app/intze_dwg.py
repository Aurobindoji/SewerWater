"""Drawings of an Intze OHT designed by intze.py, laid out as the drawings of the user's example (Brookfield Consultants,
TCP-250510/OPG-1..3, the 2700 KL tank of zone 14; user decisions 10-Nov-2026): one DXF (A1 sheets side by side in
model space, paper mm, each view at the scale written under it) and the same sheets as a PDF; the design calculation,
the bar bending schedule and the quantities as an xlsx.

Sheet 1 staging and foundation: half section / half elevation with the staircase, half foundation plan / half plan
at brace level, section and part reinforcement plan of the raft, L-sections of the foundation ring beam and of a
brace, column section, notes. Sheet 2 container: section of the tank with its bars, top ring beam, L-section of the
bottom ring beam, part plans of the domes' reinforcement, ventilator, manhole, ladder, pipe fixing. Sheet 3 staircase.
Sheet 4+ bar bending schedule and quantities. Bars are written as on the example: "408 - 25 # RADIALLY @ 150 C/C".
"""
import datetime
import math
import os

import ezdxf
from ezdxf.enums import TextEntityAlignment as TA

from . import intze

SW, SH = 841.0, 594.0           # A1 landscape, mm
GAP = 100.0
SCALES = (5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100, 125, 150, 200, 250, 300, 400, 500)
LAYERS = {  # name: (ACI colour, lineweight 1/100 mm, linetype)
    "FRAME": (7, 70, "Continuous"), "OUTLINE": (7, 35, "Continuous"), "THIN": (7, 13, "Continuous"),
    "HIDDEN": (8, 13, "DASHED"), "CENTER": (8, 9, "CENTER"), "HATCH": (8, 5, "Continuous"),
    "REBAR": (1, 25, "Continuous"), "REBAR2": (1, 9, "Continuous"), "DIM": (5, 9, "Continuous"),
    "TEXT": (7, 13, "Continuous"), "WATER": (4, 13, "DASHED"), "LEVEL": (3, 13, "Continuous"),
}
WARN = "Design for the DPR made by the app - to be checked and signed by a structural engineer before construction."
B, BI = "LiberationSans-Bold", "LiberationSans"


def fit_scale(real_w_m, real_h_m, box_w, box_h):
    for s in SCALES:
        if real_w_m * 1000.0 / s <= box_w and real_h_m * 1000.0 / s <= box_h:
            return s
    return SCALES[-1]


def arc_pts(cx, cz, r, a0, a1, n=40):
    return [(cx + r * math.cos(a0 + (a1 - a0) * i / n), cz + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]


def nb(m):
    """(n, dia) -> '7 - 20 #'"""
    return f"{m[0]} - {m[1]} #"


def at(m, what=""):
    """(dia, spacing) -> '10 # RADIALLY @ 195 C/C'"""
    return f"{m[0]} # {what + ' ' if what else ''}@ {m[1]} C/C"


def ordinal(k):
    return f"{k}{'TH' if 10 <= k % 100 <= 20 else {1: 'ST', 2: 'ND', 3: 'RD'}.get(k % 10, 'TH')}"


class Sheet:
    """One A1 sheet in model space (paper mm); remembers its entities for the PDF page."""

    def __init__(self, dw, index, title, no):
        self.dw, self.msp = dw, dw.msp
        self.ox, self.oy = index * (SW + GAP), 0.0
        self.handles = set()
        self.title, self.no = title, no

    def _k(self, e):
        self.handles.add(e.dxf.handle)
        return e

    def P(self, x, y):
        return (self.ox + x, self.oy + y)

    def line(self, p, q, layer="OUTLINE"):
        return self._k(self.msp.add_line(self.P(*p), self.P(*q), dxfattribs={"layer": layer}))

    def poly(self, pts, layer="OUTLINE", closed=False):
        return self._k(self.msp.add_lwpolyline([self.P(*p) for p in pts], close=closed, dxfattribs={"layer": layer}))

    def rect(self, x1, y1, x2, y2, layer="OUTLINE"):
        return self.poly([(x1, y1), (x2, y1), (x2, y2), (x1, y2)], layer, True)

    def circle(self, c, r, layer="OUTLINE"):
        return self._k(self.msp.add_circle(self.P(*c), r, dxfattribs={"layer": layer}))

    def dot(self, c, r=0.45):
        self.__dict__.setdefault("dotlist", []).append((c, r))
        h = self.msp.add_hatch(color=1, dxfattribs={"layer": "REBAR"})
        h.paths.add_edge_path().add_arc(self.P(*c), r, 0, 360)
        return self._k(h)

    def hatch(self, pts, scale=0.5, pattern="ANSI31"):
        h = self.msp.add_hatch(color=8, dxfattribs={"layer": "HATCH"})
        h.set_pattern_fill(pattern, scale=scale)
        h.paths.add_polyline_path([self.P(*p) for p in pts], is_closed=True)
        return self._k(h)

    def text(self, s, p, h=2.2, align=TA.MIDDLE_LEFT, layer="TEXT", rot=0.0, style=BI):
        t = self.msp.add_text(str(s), height=h, rotation=rot, dxfattribs={"layer": layer, "style": style})
        t.set_placement(self.P(*p), align=align)
        return self._k(t)

    def lines(self, rows, x, y, h=2.2, step=None, style=BI, align=TA.MIDDLE_LEFT):
        step = step or h * 1.55
        for i, s in enumerate(rows):
            self.text(s, (x, y - i * step), h, align, style=style)
        return y - len(rows) * step

    def dim_h(self, x1, x2, y, label, y_from=None, h=1.9, below=False):
        if y_from is not None:
            for x in (x1, x2):
                self.line((x, y_from), (x, y + (1.2 if y > y_from else -1.2)), "DIM")
        self.line((x1, y), (x2, y), "DIM")
        for x in (x1, x2):
            self.line((x - 0.8, y - 0.8), (x + 0.8, y + 0.8), "DIM")
        self.text(label, ((x1 + x2) / 2.0, y + (-1.0 if below else 1.0)), h, TA.TOP_CENTER if below else TA.BOTTOM_CENTER, "DIM")

    def dim_across(self, p, q, label, h=1.7, off=0.0):
        """A dimension across a member from p to q (paper mm), its text beside the line, along it."""
        L = math.dist(p, q)
        if L < 1e-6:
            return
        ux, uy = (q[0] - p[0]) / L, (q[1] - p[1]) / L
        a = 1.2
        p2, q2 = (p[0] - ux * a, p[1] - uy * a), (q[0] + ux * a, q[1] + uy * a)
        self.line(p2, q2, "DIM")
        for c in (p, q):
            self.line((c[0] - 0.7 * (ux - uy), c[1] - 0.7 * (uy + ux)), (c[0] + 0.7 * (ux - uy), c[1] + 0.7 * (uy + ux)), "DIM")
        ang = math.degrees(math.atan2(uy, ux))
        if ang > 90 or ang <= -90:
            ang -= 180 if ang > 0 else -180
        m = (q2[0] + ux * 0.6, q2[1] + uy * 0.6)
        self.text(label, m, h, TA.MIDDLE_LEFT if ux >= 0 else TA.MIDDLE_RIGHT, "DIM", rot=ang)

    def dim_v(self, y1, y2, x, label, x_from=None, h=1.9):
        if x_from is not None:
            for y in (y1, y2):
                self.line((x_from, y), (x + (1.2 if x > x_from else -1.2), y), "DIM")
        self.line((x, y1), (x, y2), "DIM")
        for y in (y1, y2):
            self.line((x - 0.8, y - 0.8), (x + 0.8, y + 0.8), "DIM")
        self.text(label, (x - 1.0, (y1 + y2) / 2.0), h, TA.BOTTOM_CENTER, "DIM", rot=90)

    def level(self, x, y, label, left=False, h=1.9):
        s = 1.6
        self.poly([(x, y), (x - s, y + s * 1.5), (x + s, y + s * 1.5)], "LEVEL", True)
        self.line((x - (9 if left else 0), y), (x + (0 if left else 9), y), "LEVEL")
        self.text(label, (x + (-2.6 if left else 2.6), y + 0.8), h, TA.BOTTOM_RIGHT if left else TA.BOTTOM_LEFT, "LEVEL")

    def leader(self, p, q, label, h=1.9, right=True, ring=0.35):
        """A note with a line to the point p, a circle of radius `ring` round it (round the bar when p is a bar)."""
        L = math.dist(p, q)
        e = (p[0] + (q[0] - p[0]) * ring / L, p[1] + (q[1] - p[1]) * ring / L) if L > ring else p
        self.line(e, q, "DIM")
        self.circle(p, ring, "DIM")
        self.line(q, (q[0] + (2.5 if right else -2.5), q[1]), "DIM")
        rows = label if isinstance(label, (list, tuple)) else [label]
        for i, s in enumerate(rows):
            self.text(s, (q[0] + (3.2 if right else -3.2), q[1] - i * h * 1.5), h, TA.MIDDLE_LEFT if right else TA.MIDDLE_RIGHT)

    def leader_rows(self, dots, r, q, label, h=1.9, right=True):
        """A leader to the bars of a beam face laid in layers (bar_row's dots): a circle round the end bar of every
        layer, the circles joined, the line to the note from the layer nearest it."""
        rows = {}
        for d in dots:
            rows.setdefault(round(d[1], 3), []).append(d)
        ends = [max(v, key=lambda d: d[0]) for _, v in sorted(rows.items())]
        ring = r + 0.45
        for a_, b_ in zip(ends, ends[1:]):
            L = math.dist(a_, b_)
            if L > 2 * ring:
                u = ((b_[0] - a_[0]) / L, (b_[1] - a_[1]) / L)
                self.line((a_[0] + u[0] * ring, a_[1] + u[1] * ring), (b_[0] - u[0] * ring, b_[1] - u[1] * ring), "DIM")
        near = min(ends, key=lambda e: math.dist(e, q))
        for e in ends:
            if e is not near:
                self.circle(e, ring, "DIM")
        self.leader(near, q, label, h, right, ring=ring)

    def leader_bar(self, p, q, label, h=1.9, right=True, near=8.0):
        """A leader to a bar: the circle round the bar dot nearest p (within `near` mm), else an ordinary leader."""
        best = min(self.__dict__.get("dotlist", []), key=lambda d: math.dist(d[0], p), default=None)
        if best and math.dist(best[0], p) <= near:
            return self.leader(best[0], q, label, h, right, ring=best[1] + 0.45)
        return self.leader(p, q, label, h, right)

    def heading(self, s, p, h=3.0, sub=None):
        self.text(s, p, h, TA.BOTTOM_CENTER, style=B)
        w = len(s) * h * 0.66
        self.line((p[0] - w / 2, p[1] - 0.9), (p[0] + w / 2, p[1] - 0.9), "THIN")
        if sub:
            self.text(sub, (p[0], p[1] - 1.8), h * 0.65, TA.TOP_CENTER)

    def frame(self, info):
        self.rect(0, 0, SW, SH, "THIN")
        self.rect(10, 10, SW - 10, SH - 10, "FRAME")
        x0, y0, w = SW - 10 - 190, 10.0, 190.0
        self.rect(x0, y0, x0 + w, y0 + 62, "FRAME")
        for y in (y0 + 50, y0 + 38, y0 + 26, y0 + 14):
            self.line((x0, y), (x0 + w, y), "THIN")
        self.text(info.get("scheme") or "WATER SUPPLY SCHEME", (x0 + w / 2, y0 + 56), 3.0, TA.MIDDLE_CENTER, style=B)
        self.text(f"{info['name']}: R.C.C. INTZE TANK {info['cap']:g} KL ON {info['stg']:g} m STAGING",
                  (x0 + w / 2, y0 + 44), 2.6, TA.MIDDLE_CENTER)
        self.text(self.title, (x0 + w / 2, y0 + 32), 3.2, TA.MIDDLE_CENTER, style=B)
        self.text(f"DRG. NO. {info['dwg_no']} - {self.no}", (x0 + 3, y0 + 20), 2.4)
        self.text(f"DATE: {info['date']}", (x0 + w - 3, y0 + 20), 2.4, TA.MIDDLE_RIGHT)
        self.text("ALL DIMENSIONS IN mm, LEVELS IN m ABOVE G.L.; SCALES AS SHOWN", (x0 + 3, y0 + 8), 2.0)
        self.text(f"Sheet {self.no} of {info['sheets']}", (x0 + w - 3, y0 + 8), 2.4, TA.MIDDLE_RIGHT)
        self.text(WARN, (14, 13.5), 2.4, style=B)


class View:
    """Real metres -> paper mm on a sheet: x = horizontal (radius), z = level."""

    def __init__(self, sh, x0, y0, scale, X0=0.0, Z0=0.0):
        self.sh, self.x0, self.y0, self.s, self.X0, self.Z0 = sh, x0, y0, scale, X0, Z0
        self.k = 1000.0 / scale

    def p(self, X, Z):
        return (self.x0 + (X - self.X0) * self.k, self.y0 + (Z - self.Z0) * self.k)

    def line(self, a, b, layer="OUTLINE"):
        return self.sh.line(self.p(*a), self.p(*b), layer)

    def poly(self, pts, layer="OUTLINE", closed=False):
        return self.sh.poly([self.p(*q) for q in pts], layer, closed)

    def rect(self, x1, z1, x2, z2, layer="OUTLINE", hatch=False):
        return self.shape([(x1, z1), (x2, z1), (x2, z2), (x1, z2)], layer, hatch)

    def shape(self, pts, layer="OUTLINE", hatch=False):
        if hatch:
            self.sh.hatch([self.p(*q) for q in pts])
        return self.poly(pts, layer, True)

    def circle(self, c, r, layer="OUTLINE"):
        return self.sh.circle(self.p(*c), r * self.k, layer)

    def dots(self, pts, spacing, r=0.4, first=None):
        """Bar dots along the polyline every `spacing` m."""
        acc, nxt = 0.0, spacing / 2.0 if first is None else first
        for (x1, z1), (x2, z2) in zip(pts, pts[1:]):
            L = math.dist((x1, z1), (x2, z2))
            while L > 0 and nxt <= acc + L:
                t = (nxt - acc) / L
                self.sh.dot(self.p(x1 + (x2 - x1) * t, z1 + (z2 - z1) * t), r)
                nxt += spacing
            acc += L


def _info(res, meta):
    m = meta or {}
    return {"name": m.get("name") or "OHT", "cap": res["capacity_kl"], "stg": res["staging_m"],
            "scheme": m.get("scheme") or "", "dwg_no": m.get("dwg_no") or (m.get("name") or "OHT"),
            "date": m.get("date") or datetime.date.today().strftime("%d.%m.%Y"), "sheets": 4}


# ------------------------------------------------------------------------------------------------- geometry helpers
def _shapes(res):
    """Outlines (real m, radius / level) of the container's members on the side r >= 0, and the domes' circles."""
    g, lev, th = res["geo"], res["levels"], res["geo"]["th"]
    R, r0, sa = g["R"], g["r0"], math.sin(g["alpha"])
    S = {}
    d1 = intze._dome(R, g["h1"])
    zc1, R1, t1 = lev["B1_top"] + g["h1"] - d1["R"], d1["R"], d1["th"]
    ex1 = lambda t: (th["t1e"] - th["t1"]) * max(0.0, 1.0 - R1 * (t1 - t) / th["edge"])
    S["top_dome"] = ([((R1 + th["t1"]) * math.sin(t1 * (1 - i / 40.0)), zc1 + (R1 + th["t1"]) * math.cos(t1 * (1 - i / 40.0))) for i in range(41)]
                     + [((R1 - ex1(t1 * i / 40.0)) * math.sin(t1 * i / 40.0), zc1 + (R1 - ex1(t1 * i / 40.0)) * math.cos(t1 * i / 40.0)) for i in range(41)])
    S["dome1"] = (zc1, R1, t1)
    S["B1"] = [(R, lev["wall_top"]), (R + th["b1"], lev["wall_top"]), (R + th["b1"], lev["B1_top"]), (R, lev["B1_top"])]
    zt = min(lev["B2_top"] + th["taper"], lev["wall_top"])
    S["wall"] = [(R, lev["B2_top"]), (R + th["twb"], lev["B2_top"]), (R + th["tw"], zt), (R + th["tw"], lev["wall_top"]), (R, lev["wall_top"])]
    S["ring"] = [(R, lev["cone_top"]), (g["bal_edge"], lev["cone_top"]), (g["bal_edge"], lev["B2_top"]), (R, lev["B2_top"])]
    S["cone"] = [(r0, lev["LWL"]), (R, lev["cone_top"]), (R + th["t0"] / sa, lev["cone_top"]), (r0 + th["t0"] / sa, lev["LWL"])]
    S["B3"] = [(r0 - th["b3"] / 2, lev["B3_bot"]), (r0 + th["b3"] / 2, lev["B3_bot"]), (r0 + th["b3"] / 2, lev["LWL"]), (r0 - th["b3"] / 2, lev["LWL"])]
    d2 = intze._dome(r0, g["h2"])
    zc2, R2, t2 = lev["LWL"] + g["h2"] - d2["R"], d2["R"], d2["th"]
    ex2 = lambda t: (th["t2e"] - th["t2"]) * max(0.0, 1.0 - R2 * (t2 - t) / th["edge"])
    S["bottom_dome"] = ([(R2 * math.sin(t2 * (1 - i / 40.0)), zc2 + R2 * math.cos(t2 * (1 - i / 40.0))) for i in range(41)]
                        + [((R2 - th["t2"] - ex2(t2 * i / 40.0)) * math.sin(t2 * i / 40.0), zc2 + (R2 - th["t2"] - ex2(t2 * i / 40.0)) * math.cos(t2 * i / 40.0)) for i in range(41)])
    S["dome2"] = (zc2, R2, t2)
    return S


def _container_outline(res):
    """The container's half section as ONE closed outline (user 10-Nov-2026: the concrete surfaces merged, no member
    drawn over another): from the top dome's crown round the outside - top ring beam, wall (its taper), balcony,
    cone, bottom ring beam - to the bottom dome's soffit, up the axis, and back round the water face."""
    g, lev, th = res["geo"], res["levels"], res["geo"]["th"]
    S = _shapes(res)
    R, r0, al = g["R"], g["r0"], g["alpha"]
    sa, ta = math.sin(al), math.tan(al)
    zc1, R1, a1 = S["dome1"]
    zc2, R2, a2 = S["dome2"]
    Ru = R1 + th["t1"]
    xb1 = R + max(th["b1"], th["tw"])
    out = []
    # top dome's upper surface, crown to where it meets the top ring beam's top (or its outer face)
    if Ru ** 2 - (lev["B1_top"] - zc1) ** 2 > 0 and math.sqrt(Ru ** 2 - (lev["B1_top"] - zc1) ** 2) <= xb1:
        xe = math.sqrt(Ru ** 2 - (lev["B1_top"] - zc1) ** 2)
        end = (xe, lev["B1_top"])
    else:
        end = (xb1, zc1 + math.sqrt(max(0.0, Ru ** 2 - xb1 ** 2)))
    ae = math.atan2(end[0], end[1] - zc1)                       # from the vertical
    out += [(Ru * math.sin(ae * i / 40), zc1 + Ru * math.cos(ae * i / 40)) for i in range(41)]
    if end[1] >= lev["B1_top"] - 1e-9:
        out.append((xb1, lev["B1_top"]))
    zt = min(lev["B2_top"] + th["taper"], lev["wall_top"])
    out += [(xb1, lev["wall_top"]), (R + th["tw"], lev["wall_top"]), (R + th["tw"], zt), (R + th["twb"], lev["B2_top"]),
            (g["bal_edge"], lev["B2_top"]), (g["bal_edge"], lev["cone_top"])]
    xct = R + th["t0"] / sa                                      # the cone's outer face at the balcony's soffit
    out.append((xct, lev["cone_top"]))
    xo3, xi3 = r0 + th["b3"] / 2, r0 - th["b3"] / 2
    zo = lev["cone_top"] - (xct - xo3) * ta                     # the cone's outer face at the beam's outer face
    if zo >= lev["LWL"]:
        out.append((xo3, zo))
    else:
        out += [(r0 + th["t0"] / sa, lev["LWL"]), (xo3, lev["LWL"])]
    out += [(xo3, lev["B3_bot"]), (xi3, lev["B3_bot"])]
    # the bottom dome's soffit (edge thickening), from the beam's inner face to the crown
    soff = S["bottom_dome"][41:][::-1]                           # edge -> crown
    k = next((i for i, q in enumerate(soff) if q[0] <= xi3), len(soff) - 1)
    if k > 0:
        (x1, z1), (x2, z2) = soff[k - 1], soff[k]
        t = (x1 - xi3) / (x1 - x2) if x1 != x2 else 0.0
        out.append((xi3, z1 + (z2 - z1) * t))
    out += soff[k:]
    # up the axis; the dome's upper surface, crown to the trough at the bottom ring
    top2 = S["bottom_dome"][:41][::-1]                           # crown -> edge, ends at (r0, LWL)
    out += top2
    # the cone's inner face, the wall's inner face, the top dome's soffit back to its crown
    out += [(R, lev["cone_top"]), (R, lev["wall_top"])]
    soff1 = S["top_dome"][41:][::-1]                             # edge -> crown
    out.append((R, max(soff1[0][1], lev["wall_top"])))
    out += soff1
    return out


def _angles(res):
    """Columns at (i + 1/2) 2 pi / n: two of them either side of the +x axis (the staircase's side)."""
    n = res["geo"]["n_col"]
    return [(i + 0.5) * 2.0 * math.pi / n for i in range(n)]


def _raft_t(res, r):
    """Thickness of the raft (m) at the radius r."""
    g, rf = res["geo"], res["members"]["raft"]
    t, te, r0, bR = rf["t"] / 1e3, rf["te"] / 1e3, g["r0"], rf["bR"]
    if r >= r0 + bR / 2:
        return te + (t - te) * (rf["Ro"] - r) / max(rf["ao"], 1e-6)
    if r <= r0 - bR / 2:
        return te + (t - te) * (r - rf["Ri"]) / max(rf["ai"], 1e-6)
    return t


def _raft_outline(res, sgn=1.0):
    g, lev, rf = res["geo"], res["levels"], res["members"]["raft"]
    zb, t, te, r0, bR = lev["raft_bot"], rf["t"] / 1e3, rf["te"] / 1e3, g["r0"], rf["bR"]
    return [(sgn * rf["Ro"], zb), (sgn * rf["Ri"], zb), (sgn * rf["Ri"], zb + (te if rf["Ri"] else t if rf["ai"] <= 0 else te)),
            (sgn * (r0 - bR / 2), zb + t), (sgn * (r0 + bR / 2), zb + t), (sgn * rf["Ro"], zb + te)]


# ------------------------------------------------------------------------------------------- sheet 1: the whole tank
def _ga(sh, res, x0, y0, bw, bh):
    g, lev, th, M = res["geo"], res["levels"], res["geo"]["th"], res["members"]
    st = M.get("stair")
    R, r0, Ro, dc = g["R"], g["r0"], g["Ro"], g["dc"]
    left = max(Ro, g["bal_edge"]) + 0.6
    right = (st["xs"] + st["gap"] / 2 + st["w"] + 0.6) if st else left
    top, bot = lev["dome1_crown"] + 2.0, lev["raft_bot"] - 1.6
    padl, padr = 44.0, 30.0
    s = next((k for k in SCALES if (left + right) * 1000.0 / k + padl + padr <= bw and (top - bot) * 1000.0 / k + 14 <= bh), SCALES[-1])
    v = View(sh, x0 + padl + left * 1000.0 / s, y0 + 14, s, 0.0, bot)
    S = _shapes(res)
    # ground
    v.line((-left, 0), (right, 0))
    for i in range(int((left + right) / 0.6)):
        x = -left + i * 0.6
        v.line((x, 0), (x - 0.3, -0.3), "THIN")
    sh.text("G.L.", v.p(right - 0.2, 0.25), 1.8, TA.BOTTOM_RIGHT)
    # raft: section left, outline right; lean concrete
    v.shape(_raft_outline(res, -1.0), hatch=True)
    v.poly(_raft_outline(res, 1.0), "HIDDEN", True)
    v.rect(-Ro - 0.1, lev["raft_bot"] - 0.1, -g["Ri"] + 0.1, lev["raft_bot"], "THIN")
    # columns and braces
    xs_cols = sorted({round(r0 * math.cos(a), 4) for a in _angles(res) if math.cos(a) > 1e-9})
    for sgn in (-1, 1):
        for x in xs_cols:
            v.rect(sgn * x - dc / 2, lev["raft_top"], sgn * x + dc / 2, lev["B3_bot"], hatch=(sgn < 0 and x == xs_cols[-1]))
        for z in g["braces"]:
            for xa, xb in zip(xs_cols, xs_cols[1:]):
                if xb - xa > dc:
                    v.rect(sgn * (xa + dc / 2), z - g["db"] / 2, sgn * (xb - dc / 2), z + g["db"] / 2)
            v.rect(sgn * 0.0, z - g["db"] / 2, sgn * (xs_cols[0] - dc / 2), z + g["db"] / 2)
    # container: section on the left
    v.shape([(-x, z) for x, z in _container_outline(res)], hatch=True)
    v.line((-R, lev["FSL"]), (0, lev["FSL"]), "WATER")
    sh.text("F.S.L.", v.p(-R * 0.5, lev["FSL"] + 0.15), 1.7, TA.BOTTOM_CENTER, "WATER")
    # elevation on the right
    v.poly(S["top_dome"][:41])
    for z, x in ((lev["wall_top"], R + th["b1"]), (lev["B1_top"], R + th["b1"]), (lev["cone_top"], g["bal_edge"]),
                 (lev["B2_top"], g["bal_edge"]), (lev["LWL"], r0 + th["b3"] / 2), (lev["B3_bot"], r0 + th["b3"] / 2)):
        v.line((0, z), (x, z))
    v.line((R + th["b1"], lev["wall_top"]), (R + th["b1"], lev["B1_top"]))
    v.poly(S["wall"][1:4])
    v.line((g["bal_edge"], lev["cone_top"]), (g["bal_edge"], lev["B2_top"]))
    v.line(S["cone"][2], (r0 + th["b3"] / 2, lev["LWL"]))
    v.line((r0 + th["b3"] / 2, lev["LWL"]), (r0 + th["b3"] / 2, lev["B3_bot"]))
    for k in range(6):                                           # railing of the balcony
        x = g["bal_edge"] - 0.05 - k * (g["bal_edge"] - R - th["twb"]) / 5.0
        v.line((x, lev["B2_top"]), (x, lev["B2_top"] + 1.0), "THIN")
    v.line((R + th["twb"], lev["B2_top"] + 1.0), (g["bal_edge"] - 0.05, lev["B2_top"] + 1.0), "THIN")
    # ventilator and lightning conductor
    v.rect(-0.75, lev["dome1_crown"] + th["t1"], 0.75, lev["dome1_crown"] + th["t1"] + 0.7)
    v.line((0, lev["dome1_crown"] + 0.8), (0, lev["dome1_crown"] + 1.7))
    sh.leader(v.p(0.1, lev["dome1_crown"] + 1.5), v.p(2.0, lev["dome1_crown"] + 1.6), "LIGHTNING CONDUCTOR", 1.7)
    sh.leader(v.p(0.6, lev["dome1_crown"] + 0.5), v.p(2.0, lev["dome1_crown"] + 0.75), "VENTILATOR", 1.7)
    v.line((0, bot + 0.6), (0, top - 0.2), "CENTER")
    # the staircase, in elevation
    if st:
        xs, lc, ds = st["xs"], st["lc"], st["col"]["d"] / 1e3
        fs = st["footing"]["side"]
        zf = lev["raft_bot"] + 0.6
        v.rect(xs - fs / 2, zf - 0.6, xs + fs / 2, zf, "HIDDEN")
        v.rect(xs - ds / 2, zf, xs + ds / 2, st["roof"])
        z_prev, n1 = 0.0, st["n1"]
        for k, z in enumerate(st["levels"], 1):
            inner = (n1 - k) % 2 == 0
            xa, xb = (xs - st["gap"] / 2 - st["w"], xs - st["gap"] / 2) if inner else (xs + st["gap"] / 2, xs + st["gap"] / 2 + st["w"])
            v.rect(xa, z_prev, xb, z)
            for j in range(1, st["risers"]):
                zz = z_prev + (z - z_prev) * j / st["risers"]
                v.line((xa, zz), (xb, zz), "THIN")
            bd = st["beam"]["d"] / 1e3
            x_from = (xs_cols[-1] + dc / 2) if z <= lev["B3_bot"] + 0.5 else g["bal_edge"] if z > lev["B2_top"] + 0.1 else xs - lc
            v.rect(min(x_from, xs - lc), z - bd, xs + lc, z)
            xr = v.p(xs + lc + 0.4, z)
            sh.text(f"RL = {z * 1e3:.0f}", (xr[0], xr[1]), 1.6, TA.MIDDLE_LEFT)
            sh.text(f"{ordinal(k)} FLIGHT", (xr[0], v.p(0, (z + z_prev) / 2)[1]), 1.4, TA.MIDDLE_LEFT)
            z_prev = z
    # levels on the left
    xl = v.p(-left, 0)[0] - 1.0
    for name, z in (("TOP OF DOME", lev["dome1_crown"] + th["t1"]), ("TOP OF RING BEAM", lev["B1_top"]), ("F.S.L.", lev["FSL"]),
                    ("BALCONY", lev["B2_top"]), ("L.W.L.", lev["LWL"]), ("G.L.", 0.0), ("FOUNDING LEVEL", lev["raft_bot"])):
        sh.level(xl, v.p(0, z)[1], f"{name} {z:+.3f}", left=True, h=1.7)
    for k, z in enumerate(g["braces"], 1):
        sh.text(f"{ordinal(k)} BRACE", (v.p(-xs_cols[-1] - dc / 2 - 0.4, z)[0], v.p(0, z)[1]), 1.6, TA.MIDDLE_RIGHT)
    sh.text("BOTTOM RING BEAM", (v.p(-r0 - th["b3"] / 2 - 0.4, 0)[0], v.p(0, (lev["B3_bot"] + lev["LWL"]) / 2)[1]), 1.6, TA.MIDDLE_RIGHT)
    # dimensions
    yD = v.p(0, lev["FSL"] - 1.0)[1]
    sh.dim_h(v.p(-R, 0)[0], v.p(0, 0)[0], yD, f"R = {R * 1e3:.0f}")
    yD0 = v.p(0, lev["B3_bot"] - 1.2)[1]
    sh.dim_h(v.p(-r0, 0)[0], v.p(0, 0)[0], yD0, f"R = {r0 * 1e3:.0f}", below=True)
    yR = v.p(0, lev["raft_bot"] - 0.9)[1]
    sh.dim_h(v.p(-Ro, 0)[0], v.p(-g["Ri"], 0)[0], yR, f"{(Ro - g['Ri']) * 1e3:.0f}", y_from=v.p(0, lev["raft_bot"])[1], below=True)
    sh.dim_h(v.p(-g["Ri"], 0)[0], v.p(0, 0)[0], yR, f"R = {g['Ri'] * 1e3:.0f}", below=True)
    xd = v.p(-left, 0)[0] + 3.0
    for z1, z2 in ((lev["raft_bot"], 0.0), (0.0, lev["LWL"]), (lev["LWL"], lev["cone_top"]), (lev["cone_top"], lev["wall_top"]),
                   (lev["wall_top"], lev["B1_top"]), (lev["B1_top"], lev["dome1_crown"])):
        sh.dim_v(v.p(0, z1)[1], v.p(0, z2)[1], xd, f"{abs(z2 - z1) * 1e3:.0f}", h=1.6)
    sh.heading("HALF SECTION", (v.p(-left / 2, 0)[0], y0 + 5), 2.8)
    sh.heading("HALF ELEVATION", (v.p(right / 2, 0)[0], y0 + 5), 2.8)
    sh.text(f"SCALE 1:{s}", (v.p(0, 0)[0], y0 + 2.5), 2.0, TA.MIDDLE_CENTER)


def _stair_plan(sh, P, res, k, labels=True):
    """The staircase in plan; P(x, y) gives the paper point of a real point (tank centre the origin, +x its side)."""
    st = res["members"]["stair"]
    xs, w, gap, lc, Lb = st["xs"], st["w"], st["gap"], st["lc"], st["Lb"]
    ds, bb = st["col"]["d"] / 1e3, st["beam"]["b"] / 1e3
    rl = w + gap / 2.0
    for sgn in (1, -1):
        y = sgn * Lb / 2.0
        sh.poly([P(st["xc"], y - bb / 2), P(xs + lc, y - bb / 2), P(xs + lc, y + bb / 2), P(st["xc"], y + bb / 2)], "OUTLINE", True)
        sh.circle(P(xs, y), ds / 2 * k)
        a0, a1 = (0.0, math.pi) if sgn > 0 else (math.pi, 2 * math.pi)
        sh.poly([P(xs + rl * math.cos(a0 + (a1 - a0) * i / 24), y + rl * math.sin(a0 + (a1 - a0) * i / 24)) for i in range(25)])
    for xa in (xs - rl, xs + gap / 2):
        sh.poly([P(xa, -Lb / 2), P(xa + w, -Lb / 2), P(xa + w, Lb / 2), P(xa, Lb / 2)], "OUTLINE", True)
        go = st["treads"] * st["tread"]
        for j in range(st["treads"] + 1):
            y = -go / 2 + j * st["tread"]
            sh.line(P(xa, y), P(xa + w, y), "THIN")
    if labels:
        sh.text("B1", P((st["xc"] + xs) / 2, Lb / 2 + 0.35), 1.6, TA.MIDDLE_CENTER)
        sh.text("B1", P((st["xc"] + xs) / 2, -Lb / 2 - 0.35), 1.6, TA.MIDDLE_CENTER)


def _plans(sh, res, x0, y0, bw, bh):
    g, M = res["geo"], res["members"]
    st, rf = M.get("stair"), M["raft"]
    r0, Ro, Ri, dc, bR = g["r0"], g["Ro"], g["Ri"], g["dc"], rf["bR"]
    left = Ro + 0.8
    right = (st["xs"] + st["gap"] / 2 + st["w"] + 1.2) if st else r0 + 2.0
    half = max(Ro, r0 + 1.5) + 0.5
    s = next((k for k in SCALES if (left + right) * 1000.0 / k + 8 <= bw and 2 * half * 1000.0 / k + 18 <= bh), SCALES[-1])
    k = 1000.0 / s
    cx, cy = x0 + 4 + left * k, y0 + 14 + half * k
    P = lambda x, y: (cx + x * k, cy + y * k)
    arc = lambda r, a0, a1, layer="OUTLINE": sh.poly([P(r * math.cos(a0 + (a1 - a0) * i / 60), r * math.sin(a0 + (a1 - a0) * i / 60)) for i in range(61)], layer)
    hp = math.pi / 2
    # foundation plan (left half)
    arc(Ro, hp, 3 * hp)
    if Ri:
        arc(Ri, hp, 3 * hp)
    arc(r0 - bR / 2, hp, 3 * hp)
    arc(r0 + bR / 2, hp, 3 * hp)
    for a in _angles(res):
        c = (r0 * math.cos(a), r0 * math.sin(a))
        sh.circle(P(*c), dc / 2 * k)
    # plan at brace level (right half)
    ang = _angles(res)
    for a, b_ in zip(ang, ang[1:] + ang[:1]):
        if math.cos(a) < -1e-9 and math.cos(b_) < -1e-9:
            continue
        pa, pb = (r0 * math.cos(a), r0 * math.sin(a)), (r0 * math.cos(b_), r0 * math.sin(b_))
        L = math.dist(pa, pb)
        ux, uy = (pb[0] - pa[0]) / L, (pb[1] - pa[1]) / L
        nx, ny = -uy * g["bb"] / 2, ux * g["bb"] / 2
        a2, b2 = (pa[0] + ux * dc / 2, pa[1] + uy * dc / 2), (pb[0] - ux * dc / 2, pb[1] - uy * dc / 2)
        pts = [(a2[0] + nx, a2[1] + ny), (b2[0] + nx, b2[1] + ny), (b2[0] - nx, b2[1] - ny), (a2[0] - nx, a2[1] - ny)]
        if min(q[0] for q in pts) >= -1e-6:
            sh.poly([P(*q) for q in pts], "OUTLINE", True)
    arc(r0, -hp, hp, "CENTER")
    sh.line(P(0, -half + 0.2), P(0, half - 0.2), "CENTER")
    sh.line(P(-left + 0.2, 0), P(right - 0.2, 0), "CENTER")
    a1 = ang[1]
    sh.line(P(0, 0), P(r0 * math.cos(a1), r0 * math.sin(a1)), "DIM")
    sh.line(P(0, 0), P(r0 * math.cos(ang[2 % len(ang)]), r0 * math.sin(ang[2 % len(ang)])), "DIM")
    sh.text(f"R = {r0 * 1e3:.0f}", P(0.55 * r0 * math.cos(a1) + 0.3, 0.55 * r0 * math.sin(a1)), 1.8, rot=math.degrees(a1))
    sh.text(f"{360.0 / g['n_col']:.2f} deg", P(0.8 * r0 * math.cos((a1 + ang[2 % len(ang)]) / 2), 0.8 * r0 * math.sin((a1 + ang[2 % len(ang)]) / 2)), 1.6, TA.MIDDLE_CENTER)
    am = ang[len(ang) // 4]
    sh.leader(P(r0 * math.cos(am), r0 * math.sin(am)), P(r0 * math.cos(am) + 1.5, r0 * math.sin(am) + 1.6),
              [f"{dc * 1e3:.0f} DIA COLUMN", f"({g['n_col']} NOS.)"], 1.7)
    ab = (ang[len(ang) // 4 - 1] + ang[len(ang) // 4 - 2]) / 2 if len(ang) >= 8 else ang[0] + math.pi / len(ang)
    rb = r0 * math.cos(math.pi / g["n_col"])
    sh.leader(P(rb * math.cos(ab), rb * math.sin(ab)), P(rb * math.cos(ab) + 2.0, rb * math.sin(ab) + 0.6),
              ["BRACE", f"{g['bb'] * 1e3:.0f} x {g['db'] * 1e3:.0f}"], 1.7)
    if st:
        _stair_plan(sh, P, res, k)
        sh.text("1ST FLIGHT", P(st["xs"] + st["gap"] / 2 + st["w"] + 0.3, 0), 1.5, TA.BOTTOM_CENTER, rot=90)
    # dimensions of the raft along the axis
    yd = cy - 3.0
    sh.dim_h(P(-Ro, 0)[0], P(-r0 - bR / 2, 0)[0], yd, f"{rf['ao'] * 1e3:.0f}", below=True)
    sh.dim_h(P(-r0 - bR / 2, 0)[0], P(-r0 + bR / 2, 0)[0], yd, f"{bR * 1e3:.0f}", below=True)
    sh.dim_h(P(-r0 + bR / 2, 0)[0], P(-Ri, 0)[0], yd, f"{rf['ai'] * 1e3:.0f}", below=True)
    if Ri:
        sh.dim_h(P(-Ri, 0)[0], P(0, 0)[0], yd, f"R = {Ri * 1e3:.0f}", below=True)
    sh.text(f"R = {Ro * 1e3:.0f}", P(-Ro * 0.5, -half + 0.6), 1.8, TA.MIDDLE_CENTER)
    sh.heading("HALF FOUNDATION PLAN", (P(-left / 2, 0)[0], y0 + 5), 2.8)
    sh.heading("HALF PLAN AT BRACE LEVEL", (P(right / 2, 0)[0], y0 + 5), 2.8)
    sh.text(f"SCALE 1:{s}", (cx, y0 + 2.5), 2.0, TA.MIDDLE_CENTER)


def _raft_section(sh, res, x0, y0, bw, bh):
    """SECTION 2-2: the raft along a radius, the outer edge on the left."""
    g, M, opt = res["geo"], res["members"], res["opt"]
    rf, rr, _col = M["raft"], M["raft_ring"], M["column"]
    Ro, Ri, r0, bR, dc = rf["Ro"], rf["Ri"], g["r0"], rf["bR"], g["dc"]
    t, te = rf["t"] / 1e3, rf["te"] / 1e3
    s = fit_scale(Ro - Ri + 0.8, t + 2.4, bw - 16, bh - 56)
    k = 1000.0 / s
    px = lambda r: x0 + 8 + (Ro - r) * k
    pz = lambda z: y0 + 44 + z * k
    c = opt["cover_raft_mm"] / 1e3
    rfo, rfi = r0 + bR / 2, r0 - bR / 2
    out = [(Ro, 0), (Ri, 0), (Ri, te), (rfi, t), (rfo, t), (Ro, te)]
    sh.hatch([(px(r), pz(z)) for r, z in out], scale=1.2, pattern="AR-CONC")
    sh.poly([(px(r), pz(z)) for r, z in out], "OUTLINE", True)
    sh.rect(px(Ro + 0.1), pz(-0.1), px(Ri - 0.1), pz(0), "THIN")
    for r in (rfo, rfi):
        sh.line((px(r), pz(0)), (px(r), pz(t)), "HIDDEN")
    sh.rect(px(r0 + dc / 2), pz(t), px(r0 - dc / 2), pz(t + 1.3))
    sh.line((px(r0), pz(-0.3)), (px(r0), pz(t + 1.7)), "CENTER")
    sh.text("C.L. OF COLUMN", (px(r0), pz(t + 1.85)), 1.7, TA.BOTTOM_CENTER)
    # bars: radial at the bottom, hoops, top mesh, the beam's stirrup and hoops, the column's bars
    up_ = max(c + 0.04, te - c - 0.04)                 # the bottom bar's crank: 40 mm short of the top bar
    sh.poly([(px(Ro - c), pz(up_)), (px(Ro - c), pz(c)), (px(Ri + c), pz(c)), (px(Ri + c), pz(up_))], "REBAR")
    cb = opt["cover_fbeam_mm"] / 1e3
    r = Ri + c + 0.08
    while r < Ro - c - 0.07:
        if not (rfi - 0.02 < r < rfo + 0.02):          # the beam's own bottom bars are there
            sh.dot((px(r), pz(c + 0.035)), 0.4)
        r += rf["hoop"][1] / 1e3
    # top bars: over the beam to its far face, bent down into it; at the slab's edge bent down too
    for a, far, j in ((Ro - c - 0.05, rfi + cb, 0), (Ri + c + 0.05, rfo - cb, 1)):
        zf = t - c - 0.03 * j
        face = rfo if j == 0 else rfi
        za_ = _raft_t(res, a) - c                      # the top bar at the edge, its leg down to the slab's middle
        pts = [(px(a), pz(max(c + 0.08, za_ - 0.1))), (px(a), pz(za_)), (px(face), pz(zf)), (px(far), pz(zf)),
               (px(far), pz(zf - 0.35))]
        sh.poly(pts, "REBAR")
        n = int(abs(a - face) / 0.2)
        for i in range(1, n):
            rr_ = a + (face - a) * i / n
            if abs(rr_ - a) >= 0.08:
                sh.dot((px(rr_), pz(_raft_t(res, rr_) - c - 0.03)), 0.35)
    sh.rect(px(rfo - cb), pz(cb), px(rfi + cb), pz(t - cb), "REBAR")
    xa_, xb_ = px(rfo - cb - 0.04), px(rfi + cb + 0.04)
    rtop = min(0.55, max(0.3, rr["top"][1] / 2e3 * k))
    rbot = min(0.55, max(0.3, rr["bot"][1] / 2e3 * k))
    dtop = bar_row(sh, xa_, xb_, pz(t - cb - 0.03), rr["top"][0], rtop, -1.0)
    dbot = bar_row(sh, xa_, xb_, pz(cb + 0.03), rr["bot"][0], rbot, 1.0)
    for sg in (-1, 1):
        xcol = r0 + sg * (dc / 2 - 0.06)
        sh.poly([(px(xcol), pz(t + 1.3)), (px(xcol), pz(cb + 0.1)), (px(xcol + sg * 0.35), pz(cb + 0.1))], "REBAR")
    # labels
    sh.leader((px(rfo + rf["ao"] * 0.5), pz(c)), (px(rfo + rf["ao"] * 0.3), pz(t + 0.25)),
              f"{nb(rf['rad'])} RADIALLY @ {rf['rad_sp']} C/C", 1.8)
    sh.leader((px(rfo + rf["ao"] * 0.55), pz(_raft_t(res, rfo + rf["ao"] * 0.55) - c)), (px(rfo + rf["ao"] * 0.7), pz(t + 0.75)),
              [at(rf["top_rad"], "RADIALLY"), at(rf["top_hoop"], "HOOPS")], 1.8, right=False)
    sh.leader_rows(dtop, rtop, (px(rfi - 0.5), pz(t + 1.15)), f"{nb(rr['top'])} HOOPS", 1.8)
    sh.leader_rows(dbot, rbot, (px(rfi - 0.5), pz(t + 0.4)), f"{nb(rr['bot'])} HOOPS (BOTTOM)", 1.8)
    sh.leader((px(rfi + cb), pz(t * 0.55)), (px(rfi - 0.5), pz(t + 0.65)), f"10 # STIRRUPS ({rr['legs']}-LEGGED)", 1.8)
    # zone dimensions below
    yd = pz(-0.1) - 13
    hs = rf["hoop"][1] / 1e3
    sh.dim_h(px(Ro), px(rfo), yd, f"{rf['ao'] * 1e3:.0f}", y_from=pz(-0.1))
    sh.text(f"{math.ceil(rf['ao'] / hs)} - {rf['hoop'][0]} # HOOPS", ((px(Ro) + px(rfo)) / 2, yd - 3.2), 1.7, TA.MIDDLE_CENTER)
    sh.dim_h(px(rfo), px(rfi), yd, f"{bR * 1e3:.0f}", y_from=pz(-0.1))
    ra = rfi
    for L, n_ in rf["zones_in"]:
        sh.dim_h(px(ra), px(ra - L), yd, f"{L * 1e3:.0f}", y_from=pz(-0.1))
        sh.text(f"{math.ceil(L / hs)} - {rf['hoop'][0]} # HOOPS", ((px(ra) + px(ra - L)) / 2, yd - 3.2), 1.7, TA.MIDDLE_CENTER)
        sh.text(f"{n_} - {rf['rad'][1]} #", ((px(ra) + px(ra - L)) / 2, yd - 6.4), 1.7, TA.MIDDLE_CENTER)
        sh.line((px(ra - L), pz(c) - 1.0), (px(ra - L), pz(c) + 1.0), "REBAR")
        ra -= L
    sh.dim_h(px(Ro), px(Ri), yd - 11, f"R = {Ro * 1e3:.0f} (OUTER), R = {Ri * 1e3:.0f} (INNER)")
    xv = px(Ri) + 7
    sh.dim_v(pz(0), pz(te), xv, f"{te * 1e3:.0f}", x_from=px(Ri))
    sh.dim_v(pz(0), pz(t), px(Ro) - 6, f"{t * 1e3:.0f}", h=1.7)
    sh.text("100 P.C.C.", (px(Ro + 0.1) - 1, pz(-0.05)), 1.6, TA.MIDDLE_RIGHT)
    sh.heading("SECTION 2 - 2 (RAFT)", (x0 + bw / 2, y0 + 4), 2.8, f"SCALE 1:{s}")


def _sector(sh, xr, yc, s, Ri, Ro, arc_mm, radial, hoops, layer="REBAR2"):
    """A sector in plan, its inner edge at xr (right), the outer on the left. radial: [(r_a, r_b, n in the full
    circle)], hoops: [(r_a, r_b, spacing m)]. Returns the point function P(r, angle) and the half angle."""
    k = 1000.0 / s
    phi = min(1.0, arc_mm / k / Ro)
    P = lambda r, t: (xr - (r * math.cos(t) - Ri) * k, yc + r * math.sin(t) * k)
    for sg in (-1, 1):
        sh.line(P(max(Ri, 0.0), sg * phi / 2), P(Ro, sg * phi / 2), "THIN")
    sh.poly([P(Ro, -phi / 2 + phi * i / 16) for i in range(17)], "OUTLINE")
    if Ri > 0:
        sh.poly([P(Ri, -phi / 2 + phi * i / 8) for i in range(9)], "OUTLINE")
    for ra, rb, n in radial:
        dth = 2 * math.pi / n
        m = int(phi / 2 / dth)
        for j in range(-m, m + 1):
            sh.line(P(ra, j * dth), P(rb, j * dth), layer)
    for ra, rb, sp in hoops:
        r = ra + sp / 2
        while r < rb:
            sh.poly([P(r, -phi / 2 + phi * i / 8) for i in range(9)], layer)
            r += sp
    return P, phi / 2


def _raft_plan(sh, res, x0, y0, bw, bh):
    g, rf = res["geo"], res["members"]["raft"]
    Ro, Ri, r0, bR = rf["Ro"], rf["Ri"], g["r0"], rf["bR"]
    s = fit_scale(Ro - Ri + 0.5, 1.0, bw - 20, 1e9)
    rfi = r0 - bR / 2
    radial, ra = [], rfi
    for i, (L, n) in enumerate(rf["zones_in"]):
        radial.append((ra - L, Ro if i == 0 else ra, n))
        ra -= L
    hs = rf["hoop"][1] / 1e3
    P, hphi = _sector(sh, x0 + bw - 12, y0 + bh / 2 + 4, s, Ri, Ro, min(bh - 40, 95), radial, [(Ri, Ro, hs)])
    # the ring beam's band and labels along the upper edge
    for r in (r0 - bR / 2, r0 + bR / 2):
        sh.poly([P(r, -hphi + 2 * hphi * i / 8) for i in range(9)], "HIDDEN")
    ra = rfi
    for L, n in rf["zones_in"]:
        pm = P(ra - L / 2, hphi)
        sh.text(f"{n} - {rf['rad'][1]} #", (pm[0], pm[1] + 5.5), 1.7, TA.MIDDLE_CENTER)
        sh.text(f"{math.ceil(L / hs)} - {rf['hoop'][0]} # HOOPS, {L * 1e3:.0f}", (pm[0], pm[1] + 2.5), 1.6, TA.MIDDLE_CENTER)
        ra -= L
    pm = P((Ro + r0 + bR / 2) / 2, hphi)
    sh.text(f"{math.ceil(rf['ao'] / hs)} - {rf['hoop'][0]} # HOOPS, {rf['ao'] * 1e3:.0f}", (pm[0], pm[1] + 2.5), 1.6, TA.MIDDLE_CENTER)
    pl = P(Ro - 0.3, -hphi)
    sh.text(f"{nb(rf['rad'])} RADIALLY @ {rf['rad_sp']} C/C ON THE COLUMN CIRCLE", (pl[0], pl[1] - 4), 1.8)
    sh.heading("PART REINFORCEMENT PLAN OF RAFT SLAB (BOTTOM)", (x0 + bw / 2, y0 + 4), 2.8, f"SCALE 1:{s}")


def _lsec(sh, x0, y0, s, span, col_w, beam_d, up, down, stir, legs, top, bot, ring_txt, title, extra=()):
    """Developed L-section of a ring beam / brace between two columns. x0, y0: paper point of the left column's
    centre line at the beam's soffit. up / down: lengths of column drawn above / below the beam (m)."""
    k = 1000.0 / s
    X = lambda x: x0 + x * k
    Z = lambda z: y0 + z * k
    ov = 0.55
    sh.poly([(X(-col_w / 2 - ov), Z(0)), (X(span + col_w / 2 + ov), Z(0))])
    sh.poly([(X(-col_w / 2 - ov), Z(beam_d)), (X(span + col_w / 2 + ov), Z(beam_d))])
    for xe in (-col_w / 2 - ov, span + col_w / 2 + ov):
        sh.poly([(X(xe), Z(0)), (X(xe) + 0.8, Z(beam_d * 0.3)), (X(xe) - 0.8, Z(beam_d * 0.7)), (X(xe), Z(beam_d))], "THIN")
    for xc in (0.0, span):
        for a, b_ in ((beam_d, beam_d + up), (-down, 0.0)):
            if b_ - a < 1e-6:
                continue
            sh.line((X(xc - col_w / 2), Z(a)), (X(xc - col_w / 2), Z(b_)))
            sh.line((X(xc + col_w / 2), Z(a)), (X(xc + col_w / 2), Z(b_)))
            zz, i = a + 0.05, 0
            while zz < b_ - 0.02:
                sh.line((X(xc - col_w / 2 + 0.04), Z(zz)), (X(xc + col_w / 2 - 0.04), Z(zz)), "REBAR2")
                zz += 0.1 if (zz - a < 0.6 or b_ - zz < 0.6) else 0.2
        for dx in (-col_w / 2 + 0.06, col_w / 2 - 0.06):
            sh.line((X(xc + dx), Z(-down if down else 0.08)), (X(xc + dx), Z(beam_d + up if up else beam_d - 0.08)), "REBAR")
    c = 0.05
    sh.line((X(-col_w / 2 - ov + 0.05), Z(c)), (X(span + col_w / 2 + ov - 0.05), Z(c)), "REBAR")
    sh.line((X(-col_w / 2 - ov + 0.05), Z(beam_d - c)), (X(span + col_w / 2 + ov - 0.05), Z(beam_d - c)), "REBAR")
    clear = span - col_w
    xa, n_end = col_w / 2 + 0.05, 0
    xsr = []
    while xa < span - col_w / 2 - 0.02:
        xsr.append(xa)
        near = min(xa - col_w / 2, span - col_w / 2 - xa)
        if near < clear / 4.0:
            xa += stir[1] / 1e3
            n_end += 1
        else:
            xa += stir[2] / 1e3
    for xa in xsr:
        sh.line((X(xa), Z(c)), (X(xa), Z(beam_d - c)), "REBAR2")
    n_mid = sum(1 for xa in xsr if min(xa - col_w / 2, span - col_w / 2 - xa) >= clear / 4.0)
    n_e = (len(xsr) - n_mid) // 2
    sh.dim_h(X(0), X(span), Z(-down) - 6 if down else Z(0) - 8, f"{span * 1e3:.2f}", y_from=Z(-down) if down else Z(0), below=True)
    sh.dim_h(X(-col_w / 2), X(col_w / 2), Z(beam_d + up) + 4, f"{col_w * 1e3:.0f}", y_from=Z(beam_d + up))
    sh.dim_v(Z(0), Z(beam_d), X(span + col_w / 2 + ov) + 6, f"{beam_d * 1e3:.0f}", x_from=X(span + col_w / 2 + ov))
    sh.leader((X(span * 0.5), Z(beam_d - c)), (X(span * 0.5) + 4, Z(beam_d + max(up, 0.5) * 0.75)), top, 1.8)
    sh.leader((X(span * 0.42), Z(c)), (X(span * 0.42) - 3, Z(-max(down, 0.6) * 0.55)), bot, 1.8, right=False)
    sh.text(f"({n_e} + {n_mid} + {n_e}) - {stir[0]} # {legs}-LEGGED STIRRUPS @ {stir[1]} / {stir[2]} C/C", (X(span / 2), Z(beam_d / 2)), 1.7, TA.MIDDLE_CENTER)
    yt = Z(beam_d + up * 0.55) if up else Z(-down * 0.5)
    sh.leader((X(span + col_w / 2 - 0.05), yt), (X(span + col_w / 2) + 6, yt), ring_txt, 1.7)
    for i, row in enumerate(extra):
        sh.text(row, (X(-col_w / 2 - ov), Z(-down) - 12 - i * 3.2 if down else Z(0) - 14 - i * 3.2), 1.7)
    sh.heading(title, (X(span / 2), (Z(-down) if down else Z(0)) - (22 + 3.2 * len(extra))), 2.8, f"SCALE 1:{s}")


def bar_row(sh, xa, xb, y, n, r, inward=1.0, gap=0.5):
    """n bar dots of paper radius r between xa and xb (paper mm) at the level y: one row when the bars fit with a
    clear gap, else in more layers, each `inward` (+1 up / -1 down) by 2 r + 1 mm (IS 456 26.3.2: bars in layers one
    over the other). Returns the dots' points."""
    r = max(0.3, r)
    room = max(xb - xa, 0.0)
    per_row = max(2, int(room // (2 * r + gap)) + 1)
    pts, row = [], 0
    while n > 0:
        k = min(n, per_row)
        yy = y + inward * row * (2 * r + 1.0)
        for i in range(k):
            x = (xa + xb) / 2 if k == 1 else xa + i * room / (k - 1)
            pts.append((x, yy))
            sh.dot((x, yy), r)
        n -= k
        row += 1
    return pts


def hooked(v, pts, layer="REBAR", ends=(True, True), inside=None, h=None):
    """A bar along pts (real m) with a hook at each end: a short leg at 150 degrees to the bar, i.e. 30 degrees off
    its line (user 10-Nov-2026), turned toward `inside` - a point in the member (or a pair, one for each end; the
    default the bar's own middle) so that the hook stays in the concrete. ends: which ends are hooked."""
    h = h or min(0.06, 2.5 / v.k)                 # 60 mm, at most 2.5 mm on the paper
    if inside is None:
        inside = (sum(q[0] for q in pts) / len(pts), sum(q[1] for q in pts) / len(pts))
    ins = inside if isinstance(inside[0], (tuple, list)) else (inside, inside)
    pts = list(pts)
    c, s_ = math.cos(math.radians(30)), math.sin(math.radians(30))
    legs = []
    for k, (on, tgt) in enumerate(zip(ends, ins)):
        i, j = (0, 1) if k == 0 else (-1, -2)
        a, b = pts[i], pts[j]
        L = math.dist(a, b)
        if L < 2 * h or not on:
            continue
        ux, uz = (a[0] - b[0]) / L, (a[1] - b[1]) / L         # on along the bar's line, beyond its end
        a2 = (a[0] - ux * h * c, a[1] - uz * h * c)           # the bend, so that the leg ends at the bar's end
        pts[i] = a2
        tips = [(a2[0] + h * (ux * c - uz * s_ * sg), a2[1] + h * (ux * s_ * sg + uz * c)) for sg in (1, -1)]
        legs.append((a2, min(tips, key=lambda q: math.dist(q, tgt))))
    v.poly(pts, layer)
    for a2, tip in legs:
        v.line(a2, tip, layer)


def _beam_xsec(sh, xc, ytop, s, b, d, top, bot, cover, title, side=0, legs=2, note=None):
    """Cross-section of a beam b x d (mm)."""
    w, h = b / s, d / s
    x0, y0 = xc - w / 2, ytop - h
    c = cover / s
    sh.rect(x0, y0, x0 + w, y0 + h)
    sh.rect(x0 + c, y0 + c, x0 + w - c, y0 + h - c, "REBAR")
    if legs == 4:
        sh.rect(x0 + w / 3, y0 + c, x0 + 2 * w / 3, y0 + h - c, "REBAR")
    for (n_, dia), y, inward in ((top, y0 + h - c - 1.2, -1.0), (bot, y0 + c + 1.2, 1.0)):
        bar_row(sh, x0 + c + 1.2, x0 + w - c - 1.2, y, n_, min(max(0.45, dia / 2 / s), 1.1), inward)
    for i in range(side):
        y = y0 + c + 1.2 + (i + 1) * (h - 2 * c - 2.4) / (side + 1)
        for x in (x0 + c + 1.2, x0 + w - c - 1.2):
            sh.dot((x, y), 0.5)
    sh.dim_h(x0, x0 + w, y0 - 4, f"{b}", y_from=y0, below=True)
    sh.dim_v(y0, y0 + h, x0 - 4, f"{d}", x_from=x0)
    sh.text(nb(top), (x0 + w + 2, y0 + h - c - 1), 1.7)
    sh.text(nb(bot), (x0 + w + 2, y0 + c + 1), 1.7)
    if note:
        sh.text(note, (x0 + w + 2, y0 + h / 2), 1.7)
    sh.heading(title, (xc, y0 - 13), 2.6, f"SCALE 1:{s}")
    return y0 - 20


def _notes(sh, res, x, y, w=180):
    opt, m = res["opt"], res["mat"]
    rows = ["NOTES:",
            "1.  ALL DIMENSIONS ARE IN MILLIMETRE, LEVELS IN METRE ABOVE THE GROUND LEVEL.",
            "2.  CONCRETE MIX FOR",
            f"      WATER CONTAINER & STAGING                 - M{m['fck']}",
            f"      FOUNDATION & STAIRCASE                       - M{m['fck_found']}",
            "      CONCRETE MIX SHALL CONFORM TO IS: 456 - 2000 AND IS: 3370 (PART 1) - 2009,",
            "      PROPERLY COMPACTED BY VIBRATOR.",
            f"3.  HIGH STRENGTH DEFORMED BARS OF GRADE Fe {m['fy']} D CONFORMING TO IS: 1786.",
            "4.  COVER FOR R.C.C. WORKS:",
            f"      TANK WALL, DOMES ON EITHER FACE {opt['cover_water_mm']} mm;  BOTTOM RING BEAM {opt['cover_ring_mm']} mm;",
            f"      COLUMNS & BRACES {opt['cover_mm']} mm;  FOUNDATION RAFT {opt['cover_raft_mm']} mm;",
            f"      FOUNDATION RING BEAM {opt['cover_fbeam_mm']} mm;  STAIRCASE FLIGHTS {opt['cover_stair_mm']} mm.",
            f"5.  OVERLAPS AND ANCHORAGE: WATER CONTAINER & STAGING {opt['lap_dia']} DIA, REMAINING",
            f"      PORTION {opt['lap_dia_found']} DIA. LAPS SHALL BE STAGGERED.",
            f"6.  NET BEARING CAPACITY OF SOIL TAKEN AS {opt['sbc_kn_m2']:g} kN/m2 AT {opt['founding_depth_m']:g} m BELOW G.L. -",
            "      TO BE CONFIRMED BY SOIL INVESTIGATION BEFORE CONSTRUCTION.",
            f"7.  SEISMIC ZONE {opt['zone']} (IS: 1893), BASIC WIND SPEED {opt['wind_vb']:g} m/s (IS: 875 PART 3).",
            "8.  ALL PIPES AND OTHER FIXTURES SHALL BE AS PER TENDER DOCUMENTS.",
            "9.  READ WITH THE OTHER SHEETS, THE DESIGN CALCULATION AND THE BAR SCHEDULE."]
    sh.text(rows[0], (x, y), 2.4, style=B)
    sh.lines(rows[1:], x, y - 5, 1.9, 3.5)


def _sheet_staging(dw, res, info):
    sh = Sheet(dw, 0, "STAGING AND FOUNDATION", 1)
    g, M, opt = res["geo"], res["members"], res["opt"]
    _ga(sh, res, 14, 250, 306, 332)
    _plans(sh, res, 14, 20, 306, 226)
    _raft_section(sh, res, 326, 452, 316, 130)
    _raft_plan(sh, res, 326, 292, 316, 156)
    col, br, rr = M["column"], M["brace"], M["raft_ring"]
    s = fit_scale(g["Lb"] + g["dc"] + 1.3, g["tr"] + 1.6, 230, 95)
    _lsec(sh, 326 + 40, 190, s, g["Lb"], g["dc"], g["tr"], 1.3, 0.0, rr["stir"], rr["legs"],
          f"{nb(rr['top'])} HOOPS (OVERLAP NEAR SUPPORT ONLY)", f"{nb(rr['bot'])} HOOPS (OVERLAP NEAR MIDSPAN ONLY)",
          [f"{nb((col['n'], col['dia']))}", f"8 # RINGS @ 100 C/C OVER {col['conf_len']}", "8 # RINGS @ 200 C/C ELSEWHERE"],
          "PART L - SECTION OF FOUNDATION RING BEAM")
    # brace: L-section and cross-section; column section
    s2 = fit_scale(g["Lb"] + g["dc"] + 1.3, g["db"] + 2.2, 150, 110)
    _lsec(sh, 660, 462, s2, g["Lb"], g["dc"], g["db"], 0.9, 0.9, br["stir"], 2, f"{nb(br['top'])} (ANCHORED IN COLUMNS)",
          f"{nb(br['bot'])}", "8 # RINGS @ 100 C/C", "L - SECTION OF BRACE")
    s3 = fit_scale(br["b"] / 1e3 + 0.1, br["d"] / 1e3 + 0.1, 40, 50)
    _beam_xsec(sh, 690, 380, s3, br["b"], br["d"], br["top"], br["bot"], opt["cover_mm"], "SECTION 3 - 3 (BRACE)", note="8 # STR.")
    s4 = fit_scale(col["d"] / 1e3 + 0.1, col["d"] / 1e3 + 0.1, 50, 50)
    xc, yc, r = 775, 355, col["d"] / 2 / s4
    sh.circle((xc, yc), r)
    c = opt["cover_mm"] / s4
    sh.circle((xc, yc), r - c, "REBAR")
    for i in range(col["n"]):
        a = 2 * math.pi * i / col["n"] + math.pi / 2
        sh.dot((xc + (r - c - 1.5) * math.cos(a), yc + (r - c - 1.5) * math.sin(a)), max(0.5, col["dia"] / 2 / s4))
    sh.dim_h(xc - r, xc + r, yc - r - 4, f"{col['d']}", y_from=yc - r, below=True)
    sh.leader((xc + (r - c - 1.5) * math.cos(0.9), yc + (r - c - 1.5) * math.sin(0.9)), (xc + r + 3, yc + r), nb((col["n"], col["dia"])), 1.8)
    sh.leader((xc + (r - c), yc - 2), (xc + r + 3, yc - 4), ["8 # RINGS", "@ 200 C/C"], 1.8)
    sh.heading("SECTION 1 - 1 (COLUMN)", (xc, yc - r - 13), 2.6, f"SCALE 1:{s4}")
    _notes(sh, res, 648, 268)
    sh.frame(info)
    return sh


# ------------------------------------------------------------------------------------------- sheet 2: the container
def _tank_section(sh, res, x0, y0, bw, bh):
    g, lev, th, M, opt = res["geo"], res["levels"], res["geo"]["th"], res["members"], res["opt"]
    R, r0 = g["R"], g["r0"]
    S = _shapes(res)
    cw = opt["cover_water_mm"] / 1e3
    width = g["bal_edge"] + 0.3
    zb = lev["B3_bot"] - 1.0
    height = lev["dome1_crown"] - zb + 0.8
    s = fit_scale(width, height, bw - 46, bh - 16)
    v = View(sh, x0 + 6, y0 + 14, s, 0.0, zb)
    v.shape(_container_outline(res))
    # the members' joints, thin: where one member's concrete ends and the next begins
    for (xa_, za_), (xb_, zb_) in (((R, lev["wall_top"]), (R + max(th["b1"], th["tw"]), lev["wall_top"])),
                                   ((R, lev["B2_top"]), (R + th["twb"], lev["B2_top"])),
                                   ((R, lev["cone_top"]), (R + th["t0"] / math.sin(g["alpha"]), lev["cone_top"])),
                                   ((r0 - th["b3"] / 2, lev["LWL"]), (r0 + th["b3"] / 2, lev["LWL"]))):
        v.line((xa_, za_), (xb_, zb_), "THIN")
    v.line((0, zb + 0.3), (0, lev["dome1_crown"] + 0.6), "CENTER")
    sh.text("C.L. OF TANK", v.p(0.1, lev["dome1_crown"] + 0.45), 1.7)
    v.line((0, lev["FSL"]), (R, lev["FSL"]), "WATER")
    sh.text("F.S.L.", v.p(R * 0.25, lev["FSL"] + 0.12), 1.8, TA.BOTTOM_CENTER, "WATER")
    dcol = g["dc"]
    v.poly([(r0 - dcol / 2, zb + 0.25), (r0 - dcol / 2, lev["B3_bot"])])
    v.poly([(r0 + dcol / 2, zb + 0.25), (r0 + dcol / 2, lev["B3_bot"])])
    # ---- bars (each bar's end anchored: bent into the ring beam it meets, as the example)
    c3 = opt["cover_ring_mm"] / 1e3
    (b3a, b3z0), _, (b3b, b3z1), _ = S["B3"]
    (b1a, b1z0), _, (b1b, b1z1), _ = S["B1"]
    zc1, R1, a1 = S["dome1"]
    td, bd = M["top_dome"], M["bottom_dome"]
    rm = R1 + th["t1"] / 2
    mid1 = [(rm * math.sin(a1 * i / 60), zc1 + rm * math.cos(a1 * i / 60)) for i in range(61)]
    end1 = mid1[-1]
    b1c = ((b1a + b1b) / 2, (b1z0 + b1z1) / 2)
    inner = [q_ for q_ in mid1 if q_[0] <= R]
    hooked(v, inner + [(R + cw, b1z1 - cw), (b1b - cw, b1z1 - cw), (b1b - cw, b1z0 + cw)], ends=(False, True), inside=b1c)
    v.dots(mid1[:-2], td["hoop"][1] / 1e3, 0.3)
    e1 = [(x - 0.02, z - 0.035) for x, z in inner if math.dist((x, z), end1) <= td["edge"]]
    d_ = 0.035
    hooked(v, e1 + [(R + cw + d_, b1z1 - cw - d_), (b1b - cw - d_, b1z1 - cw - d_), (b1b - cw - d_, b1c[1])], inside=b1c)
    # wall: verticals from the balcony ring (L at the foot) into the top ring beam (L at the top)
    w = M["wall"]
    zt = S["wall"][2][1]
    zfoot = lev["cone_top"] + cw + 0.03
    wc = lambda z_: (R + th["tw"] / 2, z_)            # a point in the wall at the level z_
    hooked(v, [(R + cw, zfoot), (R + cw, b1z1 - cw - 0.03)], inside=(wc(zfoot), b1c))
    hooked(v, [(R + th["twb"] - cw, zfoot), (R + th["twb"] - cw, lev["B2_top"]), (R + th["tw"] - cw, zt),
               (R + th["tw"] - cw, b1z1 - cw - 0.03)], inside=(wc(zfoot), b1c))
    for z in w["zones"]:
        za, zb_ = lev["wall_top"] - z["top"], max(lev["wall_top"] - z["top"] - z["len"], lev["B2_top"] + 0.03)
        v.dots([(R + cw + 0.03, za), (R + cw + 0.03, zb_)], z["sp"] / 1e3, 0.3)
        xo = lambda zz: R + th["tw"] + (th["twb"] - th["tw"]) * max(0.0, (zt - zz) / th["taper"]) - cw - 0.03
        v.dots([(xo(za), za), (xo(zb_), zb_)], z["sp"] / 1e3, 0.3)
    # balcony ring: a closed stirrup with the hoops round it
    bl = M["balcony"]
    xa, xb, za, zb_ = R + cw, g["bal_edge"] - cw, lev["cone_top"] + cw, lev["B2_top"] - cw
    v.poly([(xa, za), (xb, za), (xb, zb_), (xa, zb_)], "REBAR", True)
    per = [(xa + 0.05, zb_ - 0.045), (xb - 0.05, zb_ - 0.045), (xb - 0.05, za + 0.045), (xa + 0.05, za + 0.045)]
    L = sum(math.dist(p_, q_) for p_, q_ in zip(per, per[1:]))
    v.dots(per, L / bl["n"], 0.42, first=L / bl["n"] / 2)
    # cone, both faces: down into the bottom ring beam and bent down in it, up into the balcony ring and bent out
    al, t0 = g["alpha"], th["t0"]
    sa_, ca_ = math.sin(al), math.cos(al)
    nx, nz = sa_, -ca_
    cn = M["cone"]
    xin_a, xin_b = b3a + c3 + 0.04, b3b - c3 - 0.04
    b3c = ((b3a + b3b) / 2, (b3z0 + b3z1) / 2)
    for j, off in enumerate((cw, t0 - cw)):
        base = (r0 + nx * off, lev["LWL"] + nz * off)
        at_s = lambda s_, base=base: (base[0] + s_ * ca_, base[1] + s_ * sa_)
        s_lo = (b3z1 - c3 - 0.06 - 0.04 * j - base[1]) / sa_          # just under the beam's top
        if at_s(s_lo)[0] > xin_b:
            s_lo = (xin_b - base[0]) / ca_
        if at_s(s_lo)[0] < xin_a:
            s_lo = (xin_a - base[0]) / ca_
        p_lo = at_s(s_lo)
        foot = (p_lo[0], b3z0 + c3 + 0.08 + 0.04 * j)
        if j == 0:                                    # water face: on up the wall's inner face, a lap of 450
            p_w = at_s((R + cw + 0.03 - base[0]) / ca_)
            hooked(v, [foot, p_lo, p_w, (p_w[0], lev["B2_top"] + 0.45)], inside=(b3c, wc(lev["B2_top"] + 0.45)))
        else:                                         # outer face: into the balcony, along its bottom
            p_hi = at_s((za + 0.03 - base[1]) / sa_)
            hooked(v, [foot, p_lo, p_hi, (xb - 0.05, p_hi[1])], inside=(b3c, ((xa + xb) / 2, (za + zb_) / 2)))
        o2 = 0.035 if j == 0 else -0.035
        sft = lambda q: (q[0] + nx * o2, q[1] + nz * o2)
        a_ = sft(at_s((0.06 - nz * off) / sa_))                       # the cone proper: from the beam to the ring
        b_ = sft(at_s((g["h0"] - 0.06 - nz * off) / sa_))
        m_ = ((a_[0] + b_[0]) / 2, (a_[1] + b_[1]) / 2)
        v.dots([a_, m_], cn["hoop_low"][1] / 1e3, 0.42)
        v.dots([m_, b_], cn["hoop_up"][1] / 1e3, 0.42)
    # bottom dome, both faces: into the bottom ring beam and bent down in it
    zc2, R2, a2 = S["dome2"]
    for j, off in enumerate((cw, th["t2"] - cw)):
        rr_ = R2 - off
        t_end = math.asin(min(1.0, (b3a + c3 + 0.02) / rr_))
        pts = [(rr_ * math.sin(t_end * i / 60), zc2 + rr_ * math.cos(t_end * i / 60)) for i in range(61)]
        xe = min(xin_b - 0.08, b3a + th["b3"] * (0.55 if j == 0 else 0.42))
        ze = min(pts[-1][1], b3z1 - c3 - 0.1 - 0.04 * j)
        hooked(v, pts + [(xe, ze), (xe, b3z0 + c3 + 0.12 + 0.04 * j)], ends=(False, True), inside=b3c)
        v.dots([p_ for p_ in pts if p_[0] < b3a - 0.03], bd["hoop"][1] / 1e3, 0.3)
    # ring beams: stirrup and the hoop bars in rows
    for xa_, za_, xb_, zb2, c_ in ((b1a, b1z0, b1b, b1z1, cw), (b3a, b3z0, b3b, b3z1, c3)):
        v.rect(xa_ + c_, za_ + c_, xb_ - c_, zb2 - c_, "REBAR")
    br = M["bottom_ring"]
    rb = min(0.6, max(0.35, br["top"][1] / 2e3 * v.k))
    bar_row(sh, v.p(b3a + c3 + 0.04, 0)[0], v.p(b3b - c3 - 0.04, 0)[0], v.p(0, b3z1 - c3 - 0.03)[1], br["top"][0], rb, -1.0)
    b3dots = bar_row(sh, v.p(b3a + c3 + 0.04, 0)[0], v.p(b3b - c3 - 0.04, 0)[0], v.p(0, b3z0 + c3 + 0.03)[1], br["bot"][0], rb, 1.0)
    tr_ = M["top_ring"]
    nside = tr_["n"] // 2
    for xx in (b1a + cw + 0.03, b1b - cw - 0.03):
        for i in range(nside):
            zz = b1z0 + cw + 0.03 + i * (b1z1 - b1z0 - 2 * cw - 0.06) / max(1, nside - 1)
            sh.dot(v.p(xx, zz), 0.4)
    # ---- thicknesses of the members
    tz = lev["wall_top"] - 0.45
    sh.dim_across(v.p(R, tz), v.p(R + th["tw"], tz), f"{th['tw'] * 1e3:.0f}")
    bz = lev["B2_top"] + 0.12
    sh.dim_across(v.p(R, bz), v.p(R + th["twb"] - (th["twb"] - th["tw"]) * 0.12 / max(th["taper"], 1e-6), bz), f"{th['twb'] * 1e3:.0f}")
    sh.dim_across(v.p(g["bal_edge"], lev["cone_top"]), v.p(g["bal_edge"], lev["B2_top"]), f"{th['bal_t'] * 1e3:.0f}")
    sh.dim_across(v.p(R + th["twb"], lev["B2_top"] + 0.35), v.p(g["bal_edge"], lev["B2_top"] + 0.35), f"{th['bal_w'] * 1e3:.0f}")
    al_ = g["alpha"]
    cm = ((r0 + R) / 2, (lev["LWL"] + lev["cone_top"]) / 2)
    sh.dim_across(v.p(*cm), v.p(cm[0] + th["t0"] * math.sin(al_), cm[1] - th["t0"] * math.cos(al_)), f"{th['t0'] * 1e3:.0f}")
    for (zc_, Rs, aa), tt, outer in ((S["dome1"], th["t1"], True), (S["dome2"], th["t2"], False)):
        a_m = aa * 0.55
        r_in = Rs if outer else Rs - tt
        p_in = (r_in * math.sin(a_m), zc_ + r_in * math.cos(a_m))
        p_out = ((r_in + tt) * math.sin(a_m), zc_ + (r_in + tt) * math.cos(a_m))
        sh.dim_across(v.p(*p_in), v.p(*p_out), f"{tt * 1e3:.0f}")
    (b1a_, b1z0_), _, (b1b_, b1z1_), _ = S["B1"]
    sh.dim_across(v.p(b1b_, b1z0_), v.p(b1b_, b1z1_), f"{th['d1'] * 1e3:.0f}")
    (b3a_, b3z0_), _, (b3b_, b3z1_), _ = S["B3"]
    sh.dim_across(v.p(b3a_, b3z0_), v.p(b3b_, b3z0_), f"{th['b3'] * 1e3:.0f}")
    sh.dim_across(v.p(b3a_, b3z0_), v.p(b3a_, b3z1_), f"{th['d3'] * 1e3:.0f}")
    # ---- labels (inside the tank, as on the example) and dimensions
    pm = mid1[30]
    sh.leader_bar(v.p(*pm), v.p(pm[0] * 0.75, pm[1] - 1.5), [at(td["rad"], "RADIALLY"), at(td["hoop"], "HOOPS"), f"TOP DOME {td['t']} THICK ({td['te']} AT THE EDGE)"], 1.9)
    pe = mid1[57]
    sh.leader_bar(v.p(*pe), v.p(pe[0] - 2.2, pe[1] - 0.2), [f"{math.ceil(td['edge'] * 1e3 / td['edge_hoop'][1])} - {td['edge_hoop'][0]} # HOOPS",
              f"{math.ceil(2 * math.pi * R * 1e3 / td['edge_rad'][1])} - {at(td['edge_rad'], 'RADIALLY')}", f"AT TOP, IN {td['edge'] * 1e3:.0f} FROM THE EDGE"], 1.8, right=False)
    sh.leader_bar(v.p(R + th["b1"] / 2, lev["B1_top"] - 0.05), v.p(R + th["b1"] + 0.5, lev["B1_top"] + 0.6),
              [f"TOP RING BEAM {tr_['b']} x {tr_['d']}", f"{nb((tr_['n'], tr_['dia']))} HOOPS, 8 # STR @ 200 C/C"], 1.9)
    xz = v.p(R + th["twb"] + 0.25, 0)[0] + 1
    for z in w["zones"]:
        za, zb_ = lev["wall_top"] - z["top"], lev["wall_top"] - z["top"] - z["len"]
        if za > lev["B2_top"] + th["taper"] * 0.2:
            sh.dim_v(v.p(0, zb_)[1], v.p(0, za)[1], xz, f"{z['len'] * 1e3:.0f}", h=1.6)
            sh.text(f"{z['n']} - {z['dia']} # HOOPS ON EACH FACE", (xz + 2.5, v.p(0, (za + zb_) / 2)[1]), 1.8)
        else:
            sh.text(f"{z['n']} - {z['dia']} # HOOPS ON EACH FACE (LOWEST {z['len'] * 1e3:.0f})", (v.p(R - 0.3, 0)[0], v.p(0, (za + zb_) / 2 + 0.25)[1]), 1.8, TA.MIDDLE_RIGHT)
    nv = lambda dia_sp, dd: f"{math.ceil(math.pi * dd * 1e3 / dia_sp[1])} - {dia_sp[0]} # @ {dia_sp[1]} C/C"
    zm = (lev["wall_top"] + lev["B2_top"]) / 2 + 0.6
    sh.leader(v.p(R + cw, zm), v.p(R - 1.2, zm + 0.5), [nv(w["vert"], 2 * R), "VERTICAL, EACH FACE"], 1.8, right=False)
    sh.leader(v.p(R + cw, lev["B2_top"] + 0.35), v.p(R - 1.2, lev["B2_top"] + 0.95), [nv(w["base_in"], 2 * R), f"VERTICAL AT THE BASE, WATER FACE, {w['base_len'] * 1e3:.0f} LONG"], 1.8, right=False)
    sh.text(f"WALL {w['t']} THICK, {w['tb']} AT THE BASE", (v.p(R - 0.3, 0)[0], v.p(0, zm + 1.6)[1]), 1.9, TA.MIDDLE_RIGHT)
    sh.leader_bar(v.p(g["bal_edge"] - 0.3, lev["B2_top"] - cw), v.p(g["bal_edge"] - 0.2, lev["B2_top"] + 1.5),
              [f"BALCONY {bl['w'] * 1e3:.0f} WIDE, {bl['t']} THICK", f"{nb((bl['n'], bl['dia']))} HOOPS", at(bl["rad"], "RADIALLY") + " AT TOP", at(bl["dist"], "RADIALLY") + " AT BOTTOM"], 1.8)
    pc = ((r0 + R) / 2 + nx * cw, (lev["LWL"] + lev["cone_top"]) / 2 + nz * cw)
    sh.leader_bar(v.p(*pc), v.p(pc[0] - 3.0, pc[1] + 1.3), [f"CONICAL DOME {cn['t']} THICK", f"{cn['n_low']} - {cn['hoop_low'][0]} # HOOPS @ {cn['hoop_low'][1]} (LOWER HALF) AND",
              f"{cn['n_up']} - {cn['hoop_up'][0]} # HOOPS @ {cn['hoop_up'][1]} (UPPER HALF) ON EACH FACE",
              f"{math.ceil(math.pi * (R + r0) * 1e3 / cn['mer'][1])} - {at(cn['mer'], 'RADIALLY')} ON EACH FACE"], 1.8, right=False)
    pb = ((R2 - cw) * math.sin(a2 * 0.45), zc2 + (R2 - cw) * math.cos(a2 * 0.45))
    sh.leader_bar(v.p(*pb), v.p(pb[0] - 1.0, pb[1] + 1.6), [f"BOTTOM DOME {bd['t']} THICK ({bd['te']} AT THE EDGE)", at(bd["rad"], "RADIALLY") + " AND", at(bd["hoop"], "HOOPS") + " ON EACH FACE"], 1.9)
    pe2 = ((R2 - cw) * math.sin(a2 * 0.93), zc2 + (R2 - cw) * math.cos(a2 * 0.93))
    sh.leader_bar(v.p(*pe2), v.p(pe2[0] - 3.2, pe2[1] - 1.1), [f"{math.ceil(bd['edge'] * 1e3 / bd['edge_hoop'][1])} - {bd['edge_hoop'][0]} # HOOPS AND",
              f"{math.ceil(2 * math.pi * r0 * 1e3 / bd['edge_rad'][1])} - {at(bd['edge_rad'], 'RADIALLY')}", f"AT TOP, IN {bd['edge'] * 1e3:.0f} FROM THE EDGE"], 1.8, right=False)
    sh.leader_rows(b3dots, rb, v.p(r0 + 1.5, lev["B3_bot"] - 0.2), label=
              [f"BOTTOM RING BEAM {br['b']} x {br['d']}", f"{nb(br['top'])} HOOPS AT TOP, {nb(br['bot'])} AT BOTTOM", f"10 # {br['legs']}-LEGGED STIRRUPS (SEE PART L-SECTION)"], h=1.8)
    yb = v.p(0, zb + 0.15)[1]
    sh.dim_h(v.p(0, 0)[0], v.p(r0, 0)[0], yb, f"R = {r0 * 1e3:.0f}")
    sh.dim_h(v.p(0, 0)[0], v.p(R, 0)[0], v.p(0, lev["FSL"] - 0.8)[1], f"R = {R * 1e3:.0f}")
    sh.text(f"R = {R1 * 1e3:.0f}", v.p(R * 0.45, zc1 + R1 * math.cos(math.asin(R * 0.45 / R1)) - 0.5), 1.8, TA.MIDDLE_CENTER)
    sh.text(f"R = {R2 * 1e3:.0f}", v.p(r0 * 0.25, zc2 + R2 * math.cos(math.asin(r0 * 0.25 / R2)) - 0.6), 1.8, TA.MIDDLE_CENTER)
    xd = v.p(0, 0)[0] + 9
    for z1, z2 in ((lev["LWL"], lev["dome2_crown"]),):
        sh.dim_v(v.p(0, z1)[1], v.p(0, z2)[1], xd, f"{(z2 - z1) * 1e3:.0f}", h=1.7)
    xr = v.p(g["bal_edge"], 0)[0] + 30
    for z1, z2 in ((lev["B3_bot"], lev["LWL"]), (lev["LWL"], lev["cone_top"]), (lev["cone_top"], lev["B2_top"]), (lev["B2_top"], lev["wall_top"]),
                   (lev["wall_top"], lev["B1_top"]), (lev["B1_top"], lev["dome1_crown"])):
        sh.dim_v(v.p(0, z1)[1], v.p(0, z2)[1], xr, f"{(z2 - z1) * 1e3:.0f}", h=1.7)
    sh.heading("SECTION OF TANK", (x0 + bw / 2 - 20, y0 + 4), 3.0, f"SCALE 1:{s}")


def _dome_plan(sh, res, key, x0, y0, bw, bh, title):
    g, m = res["geo"], res["members"][key]
    a = g["R"] if key == "top_dome" else g["r0"]
    s = fit_scale(a + 0.3, 1.0, bw - 16, 1e9)
    n = math.ceil(2 * math.pi * a * 1e3 / m["rad"][1])
    ne = math.ceil(2 * math.pi * a * 1e3 / m["edge_rad"][1])
    P, hphi = _sector(sh, x0 + bw - 8, y0 + bh / 2 + 4, s, 0.0, a, min(bh - 34, 46),
                      [(a / 2, a, n), (0.25, a / 2, max(4, n // 2)), (a - m["edge"], a, ne)],
                      [(0.3, a - m["edge"], m["hoop"][1] / 1e3), (a - m["edge"], a, m["edge_hoop"][1] / 1e3)])
    pm = P(a * 0.62, -hphi)
    sh.text(f"{at(m['hoop'], 'HOOPS')};  {n} - {at(m['rad'], 'RADIALLY')} AT THE EDGE, ALTERNATE BARS STOP HALF WAY", (P(a, -hphi)[0], pm[1] - 7.5), 1.7)
    sh.text(f"EDGE {m['edge'] * 1e3:.0f}: {math.ceil(m['edge'] * 1e3 / m['edge_hoop'][1])} - {m['edge_hoop'][0]} # HOOPS, {ne} - {at(m['edge_rad'], 'RADIALLY')} AT TOP", (P(a, -hphi)[0], pm[1] - 11), 1.7)
    sh.heading(title, (x0 + bw / 2, y0 + 4), 2.6, f"SCALE 1:{s}")


def _small_details(sh, res, x0, y0):
    """Ventilator, manhole, ladder and pipe fixing, as on the example's sheet 2 (fixed details)."""
    # ventilator
    sh.heading("DETAILS OF VENTILATOR", (x0 + 40, y0 + 4), 2.4)
    yb = y0 + 14
    sh.rect(x0 + 8, yb + 22, x0 + 72, yb + 25)
    for x in (x0 + 16, x0 + 64):
        sh.line((x, yb + 6), (x, yb + 22))
    sh.poly([(x0 + 2, yb + 3), (x0 + 16, yb + 6), (x0 + 16, yb), (x0 + 2, yb)], "OUTLINE", True)
    sh.poly([(x0 + 78, yb + 3), (x0 + 64, yb + 6), (x0 + 64, yb), (x0 + 78, yb)], "OUTLINE", True)
    for i in range(7):
        sh.dot((x0 + 12 + i * 9.3, yb + 23.5), 0.4)
    sh.line((x0 + 40, yb + 25), (x0 + 40, yb + 34))
    sh.leader((x0 + 40, yb + 33), (x0 + 46, yb + 34), "LIGHTNING CONDUCTOR", 1.6)
    sh.leader((x0 + 50, yb + 23.5), (x0 + 76, yb + 28), "8 # @ 200 MESH C/C", 1.6)
    sh.leader((x0 + 64, yb + 14), (x0 + 76, yb + 17), ["FLY MESH OVER EXPANDED METAL", "ON 9 ISA 50x50x6 POSTS"], 1.6)
    sh.dim_h(x0 + 16, x0 + 64, yb - 4, "DIA = 1500", below=True)
    # manhole
    x1 = x0 + 122
    sh.heading("MANHOLE", (x1 + 30, y0 + 4), 2.4)
    sh.poly([(x1, yb + 4), (x1 + 20, yb + 9), (x1 + 20, yb + 12), (x1, yb + 7)], "OUTLINE", True)
    sh.poly([(x1 + 42, yb + 14.5), (x1 + 62, yb + 19.5), (x1 + 62, yb + 22.5), (x1 + 42, yb + 17.5)], "OUTLINE", True)
    sh.rect(x1 + 18, yb + 10, x1 + 22, yb + 15)
    sh.rect(x1 + 40, yb + 15.5, x1 + 44, yb + 20.5)
    sh.poly(arc_pts(x1 + 31, yb + 6, 22, math.radians(55), math.radians(125), 12), "THIN")
    sh.leader((x1 + 31, yb + 28), (x1 + 44, yb + 31), "18 GAUGE G.I. SHEET COVER", 1.6)
    sh.leader((x1 + 20, yb + 13), (x1 + 6, yb + 22), "ISA 50x50x6", 1.6, right=False)
    sh.leader((x1 + 43, yb + 16.5), (x1 + 56, yb + 9), ["6 DIA ANCHOR BARS 300 LONG", "4 - 8 # HOOPS ROUND THE OPENING"], 1.6)
    sh.text("DIA = 600", (x1 + 31, yb + 8), 1.6, TA.MIDDLE_CENTER, rot=14)
    # ladder
    x2 = x0 + 8
    y2 = y0 + 62
    sh.heading("STEEL LADDER (INSIDE THE TANK)", (x2 + 40, y2), 2.4)
    sh.poly([(x2 + 8, y2 + 18), (x2 + 8, y2 + 12), (x2 + 72, y2 + 12), (x2 + 72, y2 + 18)])
    sh.leader((x2 + 30, y2 + 12), (x2 + 34, y2 + 22), "20 DIA M.S. BARS @ 250 C/C", 1.6)
    sh.leader((x2 + 8, y2 + 14), (x2 + 4, y2 + 8), "ISA 50x50x6", 1.6)
    sh.dim_h(x2 + 8, x2 + 72, y2 + 8, "600", below=True)
    # pipe fixing
    x3 = x0 + 122
    sh.heading("DETAILS FOR FIXING INLET / OUTLET PIPE", (x3 + 34, y2), 2.4)
    sh.circle((x3 + 30, y2 + 30), 9)
    sh.circle((x3 + 30, y2 + 30), 14, "THIN")
    for a in (45, 135):
        ca, sa_ = math.cos(math.radians(a)), math.sin(math.radians(a))
        for off in (-12, 12):
            sh.line((x3 + 30 - 24 * ca - off * sa_, y2 + 30 - 24 * sa_ + off * ca), (x3 + 30 + 24 * ca - off * sa_, y2 + 30 + 24 * sa_ + off * ca), "REBAR2")
    sh.circle((x3 + 30, y2 + 30), 11.5, "REBAR")
    sh.leader((x3 + 39, y2 + 30), (x3 + 58, y2 + 26), ["PIPE WITH PUDDLE COLLAR", "4 - 10 # HOOPS", "16 - 10 #, 1500 LONG", "8 # STIRRUPS IN THE DOME'S THICKENING"], 1.6)


def _sheet_container(dw, res, info):
    sh = Sheet(dw, 1, "CONTAINER", 2)
    g, M, opt, th = res["geo"], res["members"], res["opt"], res["geo"]["th"]
    _tank_section(sh, res, 14, 22, 470, 560)
    br, col, tr_ = M["bottom_ring"], M["column"], M["top_ring"]
    # top ring beam
    s = fit_scale(tr_["b"] / 1e3 + 0.1, tr_["d"] / 1e3 + 0.1, 40, 40)
    _beam_xsec(sh, 520, 575, s, tr_["b"], tr_["d"], (tr_["n"] // 2, tr_["dia"]), (tr_["n"] - tr_["n"] // 2, tr_["dia"]), opt["cover_water_mm"],
               "TOP RING BEAM", note="8 # STR @ 200 C/C")
    _dome_plan(sh, res, "top_dome", 590, 500, 240, 84, "PART PLAN OF TOP DOME REINFORCEMENT")
    _dome_plan(sh, res, "bottom_dome", 590, 410, 240, 84, "PART PLAN OF BOTTOM DOME REINFORCEMENT (EACH FACE)")
    s2 = fit_scale(g["Lb"] + g["dc"] + 1.3, th["d3"] + 1.8, 190, 95)
    _lsec(sh, 520, 318, s2, g["Lb"], g["dc"], th["d3"], 0.0, 1.0, br["stir"], br["legs"],
          f"{nb(br['top'])} HOOPS (OVERLAP NEAR MIDSPAN ONLY)", f"{nb(br['bot'])} HOOPS (OVERLAP NEAR SUPPORT ONLY)",
          [nb((col["n"], col["dia"])), "8 # RINGS @ 100 / 200 C/C"], "PART L - SECTION OF BOTTOM RING BEAM")
    s3 = fit_scale(br["b"] / 1e3 + 0.1, br["d"] / 1e3 + 0.1, 45, 50)
    _beam_xsec(sh, 770, 372, s3, br["b"], br["d"], br["top"], br["bot"], opt["cover_ring_mm"], "SECTION A - A", side=br["side"][0], legs=br["legs"], note="10 # STR.")
    _small_details(sh, res, 492, 82)
    sh.lines(["NOTES:  1. ALL DIMENSIONS ARE IN MILLIMETRE.   2. READ WITH SHEETS 1 AND 3."], 492, 78, 1.9)
    sh.frame(info)
    return sh


# -------------------------------------------------------------------------------------------- sheet 3: the staircase
def _sheet_stair(dw, res, info, index):
    sh = Sheet(dw, index, "STAIRCASE", index + 1)
    g, _lev, M, opt = res["geo"], res["levels"], res["members"], res["opt"]
    st = M["stair"]
    xs, w, gap, lc, Lb, dc = st["xs"], st["w"], st["gap"], st["lc"], st["Lb"], g["dc"]
    r0, n = g["r0"], g["n_col"]
    rl = w + gap / 2
    # plans
    ext_x, ext_y = xs + rl + 0.8 - (st["xc"] - 1.2), Lb + 2 * rl + 1.2
    s = fit_scale(ext_x, ext_y, 175, 150)
    k = 1000.0 / s

    def plan(x0, y0, title, level, extra=None):
        P = lambda x, y: (x0 + (x - st["xc"] + 1.2) * k, y0 + 12 + (y + ext_y / 2) * k)
        for a in (math.pi / n, -math.pi / n):
            sh.circle(P(r0 * math.cos(a), r0 * math.sin(a)), dc / 2 * k)
        for sg in (1, -1):                                         # the braces to the next columns
            a, b_ = sg * math.pi / n, sg * 3 * math.pi / n
            pa, pb = (r0 * math.cos(a), r0 * math.sin(a)), (r0 * math.cos(b_), r0 * math.sin(b_))
            t_ = 0.45
            sh.line(P(*pa), P(pa[0] + (pb[0] - pa[0]) * t_, pa[1] + (pb[1] - pa[1]) * t_), "HIDDEN")
        sh.line(P(st["xc"], -Lb / 2), P(st["xc"], Lb / 2), "HIDDEN")
        _stair_plan(sh, P, res, k)
        if extra:
            extra(P)
        sh.text(f"{dc * 1e3:.0f} DIA COLUMN", P(st["xc"] - 0.9, Lb / 2 + 0.75), 1.7)
        sh.text(f"{st['col']['d']} DIA STAIRCASE COLUMN", P(xs - 0.4, Lb / 2 + rl + 0.35), 1.7, TA.MIDDLE_CENTER)
        sh.dim_h(P(st["xc"], 0)[0], P(xs, 0)[0], P(0, -Lb / 2 - rl)[1] - 4, f"{(xs - st['xc']) * 1e3:.0f}", below=True)
        sh.dim_h(P(xs - rl, 0)[0], P(xs - gap / 2, 0)[0], P(0, -Lb / 2 - rl)[1] - 10, f"{w * 1e3:.0f}", below=True)
        sh.dim_h(P(xs - gap / 2, 0)[0], P(xs + gap / 2, 0)[0], P(0, -Lb / 2 - rl)[1] - 10, f"{gap * 1e3:.0f}", below=True)
        sh.dim_h(P(xs + gap / 2, 0)[0], P(xs + rl, 0)[0], P(0, -Lb / 2 - rl)[1] - 10, f"{w * 1e3:.0f}", below=True)
        sh.dim_v(P(0, -Lb / 2)[1], P(0, Lb / 2)[1], P(xs + rl, 0)[0] + 7, f"{Lb * 1e3:.2f}")
        sh.text(level, P(xs, 0), 1.7, TA.MIDDLE_CENTER, rot=90)
        sh.heading(title, (x0 + ext_x * k / 2, y0 + 3), 2.6, f"SCALE 1:{s}")

    plan(18, 400, "GROUND FLOOR PLAN", f"UP - 1ST FLIGHT TO RL {st['levels'][0] * 1e3:.0f}")

    def balc(P):
        for r_, layer in ((g["bal_edge"], "OUTLINE"), (g["R"] + g["th"]["twb"], "HIDDEN")):
            hy = min(Lb / 2 + rl, r_ * 0.9)
            a = math.asin(hy / r_)
            sh.poly([P(r_ * math.cos(-a + 2 * a * i / 20), r_ * math.sin(-a + 2 * a * i / 20)) for i in range(21)], layer)
        sh.text("BALCONY", P(g["bal_edge"] - 0.5, 0), 1.8, TA.MIDDLE_CENTER, rot=90)
    plan(18, 215, "BALCONY LEVEL PLAN", f"RL {st['bal'] * 1e3:.0f}", balc)
    plan(18, 30, "ROOF LEVEL PLAN", f"RL {st['roof'] * 1e3:.0f} (TOP RING BEAM)", balc)
    # typical flight
    x0, y0 = 230, 420
    go, rise = st["treads"] * st["tread"], st["risers"] * st["riser1"]
    s2 = fit_scale(go + 2 * rl + 0.6, rise + 1.6, 250, 120)
    v = View(sh, x0 + 6, y0 + 16, s2, 0.0, -0.4)
    wt = st["waist"] / 1e3
    rz, tz = st["riser1"], st["tread"]
    kk = rz / tz                                      # slope of the line of the steps' inner corners
    sec = math.hypot(1.0, kk)
    xe = rl + go + rl                                 # the end of the upper landing
    pts = [(0, 0), (rl, 0)]
    for j in range(st["risers"]):
        x = rl + j * tz
        pts += [(x, (j + 1) * rz), (min(x + tz, rl + go), (j + 1) * rz)]
    pts += [(xe, rise)]
    # the soffit: the waist measured square to the line of the inner corners z = (x - rl) k, the landings flat
    soff = lambda w_: [(xe, rise - w_), (rl + (rise - w_ + w_ * sec) / kk, rise - w_), (rl + w_ * (sec - 1.0) / kk, -w_), (0, -w_)]
    v.shape(pts + soff(wt))
    c = opt["cover_stair_mm"] / 1e3
    # main bars: the soffit at the cover, the length of both landings, hooked at the ends
    mb = soff(wt - c)[::-1]
    mb = [(c, mb[0][1]), mb[1], mb[2], (xe - c, mb[3][1])]
    hooked(v, mb, inside=((rl / 2, -wt / 2), (xe - rl / 2, rise - wt / 2)))
    v.dots([(mb[1][0] + 0.05, mb[1][1] + 0.025 + 0.05 * kk), (mb[2][0] - 0.05, mb[2][1] + 0.025 - 0.05 * kk)], st["dist"][1] / 1e3, 0.35)
    # top bars of the landings: over the supports, then into the flight along the steps' inner corners
    xl = rl + c * (sec - 1.0) / kk                    # where z = -c meets the corner line less the cover
    tb1 = [(c, -c), (xl, -c), (xl + 0.3 * go, -c * sec + (xl + 0.3 * go - rl) * kk)]
    hooked(v, tb1, inside=((rl / 2, -wt / 2), (rl + 0.3 * go, 0.3 * go * kk - wt / 2)))
    xu = rl + go - 0.3 * go
    tb2 = [(xe - c, rise - c), (rl + go, rise - c), (xu, rise - c - (rl + go - xu) * kk)]
    hooked(v, tb2, inside=((xe - rl / 2, rise - wt / 2), (xu, (xu - rl) * kk - wt / 2)))
    v.dots([(c + 0.05, -c - 0.025), (xl - 0.02, -c - 0.025)], st["dist"][1] / 1e3, 0.3, first=st["dist"][1] / 1e3)
    v.dots([(rl + go + 0.02, rise - c - 0.025), (xe - c - 0.05, rise - c - 0.025)], st["dist"][1] / 1e3, 0.3, first=st["dist"][1] / 1e3)
    v.dots([(c + 0.05, -wt + c + 0.025), (mb[1][0] - 0.05, -wt + c + 0.025)], st["dist"][1] / 1e3, 0.3)
    v.dots([(mb[2][0] + 0.05, rise - wt + c + 0.025), (xe - c - 0.05, rise - wt + c + 0.025)], st["dist"][1] / 1e3, 0.3)
    for x, z in ((rl * 0.5, 0.0), (rl + go + rl * 0.5, rise)):
        bd_, bb_ = st["beam"]["d"] / 1e3, st["beam"]["b"] / 1e3
        v.rect(x - bb_ / 2, z - bd_, x + bb_ / 2, z - wt, "HIDDEN")
    for j in range(0, st["risers"] + 1, 3):                        # railing
        x = rl + j * st["tread"]
        z = min(j, st["risers"]) * st["riser1"]
        v.line((x, z), (x, z + 1.0), "THIN")
    v.line((rl, 1.0), (rl + go, rise + 1.0), "THIN")
    v.line((rl, 0.55), (rl + go, rise + 0.55), "THIN")
    pm = (rl + go * 0.5, (go * 0.5) * kk - (wt - c) * sec)
    sh.leader(v.p(*pm), v.p(pm[0] + 0.5, pm[1] - 0.8), [at(st["main"]) + " (MAIN)", at(st["dist"]) + " (DISTRIBUTION)", f"WAIST SLAB {st['waist']} THICK"], 1.8)
    sh.leader(v.p(rl + go * 0.3, rise * 0.3 + 1.0), v.p(rl + go * 0.05, rise * 0.3 + 1.9), ["3 - 20 DIA G.I. PIPE RAILING", "ON ISA 50x50x6 POSTS"], 1.7)
    sh.dim_h(v.p(rl, 0)[0], v.p(rl + go, 0)[0], v.p(0, -0.4)[1] - 3, f"{st['treads']} TREADS x {st['tread'] * 1e3:.0f} = {go * 1e3:.0f}", below=True)
    sh.dim_h(v.p(0, 0)[0], v.p(rl, 0)[0], v.p(0, -0.4)[1] - 3, f"{rl * 1e3:.0f}", below=True)
    sh.dim_v(v.p(0, 0)[1], v.p(0, rise)[1], v.p(rl + go + rl, 0)[0] + 6, f"{st['risers']} RISERS x {st['riser1'] * 1e3:.0f} = {rise * 1e3:.0f}")
    sh.heading("TYPICAL L - SECTION OF STAIRCASE FLIGHT", (x0 + 125, y0 + 3), 2.6, f"SCALE 1:{s2}")
    # landing beam
    bm = st["beam"]
    s3 = fit_scale(st["L1"] + lc + dc + 0.8, bm["d"] / 1e3 + 1.6, 250, 70)
    k3 = 1000.0 / s3
    X = lambda x: 236 + 6 + x * k3
    Z = lambda z: 300 + 34 + z * k3
    bd_ = bm["d"] / 1e3
    ds = st["col"]["d"] / 1e3
    L1 = st["L1"]
    sh.rect(X(0), Z(-0.7), X(dc), Z(bd_ + 0.7))
    sh.rect(X(dc), Z(0), X(dc + L1 + ds + lc - ds / 2), Z(bd_))
    sh.rect(X(dc + L1), Z(-0.7), X(dc + L1 + ds), Z(0), "OUTLINE")
    sh.line((X(dc + L1), Z(bd_)), (X(dc + L1), Z(bd_ + 0.7)))
    sh.line((X(dc + L1 + ds), Z(bd_)), (X(dc + L1 + ds), Z(bd_ + 0.7)))
    xe = dc + L1 + ds / 2 + lc
    sh.poly([(X(0.08), Z(bd_ - 0.3)), (X(0.08), Z(bd_ - 0.04)), (X(xe - 0.04), Z(bd_ - 0.04)), (X(xe - 0.04), Z(bd_ - 0.2))], "REBAR")
    sh.poly([(X(0.08), Z(0.3)), (X(0.08), Z(0.04)), (X(xe - 0.04), Z(0.04)), (X(xe - 0.04), Z(0.2))], "REBAR")
    x = dc + 0.05
    while x < xe - 0.05:
        if not (dc + L1 < x < dc + L1 + ds):
            sh.line((X(x), Z(0.04)), (X(x), Z(bd_ - 0.04)), "REBAR2")
        x += 0.15
    sh.leader((X(dc + L1 * 0.4), Z(bd_ - 0.04)), (X(dc + L1 * 0.45), Z(bd_ + 0.5)), nb(bm["top"]), 1.8)
    sh.leader((X(dc + L1 * 0.5), Z(0.04)), (X(dc + L1 * 0.55), Z(-0.5)), nb(bm["bot"]), 1.8)
    sh.text("8 # STIRRUPS @ 150 C/C", (X(dc + L1 * 0.75), Z(bd_ + 0.25)), 1.8, TA.MIDDLE_CENTER)
    sh.text(f"{bm['b']} x {bm['d']}", (X(dc + L1 * 0.2), Z(bd_ / 2)), 1.8, TA.MIDDLE_CENTER)
    sh.dim_h(X(dc), X(dc + L1), Z(-0.7) - 3, f"{L1 * 1e3:.0f}", below=True)
    sh.dim_h(X(dc + L1 + ds / 2), X(xe), Z(-0.7) - 3, f"{lc * 1e3:.0f}", below=True)
    sh.dim_h(X(0), X(dc), Z(-0.7) - 3, f"{dc * 1e3:.0f}", below=True)
    sh.text("COLUMN OF THE STAGING", (X(dc / 2), Z(bd_ + 0.95)), 1.6, TA.MIDDLE_CENTER)
    sh.text("STAIRCASE COLUMN", (X(dc + L1 + ds / 2), Z(bd_ + 0.95)), 1.6, TA.MIDDLE_CENTER)
    sh.heading("LANDING BEAM B1 (AT EVERY LANDING)", (236 + 125, 300 + 3), 2.6, f"SCALE 1:{s3}")
    # the staircase's column and footing
    cs, ft = st["col"], st["footing"]
    s4 = fit_scale(ft["side"] + 0.4, ft["side"] + 0.4, 95, 95)
    k4 = 1000.0 / s4
    fx, fy_ = 236 + 55, 215
    hs = ft["side"] / 2 * k4
    sh.rect(fx - hs, fy_ - hs - 40, fx + hs, fy_ + hs - 40)
    sh.circle((fx, fy_ - 40), cs["d"] / 2e3 * k4)
    hp = (cs["d"] / 2e3 + 0.075) * k4                # the flat top round the column: 75 mm offset (practice)
    sh.rect(fx - hp, fy_ - 40 - hp, fx + hp, fy_ - 40 + hp)
    for sgx in (-1, 1):                              # the sloping faces: from the edge's corners to the flat top's
        for sgy in (-1, 1):
            sh.line((fx + sgx * hs, fy_ - 40 + sgy * hs), (fx + sgx * hp, fy_ - 40 + sgy * hp), "THIN")
    sh.dim_h(fx - hp, fx + hp, fy_ - 40 + hp + 3, f"{2 * (cs['d'] / 2e3 + 0.075) * 1e3:.0f}", y_from=fy_ - 40 + hp)
    sh.dim_h(fx - hs, fx + hs, fy_ - hs - 44, f"{ft['side'] * 1e3:.0f}", below=True)
    sh.dim_v(fy_ - hs - 40, fy_ + hs - 40, fx - hs - 5, f"{ft['side'] * 1e3:.0f}")
    sh.heading("PLAN OF FOOTING FOR STAIRCASE COLUMN", (fx, fy_ - hs - 58), 2.6, f"SCALE 1:{s4}")
    # its section
    sx, sy = 236 + 180, 150
    t_, te_ = ft["t"] / 1e3 * k4, ft["te"] / 1e3 * k4
    cr = cs["d"] / 2e3 * k4
    hp = (cs["d"] / 2e3 + 0.075) * k4
    sh.poly([(sx - hs, sy), (sx + hs, sy), (sx + hs, sy + te_), (sx + hp, sy + t_), (sx - hp, sy + t_), (sx - hs, sy + te_)], "OUTLINE", True)
    sh.text("75", (sx + (cr + hp) / 2, sy + t_ + 1.2), 1.5, TA.BOTTOM_CENTER, "DIM")
    sh.rect(sx - hs - 2, sy - 2.5, sx + hs + 2, sy, "THIN")
    sh.rect(sx - cr, sy + t_, sx + cr, sy + t_ + 34)
    sh.poly([(sx - hs + 1.5, sy + 4), (sx - hs + 1.5, sy + 1.5), (sx + hs - 1.5, sy + 1.5), (sx + hs - 1.5, sy + 4)], "REBAR")
    xx = sx - hs + 3
    while xx < sx + hs - 2:
        sh.dot((xx, sy + 2.3), 0.4)
        xx += ft["bars"][1] / 1e3 * k4
    for sg in (-1, 1):
        sh.poly([(sx + sg * (cr - 1.5), sy + t_ + 34), (sx + sg * (cr - 1.5), sy + 2.6), (sx + sg * (cr + 6), sy + 2.6)], "REBAR")
    zz = sy + t_ + 3
    while zz < sy + t_ + 33:
        sh.line((sx - cr + 1.2, zz), (sx + cr - 1.2, zz), "REBAR2")
        zz += 0.2 * k4
    sh.leader((sx + hs * 0.5, sy + 1.5), (sx + hs * 0.6, sy - 9), at(ft["bars"]) + " EACH WAY", 1.8)
    sh.leader((sx + cr - 1.5, sy + t_ + 22), (sx + cr + 8, sy + t_ + 26), [nb((cs["n"], cs["dia"])), "8 # RINGS @ 200 C/C"], 1.8)
    sh.dim_v(sy, sy + t_, sx - hs - 5, f"{ft['t']}")
    sh.dim_v(sy, sy + te_, sx + hs + 6, f"{ft['te']}")
    sh.text("100 P.C.C.", (sx + hs + 3, sy - 1.2), 1.6)
    sh.heading("SECTION OF THE FOOTING AND STAIRCASE COLUMN", (sx, sy - 16), 2.6, f"SCALE 1:{s4}")
    # table of the flights
    tx, ty = 500, 575
    sh.heading("FLIGHTS", (tx + 60, ty), 2.8)
    heads = [("FLIGHT", 22), ("FROM RL", 26), ("TO RL", 26), ("RISERS", 24), ("SIDE", 34)]
    ty -= 6
    rh = 5.2
    rows = []
    z_prev = 0.0
    for i, z in enumerate(st["levels"], 1):
        ris = st["riser1"] if i <= st["n1"] else st["riser2"]
        rows.append([ordinal(i), f"{z_prev * 1e3:.0f}", f"{z * 1e3:.0f}", f"{st['risers']} x {ris * 1e3:.0f}",
                     "INNER (TANK SIDE)" if (st["n1"] - i) % 2 == 0 else "OUTER"])
        z_prev = z
    tw_ = sum(w_ for _, w_ in heads)
    sh.rect(tx, ty - rh * (len(rows) + 1), tx + tw_, ty, "THIN")
    xx = tx
    for name, w_ in heads:
        sh.text(name, (xx + w_ / 2, ty - rh / 2), 1.8, TA.MIDDLE_CENTER, style=B)
        xx += w_
        sh.line((xx, ty), (xx, ty - rh * (len(rows) + 1)), "THIN")
    for r_ in rows:
        ty -= rh
        sh.line((tx, ty), (tx + tw_, ty), "THIN")
        xx = tx
        for (name, w_), val in zip(heads, r_):
            sh.text(val, (xx + w_ / 2, ty - rh / 2), 1.7, TA.MIDDLE_CENTER)
            xx += w_
    ty -= rh + 8
    sh.lines([f"BALCONY RL {st['bal'] * 1e3:.0f};  ROOF (TOP RING BEAM) RL {st['roof'] * 1e3:.0f}.",
              f"TREADS {st['tread'] * 1e3:.0f} WIDE, {st['treads']} IN A FLIGHT; WIDTH OF STAIRCASE {w * 1e3:.0f}.",
              f"THE STAIRCASE IS CARRIED ON TWO SEPARATE COLUMNS OF {cs['d']} DIA AT {Lb * 1e3:.1f} C/C,",
              f"{(xs - st['xc']) * 1e3:.0f} FROM THE COLUMNS OF THE STAGING; A LANDING BEAM B1 AT EVERY LANDING.",
              "LANDINGS: SLAB OF THE WAIST'S THICKNESS, 8 # @ 150 C/C BOTH WAYS.",
              "", "NOTES:  1. ALL DIMENSIONS ARE IN MILLIMETRE.   2. READ WITH SHEETS 1 AND 2."], tx, ty, 1.9, 3.6)
    sh.frame(info)
    return sh


# ------------------------------------------------------------------------------------------------- bar schedule
def _sheets_bbs(dw, res, info, start):
    rows = res["bbs"]
    conc, steel = intze.quantities(res)
    per = 66
    chunks = [rows[i:i + per] for i in range(0, len(rows), per)] or [[]]
    sheets = []
    cols = [("S.No", 12), ("Member", 40), ("Mark", 14), ("Description", 126), ("Dia", 12), ("Nos", 16),
            ("Length m", 20), ("Total m", 22), ("Weight kg", 24), ("Shape", 34)]
    k = 0
    for ci, chunk in enumerate(chunks):
        sh = Sheet(dw, start + ci, "BAR BENDING SCHEDULE" + (f" ({ci + 1})" if len(chunks) > 1 else ""), start + ci + 1)
        x0, y = 20.0, 572.0
        sh.heading(sh.title, (x0 + 160, y), 3.4)
        y -= 9
        rh = 7.0
        tw = sum(w for _, w in cols)
        sh.rect(x0, y - rh * (len(chunk) + 1), x0 + tw, y, "THIN")
        xx = x0
        for name, w in cols:
            sh.text(name, (xx + w / 2, y - rh / 2), 2.2, TA.MIDDLE_CENTER, style=B)
            xx += w
            sh.line((xx, y), (xx, y - rh * (len(chunk) + 1)), "THIN")
        for r in chunk:
            k += 1
            y -= rh
            sh.line((x0, y), (x0 + tw, y), "THIN")
            vals = [k, r["member"], r["mark"], r["desc"][:78], r["dia"], r["no"], f"{r['length']:.2f}", f"{r['total_m']:.1f}",
                    f"{r['kg']:.1f}", r["shape"]]
            xx = x0
            for (name, w), val in zip(cols, vals):
                al = TA.MIDDLE_LEFT if name in ("Member", "Description", "Shape") else TA.MIDDLE_RIGHT
                sh.text(val, (xx + (1.5 if al == TA.MIDDLE_LEFT else w - 1.5), y - rh / 2), 1.9, al)
                xx += w
        if ci == len(chunks) - 1:
            _summary(sh, res, conc, steel, x0 + tw + 14, 560)
        sh.frame(info)
        sheets.append(sh)
    return sheets


def _summary(sh, res, conc, steel, x, y):
    by_dia = {}
    for r in res["bbs"]:
        by_dia[r["dia"]] = by_dia.get(r["dia"], 0.0) + r["kg"]
    sh.heading("STEEL BY DIA (kg)", (x + 45, y), 3.0)
    yy = y - 8
    for d in sorted(by_dia):
        sh.text(f"{d} mm", (x, yy), 2.3)
        sh.text(f"{by_dia[d]:,.0f}", (x + 90, yy), 2.3, TA.MIDDLE_RIGHT)
        yy -= 5
    sh.text("Total", (x, yy), 2.4, style=B)
    sh.text(f"{sum(by_dia.values()):,.0f}", (x + 90, yy), 2.4, TA.MIDDLE_RIGHT, style=B)
    yy -= 14
    sh.heading("QUANTITIES BY MEMBER", (x + 45, yy), 3.0)
    yy -= 8
    sh.text("Member", (x, yy), 2.2, style=B)
    sh.text("Conc. m3", (x + 65, yy), 2.2, TA.MIDDLE_RIGHT, style=B)
    sh.text("Steel kg", (x + 90, yy), 2.2, TA.MIDDLE_RIGHT, style=B)
    yy -= 5
    for n in dict.fromkeys(list(conc) + list(steel)):
        sh.text(n, (x, yy), 2.1)
        sh.text(f"{conc.get(n, 0):.1f}" if n in conc else "-", (x + 65, yy), 2.1, TA.MIDDLE_RIGHT)
        sh.text(f"{steel.get(n, 0):,.0f}" if n in steel else "-", (x + 90, yy), 2.1, TA.MIDDLE_RIGHT)
        yy -= 4.6
    sh.text("Total", (x, yy), 2.3, style=B)
    sh.text(f"{sum(conc.values()):.1f}", (x + 65, yy), 2.3, TA.MIDDLE_RIGHT, style=B)
    sh.text(f"{sum(steel.values()):,.0f}", (x + 90, yy), 2.3, TA.MIDDLE_RIGHT, style=B)
    yy -= 6
    sh.text(f"Steel {sum(steel.values()) / max(sum(conc.values()), 1):.0f} kg / m3 of concrete", (x, yy), 2.1)
    yy -= 12
    if res["warnings"]:
        sh.heading("CHECKS TO LOOK AT", (x + 45, yy), 3.0)
        rows = []
        for wtxt in res["warnings"]:
            words, line = wtxt.split(), ""
            for wd in words:
                if len(line) + len(wd) > 58:
                    rows.append(line)
                    line = ""
                line = (line + " " + wd).strip()
            rows.append(line)
            rows.append("")
        sh.lines(rows, x, yy - 8, 2.0, 3.6)


# --------------------------------------------------------------------------------------------------------- export
def _new_doc():
    doc = ezdxf.new("R2010", setup=True, units=4)
    for name, (col, lw, lt) in LAYERS.items():
        if name not in doc.layers:
            doc.layers.add(name, color=col, linetype=lt, lineweight=lw)
    doc.header["$LTSCALE"] = 1.0
    doc.header["$PSLTSCALE"] = 0
    return doc


class _DW:
    def __init__(self):
        self.doc = _new_doc()
        self.msp = self.doc.modelspace()


def make_sheets(res, meta=None):
    dw = _DW()
    info = _info(res, meta)
    sheets = [_sheet_staging(dw, res, info), _sheet_container(dw, res, info)]
    if res["members"].get("stair"):
        sheets.append(_sheet_stair(dw, res, info, len(sheets)))
    sheets += _sheets_bbs(dw, res, info, len(sheets))
    for e in dw.msp.query("TEXT"):           # the frames were drawn before the count was known
        t = e.dxf.text
        if t.startswith("Sheet ") and " of " in t:
            e.dxf.text = t.split(" of ")[0] + f" of {len(sheets)}"
    return dw, sheets


def export(res, out_dir, stem, meta=None, pdf=True, xlsx=True):
    """Write <stem>.dxf, <stem>.pdf, <stem>_calc.pdf (the design calculation) and <stem>_design.xlsx into out_dir;
    returns their paths."""
    os.makedirs(out_dir, exist_ok=True)
    dw, sheets = make_sheets(res, meta)
    paths = {}
    p = os.path.join(out_dir, stem + ".dxf")
    dw.doc.saveas(p)
    paths["dxf"] = p
    if pdf:
        paths["pdf"] = _pdf(dw, sheets, os.path.join(out_dir, stem + ".pdf"))
        from . import intze_calc                 # the design calculation as a report (user request 10-Nov-2026)
        paths["calc"] = intze_calc.export_pdf(res, os.path.join(out_dir, stem + "_calc.pdf"), meta)
    if xlsx:
        paths["xlsx"] = export_xlsx(res, os.path.join(out_dir, stem + "_design.xlsx"), meta)
    return paths


def _pdf(dw, sheets, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.config import BackgroundPolicy, ColorPolicy, Configuration, LineweightPolicy
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    cfg = Configuration(background_policy=BackgroundPolicy.WHITE, color_policy=ColorPolicy.COLOR,
                        lineweight_policy=LineweightPolicy.ABSOLUTE, lineweight_scaling=0.6)
    with PdfPages(path) as pdf:
        for sh in sheets:
            fig = plt.figure(figsize=(SW / 25.4, SH / 25.4))
            ax = fig.add_axes([0, 0, 1, 1])
            ax.set_axis_off()
            ctx = RenderContext(dw.doc)
            be = MatplotlibBackend(ax, adjust_figure=False)
            hs = sh.handles
            Frontend(ctx, be, config=cfg).draw_layout(dw.msp, finalize=False, filter_func=lambda e: e.dxf.handle in hs)
            ax.set_xlim(sh.ox, sh.ox + SW)
            ax.set_ylim(sh.oy, sh.oy + SH)
            ax.set_aspect("equal")
            pdf.savefig(fig)
            plt.close(fig)
    return path


def export_xlsx(res, path, meta=None):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = "Design"
    bold = Font(bold=True)
    yellow = PatternFill("solid", fgColor="FFFF99")
    info = _info(res, meta)
    ws.append([f"Design of the R.C.C. Intze tank {info['name']}: {res['capacity_kl']:g} KL on {res['staging_m']:g} m staging"])
    ws["A1"].font = Font(bold=True, size=13)
    ws.append([WARN])
    ws["A2"].font = Font(bold=True, color="C00000")
    ws.append([])
    ws.append(["Part", "Item", "Value", "Unit", "Reference / formula"])
    for c in ws[4]:
        c.font = bold
    last = None
    for sec, item, val, unit, ref in res["calc"]:
        ws.append([sec if sec != last else "", item, val, unit, ref])
        last = sec
        if sec == "1 Data" and item.startswith(("Concrete", "Seismic", "Net bearing", "Basic wind", "Steel stress")):
            ws.cell(ws.max_row, 3).fill = yellow
    if res["warnings"]:
        ws.append([])
        for wtxt in res["warnings"]:
            ws.append(["Check", wtxt])
    for col, w in zip("ABCDE", (16, 58, 34, 14, 90)):
        ws.column_dimensions[col].width = w
    for row in ws.iter_rows(min_row=5):
        row[4].alignment = Alignment(wrap_text=True, vertical="top")
        row[2].alignment = Alignment(wrap_text=True, vertical="top", horizontal="left")
    ws2 = wb.create_sheet("BBS")
    ws2.append(["S.No", "Member", "Mark", "Description", "Dia mm", "Nos", "Length m", "Total m", "kg/m", "Weight kg", "Shape"])
    for c in ws2[1]:
        c.font = bold
    for i, r in enumerate(res["bbs"], 1):
        n = i + 1
        ws2.append([i, r["member"], r["mark"], r["desc"], r["dia"], r["no"], r["length"], f"=F{n}*G{n}",
                    f"=E{n}^2/162", f"=H{n}*I{n}", r["shape"]])
    n = len(res["bbs"]) + 1
    ws2.append(["", "Total", "", "", "", "", "", f"=SUM(H2:H{n})", "", f"=SUM(J2:J{n})"])
    for c in ws2[ws2.max_row]:
        c.font = bold
    for col, w in zip("ABCDEFGHIJK", (6, 22, 8, 66, 8, 8, 10, 10, 8, 12, 22)):
        ws2.column_dimensions[col].width = w
    ws3 = wb.create_sheet("Quantities")
    conc, steel = intze.quantities(res)
    ws3.append(["Member", "Concrete m3", "Steel kg (BBS)"])
    for c in ws3[1]:
        c.font = bold
    for k in dict.fromkeys(list(conc) + list(steel)):
        ws3.append([k, round(conc.get(k, 0.0), 2), round(steel.get(k, 0.0), 1)])
    m = ws3.max_row
    ws3.append(["Total", f"=SUM(B2:B{m})", f"=SUM(C2:C{m})"])
    for c in ws3[ws3.max_row]:
        c.font = bold
    ws3.column_dimensions["A"].width = 24
    ws3.column_dimensions["B"].width = 14
    ws3.column_dimensions["C"].width = 16
    wb.save(path)
    return path
