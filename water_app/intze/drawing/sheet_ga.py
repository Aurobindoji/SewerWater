"""Intze drawings, sheet 1: general arrangement, plans, raft, sections, staging."""
import math
from ezdxf.enums import TextEntityAlignment as TA
from .base import B, SCALES, Sheet, View, at, fit_scale, nb, ordinal, tw
from .shapes import _angles, _container_outline, _raft_outline, _raft_t, _shapes


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
    sh.text("G.L.", (v.p(-left, 0)[0] + 5.0, v.p(0, 0)[1] - 1.0), 1.8, TA.TOP_LEFT)      # under the ground, by the level dimensions
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
    y_up = None
    for name, z in (("TOP OF DOME", lev["dome1_crown"] + th["t1"]), ("TOP OF RING BEAM", lev["B1_top"]), ("F.S.L.", lev["FSL"]),
                    ("BALCONY", lev["B2_top"]), ("L.W.L.", lev["LWL"]), ("G.L.", 0.0), ("FOUNDING LEVEL", lev["raft_bot"])):
        y = v.p(0, z)[1]
        sh.level(xl, y, f"{name} {z:+.3f}", left=True, h=1.7, below=y_up is not None and y_up - y < 5.0)
        y_up = y
    for k, z in enumerate(g["braces"], 1):
        sh.text(f"{ordinal(k)} BRACE", (v.p(-xs_cols[-1] - dc / 2 - 0.4, z)[0], v.p(0, z)[1]), 1.6, TA.MIDDLE_RIGHT)
    xb_ = v.p(-r0 - th["b3"] / 2 - 0.4, 0)[0]
    yb_ = v.p(0, (lev["B3_bot"] + lev["LWL"]) / 2)[1]
    room = xb_ - (v.p(-left, 0)[0] + 5.0)                            # to the level dimensions on the left
    sh.lines(["BOTTOM RING BEAM"] if tw("BOTTOM RING BEAM", 1.6) <= room else ["BOTTOM", "RING BEAM"], xb_, yb_ + 1.2, 1.6, align=TA.MIDDLE_RIGHT)
    # dimensions
    yD = v.p(0, lev["FSL"] - 1.0)[1]
    sh.dim_h(v.p(-R, 0)[0], v.p(0, 0)[0], yD, f"R = {R * 1e3:.0f}")
    # (the radius of the column circle: on the half plan at brace level - here its text lay over the columns)
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


def stair_side(i):
    """The end of the staircase (+1 / -1 in y) of its i-th landing beam (0 = at the ground): the 1st flight runs from
    the -y end to the +y end, the next back."""
    return -1 if i % 2 == 0 else 1


def _stair_plan(sh, P, res, k, labels=True, ends=None):
    """The staircase in plan; P(x, y) gives the paper point of a real point (tank centre the origin, +x its side).
    ends: {+1 / -1: (label, x where the beam starts)} - the landing beams seen at each end (default B1 from the
    staging's column)."""
    st = res["members"]["stair"]
    xs, w, gap, lc, Lb = st["xs"], st["w"], st["gap"], st["lc"], st["Lb"]
    ds, bb = st["col"]["d"] / 1e3, st["beam"]["b"] / 1e3
    rl = w + gap / 2.0
    ends = ends or {1: ("B1", st["xc"]), -1: ("B1", st["xc"])}
    for sgn in (1, -1):
        y = sgn * Lb / 2.0
        xa = ends[sgn][1]
        sh.poly([P(xa, y - bb / 2), P(xs + lc, y - bb / 2), P(xs + lc, y + bb / 2), P(xa, y + bb / 2)], "OUTLINE", True)
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
        for sgn in (1, -1):
            lab, xa = ends[sgn]
            # the name beside the beam clear of the flights; a short beam: over the cantilever
            xm = (xa + xs - rl) / 2 if xs - rl - xa > 0.6 else xs + lc / 2 + 0.1
            sh.text(lab, P(xm, sgn * (Lb / 2 + 0.35)), 1.6, TA.MIDDLE_CENTER)


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
    sh.leader((px(rfo + rf["ao"] * 0.5), pz(c)), (px(rfo + rf["ao"] * 0.85), pz(t + 0.15)),
              f"{nb(rf['rad'])} RADIALLY @ {rf['rad_sp']} C/C", 1.8, right=False)      # away from the column
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
    for i, (L, n_) in enumerate(rf["zones_in"]):
        sh.dim_h(px(ra), px(ra - L), yd, f"{L * 1e3:.0f}", y_from=pz(-0.1))
        dy = 7.0 if i % 2 and L * k < tw("13 - 12 # HOOPS", 1.7) + 2 else 0.0    # a narrow zone: its notes a row lower than the last
        sh.text(f"{math.ceil(L / hs)} - {rf['hoop'][0]} # HOOPS", ((px(ra) + px(ra - L)) / 2, yd - 3.2 - dy), 1.7, TA.MIDDLE_CENTER)
        sh.text(f"{n_} - {rf['rad'][1]} #", ((px(ra) + px(ra - L)) / 2, yd - 6.4 - dy), 1.7, TA.MIDDLE_CENTER)
        sh.line((px(ra - L), pz(c) - 1.0), (px(ra - L), pz(c) + 1.0), "REBAR")
        ra -= L
    sh.dim_h(px(Ro), px(Ri), yd - 19, f"R = {Ro * 1e3:.0f} (OUTER), R = {Ri * 1e3:.0f} (INNER)")
    xv = px(Ri) + 7
    sh.dim_v(pz(0), pz(te), xv, f"{te * 1e3:.0f}", x_from=px(Ri))
    sh.dim_v(pz(0), pz(t), px(Ro) - 6, f"{t * 1e3:.0f}", h=1.7)
    sh.text("100 P.C.C.", (px(Ro + 0.1) - 1, pz(-0.1) - 2.5), 1.6, TA.MIDDLE_RIGHT)    # under the P.C.C., off the dimension
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
    # the notes of the top / bottom bars in the clear span between the columns, not across a column (checked: no text
    # over a line, 21-Nov-2026): the top one from the left column's face to the right, the bottom one from the right
    # column's face to the left; a note wider than the clear span in two rows, its bracket below (24-Nov-2026: a small
    # tank's "3 - 20 # HOOPS (OVERLAP ...)" ran over the other column's bars)
    room = (span - col_w) * k - 6.2 - 1.0

    def fit(note):
        rows = list(note) if isinstance(note, (list, tuple)) else [note]
        if max(tw(r_, 1.8) for r_ in rows) <= room:
            return note
        out = []
        for r_ in rows:
            out += r_.split(" (", 1) if " (" in r_ and tw(r_, 1.8) > room else [r_]
        return [out[0]] + ["(" + r_ if r_.endswith(")") and not r_.startswith("(") else r_ for r_ in out[1:]]
    two = fit(top) != top                      # the top note in two rows: its line straight down, clear of the second
    top, bot = fit(top), fit(bot)
    sh.leader((X(col_w / 2) + 3 if two else X(span * 0.5), Z(beam_d - c)), (X(col_w / 2) + 3, Z(beam_d + max(up, 0.5) * 0.75)), top, 1.8)
    sh.leader((X(span * 0.42), Z(c)), (X(span - col_w / 2) - 3, Z(-max(down, 0.6) * 0.55) if down else Z(0) - 4), bot, 1.8, right=False)
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
