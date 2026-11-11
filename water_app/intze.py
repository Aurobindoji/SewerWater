"""Intze overhead tank (OHT): proportioning and structural design, in the manner of the Intze tanks of the Springfield
(Greenfield) water supply scheme designed by Brookfield Consultants (Prof. S. K. Agarwala): the user's examples of 10-Nov-2026 -
drawings TCP-250510/OPG-1..3 of the 2700 KL tank on 24 m staging of zone 14 (OHT zone 14.pdf)
and pages 12-15 of the design of the 3400 KL tank of zone 10 (design.pdf).

User decisions 10-Nov-2026 (they replace those of 9-Nov-2026: total depth = SWD, full circular raft, working stress
with the no-crack check):
- shape as the example: the depth of water AT THE WALL = CPHEEO Water Manual 2024 Part A Table 2.7 S.No.12 (p175-176)
  maximum side water depth (3 / 4 / 5 m), the cone below it (bottom ring 0.785 of the diameter, cone 44 deg to the
  horizontal), bottom dome rise 0.19 of its diameter, top dome rise 0.15 of its diameter, a 1 m balcony at the top of
  the cone, the wall 200 mm thickening (on its outer face) to its base, the full supply level a freeboard of 0.2 m below the top ring beam;
- sections: steel in the members in contact with water at 130 N/mm2 under the service loads (IS 3370 (Part 2):2009,
  limit state of cracking deemed to be satisfied), no thickness from the tensile stress of the concrete except the
  wall's base; staging, foundation and staircase by the limit state method of IS 456:2000 with a load factor 1.5 on
  all loads, as the report;
- foundation: an ANNULAR raft tapering from the ring beam to 200 mm at its edges, the ring beam under the columns,
  M25 (staircase too), on the NET bearing capacity of the soil (the report: 8 t/m2 at Greenfield) - its area = load /
  capacity, its inner and outer radii such that the centroid of the pressure is on the column circle (zone 14: 4.3 and
  14 m about the 10 m circle), slab moments q a2 / 6 x (1 + D edge / r face) as the report;
- an R.C.C. dog-legged staircase outside the staging on two columns of its own, up to the balcony and on to the roof.

Analysis: membrane theory for the domes and the cone, hoop tension for the wall and the ring beams, IS 3370 (Part 4)
Table 10 (fixed base) for the vertical moment at the wall's base, circular beam on n columns for the bottom ring beam
and the foundation ring beam, IS 1893 (Part 2):2014 two-mass model for the earthquake (equivalent cylinder), IS 875
(Part 3):2015 wind; columns by strain compatibility (IS 456 38.1 / 39), braces as the report (moment at the level /
n x (1 + cos 2 pi / n), M brace = 0.5 Mo (Lc / Lb) sec (pi / n)). What the example shows but no check gives is taken
from it and said so in the calculation ("practice of the example"): the thickness of the domes, their edge zones,
the meridional bars of the cone. The result is a design for a DPR; every drawing says it is to be checked by a
structural engineer before construction.

design(capacity_kl, staging_m, swd_m, opts) -> dict: geometry, levels, members, calc rows, bars (bar bending
schedule) and warnings; intze_dwg.py draws it. Staging = lowest water level above ground = top of the bottom ring
beam.
"""
import math

G = 9.81
GAMMA_W = 10.0          # kN/m3, water (practice)
GAMMA_C = 25.0          # kN/m3, reinforced concrete (IS 875 Part 1)

# IS 456:2000 Table 21 sigma_cbc (for the modular ratio); IS 3370 (Part 2):2009 Table 1 direct tension of concrete
CONC = {20: (7.0, 1.2), 25: (8.5, 1.3), 30: (10.0, 1.5), 35: (11.5, 1.6), 40: (13.0, 1.7)}
TAU_PT = [0.15, 0.25, 0.50, 0.75, 1.00, 1.25, 1.50, 1.75, 2.00, 2.25, 2.50, 2.75, 3.00]
TAU_C = {20: [0.28, 0.36, 0.48, 0.56, 0.62, 0.67, 0.72, 0.75, 0.79, 0.81, 0.82, 0.82, 0.82],     # IS 456 Table 19
         25: [0.29, 0.36, 0.49, 0.57, 0.64, 0.70, 0.74, 0.78, 0.82, 0.85, 0.88, 0.90, 0.92],
         30: [0.29, 0.37, 0.50, 0.59, 0.66, 0.71, 0.76, 0.80, 0.84, 0.88, 0.91, 0.94, 0.96],
         35: [0.29, 0.37, 0.50, 0.59, 0.67, 0.73, 0.78, 0.82, 0.86, 0.90, 0.93, 0.96, 0.99],
         40: [0.30, 0.38, 0.51, 0.60, 0.68, 0.74, 0.79, 0.84, 0.88, 0.92, 0.95, 0.98, 1.01]}
TAU_MAX = {20: 2.8, 25: 3.1, 30: 3.5, 35: 3.7, 40: 4.0}                                         # IS 456 Table 20
ZONE_Z = {"II": 0.10, "III": 0.16, "IV": 0.24, "V": 0.36}          # IS 1893 (Part 1):2016 Table 3
K2_TC2 = [(10, 1.00), (15, 1.05), (20, 1.07), (30, 1.12), (50, 1.20), (100, 1.26)]   # IS 875 (Part 3):2015 Table 2
# IS 3370 (Part 4):1967 Table 10: moment at the base of a cylindrical wall, fixed base, free top, triangular load:
# coefficient of w H3 by H2 / D t
T10 = [(0.4, 0.1205), (0.8, 0.0795), (1.2, 0.0602), (1.6, 0.0505), (2.0, 0.0436), (3.0, 0.0333), (4.0, 0.0268),
       (5.0, 0.0222), (6.0, 0.0187), (8.0, 0.0146), (10.0, 0.0122), (12.0, 0.0104), (14.0, 0.0090), (16.0, 0.0079)]

DEFAULTS = {
    "fck": 30, "fck_found": 25, "fy": 500,     # the example: M30 container and staging, M25 foundation and staircase
    "zone": "III", "sbc_kn_m2": 80.0,          # NET bearing capacity; the report 8 t/m2 (yellow, per OHT, soil test)
    "soil_type": "II",                         # IS 1893 (Part 1) Table 4: I rock / hard, II medium, III soft
    "wind_vb": 47.0,                           # IS 875 (Part 3):2015 Annex A: Springfield 47 m/s
    "R": 2.5, "I": 1.5,                        # IS 1893 (Part 2):2014 Tables 3-4
    "founding_depth_m": 2.7,                   # bottom of the raft below ground (the example: 1.8 + 0.9 m)
    "freeboard_m": 0.20,
    "roof_live_kn_m2": 0.75, "roof_finish_kn_m2": 0.10,     # IS 875 (Part 2) curved roof
    "balcony_w_m": 1.0, "balcony_live_kn_m2": 3.0,
    "cone_deg": 44.0, "D0_ratio": 0.785, "dome2_rise_ratio": 0.19, "dome1_rise_ratio": 0.15,
    "sst_water": 130.0,                        # IS 3370 (Part 2):2009: deemed to satisfy the 0.2 mm crack width
    "panel_max_m": 5.2,                        # braces at most this far apart (the example 5.1 m)
    "col_spacing_m": 3.2,                      # columns on the bottom ring at most this far apart (the example 3.13 m)
    "cover_water_mm": 45, "cover_ring_mm": 50, "cover_mm": 40, "cover_raft_mm": 50, "cover_fbeam_mm": 70,
    "cover_stair_mm": 30,                      # the example's note 4
    "lap_dia": 40, "lap_dia_found": 50,        # the example's note 5
    "stock_m": 12.0,
    "stair": True, "stair_w_m": 1.0, "stair_gap_m": 0.3, "tread_mm": 262, "stair_col_mm": 350,
}

DIAS = (8, 10, 12, 16, 20, 25, 28, 32)


def area(d):
    return math.pi * d * d / 4.0


def kg_per_m(d):
    return d * d / 162.0


def up(x, step):
    return round(math.ceil(round(x / step, 9)) * step, 6)


def _interp(table, x):
    if x <= table[0][0]:
        return table[0][1]
    for (x0, y0), (x1, y1) in zip(table, table[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return table[-1][1]


class Mat:
    def __init__(self, fck, fck_f, fy, sst_w):
        near = lambda v: min(CONC, key=lambda g: abs(g - v))
        self.fck, self.fck_f, self.fy = near(fck), near(fck_f), fy
        self.scbc, self.sct = CONC[self.fck]
        self.m = 280.0 / (3.0 * self.scbc)                    # IS 456 B-1.3 (d)
        self.sst_w = sst_w
        self.E = 5000.0 * math.sqrt(self.fck)                 # IS 456 6.2.3.1, N/mm2
        self.q_lim = 0.133 if fy >= 500 else 0.138            # Mu,lim / fck b d2, IS 456 G-1.1 (c)

    def tau_c(self, pt, fck=None):
        t = TAU_C[fck or self.fck]
        return _interp(list(zip(TAU_PT, t)), max(TAU_PT[0], min(pt, TAU_PT[-1])))


def ast_flex(Mu, b, d, fck, fy):
    """Tension steel (mm2) of a singly reinforced section b x d (mm) for Mu (kNm), IS 456 G-1.1 (b); None beyond it."""
    k = 4.6 * Mu * 1e6 / (fck * b * d * d)
    if k >= 1.0:
        return None
    return 0.5 * fck / fy * (1.0 - math.sqrt(1.0 - k)) * b * d


def _dome(a, rise):
    """Spherical cap of base radius a and the given rise: radius, sin / cos of the semi-angle, angle, area, volume."""
    R = (a * a + rise * rise) / (2.0 * rise)
    s, c = a / R, (R - rise) / R
    th = math.asin(min(1.0, s))
    return {"R": R, "sin": s, "cos": c, "th": th, "area": 2.0 * math.pi * R * rise,
            "vol": math.pi * rise * rise * (3.0 * R - rise) / 3.0}


def _capacity(D, D0, h0, hc, h2):
    """Water held between the LWL (top of the bottom ring beam) and the FSL, m3."""
    cyl = math.pi / 4.0 * D * D * hc
    cone = math.pi * h0 / 12.0 * (D * D + D * D0 + D0 * D0)
    return cyl + cone - _dome(D0 / 2.0, h2)["vol"]


def _mesh(As_req, dias=(10, 12, 16, 20, 25), smax=200, smin=90):
    """Bars (dia, spacing) giving at least As_req mm2 per m: the smallest dia whose spacing is not below smin."""
    for d in dias:
        s = smax if As_req <= 0 else min(smax, int(1000.0 * area(d) / As_req // 5 * 5))
        if s >= smin:
            return d, s
    return dias[-1], smin


def _bars(As_req, dias=(12, 16, 20, 25, 28, 32), nmin=2, width=None, cover=40, even=False, cc_min=None):
    """Number and dia of bars giving at least As_req mm2: the smallest dia whose bars fit in one layer of the width
    (clear gap >= max(dia, 25 mm), IS 456 26.3.2; or centres at least cc_min apart), else the largest dia."""
    last = None
    for d in dias:
        n = max(nmin, math.ceil(As_req / area(d) - 1e-9))
        if even and n % 2:
            n += 1
        last = (n, d)
        if width is None:
            if n <= 8:
                return last
            continue
        fit = int(width // cc_min) if cc_min else int((width - 2 * cover - 20 + max(d, 25)) // (d + max(d, 25)))
        if n <= max(nmin, fit):
            return last
    return last


def _ring_section(As_req, bmin, dmin, cover):
    """A ring beam in hoop tension: its bars round the section (centres >= 75 mm) and the smallest b x d (mm) that
    holds them: (b, d, n, dia)."""
    best = None
    for dia in (12, 16, 20):
        n = max(4, math.ceil(As_req / area(dia) - 1e-9))
        n += n % 2
        need = n * max(75.0, 2.5 * dia + 25.0)
        for b in (bmin, bmin + 50, bmin + 100, bmin + 150, bmin + 250, bmin + 350):
            d = dmin
            while 2 * (b + d) - 8 * cover < need and d < 2.5 * b:
                d += 50
            if 2 * (b + d) - 8 * cover >= need and (best is None or (b * d, n) < (best[0] * best[1], best[2])):
                best = (b, d, n, dia)
    return best or (bmin + 350, int(2.5 * (bmin + 350)), n, 20)


def _circ_beam(w, R, n):
    """Circular beam of radius R on n equal supports, load w per m: support / mid-span moments, the largest torsion,
    its angle from the support and the shear at the support (kN, m). Positive moment = sagging."""
    th = math.pi / n
    Ms = w * R * R * (th / math.tan(th) - 1.0)
    Mm = w * R * R * (th / math.sin(th) - 1.0)
    phi = math.acos(math.sin(th) / th)                   # from mid-span, where dT / dphi = 0
    T = w * R * R * (th * math.sin(phi) / math.sin(th) - phi)
    return {"Ms": Ms, "Mm": Mm, "T": T, "phi_deg": math.degrees(th - phi), "V": w * R * th}


def proportion(cap_kl, swd_m, opt):
    """The container for the capacity: the depth of water at the wall = swd, the cone below (see the module text)."""
    hc = float(opt.get("cyl_depth_m") or swd_m)
    tana = math.tan(math.radians(opt["cone_deg"]))

    def shape(D):
        D0 = round(opt["D0_ratio"] * D / 0.05) * 0.05
        return D0, round((D - D0) / 2.0 * tana, 3), up(opt["dome2_rise_ratio"] * D0, 0.05)

    def cap(D):
        D0, h0, h2 = shape(D)
        return _capacity(D, D0, h0, hc, h2)
    if opt.get("D_m"):
        D = float(opt["D_m"])
    else:
        lo, hi = 2.0, 80.0
        for _ in range(60):
            mid = (lo + hi) / 2.0
            if cap(mid) < cap_kl:
                lo = mid
            else:
                hi = mid
        D = up(hi, 0.05)
        while cap(D) < cap_kl:
            D = round(D + 0.05, 2)
    D0, h0, h2 = shape(D)
    alpha = math.radians(opt["cone_deg"])
    return {"D": D, "R": D / 2.0, "D0": D0, "r0": D0 / 2.0, "hc": hc, "h0": h0, "H": hc + h0, "h2": h2,
            "h1": up(opt["dome1_rise_ratio"] * D, 0.05), "alpha": alpha, "fb": opt["freeboard_m"],
            "slant": h0 / math.sin(alpha)}


def cone_depth(cap_kl, swd_m, opts=None):
    """Height of the cone below the wall of a new Intze OHT of this capacity (m): its depth of water from the LWL is
    swd + this (user decision 10-Nov-2026: SWD at the wall, the cone below - the pump head of the DPR uses both)."""
    opt = dict(DEFAULTS)
    opt.update({k: v for k, v in (opts or {}).items() if v not in (None, "")})
    return proportion(float(cap_kl), float(swd_m), opt)["h0"]


def _forces(g, th, opt):
    """Membrane forces of the container for the sizes th (m): per m of circumference unless said."""
    R, r0, H, a = g["R"], g["r0"], g["H"], g["alpha"]
    sa, ca, ta = math.sin(a), math.cos(a), math.tan(a)
    f = {}
    d1 = _dome(R, g["h1"])
    w1 = GAMMA_C * th["t1"] + opt["roof_live_kn_m2"] + opt["roof_finish_kn_m2"]
    T1 = w1 * d1["R"] / (1.0 + d1["cos"])
    f.update(dome1=d1, w1=w1, T1=T1, H1=T1 * d1["cos"], V1=T1 * d1["sin"], hoop1_crown=w1 * d1["R"] / 2.0,
             P1=T1 * d1["cos"] * R)
    Hw = g["hc"] + g["fb"] - th["bal_t"]                   # the wall, from the balcony's top to the top ring beam
    f["Hwall"] = Hw
    f["A_wall"] = th["tw"] * Hw + (th["twb"] - th["tw"]) * min(th["taper"], Hw) / 2.0
    W2 = (f["V1"] + GAMMA_C * (th["b1"] * th["d1"] + f["A_wall"] + (th["twb"] + th["bal_w"]) * th["bal_t"])
          + opt["balcony_live_kn_m2"] * th["bal_w"])
    f["W2"] = W2
    f["P2"] = (W2 / ta + GAMMA_W * max(0.0, g["hc"] - th["bal_t"] / 2.0) * th["bal_t"]) * R
    q0 = GAMMA_C * th["t0"]

    def cone_at(r):
        water = 2.0 * math.pi * (H * (R * R - r * r) / 2.0 - ta * ((R ** 3 - r ** 3) / 3.0 - r0 * (R * R - r * r) / 2.0))
        V = W2 * 2.0 * math.pi * R + GAMMA_W * water + q0 * math.pi * (R + r) * (R - r) / ca
        p = GAMMA_W * (H - (r - r0) * ta)
        return {"r": r, "Nphi": V / (2.0 * math.pi * r * sa), "Nth": (p + q0 * ca) * r / sa, "p": p, "V": V}
    f["cone"] = [cone_at(r0 + (R - r0) * i / 4.0) for i in range(5)]
    d2 = _dome(r0, g["h2"])
    Wd = GAMMA_W * (math.pi * r0 * r0 * H - d2["vol"]) + GAMMA_C * th["t2"] * d2["area"]
    T2 = Wd / (2.0 * math.pi * r0 * d2["sin"])
    f.update(dome2=d2, Wd=Wd, T2=T2, hoop2_crown=(GAMMA_W * (H - g["h2"]) + GAMMA_C * th["t2"]) * d2["R"] / 2.0)
    Nc = f["cone"][0]["Nphi"]
    f["H3"] = T2 * d2["cos"] - Nc * ca          # outward (+) on the bottom ring beam
    f["P3"] = f["H3"] * r0                      # hoop: + tension
    f["w3"] = Nc * sa + T2 * d2["sin"] + GAMMA_C * th["b3"] * th["d3"]
    return f


def _kz(z):
    return _interp(K2_TC2, max(z, 10.0))


def _sa_g(T, soil, damping5=True):
    """IS 1893 (Part 1):2016 6.4.2 for 5 % damping; x 1.75 for 0.5 % (IS 1893 Part 2, convective)."""
    corner = {"I": 0.40, "II": 0.55, "III": 0.67}[soil]
    c = {"I": 1.00, "II": 1.36, "III": 1.67}[soil]
    if T < 0.1:
        sa = 1.0 + 15.0 * T
    elif T <= corner:
        sa = 2.5
    elif T <= 4.0:
        sa = c / T
    else:
        sa = c / 4.0
    return sa * (1.0 if damping5 else 1.75)


# ------------------------------------------------------------------------------------------ circular column, IS 456
def _steel_stress(eps, fy):
    """Design stress of a cold-worked bar at the strain eps (IS 456 Fig. 23 / SP 16 Table A), N/mm2, signed."""
    Es, fyd, e = 2.0e5, 0.87 * fy, abs(eps)
    pts = [(0.0, 0.0), (0.8 * fyd / Es, 0.8 * fyd)] + [(k * fyd / Es + ine, k * fyd) for k, ine in
                                                       ((0.85, 0.0001), (0.90, 0.0003), (0.95, 0.0007),
                                                        (0.975, 0.0010), (1.0, 0.0020))]
    return math.copysign(_interp(pts, e), eps)


def col_curve(D, n, dia, c_centre, fck, fy, strips=40):
    """Interaction curve [(Pu kN, Mu kNm)] of a circular column D (mm) with n bars at c_centre from the face, by
    strain compatibility (IS 456 38.1, 39.1): the neutral axis from near the compressed face to far outside."""
    R = D / 2.0
    ys = [R - (R - c_centre) * math.cos(2.0 * math.pi * (i + 0.5) / n) for i in range(n)]   # from the compressed face
    As = area(dia)
    out = []
    for k in range(1, 140):
        xu = D * (0.03 * k if k <= 40 else 1.2 + 0.08 * (k - 40) ** 1.6)
        if xu <= D:
            strain = lambda y: 0.0035 * (xu - y) / xu
        else:
            strain = lambda y: 0.002 * (xu - y) / (xu - 3.0 * D / 7.0)

        def fc(e):
            if e <= 0:
                return 0.0
            return 0.446 * fck * (1.0 if e >= 0.002 else 2.0 * e / 0.002 - (e / 0.002) ** 2)
        P = M = 0.0
        for i in range(strips):
            y = (i + 0.5) * D / strips
            s = fc(strain(y))
            if s:
                dA = 2.0 * math.sqrt(max(0.0, R * R - (R - y) ** 2)) * D / strips
                P += s * dA
                M += s * dA * (R - y)
        for y in ys:
            e = strain(y)
            s = _steel_stress(e, fy) - fc(e)
            P += s * As
            M += s * As * (R - y)
        out.append((P / 1e3, M / 1e6))
    return out


def col_moment(curve, Pu):
    """Mu the column takes with Pu (from its interaction curve); None when Pu is beyond the curve."""
    for (p0, m0), (p1, m1) in zip(curve, curve[1:]):
        if (p0 - Pu) * (p1 - Pu) <= 0 and p1 != p0:
            return m0 + (m1 - m0) * (Pu - p0) / (p1 - p0)
    return None


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
        As1 = f["P1"] * 1e3 / sst
        b1, d1, n1, dia1 = _ring_section(As1, 250, 200, cw)
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
    M["top_ring"] = {"b": b1, "d": d1, "n": n1, "dia": dia1, "stir": (8, 200), "P": f["P1"]}
    # wall: hoops by zones of about 1 m from its top, both faces
    Hw = f["Hwall"]
    nz = max(1, int(round(Hw / 1.0)))
    zl = Hw / nz
    zones = []
    for i in range(nz):
        bot = (i + 1) * zl
        T = GAMMA_W * max(0.0, bot - g["fb"]) * R
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

        for tr_mm in range(300, 3050, 50):
            d0 = tr_mm - covr - 12
            if max(Mo_u, Mi_u) * 1e6 > mat.q_lim * fckf * 1000.0 * d0 * d0:
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
    # the staircase's column and its footing
    per_level = 2.0 * (R_fl + R_land) * 0.75 + self_ * (L1 / 2.0 + lc)
    H_col = roof + float(opt["founding_depth_m"]) - 0.6
    P = math.ceil(len(levels) / 2.0) * per_level + GAMMA_C * area(ds) * H_col
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
            "bal": bal, "roof": roof}


def _rows(r, res, f, mat, C, cb3, cbr, raft, W_tot, W_live, Mw, Mlev, Mo, tve3):
    g, th, M, opt, lev = res["geo"], res["geo"]["th"], res["members"], res["opt"], res["levels"]
    n = g["n_col"]
    b = lambda m: "%d @ %d" % (m[0], m[1])
    s = "1 Data"
    r(s, "Capacity required", res["capacity_kl"], "KL", "water design (OHT capacity of the OZ)")
    r(s, "Staging (LWL above ground)", res["staging_m"], "m", "water design")
    r(s, "Depth of water at the wall", g["hc"], "m", "CPHEEO Water Manual 2024 Part A Table 2.7 S.No.12 p175-176: maximum side water depth")
    r(s, "Concrete: container and staging / foundation and staircase", f"M{mat.fck} / M{mat.fck_f}", "", "the example's note 2; IS 3370 (Part 1):2009 M30 minimum")
    r(s, "Steel", f"Fe{mat.fy}", "", "IS 1786")
    r(s, "Steel stress in the members in contact with water", mat.sst_w, "N/mm2", "IS 3370 (Part 2):2009: crack width deemed satisfied (user 10-Nov-2026)")
    r(s, "Load factor (staging, foundation, staircase)", 1.5, "", "IS 456:2000 Table 18, on all the loads as the report")
    r(s, "Seismic zone / Z / I / R", f"{opt['zone']} / {ZONE_Z[opt['zone']]} / {opt['I']} / {opt['R']}", "", "IS 1893 (Part 1):2016 Table 3; IS 1893 (Part 2):2014 Tables 3-4")
    r(s, "Net bearing capacity of the soil / soil type", f"{opt['sbc_kn_m2']:g} / {opt['soil_type']}", "kN/m2", "input, to be confirmed by a soil test (the report: 8 t/m2)")
    r(s, "Basic wind speed", opt["wind_vb"], "m/s", "IS 875 (Part 3):2015 Annex A")
    s = "2 Geometry"
    r(s, "Internal diameter D", round(g["D"], 2), "m", "found for the capacity")
    r(s, "Diameter of the bottom ring (column circle) D0", round(g["D0"], 2), "m", f"{opt['D0_ratio']} D (the example 20.0 / 25.47)")
    r(s, "Height of the cone", round(g["h0"], 3), "m", f"{opt['cone_deg']:g} deg to the horizontal (the example)")
    r(s, "Depth of water: wall + cone", f"{g['hc']:.2f} + {g['h0']:.2f} = {g['H']:.2f}", "m", "")
    r(s, "Rise of the bottom dome / its radius", f"{g['h2']:.2f} / {f['dome2']['R']:.3f}", "m", f"{opt['dome2_rise_ratio']} D0 (the example 3.8 / 14.958)")
    r(s, "Rise of the top dome / its radius", f"{g['h1']:.2f} / {f['dome1']['R']:.3f}", "m", f"{opt['dome1_rise_ratio']} D (the example 3.8 / 23.24)")
    r(s, "Freeboard", g["fb"], "m", "FSL below the top ring beam")
    r(s, "Capacity provided", round(g["cap"], 1), "m3", "cylinder + cone - bottom dome")
    for k in ("raft_bot", "raft_top", "GL", "B3_bot", "LWL", "dome2_crown", "cone_top", "B2_top", "FSL", "wall_top", "B1_top", "dome1_crown"):
        r(s, f"Level: {k}", round(lev[k], 3), "m", "above ground")
    s = "3 Top dome"
    r(s, "Thickness / at the edge", f"{M['top_dome']['t']} / {M['top_dome']['te']}", "mm", "practice of the example (100 / 120 over 1.4 m)")
    r(s, "Load (self + live + finish)", round(f["w1"], 2), "kN/m2", "IS 875 (Part 2)")
    r(s, "Meridional thrust at the edge", round(f["T1"], 2), "kN/m", "w R / (1 + cos theta)")
    r(s, "Compressive stress: meridional / hoop at the crown", f"{f['T1'] / (th['t1'] * 1e3):.2f} / {f['hoop1_crown'] / (th['t1'] * 1e3):.2f}", "N/mm2", "")
    r(s, "Bars both ways", b(M["top_dome"]["rad"]), "mm", "0.24 %, at most 200 apart (IS 3370 (Part 2) 8.1)")
    r(s, "Edge zone: radial at top / hoops", f"{b(M['top_dome']['edge_rad'])} / {b(M['top_dome']['edge_hoop'])}", "mm", "practice of the example")
    s = "4 Top ring beam"
    r(s, "Hoop tension", round(f["P1"], 1), "kN", "T1 cos theta x D / 2")
    r(s, "Steel", round(f["P1"] * 1e3 / mat.sst_w), "mm2", f"P / {mat.sst_w:g}")
    r(s, "Size / hoop bars", f"{M['top_ring']['b']} x {M['top_ring']['d']} / {M['top_ring']['n']}-{M['top_ring']['dia']}", "mm", "the section that holds the bars")
    s = "5 Cylindrical wall"
    r(s, "Thickness: top / base", f"{M['wall']['t']} / {M['wall']['tb']}", "mm", f"base: direct tension of the uncracked section <= {mat.sct} N/mm2 (IS 3370 (Part 2) Table 1); on the outer face over the lowest {M['wall']['taper']:g} m")
    for z in M["wall"]["zones"]:
        r(s, f"Hoops {z['top']:.2f} - {z['top'] + z['len']:.2f} m below the top: tension / steel", f"{z['T']:.0f} / {z['As']:.0f}", "kN/m / mm2/m",
          f"{z['n']} nos {z['dia']} @ {z['sp']} on each face")
    r(s, "H2 / D t", round(M["wall"]["K"], 2), "", "IS 3370 (Part 4) Table 10")
    r(s, "Vertical moment at the base", round(Mw, 1), "kNm/m", "base taken as fixed; tension on the water face")
    r(s, "Vertical bars: water face at the base / elsewhere", f"{b(M['wall']['base_in'])} / {b(M['wall']['vert'])}", "mm", f"M / ({mat.sst_w:g} x 0.87 d); 0.24 %")
    s = "6 Balcony ring"
    r(s, "Vertical load on the cone's top", round(f["W2"], 1), "kN/m", "roof + top ring + wall + balcony")
    r(s, "Hoop tension", round(f["P2"], 1), "kN", "(W cot alpha + water on the ring) x D / 2")
    r(s, "Section / hoop bars", f"{(th['twb'] + th['bal_w']) * 1e3:.0f} x {M['balcony']['t']} / {M['balcony']['n']}-{M['balcony']['dia']}", "mm", f"P / {mat.sst_w:g} (the example 21-20)")
    r(s, "Balcony: radial bars at top", b(M["balcony"]["rad"]), "mm", "cantilever 1 m, 3 kN/m2")
    s = "7 Conical dome"
    for c in f["cone"]:
        r(s, f"At r = {c['r']:.2f} m: meridional thrust / hoop tension", f"{c['Nphi']:.0f} / {c['Nth']:.0f}", "kN/m", "V / (2 pi r sin a); (p + q cos a) r / sin a")
    r(s, "Thickness", M["cone"]["t"], "mm", "hoop steel at most 2.25 % of the section (the example 390)")
    r(s, "Hoops on each face: lower half / upper half", f"{M['cone']['n_low']} nos {b(M['cone']['hoop_low'])} / {M['cone']['n_up']} nos {b(M['cone']['hoop_up'])}", "mm", f"N / {mat.sst_w:g}, half on each face")
    r(s, "Meridional bars on each face", b(M["cone"]["mer"]), "mm", "0.3 % each face - practice of the example (the junction moments not analysed)")
    s = "8 Bottom dome"
    r(s, "Thickness / at the edge", f"{M['bottom_dome']['t']} / {M['bottom_dome']['te']}", "mm", "practice of the example (200 / 350 over 1.4 m)")
    r(s, "Load (water + self)", round(f["Wd"], 0), "kN", "")
    r(s, "Meridional thrust at the edge / stress", f"{f['T2']:.0f} / {f['T2'] / (th['t2'] * 1e3):.2f}", "kN/m / N/mm2", "W / (pi D0 sin theta)")
    r(s, "Bars both ways on each face", b(M["bottom_dome"]["rad"]), "mm", "0.24 %")
    r(s, "Edge zone: radial at top / hoops", f"{b(M['bottom_dome']['edge_rad'])} / {b(M['bottom_dome']['edge_hoop'])}", "mm", "practice of the example")
    s = "9 Bottom ring beam"
    r(s, "Horizontal thrust: dome out / cone in", f"{f['T2'] * f['dome2']['cos']:.0f} / {f['cone'][0]['Nphi'] * math.cos(g['alpha']):.0f}", "kN/m", "")
    r(s, "Net hoop force (+ tension)", round(f["P3"], 0), "kN", "")
    r(s, "Vertical load", round(f["w3"], 1), "kN/m", "")
    r(s, "Moment at a column / at mid-span (service)", f"{cb3['Ms']:.1f} / {cb3['Mm']:.1f}", "kNm", "w R2 (t cot t - 1); w R2 (t / sin t - 1), t = pi / n")
    r(s, "Largest torsion / shear at a column", f"{cb3['T']:.1f} / {cb3['V']:.1f}", "kNm / kN", f"at {cb3['phi_deg']:.1f} deg from a column")
    bm = M["bottom_ring"]
    r(s, "Size", f"{bm['b']} x {bm['d']}", "mm", "width of the column, depth 1.5 x width or by Mu,lim")
    r(s, "Top / bottom hoop bars", f"{bm['top'][0]}-{bm['top'][1]} / {bm['bot'][0]}-{bm['bot'][1]}", "", "1.5 M + torsion (IS 456 41.4.2)")
    r(s, "Equivalent shear stress", round(tve3, 2), "N/mm2", f"<= {TAU_MAX[mat.fck]} (IS 456 Table 20)")
    r(s, "Stirrups", f"{bm['legs']}-legged 10 @ {bm['stir'][1]} near the columns, @ {bm['stir'][2]} between", "mm", "IS 456 41.4.3")
    s = "10 Weights"
    for k, v in C["Wt"].items():
        r(s, k, round(v, 0), "kN", "")
    r(s, "Container (empty)", round(C["W_cont"], 0), "kN", "")
    r(s, "Water", round(res["weights"]["Water"], 0), "kN", "")
    r(s, "Live load: roof and balcony", round(W_live, 0), "kN", "")
    r(s, "Columns / braces", f"{C['W_col']:.0f} / {C['W_br']:.0f}", "kN", "")
    r(s, "Total at the base of the columns, tank full", round(W_tot, 0), "kN", "")
    s = "11 Lateral loads"
    r(s, "Equivalent cylinder h / D", f"{C['h_eq']:.2f} / {g['D']:.2f}", "m", "IS 1893 (Part 2):2014 4.2.1")
    r(s, "Impulsive / convective weight", f"{C['mi'] * G:.0f} / {C['mc'] * G:.0f}", "kN", "")
    r(s, "Structure (container + 1/3 staging)", round(C["ms"] * G, 0), "kN", "4.3.1.2")
    r(s, "Lateral stiffness of the staging", round(C["Ks"], 0), "kN/m", f"n x 12 E I / h3 x {C['afac']:.2f} (the braces' restraint), panels in series")
    r(s, "Ti / Tc", f"{C['Ti']:.2f} / {C['Tc']:.2f}", "s", "")
    r(s, "(Ah)i / (Ah)c", f"{C['Ahi']:.4f} / {C['Ahc']:.4f}", "", "Z/2 x I/R x Sa/g (convective 0.5 % damping)")
    r(s, "Earthquake, tank full: base shear / moment", f"{C['Vq']:.0f} / {C['Mq']:.0f}", "kN / kNm", "impulsive and convective by SRSS")
    r(s, "Earthquake, tank empty: base shear / moment", f"{C['Ve']:.0f} / {C['Me']:.0f}", "kN / kNm", "")
    r(s, "Wind: pressure at the top / shear / moment", f"{C['pd_top']:.2f} / {C['Vw']:.0f} / {C['Mw']:.0f}", "kN/m2 / kN / kNm", "0.6 Vz2 x Kd Ka Kc; Cf container 0.7, columns 1.2, braces 2.0")
    r(s, "Sloshing wave", round(res["slosh_m"], 2), "m", f"IS 1893 (Part 2) 4.11; freeboard {g['fb']:.2f} m")
    s = "12 Columns"
    r(s, "Number / diameter", f"{n} / {M['column']['d']}", "nos / mm", f"at most {opt['col_spacing_m']:g} m apart on the {g['D0']:.2f} m circle")
    r(s, "Braces / panel height", f"{len(C['braces'])} / {C['Lp']:.2f}", "nos / m", f"at most {opt['panel_max_m']:g} m apart, the lowest at the ground")
    r(s, "Axial load, tank full / empty (service)", f"{C['P_full']:.0f} / {C['P_empty']:.0f}", "kN", "")
    for name, Pu, Mu in C["cases"]:
        r(s, name, f"Pu {Pu:.0f}, Mu {max(Mu, abs(Pu) * C['emin']):.0f}", "kN, kNm", "1.5 x; axial 2 M / (n r), moment V h / n; minimum eccentricity IS 456 25.4")
    r(s, "Bars", f"{M['column']['n']}-{M['column']['dia']} ({M['column']['pt']:.2f} %)", "", f"interaction by strain compatibility, used {C['util']:.2f}")
    r(s, "Rings", f"8 @ 200, 8 @ 100 over {M['column']['conf_len']} at each joint", "mm", "the example; IS 13920:2016 7.6")
    s = "13 Braces"
    r(s, "Moment at a brace level", round(Mlev, 0), "kNm", "shear x panel height (the report)")
    r(s, "Mo", round(Mo, 1), "kNm", "M / n x (1 + cos 2 pi / n)")
    r(s, "Moment / shear of a brace", f"{M['brace']['Mb']:.1f} / {M['brace']['Fb']:.1f}", "kNm / kN", "0.5 Mo (Lc / Lb) sec (pi / n); 2 Mb / Lc")
    r(s, "Size / bars on each face", f"{M['brace']['b']} x {M['brace']['d']} / {M['brace']['top'][0]}-{M['brace']['top'][1]}", "mm", "Ast = Asc = 1.5 M / (0.87 fy x lever arm)")
    r(s, "Stirrups", f"8 @ 100 at the ends, @ {M['brace']['stir'][2]} between", "mm", "")
    s = "14 Foundation"
    rf = M["raft"]
    r(s, "Annular raft: outer / inner radius", f"{rf['Ro']:.2f} / {rf['Ri']:.2f}", "m", "area = load / net capacity, centroid of the pressure on the column circle")
    r(s, "Net pressure: gravity / with the lateral load", f"{raft['q_g']:.1f} / {raft['q_max']:.1f}", "kN/m2", f"<= {opt['sbc_kn_m2']:g} / 1.25 x (IS 1893 (Part 1) Table 1)")
    r(s, "Least pressure, tank empty with the lateral load", round(raft["q_min"], 1), "kN/m2", ">= 0, no uplift")
    r(s, "Projection: outer / inner", f"{rf['ao']:.2f} / {rf['ai']:.2f}", "m", f"beyond the ring beam {rf['bR'] * 1e3:.0f} wide")
    r(s, "Factored moment: outer / inner", f"{rf['Mo']:.0f} / {rf['Mi']:.0f}", "kNm/m", "q a2 / 6 x (1 + D edge / r face), the report")
    r(s, "Thickness at the beam / at the edges", f"{rf['t']} / {rf['te']}", "mm", "Mu,lim and the shear at d from the beam (IS 456 Table 19)")
    r(s, "Radial bars at the bottom", f"{rf['rad'][0]}-{rf['rad'][1]} @ {rf['rad_sp']} on the column circle", "mm", "1.5 M / (0.87 fy 0.9 d) (IS 456 G-1.1)")
    r(s, "Inner projection: lengths and bars", "; ".join(f"{L:.2f} m {k} nos" for L, k in rf["zones_in"]), "", "half the bars stop where the moment allows")
    r(s, "Hoops at the bottom / top mesh", f"{b(rf['hoop'])} / {b(rf['top_rad'])} radial, {b(rf['top_hoop'])} hoops", "mm", "0.12 %; top as the example")
    rr = M["raft_ring"]
    r(s, "Ring beam: factored moment at a column / mid-span, shear", f"{cbr['Ms']:.0f} / {cbr['Mm']:.0f}, {cbr['V']:.0f}", "kNm, kN", "inverted circular beam under 1.5 x load")
    r(s, "Ring beam: size / bottom / top hoops", f"{rr['b']} x {rr['d']} / {rr['bot'][0]}-{rr['bot'][1]} / {rr['top'][0]}-{rr['top'][1]}", "mm", "")
    r(s, "Ring beam: stirrups", f"{rr['legs']}-legged 10 @ {rr['stir'][1]} near the columns, @ {rr['stir'][2]} between", "mm", "")
    st = M.get("stair")
    if st:
        s = "15 Staircase"
        r(s, "Flights to the balcony / on to the roof", f"{st['n1']} / {st['n2']}", "nos", f"balcony {st['bal']:.3f} m, roof {st['roof']:.3f} m")
        r(s, "Treads / risers in a flight", f"{st['treads']} x {st['tread'] * 1e3:.0f} / {st['risers']} x {st['riser1'] * 1e3:.0f} ({st['riser2'] * 1e3:.0f} above the balcony)", "mm", "the report 11 x 262 / 12 x 180")
        r(s, "Waist slab / span / factored load", f"{st['waist']} / {st['Lb']:.2f} / {st['wu']:.1f}", "mm / m / kN/m2", "live load 3 kN/m2")
        r(s, "Moment / main bars / distribution", f"{st['Mu']:.1f} / {b(st['main'])} / {b(st['dist'])}", "kNm/m / mm", "w L2 / 8")
        r(s, "Landing beam: size / span / bars top and bottom", f"{st['beam']['b']} x {st['beam']['d']} / {st['L1']:.2f} / {st['beam']['top'][0]}-{st['beam']['top'][1]}", "mm / m", f"Mu {st['beam']['Mu']:.0f} kNm; stirrups 8 @ 150")
        r(s, "Staircase column (2 nos): dia / bars / load", f"{st['col']['d']} / {st['col']['n']}-{st['col']['dia']} / {st['col']['P']:.0f}", "mm / kN", f"1.5 P <= {st['col']['Pcap']:.0f} kN (IS 456 39.3)")
        r(s, "Footing of each", f"{st['footing']['side']:.1f} x {st['footing']['side']:.1f} m, {st['footing']['t']} to {st['footing']['te']} mm, {b(st['footing']['bars'])} both ways", "", "on the net bearing capacity")


# ---------------------------------------------------------------------------------------------- bar bending schedule
def bbs(res):
    """Bar bending schedule rows: member, mark, description, dia, number, length m, shape."""
    g, M, _lev, opt = res["geo"], res["members"], res["levels"], res["opt"]
    th = g["th"]
    R, r0, D = g["R"], g["r0"], g["D"]
    stock = opt["stock_m"]
    rows = []

    def add(member, mark, desc, dia, num, length, shape="straight"):
        num = int(math.ceil(num - 1e-9))
        rows.append({"member": member, "mark": mark, "desc": desc, "dia": dia, "no": num, "length": round(length, 3),
                     "shape": shape, "total_m": round(num * length, 2), "kg": round(num * length * kg_per_m(dia), 2)})

    def ring(circ, dia, lap=opt["lap_dia"]):
        return circ + math.ceil(circ / stock) * lap * dia / 1000.0

    def lapped(L, dia, lap=opt["lap_dia"]):
        return L + max(0, math.ceil(L / stock) - 1) * lap * dia / 1000.0

    def dome(name, mk, a, rise, m, faces):
        d = _dome(a, rise)
        arc = d["R"] * d["th"]
        for face in faces:
            fl = f" {face} face" if face else ""
            k = face[:1] if face else ""
            dr, sr = m["rad"]
            n = math.ceil(2 * math.pi * a * 1000 / sr)
            add(name, f"{mk}1{k}", f"radial{fl}, edge to crown ({sr} c/c at the edge)", dr, n / 2, lapped(arc + 0.3, dr), "curved")
            add(name, f"{mk}2{k}", f"radial{fl}, alternate, stop half way", dr, n - n // 2, arc / 2.0 + 0.3, "curved")
            dh, sh = m["hoop"]
            add(name, f"{mk}3{k}", f"hoops{fl} @ {sh} (mean dia {a:.2f} m)", dh, arc * 1000 / sh, ring(math.pi * a, dh), "ring")
        de, se = m["edge_rad"]
        add(name, f"{mk}4", f"edge zone {m['edge']:g} m: radial at top @ {se}", de, 2 * math.pi * a * 1000 / se, m["edge"] + 0.45, "bent")
        de, se = m["edge_hoop"]
        add(name, f"{mk}5", f"edge zone: hoops @ {se}", de, m["edge"] * 1000 / se, ring(2 * math.pi * (a - m["edge"] / 2.0), de), "ring")

    dome("Top dome", "TD", R, g["h1"], M["top_dome"], ("",))
    tr_ = M["top_ring"]
    c1 = 2 * math.pi * (R + th["tw"] / 2.0)
    add("Top ring beam", "B1-1", "hoop bars", tr_["dia"], tr_["n"], ring(c1, tr_["dia"]), "ring")
    add("Top ring beam", "B1-2", "stirrups 8 @ 200", 8, c1 / 0.2, 2 * (tr_["b"] + tr_["d"] - 4 * opt["cover_water_mm"]) / 1e3 + 0.2, "closed stirrup")
    w = M["wall"]
    for i, z in enumerate(w["zones"], 1):
        for face, dd in (("inner", D + 0.1), ("outer", D + 2 * th["tw"] - 0.1)):
            add("Cylindrical wall", f"W{i}{face[0]}", f"hoops {face} face, {z['top']:.2f}-{z['top'] + z['len']:.2f} m below the top @ {z['sp']}",
                z["dia"], z["n"], ring(math.pi * dd, z["dia"]), "ring")
    dv, sv = w["vert"]
    for face, dd in (("inner", D + 0.1), ("outer", D + 2 * th["tw"] - 0.1)):
        add("Cylindrical wall", f"WV{face[0]}", f"vertical {face} face @ {sv}", dv, math.pi * dd * 1000 / sv,
            lapped(g["Hwall"] + th["d1"] + th["bal_t"] - 0.1 + 0.3, dv), "L")
    dv, sv = w["base_in"]
    add("Cylindrical wall", "WB", f"vertical at the base, water face @ {sv}", dv, math.pi * D * 1000 / sv,
        w["base_len"] + th["bal_t"] + 40 * dv / 1e3, "L")
    bl = M["balcony"]
    add("Balcony ring", "BL1", "hoop bars", bl["dia"], bl["n"], ring(2 * math.pi * (R + (th["twb"] + bl["w"]) / 2.0), bl["dia"]), "ring")
    add("Balcony ring", "BL2", f"radial at top @ {bl['rad'][1]}", bl["rad"][0], 2 * math.pi * (R + th["twb"]) * 1000 / bl["rad"][1],
        bl["w"] + th["twb"] + 0.6, "L")
    add("Balcony ring", "BL3", f"radial at bottom @ {bl['dist'][1]}", bl["dist"][0], 2 * math.pi * (R + th["twb"]) * 1000 / bl["dist"][1],
        bl["w"] + 0.5, "straight")
    c = M["cone"]
    L = g["slant"]
    for face in ("inner", "outer"):
        add("Conical dome", f"C1{face[0]}", f"hoops {face} face, lower half @ {c['hoop_low'][1]}", c["hoop_low"][0], c["n_low"],
            ring(math.pi * (3 * r0 + R) / 2, c["hoop_low"][0]), "ring")
        add("Conical dome", f"C2{face[0]}", f"hoops {face} face, upper half @ {c['hoop_up'][1]}", c["hoop_up"][0], c["n_up"],
            ring(math.pi * (r0 + 3 * R) / 2, c["hoop_up"][0]), "ring")
        add("Conical dome", f"C3{face[0]}", f"meridional {face} face @ {c['mer'][1]} at mid height", c["mer"][0],
            math.pi * (R + r0) * 1000 / c["mer"][1], L + 2 * opt["lap_dia"] * c["mer"][0] / 1e3, "bent")
    dome("Bottom dome", "BD", r0, g["h2"], M["bottom_dome"], ("top", "bottom"))
    br = M["bottom_ring"]
    c3 = 2 * math.pi * r0
    add("Bottom ring beam", "B3-1", "top hoop bars", br["top"][1], br["top"][0], ring(c3, br["top"][1]), "ring")
    add("Bottom ring beam", "B3-2", "bottom hoop bars", br["bot"][1], br["bot"][0], ring(c3, br["bot"][1]), "ring")
    if br["side"][0]:
        add("Bottom ring beam", "B3-3", "side face bars", br["side"][1], 2 * br["side"][0], ring(c3, br["side"][1]), "ring")
    per = 2 * (br["b"] + br["d"] - 4 * opt["cover_ring_mm"]) / 1e3 + 0.24
    add("Bottom ring beam", "B3-4", f"{br['legs']}-legged stirrups 10 @ {br['stir'][1]} / {br['stir'][2]}",
        10, c3 * 1000 / ((br["stir"][1] + br["stir"][2]) / 2.0) * (br["legs"] / 2), per if br["legs"] == 2 else per * 0.8, "closed stirrup")
    col = M["column"]
    nc = g["n_col"]
    add("Columns", "K1", f"longitudinal bars ({nc} columns)", col["dia"], col["n"] * nc,
        lapped(g["Lc"] + g["tr"] + th["d3"] - 0.15 + 0.5, col["dia"]), "L at the raft")
    tie = math.pi * (col["d"] - 2 * opt["cover_mm"]) / 1e3 + 0.2
    joints = len(g["braces"]) * 2 + 2
    n_conf = joints * math.ceil(col["conf_len"] / 100.0)
    add("Columns", "K2", "rings 8 @ 100 near the joints", 8, n_conf * nc, tie, "circular tie")
    add("Columns", "K3", "rings 8 @ 200", 8, max(0.0, g["Lc"] * 1e3 - joints * col["conf_len"]) / 200.0 * nc, tie, "circular tie")
    b = M["brace"]
    n_br = len(g["braces"]) * nc
    if n_br:
        Lcl = g["Lb"] - g["dc"]
        Lbar = Lcl + 2 * 47 * b["top"][1] / 1e3
        add("Braces", "BR1", "top bars", b["top"][1], b["top"][0] * n_br, Lbar, "anchored in the columns")
        add("Braces", "BR2", "bottom bars", b["bot"][1], b["bot"][0] * n_br, Lbar, "anchored in the columns")
        add("Braces", "BR3", f"stirrups 8 @ 100 / {b['stir'][2]}", 8, (Lcl * 1e3 / ((100 + b["stir"][2]) / 2.0)) * n_br,
            2 * (b["b"] + b["d"] - 4 * opt["cover_mm"]) / 1e3 + 0.2, "closed stirrup")
    rf = M["raft"]
    lapf = opt["lap_dia_found"]
    n, dia = rf["rad"]
    full = rf["ao"] + rf["bR"] + rf["ai"]
    _done, s_acc, prev = 0, rf["ao"] + rf["bR"], None
    groups = []
    for Lz, k in rf["zones_in"]:
        if prev is not None and k < prev:
            groups.append((prev - k, s_acc))
        s_acc += Lz
        prev = k
    groups.append((prev, full))
    for i, (cnt, Lbar) in enumerate(groups, 1):
        add("Raft", f"R1.{i}", f"radial at the bottom, {Lbar:.2f} m from the outer edge", dia, cnt, lapped(Lbar + 0.3, dia, lapf), "cranked ends")
    dh, sh = rf["hoop"]
    add("Raft", "R2", f"hoops at the bottom @ {sh}", dh, (rf["Ro"] - rf["Ri"]) * 1000 / sh, ring(math.pi * (rf["Ro"] + rf["Ri"]), dh, lapf), "ring")
    add("Raft", "R3", f"radial at the top @ {rf['top_rad'][1]}", rf["top_rad"][0], 2 * math.pi * r0 * 1000 / rf["top_rad"][1],
        lapped(rf["Ro"] - rf["Ri"], rf["top_rad"][0], lapf), "bent to the slope")
    add("Raft", "R4", f"hoops at the top @ {rf['top_hoop'][1]}", rf["top_hoop"][0], (rf["Ro"] - rf["Ri"]) * 1000 / rf["top_hoop"][1],
        ring(math.pi * (rf["Ro"] + rf["Ri"]), rf["top_hoop"][0], lapf), "ring")
    rr = M["raft_ring"]
    add("Foundation ring beam", "FB1", "top hoop bars", rr["top"][1], rr["top"][0], ring(c3, rr["top"][1], lapf), "ring")
    add("Foundation ring beam", "FB2", "bottom hoop bars", rr["bot"][1], rr["bot"][0], ring(c3, rr["bot"][1], lapf), "ring")
    perr = 2 * (rr["b"] + rr["d"] - 4 * opt["cover_fbeam_mm"]) / 1e3 + 0.24
    add("Foundation ring beam", "FB3", f"{rr['legs']}-legged stirrups 10 @ {rr['stir'][1]} / {rr['stir'][2]}", 10,
        c3 * 1000 / ((rr["stir"][1] + rr["stir"][2]) / 2.0) * (rr["legs"] / 2), perr if rr["legs"] == 2 else perr * 0.8, "closed stirrup")
    st = M.get("stair")
    if st:
        nf = st["n1"] + st["n2"]
        Lfl = math.hypot(st["treads"] * st["tread"], st["risers"] * st["riser1"]) + 1.2
        add("Staircase", "S1", f"flights: main bars @ {st['main'][1]} ({nf} flights)", st["main"][0], st["w"] * 1000 / st["main"][1] * nf, Lfl, "cranked")
        add("Staircase", "S2", f"flights: distribution @ {st['dist'][1]}", st["dist"][0], Lfl * 1000 / st["dist"][1] * nf, st["w"] - 0.05, "straight")
        Lbeam = st["L1"] + st["lc"] + 0.8
        add("Staircase", "S3", "landing beams: top and bottom bars", st["beam"]["top"][1], 2 * st["beam"]["top"][0] * nf, Lbeam, "anchored")
        add("Staircase", "S4", "landing beams: stirrups 8 @ 150", 8, (st["L1"] + st["lc"]) * 1000 / 150 * nf,
            2 * (st["beam"]["b"] + st["beam"]["d"] - 4 * opt["cover_stair_mm"]) / 1e3 + 0.2, "closed stirrup")
        add("Staircase", "S5", "landings: mesh 8 @ 150 both ways", 8, nf * 2 * 2.3 * 1000 / 150, 1.6, "straight")
        add("Staircase", "S6", "columns: longitudinal bars (2 columns)", st["col"]["dia"], 2 * st["col"]["n"], lapped(st["col"]["H"] + 0.8, st["col"]["dia"]), "L at the footing")
        add("Staircase", "S7", "columns: rings 8 @ 200", 8, 2 * st["col"]["H"] * 1000 / 200, math.pi * (st["col"]["d"] - 60) / 1e3 + 0.2, "circular tie")
        fb, fs = st["footing"]["bars"]
        add("Staircase", "S8", f"footings: mesh @ {fs} both ways (2 footings)", fb, 2 * 2 * st["footing"]["side"] * 1000 / fs, st["footing"]["side"] - 0.1, "straight")
    return rows


def quantities(res):
    """Concrete (m3) and steel (kg) by member."""
    g, W, M = res["geo"], res["weights"], res["members"]
    conc = {k: v / GAMMA_C for k, v in W.items() if k != "Water"}
    conc["Columns"] = g["n_col"] * area(g["dc"]) * g["Lc"]
    conc["Braces"] = len(g["braces"]) * g["n_col"] * g["bb"] * g["db"] * (g["Lb"] - g["dc"])
    rf = M["raft"]
    r0, bR, t, te = g["r0"], rf["bR"], rf["t"] / 1e3, rf["te"] / 1e3
    rfo, rfi = r0 + bR / 2.0, r0 - bR / 2.0
    ring_ = math.pi * (rfo ** 2 - rfi ** 2) * t
    # a tapered annulus: thickness linear from t at the beam's face to te at the edge
    out_ = math.pi * ((rf["Ro"] ** 2 - rfo ** 2) * te + (t - te) * (rf["Ro"] - rfo) * (rf["Ro"] + 2 * rfo) / 3.0)
    in_ = math.pi * ((rfi ** 2 - rf["Ri"] ** 2) * te + (t - te) * (rfi - rf["Ri"]) * (rf["Ri"] + 2 * rfi) / 3.0)
    conc["Raft"] = out_ + in_
    conc["Foundation ring beam"] = ring_
    st = M.get("stair")
    if st:
        nf = st["n1"] + st["n2"]
        fl = st["w"] * st["Lb"] * (st["waist"] / 1e3 * 1.25 + st["riser1"] / 2.0)
        land = math.pi * (st["w"] + st["gap"] / 2.0) ** 2 / 2.0 * st["waist"] / 1e3
        beam = st["beam"]["b"] * st["beam"]["d"] / 1e6 * (st["L1"] + st["lc"])
        conc["Staircase"] = (nf * (fl + land + beam) + 2 * area(st["col"]["d"] / 1e3) * st["col"]["H"]
                             + 2 * st["footing"]["side"] ** 2 * (st["footing"]["t"] + st["footing"]["te"]) / 2e3)
    steel = {}
    for r in res["bbs"]:
        steel[r["member"]] = steel.get(r["member"], 0.0) + r["kg"]
    return conc, steel
