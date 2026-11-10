"""E&M design sheets of the water DPR as the Riverside water DPR (U.P. Jal Nigam 2026) p319-361 - user decision
6-Nov-2026: the design gives the cost. One column an operation zone (as DPR p356 / p360), every value a live formula
from sheet EM TS (and the OZ's T3); the norms in column D, yellow (dpr_water.json em_design).

    EMD TW       p357-359 design of drilling and size of pipes: screen / slotted pipe by the vertical velocity, its
                 length by the entrance velocity, the bores, housing pipe, depths; pea gravel
    EMD TW Est   p319-320 unit estimate of a tube well, its quantities from EMD TW -> the rate of a TW (sheet EM)
    EMD HP       p360 H.P. of the motors, p356 capacity of the transformer of a TW and of a booster
    EMD CWR      p350-351 / p361 the CWR pumping plant: power, starting current, transformers, column pipe, delivery,
                 common header, breakers, cables -> its transformers in the sub-station (sheet EM)
    EMD PC       p345-349 power connection with the 11 kV line: a TW, a booster, a CWR
    EMD TR       p352-353 three months trial run: a TW, a CWR pumping plant, a booster

    write(B, T) -> {key: [cell of OZ i]} for sheet EM: "tw" TW (Rs lakh), "pc_tw" / "pc_b" / "pc_c" power
                   connections, "tr_tw" / "tr_c" / "tr_b" trial runs, "tf_kva" / "tf_n" the CWR transformers
"""
PI4 = "PI()/4"


def _next(x, sizes):
    """The first of sizes (ascending) not below x - a nested IF (the last size above it)."""
    f = f"{sizes[-1]:g}"
    for s in reversed(sizes[:-1]):
        f = f"IF({x}<={s:g},{s:g},{f})"
    return f


def _cable(i, table):
    """The smallest cable (sq mm) of table [[sq mm, A]] that carries i amperes."""
    f = f"{table[-1][0]:g}"
    for s, a in reversed(table[:-1]):
        f = f"IF({i}<={a:g},{s:g},{f})"
    return f


def _ov(a, b, lo, hi):
    """Length of [a, b] within [lo, hi]."""
    return f"MAX(0,MIN({b},{hi})-MAX({a},{lo}))"


class Grid:
    """A sheet of rows x one column an OZ: A S.No., B particulars, C unit, D the norm / rate, E... the OZs."""

    def __init__(self, B, name, heading, rate_head="Norm"):
        self.B, self.n = B, len(B.T3)
        self.ws = B.sheet(name, heading, 4 + self.n)
        self.c0 = 5
        self.cols = [B.col(self.c0 + i) for i in range(self.n)]
        B.header(self.ws, 5, ["S.No.", "Particulars", "Unit", rate_head] + [t["zone"]["name"] for t in B.T3],
                 [7, 62, 9, 12] + [13] * self.n)
        self.ws.row_dimensions[5].height = 45
        self.ws.freeze_panes = "E6"
        self.r, self.row = 6, {}

    def head(self, text):
        self.B.cell(self.ws, self.r, 2, text, bold=True)
        self.r += 1

    def rows(self, spec):
        """spec: [(key, no, label, unit, norm, fn(i, c, R, N), fmt)]; R(key) this OZ's cell, N(key) the norm. The
        rows are numbered first, so a formula may use a later row."""
        start = self.r
        for k, item in enumerate(spec):
            self.row[item[0]] = start + k
        for k, (key, no, label, unit, norm, fn, fmt) in enumerate(spec):
            x = start + k
            B, ws = self.B, self.ws
            B.cell(ws, x, 1, no)
            B.cell(ws, x, 2, label)
            B.cell(ws, x, 3, unit)
            B.cell(ws, x, 4, norm, fmt=fmt if isinstance(norm, (int, float)) else None,
                   inp=isinstance(norm, (int, float)) and not isinstance(norm, bool))
            for i, c in enumerate(self.cols):
                R = (lambda c_: lambda kk: f"{c_}{self.row[kk]}")(c)
                N = lambda kk: f"$D${self.row[kk]}"
                v = fn(i, c, R, N) if fn else None
                if v is not None:
                    B.cell(ws, x, self.c0 + i, v, fmt=fmt)
        self.r = start + len(spec)

    def cell(self, key, i):
        return f"'{self.ws.title}'!${self.cols[i]}${self.row[key]}"

    def note(self, text):
        self.ws.cell(self.r + 1, 2, text).font = self.B.italic
        self.r += 2


def _f(s):
    return "=" + s


def tw_design(B, T, E):
    D = E["tw"]
    g = Grid(B, "EMD TW", "DESIGN OF DRILLING AND SIZE OF PIPES FOR CONSTRUCTION OF TUBE WELL, PEA GRAVEL "
                          "(Riverside water DPR p357-359)")
    nx = lambda x: _next(x, D["pipe_sizes"])
    g.head("Discharge")
    g.rows([("n", 1, "New tube wells of the OZ, standby too (sheet EM TS)", "nos", None, lambda i, c, R, N: _f(T("tw", i)), "#,##0"),
            ("lpm", 2, "Discharge required of a tube well (sheet TW)", "LPM", None, lambda i, c, R, N: _f(T("q", i)),
             "#,##0"),
            ("m3h", 3, "Qty. pumped an hour = Q (LPM) x 60 / 1000", "m3/hr", None,
             lambda i, c, R, N: f"={R('lpm')}*60/1000", "#,##0.00"),
            ("q", 4, "Qty. pumped a second = Q (LPM) / (60 x 1000)", "m3/sec", None,
             lambda i, c, R, N: f"={R('lpm')}/60000", "0.0000")])
    g.head("(A) Size of pipes (screen / slotted pipes): vertical velocity = Q / (PI x D^2 / 4)")
    g.rows([("v150", 1, "Vertical velocity in 150 mm dia", "m/sec", None,
             lambda i, c, R, N: f"={R('q')}/({PI4}*0.15^2)", "0.000"),
            ("v200", 2, "Vertical velocity in 200 mm dia", "m/sec", None,
             lambda i, c, R, N: f"={R('q')}/({PI4}*0.2^2)", "0.000"),
            ("v300", 3, "Vertical velocity in 300 mm dia", "m/sec", None,
             lambda i, c, R, N: f"={R('q')}/({PI4}*0.3^2)", "0.000"),
            ("vmax", 4, "Permissible vertical velocity (0.6 to 1.2 m/s)", "m/sec", D["max_vertical_v"], None, "0.00"),
            ("small", 5, "150 mm dia up to this discharge (DPR: 150 mm for 1000 LPM, 200 mm for 1200-1500 LPM - "
                         "longer life of the T.W.)", "LPM", D["small_screen_upto_lpm"], None, "#,##0"),
            ("dia", 6, "Size of screen / slotted pipe selected", "mm", None,
             lambda i, c, R, N: f"=IF(AND({R('lpm')}<={N('small')},{R('v150')}<={N('vmax')}),150,"
                                f"IF({R('v200')}<={N('vmax')},200,300))", "#,##0"),
            ("v", 7, "Vertical velocity in the pipe selected", "m/sec", None,
             lambda i, c, R, N: f"={R('q')}/({PI4}*({R('dia')}/1000)^2)", "0.000")])
    g.head("(B) Length of slotted pipe: slot 3/64\" x 3\"")
    g.rows([("open", 1, "Opening area", "", D["open_area"], None, "0%"),
            ("cc", 2, "Contraction coefficient", "", D["contraction"], None, "0.00"),
            ("a", 3, "Effective opening area for one metre length = PI x D x opening x contraction", "sqm", None,
             lambda i, c, R, N: f"=PI()*{R('dia')}/1000*{N('open')}*{N('cc')}", "0.0000"),
            ("vemax", 4, "Max. permissible entrance velocity (IS code)", "m/sec", D["entrance_v_max"], None, "0.000"),
            ("ve", 5, "Entrance velocity designed (longer life of the tube well)", "m/sec", D["entrance_v"], None,
             "0.000"),
            ("area", 6, "Total open area required = Q / designed velocity", "sqm", None,
             lambda i, c, R, N: f"={R('q')}/{N('ve')}", "0.00"),
            ("eff", 7, "Effective length of slotted pipe = open area / effective opening area a metre", "m", None,
             lambda i, c, R, N: f"={R('area')}/{R('a')}", "0.00"),
            ("ends", 8, "Additional length: plain length of 0.30 m at both ends of 7 pipes of 6 m (as DPR p358)", "m",
             D["plain_ends_m"], lambda i, c, R, N: f"={N('ends')}", "0.00"),
            ("sl", 9, "Total length of slotted pipe required", "m", None,
             lambda i, c, R, N: f"={R('eff')}+{R('ends')}", "0.00"),
            ("pl", 10, "Length of a pipe", "m", D["pipe_length_m"], None, "0"),
            ("slot", 11, "Say (whole pipes)", "m", None, lambda i, c, R, N: f"=CEILING({R('sl')},{N('pl')})", "#,##0")])
    g.head("(C) Drilling size")
    g.rows([("od", 1, "O.D. of screen pipe = size + wall", "mm", D["od_add_mm"],
             lambda i, c, R, N: f"={R('dia')}+{N('od')}", "0.0"),
            ("shroud", 2, "Thickness of gravel shroud around the screen (norms 13 to 18 cm)", "mm", D["shroud_mm"], None,
             "#,##0"),
            ("bore_s", 3, "Bore dia for the screen = O.D. + 2 x shroud", "mm", None,
             lambda i, c, R, N: f"={R('od')}+2*{N('shroud')}", "0.0"),
            ("round", 4, "Bore sizes in steps of", "mm", D["bore_round_mm"], None, "#,##0"),
            ("bs", 5, "Size of bore for the screen / plain pipe", "mm", None,
             lambda i, c, R, N: f"=CEILING({R('bore_s')},{N('round')})", "#,##0")])
    g.head("(D) Size of housing pipe")
    g.rows([("pump", 1, "Alternative I: outer dia of the submersible pump (1000-1500 LPM) in general", "mm",
             D["pump_od_mm"], None, "#,##0"),
            ("col", 2, "Alternative II: flanged column pipe used for the pump", "mm", D["column_pipe_mm"], None, "#,##0"),
            ("bowl", 3, "Alternative III: bowl dia of the 3 cusec O.P. unit for development", "mm", D["op_bowl_mm"], None,
             "#,##0"),
            ("vert", 4, "Verticality tolerance (100 mm in 30 m length in one plane, IS)", "mm", D["verticality_mm"], None,
             "#,##0"),
            ("hreq", 5, "Housing required = the largest of I-III + tolerance", "mm", None,
             lambda i, c, R, N: f"=MAX({N('pump')},{N('col')},{N('bowl')})+{N('vert')}", "#,##0"),
            ("hd", 6, "Size of housing pipe selected", "mm", None,
             lambda i, c, R, N: "=MAX(" + R("dia") + "," + nx(R("hreq")) + ")", "#,##0"),
            ("hod", 7, "O.D. of housing pipe", "mm", None, lambda i, c, R, N: f"={R('hd')}+{N('od')}", "0.0"),
            ("bh", 8, "Size of bore for the housing pipe = CEILING(O.D. + 2 x shroud)", "mm", None,
             lambda i, c, R, N: f"=CEILING({R('hod')}+2*{N('shroud')},{N('round')})", "#,##0")])
    g.head("(E) Depth of tube well (lengths as the quantities of DPR p319-320)")
    g.rows([("lh", 1, "Housing pipe (from G.L.)", "m", D["housing_m"], lambda i, c, R, N: f"={N('lh')}", "#,##0"),
            ("la", 2, "Lowering of tube well assembly", "m", D["assembly_m"], lambda i, c, R, N: f"={N('la')}", "#,##0"),
            ("lp", 3, "Plain / slotted pipe = assembly - housing", "m", None,
             lambda i, c, R, N: f"={R('la')}-{R('lh')}", "#,##0"),
            ("share", 4, "Slotted pipe at most this share of the plain pipe (SOR 4)", "", D["slotted_max_share"],
             lambda i, c, R, N: f'=IF({R("slot")}<={N("share")}*({R("lp")}-{R("slot")}),"OK","more than the share")',
             "0%"),
            ("ext", 5, "Drilling deeper than the assembly (settlement of bore mud, falling strata)", "", D["drill_extra"],
             None, "0%"),
            ("dstep", 6, "Drilling depth in steps of", "m", D["drill_round_m"], None, "#,##0"),
            ("dd", 7, "Drilling depth of tube well bore", "m", None,
             lambda i, c, R, N: f"=CEILING({R('la')}*(1+{N('ext')}),{N('dstep')})", "#,##0"),
            ("hx", 8, "Bore of the housing size below the housing pipe", "m", D["upper_bore_extra_m"], None, "#,##0"),
            ("hb", 9, "Depth of the bore of the housing size", "m", None, lambda i, c, R, N: f"={R('lh')}+{N('hx')}",
             "#,##0")])
    g.head("(F) Calculation of pea gravel (DPR p357)")
    g.rows([("vb", 1, "Volume of bore = PI / 4 x (D housing bore^2 x its depth + D screen bore^2 x the rest)", "m3",
             None, lambda i, c, R, N: f"={PI4}*(({R('bh')}/1000)^2*{R('hb')}+({R('bs')}/1000)^2*({R('dd')}-{R('hb')}))",
             "0.00"),
            ("va", 2, "Volume of T.W. assembly = PI / 4 x (D housing^2 x its length + D screen^2 x the rest)", "m3",
             None, lambda i, c, R, N: f"={PI4}*(({R('hd')}/1000)^2*{R('lh')}+({R('dia')}/1000)^2*{R('lp')})", "0.00"),
            ("vg", 3, "Volume of gravel = bore - assembly", "m3", None, lambda i, c, R, N: f"={R('vb')}-{R('va')}",
             "0.00"),
            ("cav", 4, "Caving (fine sand strata)", "", D["caving"], lambda i, c, R, N: f"={R('vg')}*{N('cav')}",
             "0.00"),
            ("dev", 5, "During development of T.W. by compressor & O.P. unit", "m3", D["development_gravel_m3"],
             lambda i, c, R, N: f"={N('dev')}", "0.00"),
            ("pg", 6, "Pea gravel required", "m3", None, lambda i, c, R, N: f"={R('vg')}+{R('cav')}+{R('dev')}", "0.00"),
            ("gravel", 7, "Say", "m3", None, lambda i, c, R, N: f"=ROUNDUP({R('pg')},0)", "#,##0")])
    g.note("Riverside water DPR p357-359 (Construction Division E&M, U.P. Jal Nigam): the method and norms; the lengths "
           "as the quantities of its unit estimate p319-320 (housing 60 m, assembly 190 m, drilling 210 m; its text "
           "180 / 200 m). Column D yellow: norms to be confirmed.")
    B.sign(g.ws, g.r + 2, 4 + len(B.T3))
    return g


def tw_estimate(B, T, E, d):
    R_ = E["tw_rates"]
    g = Grid(B, "EMD TW Est", "UNIT ESTIMATE FOR TUBE WELL CONSTRUCTION & DEVELOPMENT (Riverside water DPR p319-320; "
                              "quantities from sheet EMD TW)", "Rate (Rs)")
    D = lambda k, i: d.cell(k, i)
    g.head("Design (sheet EMD TW)")
    g.rows([("lpm", "", "Proposed discharge", "LPM", None, lambda i, c, R, N: _f(D("lpm", i)), "#,##0"),
            ("hd", "", "Proposed dia of housing pipe", "mm", None, lambda i, c, R, N: _f(D("hd", i)), "#,##0"),
            ("dia", "", "Proposed dia of plain / slotted pipe", "mm", None, lambda i, c, R, N: _f(D("dia", i)), "#,##0"),
            ("lh", "", "Housing pipe", "m", None, lambda i, c, R, N: _f(D("lh", i)), "#,##0"),
            ("la", "", "Proposed depth of tube well (assembly)", "m", None, lambda i, c, R, N: _f(D("la", i)), "#,##0"),
            ("dd", "", "Proposed drilling depth", "m", None, lambda i, c, R, N: _f(D("dd", i)), "#,##0"),
            ("hb", "", "Bore of the housing size to", "m", None, lambda i, c, R, N: _f(D("hb", i)), "#,##0"),
            ("bh", "", "Bore for the housing pipe", "mm", None, lambda i, c, R, N: _f(D("bh", i)), "#,##0"),
            ("bs", "", "Bore for the plain / slotted pipe", "mm", None, lambda i, c, R, N: _f(D("bs", i)), "#,##0")])
    g.r += 1
    first = g.r
    items = {it[2]: it for it in R_["items"]}
    fixed = lambda no, as_=None: (f"f{no}", as_ or no, items[no][3], items[no][4], items[no][6],
                                  (lambda q_: lambda i, c, R, N: q_)(items[no][5]), "#,##0.00")
    band = R_["band_m"]
    bands = [("upto 100 m", 0, band), ("below 100 m", band, 100000)]
    g.head("1  TRANSPORTATION")
    g.rows([fixed("1.1")])
    g.head("1.2  TUBE WELL ASSEMBLY: M.S. tube well assembly with all parts like plain pipe, slotted pipe (up to 50 % of "
           "plain pipes), rings, well cap, bail plug, clamp, reducer, central guide, support structure etc.")
    g.rows([(f"p{s}", f"1.2.{k}", f"{s} mm dia M.S. pipe (housing / plain / slotted)", "mtr", R_["pipe"][s],
             (lambda s_: lambda i, c, R, N: f"=IF({R('hd')}={s_},{R('lh')},0)+IF({R('dia')}={s_},{R('la')}-{R('lh')},0)")(s),
             "#,##0.00")
            for k, s in enumerate(sorted(R_["pipe"], key=int), 1)])
    g.head("2  CONSTRUCTION OF TUBE WELL (DRILLING): erection of rig machine and drilling work")
    spec, k = [], 0
    for b, lo, hi in bands:
        for dm, rate in sorted(R_["drill"][b].items(), key=lambda t: int(t[0])):
            k += 1
            spec.append((f"d{dm}{lo}", f"2.1.{k}", f"Drilling of {dm} mm dia bore, {b} BGL", "m", rate,
                         (lambda dm_, lo_, hi_: lambda i, c, R, N:
                          f"=IF({R('bh')}={dm_},{_ov(0, R('hb'), lo_, hi_)},0)+"
                          f"IF({R('bs')}={dm_},{_ov(R('hb'), R('dd'), lo_, hi_)},0)")(dm, lo, hi), "#,##0.00"))
    spec += [fixed("2.1.4", f"2.1.{k + 1}"), fixed("2.1.5", f"2.1.{k + 2}")]
    g.rows(spec)
    g.head("2.2  LOWERING OF TUBE WELL ASSEMBLY AND SHROUDING OF T.W. BY GRAVEL")
    spec, k = [], 0
    for b, lo, hi in bands:
        for dm, rate in sorted(R_["lower"][b].items(), key=lambda t: int(t[0])):
            k += 1
            spec.append((f"l{dm}{lo}", f"2.2.{k}", f"Lowering of {dm} mm dia M.S.E.R.W. pipe, {b}", "m", rate,
                         (lambda dm_, lo_, hi_: lambda i, c, R, N:
                          f"=IF({R('hd')}={dm_},{_ov(0, R('lh'), lo_, hi_)},0)+"
                          f"IF({R('dia')}={dm_},{_ov(R('lh'), R('la'), lo_, hi_)},0)")(dm, lo, hi), "#,##0.00"))
    spec.append(fixed("2.2.4", f"2.2.{k + 1}"))
    g.rows(spec)
    g.head("3  PEA GRAVEL")
    g.rows([("gr", "3", "1.60 mm to 4.80 mm size pea gravel duly screened, washed and stacked at site (sheet EMD TW)",
             "m3", R_["gravel"], lambda i, c, R, N: _f(D("gravel", i)), "#,##0.00")])
    g.head("4  DEVELOPMENT OF TUBE WELL")
    g.rows([fixed(n) for n in ("4.1.1", "4.1.2", "4.1.3", "4.1.4", "4.2.1", "4.2.2", "4.2.3")])
    g.head("5  TEST")
    g.rows([fixed(n) for n in ("5.1", "5.2", "5.3")])
    last = g.r - 1
    g.rows([("rs", "", "Grand total (Rs) = rates x quantities", "Rs", None,
             lambda i, c, R, N: f"=SUMPRODUCT($D${first}:$D${last},{c}{first}:{c}{last})", "#,##0.00"),
            ("lakh", "", "Say (Rs lakh) - a tube well", "lakh", None, lambda i, c, R, N: f"=ROUND({R('rs')}/100000,2)",
             "#,##0.00")])
    for c in range(1, 5 + len(B.T3)):
        g.ws.cell(g.row["lakh"], c).font = B.bold
    g.note("Rates: Riverside water DPR p319-320 = SOR of the CE (E/M) U.P. Jal Nigam p362-364 (drilling 1.2 / 1.3, "
           "lowering 5.1 / 5.2, pea gravel 12.10 Springfield, development 6.2 / 6.4); the M.S. assembly at the SOR x 1.35 "
           "as the DPR (150 mm by the same ratio); drilling and lowering below 100 m at the 101-200 m rates, as the DPR. "
           "Quantities: per tube well, from the design (sheet EMD TW).")
    B.sign(g.ws, g.r + 2, 4 + len(B.T3))
    return g


def hp_transformer(B, T, E):
    L = E["load"]
    g = Grid(B, "EMD HP", "CALCULATION OF H.P. OF MOTOR AND CAPACITY OF TRANSFORMER - TUBE WELLS AND BOOSTERS "
                          "(Riverside water DPR p356, p360)")
    nr = lambda x: _next(x, L["ratings"])
    t3 = lambda i, k, off=0: f"{_q(B.T3[i]['sheet'])}!$F${B.T3[i]['ref'][k] + off}"
    g.head("A. Tube well pumping plant (the OZ's T6, design of pumping plant)")
    g.rows([("h", 1, "Total head for pumping", "m", None, lambda i, c, R, N: _f(t3(i, "head")), "#,##0.00"),
            ("q", 2, "Discharge", "LPM", None, lambda i, c, R, N: _f(t3(i, "head", 1)), "#,##0"),
            ("eff", 3, "Assuming efficiency of pump", "", None, lambda i, c, R, N: _f(t3(i, "head", 3)), "0%"),
            ("whp", 4, "W.H.P. = Q x H / 4500", "HP", None, lambda i, c, R, N: _f(t3(i, "head", 2)), "#,##0.00"),
            ("bhp", 5, "B.H.P. of pump = W.H.P. / efficiency", "HP", None, lambda i, c, R, N: _f(t3(i, "head", 4)),
             "#,##0.00"),
            ("kw", 6, "B.H.P. in kW (x 0.746)", "kW", None, lambda i, c, R, N: f"={R('bhp')}*0.746", "#,##0.00"),
            ("m", 7, "Multiplying factor as per CPHEEO manual (margin by kW)", "", None,
             lambda i, c, R, N: f"=1+{t3(i, 'head', 5)}", "0.00"),
            ("thp", 8, "Total H.P.", "HP", None, lambda i, c, R, N: _f(t3(i, "head", 6)), "#,##0.00"),
            ("hp", 9, "Next available higher size (motor)", "HP", None, lambda i, c, R, N: _f(T("hp", i)), "#,##0")])
    g.head("B. Capacity of transformer of a tube well")
    g.rows([("tkw", 1, "H.P. of motor in kW (x 0.746)", "kW", None, lambda i, c, R, N: f"={R('hp')}*0.746", "#,##0.00"),
            ("lf", 2, "Load of light & fan", "kW", L["light_fan_kw"], lambda i, c, R, N: f"={N('lf')}", "#,##0.00"),
            ("tot", 3, "Total kW", "kW", None, lambda i, c, R, N: f"={R('tkw')}+{R('lf')}", "#,##0.00"),
            ("pf", 4, "Load in kVA (power factor)", "kVA", L["pf"], lambda i, c, R, N: f"={R('tot')}/{N('pf')}",
             "#,##0.00"),
            ("mg", 5, "Additional load for safety", "", L["margin"], lambda i, c, R, N: f"={R('pf')}*{N('mg')}",
             "#,##0.00"),
            ("kva", 6, "Required kVA", "kVA", None, lambda i, c, R, N: f"={R('pf')}+{R('mg')}", "#,##0.00"),
            ("tr", 7, "Next available rating of transformer as per departmental", "kVA", None,
             lambda i, c, R, N: "=" + nr(R("kva")), "#,##0"),
            ("load", 8, "Load for the power connection (whole kVA)", "kVA", None,
             lambda i, c, R, N: f"=ROUNDUP({R('kva')},0)", "#,##0")])
    g.head("C. Booster pumping plant (VFD pumps of the design, sheet EM TS)")
    g.rows([("bh", 1, "Head of the booster", "m", None, lambda i, c, R, N: _f(T("vh", i)), "#,##0.00"),
            ("bq", 2, "Discharge, peak", "L/s", None, lambda i, c, R, N: _f(T("vq", i)), "#,##0.00"),
            ("bkw", 3, "Power of the pumps (design)", "kW", None, lambda i, c, R, N: _f(T("vkw", i)), "#,##0.00"),
            ("bw", 4, "Pumps working", "nos", None, lambda i, c, R, N: _f(T("bw", i)), "#,##0"),
            ("bmhp", 5, "Motor of a pump (CPHEEO margin, next 5 HP)", "HP", None, lambda i, c, R, N: _f(T("bhp", i)),
             "#,##0"),
            ("btkw", 6, "Motors working in kW (x 0.746)", "kW", None,
             lambda i, c, R, N: f"={R('bw')}*{R('bmhp')}*0.746", "#,##0.00"),
            ("btot", 7, "Total kW with light & fan", "kW", None,
             lambda i, c, R, N: f"=IF({R('bw')}>0,{R('btkw')}+{N('lf')},0)", "#,##0.00"),
            ("bkva", 8, "Required kVA = kW / pf x (1 + additional)", "kVA", None,
             lambda i, c, R, N: f"={R('btot')}/{N('pf')}*(1+{N('mg')})", "#,##0.00"),
            ("btr", 9, "Next available rating of transformer", "kVA", None,
             lambda i, c, R, N: f"=IF({R('bw')}>0," + nr(R("bkva")) + ",0)", "#,##0"),
            ("bload", 10, "Load for the power connection (whole kVA)", "kVA", None,
             lambda i, c, R, N: f"=ROUNDUP({R('bkva')},0)", "#,##0")])
    g.note("Margin of safety for the motor as per CPHEEO (Riverside water DPR p360): up to 1.5 kW 50 %, 1.5-3.7 kW 40 %, "
           "3.7-7.5 kW 30 %, 7.5-15 kW 20 %, 15-75 kW 15 %, above 75 kW 10 %. Departmental transformer ratings: "
           + ", ".join(f"{x:g}" for x in L["ratings"]) + " kVA.")
    B.sign(g.ws, g.r + 2, 4 + len(B.T3))
    return g


def _q(name):
    from .dpr import q
    return q(name)


def cwr(B, T, E, hp):
    C, L, P = E["cwr_el"], E["load"], E["cwr_pipe"]
    eff = B.S["em"]["rules"]["cwr_efficiency"]
    from .dpr import motor_margin
    g = Grid(B, "EMD CWR", "TECHNICAL STATEMENT - CWR PUMPING PLANT: POWER, TRANSFORMER, PIPES, BREAKERS, CABLES "
                           "(Riverside water DPR p350-351, p361)")
    nr = lambda x: _next(x, L["ratings"])
    ns = lambda x: _next(x, P["sizes"])
    has = lambda R: f"{R('w')}>0"
    g.head("A. Pumps (sheet EM TS)")
    g.rows([("w", 1, "Pumps working", "nos", None, lambda i, c, R, N: _f(T("cw", i)), "#,##0"),
            ("s", 2, "Pumps standby", "nos", None, lambda i, c, R, N: _f(T("cs", i)), "#,##0"),
            ("lps", 3, "Discharge of a pump", "L/s", None, lambda i, c, R, N: _f(T("cq", i)), "#,##0.00"),
            ("lpm", 4, "Discharge of a pump", "LPM", None, lambda i, c, R, N: f"={R('lps')}*60", "#,##0"),
            ("h", 5, "Total head (static, terminal, sump, losses - T14 C.6)", "m", None, lambda i, c, R, N: _f(T("ch", i)),
             "#,##0.00"),
            ("whp", 6, "B.H.P. = discharge (LPM) x head x specific gravity 1 / 4500", "HP", None,
             lambda i, c, R, N: f"={R('lpm')}*{R('h')}/4500", "#,##0.00"),
            ("eff", 7, "Efficiency of pump", "", eff, lambda i, c, R, N: f"={N('eff')}", "0%"),
            ("bhp", 8, "B.H.P. input to pump = B.H.P. / efficiency", "HP", None,
             lambda i, c, R, N: f"=IF({has(R)},{R('whp')}/{R('eff')},0)", "#,##0.00"),
            ("bkw", 9, "B.kW to pump (x 0.746)", "kW", None, lambda i, c, R, N: f"={R('bhp')}*0.746", "#,##0.00"),
            ("mg", 10, "Margin as per manual (CPHEEO, by kW)", "", None,
             lambda i, c, R, N: f"=IF({has(R)}," + motor_margin(B.S["pump"], R("bkw")) + ",0)", "0%"),
            ("req", 11, "Required H.P. of motor", "HP", None, lambda i, c, R, N: f"={R('bhp')}*(1+{R('mg')})", "#,##0.00"),
            ("hp", 12, "Next commercial rating of motor (sheet EM TS)", "HP", None, lambda i, c, R, N: _f(T("chp", i)),
             "#,##0")])
    g.head("H. Calculation of power")
    g.rows([("lhp", 1, "Load of the working pumps", "HP", None, lambda i, c, R, N: f"={R('w')}*{R('hp')}", "#,##0.00"),
            ("lkw", 2, "Load in kW (x 0.746)", "kW", None, lambda i, c, R, N: f"={R('lhp')}*0.746", "#,##0.00"),
            ("pf", 3, "Power factor", "", C["pf"], None, "0.00"),
            ("me", 4, "Motor efficiency", "", C["motor_eff"], None, "0%"),
            ("in", 5, "Incoming load = kW / (pf x motor efficiency)", "kVA", None,
             lambda i, c, R, N: f"={R('lkw')}/({N('pf')}*{N('me')})", "#,##0.00"),
            ("misc", 6, "Miscellaneous load", "kVA", C["misc_kva"], lambda i, c, R, N: f"=IF({has(R)},{N('misc')},0)",
             "#,##0.00"),
            ("tl", 7, "Total load", "kVA", None, lambda i, c, R, N: f"=ROUNDUP({R('in')}+{R('misc')},0)", "#,##0")])
    g.head("Check for starting current")
    g.rows([("lt", 1, "LT voltage", "kV", C["lt_kv"], None, "0.0"),
            ("fe", 2, "Efficiency in the full load current", "", C["flc_eff"], None, "0%"),
            ("flc", 3, "Full load current of one motor = required HP x 0.746 / (1.7321 x kV x pf x efficiency)", "A",
             None, lambda i, c, R, N: f"={R('req')}*0.746/(1.7321*{N('lt')}*{N('pf')}*{N('fe')})", "#,##0.00"),
            ("aux", 4, "Current of auxiliary load = misc. kVA / kV / 1.7321", "A", None,
             lambda i, c, R, N: f"={R('misc')}/{N('lt')}/1.7321", "#,##0.00"),
            ("run", 5, "Total current when one pump runs", "A", None, lambda i, c, R, N: f"={R('flc')}+{R('aux')}",
             "#,##0.00"),
            ("sf", 6, "Starting current of the second pump, times the full load current", "", C["start_factor"], None,
             "0.0"),
            ("st", 7, "Total current when the second starts (one running + starting + aux.)", "A", None,
             lambda i, c, R, N: f"={R('flc')}*(1+{N('sf')})+{R('aux')}", "#,##0.00")])
    g.head("I. Transformer capacity (peak efficiency at about 75 % of the rating: margin 20 %)")
    g.rows([("mgn", 1, "Margin", "", L["margin"], None, "0%"),
            ("pk", 2, "Total peak load with the margin", "kVA", None, lambda i, c, R, N: f"={R('tl')}*(1+{N('mgn')})",
             "#,##0.00"),
            ("r1", 3, "Next commercial rating", "kVA", None, lambda i, c, R, N: f"=IF({has(R)}," + nr(R("pk")) + ",0)",
             "#,##0"),
            ("e1", 4, "Check for efficiency = peak / rating", "", None,
             lambda i, c, R, N: f"=IF({R('r1')}>0,{R('pk')}/{R('r1')},0)", "0%"),
            ("skva", 5, "Starting load = 1.7321 x kV x starting current", "kVA", None,
             lambda i, c, R, N: f"=1.7321*{N('lt')}*{R('st')}", "#,##0.00"),
            ("ov", 6, "Short duration over loading the transformers are designed for", "", C["overload"], None, "0%"),
            ("r2", 7, "Rating for the starting load = next rating of starting kVA / (1 + over loading)", "kVA", None,
             lambda i, c, R, N: f"=IF({has(R)}," + nr(f"{R('skva')}/(1+{N('ov')})") + ",0)", "#,##0"),
            ("kva", 8, "Selected rating of transformer (11 / 0.4 kV)", "kVA", None,
             lambda i, c, R, N: f"=MAX({R('r1')},{R('r2')})", "#,##0"),
            ("e2", 9, "Check: starting load / selected rating", "", None,
             lambda i, c, R, N: f"=IF({R('kva')}>0,{R('skva')}/{R('kva')},0)", "0%"),
            ("n", 10, "Transformers (1 W + 1 S)", "nos", C["transformers"], lambda i, c, R, N: f"=IF({has(R)},{N('n')},0)",
             "#,##0"),
            ("pc", 11, "Load for the power connection (to 10 kVA, as DPR p346: 140 kVA for 136.80)", "kVA", None,
             lambda i, c, R, N: f"=CEILING({R('pk')},{E['pc']['cwr_round_kva']})", "#,##0")])
    g.head("K. Pipes (velocity, CPHEEO; DPR p351, p361)")
    g.rows([("vs", 1, "Column / suction pipe of a pump: design velocity (1.8-2.6 m/s)", "m/s", P["suction_v"], None,
             "0.00"),
            ("ds", 2, "Dia = SQRT(4 Q / (PI x V))", "mm", None,
             lambda i, c, R, N: f"=SQRT(4*{R('lps')}/1000/(PI()*{N('vs')}))*1000", "#,##0.00"),
            ("cs", 3, "Say (commercial size)", "mm", None, lambda i, c, R, N: f"=IF({has(R)}," + ns(R("ds")) + ",0)",
             "#,##0"),
            ("vd", 4, "Delivery pipe of a pump: design velocity (2.0-2.5 m/s)", "m/s", P["delivery_v"], None, "0.00"),
            ("dd", 5, "Dia = SQRT(4 Q / (PI x V))", "mm", None,
             lambda i, c, R, N: f"=SQRT(4*{R('lps')}/1000/(PI()*{N('vd')}))*1000", "#,##0.00"),
            ("cd", 6, "Say (commercial size)", "mm", None, lambda i, c, R, N: f"=IF({has(R)}," + ns(R("dd")) + ",0)",
             "#,##0"),
            ("vh", 7, "Common header (the working pumps): design velocity", "m/s", P["header_v"], None, "0.00"),
            ("dh", 8, "Dia = SQRT(4 Q / (PI x V))", "mm", None,
             lambda i, c, R, N: f"=SQRT(4*{R('w')}*{R('lps')}/1000/(PI()*{N('vh')}))*1000", "#,##0.00"),
            ("ch", 9, "Say (commercial size)", "mm", None, lambda i, c, R, N: f"=IF({has(R)}," + ns(R("dh")) + ",0)",
             "#,##0")])
    g.head("N. Capacity of breakers")
    g.rows([("scf", 1, "Short circuit current of motor = full load current x", "", C["sc_factor"], None, "0"),
            ("sc", 2, "Short circuit current of motor", "kA", None, lambda i, c, R, N: f"={R('flc')}*{N('scf')}/1000",
             "0.00"),
            ("ilt", 3, "LT side current = rating / (1.7321 x LT kV)", "A", None,
             lambda i, c, R, N: f"={R('kva')}/(1.7321*{N('lt')})", "#,##0.00"),
            ("bf", 4, "Rating of breaker = current x", "", C["breaker_factor"], None, "0.00"),
            ("ib", 5, "Rating of LT side breaker", "A", None, lambda i, c, R, N: f"={R('ilt')}*{N('bf')}", "#,##0.00"),
            ("acb", 6, "Next commercial rating of ACB", "A", None,
             lambda i, c, R, N: f"=IF({has(R)}," + _next(R("ib"), C["acb"]) + ",0)", "#,##0"),
            ("ht", 7, "HT voltage", "kV", C["ht_kv"], None, "0"),
            ("iht", 8, "HT side current = rating / (1.7321 x HT kV); VCB 630 A, 12.5 kA or better", "A", None,
             lambda i, c, R, N: f"={R('kva')}/(1.7321*{N('ht')})", "#,##0.00"),
            ("im", 9, "Rating of motor side breaker = full load current x factor", "A", None,
             lambda i, c, R, N: f"={R('flc')}*{N('bf')}", "#,##0.00"),
            ("mccb", 10, "Next commercial rating of MCCB", "A", None,
             lambda i, c, R, N: f"=IF({has(R)}," + _next(R("im"), C["mccb"]) + ",0)", "#,##0")])
    al, cu = C["al_cable"], C["cu_cable"]
    g.head("O. Cable size (3.5 core XLPE armoured; ampacities in the note - indicative)")
    g.rows([("dr", 1, "Derating factor", "", C["derate"], None, "0.00"),
            ("ia", 2, "LT incoming current with derating = LT current / factor", "A", None,
             lambda i, c, R, N: f"={R('ilt')}/{N('dr')}", "#,##0.00"),
            ("runs", 3, "LT transformer side cable: runs", "R", None,
             lambda i, c, R, N: f"=IF({has(R)},ROUNDUP({R('ia')}/{al[-1][1]:g},0),0)", "#,##0"),
            ("alc", 4, "LT transformer side cable: Al, a run", "sq mm", None,
             lambda i, c, R, N: f"=IF({has(R)}," + _cable(f"{R('ia')}/{R('runs')}", al) + ",0)", "#,##0"),
            ("im2", 5, "Motor side current with derating = full load current / factor", "A", None,
             lambda i, c, R, N: f"={R('flc')}/{N('dr')}", "#,##0.00"),
            ("cmin", 6, "Motor side cable at least (as DPR p351)", "sq mm", C["cu_min_sqmm"], None, "0"),
            ("cuc", 7, "Motor side cable up to the pump monitoring unit: Cu", "sq mm", None,
             lambda i, c, R, N: f"=IF({has(R)},MAX({N('cmin')}," + _cable(R("im2"), cu) + "),0)", "#,##0")])
    g.note("Cable ampacities used (A, 3.5 core XLPE armoured, in air - indicative, to be confirmed): Al "
           + ", ".join(f"{s:g} sq mm {a:g}" for s, a in al) + "; Cu " + ", ".join(f"{s:g} sq mm {a:g}" for s, a in cu)
           + ". HT cable (11 kV) as per requirement. Riverside water DPR p350-351 (CWR pumping plant 2 W + 1 S): the "
             "same steps; its full load current uses the required H.P. (42.64 HP: 60.40 A), its transformer 160 kVA "
             "(2 nos, 1 W + 1 S), ACB 315 A, MCCB 125 A, cables 150 (written 140) sq mm Al and 25 sq mm Cu.")
    B.sign(g.ws, g.r + 2, 4 + len(B.T3))
    return g


def power(B, T, E, hp, cw):
    P = E["pc"]
    g = Grid(B, "EMD PC", "ESTIMATE FOR POWER CONNECTION TRANSMISSION LINE - TUBE WELL, BOOSTER, CWR (Riverside water "
                          "DPR p345-349)", "Rate (Rs)")
    H = lambda k, i: hp.cell(k, i)
    out = {}

    def block(tag, title, gate, load, items, line_m):
        g.head(title)
        g.rows([(f"{tag}g", "", "Provided (1 / 0)", "", None, lambda i, c, R, N: "=" + gate(i), "0"),
                (f"{tag}kva", "", "Load (sheet " + ("EMD CWR" if tag == "c" else "EMD HP") + ")", "kVA", None,
                 lambda i, c, R, N: "=" + load(i), "#,##0"),
                (f"{tag}m", "", "Length of the 11 kV line (site) - yellow", "m", None,
                 lambda i, c, R, N: line_m, "#,##0")])
        for i, c in enumerate(g.cols):
            g.ws.cell(g.row[f"{tag}m"], g.c0 + i).fill = B.yellow
        first = g.r
        spec = [(f"{tag}{k}", k + 1, text, unit, rate, fn, "#,##0.00") for k, (text, unit, rate, fn) in enumerate(items)]
        g.rows(spec)
        last = g.r - 1
        g.rows([(f"{tag}rs", "", "Total (A + B), Rs", "Rs", None,
                 lambda i, c, R, N: f"=SUMPRODUCT($D${first}:$D${last},{c}{first}:{c}{last})", "#,##0.00"),
                (f"{tag}l", "", "Gross total (Rs lakh)", "lakh", None,
                 lambda i, c, R, N: f"=ROUND({R(tag + 'rs')}/100000,2)", "#,##0.00")])
        for c in range(1, 5 + len(B.T3)):
            g.ws.cell(g.row[f"{tag}l"], c).font = B.bold
        out[tag] = [g.cell(f"{tag}l", i) for i in range(len(B.T3))]
        g.r += 1

    G = lambda tag: (lambda i, c, R, N: f"={R(tag + 'g')}")
    K = lambda tag: (lambda i, c, R, N: f"={R(tag + 'g')}*{R(tag + 'kva')}")
    M = lambda tag: (lambda i, c, R, N: f"={R(tag + 'g')}*{R(tag + 'm')}")
    sub = "A. Fixed charges: 25 / 63 kVA transformer 11 / 0.4 kV with D.P. sub-station"
    block("t", "Power connection for a tube well (a new tube well of the OZ)", lambda i: "1",
          lambda i: H("load", i),
          [(sub, "No.", P["tw_transformer"], G("t")), ("Processing fee", "Job", P["tw_processing"], G("t")),
           ("Security charge per kVA", "kVA", P["security_per_kva"], K("t")),
           ("Energy meter, cable, cutouts etc.", "Job", P["tw_meter"], G("t")),
           ("B. Construction of 11 kV underground double circuit line including cost of cable and laying of cable and "
            "restoration charges", "mtr", P["line_per_m"], M("t"))], P["tw_line_m"])
    block("b", "Power connection for a booster pumping plant", lambda i: f"IF({T('bw', i)}>0,1,0)",
          lambda i: H("bload", i),
          [(sub, "No.", P["tw_transformer"], G("b")), ("Processing fee", "Job", P["tw_processing"], G("b")),
           ("Security charge per kVA", "kVA", P["security_per_kva"], K("b")),
           ("Energy meter, cable, cutouts etc.", "Job", P["tw_meter"], G("b")),
           ("B. Construction of 11 kV underground double circuit line", "mtr", P["line_per_m"], M("b"))],
          P["booster_line_m"])
    block("c", "Power connection for a CWR (its sub-station: sheet EMD CWR)", lambda i: f"IF({T('cw', i)}>0,1,0)",
          lambda i: cw.cell("pc", i),
          [("A. Fixed charges: processing fee", "Job", P["cwr_processing"], G("c")),
           ("Security charge per kVA", "kVA", P["security_per_kva"], K("c")),
           ("Meter, cable, cutouts etc.", "Job", P["cwr_meter"], G("c")),
           ("B. Construction of 11 kV underground double circuit line including cost of cable and laying of cable and "
            "restoration charges", "mtr", P["line_per_m"], M("c"))], P["cwr_line_m"])
    g.note("Riverside water DPR p345 (tube wells 43 / 26 kVA, booster 15 kVA: 63 / 25 kVA transformers, 540-575 m of "
           "line, Rs 17.57-18.83 lakh) and p346-349 (CWR 119-140 kVA, 560-720 m, Rs 20.59-24.53 lakh). The length of "
           "the line is of the site: yellow, fill in.")
    B.sign(g.ws, g.r + 2, 4 + len(B.T3))
    return out


def trial(B, T, E, hp, cw):
    R_ = E["trial"]
    g = Grid(B, "EMD TR", "THREE MONTH TRIAL & RUN COST - TUBE WELL, CWR PUMPING PLANT, BOOSTER (Riverside water DPR "
                          "p352-353)")
    H = lambda k, i: hp.cell(k, i)
    out = {}
    g.rows([("mo", "", "Months of trial run", "months", R_["months"], None, "0"),
            ("days", "", "Days a month", "days", R_["days"], None, "0"),
            ("kwh", "", "Rate of electricity", "Rs / kWh", R_["rate_kwh"], None, "0.00"),
            ("fix", "", "Fixed charges a month", "Rs / kW", R_["fixed_rs_per_kw_month"], None, "#,##0"),
            ("opn", "", "Operators (a month)", "nos", R_["operators"], None, "0"),
            ("ops", "", "Salary of an operator a month", "Rs", R_["operator_rs_month"], None, "#,##0")])

    def elec(tag, kw, other, other_v, hours, hours_v=None):
        return [(f"{tag}kw", 1, "kW of motor", "kW", None, kw, "#,##0.00"),
                (f"{tag}o", 2, other, "kW", other_v, lambda i, c, R, N: f"=IF({R(tag + 'kw')}>0,{N(tag + 'o')},0)",
                 "#,##0.00"),
                (f"{tag}t", 3, "Total kW required", "kW", None,
                 lambda i, c, R, N: f"={R(tag + 'kw')}+{R(tag + 'o')}", "#,##0.00"),
                (f"{tag}h", 4, "Hours of pumping", "hrs", hours_v, hours, "#,##0.00"),
                (f"{tag}r", 5, "Running charges for 1 month = kW x hours x days x rate", "Rs", None,
                 lambda i, c, R, N: f"={R(tag + 't')}*{R(tag + 'h')}*{N('days')}*{N('kwh')}", "#,##0.00"),
                (f"{tag}f", 6, "Fixed charges for 1 month = kW (whole) x rate", "Rs", None,
                 lambda i, c, R, N: f"=ROUNDUP({R(tag + 't')},0)*{N('fix')}", "#,##0.00"),
                (f"{tag}e", 7, "Total electric charges for one month", "Rs", None,
                 lambda i, c, R, N: f"={R(tag + 'r')}+{R(tag + 'f')}", "#,##0.00")]

    def total(tag, parts):
        g.rows([(f"{tag}m", "", "Total trial & run charges for one month", "Rs", None,
                 lambda i, c, R, N: "=" + "+".join(R(p) for p in parts), "#,##0.00"),
                (f"{tag}3", "", "Total trial & run charges for the months", "Rs", None,
                 lambda i, c, R, N: f"={R(tag + 'm')}*{N('mo')}", "#,##0.00"),
                (f"{tag}l", "", "Say (Rs lakh)", "lakh", None, lambda i, c, R, N: f"=ROUND({R(tag + '3')}/100000,2)",
                 "#,##0.00")])
        for c in range(1, 5 + len(B.T3)):
            g.ws.cell(g.row[f"{tag}l"], c).font = B.bold
        out[tag] = [g.cell(f"{tag}l", i) for i in range(len(B.T3))]
        g.r += 1

    g.r += 1
    g.head("TUBE WELL - A. Expenditure on sodium hypochlorite (a month)")
    g.rows([("q", 1, "Average discharge of T/W (sheet TW)", "LPM", None, lambda i, c, R, N: _f(T("q", i)), "#,##0"),
            ("hr", 2, "Pumping hours at the end of designed period (sheet EM TS)", "hrs", None,
             lambda i, c, R, N: _f(T("hrs", i)), "#,##0.00"),
            ("kl", 3, "Discharge passing through mains a day = LPM x 60 x hours / 1000", "KL", None,
             lambda i, c, R, N: f"={R('q')}*60*{R('hr')}/1000", "#,##0.00"),
            ("ppm", 4, "Dose of chlorine", "ppm", R_["chlorine_ppm"], None, "0.00"),
            ("kg", 5, "Chlorine required in 1 month = KL x ppm x days / 1000", "Kg", None,
             lambda i, c, R, N: f"={R('kl')}*{N('ppm')}*{N('days')}/1000", "#,##0.00"),
            ("gl", 6, "Chlorine in 1000 ml of sodium hypochlorite", "g", R_["hypo_g_per_l"], None, "#,##0"),
            ("l", 7, "Sodium hypochlorite required for 1 month", "Ltr", None,
             lambda i, c, R, N: f"={R('kg')}*1000/{N('gl')}", "#,##0.00"),
            ("rl", 8, "Rate of sodium hypochlorite (SOR p364 11.7)", "Rs / Ltr", R_["hypo_rs_per_l"], None, "#,##0.00"),
            ("chl", 9, "Total chlorination charges for one month", "Rs", None,
             lambda i, c, R, N: f"={R('l')}*{N('rl')}", "#,##0.00")])
    g.head("TUBE WELL - B. Expenditure on electricity for the TW pumping plant (a month)")
    g.rows(elec("w", lambda i, c, R, N: f"={H('hp', i)}*0.746", "Light & fan load", R_["tw_light_kw"],
                lambda i, c, R, N: f"={R('hr')}"))
    g.head("TUBE WELL - C. Expenditure on staff (a month)")
    g.rows([("ws", 1, "Pump operators x salary", "Rs", None, lambda i, c, R, N: f"={N('opn')}*{N('ops')}", "#,##0.00")])
    total("tw", ["chl", "we", "ws"])
    g.head("CWR PUMPING PLANT - D. Expenditure on electricity (a month)")
    g.rows(elec("c", lambda i, c, R, N: f"={cw.cell('w', i)}*{cw.cell('hp', i)}*0.746", "Light & fan load",
                R_["cwr_light_kw"], lambda i, c, R, N: f"=IF({R('ckw')}>0,{R('hr')},0)"))
    g.rows([("cs", 8, "Operator charges", "Rs", None, lambda i, c, R, N: f"=IF({R('ckw')}>0,{N('opn')}*{N('ops')},0)",
             "#,##0.00")])
    total("c", ["ce", "cs"])
    g.head("BOOSTER PUMPING PLANT - E. Expenditure on electricity (a month)")
    g.rows(elec("b", lambda i, c, R, N: f"={H('btkw', i)}", "Other instruments", R_["booster_other_kw"],
                lambda i, c, R, N: f"=IF({R('bkw')}>0,{N('bh')},0)", R_["booster_hours"]))
    total("b", ["be"])
    g.note("Riverside water DPR p352-353: tube well Rs 3.99 lakh (1380 LPM, 12 h, 25 kW + 2 kW, operator 1 x 12000 x 3 "
           "a month), CWR pumping plant Rs 9.37 lakh (82.74 kW, operator Rs 36000 a month), booster Rs 0.80 lakh "
           "(7.46 + 0.5 kW, 12 h, no operator).")
    B.sign(g.ws, g.r + 2, 4 + len(B.T3))
    return out


def write(B, T):
    """The design sheets; T(key, i) the cell of sheet EM TS of OZ i. Returns the cells sheet EM takes."""
    E = B.S["em_design"]
    d = tw_design(B, T, E)
    est = tw_estimate(B, T, E, d)
    hp = hp_transformer(B, T, E)
    cw = cwr(B, T, E, hp)
    pc = power(B, T, E, hp, cw)
    tr = trial(B, T, E, hp, cw)
    n = range(len(B.T3))
    return {"tw": [est.cell("lakh", i) for i in n], "pc_tw": pc["t"], "pc_b": pc["b"], "pc_c": pc["c"],
            "tr_tw": tr["tw"], "tr_c": tr["c"], "tr_b": tr["b"], "tf_kva": [cw.cell("kva", i) for i in n],
            "tf_n": [cw.cell("n", i) for i in n], "hd": [d.cell("hd", i) for i in n],
            "dia": [d.cell("dia", i) for i in n]}
