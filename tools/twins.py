"""The twin files of sewer_app and water_app - only shown, never changed.

sewer_app and water_app share no code (user decision 21-Oct-2026, restated 26-Nov-2026): files that do the same
work are kept as two copies. When one copy is changed, its twin may want the same fix - asked of the user first, and
made as a change of its own. This tool lists, for each twin pair, how alike the two are and which of them changed
since a git revision (default: the last tag).

    python tools/twins.py                 since the last tag
    python tools/twins.py --since REV     since REV
    python tools/twins.py --diff NAME     the two copies of NAME (e.g. repair.py, ui.js) side by side as a diff
"""
import difflib
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEWER, WATER = "sewer_app", "water_app"


def _by_name(top):
    """{file name: its path inside the module} - the module's Python files in any folder (water's are in folders since
    rewrite stage 3) and the page's files; vendor libraries and __init__ left out."""
    out = {}
    base = os.path.join(ROOT, top)
    for d, _, fs in os.walk(base):
        rel = os.path.relpath(d, base).replace(os.sep, "/")
        if "__pycache__" in rel or "vendor" in rel.split("/"):
            continue
        for f in fs:
            if f.endswith((".py", ".js", ".css", ".html")) and f != "__init__.py":
                key = f if f.endswith(".py") else f"static:{f}"
                out.setdefault(key, f"{rel}/{f}".lstrip("./") if rel != "." else f)
    return out


def pairs():
    """(name, sewer path, water path) of the files found in both modules."""
    a, b = _by_name(SEWER), _by_name(WATER)
    return [(k.split(":")[-1], a[k], b[k]) for k in sorted(set(a) & set(b))]


def lines(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read().splitlines()


def alike(a, b):
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    return 2.0 * sum(m.size for m in sm.get_matching_blocks()) / max(1, len(a) + len(b))


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False).stdout.strip()


def report(since):
    changed = set(git("diff", "--name-only", since, "--").splitlines()) | set(
        git("diff", "--name-only", "--").splitlines())
    print(f"twin files of {SEWER} / {WATER}; changed since {since} (or uncommitted)\n")
    print(f"{'file':18s} {'water path':28s} {'sewer':>6s} {'water':>6s} {'alike':>6s}  changed")
    for name, ps, pw in pairs():
        a, b = lines(os.path.join(ROOT, SEWER, ps)), lines(os.path.join(ROOT, WATER, pw))
        r = alike(a, b)
        if r < 0.3:                                      # same name, different work (zoning, design...)
            continue
        cs, cw = f"{SEWER}/{ps}" in changed, f"{WATER}/{pw}" in changed
        mark = {(True, True): "both", (True, False): "sewer only", (False, True): "water only"}.get((cs, cw), "")
        print(f"{name:18s} {pw:28s} {len(a):6d} {len(b):6d} {r:6.0%}  {mark}")


def show(name):
    for n, ps, pw in pairs():
        if n == name:
            a, b = os.path.join(ROOT, SEWER, ps), os.path.join(ROOT, WATER, pw)
            sys.stdout.writelines(l + "\n" for l in difflib.unified_diff(lines(a), lines(b), f"{SEWER}/{ps}",
                                                                           f"{WATER}/{pw}", lineterm=""))
            return
    print(f"no twin named {name}")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--diff":
        show(sys.argv[2])
    elif len(sys.argv) in (1, 3) and (len(sys.argv) == 1 or sys.argv[1] == "--since"):
        report(sys.argv[2] if len(sys.argv) == 3 else git("describe", "--tags", "--abbrev=0"))
    else:
        print(__doc__)
        sys.exit(2)
