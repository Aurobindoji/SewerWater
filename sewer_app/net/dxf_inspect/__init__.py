"""
dxf_inspect.py - READ-ONLY check of a CAD drawing (DXF / DWG) before a sewer design.
Tells what a sewer design needs, what the drawing has, and what is missing.
From the original scripts dxf_inspect.py, logic unchanged (output folder: sewer_app\\output; DWG read through ODA).

    python -m sewer_app.net.dxf_inspect "oakdale.dxf"
    python -m sewer_app.net.dxf_inspect "...\\oakdale.dxf" --pipe-layers PIPE0,PIPE1 --mh-layers TWO_CONCENTRIC_CIRCLES
    python -m sewer_app.net.dxf_inspect "...\\oakdale.dxf" --tol 0.5 --level-radius 10

A DWG is read through the free ODA File Converter when it is installed; otherwise save it as DXF
(AutoCAD: SAVEAS -> DXF). Nothing is written into the drawing.

What it reports (console + Excel 'output\\dxf_inspect\\<name>_dxf_inspect_<time>.xlsx')
  1. Drawing  : DXF version, units ($INSUNITS), extents, coordinate size (projected metres or not).
  2. Layers   : every layer with its entity types and counts, colour, total line length.
  3. Texts    : TEXT / MTEXT / block attributes per layer - how many are numbers, their range and
                common prefixes (GL, IL, RL, MH, mm ...) -> candidate ground-level / invert / diameter layers.
  4. Blocks   : block references per name and layer, with attribute tags and sample values.
  5. Network  : for the pipe layers (given, or guessed from the layer name: pipe / sewer / sw / main /
                line), lines are joined end to end within --tol: nodes, connected parts, loops, dead
                ends, near-miss gaps (ends that almost touch), T-joints without a node, segments longer
                than 30 m (CPHEEO manhole spacing), crossings without a node.
  6. Manholes : for point-like layers (block / circle / point) - how many network nodes have a symbol
                within --tol; the best match is proposed as the manhole layer.
  7. Levels   : ground level per node from (a) Z of the line vertices, (b) block attributes such as
                GL / RL / GROUND / ELEV, (c) the nearest numeric text within --level-radius m.
                Coverage per source is reported.
  8. Outfall  : texts such as STP / OUTFALL / SPS / IPS / PS / DISPOSAL and the nearest dead end.
  9. Checklist: REQUIRED item -> FOUND / PARTIAL / MISSING, with what to do.
"""
# dxf_inspect in parts (rewrite stage 4b, 26-Nov-2026) - each name is still dxf_inspect.<name>
from .kinds import (  # noqa: F401
    BASE, DEC_RE, DIA_RE, ID_RE, IL_MAX_DEPTH_M, IL_MIN_DEPTH_M, IL_RE, IL_SHALLOW_M, INVERT_TAG, LEVEL_TAG,
    NOT_PIPE_NAME, NUM, OUTFALL_WORD, OUT_DIR, PIPE_NAME, SLOPE_RE, UNITS, Z_TEXT_AGREE_M, classify,
)
from .reading import load, polyline_points, pos_of, seg_len, text_height, text_of  # noqa: F401
from .spatial import Grid, point_seg_dist, seg_cross  # noqa: F401
from .layers import inventory  # noqa: F401
from .matching import (  # noqa: F401
    NUMBER_BONUS_M, labels_near_nodes, match_points, match_to_nodes, optimal_pairs, pair_with_labels,
    pipe_annotations,
)
from .levels import level_candidates, node_inverts, node_levels, parse_number, split_gl_il, text_summary  # noqa: F401
from .network import build_network, components, network_checks  # noqa: F401
from .cli import main  # noqa: F401
