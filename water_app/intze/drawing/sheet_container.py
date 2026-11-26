"""Intze drawings, sheet 2: the container - tank section, dome plan, ring and joint details."""
import math
from ezdxf.enums import TextEntityAlignment as TA
from .base import SW, Sheet, View, arc_pts, at, fit_scale, nb, tw
from .shapes import _container_outline, _shapes
from .sheet_ga import _beam_xsec, _lsec, _sector, bar_row, hooked
from .sheet_stair import _brk, _clip


# ------------------------------------------------------------------------------------------- sheet 2: the container
def _ring_bars(res, z_from):
    """The bars at the top ring beam, as the example's detail (user 22-Nov-2026), real m: the dome's middle bar on
    along its own line into the beam, hooked there; the dome's extra top bars at the edge into the beam and down its
    outer side; the wall's outer vertical up and bent into the dome's top layer (a lap); the wall's inner vertical
    up and bent out over the beam's bottom. z_from: where the wall's bars start. -> [(points, ends, inside)]."""
    g, lev, th, opt = res["geo"], res["levels"], res["geo"]["th"], res["opt"]
    R, cw = g["R"], opt["cover_water_mm"] / 1e3
    S = _shapes(res)
    zc1, R1, a1 = S["dome1"]
    zw, zt = lev["wall_top"], lev["B1_top"]
    xb1 = R + max(th["b1"], th["tw"])
    tw, edge = th["tw"], res["members"]["top_dome"]["edge"]
    mid_b = ((R + xb1) / 2, (zw + zt) / 2)
    circ = lambda r_, x: (x, zc1 + math.sqrt(max(r_ * r_ - x * x, 0.0)))
    out = []
    # the dome's mesh bar (its middle, a little under it): on along its line past the wall's face to the beam's bottom
    rm = R1 + th["t1"] / 2 - 0.012
    pts = [circ(rm, R - 1.2 + 1.2 * i / 12) for i in range(13)]
    (xa, za), (xb, zb) = pts[-2], pts[-1]
    L = math.dist((xa, za), (xb, zb))
    ux, uz = (xb - xa) / L, (zb - za) / L
    t_end = min(((zw + cw + 0.05) - zb) / uz if uz < 0 else 9.0, ((xb1 - cw - 0.05) - xb) / ux if ux > 0 else 9.0)
    out.append((pts + [(xb + ux * t_end, zb + uz * t_end)], (False, True), mid_b))
    # the wall's outer vertical IS the dome's extra top bar at the edge (as the example): up the wall's outer face,
    # through the beam under its top bars, and on in the dome's top layer for the edge's length
    rt = R1 + th["t1"] - cw
    zr = zt - cw - 0.04                                       # under the beam's top bars
    xo = R + tw - cw
    xc = min(math.sqrt(max(rt * rt - (zr - zc1) ** 2, 0.0)), xo - 0.04)
    top = [circ(rt, xc - (xc - (R - edge)) * i / 20) for i in range(21)]
    out.append(([(xo, z_from), (xo, zr)] + top, (False, False), mid_b))
    # the wall's inner vertical: up over the beam's bottom bars, bent out along the beam
    zi = zw + cw + 0.035                                      # over the beam's bottom bars
    out.append(([(R + cw, z_from), (R + cw, zi), (R + 0.55 * tw, zi)], (False, True), mid_b))   # short: not over the outer bar
    return out


def _tank_section(sh, res, x0, y0, bw, bh):
    g, lev, th, M, opt = res["geo"], res["levels"], res["geo"]["th"], res["members"], res["opt"]
    R, r0 = g["R"], g["r0"]
    S = _shapes(res)
    cw = opt["cover_water_mm"] / 1e3
    width = g["bal_edge"] + 0.3
    zb = lev["B3_bot"] - 1.0
    height = lev["dome1_crown"] - zb + 0.8
    s = fit_scale(width, height, bw - 46, bh - 16)
    v = View(sh, x0 + 6, y0 + bh - 4 - height * 1000.0 / s, s, 0.0, zb)   # its top at the box's top
    v.shape(_container_outline(res))
    # (no joint lines on the concrete: wall, beams, balcony and cone are cast as one - user 22-Nov-2026)
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
    b1c = ((b1a + b1b) / 2, (b1z0 + b1z1) / 2)
    # the top ring beam's joint as the example's (user 22-Nov-2026, _ring_bars): the dome's bar on into the beam and
    # hooked; the wall's outer vertical through the beam into the dome's top layer; the inner one bent short; the
    # beam's corner bars only (all its bars: the detail of the top ring beam)
    zfoot = lev["cone_top"] + cw + 0.03
    rbars = _ring_bars(res, zfoot)
    mbar = [q_ for q_ in mid1 if q_[0] < R - 1.2] + rbars[0][0]          # the dome's middle bar, crown to its hook
    hooked(v, mbar, ends=(False, True), inside=b1c)
    v.dots([q_ for q_ in mbar if q_[0] <= R - 0.05], td["hoop"][1] / 1e3, 0.3)
    # wall: verticals from the balcony ring (L at the foot) into the top ring beam (L at the top)
    w = M["wall"]
    zt = S["wall"][2][1]
    wc = lambda z_: (R + th["tw"] / 2, z_)            # a point in the wall at the level z_
    ob = rbars[1][0]                                  # the outer vertical: its taper at the base, then as the detail
    hooked(v, [(R + th["twb"] - cw, zfoot), (R + th["twb"] - cw, lev["B2_top"]), (R + th["tw"] - cw, zt)] + ob[1:], ends=(False, False))
    hooked(v, rbars[2][0], ends=rbars[2][1], inside=b1c)
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
    # the hoop bars in a row at the top and one at the bottom, as the beam's own cross-section (TOP RING BEAM) shows
    # them - five a face up its 200 depth ran together (user 21-Nov-2026)
    rr_ = 0.35 / v.k + 0.004                         # the corner bars, inside the stirrup's corners
    for xx in (b1a + cw + 2 * rr_, b1b - cw - 2 * rr_):
        for zz in (b1z1 - cw - rr_, b1z0 + cw + rr_):
            sh.dot(v.p(xx, zz), 0.35)
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
    sh.dim_v(v.p(0, b1z0_)[1], v.p(0, b1z1_)[1], v.p(b1b_, 0)[0] + 3, f"{th['d1'] * 1e3:.0f}", x_from=v.p(b1b_, 0)[0], h=1.6)   # beside the beam
    (b3a_, b3z0_), _, (b3b_, b3z1_), _ = S["B3"]
    sh.dim_h(v.p(b3a_, 0)[0], v.p(b3b_, 0)[0], v.p(0, b3z0_)[1] - 3, f"{th['b3'] * 1e3:.0f}", below=True)   # under the beam, between the column's faces
    sh.dim_v(v.p(0, b3z0_)[1], v.p(0, b3z1_)[1], v.p(b3a_ - 0.15, 0)[0], f"{th['d3'] * 1e3:.0f}", x_from=v.p(b3a_, 0)[0], h=1.7)
    # ---- labels (inside the tank, as on the example) and dimensions
    pm = mid1[30]
    q_ = v.p(*pm)
    sh.leader_bar(q_, (q_[0] + 6, q_[1] + 16), [at(td["rad"], "RADIALLY"), at(td["hoop"], "HOOPS"), f"TOP DOME {td['t']} THICK ({td['te']} AT THE EDGE)"], 1.9)
    pe = mid1[57]
    sh.leader_bar(v.p(*pe), (v.p(R + th["b1"] + 0.5, 0)[0], v.p(0, lev["B1_top"] + 0.6)[1] + 10), [f"{math.ceil(td['edge'] * 1e3 / td['edge_hoop'][1])} - {td['edge_hoop'][0]} # HOOPS",
              f"{math.ceil(2 * math.pi * R * 1e3 / td['edge_rad'][1])} - {at(td['edge_rad'], 'RADIALLY')}", f"AT TOP, IN {td['edge'] * 1e3:.0f} FROM THE EDGE"], 1.8)
    sh.leader_bar(v.p(R + th["b1"] / 2, lev["B1_top"] - 0.05), v.p(R + th["b1"] + 0.5, lev["B1_top"] + 0.6),
              [f"TOP RING BEAM {tr_['b']} x {tr_['d']}", f"{nb((tr_['n'], tr_['dia']))} HOOPS, 8 # STR @ 200 C/C", "(SEE ITS DETAIL)"], 1.9)
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
    qw = v.p(R - 1.2, zm + 0.5)
    yR = v.p(0, lev["FSL"] - 0.8)[1]                # the "R = ..." dimension's line: the note's rows clear of it
    if qw[1] - 2 * 1.8 * 1.5 - 1.5 < yR < qw[1] + 1.5:
        qw = (qw[0], yR - 2.0)
    sh.leader(v.p(R + cw, zm), qw, [f"WALL {w['t']} THICK, {w['tb']} AT THE BASE", nv(w["vert"], 2 * R), "VERTICAL, EACH FACE"], 1.8, right=False)
    sh.leader(v.p(R + cw, lev["B2_top"] + 0.35), v.p(R - 1.2, lev["B2_top"] + 0.95), [nv(w["base_in"], 2 * R), f"VERTICAL AT THE BASE, WATER FACE, {w['base_len'] * 1e3:.0f} LONG"], 1.8, right=False)
    sh.leader_bar(v.p(g["bal_edge"] - 0.3, lev["cone_top"] + cw), v.p(R - 0.1, lev["cone_top"] - 0.9),
              [f"BALCONY {bl['w'] * 1e3:.0f} WIDE, {bl['t']} THICK", f"{nb((bl['n'], bl['dia']))} HOOPS", at(bl["rad"], "RADIALLY") + " AT TOP", at(bl["dist"], "RADIALLY") + " AT BOTTOM"], 1.8)
    pc = ((r0 + R) / 2 + nx * cw, (lev["LWL"] + lev["cone_top"]) / 2 + nz * cw)
    # its note inside the tank, over the bottom dome: raised where the dome would run through it (a small tank)
    zq, wq = pc[1] + 1.3, tw("4 - 12 # HOOPS @ 150 (UPPER HALF) ON EACH FACE", 1.8) / v.k   # the note's width (m)
    xl_ = max(0.0, pc[0] - 3.0 - wq)
    zd = zc2 + math.sqrt(max(R2 * R2 - xl_ * xl_, 0.0))              # the dome's top at the note's left end
    zq = max(zq, zd + th["t2"] + 4 * 1.8 * 1.5 / v.k + 0.1)
    sh.leader_bar(v.p(*pc), v.p(pc[0] - 3.0, zq), [f"CONICAL DOME {cn['t']} THICK", f"{cn['n_low']} - {cn['hoop_low'][0]} # HOOPS @ {cn['hoop_low'][1]} (LOWER HALF) AND",
              f"{cn['n_up']} - {cn['hoop_up'][0]} # HOOPS @ {cn['hoop_up'][1]} (UPPER HALF) ON EACH FACE",
              f"{math.ceil(math.pi * (R + r0) * 1e3 / cn['mer'][1])} - {at(cn['mer'], 'RADIALLY')} ON EACH FACE"], 1.8, right=False)
    pb = ((R2 - cw) * math.sin(a2 * 0.45), zc2 + (R2 - cw) * math.cos(a2 * 0.45))
    sh.leader_bar(v.p(*pb), v.p(pb[0] - 0.3, pb[1] - 1.25), [f"BOTTOM DOME {bd['t']} THICK ({bd['te']} AT THE EDGE)", at(bd["rad"], "RADIALLY") + " AND", at(bd["hoop"], "HOOPS") + " ON EACH FACE"], 1.9, right=False)
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
    xr = v.p(g["bal_edge"], 0)[0] + 58
    for z1, z2 in ((lev["B3_bot"], lev["LWL"]), (lev["LWL"], lev["cone_top"]), (lev["cone_top"], lev["B2_top"]), (lev["B2_top"], lev["wall_top"]),
                   (lev["wall_top"], lev["B1_top"]), (lev["B1_top"], lev["dome1_crown"])):
        sh.dim_v(v.p(0, z1)[1], v.p(0, z2)[1], xr, f"{(z2 - z1) * 1e3:.0f}", h=1.7)
    sh.heading("SECTION OF TANK", (x0 + bw / 2 - 20, max(y0 + 4, yb - 14)), 3.0, f"SCALE 1:{s}")   # just under the view


def _dome_plan(sh, res, key, x0, y0, bw, bh, title):
    g, m = res["geo"], res["members"][key]
    a = g["R"] if key == "top_dome" else g["r0"]
    rc = round(min(1.5, max(0.8, a / 8)), 1)              # the crown, drawn whole (as the example's)
    s = fit_scale(a + 0.3 + rc, 1.0, bw - 16, 1e9)
    k = 1000.0 / s
    n = math.ceil(2 * math.pi * a * 1e3 / m["rad"][1])
    ne = math.ceil(2 * math.pi * a * 1e3 / m["edge_rad"][1])
    narrow = tw(f"{at(m['hoop'], 'HOOPS')};  {n} - {at(m['rad'], 'RADIALLY')} AT THE EDGE, ALTERNATE BARS STOP HALF WAY", 1.7) > bw - 4
    xt, yt = x0 + bw - 8 - rc * k, y0 + bh / 2 + (10 if narrow else 4)
    P, hphi = _sector(sh, xt, yt, s, 0.0, a, min(bh - 34, 46),
                      [(a / 2, a, n), (rc, a / 2, max(4, n // 2)), (a - m["edge"], a, ne)],
                      [(rc, a - m["edge"], m["hoop"][1] / 1e3), (a - m["edge"], a, m["edge_hoop"][1] / 1e3)])
    # the crown in plan: its circle, the radial bars across it (every one of those that reach it is drawn as far as
    # the ring next to the centre) and the hoops at the dome's spacing
    sh.circle((xt, yt), rc * k, "OUTLINE")
    nr = max(4, n // 2)
    step = max(1, nr // 36)                                # at most 36 lines: the drawing stays readable
    for j in range(0, nr, step):
        t = 2 * math.pi * j / nr
        r1 = 0.15 * k
        sh.line((xt + r1 * math.cos(t), yt + r1 * math.sin(t)), (xt + rc * k * math.cos(t), yt + rc * k * math.sin(t)), "REBAR2")
    r_ = m["hoop"][1] / 1e3
    while r_ < rc:
        sh.circle((xt, yt), r_ * k, "REBAR2")
        r_ += m["hoop"][1] / 1e3
    sh.dim_h(xt, xt + rc * k, yt - rc * k - 3, f"{rc * 1e3:.0f}", y_from=yt, below=True)
    pm = P(a, -hphi)                                       # the notes under the sector's lowest corner
    pm = (pm[0], pm[1] + 3.5)
    rows = [f"{at(m['hoop'], 'HOOPS')};  {n} - {at(m['rad'], 'RADIALLY')} AT THE EDGE, ALTERNATE BARS STOP HALF WAY",
            f"EDGE {m['edge'] * 1e3:.0f}: {math.ceil(m['edge'] * 1e3 / m['edge_hoop'][1])} - {m['edge_hoop'][0]} # HOOPS, {ne} - {at(m['edge_rad'], 'RADIALLY')} AT TOP"]
    if tw(rows[0], 1.7) > bw - 4:                            # a narrow plan: shorter lines
        rows = [f"{at(m['hoop'], 'HOOPS')};  {n} - {at(m['rad'], 'RADIALLY')}", "AT THE EDGE, ALTERNATE BARS STOP HALF WAY",
                f"EDGE {m['edge'] * 1e3:.0f}: {math.ceil(m['edge'] * 1e3 / m['edge_hoop'][1])} - {m['edge_hoop'][0]} # HOOPS,", f"{ne} - {at(m['edge_rad'], 'RADIALLY')} AT TOP"]
    sh.lines(rows, P(a, -hphi)[0], pm[1] - 7.5, 1.7, step=3.3)
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
    sh.leader((x2 + 72, y2 + 14), (x2 + 77, y2 + 21), "ISA 50x50x6", 1.6)   # right: the section's dims on the left
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


def _ring_detail(sh, res, x0, y0, bw, bh):
    """DETAIL OF TOP RING BEAM (user 22-Nov-2026, as the example's): the beam with a piece of the top dome and of the
    wall, large enough to see every bar - the dome's two layers anchored down the beam's outer side, the wall's
    verticals bent into the beam, the beam's hoop bars in a row at the top and one at the bottom inside its stirrup."""
    g, lev, th, M, opt = res["geo"], res["levels"], res["geo"]["th"], res["members"], res["opt"]
    R, cw = g["R"], opt["cover_water_mm"] / 1e3
    S = _shapes(res)
    zc1, R1, a1 = S["dome1"]
    tr_ = M["top_ring"]
    b1, d1, tw = th["b1"], th["d1"], th["tw"]
    xb1 = R + max(b1, tw)
    zw, zt = lev["wall_top"], lev["B1_top"]
    Ls, Lw = 0.42, 0.30                                          # the pieces of the dome and the wall shown
    Ru = R1 + th["t1"]
    xl = R - Ls
    s = fit_scale(Ls + max(b1, tw) + 0.2, (zc1 + math.sqrt(Ru * Ru - xl * xl)) - (zw - Lw) + 0.15, bw - 70, bh - 18)
    v = View(sh, x0 + 4, y0 + 16, s, xl, zw - Lw)
    # ---- concrete: one outline, the cut ends as break lines
    xe = min(math.sqrt(max(Ru * Ru - (zt - zc1) ** 2, 0.0)), xb1)
    up = [(xl + (xe - xl) * i / 20, zc1 + math.sqrt(max(Ru * Ru - (xl + (xe - xl) * i / 20) ** 2, 0.0))) for i in range(21)]
    soff = [q for q in S["top_dome"][41:] if q[0] >= xl]          # crown -> edge, the thickened soffit
    (x0_, z0_), (x1_, z1_) = soff[-1], soff[-2]
    zR = z0_ + (R - x0_) * (z0_ - z1_) / (x0_ - x1_) if x0_ < R and abs(x0_ - x1_) > 1e-9 else z0_
    soff = [q for q in soff if q[0] < R] + [(R, max(zR, zw))]
    z_soff_l = zc1 + math.sqrt(max(R1 * R1 - xl * xl, 0.0))
    soff = [(xl, z_soff_l)] + soff
    v.poly(up + [(xb1, zt), (xb1, zw), (R + tw, zw), (R + tw, zw - Lw)])
    v.poly([(R, zw - Lw)] + [(R, max(zR, zw))] + soff[::-1][1:])
    for a_, b_ in (((xl, z_soff_l), up[0]), ((R, zw - Lw), (R + tw, zw - Lw))):            # break lines (zig-zag)
        L_ = math.dist(a_, b_)
        ux_, uz_ = (b_[0] - a_[0]) / L_, (b_[1] - a_[1]) / L_
        m_ = ((a_[0] + b_[0]) / 2, (a_[1] + b_[1]) / 2)
        d_ = 0.03
        v.poly([a_, (m_[0] - ux_ * d_, m_[1] - uz_ * d_), (m_[0] - ux_ * d_ / 3 - uz_ * d_, m_[1] - uz_ * d_ / 3 + ux_ * d_),
                (m_[0] + ux_ * d_ / 3 + uz_ * d_, m_[1] + uz_ * d_ / 3 - ux_ * d_), (m_[0] + ux_ * d_, m_[1] + uz_ * d_), b_], "THIN")
    # ---- the beam's stirrup and hoop bars
    v.rect(R + cw, zw + cw, xb1 - cw, zt - cw, "REBAR")
    rb = max(0.5, tr_["dia"] / 2e3 * v.k)
    rm = rb / v.k
    nt, nbt = tr_["n"] // 2, tr_["n"] - tr_["n"] // 2
    x_a, x_b = R + cw + rm + 0.008, xb1 - cw - rm - 0.008
    rows = []
    for nn, zz in ((nt, zt - cw - rm - 0.003), (nbt, zw + cw + rm + 0.003)):
        pts = [(x_a + i * (x_b - x_a) / max(1, nn - 1), zz) for i in range(nn)]
        for q in pts:
            sh.dot(v.p(*q), rb)
        rows.append(pts)
    # ---- dimensions and notes (the dome's and the wall's own bars: in the section of the tank, as the example)
    sh.dim_h(v.p(R, 0)[0], v.p(xb1, 0)[0], v.p(0, zw - Lw)[1] - 4, f"{max(b1, tw) * 1e3:.0f}", y_from=v.p(0, zw)[1], below=True)
    sh.dim_h(v.p(R, 0)[0], v.p(R + tw, 0)[0], v.p(0, zw - Lw * 0.45)[1], f"{tw * 1e3:.0f}")
    sh.dim_v(v.p(0, zw)[1], v.p(0, zt)[1], v.p(xb1, 0)[0] + 4, f"{d1 * 1e3:.0f}", x_from=v.p(xb1, 0)[0])
    zs = max(zR, zw)                                          # where the dome's soffit meets the wall's face
    if zs - zw > 0.02:
        sh.dim_v(v.p(0, zw)[1], v.p(0, zs)[1], v.p(R, 0)[0] - 5, f"{(zs - zw) * 1e3:.0f}", x_from=v.p(R, 0)[0])
    xr_ = v.p(xb1, 0)[0] + 9
    sh.leader(v.p(*rows[0][-1]), (xr_, v.p(0, zt)[1] + 6), f"{nb((tr_['n'], tr_['dia']))} HOOPS ({nt} TOP, {nbt} BOTTOM)", 1.7)
    sh.leader(v.p(xb1 - cw - 0.06, zt - cw), (xr_, v.p(0, zt)[1] + 12), "8 # STR. @ 200 C/C", 1.7)
    sh.heading("DETAIL OF TOP RING BEAM", (x0 + bw / 2, y0 + 5), 2.4, f"SCALE 1:{s}")


def _joint_detail(sh, res, x0, y0, bw, bh):
    """DETAIL OF THE JOINT OF THE WALL, BALCONY AND CONE (user 23-Nov-2026): that corner of the section of the tank
    large, its bars as the section draws them - the wall's verticals from the balcony up, the balcony's closed
    stirrup with its hoops, the cone's water-face bar on up the wall's face (a lap), its outer bar into the balcony
    along its bottom, the hoops of the cone and the wall. x0, y0, bw, bh: the box; the drawing in its middle, the
    notes of the water face on its left, the outer face's on its right."""
    g, lev, th, M, opt = res["geo"], res["levels"], res["geo"]["th"], res["members"], res["opt"]
    R, r0, cw = g["R"], g["r0"], opt["cover_water_mm"] / 1e3
    al, t0 = g["alpha"], th["t0"]
    sa_, ca_ = math.sin(al), math.cos(al)
    nx, nz = sa_, -ca_
    w, bl, cn = M["wall"], M["balcony"], M["cone"]
    Za, Zt = lev["cone_top"] - 0.5, lev["B2_top"] + 0.5
    x_in = lambda z_: r0 + (z_ - lev["LWL"]) / math.tan(al)       # the cone's water face at level z_
    Xa, Xb = min(R - 0.3, x_in(Za) - 0.05), g["bal_edge"] + 0.06    # the cone whole down to the window's foot
    s = fit_scale(Xb - Xa, Zt - Za, 95, bh - 22)
    k = 1000.0 / s
    xd = x0 + 138                                      # the drawing's left edge
    v = View(sh, xd, y0 + 18, s, Xa, Za)
    # ---- concrete: the one outline cut to the window, the cut edges as break lines
    cut = _clip(_container_outline(res), Xa, Za, Xb + 1.0, Zt)
    on_cut = lambda q: abs(q[1] - Za) < 1e-6 or abs(q[1] - Zt) < 1e-6 or abs(q[0] - Xa) < 1e-6
    for a_, b_ in zip(cut, cut[1:] + cut[:1]):
        if math.dist(a_, b_) < 1e-6:
            continue
        if on_cut(a_) and on_cut(b_) and (abs(a_[1] - b_[1]) < 1e-6 or abs(a_[0] - b_[0]) < 1e-6):
            _brk(sh, v.p(*a_), v.p(*b_))
        else:
            v.line(a_, b_)
    # ---- bars
    zfoot = lev["cone_top"] + cw + 0.03
    zt_ = Zt - 0.03
    tz = lambda z_: R + th["tw"] + (th["twb"] - th["tw"]) * max(0.0, 1.0 - (z_ - lev["B2_top"]) / max(th["taper"], 1e-6))
    v.poly([(R + th["twb"] - cw, zfoot), (R + th["twb"] - cw, lev["B2_top"]), (tz(zt_) - cw, zt_)], "REBAR")    # wall, outer
    v.poly([(R + cw, zfoot), (R + cw, zt_)], "REBAR")                                                            # wall, inner
    xa, xb, za, zb_ = R + cw, g["bal_edge"] - cw, lev["cone_top"] + cw, lev["B2_top"] - cw
    v.poly([(xa, za), (xb, za), (xb, zb_), (xa, zb_)], "REBAR", True)                                           # balcony
    per = [(xa + 0.05, zb_ - 0.045), (xb - 0.05, zb_ - 0.045), (xb - 0.05, za + 0.045), (xa + 0.05, za + 0.045)]
    Lp = sum(math.dist(p_, q_) for p_, q_ in zip(per, per[1:]))
    v.dots(per, Lp / bl["n"], 0.6, first=Lp / bl["n"] / 2)
    ends = {}
    for j, off in enumerate((cw, t0 - cw)):            # the cone's two faces, from the window's foot
        base = (r0 + nx * off, lev["LWL"] + nz * off)
        at_s = lambda s_, base=base: (base[0] + s_ * ca_, base[1] + s_ * sa_)
        p0 = at_s((Za + 0.03 - base[1]) / sa_)
        if j == 0:                                     # water face: on up the wall's inner face, a lap of 450
            p_w = at_s((R + cw + 0.03 - base[0]) / ca_)
            path = [p0, p_w, (p_w[0], lev["B2_top"] + 0.45)]
        else:                                          # outer face: into the balcony, along its bottom
            p_hi = at_s((za + 0.03 - base[1]) / sa_)
            path = [p0, p_hi, (xb - 0.05, p_hi[1])]
        v.poly(path, "REBAR")
        ends[j] = path
        o2 = 0.035 if j == 0 else -0.035
        sft = lambda q, o2=o2: (q[0] + nx * o2, q[1] + nz * o2)
        a_ = sft(at_s((Za + 0.06 - base[1]) / sa_))
        b_ = sft(at_s((g["h0"] - 0.06 - nz * off) / sa_))
        v.dots([a_, b_], cn["hoop_up"][1] / 1e3, 0.5)
    zone = min(w["zones"], key=lambda z_: lev["wall_top"] - z_["top"] - z_["len"])          # the lowest zone of hoops
    for xf in (lambda z_: R + cw + 0.03, lambda z_: tz(z_) - cw - 0.03):
        zz = lev["B2_top"] + 0.06
        while zz < zt_ - 0.02:
            sh.dot(v.p(xf(zz), zz), 0.5)
            zz += zone["sp"] / 1e3
    # ---- dimensions
    xe_ = v.p(g["bal_edge"], 0)[0]
    sh.dim_v(v.p(0, lev["cone_top"])[1], v.p(0, lev["B2_top"])[1], xe_ + 5, f"{th['bal_t'] * 1e3:.0f}", x_from=xe_)
    sh.dim_h(v.p(R, 0)[0], xe_, v.p(0, Zt)[1] + 4, f"{(g['bal_edge'] - R) * 1e3:.0f}", y_from=v.p(0, lev["B2_top"])[1])
    # (the wall's thickness at the base: in the note on the right - a dimension over the wall sat on its bars)
    cm = (R + 0.05 - (lev["cone_top"] - Za) * 0.55 / math.tan(al), lev["cone_top"] - (lev["cone_top"] - Za) * 0.55)
    sh.dim_across(v.p(*cm), v.p(cm[0] + t0 * sa_, cm[1] - t0 * ca_), f"{t0 * 1e3:.0f}")
    # ---- notes: the water face on the left, the outer face on the right
    xl, xr = xd - 6, xd + (Xb - Xa) * k + 6
    nv = lambda dia_sp, dd: f"{math.ceil(math.pi * dd * 1e3 / dia_sp[1])} - {dia_sp[0]} # @ {dia_sp[1]} C/C"
    # (the left notes low: the L-section of the bottom ring beam is over them)
    sh.leader(v.p(R + cw, lev["B2_top"] + 0.5), (xl, y0 + 50),
              [nv(w["vert"], 2 * R) + " VERTICAL,", f"EACH FACE; {zone['n']} - {zone['dia']} # HOOPS"], 1.6, right=False)
    pw = ends[0][1]
    sh.leader(v.p(pw[0], pw[1] + 0.25), (xl, y0 + 38),
              [f"CONE'S WATER-FACE BARS ({at(cn['mer'])})", "ON UP THE WALL'S FACE, LAP 450"], 1.6, right=False)
    q1 = ends[0][0]
    sh.leader(v.p(q1[0] + (ends[0][1][0] - q1[0]) * 0.3, q1[1] + (ends[0][1][1] - q1[1]) * 0.3), (xl, y0 + 25),
              [f"CONE {cn['t']} THICK,", f"{cn['hoop_up'][0]} # HOOPS @ {cn['hoop_up'][1]} EACH FACE"], 1.6, right=False)
    sh.leader(v.p(xb - 0.05, (za + zb_) / 2), (xr, v.p(0, lev["B2_top"] + 0.15)[1]),
              [f"BALCONY: {nb((bl['n'], bl['dia']))} HOOPS,", at(bl["rad"], "RADIALLY") + " TOP,", at(bl["dist"]) + " BOTTOM"], 1.6)
    ph = ends[1][1]
    sh.leader(v.p(ph[0] + 0.1, ph[1]), (xr, v.p(0, lev["cone_top"] - 0.3)[1]),
              ["CONE'S OUTER BARS INTO THE", "BALCONY, ALONG ITS BOTTOM"], 1.6)
    sh.leader(v.p(tz(lev["B2_top"] + 0.35) - cw, lev["B2_top"] + 0.35), (xr, v.p(0, Zt - 0.05)[1]),
              [f"WALL {w['tb']} AT THE BASE,", f"{w['t']} ABOVE A {th['taper'] * 1e3:.0f} TAPER"], 1.6)
    sh.heading("DETAIL OF THE JOINT OF WALL, BALCONY AND CONE", (x0 + bw / 2, y0 + 7), 2.4, f"SCALE 1:{s}")


def _sheet_container(dw, res, info):
    sh = Sheet(dw, 1, "CONTAINER", 2)
    g, M, opt, th = res["geo"], res["members"], res["opt"], res["geo"]["th"]
    # the section of the tank large, over the sheet's whole height on the left (as the example, 1:30); the details in
    # a column on the right (user request 21-Nov-2026: the drawing as the example's)
    _tank_section(sh, res, 14, 22, 530, 560)
    xr = 552                                        # the right column: xr .. 831
    br, col = M["bottom_ring"], M["column"]
    # top ring beam: the joint's detail
    _ring_detail(sh, res, xr, 494, 150, 90)
    _joint_detail(sh, res, xr, 200, SW - 10 - xr, 100)
    _dome_plan(sh, res, "top_dome", xr + 152, 498, SW - 10 - xr - 156, 84, "PART PLAN OF TOP DOME REINFORCEMENT")
    _dome_plan(sh, res, "bottom_dome", xr + 4, 404, SW - 10 - xr - 8, 88, "PART PLAN OF BOTTOM DOME REINFORCEMENT (EACH FACE)")
    s2 = fit_scale(g["Lb"] + g["dc"] + 1.3, th["d3"] + 1.8, 180, 95)
    _lsec(sh, xr + 6, 318, s2, g["Lb"], g["dc"], th["d3"], 0.0, 1.0, br["stir"], br["legs"],
          f"{nb(br['top'])} HOOPS (OVERLAP NEAR MIDSPAN ONLY)", f"{nb(br['bot'])} HOOPS (OVERLAP NEAR SUPPORT ONLY)",
          [nb((col["n"], col["dia"])), "8 # RINGS @ 100 / 200 C/C"], "PART L - SECTION OF BOTTOM RING BEAM")
    s3 = fit_scale(br["b"] / 1e3 + 0.1, br["d"] / 1e3 + 0.1, 45, 50)
    _beam_xsec(sh, 790, 372, s3, br["b"], br["d"], br["top"], br["bot"], opt["cover_ring_mm"], "SECTION A - A", side=br["side"][0], legs=br["legs"], note="10 # STR.")
    _small_details(sh, res, xr, 82)
    sh.lines(["NOTES:  1. ALL DIMENSIONS ARE IN MILLIMETRE.   2. READ WITH SHEETS 1 AND 3."], xr, 78, 1.9)
    sh.frame(info)
    return sh
