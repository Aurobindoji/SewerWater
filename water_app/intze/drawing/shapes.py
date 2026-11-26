"""Intze drawings: the tank's shapes - container outline, raft outline and thickness."""
import math
from water_app.intze import design as intze


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
    # the face runs on down to the beam's side, also below the beam's top: no flat ledge on the beam (user 21-Nov-2026)
    out.append((xo3, max(zo, lev["B3_bot"] + 0.1)))
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
    # the thickened soffit carried on to the wall's inner face: it met it with a small step (user 22-Nov-2026)
    (x0_, z0_), (x1_, z1_) = soff1[0], soff1[1]
    if x0_ < R - 1e-9 and abs(x0_ - x1_) > 1e-9:
        out.append((R, max(z0_ + (R - x0_) * (z0_ - z1_) / (x0_ - x1_), lev["wall_top"])))
        out += soff1[1:]
    else:
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
