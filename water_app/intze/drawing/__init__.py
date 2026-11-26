"""Drawings of an Intze OHT designed by intze.py, laid out as the drawings of the user's example (Brookfield Consultants,
TCP-250510/OPG-1..3, the 2700 KL tank of zone 14; user decisions 10-Nov-2026): one DXF (A1 sheets side by side in
model space, paper mm, each view at the scale written under it) and the same sheets as a PDF; the design calculation,
the bar bending schedule and the quantities as an xlsx.

Sheet 1 staging and foundation: half section / half elevation with the staircase, half foundation plan / half plan
at brace level, section and part reinforcement plan of the raft, L-sections of the foundation ring beam and of a
brace, column section, notes. Sheet 2 container: section of the tank with its bars, top ring beam, L-section of the
bottom ring beam, part plans of the domes' reinforcement, ventilator, manhole, ladder, pipe fixing. Sheet 3 staircase.
Sheet 4+ bar bending schedule and quantities. Bars are written as on the example: "408 - 25 # RADIALLY @ 150 C/C".
"""
# drawing in parts (rewrite stage 5, 26-Nov-2026) - each name is still drawing.<name>
from .base import (  # noqa: F401
    B, BI, GAP, LAYERS, SCALES, SH, SW, Sheet, View, WARN, _FONT, _info, arc_pts, at, fit_scale, nb, ordinal, tw,
)
from .shapes import _angles, _container_outline, _raft_outline, _raft_t, _shapes  # noqa: F401
from .sheet_ga import (  # noqa: F401
    _beam_xsec, _ga, _lsec, _notes, _plans, _raft_plan, _raft_section, _sector, _sheet_staging, _stair_plan, bar_row,
    hooked, stair_side,
)
from .sheet_stair import _brk, _clip, _roof_landing, _sheet_stair, _stair_beam, _stirrups  # noqa: F401
from .sheet_container import (  # noqa: F401
    _dome_plan, _joint_detail, _ring_bars, _ring_detail, _sheet_container, _small_details, _tank_section,
)
from .sheet_bbs import _sheets_bbs, _summary  # noqa: F401
from .export import _DW, _new_doc, _pdf, export, export_xlsx, make_sheets  # noqa: F401
