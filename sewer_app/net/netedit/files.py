"""netedit: the working state on disk - its path, load / store."""
import json
import os


# ---------------------------------------------------------------- files
def state_path(out_root, stem):
    return os.path.join(out_root, stem, f"{stem}_netedit.json")


def load(out_root, stem):
    p = state_path(out_root, stem)
    if not os.path.isfile(p):
        return None
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
