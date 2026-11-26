"""WATER MODULE COPY of sewer_app/netedit.py (isolation of sewer and water, user request 21-Oct-2026): changes here do not\nreach the sewer module, nor the reverse. Water rules are written in directly (a water main network keeps its loops\nand has no outfalls)."""
"""A sewer network read from a DXF, shown on the map of the UI and corrected there (user decision 12-Oct-2026:
"DXF network को नक्शे पर देखकर सुधारना").

    rows, guess = netedit.dxf_layers(path)                 # layers of the drawing + suggested pipe / MH layers
    st = netedit.import_dxf(stem, path, pipes, mhs, levels, epsg)   # dxf_extract -> working state (JSON)
    page = netedit.page_data(st)                            # nodes, conduits (lat / lon), issues
    netedit.apply(st, ops)                                  # the user's corrections, each one logged
    netedit.auto_repair(st)                                 # repair.repair (gaps, T-joints, loops, missing GL)
    netedit.save_network(st)                                # CSV files for zoning / design + the log of edits

The working state is output\\<stem>\\<stem>_netedit.json; the drawing's texts (for showing them on the map next to
the manholes) are in <stem>_dxf_texts.json. Problems are those of repair.check: the ones dxf_extract found while
reading (labels / GLs matched in pass 2, manholes without a label, gaps, T-joints ...) are kept from the import and
dropped when their manhole is gone; the network problems (no GL, GL spikes, loops, parts without an outfall, short
conduits) are found again after every change. A person can mark a problem as checked ('reviewed').
"""
# netedit in parts (rewrite stage 3b, 26-Nov-2026) - each name is still netedit.<name>
import json  # noqa: F401 (used outside as a module attribute)
from .common import (  # noqa: F401
    EX_TYPES, GL_TYPES, LABEL_TYPES, LOW, SUGGESTED, SUGGEST_GL_M, SUGGEST_RADIUS_M, UNDO_MAX, USER_GL, _TEXTS,
    _UNDO,
)
from .files import OLD_NAMES, RENAMED_FILES, _RENAME_SEEN, load, rename_old_names, state_path, store  # noqa: F401
from .coords import converters  # noqa: F401
from .texts import _f, _net_json, _shown_by_page, _texts, _tuples, texts_in  # noqa: F401
from .problems import NODE_ITEM, _connected, _key, _linked, _looks_like_node, cut_pairs, issues  # noqa: F401
from .suggest import ID_TEXT, LEVEL_TEXT, _LEVELS, _level_grid, label_levels, suggestions  # noqa: F401
from .edits import (  # noqa: F401
    _OPS, _apply1, _apply_suggestion, _ctx, _log, _op_apply_suggestions, _op_connect, _op_delete_conduit,
    _op_delete_mh, _op_gl_from_labels, _op_merge, _op_move, _op_outfall, _op_rejoin_cuts, _op_rename,
    _op_rename_prefix, _op_review, _op_set_gl, _op_set_noconn, _op_split, _plen, _review, _snapshot, apply, place,
    undo,
)
from .renumber import MERGED, _rename_all, renumber, renumber_order  # noqa: F401
from .mend import THROUGH, auto_repair, joints_only, merge_pairs, save_network, through_merge  # noqa: F401
from .drawing import (  # noqa: F401
    _INV, _INV_INFO, _colour_guess, _inventory, dxf_layers, dxf_net_preview, dxf_preview, dxf_roads_kml, import_dxf,
)
from .page import page_data  # noqa: F401
