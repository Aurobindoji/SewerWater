"""Intze design: the circular staging columns - steel stress, interaction curve, moments."""
import math
from .basics import _interp, area


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
