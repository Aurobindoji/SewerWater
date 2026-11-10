"""The civil works of the water DPR besides the network, OHTs and CWRs - in the format of the Riverside water DPR
(U.P. Jal Nigam, AMRUT 2.0, 2026; user decision 6-Nov-2026: the DPR export as that DPR), each from the design's
counts by operation zone (sheets TW, EM TS) and the unit estimates of the Elmwood estimate (= that DPR's p382):

    pump_house(B)     PH      pump house cum chlorination room of each new tube well, its bypass chamber; repairs of
                              the pump house of each existing tube well (p203-204)
    site(B)           BW      boundary wall of each new water works campus and tube well site less a gate each,
                              repairs of the walls of the existing campuses, gates, interlocking approach road, earth
                              filling, semi-circular drain, arboriculture (p301-315)
    buildings(B)      SQ, GWR, MCS, HT,LT   staff quarters, ground water recharge, MCS building, HT / LT panel rooms
                              of each CWR and booster pump room of each booster (p273-276, p316-317)
    oht_repair(B, z)  Rep. OHT (k)   repairs of an existing OHT: the measurements of the DPR's 750 KL or 1500 KL tank,
                              the nearer (p256-272)

The counts and measurements are yellow - change them to the project's; B.CIV = {key: Rs lakh cell} for ABS Com.
B = dpr.Book after the E&M sheets (dpr_em.write: B.EMTS).
"""
from .dpr import q

STAGE_NOTE = "Riverside water DPR (U.P. Jal Nigam 2026)"


def _cols(B, ws):
    B.header(ws, 5, ["Sl No", "SOR Ref.", "Item of work", "No.", "L", "B", "H/D", "Qty", "Rate", "Unit", "Amount"],
             [6, 9, 52, 8, 8, 8, 7, 11, 12, 7, 15])


class _Sheet:
    """Rows of an estimate in the DPR's columns: title(...) a bold line, row(...) a measured line, total(...)."""

    def __init__(self, B, name, heading):
        self.B, self.ws = B, B.sheet(name, heading, 11)
        _cols(B, self.ws)
        self.x = 6

    def title(self, no, text):
        B, ws = self.B, self.ws
        B.cell(ws, self.x, 1, no)
        B.cell(ws, self.x, 3, text, bold=True).alignment = B.wrap
        ws.row_dimensions[self.x].height = max(15, 15 * (len(text) // 55 + 1))
        self.x += 1

    def row(self, text, no=None, L=None, b=None, h=None, qty=None, rate=None, unit=None, ref="AOR", inp=(),
            rate_inp=False):
        """A measured line: Qty = the product of No, L, B, H given (or qty), Amount = Qty x Rate when a rate."""
        B, ws, x = self.B, self.ws, self.x
        B.cell(ws, x, 2, ref)
        B.cell(ws, x, 3, text).alignment = B.wrap
        for c, v in ((4, no), (5, L), (6, b), (7, h)):
            if v is not None:
                B.cell(ws, x, c, v, fmt="#,##0.00", inp=c in inp)
        if qty is None:
            qty = "=" + "*".join(f"{B.col(c)}{x}" for c, v in ((4, no), (5, L), (6, b), (7, h)) if v is not None)
        B.cell(ws, x, 8, qty, fmt="#,##0.00")
        if rate is not None:
            B.cell(ws, x, 9, rate, fmt="#,##0.00", inp=rate_inp)
            B.cell(ws, x, 10, unit)
            B.cell(ws, x, 11, f"=H{x}*I{x}", fmt="#,##0.00")
        self.x += 1
        return x

    def sub(self, rows, rate, unit, label="Sub total"):
        """A line summing the quantities of rows, at a rate."""
        B, ws, x = self.B, self.ws, self.x
        B.cell(ws, x, 7, label, bold=True)
        B.cell(ws, x, 8, f"=SUM(H{rows[0]}:H{rows[-1]})", fmt="#,##0.00", bold=True)
        if rate is not None:
            B.cell(ws, x, 9, rate, fmt="#,##0.00")
            B.cell(ws, x, 10, unit)
            B.cell(ws, x, 11, f"=H{x}*I{x}", fmt="#,##0.00", bold=True)
        self.x += 1
        return x

    def total(self, rows, note=None):
        """Total of the amounts of rows, Say (in lakh); returns the lakh cell."""
        B, ws, x = self.B, self.ws, self.x
        B.cell(ws, x, 3, "Total", bold=True)
        B.cell(ws, x, 11, "=" + "+".join(f"K{r}" for r in rows) if rows else 0, fmt="#,##0.00", bold=True)
        B.cell(ws, x + 1, 3, "Say (in lakh)", bold=True)
        B.cell(ws, x + 1, 11, f"=ROUND(K{x}/100000,2)", fmt="#,##0.00", bold=True)
        if note:
            ws.cell(x + 3, 2, note).font = B.italic
        B.sign(ws, x + 5, 9)
        return f"{q(ws.title)}!$K${x + 1}"


def _zones(B):
    """(i, zone, row of sheet TW) of each OZ."""
    return [(i, t["zone"], 6 + i) for i, t in enumerate(B.T3)]


def pump_house(B):
    U = B.S["civil"]["units"]
    E = _Sheet(B, "PH", "ESTIMATE & DETAILED MEASUREMENT FOR PUMP HOUSE")
    E.title("A", "NEW PUMPHOUSE")
    E.title(1, "Provide all materials, labour, T&P etc. complete and construct pump house size (3.6 x 3.0 x 3.0 m) and "
               "chlorinating room size (2.5 x 1.8 x 3.0 m) as per departmental type design and drawing - one for each "
               "new tube well, the standby ones too (sheet TW, O)")
    new = [E.row(f"Zone {z['name']}", no=f"=TW!O{r}", rate=f"={U['pump_house']}", unit="Nos") for i, z, r in _zones(B)]
    E.title("B", "Bye pass chamber - one for each new pump house")
    byp = [E.row(f"Zone {z['name']}", no=f"=D{y}", rate=f"={U['bypass']}", unit="Nos") for (i, z, r), y in
           zip(_zones(B), new)]
    E.title("C", "REPAIR OF EXISTING PUMP HOUSE")
    E.title(2, "Supply of all materials, labour, T&P etc. and construction work for repairing of existing pump house "
               "cum chlorinome (as per unit estimate attached) - one for each existing tube well (sheet TW)")
    rep = [E.row(f"Zone {z['name']}", no=f"=TW!C{r}", rate=f"={U['ph_repair']}", unit="Nos") for i, z, r in _zones(B)]
    # a rebored tube well: no pump house, a girder pillar over it (user 7-Nov-2026: as built on site)
    E.title("D", "GIRDER PILLAR FOR REBORED TUBE WELL")
    E.title(3, "Provide all materials, labour, T&P etc. complete and construct girder pillar as per departmental type "
               "design (as per unit estimate attached) - one for each rebored tube well (sheet TW, P); no new pump "
               "house")
    gp = [E.row(f"Zone {z['name']}", no=f"=TW!P{r}", rate=f"={U['girder_pillar']}", unit="Nos") for i, z, r in _zones(B)]
    return E.total(new + byp + rep + gp, note=f"{STAGE_NOTE} p203-204; rates: unit estimates Pump House, Bypass "
                                              "Chamber, PH Repair, Girder Pillar (sheet Unit Rates).")


def site(B):
    C = B.S["civil"]
    U = C["units"]
    E = _Sheet(B, "BW", "DETAILED MEASUREMENT & ESTIMATE FOR BOUNDARY WALL, GATE, PILLARS, APPROACH ROAD & SITE "
                        "DEVELOPMENT")
    (cl, cb), (tl, tb) = C["campus_wall_m"], C["tw_wall_m"]
    E.title(1, "Construction of boundary wall as per departmental type design at water works including supply of all "
               "materials, labour, T&P etc. complete - the campus of each new OHT, each new tube well site")
    walls, sites = [], []
    for i, z, r in _zones(B):
        E.title("", f"Zone {z['name']}")
        y0 = E.x
        if not z["existing"]:
            E.row("For water works", no=2, L=cl, inp=(4, 5))
            E.row("", no=2, L=cb, inp=(4, 5))
        E.row("For tube well sites (new tube wells, the standby ones too)", no=f"=2*TW!O{r}", L=tl, inp=(5,))
        E.row("", no=f"=2*TW!O{r}", L=tb, inp=(5,))
        walls.append(E.sub(list(range(y0, E.x)), None, None))
        sites.append(f"{0 if z['existing'] else 1}+TW!O{r}")
    gates = "+".join(sites) or "0"
    E.row("Deduct for 3.6 m wide gate", no=f"={gates}", L=-C["gate_m"], inp=(5,))
    walls.append(E.x - 1)
    wall = E.row("Total length of the new boundary wall", qty="=" + "+".join(f"H{y}" for y in walls),
                 rate=f"={U['wall']}", unit="Rmt")
    E.title(2, "Repairing of boundary wall as per departmental type design at water works including supply of all "
               "materials, labour, T&P etc. - the campus of each existing OHT")
    reps = [E.row(f"Zone {z['name']} - for water works", no=1, L=C["wall_repair_m"], inp=(4, 5))
            for i, z, r in _zones(B) if z["existing"]]
    rep = E.row("Total length repaired", qty="=" + ("+".join(f"H{y}" for y in reps) if reps else "0"),
                rate=f"={U['wall_repair']}", unit="Rmt")
    gate = E.row("Supply and fixing of 3.6 m wide gate including construction of pillars as per departmental type "
                 "design - each new campus and tube well site", no=f"={gates}", rate=f"={U['gate']}", unit="Nos", ref="AOR")
    n = len(B.T3)
    E.title(4, "Provide all materials, labour, T&P etc. required for proper completion of work and construct interlocking "
               "road - approach road of each water works")
    ys = [E.row("For water works", no=n, L=l_, b=w_, inp=(4, 5, 6)) for l_, w_ in C["approach_road"]]
    road = E.sub(ys, f"={U['interlocking']}", "Sqm", label="Total")
    new_oht = sum(1 for t in B.T3 if not t["zone"]["existing"])
    E.title(5, "Provide all materials, labour, T&P etc. required for proper completion of works including levelling, "
               "dressing, excavation and filling of earth where necessary for development of water works site including "
               "carriage of earth from distant of about 8 km - each new OHT campus (user decision 6-Nov-2026)")
    fl, fb, fh = C["earth_fill"]
    earth = E.row("For water works", no=new_oht, L=fl, b=fb, h=fh, rate=f"={U['earth']}", unit="Cum", inp=(4, 5, 6, 7))
    drain = E.row("Construction of semi-circular drain - each water works", no=n, L=C["drain_m"], rate=f"={U['drain']}",
                  unit="Rmt", inp=(4, 5))
    arb = E.row("Provision for arboriculture for departmental water works compound", no=n, rate=C["arboriculture"],
                unit="Job", ref="L.S.", inp=(4,), rate_inp=True)
    return E.total([wall, rep, gate, road, earth, drain, arb],
                   note=f"{STAGE_NOTE} p301-315: wall 2 x {cl} + 2 x {cb} m a new campus, 2 x {tl} + 2 x {tb} m a tube "
                        f"well site (our tube wells stand 100 m from the OHT), less a {C['gate_m']:g} m gate each; "
                        "rates: unit estimates Boundary Wall, BW Repair, Gate, Interlocking, Earth Filling, U Drain.")


def buildings(B):
    """Staff quarters, ground water recharge, MCS building, HT / LT panel and booster rooms. B.CIV keys."""
    U = B.S["civil"]["units"]
    n = len(B.T3)
    new_oht = sum(1 for t in B.T3 if not t["zone"]["existing"])
    out = {}
    for key, name, heading, text, cnt, unit_key, note in (
            ("sq", "SQ", "ESTIMATE OF STAFF QUARTER",
             "Provide all material, labour, T&P etc. required for proper completion of work and construct staff quarters "
             "for operator and chaukidar as per design type (set) - one at each new OHT campus", new_oht, "staff_quarter",
             "p316; rate: unit estimate Staff Quarter (single room)"),
            ("gwr", "GWR", "ESTIMATE FOR GROUND WATER RECHARGE",
             "Construction of ground water recharge mechanism - one in each zone", n, "gwr",
             "p317; rate: unit estimate GW Recharge"),
            ("mcs", "MCS", "ESTIMATE OF MASTER CONTROL STATION",
             "Construction of new master control station with lab and toilet", 0, "mcs",
             "p47 (none in that DPR); rate: unit estimate MCS")):
        E = _Sheet(B, name, heading)
        y = E.row(text, no=cnt, rate=f"={U[unit_key]}", unit="Nos", ref="", inp=(4,))
        E.ws.row_dimensions[y].height = 60
        out[key] = E.total([y], note=f"{STAGE_NOTE} {note}.")
        out[key + "_n"] = f"{name}!$D${y}"                  # the number, for ABS Com (p45: "15 Nos", "11 Nos")
    # HT / LT panel rooms of each CWR, booster room of each booster (sheet EM TS)
    col, f0 = B.EMTS["col"], B.EMTS["first"]
    f1 = f0 + n - 1
    cwr = f"COUNTIF('EM TS'!${col['ckl']}${f0}:${col['ckl']}${f1},\">0\")"
    boo = f"COUNTIF('EM TS'!${col['bw']}${f0}:${col['bw']}${f1},\">0\")"
    ws = B.sheet("HT,LT", "ABSTRACT OF COST FOR CONSTRUCTION OF H.T. PANEL, L.T. PANEL & BOOSTER PUMP ROOM", 6)
    B.header(ws, 5, ["Sl. No", "Description", "Qty.", "Unit", "Rate (Rs. lakh)", "Amount (Rs. lakh)"], [7, 50, 9, 8, 14, 16])
    B.cell(ws, 6, 1, 1)
    B.cell(ws, 6, 2, "Construction of room in the framed structure including all the associated works").alignment = B.wrap
    for x, (lab, cnt, k) in enumerate((("H.T. panel room (each CWR)", cwr, "ht_room"),
                                       ("L.T. panel room (each CWR)", cwr, "lt_room"),
                                       ("Booster pump room (each booster)", boo, "booster_room")), 7):
        B.cell(ws, x, 2, lab)
        B.cell(ws, x, 3, f"={cnt}", fmt="#,##0")
        B.cell(ws, x, 4, "No.")
        B.cell(ws, x, 5, f"={U[k]}", fmt="#,##0.00")
        B.cell(ws, x, 6, f"=C{x}*E{x}", fmt="#,##0.00")
    B.cell(ws, 10, 2, "Total", bold=True)
    B.cell(ws, 10, 6, "=ROUND(SUM(F7:F9),2)", fmt="#,##0.00", bold=True)
    ws.cell(12, 2, f"{STAGE_NOTE} p273-276: CPWD plinth area rate 2023 (Springfield cost index 107) + 3.75 % external "
                   "electrical services + 12.5 % internal electrification + 4 % power wiring; rooms 5.5 x 4, 4 x 3.5, "
                   "6 x 5 m (unit estimates HT Room, LT Room, Booster Room).").font = B.italic
    B.sign(ws, 15, 5)
    out["rooms"] = "'HT,LT'!$F$10"
    out["rooms_n"], out["cwr_n"] = "'HT,LT'!$C$7+'HT,LT'!$C$9", "'HT,LT'!$C$7"     # the rooms' sets; the CWRs
    B.CIV = dict(getattr(B, "CIV", {}), **out)
    return out


def oht_repair(B, z, k):
    """Sheet Rep. OHT (k): repairs of the existing OHT of OZ z, the measurements of the DPR's tank nearer its capacity.
    Returns its Rs lakh cell."""
    R = B.S["oht_repair"]
    T = R["750"] if (z.get("capacity_kl") or 0) <= R["split_kl"] else R["1500"]
    rt = R["rates"]
    E = _Sheet(B, f"Rep. OHT ({k})", f"DETAILED MEASUREMENT AND ESTIMATE FOR REPAIR OF R.C.C. OVER HEAD TANK - "
                                     f"{z.get('capacity_kl') or 0:,.0f} KL (OPERATION ZONE {z['name']})")
    amts = []

    def dims(rows, rate, unit):
        ys = []
        for lab, *d in rows:
            d = list(d) + [None] * (4 - len(d))
            ys.append(E.row(lab, no=d[0], L=d[1], b=d[2], h=d[3], rate=rate, unit=unit, ref="", inp=(4, 5, 6, 7),
                            rate_inp=True))
        return ys
    E.title(1, "Providing and fixing double scaffolding system (cup lock type) on the exterior side of OHT up to 25 m height "
               "including additional rows, working platform, bracings etc. (CPWD DSR vol. 2 item 14.72)")
    amts += dims(T["scaffold"], rt["scaffold"], "Sqm")
    E.title(2, "Sealing cracks and faulty construction joints: U-shape groove 25 x 25 mm, integral crystalline slurry and "
               "crystalline mortar (CPWD DSR vol. 2 item 22.25.1) - construction joints")
    amts += dims(T["joints"], rt["joints"], "M")
    E.title(3, "18 mm cement plaster in two coats - under layer 12 mm 1:5 and top layer 6 mm 1:6 (CPWD DSR vol. 2 item "
               "13.11)")
    amts += dims(T["plaster"], rt["plaster"], "Sqm")
    E.title(4, "Providing and injecting approved grout (OHT tank body) into cracks / honey-comb area (CPWD DSR vol. 2 item "
               "26.35)")
    for lab, kg, rate in zip(("I  Acrylic polymer modified cement slurry with non shrink compound (26.35.1)",
                              "II  SBR polymer modified cement slurry with shrinkage compensating cement (26.35.2)",
                              "III  Epoxy injection grout (26.35.3)"), T["grout_kg"], rt["grout"]):
        amts.append(E.row(lab, qty=kg, rate=rate, unit="Kg", ref="", rate_inp=True))
    E.title(5, "Integral crystalline slurry of hydrophilic nature for water proofing treatment from the negative "
               "(internal) side (CPWD DSR vol. 2 item 22.23) - vertical one coat @ 1.40 kg/sqm (22.23.1), horizontal one "
               "coat @ 1.10 kg/sqm (22.23.2)")
    for lab, n, L, b, h, rate in T["slurry_v"] + T["slurry_h"]:
        amts.append(E.row(lab, no=n, L=L, b=b, h=h, rate=rate, unit="Sqm", ref="", inp=(4, 5, 6, 7), rate_inp=True))
    jobs = [("Repair of M.S. ladder of 80 x 80 x 6 mm angle section with hand rails, from balcony to top dome and inside",
             T["ladder_qtl"], rt["ladder"], "Qtl"),
            ("Repairing 1 m wide RCC balcony around the tank wall", 1, rt["balcony"], "Job"),
            ("Repairing of railing of 20 mm dia G.I. pipe (3 rows) on both sides of staircase, around the balcony and at "
             "the periphery of the top dome", 1, rt["railing"], "Job"),
            ("Repairing of ventilator at top dome (1.2 m dia, RCC cover, mosquito net)", 1, rt["ventilator"], "Job"),
            ("Repairing of water level indicator", 1, rt["wli"], "Job"),
            ("Repairing of C.I. manhole 60 x 60 cm with locking arrangement", 1, rt["manhole"], "Job"),
            ("Repairing of sluice valve chamber including T&P, labour etc.", 1, rt["sv_chamber_repair"], "Job"),
            ("Construction of masonry type sluice valve chamber for the above sluice valves as per departmental type "
             "design", 1, rt["sv_chamber"], "No.")]
    for i, (lab, qty, rate, unit) in enumerate(jobs, 6):
        E.title(i, lab)
        amts.append(E.row("", no=1 if unit != "Qtl" else None, qty=qty if unit == "Qtl" else None, rate=rate, unit=unit,
                          ref="", rate_inp=True))
    E.title("(xiii)", "Supply, fixing, jointing of replacement of old pipes with C.I. D/F pipes and specials as vertical "
                      "pipes for inlet, outlet, overflow and washout, with all jointing materials and excavation")
    for lab, L, rate in T["pipes"]:
        amts.append(E.row(lab, no=1, L=L, rate=rate, unit="m", ref="", inp=(5,), rate_inp=True))
    E.title(14, "Cleaning of OHT including rubbing of internal surfaces and disposal of silt and garbage outside the campus")
    amts.append(E.row("", no=1, rate=rt["cleaning"], unit="Job", ref="", rate_inp=True))
    E.title(15, "Removing dry or oil bound distemper, water proofing cement paint and the like by scrapping, sand "
                "papering and preparing the surface smooth (CPWD DSR vol. 2 item 13.91)")
    sc = dims(T["scrape"], rt["scrape"], "Sqm")
    amts += sc
    E.title(16, "Finishing of all wall / concrete surfaces in two coat premium acrylic smooth exterior paint with one coat of "
                "exterior primer, white cement based putty (CPWD DSR vol. 2 item 13.47.1) - the area of item 15")
    amts.append(E.row("", qty=f"=SUM(H{sc[0]}:H{sc[-1]})", rate=rt["paint"], unit="Sqm", ref="", rate_inp=True))
    E.title(17, "Painting of all M.S. / steel pipe works with three coats of approved cement paint and anticorrosive paints")
    amts.append(E.row("", no=1, rate=rt["pipe_paint"], unit="Job", ref="", rate_inp=True))
    return E.total(amts, note=f"{STAGE_NOTE} p256-272: the measurements of its {T['title']} tank (the nearer to this "
                              f"one's capacity; up to {R['split_kl']:,} KL the 750 KL one) - change them to this tank's.")
