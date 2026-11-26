"""Intze design: ring sections and beams, the tank's proportions, the new capacity for a shortfall, the forces, wind and seismic factors."""
import math
from .basics import DEFAULTS, GAMMA_C, GAMMA_W, K2_TC2, _capacity, _dome, _interp, area, up


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


def new_kl(required_kl, existing_kl=None, step=50):
    """Capacity of the new OHT of an OZ (KL): its whole need where it has no OHT, the shortfall rounded up to `step`
    where an existing one is short of the need (user 23/24-Nov-2026: the existing one kept, the new one makes up the
    rest - as the water DPR T14 S.7), 0 where the existing one is enough."""
    need, have = float(required_kl or 0), float(existing_kl or 0)
    if need <= 0 or have >= need - 1e-6:
        return 0.0
    if have <= 0:
        return need
    return float(math.ceil((need - have) / step - 1e-9) * step) if step else need - have


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
