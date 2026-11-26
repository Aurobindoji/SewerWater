"""Intze drawings: layers, the sheet and its views, text and scale helpers."""
import datetime
import math
from ezdxf.enums import TextEntityAlignment as TA


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


_FONT = []


def tw(s, h):
    """Width (paper mm) of the text s at the height h in the drawing's font (Liberation Sans, as the PDF writes it)."""
    if not _FONT:
        from ezdxf.fonts import fonts
        _FONT.append(fonts.make_font("LiberationSans-Regular.ttf", 1.0))
    return _FONT[0].text_width(str(s)) * h


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
        if tw(label, h) > abs(x2 - x1) - 0.5:          # a short span: its text before its left end, a row off the line
            self.text(label, (min(x1, x2) - 0.8, y + (-2.4 if below else 2.4)), h, TA.TOP_RIGHT if below else TA.BOTTOM_RIGHT, "DIM")
        else:
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

    def level(self, x, y, label, left=False, h=1.9, below=False):
        """A level mark; its text above the line, or under it (below) when the next level up is too near."""
        s = 1.6
        self.poly([(x, y), (x - s, y + s * 1.5), (x + s, y + s * 1.5)], "LEVEL", True)
        self.line((x - (9 if left else 0), y), (x + (0 if left else 9), y), "LEVEL")
        al = (TA.TOP_RIGHT if left else TA.TOP_LEFT) if below else (TA.BOTTOM_RIGHT if left else TA.BOTTOM_LEFT)
        self.text(label, (x + (-2.6 if left else 2.6), y + (-0.8 if below else 0.8)), h, al, "LEVEL")

    def leader(self, p, q, label, h=1.9, right=True, ring=0.35):
        """A note with a line to the point p, a circle of radius `ring` round it (round the bar when p is a bar)."""
        rows = label if isinstance(label, (list, tuple)) else [label]
        # the note inside the frame: a note placed by real metres runs off the sheet at a large scale (a small tank)
        wmax = max((tw(r_, h) for r_ in rows), default=0.0) + 3.5
        q = (max(q[0], 12.0 + wmax), q[1]) if not right else (min(q[0], SW - 12.0 - wmax), q[1])
        L = math.dist(p, q)
        e = (p[0] + (q[0] - p[0]) * ring / L, p[1] + (q[1] - p[1]) * ring / L) if L > ring else p
        self.line(e, q, "DIM")
        self.circle(p, ring, "DIM")
        self.line(q, (q[0] + (2.5 if right else -2.5), q[1]), "DIM")
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
