"""Intze design: the constants, materials (WSM, IS 3370), bar areas and weights, dome and capacity geometry."""
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


RING1_NOMINAL = 4 * math.pi * 12 * 12 / 4.0   # the top ring beam's hoop bars: 4 - 12 # (mm2), as the example


RING1_BAND = 1.0                               # the wall's top band (m) that takes the rest of the top dome's pull


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
