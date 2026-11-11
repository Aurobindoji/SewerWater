"""The design calculation of an Intze OHT (intze.py) as a report, in the manner of the Brookfield Consultants report the user
gave on 10-Nov-2026 (design.pdf, pages 12-15 of the 3400 KL tank of zone 10): every step
as "symbol = formula = the numbers = result", then "Provide ..." - A4 pages as a PDF (user decision 10-Nov-2026:
"Report जैसी PDF"), written beside the drawings as <stem>_calc.pdf.

report(res) -> list of (kind, text) lines; export_pdf(res, path, meta) writes them.
"""
import datetime
import math

from . import intze

G = 9.81
PI = math.pi


def n_(x, d=2):
    """A number for the report: d decimals, no trailing noise."""
    if x is None:
        return "-"
    if abs(x) >= 1000 and d <= 2:
        return f"{x:,.{max(0, d - 1)}f}"
    return f"{x:.{d}f}"


def mesh_as(m):
    """mm2 per m of a (dia, spacing) mesh."""
    return intze.area(m[0]) * 1000.0 / m[1]


class R:
    def __init__(self):
        self.out = []

    def h1(self, t):
        self.out.append(("h1", t))

    def h2(self, t):
        self.out.append(("h2", t))

    def t(self, t, indent=1):
        self.out.append(("t%d" % indent, t))

    def f(self, lhs, formula, subst=None, result=None, unit="", ok=None):
        """lhs = formula = subst = result unit (two lines when long)."""
        res = f"{result} {unit}".rstrip() if result is not None else ""
        one = f"{lhs} = {formula}" + (f" = {subst}" if subst else "") + (f" = {res}" if res else "")
        if ok:
            one += f"   {ok}"
        if len(one) <= 94:
            self.out.append(("f", one))
        else:
            self.out.append(("f", f"{lhs} = {formula}"))
            self.out.append(("f2", (f"= {subst}" if subst else "") + (f" = {res}" if res else "") + (f"   {ok}" if ok else "")))

    def tm(self, t):
        """A row of a table, in the fixed-width font so that its columns line up."""
        self.out.append(("tm", t))

    def p(self, t):
        self.out.append(("p", t))

    def gap(self):
        self.out.append(("gap", ""))


def report(res):
    """The lines of the report."""
    g, th, M, opt, _lev, x = res["geo"], res["geo"]["th"], res["members"], res["opt"], res["levels"], res["x"]
    mat, f, C = x["mat"], x["f"], x["C"]
    fck, fckf, fy, sst = mat.fck, mat.fck_f, mat.fy, mat.sst_w
    D, D0, R_, r0, H = g["D"], g["D0"], g["R"], g["r0"], g["H"]
    al = g["alpha"]
    sa, ca, ta = math.sin(al), math.cos(al), math.tan(al)
    n = g["n_col"]
    r = R()

    # ------------------------------------------------------------------------------------------------ 1 data
    r.h1("1.0 DESIGN DATA")
    r.t(f"Capacity of the tank = {res['capacity_kl']:g} kL;  staging (L.W.L. above G.L.) = {res['staging_m']:g} m")
    r.t(f"Depth of water at the wall = {g['hc']:g} m (CPHEEO Water Manual 2024, Part A, Table 2.7 S.No.12: maximum")
    r.t("side water depth), the conical dome below it; free board = %s m" % n_(g["fb"]))
    r.t(f"Concrete: water container & staging M {fck} (M: {fck * 10}), foundation & staircase M {fckf} (M: {fckf * 10});"
        f" steel Fe {fy} D (IS: 1786)")
    r.t(f"Steel stress in members in contact with water, σst = {sst:g} N/mm² (IS: 3370 (Part 2) - 2009, crack width")
    r.t("deemed satisfied); staging, foundation and staircase by the limit state method of IS: 456 - 2000, load factor 1.5")
    r.t(f"Modular ratio m = 280 / (3 σcbc) = 280 / (3 x {mat.scbc:g}) = {n_(mat.m)};  permissible direct tension in"
        f" concrete = {mat.sct:g} N/mm² (IS: 3370 (Part 2) Table 1)")
    r.t(f"Seismic zone {opt['zone']} (Z = {intze.ZONE_Z[opt['zone']]}), importance factor I = {opt['I']}, response"
        f" reduction factor R = {opt['R']} (IS: 1893 (Part 1) - 2016, IS: 1893 (Part 2) - 2014); soil type {opt['soil_type']}")
    r.t(f"Basic wind speed Vb = {opt['wind_vb']:g} m/s (IS: 875 (Part 3) - 2015);  net bearing capacity of soil ="
        f" {opt['sbc_kn_m2']:g} kN/m² at {opt['founding_depth_m']:g} m below G.L. (assumed - to be confirmed by soil test)")
    r.t("Unit weights: R.C.C. 25 kN/m³, water 10 kN/m³;  live load on the roof %s kN/m², on the balcony %s kN/m²"
        % (n_(opt["roof_live_kn_m2"]), n_(opt["balcony_live_kn_m2"], 1)))

    # ------------------------------------------------------------------------------------------------ 2 geometry
    r.h1("2.0 DIMENSIONS OF THE CONTAINER")
    d2 = intze._dome(r0, g["h2"])
    cyl = PI / 4 * D * D * g["hc"]
    cone = PI * g["h0"] / 12 * (D * D + D * D0 + D0 * D0)
    dvol = d2["vol"]
    r.t(f"Internal diameter of the cylinder D = {n_(D)} m;  diameter of the bottom ring (column circle) D0 = {n_(D0)} m")
    r.f("Height of the conical dome h0", "(D - D0) / 2 x tan α", f"({n_(D)} - {n_(D0)}) / 2 x tan {opt['cone_deg']:g}°", n_(g["h0"], 3), "m")
    r.t(f"Rise of the bottom dome h2 = {n_(g['h2'])} m;  rise of the top dome h1 = {n_(g['h1'])} m")
    r.f("Volume of the cylinder", "π/4 D² hc", f"π/4 x {n_(D)}² x {n_(g['hc'], 3)}", n_(cyl, 1), "m³")
    r.f("Volume of the conical portion", "π h0 / 12 (D² + D D0 + D0²)",
        f"π x {n_(g['h0'], 3)} / 12 ({n_(D)}² + {n_(D)} x {n_(D0)} + {n_(D0)}²)", n_(cone, 1), "m³")
    r.f("Radius of the bottom dome R2", "(r0² + h2²) / 2 h2", f"({n_(r0, 3)}² + {n_(g['h2'])}²) / (2 x {n_(g['h2'])})", n_(d2["R"], 3), "m")
    r.f("Volume of the bottom dome", "π h2² (3 R2 - h2) / 3", f"π x {n_(g['h2'])}² (3 x {n_(d2['R'], 3)} - {n_(g['h2'])}) / 3",
        n_(dvol, 1), "m³")
    r.f("Capacity provided", "cylinder + cone - bottom dome", f"{n_(cyl, 1)} + {n_(cone, 1)} - {n_(dvol, 1)}",
        n_(g["cap"], 1), "m³", f">= {res['capacity_kl']:g} kL, OK.")

    # ------------------------------------------------------------------------------------------------ 3 top dome
    r.h1("3.0 DESIGN OF TOP DOME")
    d1 = f["dome1"]
    t1 = th["t1"] * 1e3
    r.f("Radius of the top dome R1", "(R² + h1²) / 2 h1", f"({n_(R_, 3)}² + {n_(g['h1'])}²) / (2 x {n_(g['h1'])})", n_(d1["R"], 3), "m")
    r.f("sin θ1", "R / R1", f"{n_(R_, 3)} / {n_(d1['R'], 3)}", n_(d1["sin"], 4), f";  cos θ1 = {n_(d1['cos'], 4)}")
    r.f("Load w", "self weight + live load + finish", f"25 x {n_(th['t1'], 3)} + {n_(opt['roof_live_kn_m2'])} + {n_(opt['roof_finish_kn_m2'])}",
        n_(f["w1"]), "kN/m²")
    r.f("Meridional thrust at the edge T1", "w R1 / (1 + cos θ1)", f"{n_(f['w1'])} x {n_(d1['R'], 3)} / (1 + {n_(d1['cos'], 4)})",
        n_(f["T1"]), "kN/m")
    r.f("Meridional stress", "T1 / t", f"{n_(f['T1'] * 1e3, 0)} / (1000 x {t1:.0f})", n_(f["T1"] / t1), "N/mm²", "small, OK.")
    r.f("Hoop stress at the crown", "w R1 / 2 t", f"{n_(f['w1'])} x {n_(d1['R'], 3)} x 1000 / (2 x 1000 x {t1:.0f})",
        n_(f["hoop1_crown"] / t1), "N/mm²", "small, OK.")
    td = M["top_dome"]
    r.f("Minimum steel", "0.24 % of the section", f"0.0024 x 1000 x {t1:.0f}", n_(0.0024 * 1000 * t1, 0), "mm²/m")
    r.p(f"Provide {td['rad'][0]} φ tor bars @ {td['rad'][1]} c/c radially and as hoops ({n_(mesh_as(td['rad']), 0)} mm²/m)."
        f" Thickness {td['t']} mm, increased to {td['te']} mm over {td['edge'] * 1e3:.0f} mm at the edge with {td['edge_rad'][0]} φ"
        f" @ {td['edge_rad'][1]} c/c radially at top and {td['edge_hoop'][0]} φ hoops @ {td['edge_hoop'][1]} c/c (as the example).")

    # ------------------------------------------------------------------------------------------------ 4 top ring beam
    r.h1("4.0 DESIGN OF TOP RING BEAM")
    tr_ = M["top_ring"]
    r.f("Horizontal component of T1", "T1 cos θ1", f"{n_(f['T1'])} x {n_(d1['cos'], 4)}", n_(f["H1"]), "kN/m")
    r.f("Hoop tension P1", "T1 cos θ1 x D / 2", f"{n_(f['H1'])} x {n_(D)} / 2", n_(f["P1"], 1), "kN")
    As1 = f["P1"] * 1e3 / sst
    r.f("Ast", "P1 / σst", f"{n_(f['P1'] * 1e3, 0)} / {sst:g}", n_(As1, 0), "mm²")
    r.p(f"Provide {tr_['n']} - {tr_['dia']} φ tor hoops ({n_(tr_['n'] * intze.area(tr_['dia']), 0)} mm²) in a {tr_['b']} x {tr_['d']}"
        f" mm ring beam, with 8 φ stirrups @ 200 c/c.")

    # ------------------------------------------------------------------------------------------------ 5 wall
    r.h1("5.0 DESIGN OF CYLINDRICAL WALL")
    w = M["wall"]
    Tw = intze.GAMMA_W * g["hc"] * R_
    Asw = Tw * 1e3 / sst
    r.f("Hoop tension at the base T", "w hc D / 2", f"10 x {n_(g['hc'], 3)} x {n_(D)} / 2", n_(Tw, 1), "kN/m")
    r.f("Ast at the base", "T / σst", f"{n_(Tw * 1e3, 0)} / {sst:g}", n_(Asw, 0), "mm²/m")
    tb = w["tb"]
    st = Tw * 1e3 / (1000 * tb + (mat.m - 1) * Asw)
    r.f("Tensile stress in concrete at the base", "T / (1000 t + (m - 1) Ast)",
        f"{n_(Tw * 1e3, 0)} / (1000 x {tb} + {n_(mat.m - 1)} x {n_(Asw, 0)})", n_(st), "N/mm²", f"<= {mat.sct:g}, OK.")
    r.t(f"Wall {w['t']} mm thick at the top, thickened on its outer face to {tb} mm over the lowest {w['taper']:g} m.")
    r.t("Hoop steel by zones from the top of the wall (depth of water below the F.S.L. at the bottom of each zone):")
    for z in w["zones"]:
        dep = max(0.0, z["top"] + z["len"] - g["fb"])
        prov = 2 * mesh_as((z["dia"], z["sp"]))
        r.f(f"   {n_(z['top'])} - {n_(z['top'] + z['len'])} m: T", "w h D / 2",
            f"10 x {n_(dep, 3)} x {n_(D)} / 2 = {n_(z['T'], 1)} kN/m;  Ast = {n_(z['As'], 0)} mm²/m", None, "")
        r.p(f"   Provide {z['n']} - {z['dia']} φ hoops @ {z['sp']} c/c on each face ({n_(prov, 0)} mm²/m).")
    tavg = (th["tw"] + th["twb"]) / 2
    coef = w["Mw"] / (intze.GAMMA_W * g["hc"] ** 3)
    r.f("H² / D t", "hc² / (D t)", f"{n_(g['hc'], 3)}² / ({n_(D)} x {n_(tavg, 3)})", n_(w["K"]), "", "(IS: 3370 (Part 4) Table 10)")
    r.f("Vertical moment at the base (fixed)", f"{n_(coef, 4)} w hc³", f"{n_(coef, 4)} x 10 x {n_(g['hc'], 3)}³", n_(w["Mw"], 1), "kNm/m")
    dwb = tb - opt["cover_water_mm"] - 8
    r.f("Ast (water face)", "M / (σst x 0.87 d)", f"{n_(w['Mw'] * 1e6, 0)} / ({sst:g} x 0.87 x {dwb})",
        n_(w["Mw"] * 1e6 / (sst * 0.87 * dwb), 0), "mm²/m")
    r.p(f"Provide {w['base_in'][0]} φ @ {w['base_in'][1]} c/c vertically on the water face at the base, {w['base_len'] * 1e3:.0f} long, and"
        f" {w['vert'][0]} φ @ {w['vert'][1]} c/c vertically on each face elsewhere (0.24 %).")

    # ------------------------------------------------------------------------------------------------ 6 balcony ring
    r.h1("6.0 DESIGN OF BALCONY RING (RING BEAM AT THE TOP OF THE CONICAL DOME)")
    bl = M["balcony"]
    Aw = f["A_wall"]
    r.f("Vertical load at the top of the cone W", "T1 sin θ1 + top ring beam + wall + balcony ring + live load",
        f"{n_(f['V1'])} + 25 ({n_(th['b1'] * th['d1'], 3)} + {n_(Aw, 3)} + {n_((th['twb'] + th['bal_w']) * th['bal_t'], 3)})"
        f" + {n_(opt['balcony_live_kn_m2'], 1)} x {n_(th['bal_w'])}", n_(f["W2"], 1), "kN/m")
    r.f("Hoop tension P2", "(W cot α + w h t) D / 2",
        f"({n_(f['W2'], 1)} / {n_(ta, 4)} + 10 x {n_(g['hc'] - th['bal_t'] / 2, 3)} x {n_(th['bal_t'])}) x {n_(D)} / 2", n_(f["P2"], 1), "kN")
    r.f("Ast", "P2 / σst", f"{n_(f['P2'] * 1e3, 0)} / {sst:g}", n_(f["P2"] * 1e3 / sst, 0), "mm²")
    r.p(f"Provide {bl['n']} - {bl['dia']} φ tor hoops ({n_(bl['n'] * intze.area(bl['dia']), 0)} mm²) in the ring"
        f" {(th['twb'] + th['bal_w']) * 1e3:.0f} x {bl['t']} mm.")
    r.f("Balcony cantilever Mu", "1.5 [(25 t + LL) b² / 2 + 1.0 b]",
        f"1.5 [(25 x {n_(th['bal_t'])} + {n_(opt['balcony_live_kn_m2'], 1)}) x {n_(th['bal_w'])}² / 2 + {n_(th['bal_w'])}]",
        n_(x["Mu_bal"]), "kNm/m")
    r.p(f"Ast = {n_(x['As_bal'], 0)} mm²/m: provide {bl['rad'][0]} φ @ {bl['rad'][1]} c/c radially at top and {bl['dist'][0]} φ"
        f" @ {bl['dist'][1]} c/c at bottom.")

    # ------------------------------------------------------------------------------------------------ 7 cone
    r.h1("7.0 DESIGN OF CONICAL DOME")
    cn = M["cone"]
    q0 = 25 * th["t0"]
    r.t(f"α = {opt['cone_deg']:g}° (to the horizontal); thickness t0 = {cn['t']} mm, self weight q = 25 x {n_(th['t0'])} = {n_(q0)} kN/m²;"
        " H = depth of water at the bottom of the cone = %s m" % n_(H, 3))
    r.t("At a radius r: V = load above (water above the cone + cone + W at its top), p = w (H - (r - r0) tan α),")
    r.t("meridional thrust Nφ = V / (2 π r sin α), hoop tension Nθ = (p + q cos α) r / sin α")
    for c in f["cone"]:
        r.f(f"   r = {n_(c['r'], 3)} m: Nφ", "V / (2 π r sin α)", f"{n_(c['V'], 0)} / (2π x {n_(c['r'], 3)} x {n_(sa, 4)})",
            n_(c["Nphi"], 1), "kN/m")
        r.f("               Nθ", "(p + q cos α) r / sin α", f"({n_(c['p'], 2)} + {n_(q0)} x {n_(ca, 4)}) x {n_(c['r'], 3)} / {n_(sa, 4)}",
            n_(c["Nth"], 1), "kN/m")
    Nm = max(c["Nth"] for c in f["cone"])
    r.f("Thickness for the hoop steel at most 2.25 %", "Nθ max / (σst x 0.0225)", f"{n_(Nm * 1e3, 0)} / ({sst:g} x 0.0225)",
        n_(Nm * 1e3 / sst / 0.0225 / 1e3, 0), "mm", f"provided {cn['t']} mm, OK.")
    r.f("Meridional stress", "Nφ max / t", f"{n_(f['cone'][0]['Nphi'] * 1e3, 0)} / (1000 x {cn['t']})",
        n_(f["cone"][0]["Nphi"] / cn["t"]), "N/mm²", "small, OK.")
    for lab, N, m_, cnt in (("lower half", cn["N_low"], cn["hoop_low"], cn["n_low"]), ("upper half", cn["N_up"], cn["hoop_up"], cn["n_up"])):
        r.f(f"Ast, {lab}", "Nθ / σst", f"{n_(N * 1e3, 0)} / {sst:g}", n_(N * 1e3 / sst, 0), "mm²/m")
        r.p(f"Provide {cnt} - {m_[0]} φ hoops @ {m_[1]} c/c on each face ({n_(2 * mesh_as(m_), 0)} mm²/m) in the {lab}.")
    r.p(f"Provide {cn['mer'][0]} φ @ {cn['mer'][1]} c/c meridionally on each face (0.3 % each face, as the example).")

    # ------------------------------------------------------------------------------------------------ 8 bottom dome
    r.h1("8.0 DESIGN OF BOTTOM DOME")
    bd = M["bottom_dome"]
    t2 = th["t2"] * 1e3
    r.f("sin θ2", "r0 / R2", f"{n_(r0, 3)} / {n_(d2['R'], 3)}", n_(d2["sin"], 4), f";  cos θ2 = {n_(d2['cos'], 4)}")
    r.f("Load W", "w (π r0² H - volume of the dome) + 25 t2 x area", f"10 (π x {n_(r0, 3)}² x {n_(H, 3)} - {n_(dvol, 1)}) + 25 x {n_(th['t2'])}"
        f" x {n_(d2['area'], 1)}", n_(f["Wd"], 0), "kN")
    r.f("Meridional thrust T2", "W / (2 π r0 sin θ2)", f"{n_(f['Wd'], 0)} / (2π x {n_(r0, 3)} x {n_(d2['sin'], 4)})", n_(f["T2"], 1), "kN/m")
    r.f("Meridional stress", "T2 / t", f"{n_(f['T2'] * 1e3, 0)} / (1000 x {t2:.0f})", n_(f["T2"] / t2), "N/mm²",
        f"<= {n_(0.25 * fck / 2.0, 2)}, OK.")
    r.f("Hoop stress at the crown", "w R2 / 2 t", f"{n_(f['hoop2_crown'] * 2 / d2['R'])} x {n_(d2['R'], 3)} x 1000 / (2 x 1000 x {t2:.0f})",
        n_(f["hoop2_crown"] / t2), "N/mm²", "OK.")
    r.p(f"Provide {bd['rad'][0]} φ @ {bd['rad'][1]} c/c radially and as hoops on each face (0.24 %); {bd['t']} mm thick, {bd['te']} mm"
        f" over {bd['edge'] * 1e3:.0f} mm at the edge with {bd['edge_rad'][0]} φ @ {bd['edge_rad'][1]} c/c radially at top and"
        f" {bd['edge_hoop'][0]} φ hoops @ {bd['edge_hoop'][1]} c/c (as the example).")

    # ------------------------------------------------------------------------------------------------ 9 bottom ring beam
    r.h1("9.0 DESIGN OF BOTTOM RING BEAM")
    c0 = f["cone"][0]
    br = M["bottom_ring"]
    cb3 = x["cb3"]
    r.f("Horizontal thrust of the bottom dome (outward)", "T2 cos θ2", f"{n_(f['T2'], 1)} x {n_(d2['cos'], 4)}", n_(f["T2"] * d2["cos"], 1), "kN/m")
    r.f("Horizontal thrust of the cone (inward)", "Nφ cos α", f"{n_(c0['Nphi'], 1)} x {n_(ca, 4)}", n_(c0["Nphi"] * ca, 1), "kN/m")
    r.f("Net hoop force (+ tension)", "(T2 cos θ2 - Nφ cos α) r0", f"{n_(f['H3'], 2)} x {n_(r0, 3)}", n_(f["P3"], 1), "kN")
    r.f("Vertical load w", "Nφ sin α + T2 sin θ2 + self weight",
        f"{n_(c0['Nphi'], 1)} x {n_(sa, 4)} + {n_(f['T2'], 1)} x {n_(d2['sin'], 4)} + 25 x {n_(th['b3'])} x {n_(th['d3'])}", n_(f["w3"], 1), "kN/m")
    thn = PI / n
    r.t(f"Circular beam on {n} columns, radius r0 = {n_(r0, 3)} m, θ = π / n = {n_(math.degrees(thn), 2)}°:")
    r.f("   Moment at a column", "w r0² (θ cot θ - 1)", f"{n_(f['w3'], 1)} x {n_(r0, 3)}² ({n_(thn, 4)} x {n_(1 / math.tan(thn), 4)} - 1)", n_(cb3["Ms"], 1), "kNm")
    r.f("   Moment at mid-span", "w r0² (θ / sin θ - 1)", f"{n_(f['w3'], 1)} x {n_(r0, 3)}² ({n_(thn, 4)} / {n_(math.sin(thn), 4)} - 1)", n_(cb3["Mm"], 1), "kNm")
    r.f("   Largest torsion", "w r0² (θ sin φ / sin θ - φ)", None, n_(cb3["T"], 2), f"kNm at {n_(cb3['phi_deg'], 1)}° from a column")
    r.f("   Shear at a column", "w r0 θ", f"{n_(f['w3'], 1)} x {n_(r0, 3)} x {n_(thn, 4)}", n_(cb3["V"], 1), "kN")
    r.f("Equivalent moment Mu (support)", "1.5 M + 1.5 T (1 + D/b) / 1.7", f"1.5 x {n_(abs(cb3['Ms']), 1)} + {n_(x['Mt3'], 1)}",
        n_(1.5 * abs(cb3["Ms"]) + x["Mt3"], 1), "kNm")
    r.f("Effective depth required", "√(Mu / (0.133 fck b))", f"√({n_((1.5 * abs(cb3['Ms']) + x['Mt3']) * 1e6, 0)} / (0.133 x {fck} x {br['b']}))",
        n_(math.sqrt((1.5 * abs(cb3['Ms']) + x['Mt3']) * 1e6 / (mat.q_lim * fck * br['b'])), 0), "mm", f"provided {x['dd3']:.0f} mm, OK.")
    r.f("Ast (top, at the columns)", "IS: 456 G-1.1 (b) + half the net hoop tension / σst", None, n_(x["As3_top"], 0), "mm²")
    r.f("Ast (bottom, at mid-span)", "IS: 456 G-1.1 (b) + half the net hoop tension / σst", None, n_(x["As3_bot"], 0), "mm²")
    r.p(f"Provide a {br['b']} x {br['d']} mm beam with {br['top'][0]} - {br['top'][1]} φ hoops at top"
        f" ({n_(br['top'][0] * intze.area(br['top'][1]), 0)} mm²) and {br['bot'][0]} - {br['bot'][1]} φ at bottom"
        f" ({n_(br['bot'][0] * intze.area(br['bot'][1]), 0)} mm²)" + (f", {br['side'][0]} - {br['side'][1]} φ on each side face." if br["side"][0] else "."))
    r.f("Equivalent shear Ve", "1.5 V + 1.6 x 1.5 T / b", f"1.5 x {n_(cb3['V'], 1)} + 1.6 x 1.5 x {n_(cb3['T'], 2)} / {n_(th['b3'])}",
        n_(x["Ve3"], 1), "kN")
    r.f("τve", "Ve / (b d)", f"{n_(x['Ve3'] * 1e3, 0)} / ({br['b']} x {x['dd3']:.0f})", n_(x["tve3"]), "N/mm²", f"<= τc,max {intze.TAU_MAX[fck]}, OK.")
    r.f("Asv / sv", "T / (b1 d1 0.87 fy) + V / (2.5 d1 0.87 fy), at least 0.4 b / 0.87 fy", None, n_(x["asv3"], 3), "mm²/mm")
    r.p(f"Provide {br['legs']}-legged 10 φ stirrups @ {br['stir'][1]} c/c near the columns and @ {br['stir'][2]} c/c elsewhere.")

    # ------------------------------------------------------------------------------------------------ 10 loads
    r.h1("10.0 LOADS ON THE STAGING")
    for k, v in C["Wt"].items():
        r.tm(f"{k:<28s} {n_(v, 0):>10s} kN")
    r.tm(f"{'Container (empty)':<28s} {n_(C['W_cont'], 0):>10s} kN")
    r.tm(f"{'Water':<28s} {n_(x['W_water'], 0):>10s} kN")
    r.tm(f"{'Live load (roof, balcony)':<28s} {n_(x['W_live'], 0):>10s} kN")
    r.tm(f"{'Columns':<28s} {n_(C['W_col'], 0):>10s} kN")
    r.tm(f"{'Braces':<28s} {n_(C['W_br'], 0):>10s} kN")
    r.tm(f"{'Total at the column bases':<28s} {n_(x['W_tot'], 0):>10s} kN (tank full)")

    # ------------------------------------------------------------------------------------------------ 11 lateral
    r.h1("11.0 LATERAL LOADS (IS: 1893 (PART 2) - 2014, IS: 875 (PART 3) - 2015)")
    heq, hD = C["h_eq"], C["h_eq"] / D
    mw = x["W_water"]
    r.f("Height of the equivalent cylinder h", "capacity / (π R²)", f"{n_(g['cap'], 1)} / (π x {n_(R_, 3)}²)", n_(heq, 3), "m",
        f"h / D = {n_(hD, 4)}")
    r.f("Impulsive weight Wi", "W tanh(0.866 D/h) / (0.866 D/h)", f"{n_(mw, 0)} x tanh({n_(0.866 / hD, 3)}) / {n_(0.866 / hD, 3)}",
        n_(C["mi"] * G, 0), "kN")
    r.f("Convective weight Wc", "W x 0.23 tanh(3.68 h/D) / (h/D)", f"{n_(mw, 0)} x 0.23 tanh({n_(3.68 * hD, 3)}) / {n_(hD, 4)}",
        n_(C["mc"] * G, 0), "kN")
    r.f("Structure weight Ws", "container + 1/3 staging", f"{n_(C['W_cont'], 0)} + ({n_(C['W_col'], 0)} + {n_(C['W_br'], 0)}) / 3",
        n_(C["ms"] * G, 0), "kN")
    r.f("Lateral stiffness of the staging Ks", "1 / Σ (h³ / (n 12 E I a))", f"n = {n}, E = {n_(mat.E, 0)} N/mm², a = {n_(C['afac'], 3)}"
        f" (restraint by the braces)", n_(C["Ks"], 0), "kN/m")
    Ti, Tc = C["Ti"], C["Tc"]
    sai, sac = intze._sa_g(Ti, opt["soil_type"]), intze._sa_g(Tc, opt["soil_type"], damping5=False)
    r.f("Ti", "2π √((Wi + Ws) / g Ks)", f"2π √({n_((C['mi'] + C['ms']) * G, 0)} / (9.81 x {n_(C['Ks'], 0)}))", n_(Ti, 3), "s")
    r.f("Tc", "Cc √(D / g), Cc = 2π / √(3.68 tanh(3.68 h/D))", None, n_(Tc, 3), "s")
    Z, I_, R_f = intze.ZONE_Z[opt["zone"]], opt["I"], opt["R"]
    r.f("(Ah)i", "Z/2 x I/R x Sa/g", f"{Z}/2 x {I_}/{R_f} x {n_(sai, 3)}", n_(C["Ahi"], 4), "")
    r.f("(Ah)c", "Z/2 x I/R x 1.75 Sa/g (0.5 % damping)", f"{Z}/2 x {I_}/{R_f} x {n_(sac, 3)}", n_(C["Ahc"], 4), "")
    r.f("Base shear: impulsive Vi", "(Ah)i (Wi + Ws)", f"{n_(C['Ahi'], 4)} x {n_((C['mi'] + C['ms']) * G, 0)}", n_(C["Vi"], 1), "kN")
    r.f("convective Vc", "(Ah)c Wc", f"{n_(C['Ahc'], 4)} x {n_(C['mc'] * G, 0)}", n_(C["Vc"], 1), "kN")
    r.f("V (tank full)", "√(Vi² + Vc²)", f"√({n_(C['Vi'], 1)}² + {n_(C['Vc'], 1)}²)", n_(C["Vq"], 1), "kN")
    r.f("Overturning moment at the base (tank full)", "√(Mi² + Mc²)", None, n_(C["Mq"], 0), "kNm")
    r.f("Tank empty: V / M", "(Ah) Ws", None, f"{n_(C['Ve'], 1)} kN / {n_(C['Me'], 0)}", "kNm")
    r.f("Wind: design pressure at the top", "0.6 Vz² Kd Ka Kc", None, n_(C["pd_top"], 3), "kN/m²")
    r.f("Wind: V / M", "Cf x pd x area (container 0.7, columns 1.2, braces 2.0)", None, f"{n_(C['Vw'], 1)} kN / {n_(C['Mw'], 0)}", "kNm")
    r.f("Sloshing wave", "(Ah)c R D / 2", f"{n_(C['Ahc'], 4)} x {R_f} x {n_(D)} / 2", n_(res["slosh_m"]), "m", f"(free board {n_(g['fb'])} m)")

    # ------------------------------------------------------------------------------------------------ 12 columns
    r.h1("12.0 DESIGN OF COLUMNS")
    col = M["column"]
    r.t(f"{n} columns of {col['d']} mm dia on a circle of radius {n_(r0, 3)} m; {len(g['braces'])} brace levels, panel height"
        f" {n_(C['Lp'], 3)} m.")
    r.f("Axial load per column (tank full)", "W / n + self weight", None, n_(C["P_full"], 1), "kN")
    r.f("Axial load per column (tank empty)", "W empty / n + self weight", None, n_(C["P_empty"], 1), "kN")
    lat = max(C["lat"], key=lambda t: t[2])
    r.f("Axial load from the overturning ΔP", "2 M / (n r0)", f"2 x {n_(lat[2], 0)} / ({n} x {n_(r0, 3)})", n_(2 * lat[2] / (n * r0), 1), "kN",
        f"({lat[0]})")
    r.f("Moment in a column", "V h / n", f"{n_(C['Vmax'], 1)} x {n_(C['h_des'], 3)} / {n}", n_(C["Vmax"] * C["h_des"] / n, 1), "kNm")
    r.t("Factored loads (x 1.5; the column in the line of the load takes ΔP and half the moment, the one on the bending")
    r.t("axis the whole moment; minimum eccentricity l/500 + D/30, IS: 456 25.4):")
    for name, Pu, Mu in C["cases"]:
        r.tm(f"{name:<52s} Pu = {n_(Pu, 0):>6s} kN, Mu = {n_(max(Mu, abs(Pu) * C['emin']), 1):>6s} kNm")
    r.p(f"Provide {col['n']} - {col['dia']} φ tor bars ({n_(col['pt'])} %) in each column; the interaction curve by strain"
        f" compatibility (IS: 456 38.1, 39.1) gives a utilisation of {n_(C['util'])} <= 1, OK.")
    r.p(f"Also provide 8 φ tor rings @ 200 c/c, and @ 100 c/c over {col['conf_len']} mm at each joint (IS: 13920 - 2016).")

    # ------------------------------------------------------------------------------------------------ 13 braces
    r.h1("13.0 DESIGN OF BRACES (M: %d CONCRETE)" % (fck * 10))
    b = M["brace"]
    Lb, Lcl = g["Lb"], g["Lb"] - g["dc"]
    r.f("Maximum bending moment at any brace level M", "V x panel height", f"{n_(C['Vmax'], 1)} x {n_(C['Lp'], 3)}", n_(x["Mlev"], 1), "kNm")
    r.f("Mo", "M / n (1 + cos 2π/n)", f"{n_(x['Mlev'], 1)} / {n} (1 + cos 2π/{n})", n_(x["Mo"], 2), "kNm")
    r.f("Maximum bending moment in brace Mb", "0.5 Mo (Lc / Lb) sec (π/n)", f"0.5 x {n_(x['Mo'], 2)} ({n_(Lcl, 3)} / {n_(Lb, 3)}) sec (π/{n})",
        n_(b["Mb"], 2), "kNm")
    r.f("Fb", "2 Mb / Lc", f"2 x {n_(b['Mb'], 2)} / {n_(Lcl, 3)}", n_(b["Fb"], 2), "kN")
    z = b["d"] - 2 * (opt["cover_mm"] + 18)
    r.f("Ast = Asc", "1.5 Mb / (0.87 fy z)", f"1.5 x {n_(b['Mb'] * 1e6, 0)} / (0.87 x {fy} x {z})", n_(1.5 * b["Mb"] * 1e6 / (0.87 * fy * z), 0),
        "mm²", f"(minimum {n_(0.85 * b['b'] * x['deb'] / fy, 0)})")
    r.p(f"Provide {b['top'][0]} - {b['top'][1]} φ tor bars on each face in each {b['b']} x {b['d']} brace"
        f" ({n_(b['top'][0] * intze.area(b['top'][1]), 0)} mm²).")
    r.f("Asv / sv", "(1.5 Fb - τc b d) / (0.87 fy d), at least 0.4 b / 0.87 fy", None, n_(x["asv_b"], 4), "mm²/mm")
    r.p(f"Provide 8 φ two legged stirrups @ 100 c/c near the columns and @ {b['stir'][2]} c/c elsewhere in each brace.")

    # ------------------------------------------------------------------------------------------------ 14 foundation
    r.h1("14.0 FOUNDATION (M: %d CONCRETE)" % (fckf * 10))
    rf, raft = M["raft"], x["raft"]
    q = opt["sbc_kn_m2"]
    r.t(f"Net bearing capacity of soil = {q:g} kN/m²; total load at the column bases = {n_(x['W_tot'], 0)} kN.")
    r.f("Bearing area required", "W / q", f"{n_(x['W_tot'], 0)} / {q:g}", n_(x["W_tot"] / q, 1), "m²")
    r.t(f"Provide an annular raft with its outer radius {n_(rf['Ro'])} m and inner radius {n_(rf['Ri'])} m (the centroid of the"
        " pressure on the column circle).")
    r.f("Bearing area provided", "π (Ro² - Ri²)", f"π ({n_(rf['Ro'])}² - {n_(rf['Ri'])}²)", n_(raft["A"], 1), "m²")
    r.f("Net pressure (gravity)", "W / A", f"{n_(x['W_tot'], 0)} / {n_(raft['A'], 1)}", n_(raft["q_g"], 1), "kN/m²", f"<= {q:g}, OK.")
    r.f("With the lateral load", "W / A + M / Z", None, n_(raft["q_max"], 1), "kN/m²", f"<= 1.25 x {q:g} = {n_(1.25 * q, 1)}, OK.")
    r.f("Tank empty, least", "W / A - M / Z", None, n_(raft["q_min"], 1), "kN/m²", ">= 0, no uplift, OK.")
    r.f("Design pressure qu", "larger of 1.5 q and 1.2 q max", None, n_(rf["qu"], 1), "kN/m²")
    rfo, rfi = r0 + rf["bR"] / 2, r0 - rf["bR"] / 2
    r.t(f"Cantilever projection of the raft slab: outer {n_(rf['ao'], 3)} m, inner {n_(rf['ai'], 3)} m (ring beam {rf['bR'] * 1e3:.0f} wide).")
    r.f("i. Maximum moment in the outer cantilever", "qu a² (2 Ro + r) / (6 r)",
        f"{n_(rf['qu'], 1)} x {n_(rf['ao'], 3)}² (2 x {n_(rf['Ro'])} + {n_(rfo, 3)}) / (6 x {n_(rfo, 3)})", n_(rf["Mo"], 1), "kNm/m")
    r.f("ii. Maximum moment in the inner cantilever", "qu a² (2 Ri + r) / (6 r)",
        f"{n_(rf['qu'], 1)} x {n_(rf['ai'], 3)}² (2 x {n_(rf['Ri'])} + {n_(rfi, 3)}) / (6 x {n_(rfi, 3)})", n_(rf["Mi"], 1), "kNm/m")
    Mmax = max(rf["Mo"], rf["Mi"])
    r.f("Effective depth required", "√(Mu / (0.133 fck b))", f"√({n_(Mmax * 1e6, 0)} / (0.133 x {fckf} x 1000))",
        n_(math.sqrt(Mmax * 1e6 / (mat.q_lim * fckf * 1000)), 0), "mm")
    r.p(f"Provide {x['d0']:.0f} mm (effective), {rf['t']} mm (overall) thickness at the ring beam, tapered to {rf['te']} mm at the"
        f" edges (shear at d from the beam checked with IS: 456 Table 19).")
    r.f("Ast (outer / inner)", "IS: 456 G-1.1 (b), at least 0.12 %", None, f"{n_(x['Ast_o'], 0)} / {n_(x['Ast_i'], 0)}", "mm²/m")
    r.p(f"Provide {rf['rad'][0]} - {rf['rad'][1]} φ tor bars in the radial direction at {rf['rad_sp']} mm c/c on the column circle"
        f" (the inner projection: " + "; ".join(f"{k} bars over {L * 1e3:.0f} mm" for L, k in rf["zones_in"]) + ").")
    r.p(f"Also provide {rf['hoop'][0]} φ tor hoops @ {rf['hoop'][1]} c/c at the bottom, and {rf['top_rad'][0]} φ @ {rf['top_rad'][1]} c/c"
        f" radially with {rf['top_hoop'][0]} φ hoops @ {rf['top_hoop'][1]} c/c at the top.")
    r.h2("Design of Foundation Ring Beam")
    rr, cbr = M["raft_ring"], x["cbr"]
    r.f("Factored load on the ring beam", "1.5 W / (2 π r0)", f"1.5 x {n_(x['W_tot'], 0)} / (2π x {n_(r0, 3)})",
        n_(1.5 * x["W_tot"] / (2 * PI * r0), 1), "kN/m")
    r.f("Maximum hogging moment (at the columns)", "w r0² (1 - θ cot θ)", None, n_(abs(cbr["Ms"]), 1), "kNm")
    r.f("Maximum sagging moment (mid-span)", "w r0² (θ / sin θ - 1)", None, n_(abs(cbr["Mm"]), 1), "kNm")
    r.f("Design shear force", "w r0 θ", None, n_(cbr["V"], 1), "kN")
    r.f("Ast (bottom, under the columns) / (top, mid-span)", "IS: 456 G-1.1 (b)", None, f"{n_(x['Asr_bot'], 0)} / {n_(x['Asr_top'], 0)}", "mm²")
    r.p(f"Provide a {rr['b']} x {rr['d']} mm ring beam (in the depth of the raft) with {rr['bot'][0]} - {rr['bot'][1]} φ tor hoops at the"
        f" bottom and {rr['top'][0]} - {rr['top'][1]} φ at the top; {rr['legs']}-legged 10 φ stirrups @ {rr['stir'][1]} c/c near the columns"
        f" and @ {rr['stir'][2]} c/c elsewhere.")

    # ------------------------------------------------------------------------------------------------ 15 staircase
    sc = M.get("stair")
    if sc:
        r.h1("15.0 STAIR CASE (M: %d CONCRETE)" % (fckf * 10))
        r.t(f"RL of balcony = {sc['bal'] * 1e3:.0f} mm;  RL of tank roof = {sc['roof'] * 1e3:.0f} mm;  width of staircase = {sc['w'] * 1e3:.0f} mm")
        r.t(f"Staircase is carried on two separate columns of {sc['col']['d']} mm dia spaced at {sc['Lb'] * 1e3:.1f} mm c/c, "
            f"{(sc['xs'] - sc['xc']) * 1e3:.0f} mm from the columns of the staging.")
        r.t(f"There are {sc['treads']} treads ({sc['tread'] * 1e3:.0f} mm wide) and {sc['risers']} risers ({sc['riser1'] * 1e3:.0f} mm high) in each"
            f" flight;  {sc['n1']} flights from GL to balcony and {sc['n2']} flights from balcony to roof.")
        r.h2("Design of Flights / Landings")
        r.t(f"Thickness of waist slab and landing = {sc['waist']} mm;  effective span of flight = {sc['Lb'] * 1e3:.0f} mm;  live load 3 kN/m²")
        r.f("Factored load", "1.5 (self weight + finish + live load)", None, n_(sc["wu"], 2), "kN/m²")
        r.f("Mu", "wu L² / 8", f"{n_(sc['wu'], 2)} x {n_(sc['Lb'], 3)}² / 8", n_(sc["Mu"], 2), "kNm/m")
        r.p(f"Provide {sc['main'][0]} φ @ {sc['main'][1]} c/c as main bars and {sc['dist'][0]} φ @ {sc['dist'][1]} c/c as distribution.")
        r.h2("Landing Beam B1")
        bm = sc["beam"]
        r.t(f"Span from the column of the staging to the staircase column = {sc['L1'] * 1e3:.0f} mm, cantilever {sc['lc'] * 1e3:.0f} mm beyond it.")
        r.f("Mu", "1.5 x (flight + landing reactions and self weight)", None, n_(bm["Mu"], 1), "kNm")
        r.p(f"Provide a {bm['b']} x {bm['d']} mm beam with {bm['top'][0]} - {bm['top'][1]} φ at top and bottom and 8 φ stirrups @ 150 c/c.")
        r.h2("Staircase Columns and Footings")
        cs, ft = sc["col"], sc["footing"]
        r.f("Load on a staircase column P", "reactions of the landings it carries + self weight", None, n_(cs["P"], 0), "kN")
        r.f("Capacity", "0.4 fck Ac + 0.67 fy Asc", None, n_(cs["Pcap"], 0), "kN", f">= 1.5 P = {n_(1.5 * cs['P'], 0)}, OK.")
        r.p(f"Provide {cs['n']} - {cs['dia']} φ tor bars with 8 φ rings @ 200 c/c in each {cs['d']} mm dia column.")
        r.p(f"Provide a {ft['side'] * 1e3:.0f} x {ft['side'] * 1e3:.0f} mm footing, {ft['t']} mm thick at the column tapered to {ft['te']} mm,"
            f" with {ft['bars'][0]} φ @ {ft['bars'][1]} c/c each way.")
    if res["warnings"]:
        r.h1("CHECKS TO LOOK AT")
        for wtxt in res["warnings"]:
            r.t("- " + wtxt)
    return r.out


# ------------------------------------------------------------------------------------------------------- the PDF
def export_pdf(res, path, meta=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.font_manager import FontProperties
    m = meta or {}
    lines = report(res)
    W, H = 8.27, 11.69                          # A4, inches
    top, bot, left = 10.55, 0.85, 0.75
    step = {"h1": 0.30, "h2": 0.24, "gap": 0.12}
    fonts = {"h1": FontProperties(family="DejaVu Sans", weight="bold", size=10.5),
             "h2": FontProperties(family="DejaVu Sans", weight="bold", size=9.5),
             "p": FontProperties(family="DejaVu Sans", size=8.6),
             "x": FontProperties(family="DejaVu Sans", size=8.6)}
    mono = FontProperties(family="DejaVu Sans Mono", size=8.2)
    title = [f"Design of {res['capacity_kl']:g} kL Intze Tank on {res['staging_m']:g} m Staging",
             f"{m.get('name') or 'OHT'}" + (f", {m['scheme']}" if m.get("scheme") else "")]
    foot = "Design for the DPR made by the app (water_app) - to be checked and signed by a structural engineer before construction."
    import textwrap
    wrapped = []
    for kind, text in lines:                    # wrap to the page: ~118 characters of text, ~94 of the formulas
        width = 94 if kind in ("f", "f2", "tm") else 112 if kind == "p" else 118
        parts = textwrap.wrap(text, width) if text else [""]
        for j, part in enumerate(parts):
            wrapped.append((kind if j == 0 else ("f2" if kind in ("f", "f2") else kind), part))
    pages, cur, y = [], [], top
    for kind, text in wrapped:
        h = step.get(kind, 0.19)
        if kind == "h1" and y - h - 0.6 < bot:
            y = bot - 1
        if y - h < bot:
            pages.append(cur)
            cur, y = [], top
        if kind == "h1" and cur:
            y -= 0.1
        cur.append((kind, text, y))
        y -= h
    pages.append(cur)
    with PdfPages(path) as pdf:
        for i, pg in enumerate(pages, 1):
            fig = plt.figure(figsize=(W, H))
            fig.text(W / 2 / W, 11.25 / H, title[0], ha="center", va="center", fontsize=11.5, fontweight="bold")
            fig.text(W / 2 / W, 11.0 / H, title[1], ha="center", va="center", fontsize=9.5)
            fig.add_artist(plt.Line2D([left / W, (W - left) / W], [10.8 / H, 10.8 / H], color="black", linewidth=0.8))
            for kind, text, yy in pg:
                xx = left + {"t1": 0.0, "t2": 0.3, "f": 0.25, "f2": 0.9, "p": 0.25, "tm": 0.25}.get(kind, 0.0)
                if kind in ("h1", "h2"):
                    fig.text(xx / W, yy / H, text, fontproperties=fonts[kind], va="top")
                elif kind == "p":
                    fig.text(xx / W, yy / H, text, fontproperties=fonts["p"], va="top", style="italic", wrap=True)
                elif kind == "gap":
                    continue
                else:
                    fig.text(xx / W, yy / H, text, fontproperties=mono if kind in ("f", "f2", "tm") else fonts["x"], va="top")
            fig.add_artist(plt.Line2D([left / W, (W - left) / W], [0.62 / H, 0.62 / H], color="black", linewidth=0.5))
            fig.text(left / W, 0.45 / H, foot, fontsize=7)
            fig.text((W - left) / W, 0.45 / H, str(i), fontsize=9, ha="right")
            fig.text(left / W, 0.28 / H, f"{datetime.date.today().strftime('%d.%m.%Y')}", fontsize=7)
            pdf.savefig(fig)
            plt.close(fig)
    return path
