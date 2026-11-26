"""Intze drawings, sheet 3: the staircase - its beams, the roof landing, the stair sheet."""
import math
from ezdxf.enums import TextEntityAlignment as TA
from .base import B, Sheet, View, at, fit_scale, nb, ordinal
from .shapes import _container_outline
from .sheet_ga import _beam_xsec, _stair_plan, hooked, stair_side


# -------------------------------------------------------------------------------------------- sheet 3: the staircase
def _brk(sh, p, q):
    """A break line (zigzag) from p to q, paper mm."""
    m1 = (p[0] + (q[0] - p[0]) * 0.4, p[1] + (q[1] - p[1]) * 0.4)
    m2 = (p[0] + (q[0] - p[0]) * 0.6, p[1] + (q[1] - p[1]) * 0.6)
    L = math.dist(p, q) or 1.0
    nx, ny = -(q[1] - p[1]) / L * 1.2, (q[0] - p[0]) / L * 1.2
    sh.poly([p, m1, (m1[0] + nx, m1[1] + ny), (m2[0] - nx, m2[1] - ny), m2, q], "THIN")


def _clip(pts, xmin, zmin, xmax=None, zmax=None):
    """The polygon pts cut to xmin <= X (<= xmax) and zmin <= Z (<= zmax) (Sutherland-Hodgman, the region is convex)."""
    atx = lambda x_: (lambda a, b: (x_, a[1] + (b[1] - a[1]) * (x_ - a[0]) / (b[0] - a[0])))
    atz = lambda z_: (lambda a, b: (a[0] + (b[0] - a[0]) * (z_ - a[1]) / (b[1] - a[1]), z_))
    planes = [(lambda q: q[0] >= xmin, atx(xmin)), (lambda q: q[1] >= zmin, atz(zmin))]
    if xmax is not None:
        planes.append((lambda q: q[0] <= xmax, atx(xmax)))
    if zmax is not None:
        planes.append((lambda q: q[1] <= zmax, atz(zmax)))
    for inside, cut in planes:
        out = []
        for i, b in enumerate(pts):
            a = pts[i - 1]
            if inside(b):
                if not inside(a):
                    out.append(cut(a, b))
                out.append(b)
            elif inside(a):
                out.append(cut(a, b))
        pts = out
    return pts


def _stirrups(v, x1, x2, z1, z2, skip=(), step=0.15):
    x = x1
    while x < x2 - 1e-6:
        if not any(a < x < b for a, b in skip):
            v.line((x, z1), (x, z2), "REBAR2")
        x += step


def _stair_beam(sh, res, kind, x0, y0, bw):
    """Elevation of the landing beam B3 (from the outer face of the cone / balcony to the staircase column and on)
    or B4 (a balanced cantilever on the staircase column alone, user 23-Nov-2026); fitted to the width bw from x0,
    y0 the paper level of its soffit."""
    st, g = res["members"]["stair"], res["geo"]
    bm = st["beams"][kind]
    lc, ds, d, c = st["lc"], st["col"]["d"] / 1e3, bm["d"] / 1e3, 0.04
    L = bm["L"] if kind == "B3" else lc
    ta = math.tan(g["alpha"])
    tt = g["th"]["t0"] / math.sin(g["alpha"])          # the cone's thickness, level across
    # B3 drawn at its longest span: on the cone, or at the balcony's level on the balcony's edge
    lmax = max((x_ for x_ in st["landings"] if x_["type"] == kind), key=lambda x_: x_["L"])
    on_bal = kind == "B3" and lmax["z"] - d / 2 >= res["levels"]["cone_top"] - 1e-6
    bt = g["th"]["bal_t"]
    ch = lambda r_: math.sqrt(max(r_ * r_ - (st["Lb"] / 2.0) ** 2, 0.0))      # a radius met on the beam's line
    xcone = ch(g["R"] + g["th"]["t0"] / math.sin(g["alpha"])) - ch(g["bal_edge"])   # the cone under the balcony, from its edge
    f = (lambda z: (z - d / 2) / ta) if kind == "B3" and not on_bal else (lambda z: 0.0)   # the left end at level z
    xcol = L + ds / 2
    xe = xcol + ds / 2 + lc
    left = (-0.8 / ta - tt) if kind == "B3" and not on_bal else (xcone - tt - 0.8 / ta if on_bal else 0.0)
    s = fit_scale(xe - left + 0.4, d + 1.6, bw, 70)
    v = View(sh, x0 + (0.2 - left) * 1000 / s, y0, s)
    if on_bal:                                         # the balcony's slab, the cone under it: one piece with the beam
        zs = d - bt                                    # the balcony's soffit
        xl = xcone - tt
        v.poly([(xl, d), (xe, d), (xe, 0), (0, 0)] + ([(0, zs)] if zs > 1e-6 else []) + [(xcone, zs), (xcone - 0.8 / ta, zs - 0.8)])
        v.line((xl, zs), (xl - 0.8 / ta, zs - 0.8))
        _brk(sh, v.p(xl, zs), v.p(xl, d))
        _brk(sh, v.p(xl - 0.8 / ta, zs - 0.8), v.p(xcone - 0.8 / ta, zs - 0.8))
        sh.leader(v.p(xl / 2, d - bt / 2), v.p(xl / 2 + 0.2, d + 0.5), "BALCONY", 1.7, right=False)
    else:
        v.poly([(f(0), 0), (xe, 0), (xe, d), (f(d), d)] + ([] if kind == "B3" else [(f(0), 0)]))
    for z1, z2, zb in ((-0.7, 0.0, -0.7), (d, d + 0.7, d + 0.7)):          # the staircase column below and above
        v.line((xcol - ds / 2, z1), (xcol - ds / 2, z2))
        v.line((xcol + ds / 2, z1), (xcol + ds / 2, z2))
        _brk(sh, v.p(xcol - ds / 2 - 0.05, zb), v.p(xcol + ds / 2 + 0.05, zb))
    if on_bal:                                         # the top bars on into the balcony, the bottom bars bent up at its edge
        top = [(xcone - tt + 0.06, d - c), (xe - c, d - c), (xe - c, d / 2 + 0.03)]
        bot = [(c, d - c - 0.06), (c, c), (xe - c - 0.04, c), (xe - c - 0.04, d / 2 - 0.03)]
    elif kind == "B3":                                 # a piece of the cone: its outer face above and below the beam
        zl, zh = -0.8, d + 0.8
        v.line((f(zl), zl), (f(0), 0))
        v.line((f(d), d), (f(zh), zh))
        v.line((f(zl) - tt, zl), (f(zh) - tt, zh))
        _brk(sh, v.p(f(zl) - tt, zl), v.p(f(zl), zl))
        _brk(sh, v.p(f(zh) - tt, zh), v.p(f(zh), zh))
        # top bars down the cone's middle, bottom bars up it: anchored in the cone
        top = [(f(d - c - 0.45) - tt * 0.6, d - c - 0.45), (f(d - c) - tt * 0.6, d - c), (xe - c, d - c), (xe - c, d / 2 + 0.03)]
        bot = [(f(c + 0.45) - tt * 0.35, c + 0.45), (f(c) - tt * 0.35, c), (xe - c - 0.04, c), (xe - c - 0.04, d / 2 - 0.03)]
        sh.leader(v.p(f(-0.45) - tt / 2, -0.45), v.p(f(-0.45) + 0.45, -0.55), "CONE", 1.7)
    else:
        top = [(c, d / 2 + 0.03), (c, d - c), (xe - c, d - c), (xe - c, d / 2 + 0.03)]
        bot = [(c + 0.04, d / 2 - 0.03), (c + 0.04, c), (xe - c - 0.04, c), (xe - c - 0.04, d / 2 - 0.03)]
    v.poly(top, "REBAR")
    v.poly(bot, "REBAR")
    _stirrups(v, max(f(0), f(d)) + 0.05, xe - 0.05, c, d - c, skip=((xcol - ds / 2, xcol + ds / 2),))
    qx, qz = v.p(xcol - ds / 2, d + 0.45)              # the note ends short of the column
    sh.leader(v.p(xcol - ds / 2 - max(L * 0.35, 0.3), d - c), (qx - 2.0, qz), nb(bm["top"]), 1.8, right=False)
    sh.leader(v.p(xe - lc * 0.5, c), v.p(xe - lc * 0.4, -0.5), nb(bm["bot"]), 1.8)
    sh.text("8 # STR. @ 150 C/C", v.p(xe - lc / 2, d + 0.2), 1.7, TA.BOTTOM_CENTER)
    yd = v.p(0, -0.7)[1] - 3
    xf = f(d / 2)
    sh.dim_h(v.p(xf, 0)[0], v.p(xcol - ds / 2, 0)[0], yd, f"{L * 1e3:.0f}", below=True)
    sh.dim_h(v.p(xcol - ds / 2, 0)[0], v.p(xcol + ds / 2, 0)[0], yd, f"{ds * 1e3:.0f}", below=True)
    sh.dim_h(v.p(xcol + ds / 2, 0)[0], v.p(xe, 0)[0], yd, f"{lc * 1e3:.0f}", below=True)
    sh.dim_v(v.p(0, 0)[1], v.p(0, d)[1], v.p(xe, 0)[0] + 5, f"{bm['d']}", x_from=v.p(xe, 0)[0])
    lv = ", ".join(f"{z * 1e3:.0f}" for z in bm["levels"])
    sub = f"RL {lv};  SCALE 1:{s}"
    if kind == "B3" and len(bm["levels"]) > 1:
        sp = [xs_ for xs_ in st["landings"] if xs_["type"] == "B3"]
        sub = "SPAN " + ", ".join(f"{x_['L'] * 1e3:.0f} AT RL {x_['z'] * 1e3:.0f}" for x_ in sp) + f";  SCALE 1:{s}"
    sh.heading({"B3": "LANDING BEAM B3 (ON THE CONE / BALCONY)", "B4": "LANDING BEAM B4 (ON THE STAIRCASE COLUMN)"}[kind],
               (x0 + bw / 2, yd - 9), 2.6, sub)


def _roof_landing(sh, res, x0, y0, bw):
    """Section 14-14 along B5 at the roof (user 23-Nov-2026): the landing at the top ring beam's level carried on flat
    to it on B5, from the top ring beam to the staircase column and on; x0, y0 the paper point of the left end of the
    view at its lowest level."""
    st, g, lev = res["members"]["stair"], res["geo"], res["levels"]
    bm, br = st["beams"]["B5"], st["bridge"]
    # the section runs along B5, Lb / 2 off the tank's axis: the tank's round faces met there (ch)
    ch = lambda r_: math.sqrt(max(r_ * r_ - (st["Lb"] / 2.0) ** 2, 0.0))
    R, roof, xb1, xs = ch(g["R"]), st["roof"], st["xb1_line"], st["xs"]
    lc, ds, d, c = st["lc"], st["col"]["d"] / 1e3, bm["d"] / 1e3, 0.04
    xe = xs + ds / 2 + lc
    Xa, Zb = R - 0.6, roof - 1.0
    s = fit_scale(xe - Xa + 0.6, 2.4, bw, 80)
    v = View(sh, x0, y0, s, Xa, Zb)
    # the tank: the top ring beam, the wall's top and the top dome's edge, cut out of the one outline
    cut = _clip([(ch(x_), z_) for x_, z_ in _container_outline(res)], Xa, Zb + 0.1)
    v.poly(cut, "OUTLINE", True)
    # B5 and the staircase column under it
    v.poly([(xb1, roof - d), (xe, roof - d), (xe, roof), (xb1, roof)])
    v.line((xb1, roof - d), (xb1, lev["wall_top"]))
    for xx in (xs - ds / 2, xs + ds / 2):
        v.line((xx, Zb + 0.1), (xx, roof - d))
    _brk(sh, v.p(xs - ds / 2 - 0.05, Zb + 0.1), v.p(xs + ds / 2 + 0.05, Zb + 0.1))
    # bars: the top bars carried 300 into the top ring beam, the bottom bars from the ring beam's face
    v.poly([(max(xb1 - 0.3, R + 0.04), roof - c), (xe - c, roof - c), (xe - c, roof - d / 2 + 0.03)], "REBAR")
    v.poly([(xb1 + c, roof - d / 2 - 0.03), (xb1 + c, roof - d + c), (xe - c - 0.04, roof - d + c), (xe - c - 0.04, roof - d / 2 - 0.03)], "REBAR")
    _stirrups(v, xb1 + 0.06, xe - 0.05, roof - d + c, roof - c, skip=((xs - ds / 2, xs + ds / 2),))
    # the railing at the landing's outer edge, seen beyond
    for xx in (xb1 + 0.1, xs, xe - 0.08):
        v.line((xx, roof), (xx, roof + 1.0), "THIN")
    for zz in (0.35, 0.68, 1.0):                       # the three pipes
        v.line((xb1 + 0.1, roof + zz), (xe - 0.08, roof + zz), "THIN")
    L = xs - ds / 2 - xb1
    sh.leader(v.p(xb1 + L * 0.55, roof - c), v.p(xb1 + L * 0.45, roof + 0.56), [nb(bm["top"]) + " (300 INTO THE", "TOP RING BEAM)"], 1.7)   # between the rails
    sh.leader(v.p(xb1 + L * 0.5, roof - d + c), v.p(xb1 + L * 0.65, roof - d - 0.45), nb(bm["bot"]), 1.7)
    sh.text("8 # STR. @ 150 C/C", v.p(xe - lc / 2, roof + 0.2), 1.7, TA.BOTTOM_CENTER)
    sh.leader(v.p(R + 0.05, lev["wall_top"] - 0.4), v.p(R - 0.45, Zb + 0.35), "TANK WALL", 1.7, right=False)
    sh.leader(v.p(xb1 - 0.12, roof - 0.1), v.p(xb1 - 0.5, roof + 0.75), "TOP RING BEAM", 1.7, right=False)
    sh.leader(v.p(xe - 0.08, roof + 0.8), v.p(xe + 0.25, roof + 1.15), ["3 - 20 DIA G.I. PIPE RAILING", "ON ISA 50x50x6 POSTS"], 1.7)
    sh.leader(v.p(xs + ds / 2, Zb + 0.45), v.p(xs + ds / 2 + 0.4, Zb + 0.3), "STAIRCASE COLUMN", 1.7)
    sh.level(v.p(xe, roof)[0] + 2, v.p(xe, roof)[1], f"RL {roof * 1e3:.0f}")
    yd = v.p(0, Zb)[1] - 3
    sh.dim_h(v.p(xb1, 0)[0], v.p(xs - ds / 2, 0)[0], yd, f"{L * 1e3:.0f}", below=True)
    sh.dim_h(v.p(xs - ds / 2, 0)[0], v.p(xs + ds / 2, 0)[0], yd, f"{ds * 1e3:.0f}", below=True)
    sh.dim_h(v.p(xs + ds / 2, 0)[0], v.p(xe, 0)[0], yd, f"{lc * 1e3:.0f}", below=True)
    sh.heading("SECTION 14 - 14 (BEAM B5 AT THE ROOF)", (x0 + bw / 2, yd - 9), 2.6,
               f"THE LANDING CARRIED ON FLAT TO THE TOP RING BEAM: SLAB {br['t']} THICK, {at(br['main'])} AT TOP;  SCALE 1:{s}")


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

    def plan(x0, y0, title, level, extra=None, ends=None, cols="OUTLINE"):
        P = lambda x, y: (x0 + (x - st["xc"] + 1.2) * k, y0 + 12 + (y + ext_y / 2) * k)
        for a in (math.pi / n, -math.pi / n):
            sh.circle(P(r0 * math.cos(a), r0 * math.sin(a)), dc / 2 * k, cols)
        for sg in (1, -1):                                         # the braces to the next columns
            a, b_ = sg * math.pi / n, sg * 3 * math.pi / n
            pa, pb = (r0 * math.cos(a), r0 * math.sin(a)), (r0 * math.cos(b_), r0 * math.sin(b_))
            t_ = 0.45
            sh.line(P(*pa), P(pa[0] + (pb[0] - pa[0]) * t_, pa[1] + (pb[1] - pa[1]) * t_), "HIDDEN")
        sh.line(P(st["xc"], -Lb / 2), P(st["xc"], Lb / 2), "HIDDEN")
        _stair_plan(sh, P, res, k, ends=ends)
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
    # the landing beams seen in a plan: the landing at its level at one end, the one below at the other (user
    # 23-Nov-2026: each on what it rests on - B1 the staging's column, B3 the cone / balcony, B4 the staircase column
    # alone, B5 the top ring beam)
    lands = st["landings"]

    xbal = math.sqrt(max(g["bal_edge"] ** 2 - (Lb / 2) ** 2, 0.0))   # the balcony's edge on the beams' line

    def seen(i, x_cut):
        kind = lands[i]["type"]
        return kind, {"B1": x_cut, "B3": max(x_cut, xs - lands[i]["L"] - st["col"]["d"] / 2e3),
                      "B4": xs - lc, "B5": st["xb1_line"]}[kind]
    ib = st["n1"]                                     # the balcony's landing; the roof's is the last
    plan(18, 215, "BALCONY LEVEL PLAN", f"RL {st['bal'] * 1e3:.0f}", balc,
         {stair_side(ib): seen(ib, xbal), -stair_side(ib): seen(ib - 1, xbal)}, "HIDDEN")
    it = len(lands) - 1
    sr = stair_side(it)
    bb_ = st["beam"]["b"] / 1e3

    def roof(P):
        balc(P)
        hy = min(Lb / 2 + rl, st["xb1"] * 0.9)
        a = math.asin(hy / st["xb1"])
        sh.poly([P(st["xb1"] * math.cos(-a + 2 * a * i / 20), st["xb1"] * math.sin(-a + 2 * a * i / 20)) for i in range(21)])
        # the landing carried on flat to the top ring beam
        y1, y2 = sr * (Lb / 2 - bb_ / 2), sr * (Lb / 2 + rl)
        arc = lambda y_: math.sqrt(max(st["xb1"] ** 2 - y_ * y_, 0.0))      # its end on the ring beam's round face
        sh.poly([P(arc(y1), y1), P(xs - rl, y1), P(xs - rl, y2), P(arc(y2), y2)])
        sh.text("TOP RING BEAM", P(st["xb1"] - 0.25, -sr * Lb / 4), 1.6, TA.MIDDLE_CENTER, rot=90)
        # the section 14-14 along B5
        # its name beside the mark, on the side of the tank's axis: the ring beam's round face bends away there
        for xm in (st["xb1_line"] - 0.35, xs + rl + 0.5):
            p_ = P(xm, sr * Lb / 2)
            sh.line((p_[0] - 2.2, p_[1]), (p_[0] + 2.2, p_[1]), "FRAME")
            sh.text("14", (p_[0], p_[1] - sr * 1.5), 2.4, TA.TOP_CENTER if sr > 0 else TA.BOTTOM_CENTER, style=B)
    plan(18, 30, "ROOF LEVEL PLAN", f"RL {st['roof'] * 1e3:.0f} (TOP RING BEAM)", roof,
         {sr: seen(it, xbal), -sr: seen(it - 1, xbal)}, "HIDDEN")
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
    # at the landings' ends the bottom bar is bent up and the top bar down, a third of the depth each and 30 mm apart:
    # they do not meet (user 21-Nov-2026: "top-bottom steel meet at end points")
    lg = 0.35 * (wt - 2 * c)
    mb = soff(wt - c)[::-1]
    mb = [(c, mb[0][1] + lg), (c, mb[0][1]), mb[1], mb[2], (xe - c, mb[3][1]), (xe - c, mb[3][1] + lg)]
    hooked(v, mb, ends=(False, False))
    f1, f2 = mb[2], mb[3]                             # the flight's soffit bar: its start and end
    v.dots([(f1[0] + 0.05, f1[1] + 0.025 + 0.05 * kk), (f2[0] - 0.05, f2[1] + 0.025 - 0.05 * kk)], st["dist"][1] / 1e3, 0.35)
    # top bars of the landings: over the supports, then into the flight along the steps' inner corners
    xl = rl + c * (sec - 1.0) / kk                    # where z = -c meets the corner line less the cover
    tb1 = [(c + 0.03, -c - lg), (c + 0.03, -c), (xl, -c), (xl + 0.3 * go, -c * sec + (xl + 0.3 * go - rl) * kk)]
    hooked(v, tb1, ends=(False, True), inside=((rl / 2, -wt / 2), (rl + 0.3 * go, 0.3 * go * kk - wt / 2)))
    # the upper landing's top bar: along the landing to where it meets the line of the steps' inner corners (less the
    # cover), then down that line - straight from the landing's top it ran over the last treads, out of the concrete
    xu = rl + go - 0.3 * go
    xm = min(rl + (rise - c + c * sec) / kk, xe - c - 0.1)
    tb2 = [(xe - c - 0.03, rise - c - lg), (xe - c - 0.03, rise - c), (xm, rise - c), (xu, (xu - rl) * kk - c * sec)]
    hooked(v, tb2, ends=(False, True), inside=((xe - rl / 2, rise - wt / 2), (xu, (xu - rl) * kk - wt / 2)))
    v.dots([(c + 0.05, -c - 0.025), (xl - 0.02, -c - 0.025)], st["dist"][1] / 1e3, 0.3, first=st["dist"][1] / 1e3)
    v.dots([(xm + 0.02, rise - c - 0.025), (xe - c - 0.05, rise - c - 0.025)], st["dist"][1] / 1e3, 0.3, first=st["dist"][1] / 1e3)
    v.dots([(c + 0.05, -wt + c + 0.025), (f1[0] - 0.05, -wt + c + 0.025)], st["dist"][1] / 1e3, 0.3)
    v.dots([(f2[0] + 0.05, rise - wt + c + 0.025), (xe - c - 0.05, rise - wt + c + 0.025)], st["dist"][1] / 1e3, 0.3)
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
    # top bars bent down into the column of the staging, bottom bars bent up into it (an L each, 60 mm apart, user
    # 21-Nov-2026: they met end to end as one closed loop); at the free end the legs stop short of each other
    sh.poly([(X(0.08), Z(-0.3)), (X(0.08), Z(bd_ - 0.04)), (X(xe - 0.04), Z(bd_ - 0.04)), (X(xe - 0.04), Z(bd_ / 2 + 0.03))], "REBAR")
    sh.poly([(X(0.14), Z(bd_ + 0.3)), (X(0.14), Z(0.04)), (X(xe - 0.08), Z(0.04)), (X(xe - 0.08), Z(bd_ / 2 - 0.03))], "REBAR")
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
    b1lv = st["beams"]["B1"]["levels"]
    sh.heading("LANDING BEAM B1 (ON A COLUMN OF THE STAGING)", (236 + 125, min(300 + 3, Z(-0.7) - 10)), 2.6,
               f"RL {b1lv[0] * 1e3:.0f} TO {b1lv[-1] * 1e3:.0f};  SCALE 1:{s3}")   # under its dimensions
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
    # the landing beams on what each rests on, the roof's landing and the beams' sections (user 23-Nov-2026)
    _roof_landing(sh, res, 505, 345, 175)
    bms = st["beams"]
    if "B3" in bms:
        _stair_beam(sh, res, "B3", 500, 250, 190)
    if "B4" in bms:
        _stair_beam(sh, res, "B4", 705, 250, 115)
    for i, (kind, b_) in enumerate(bms.items()):
        _beam_xsec(sh, 515 + i * 62, 175, 15, b_["b"], b_["d"], b_["top"], b_["bot"], opt["cover_stair_mm"],
                   f"SECTION OF {kind}", note="8 # STR. @ 150")
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
              f"{(xs - st['xc']) * 1e3:.0f} FROM THE COLUMNS OF THE STAGING. A LANDING BEAM AT EVERY LANDING:",
              "B1 ON A COLUMN OF THE STAGING, B3 ON THE CONE / BALCONY, B4 ON THE STAIRCASE COLUMN ALONE",
              "(NOT INTO THE TANK WALL), B5 AT THE ROOF ON THE TOP RING BEAM.",
              "LANDINGS: SLAB OF THE WAIST'S THICKNESS, 8 # @ 150 C/C BOTH WAYS.",
              "", "NOTES:  1. ALL DIMENSIONS ARE IN MILLIMETRE.   2. READ WITH SHEETS 1 AND 2."], tx, ty, 1.9, 3.6)
    sh.frame(info)
    return sh
