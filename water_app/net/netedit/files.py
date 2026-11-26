"""netedit: the working state on disk - its path, load / store, and the old pipe names renamed once."""
import json
import os
import re


# ---------------------------------------------------------------- files
def state_path(out_root, stem):
    return os.path.join(out_root, stem, f"{stem}_netedit.json")


# names of an import before the water module had its own (user requests 21-Oct-2026 'water में CO- नहीं, P-', 22-Oct-2026
# 'J- की जगह MH-'): (old, new, is it a pipe name, backup suffix)
OLD_NAMES = ((re.compile(r"(?<![A-Za-z0-9])CO-(?=\d)"), "P-", True, ".CO_names.bak"),
             (re.compile(r"(?<![A-Za-z0-9])MH-G(?=\d)"), "J-G", False, ".MH_names.bak"))


RENAMED_FILES = ("_netedit.json", "_network_conduits.csv", "_network_manholes.csv", "_network_edits.csv",
                 "_population.csv", "_wzoning_ui.json", "_wdesign_ui.json")


_RENAME_SEEN = set()            # (out_root, stem) looked at in this run of the server


def rename_old_names(out_root, stem):
    """A network imported before has the sewer's names: pipes CO-<n> (before 21-Oct-2026) and the junctions without a
    drawing label MH-G<n> (before 22-Oct-2026). Renamed once - P-<n>, J-G<n> - in the working state, the saved
    network, its list of changes, its population and the last zoning / design kept for the page, so that all of them
    still match. Each file is kept first as <file>.CO_names.bak / .MH_names.bak. A kind is not renamed when one of its
    new names is already there (two names could meet). Returns the files changed."""
    folder = os.path.join(out_root, stem)
    p = state_path(out_root, stem)
    if (out_root, stem) in _RENAME_SEEN or not os.path.isfile(p):
        return []
    _RENAME_SEEN.add((out_root, stem))
    with open(p, encoding="utf-8") as fh:
        data = json.load(fh)
    chosen = data.get("prefix") or {}         # names chosen on the page at the import (30-Oct-2026): kept as they are
    net = data["net"]
    names = {True: [str(k["label"]) for k in net["conduits"]], False: [str(n) for n in net["nodes"]]}
    done = []
    for old, new, pipe, bak in OLD_NAMES:
        if chosen.get("pipe" if pipe else "node") == ("CO-" if pipe else "MH-"):
            continue
        labels = names[pipe]
        if not any(old.match(x) for x in labels) or any(re.match(re.escape(new) + r"\d", x) for x in labels):
            continue
        for suffix in RENAMED_FILES:
            f = os.path.join(folder, stem + suffix)
            if not os.path.isfile(f):
                continue
            with open(f, encoding="utf-8", newline="") as fh:
                text = fh.read()
            changed = old.sub(new, text)
            if changed == text:
                continue
            if not os.path.isfile(f + bak):
                with open(f + bak, "w", encoding="utf-8", newline="") as fh:
                    fh.write(text)
            with open(f + ".tmp", "w", encoding="utf-8", newline="") as fh:
                fh.write(changed)
            os.replace(f + ".tmp", f)
            done.append(f)
    return done


def load(out_root, stem):
    p = state_path(out_root, stem)
    if not os.path.isfile(p):
        return None
    rename_old_names(out_root, stem)
    with open(p, encoding="utf-8") as fh:
        st = json.load(fh)
    st["_root"] = out_root
    return st


def store(st):
    p = state_path(st["_root"], st["stem"])
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    text = json.dumps({k: v for k, v in st.items() if not k.startswith("_")}, ensure_ascii=False,
                      separators=(",", ":"))                    # one string: much faster than json.dump to a file
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, p)
