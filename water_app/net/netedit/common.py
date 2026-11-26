"""netedit: the shared names - problem kinds, limits, the undo stacks and caches of this run."""
import collections


USER_GL = "edited in the map UI (user)"


EX_TYPES = {"label matched in pass 2 - CHECK", "label matched in pass 2 - low risk", "GL matched in pass 2 - CHECK",
            "GL matched in pass 2 - low risk", "no drawing label (name generated)", "manhole on a continuous line - check",
            "near-miss gap", "T-joint", "label used twice in the drawing", "label suggested (nearest unused label) - CHECK"}


LOW = {"label matched in pass 2 - low risk", "GL matched in pass 2 - low risk"}


GL_TYPES = {"GL matched in pass 2 - CHECK", "GL matched in pass 2 - low risk", "no ground level",
            "GL spike (> 2 m from all neighbours)"}


LABEL_TYPES = {"label matched in pass 2 - CHECK", "label matched in pass 2 - low risk",
               "no drawing label (name generated)", "label used twice in the drawing", "label suggested (nearest unused label) - CHECK"}


SUGGESTED = "label suggested (nearest unused label) - CHECK"


SUGGEST_RADIUS_M = 25.0         # a label further than this from the symbol is not suggested


SUGGEST_GL_M = 4.0              # the GL text is looked for this close to the label text


UNDO_MAX = 20


_UNDO = collections.defaultdict(lambda: collections.deque(maxlen=UNDO_MAX))


_TEXTS = {}
