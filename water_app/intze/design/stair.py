"""Intze design: the staircase - its flights, landings and their beams (B1 / B3 / B4 / B5)."""
import math
from .basics import GAMMA_C, _bars, _mesh, area, ast_flex, up


def beam_len(st, kind):
    """The length of a staircase landing beam (m): its span to the staircase's column and the cantilever beyond; B4 the
    cantilever on either side of the column."""
    bm, lc, ds = st["beams"][kind], st["lc"], st["col"]["d"] / 1e3
    return 2 * lc + ds if kind == "B4" else bm["L"] + ds + lc


def _stair(g, lev, opt, mat, q_all):
    """The R.C.C. dog-legged staircase of the example (drawing OPG-3, report 6.0): two flights side by side between
    two columns of its own outside the balcony, beams from two columns of the staging to them at every landing."""
    fckf, fy = mat.fck_f, mat.fy
    w, gap, tread = float(opt["stair_w_m"]), float(opt["stair_gap_m"]), opt["tread_mm"] / 1e3
    n, r0, dc = g["n_col"], g["r0"], g["dc"]
    Lb = g["Lb"]
    ds = opt["stair_col_mm"] / 1e3
    xc = r0 * math.cos(math.pi / n)                    # the chord of the two columns, from the tank's centre
    xs = g["bal_edge"] + w + gap / 2.0 - 0.15          # the line of the staircase's columns
    treads = max(6, min(11, int((Lb - 0.05) // tread)))
    ris = treads + 1
    bal, roof = lev["B2_top"], lev["B1_top"]
    n1 = max(2, int(round(bal / (ris * 0.185))))
    n2 = max(1, int(round((roof - bal) / (ris * 0.185))))
    r1, r2 = bal / (n1 * ris), (roof - bal) / (n2 * ris)
    levels = [round(k * bal / n1, 3) for k in range(1, n1 + 1)] + [round(bal + k * (roof - bal) / n2, 3) for k in range(1, n2 + 1)]
    # flight: waist slab spanning between the landing beams
    span = Lb
    tw_ = max(0.12, up(span / 28.0, 0.01))
    w_fl = GAMMA_C * (tw_ * math.hypot(1.0, max(r1, r2) / tread) + max(r1, r2) / 2.0) + 1.0      # self + finish, on plan
    wu = 1.5 * (w_fl + 3.0)
    Mu = wu * span * span / 8.0
    d = tw_ * 1e3 - opt["cover_stair_mm"] - 5
    Ast = max(ast_flex(Mu, 1000.0, d, fckf, fy) or 9e9, 0.0012 * 1000.0 * tw_ * 1e3)
    main = _mesh(Ast, (10, 12, 16), smax=200, smin=80)
    # landing beam: from the staging's column to the staircase's column, a cantilever beyond it for the outer flight
    L1 = xs - xc - dc / 2.0 - ds / 2.0
    lc = gap / 2.0 + w
    R_fl = (w_fl + 3.0) * w * span / 2.0                                        # one flight's end, service
    R_land = (GAMMA_C * tw_ + 3.0) * math.pi * (w + gap / 2.0) ** 2 / 2.0 / 2.0   # half the semicircular landing
    bbm, dbm = 250, int(max(400, up(L1 / 12.0, 0.05) * 1e3))
    self_ = GAMMA_C * bbm * dbm / 1e6
    Mu_c = 1.5 * ((R_fl + R_land) * lc / 2.0 + self_ * lc * lc / 2.0)
    Mu_s = 1.5 * (self_ * L1 * L1 / 8.0 + (R_fl + R_land) * (lc / 2.0) * (1.0 - lc / 2.0 / L1))
    db_ = dbm - opt["cover_stair_mm"] - 8 - 6
    Asb = max(ast_flex(max(Mu_c, Mu_s), bbm, db_, fckf, fy) or 9e9, 0.85 * bbm * db_ / fy)
    nb, diab = _bars(Asb, (12, 16, 20), nmin=3, width=bbm, cover=opt["cover_stair_mm"])

    def bars_for(Mu):
        As = max(ast_flex(Mu, bbm, db_, fckf, fy) or 9e9, 0.85 * bbm * db_ / fy)
        return _bars(As, (12, 16, 20), nmin=3, width=bbm, cover=opt["cover_stair_mm"])

    # the landing beam at each landing, by what it can rest on (user 23-Nov-2026): B1 on a column of the staging while
    # the landing is below the columns' top; above it up to the balcony B3 on the cone / balcony's outer face; above
    # the balcony B4, a balanced cantilever on the staircase's column alone (never into the wall that holds the water);
    # at the roof B5 on the top ring beam, the landing slab carried on flat to the ring beam
    th = g["th"]

    def face(z):                                       # the container's outer face at level z (beam's mid-depth)
        r0b = r0 + th["b3"] / 2.0
        if z >= lev["cone_top"]:
            return g["bal_edge"]
        xct = g["R"] + th["t0"] / math.sin(g["alpha"])
        return max(r0b, xct - (lev["cone_top"] - z) / math.tan(g["alpha"]))
    xb1 = g["R"] + max(th["b1"], th["tw"])             # the top ring beam's outer face
    # a round face met on the line of the landing beam (Lb / 2 off the tank's axis), not at its radius
    on_line = lambda r_: math.sqrt(max(r_ * r_ - (Lb / 2.0) ** 2, 0.0))
    landings = []
    for z in [0.0] + levels:
        zm = z - dbm / 2e3
        if z >= roof - 1e-6:
            kind, L = "B5", xs - on_line(xb1) - ds / 2.0
        elif z > bal + 1e-6:
            kind, L = "B4", 0.0
        elif zm <= lev["B3_bot"]:
            kind, L = "B1", L1
        else:
            kind, L = "B3", xs - on_line(face(zm)) - ds / 2.0
        landings.append({"z": z, "type": kind, "L": L})
    rl = w + gap / 2.0
    # the landing at the roof, carried on flat to the top ring beam: a slab cantilevered from B5 over the landing's width
    t_br = tw_
    w_br = GAMMA_C * t_br + 1.0 + 3.0
    Mu_br = 1.5 * w_br * rl * rl / 2.0
    br_main = _mesh(max(ast_flex(Mu_br, 1000.0, d, fckf, fy) or 9e9, 0.0012 * 1000.0 * t_br * 1e3), (8, 10, 12), smax=200, smin=80)
    beams = {}
    for kind in ("B1", "B3", "B4", "B5"):
        Ls = [x["L"] for x in landings if x["type"] == kind]
        if not Ls:
            continue
        L = max(Ls)
        if kind == "B1":
            Mu, R_col = max(Mu_c, Mu_s), 2.0 * (R_fl + R_land) * 0.75 + self_ * (L / 2.0 + lc)
        elif kind == "B3":
            Ms = 1.5 * (self_ * L * L / 8.0 + (R_fl + R_land) * (lc / 2.0) * max(0.0, 1.0 - lc / 2.0 / max(L, lc)))
            Mu, R_col = max(Mu_c, Ms), 2.0 * (R_fl + R_land) * 0.75 + self_ * (L / 2.0 + lc)
        elif kind == "B4":                             # the same cantilever on either side of the column
            Mu, R_col = Mu_c, 2.0 * (R_fl + R_land) + self_ * 2.0 * lc
        else:                                          # B5: the landing slab over its span, the top flight near the column
            q = w_br * rl + self_
            a_ = max(L - lc / 2.0, 0.0)                # the flight's end from the ring beam
            Ms = 1.5 * (q * L * L / 8.0 + R_fl * a_ * (L - a_) / max(L, 1e-6))
            Mu, R_col = max(Mu_c, Ms), q * L / 2.0 + R_fl * a_ / max(L, 1e-6) + (R_land + self_ * lc)
        nb_, dia_ = bars_for(Mu)
        beams[kind] = {"b": bbm, "d": dbm, "top": (nb_, dia_), "bot": (nb_, dia_) if kind != "B4" else (3, 12),
                       "stir": (8, 150), "Mu": Mu, "L": L, "R": R_col, "n": len(Ls),
                       "levels": [x["z"] for x in landings if x["type"] == kind]}
    # the staircase's column and its footing: the landings alternate between the two columns
    H_col = roof + float(opt["founding_depth_m"]) - 0.6
    loads = [beams[x["type"]]["R"] for x in landings]
    P = max(sum(loads[0::2]), sum(loads[1::2])) + GAMMA_C * area(ds) * H_col
    ncol, dcol = 6, 16
    Pcap = (0.4 * fckf * (area(ds * 1e3) - ncol * area(dcol)) + 0.67 * fy * ncol * area(dcol)) / 1e3
    side = up(math.sqrt(1.1 * P / q_all), 0.1)
    Mf = 1.5 * (P / side ** 2) * side * ((side - ds) / 2.0) ** 2 / 2.0
    tf = 0.6
    Asf = max(ast_flex(Mf, side * 1e3, tf * 1e3 - 60, fckf, fy) or 9e9, 0.0012 * side * 1e3 * tf * 1e3 / 2.0) / side
    return {"w": w, "gap": gap, "tread": tread, "treads": treads, "risers": ris, "n1": n1, "n2": n2, "riser1": r1,
            "riser2": r2, "levels": levels, "xs": xs, "xc": xc, "Lb": Lb, "L1": L1, "lc": lc, "waist": int(round(tw_ * 1e3)),
            "main": main, "dist": (8, 200), "Mu": Mu, "wu": wu, "beam": {"b": bbm, "d": dbm, "top": (nb, diab),
                                                                        "bot": (nb, diab), "stir": (8, 150), "Mu": max(Mu_c, Mu_s)},
            "col": {"d": int(ds * 1e3), "n": ncol, "dia": dcol, "tie": (8, 200), "P": P, "Pcap": Pcap, "H": H_col},
            "footing": {"side": side, "t": int(tf * 1e3), "te": 150, "bars": _mesh(Asf, (10, 12, 16), smax=200)},
            "bal": bal, "roof": roof, "landings": landings, "beams": beams, "xb1": xb1, "xb1_line": on_line(xb1),
            "bridge": {"t": int(round(t_br * 1e3)), "span": xs - rl - on_line(xb1), "cant": rl, "Mu": Mu_br, "main": br_main}}
