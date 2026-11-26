"""Intze design: the bar bending schedule and the quantities."""
import math
from .basics import G, GAMMA_C, TAU_MAX, ZONE_Z, _dome, area, kg_per_m
from .stair import beam_len


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
    r(s, "Size / hoop bars (nominal)", f"{M['top_ring']['b']} x {M['top_ring']['d']} / {M['top_ring']['n']}-{M['top_ring']['dia']}", "mm", "as the example")
    r(s, "Taken by the beam / by the wall's top band", f"{M['top_ring']['P_ring']:.0f} / {M['top_ring']['P_band']:.0f}", "kN", f"beam: its bars x {mat.sst_w:g}; the rest added to the wall's top hoops")
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
        for kind, bm in st["beams"].items():
            sup = {"B1": "column of the staging", "B3": "outer face of the cone / balcony", "B4": "staircase column only",
                   "B5": "top ring beam"}[kind]
            span = f"{bm['L']:.2f} + {st['lc']:.2f}" if kind != "B4" else f"{st['lc']:.2f} + {st['lc']:.2f}"
            r(s, f"Landing beam {kind} ({bm['n']} nos): size / span / bars top, bottom",
              f"{bm['b']} x {bm['d']} / {span} / {bm['top'][0]}-{bm['top'][1]}, {bm['bot'][0]}-{bm['bot'][1]}", "mm / m",
              f"on the {sup}; Mu {bm['Mu']:.0f} kNm; stirrups 8 @ 150")
        br = st["bridge"]
        r(s, "Roof landing carried on to the top ring beam: slab / bars", f"{br['t']} / {br['main'][0]} @ {br['main'][1]}",
          "mm", f"cantilever {br['cant']:.2f} m from B5, Mu {br['Mu']:.1f} kNm/m")
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
        for kind, bm in st["beams"].items():           # B1 / B3 / B4 / B5 (each of its landings)
            Lb_ = beam_len(st, kind)
            add("Staircase", f"S3-{kind}", f"landing beams {kind} ({bm['n']} nos): top bars", bm["top"][1], bm["top"][0] * bm["n"], Lb_ + 0.8, "anchored")
            add("Staircase", f"S3-{kind}b", f"landing beams {kind}: bottom bars", bm["bot"][1], bm["bot"][0] * bm["n"], Lb_ + 0.6, "anchored")
            add("Staircase", f"S4-{kind}", f"landing beams {kind}: stirrups 8 @ 150", 8, Lb_ * 1000 / 150 * bm["n"],
                2 * (bm["b"] + bm["d"] - 4 * opt["cover_stair_mm"]) / 1e3 + 0.2, "closed stirrup")
        br = st["bridge"]
        add("Staircase", "S9", f"roof landing to the top ring beam: top bars {br['main'][0]} @ {br['main'][1]}", br["main"][0],
            (br["span"] + 0.3) * 1000 / br["main"][1], br["cant"] + 0.5, "anchored in B5")
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
        beams = sum(bm["b"] * bm["d"] / 1e6 * beam_len(st, k) * bm["n"] for k, bm in st["beams"].items())
        br = st["bridge"]
        conc["Staircase"] = (nf * (fl + land) + beams + br["t"] / 1e3 * br["span"] * br["cant"]
                             + 2 * area(st["col"]["d"] / 1e3) * st["col"]["H"]
                             + 2 * st["footing"]["side"] ** 2 * (st["footing"]["t"] + st["footing"]["te"]) / 2e3)
    steel = {}
    for r in res["bbs"]:
        steel[r["member"]] = steel.get(r["member"], 0.0) + r["kg"]
    return conc, steel
