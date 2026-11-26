"""Intze design: the whole tank designed - domes, ring beams, walls, cone, staging, raft."""
import math
from .basics import (
    DEFAULTS, G, GAMMA_C, GAMMA_W, Mat, RING1_BAND, RING1_NOMINAL, T10, TAU_MAX, ZONE_Z, _bars, _capacity, _interp,
    _mesh, area, ast_flex, up,
)
from .bbs import _rows, bbs
from .columns import col_curve, col_moment
from .members import _circ_beam, _forces, _kz, _ring_section, _sa_g, proportion
from .stair import _stair


# ------------------------------------------------------------------------------------------------------- the design
def design(cap_kl, staging_m, swd_m, opts=None):
    """The whole design; see the module text. opts may fix any default (DEFAULTS), D_m or cyl_depth_m."""
    opt = dict(DEFAULTS)
    opt.update({k: v for k, v in (opts or {}).items() if v not in (None, "")})
    mat = Mat(int(opt["fck"]), int(opt["fck_found"]), int(opt["fy"]), float(opt["sst_water"]))
    fck, fckf, fy, sst = mat.fck, mat.fck_f, mat.fy, mat.sst_w
    calc, warn = [], []

    def row(sec, item, val, unit="", ref=""):
        calc.append((sec, item, val, unit, ref))

    g = proportion(cap_kl, swd_m, opt)
    D, D0, R, r0 = g["D"], g["D0"], g["R"], g["r0"]
    sa, ca = math.sin(g["alpha"]), math.cos(g["alpha"])
    cw = opt["cover_water_mm"]
    # ---- the container: thicknesses (the loads change with them)
    th = {"t1": 0.10, "t1e": 0.12, "edge": 1.4, "b1": 0.25, "d1": 0.20, "tw": 0.20, "twb": 0.30, "taper": 1.0,
          "bal_w": float(opt["balcony_w_m"]), "bal_t": 0.40, "t0": 0.40, "t2": 0.20, "t2e": 0.35, "b3": 0.60,
          "d3": 0.90}
    for _ in range(8):
        f = _forces(g, th, opt)
        new = dict(th)
        Tw = GAMMA_W * g["hc"] * R                                      # hoop tension at the wall's base
        new["twb"] = max(th["tw"], up((Tw * 1e3 / mat.sct - (mat.m - 1.0) * Tw * 1e3 / sst) / 1e6, 0.025))
        Nmax = max(c["Nth"] for c in f["cone"])
        new["t0"] = max(0.25, up(new["twb"] + 0.025, 0.025), up(Nmax * 1e3 / sst / 0.0225 / 1e6, 0.025))
        new["bal_t"] = new["t0"]
        while max(f["T1"], f["hoop1_crown"]) / (new["t1"] * 1e3) > 0.25 * fck / 4.0:     # a quarter of 0.25 fck: thin shell
            new["t1"] = round(new["t1"] + 0.025, 3)
        while max(f["T2"], f["hoop2_crown"]) / (new["t2"] * 1e3) > 0.25 * fck / 2.0:
            new["t2"] = round(new["t2"] + 0.025, 3)
        new["t1e"] = up(1.2 * new["t1"], 0.01)
        new["t2e"] = up(1.75 * new["t2"], 0.025)
        # the top ring beam nominal, 4 - 12 # (as the example): the rest of the dome's pull is taken by the wall's
        # top band of hoops (user 22-Nov-2026) - see the wall's zones
        b1, d1, n1, dia1 = _ring_section(RING1_NOMINAL, 250, 200, cw)
        new["b1"], new["d1"] = b1 / 1e3, d1 / 1e3
        new = {k: round(v, 3) for k, v in new.items()}
        if new == th:
            break
        th = new
    f = _forces(g, th, opt)
    g["cap"] = _capacity(D, D0, g["h0"], g["hc"], g["h2"])
    M = {}
    # top dome
    t1m = int(round(th["t1"] * 1e3))
    M["top_dome"] = {"t": t1m, "te": int(round(th["t1e"] * 1e3)), "edge": th["edge"],
                     "rad": _mesh(0.0024 * t1m * 1e3, (10, 12)), "hoop": _mesh(0.0024 * t1m * 1e3, (10, 12)),
                     "edge_rad": (10, 100), "edge_hoop": (12, 150)}
    P_ring = n1 * area(dia1) * sst / 1e3                         # what the ring beam's hoops carry (kN)
    P_band = max(0.0, f["P1"] - P_ring)                         # the rest: the wall's top band
    M["top_ring"] = {"b": b1, "d": d1, "n": n1, "dia": dia1, "stir": (8, 200), "P": f["P1"], "P_ring": P_ring, "P_band": P_band}
    # wall: hoops by zones of about 1 m from its top, both faces; the zones within RING1_BAND of the top take, besides
    # the water, the part of the dome's pull the ring beam does not (as the example: 4 - 12 # in the beam, 13 - 12 #
    # a face in the wall's top 950)
    Hw = f["Hwall"]
    nz = max(1, int(round(Hw / 1.0)))
    zl = Hw / nz
    band = [i for i in range(nz) if i * zl < RING1_BAND - zl / 2] or [0]   # the zones starting in its upper part
    T_band = P_band / (len(band) * zl)                          # kN per m of height
    zones = []
    for i in range(nz):
        bot = (i + 1) * zl
        T = GAMMA_W * max(0.0, bot - g["fb"]) * R + (T_band if i in band else 0.0)
        over = max(0.0, bot - (Hw - th["taper"]))                 # into the taper
        t_loc = th["tw"] + (th["twb"] - th["tw"]) * min(1.0, over / max(th["taper"], 1e-6))
        As = max(T * 1e3 / sst, 0.0024 * t_loc * 1e6)
        dia, sp = _mesh(As / 2.0, (10, 12, 16, 20, 25))
        zones.append({"top": round(i * zl, 3), "len": round(zl, 3), "T": T, "As": As, "dia": dia, "sp": sp,
                      "n": math.ceil(zl * 1000.0 / sp)})
    K = g["hc"] ** 2 / (D * (th["tw"] + th["twb"]) / 2.0)
    Mw = _interp(T10, K) * GAMMA_W * g["hc"] ** 3                        # kNm/m, tension on the water face
    dwb = th["twb"] * 1e3 - cw - 8
    As_min_w = 0.0024 * th["tw"] * 1e6 / 2.0
    M["wall"] = {"t": int(round(th["tw"] * 1e3)), "tb": int(round(th["twb"] * 1e3)), "taper": th["taper"],
                 "zones": zones, "vert": _mesh(As_min_w, (10, 12)),
                 "base_in": _mesh(max(Mw * 1e6 / (sst * 0.87 * dwb), As_min_w), (10, 12, 16, 20)),
                 "base_len": round(min(Hw, th["taper"] + 0.6), 2), "Mw": Mw, "K": K}
    # balcony = the ring beam at the top of the cone
    nb2, db2 = _bars(f["P2"] * 1e3 / sst, (16, 20, 25, 28), nmin=6, even=True,
                     width=2 * int((th["twb"] + th["bal_w"] + th["bal_t"]) * 1e3), cover=cw, cc_min=100)
    blt = th["bal_t"] * 1e3
    Mu_bal = 1.5 * ((GAMMA_C * th["bal_t"] + opt["balcony_live_kn_m2"]) * th["bal_w"] ** 2 / 2.0 + 1.0 * th["bal_w"])
    As_bal = max(ast_flex(Mu_bal, 1000.0, blt - cw - 6, fck, fy) or 0.0, 0.0012 * blt * 1e3)
    M["balcony"] = {"w": th["bal_w"], "t": int(round(blt)), "n": nb2, "dia": db2, "rad": _mesh(As_bal, (10, 12, 16)),
                    "dist": (10, 200), "P": f["P2"]}
    # cone
    t0m = int(round(th["t0"] * 1e3))
    N_low, N_up = max(c["Nth"] for c in f["cone"][:3]), max(c["Nth"] for c in f["cone"][2:])
    As_min0 = 0.0024 * t0m * 1e3
    hl = _mesh(max(N_low * 1e3 / sst, As_min0) / 2.0, (12, 16, 20, 25, 28))
    hu = _mesh(max(N_up * 1e3 / sst, As_min0) / 2.0, (12, 16, 20, 25, 28))
    M["cone"] = {"t": t0m, "hoop_low": hl, "hoop_up": hu, "n_low": math.ceil(g["slant"] / 2.0 * 1e3 / hl[1]),
                 "n_up": math.ceil(g["slant"] / 2.0 * 1e3 / hu[1]), "mer": _mesh(0.003 * t0m * 1e3, (16, 20), smin=120),
                 "N_low": N_low, "N_up": N_up}
    t2m = int(round(th["t2"] * 1e3))
    M["bottom_dome"] = {"t": t2m, "te": int(round(th["t2e"] * 1e3)), "edge": th["edge"],
                        "rad": _mesh(0.0024 * t2m * 1e3 / 2.0, (10, 12)), "hoop": _mesh(0.0024 * t2m * 1e3 / 2.0, (10, 12)),
                        "edge_rad": (12, 100), "edge_hoop": (12, 150)}
    # ---- staging, foundation: passes for the sizes that feed each other
    n_col = int(opt.get("n_columns") or max(4, 2 * math.ceil(math.pi * D0 / opt["col_spacing_m"] / 2.0 - 1e-9)))
    Lb = 2.0 * r0 * math.sin(math.pi / n_col)
    Z, Ifac, Rr = ZONE_Z[opt["zone"]], opt["I"], opt["R"]
    Df = float(opt["founding_depth_m"])
    lwl = float(staging_m)
    tr, bb, db, d3 = 0.9, 0.25, 0.60, None
    W_water = GAMMA_W * g["cap"]
    W_live = opt["roof_live_kn_m2"] * math.pi * R * R + opt["balcony_live_kn_m2"] * math.pi * (
        (R + th["twb"] + th["bal_w"]) ** 2 - (R + th["twb"]) ** 2)
    C = None
    for _pass in range(4):
        found = None
        for dc_mm in range(400, 1650, 50):
            dc = dc_mm / 1e3
            th["b3"] = max(dc, 0.4)
            th["d3"] = max(d3 or 0.0, up(1.5 * th["b3"], 0.05))
            f = _forces(g, th, opt)
            lev = {"GL": 0.0, "LWL": lwl, "B3_bot": lwl - th["d3"], "cone_top": lwl + g["h0"],
                   "B2_top": lwl + g["h0"] + th["bal_t"], "FSL": lwl + g["H"], "wall_top": lwl + g["H"] + g["fb"],
                   "dome2_crown": lwl + g["h2"], "raft_bot": -Df, "raft_top": -Df + tr}
            lev["B1_top"] = lev["wall_top"] + th["d1"]
            lev["dome1_crown"] = lev["B1_top"] + g["h1"]
            col_base = lev["raft_top"]
            zg = 0.45 if lev["B3_bot"] > 4.0 else None                 # a brace at the ground
            z0 = zg if zg is not None else col_base
            n_pan = max(1, math.ceil((lev["B3_bot"] - z0) / opt["panel_max_m"] - 1e-9))
            Lp = (lev["B3_bot"] - z0) / n_pan
            stub = (zg - col_base) if zg is not None else 0.0
            braces = [z0 + k * Lp for k in range(0 if zg is not None else 1, n_pan)]
            Lc = lev["B3_bot"] - col_base
            Wt = {"Top dome": GAMMA_C * th["t1"] * f["dome1"]["area"],
                  "Top ring beam": GAMMA_C * th["b1"] * th["d1"] * 2 * math.pi * (R + th["tw"] / 2.0),
                  "Cylindrical wall": GAMMA_C * f["A_wall"] * 2 * math.pi * (R + th["tw"] / 2.0),
                  "Balcony ring": GAMMA_C * (th["twb"] + th["bal_w"]) * th["bal_t"] * 2 * math.pi * (
                      R + (th["twb"] + th["bal_w"]) / 2.0),
                  "Conical dome": GAMMA_C * th["t0"] * math.pi * (R + r0) * g["slant"],
                  "Bottom dome": GAMMA_C * th["t2"] * f["dome2"]["area"],
                  "Bottom ring beam": GAMMA_C * th["b3"] * th["d3"] * 2.0 * math.pi * r0}
            zc = {"Top dome": lev["B1_top"] + g["h1"] / 3.0, "Top ring beam": lev["B1_top"] - th["d1"] / 2.0,
                  "Cylindrical wall": (lev["B2_top"] + lev["wall_top"]) / 2.0,
                  "Balcony ring": lev["cone_top"] + th["bal_t"] / 2.0, "Conical dome": lwl + g["h0"] / 2.0,
                  "Bottom dome": lwl + g["h2"] / 3.0, "Bottom ring beam": lwl - th["d3"] / 2.0}
            W_cont = sum(Wt.values())
            z_cont = sum(Wt[k] * zc[k] for k in Wt) / W_cont
            W_col = n_col * GAMMA_C * area(dc) * Lc
            W_br = len(braces) * n_col * GAMMA_C * bb * db * (Lb - dc)
            W_stg = W_col + W_br
            # lateral stiffness: columns restrained by the braces (stiffness ratio of the joints), panels in series
            Ic, Ib = math.pi * dc ** 4 / 64.0, bb * db ** 3 / 12.0
            kbar = (4.0 * (Ib / Lb) * 0.5) / (2.0 * Ic / Lp)
            afac = kbar / (2.0 + kbar)
            Ek = mat.E * 1e3
            hts = [Lp] * n_pan + ([stub] if stub > 0.3 else [])
            Ks = 1.0 / sum(h ** 3 / (n_col * 12.0 * Ek * Ic * afac) for h in hts)
            # IS 1893 (Part 2):2014 two-mass model, equivalent cylinder
            h_eq = g["cap"] / (math.pi * R * R)
            hD = h_eq / D
            mw = W_water / G
            mi = mw * math.tanh(0.866 / hD) / (0.866 / hD)
            mc = mw * 0.23 * math.tanh(3.68 * hD) / hD
            hi_s = h_eq * (0.375 * (1 + 1.333 * ((0.866 / hD) / math.tanh(0.866 / hD) - 1)) if hD <= 1.33 else 0.45)
            x = 3.68 * hD
            hc_s = h_eq * (1 - (math.cosh(x) - 2.01) / (x * math.sinh(x)))
            ms = (W_cont + W_stg / 3.0) / G
            Ti = 2 * math.pi * math.sqrt((mi + ms) / Ks)
            Tc = 2 * math.pi / math.sqrt(3.68 * math.tanh(x)) * math.sqrt(D / G)
            Ahi = Z / 2.0 * Ifac / Rr * _sa_g(Ti, opt["soil_type"])
            Ahc = Z / 2.0 * Ifac / Rr * _sa_g(Tc, opt["soil_type"], damping5=False)
            hs = lwl - col_base
            Vi, Vc = Ahi * (mi + ms) * G, Ahc * mc * G
            Mi = Ahi * (mi * (hi_s + hs) + ms * (z_cont - col_base)) * G
            Mc = Ahc * mc * (hc_s + hs) * G
            Vq, Mq = math.hypot(Vi, Vc), math.hypot(Mi, Mc)
            Ti_e = 2 * math.pi * math.sqrt(ms / Ks)
            Ahe = Z / 2.0 * Ifac / Rr * _sa_g(Ti_e, opt["soil_type"])
            Ve, Me_ = Ahe * ms * G, Ahe * ms * (z_cont - col_base) * G

            def pd(z):                       # IS 875 (Part 3):2015, k1 = k3 = k4 = 1, category 2, Kd 0.9, Ka 1.0, Kc 0.9
                vz = opt["wind_vb"] * _kz(z)
                return 0.81 * 0.6 * vz * vz / 1000.0
            A_cont = ((D + 2 * th["tw"]) * (lev["B1_top"] - lev["cone_top"]) + (D + D0) / 2.0 * g["h0"]
                      + 2.0 / 3.0 * D * g["h1"])
            Fw_c = 0.7 * A_cont * pd(lev["B1_top"])
            Fw_s = (1.2 * n_col * dc * Lc + 2.0 * len(braces) * db * D0) * pd(lev["B3_bot"])
            Vw = Fw_c + Fw_s
            Mw_ = Fw_c * ((lev["dome1_crown"] + lwl) / 2.0 - col_base) + Fw_s * Lc / 2.0
            lat = [("earthquake, tank full", Vq, Mq, True), ("earthquake, tank empty", Ve, Me_, False),
                   ("wind, tank full", Vw, Mw_, True), ("wind, tank empty", Vw, Mw_, False)]
            P_full = (W_cont + W_water + W_live + W_br) / n_col + GAMMA_C * area(dc) * Lc
            P_empty = (W_cont + W_br) / n_col + GAMMA_C * area(dc) * Lc
            h_des = max(Lp, stub)
            emin = max(0.02, h_des / 500.0 + dc / 30.0)
            cases = [("gravity, tank full", 1.5 * P_full, 0.0)]
            for name, V, Mo_, full in lat:
                Pg, dP, Mcol = (P_full if full else P_empty), 2.0 * Mo_ / (n_col * r0), V * h_des / n_col
                cases.append((name + ": column in the line of the load", 1.5 * (Pg + dP), 1.5 * Mcol / 2.0))
                cases.append((name + ": column on the bending axis", 1.5 * Pg, 1.5 * Mcol))
                if not full:
                    cases.append((name + ": uplift side", 0.9 * Pg - 1.5 * dP, 1.5 * Mcol / 2.0))
            Ag = area(dc_mm)
            cands = []
            for dia in (16, 20, 25, 28, 32):
                fit = int(math.pi * (dc_mm - 2 * opt["cover_mm"] - 20 - dia) // max(dia + 40, 100))
                for n in range(6 if dia <= 20 else 8, fit + 1):
                    pt = 100.0 * n * area(dia) / Ag
                    if 0.8 <= pt <= 3.0:
                        cands.append((pt, n, dia))
            ok = None
            for pt, n, dia in sorted(cands):
                if pt > 2.0 and dc_mm < 1600:
                    break
                curve = col_curve(dc_mm, n, dia, opt["cover_mm"] + 10 + dia / 2.0, fck, fy)
                worst = 0.0
                for name, Pu, Mu in cases:
                    cap_m = col_moment(curve, Pu)
                    need = max(Mu, abs(Pu) * emin)
                    if cap_m is None or cap_m <= 0:
                        worst = 9.9
                        break
                    worst = max(worst, need / cap_m)
                if worst <= 1.0:
                    ok = (pt, n, dia, worst)
                    break
            if ok:
                found = dict(dc=dc, dc_mm=dc_mm, pt=ok[0], n=ok[1], dia=ok[2], util=ok[3], cases=cases, lat=lat,
                             P_full=P_full, P_empty=P_empty, emin=emin, h_des=h_des, Ks=Ks, Ti=Ti, Tc=Tc, Ahi=Ahi,
                             Ahc=Ahc, mi=mi, mc=mc, ms=ms, h_eq=h_eq, Vi=Vi, Vc=Vc, Vq=Vq, Mq=Mq, Ve=Ve, Me=Me_,
                             Vw=Vw, Mw=Mw_, pd_top=pd(lev["B1_top"]), afac=afac, W_col=W_col, W_br=W_br,
                             W_cont=W_cont, Wt=Wt, n_pan=n_pan, Lp=Lp, stub=stub, braces=braces, Lc=Lc, lev=lev,
                             Vmax=max(v for _, v, _, _ in lat), Mfull=max(Mq, Mw_), Mempty=max(Me_, Mw_))
                break
        if found is None:
            raise ValueError("no column of up to 1600 mm passes - the staging is too high or the zone too severe")
        C = found
        dc, dc_mm, lev = C["dc"], C["dc_mm"], C["lev"]
        # braces, as the report
        Lcl = Lb - dc
        Mlev = C["Vmax"] * C["Lp"]
        Mo = Mlev / n_col * (1.0 + math.cos(2.0 * math.pi / n_col))
        Mb = 0.5 * Mo * (Lcl / Lb) / math.cos(math.pi / n_col)
        Fb = 2.0 * Mb / Lcl
        nb, ndb = bb, db
        while True:
            de = ndb * 1e3 - opt["cover_mm"] - 8 - 10
            if 1.5 * Fb * 1e3 / (nb * 1e3 * de) <= TAU_MAX[fck] / 2.0 and 1.5 * Mb * 1e6 <= 2.0 * mat.q_lim * fck * nb * 1e3 * de * de:
                break
            ndb = round(ndb + 0.05, 2)
            if ndb > 3.0 * nb:
                nb = round(nb + 0.05, 2)
        # bottom ring beam: circular beam on the columns, limit state
        cb3 = _circ_beam(f["w3"], r0, n_col)
        b3m = th["b3"] * 1e3
        nd3 = th["d3"]
        while True:
            dd3 = nd3 * 1e3 - opt["cover_ring_mm"] - 10 - 12
            Mt3 = 1.5 * cb3["T"] * (1.0 + nd3 / th["b3"]) / 1.7                      # IS 456 41.4.2
            Me3 = 1.5 * max(abs(cb3["Ms"]), abs(cb3["Mm"])) + Mt3
            Ve3 = 1.5 * cb3["V"] + 1.6 * 1.5 * cb3["T"] / th["b3"]
            if Me3 * 1e6 <= mat.q_lim * fck * b3m * dd3 * dd3 and Ve3 * 1e3 / (b3m * dd3) <= TAU_MAX[fck]:
                break
            nd3 = round(nd3 + 0.05, 2)
        # the annular raft on the net bearing capacity, as the report
        W_tot = C["W_cont"] + W_water + W_live + C["W_col"] + C["W_br"]
        W_emp = C["W_cont"] + C["W_col"] + C["W_br"]
        q_all = float(opt["sbc_kn_m2"])
        bR = up(dc + 0.1, 0.05)
        kf, raft = 1.0, None
        while kf < 4.0:
            a2 = W_tot / q_all * kf / math.pi
            if 2.0 / 3.0 * math.sqrt(a2) >= r0:               # the centroid of even a full circle is beyond the columns
                Ro, Ri = math.sqrt(a2), 0.0
            else:
                lo, hi = 0.0, r0
                for _ in range(60):
                    mid = (lo + hi) / 2.0
                    if 2.0 / 3.0 * ((mid * mid + a2) ** 1.5 - mid ** 3) / a2 < r0:
                        lo = mid
                    else:
                        hi = mid
                Ri = hi
                Ro = math.sqrt(Ri * Ri + a2)
            Ro, Ri = up(Ro, 0.05), math.floor(Ri / 0.05 + 1e-9) * 0.05
            if Ri < 0.5:
                Ri = 0.0
            Ro = max(Ro, r0 + bR / 2.0 + 0.3)
            Ri = min(Ri, r0 - bR / 2.0 - 0.3) if Ri else 0.0
            A = math.pi * (Ro * Ro - Ri * Ri)
            Zr = math.pi * (Ro ** 4 - Ri ** 4) / (4.0 * Ro)
            q_g = W_tot / A
            q_max = q_g + (C["Mfull"] + C["Vmax"] * tr) / Zr
            q_min = W_emp / A - (C["Mempty"] + C["Vmax"] * tr) / Zr
            if q_g <= q_all + 1e-6 and q_max <= 1.25 * q_all and q_min >= 0:
                raft = dict(Ro=Ro, Ri=Ri, A=A, Z=Zr, q_g=q_g, q_max=q_max, q_min=q_min, kf=kf)
                break
            kf *= 1.03
        if raft is None:
            raise ValueError("raft: no size gives a bearing pressure within the net bearing capacity")
        Ro, Ri = raft["Ro"], raft["Ri"]
        qu = max(1.5 * raft["q_g"], 1.2 * raft["q_max"])
        rfo, rfi = r0 + bR / 2.0, r0 - bR / 2.0
        ao, ai = Ro - rfo, rfi - Ri
        Mo_u = qu * ao * ao * (2.0 * Ro + rfo) / (6.0 * rfo)
        Mi_u = qu * ai * ai * (2.0 * Ri + rfi) / (6.0 * rfi) * (1.2 if Ri == 0 else 1.0)
        covr = opt["cover_raft_mm"]
        te = 0.2

        def depth_at(tmm, a, s):                 # effective depth at s from the beam's face (the slab tapers to te)
            return (tmm - (tmm - te * 1e3) * min(1.0, s / max(a, 1e-6))) - covr - 12

        # the foundation ring beam lies in the raft's depth: that depth must hold the beam's moments too (21-Nov-2026:
        # a 150 KL tank got a 350 raft whose ring beam needed millions of bars - ast_flex beyond its limit)
        cbr0 = _circ_beam(1.5 * W_tot / (2 * math.pi * r0), r0, n_col)
        bRm0 = bR * 1e3
        for tr_mm in range(300, 3050, 50):
            d0 = tr_mm - covr - 12
            if max(Mo_u, Mi_u) * 1e6 > mat.q_lim * fckf * 1000.0 * d0 * d0:
                continue
            ddr0 = tr_mm - opt["cover_fbeam_mm"] - 20
            Mr0 = max(abs(cbr0["Ms"]), abs(cbr0["Mm"])) + cbr0["T"] * (1.0 + tr_mm / bRm0) / 1.7
            if Mr0 * 1e6 > mat.q_lim * fckf * bRm0 * ddr0 * ddr0:
                continue
            good, As_sh = True, {True: 0.0, False: 0.0}
            for a, outer in ((ao, True), (ai, False)):
                s = d0 / 1e3
                if s >= a:
                    continue
                x = rfo + s if outer else rfi - s
                V = qu * ((Ro * Ro - x * x) if outer else (x * x - Ri * Ri)) / (2.0 * x)
                ds = depth_at(tr_mm, a, s)
                pt = next((p_ / 100.0 for p_ in range(15, 61) if mat.tau_c(p_ / 100.0, fckf) >= V * 1e3 / (1000.0 * ds)), None)
                if pt is None:               # more than 0.6 % of steel for the shear: a thicker slab
                    good = False
                    break
                As_sh[outer] = pt / 100.0 * 1000.0 * ds * x / (rfo if outer else rfi)
            if good:
                break
        ntr = tr_mm / 1e3
        changed = abs(ntr - tr) > 1e-6 or abs(nb - bb) > 1e-6 or abs(ndb - db) > 1e-6 or abs(nd3 - th["d3"]) > 1e-6
        tr, bb, db, d3 = ntr, nb, ndb, nd3
        if not changed:
            break
    th["d3"] = d3
    # ---- members of the staging
    cb3 = _circ_beam(f["w3"], r0, n_col)
    b3m, d3m = int(round(th["b3"] * 1e3)), int(round(th["d3"] * 1e3))
    cring = opt["cover_ring_mm"]
    dd3 = d3m - cring - 10 - 12
    Mt3 = 1.5 * cb3["T"] * (1.0 + th["d3"] / th["b3"]) / 1.7
    hoop3 = max(0.0, f["P3"]) * 1e3 / sst / 2.0
    As_min3 = 0.85 * b3m * dd3 / fy
    As3_top = max(ast_flex(1.5 * abs(cb3["Ms"]) + Mt3, b3m, dd3, fck, fy), As_min3) + hoop3
    As3_bot = max(ast_flex(1.5 * abs(cb3["Mm"]) + Mt3, b3m, dd3, fck, fy), As_min3) + hoop3
    Ve3 = 1.5 * cb3["V"] + 1.6 * 1.5 * cb3["T"] / th["b3"]
    tve3 = Ve3 * 1e3 / (b3m * dd3)
    b1_, d1_ = b3m - 2 * cring - 10, d3m - 2 * cring - 10
    legs3 = 4 if b3m >= 600 else 2
    asv3 = max(1.5 * cb3["T"] * 1e6 / (b1_ * d1_ * 0.87 * fy) + 1.5 * cb3["V"] * 1e3 / (2.5 * d1_ * 0.87 * fy),
               (tve3 - mat.tau_c(100.0 * As3_top / (b3m * dd3))) * b3m / (0.87 * fy), 0.4 * b3m / (0.87 * fy))
    sv3 = int(max(100, min(200, legs3 * area(10) / asv3 // 5 * 5)))
    n3t, d3t = _bars(As3_top, (20, 25, 28, 32), nmin=3, width=b3m, cover=cring)
    n3b, d3b = _bars(As3_bot, (20, 25, 28, 32), nmin=3, width=b3m, cover=cring)
    M["bottom_ring"] = {"b": b3m, "d": d3m, "top": (n3t, d3t), "bot": (n3b, d3b), "side": (2 if d3m >= 750 else 0, 12),
                        "stir": (10, min(100, sv3), sv3), "legs": legs3}
    conf_len = int(max(dc_mm, C["Lp"] * 1e3 / 6.0, 450))
    M["column"] = {"d": dc_mm, "n": C["n"], "dia": C["dia"], "tie": (8, 200), "conf": (8, 100), "conf_len": conf_len,
                   "pt": C["pt"]}
    Lcl = Lb - dc
    Mlev = C["Vmax"] * C["Lp"]
    Mo = Mlev / n_col * (1.0 + math.cos(2.0 * math.pi / n_col))
    Mb = 0.5 * Mo * (Lcl / Lb) / math.cos(math.pi / n_col)
    Fb = 2.0 * Mb / Lcl
    bbm, dbm = int(round(bb * 1e3)), int(round(db * 1e3))
    deb = dbm - opt["cover_mm"] - 8 - 10
    Ast_b = max(1.5 * Mb * 1e6 / (0.87 * fy * (dbm - 2 * (opt["cover_mm"] + 18))), 0.85 * bbm * deb / fy)
    nbb, dbb = _bars(Ast_b, (16, 20, 25), nmin=2, width=bbm)
    asv_b = max((1.5 * Fb * 1e3 - mat.tau_c(100.0 * nbb * area(dbb) / (bbm * deb)) * bbm * deb) / (0.87 * fy * deb),
                0.4 * bbm / (0.87 * fy))
    svb = int(max(100, min(200, 0.75 * deb, 2 * area(8) / asv_b) // 5 * 5))
    M["brace"] = {"b": bbm, "d": dbm, "top": (nbb, dbb), "bot": (nbb, dbb), "stir": (8, 100, svb), "Mb": Mb, "Fb": Fb}
    # ---- the raft's steel
    Ro, Ri = raft["Ro"], raft["Ri"]
    trm = int(round(tr * 1e3))
    d0 = trm - covr - 12
    Ast_o = max(ast_flex(Mo_u, 1000.0, d0, fckf, fy), As_sh[True], 0.0012 * 1000.0 * trm)
    Ast_i = max(ast_flex(Mi_u, 1000.0, d0, fckf, fy), As_sh[False], 0.0012 * 1000.0 * trm)
    rad = None
    for dia in (12, 16, 20, 25, 28, 32):
        n = max(math.ceil(2 * math.pi * rfo * Ast_o / area(dia)), math.ceil(2 * math.pi * rfi * Ast_i / area(dia)))
        n = int(math.ceil(n / 4.0) * 4)
        if 2 * math.pi * r0 / n * 1e3 >= 140 or dia == 32:       # the smallest bar not closer than 140 on the column circle
            rad = (n, dia)
            break
    n_rad, dia_rad = rad
    # the inner cantilever in three lengths: half the bars stop where the moment allows it
    Ls = [up(ai * k, 0.05) for k in (0.37, 0.33)]
    Ls.append(round(ai - sum(Ls), 3))
    zin, n_now, s_acc = [], n_rad, 0.0
    for L in Ls:
        if s_acc > 0:
            rs = rfi - s_acc
            Ms_ = qu * (ai - s_acc) ** 2 * (2.0 * Ri + rs) / (6.0 * rs)
            ds = depth_at(trm, ai, s_acc)
            need = math.ceil(2 * math.pi * rs * max(ast_flex(Ms_, 1000.0, ds, fckf, fy) or 9e9, 0.0012 * 1000.0 * (ds + covr + 12)) / area(dia_rad))
            if n_now // 2 >= need and n_now // 2 >= 8 and 2 * math.pi * rs / (n_now // 2) <= 0.45:
                n_now //= 2
        zin.append((round(L, 3), n_now))
        s_acc += L
    t_mean = (trm + te * 1e3) / 2.0
    M["raft"] = {"Ro": Ro, "Ri": Ri, "t": trm, "te": int(te * 1e3), "rad": (n_rad, dia_rad),
                 "rad_sp": int(round(2 * math.pi * r0 / n_rad * 1e3)), "zones_in": zin,
                 "hoop": _mesh(0.0012 * 1000.0 * t_mean, (12, 16), smax=200), "top_rad": (10, 200), "top_hoop": (10, 200),
                 "ao": ao, "ai": ai, "bR": bR, "Mo": Mo_u, "Mi": Mi_u, "qu": qu}
    # foundation ring beam (in the depth of the raft)
    cbr = _circ_beam(1.5 * W_tot / (2 * math.pi * r0), r0, n_col)
    bRm = int(round(bR * 1e3))
    cfb = opt["cover_fbeam_mm"]
    ddr = trm - cfb - 10 - 10
    Mtr = cbr["T"] * (1.0 + tr / bR) / 1.7
    Asr_min = 0.85 * bRm * ddr / fy
    Asr_bot = max(ast_flex(abs(cbr["Ms"]) + Mtr, bRm, ddr, fckf, fy) or 9e9, Asr_min)      # under the columns
    Asr_top = max(ast_flex(abs(cbr["Mm"]) + Mtr, bRm, ddr, fckf, fy) or 9e9, Asr_min)      # at mid-span
    Ver = cbr["V"] + 1.6 * cbr["T"] / bR
    legsr = 4 if bRm >= 600 else 2
    asv_r = max((Ver * 1e3 - mat.tau_c(100.0 * Asr_bot / (bRm * ddr), fckf) * bRm * ddr) / (0.87 * fy * ddr),
                0.4 * bRm / (0.87 * fy))
    svr = int(max(100, min(200, legsr * area(10) / asv_r // 5 * 5)))
    nrt, drt = _bars(Asr_top, (16, 20, 25, 28, 32), nmin=3, width=bRm, cover=cfb)
    nrb, drb = _bars(Asr_bot, (16, 20, 25, 28, 32), nmin=3, width=bRm, cover=cfb)
    M["raft_ring"] = {"b": bRm, "d": trm, "top": (nrt, drt), "bot": (nrb, drb), "stir": (10, min(100, svr), svr),
                      "legs": legsr}
    lev["raft_top"] = -Df + tr
    lev["col_bot"] = lev["raft_top"]
    geo = dict(g)
    geo.update(n_col=n_col, n_pan=C["n_pan"], Lp=C["Lp"], stub=C["stub"], braces=C["braces"], Lc=C["Lc"], Lb=Lb,
               dc=dc, bb=bb, db=db, Ro=Ro, Ri=Ri, tr=tr, te=te, bR=bR, th=th, Hwall=f["Hwall"],
               bal_edge=R + th["twb"] + th["bal_w"])
    stair = _stair(geo, lev, opt, mat, q_all) if opt.get("stair") else None
    M["stair"] = stair
    slosh = C["Ahc"] * Rr * D / 2.0                        # IS 1893 (Part 2):2014 4.11
    if slosh > g["fb"] + 1e-6:
        warn.append(f"sloshing wave {slosh:.2f} m > freeboard {g['fb']:.2f} m (IS 1893 (Part 2) 4.11): the edge of "
                    "the top dome takes the water's pressure - to be checked, or the freeboard raised")
    if C["Lp"] * 1e3 / dc_mm > 12:
        warn.append(f"columns slender (panel {C['Lp']:.2f} m / dia {dc_mm} mm > 12): additional moments of IS 456 39.7 "
                    "not included")
    if f["P3"] > 0:
        warn.append(f"bottom ring beam in net hoop tension {f['P3']:.0f} kN (the dome's thrust exceeds the cone's)")
    res = {"capacity_kl": cap_kl, "staging_m": staging_m, "swd_m": swd_m, "opt": opt, "geo": geo, "levels": lev,
           "members": M, "calc": calc, "warnings": warn, "weights": dict(C["Wt"], Water=W_water), "slosh_m": slosh,
           "mat": {"fck": fck, "fck_found": fckf, "fy": fy, "m": round(mat.m, 2)}}
    _rows(row, res, f, mat, C, cb3, cbr, raft, W_tot, W_live, Mw, Mlev, Mo, tve3)
    res["bbs"] = bbs(res)
    # every intermediate value, for the report-style calculation (intze_calc.py, user request 10-Nov-2026)
    res["x"] = {k: v for k, v in locals().items()
                if k not in ("res", "calc", "row", "warn", "opts") and isinstance(v, (int, float, dict, tuple, list, Mat))}
    return res
