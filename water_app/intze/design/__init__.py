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
# design in parts (rewrite stage 5, 26-Nov-2026) - each name is still design.<name>
from .basics import (  # noqa: F401
    CONC, DEFAULTS, DIAS, G, GAMMA_C, GAMMA_W, K2_TC2, Mat, RING1_BAND, RING1_NOMINAL, T10, TAU_C, TAU_MAX, TAU_PT,
    ZONE_Z, _bars, _capacity, _dome, _interp, _mesh, area, ast_flex, kg_per_m, up,
)
from .members import _circ_beam, _forces, _kz, _ring_section, _sa_g, cone_depth, new_kl, proportion  # noqa: F401
from .columns import _steel_stress, col_curve, col_moment  # noqa: F401
from .stair import _stair, beam_len  # noqa: F401
from .bbs import _rows, bbs, quantities  # noqa: F401
from .tank import design  # noqa: F401
