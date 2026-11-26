"""WATER MODULE COPY of sewer_app/net/dxf_inspect/ (isolation of sewer and water, user request 21-Oct-2026): changes here do not\nreach the sewer module, nor the reverse. Water rules are written in directly (a water main network keeps its loops\nand has no outfalls)."""
"""
dxf_inspect.py - reading a CAD drawing (DXF / DWG) for the water network import (dxf_extract, netedit): entities,
text kinds, joining lines into a network, its checks, ground levels per junction.
The command-line check of a drawing (console + Excel report) is in the sewer copy only - python -m
sewer_app.net.dxf_inspect (17-Nov-2026: the water copy of it was not reachable from the water app and was removed).
A DWG is read through the free ODA File Converter when it is installed; nothing is written into the drawing.
"""
# dxf_inspect in parts (rewrite stage 3b, 26-Nov-2026) - each name is still dxf_inspect.<name>
from .kinds import (  # noqa: F401
    DEC_RE, DIA_RE, ID_RE, IL_RE, LEVEL_FAR_M, LEVEL_SPREAD_M, LEVEL_TAG, NOT_PIPE_NAME, NUM, PIPE_NAME, SLOPE_RE,
    Z_TEXT_AGREE_M, classify,
)
from .reading import load, polyline_points, pos_of, seg_len, text_height, text_of  # noqa: F401
from .spatial import Grid, point_seg_dist, seg_cross  # noqa: F401
from .layers import (  # noqa: F401
    LABELLED_SHARE, LENGTH_TEXT, PIPE_LABEL, SCALE_AGREE, SPLIT_COLOURS, SPLIT_SHARE, _colour, _labelled_apart,
    _scale_all, drawing_scale, inventory, pipe_label_hits, split_layer,
)
from .matching import NUMBER_BONUS_M, labels_near_nodes, match_to_nodes, optimal_pairs, pair_with_labels  # noqa: F401
from .levels import (  # noqa: F401
    is_tagged_level, level_band, level_candidates, level_texts_of_layer, node_levels, parse_number,
)
from .network import build_network, components, network_checks  # noqa: F401
