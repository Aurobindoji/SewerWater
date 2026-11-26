"""The twin files of sewer_app and water_app - only shown, never changed.

sewer_app and water_app share no code (user decision 21-Oct-2026, restated 26-Nov-2026): files that do the same
work are kept as two copies. When one copy is changed, its twin may want the same fix - asked of the user first, and
made as a change of its own. This tool lists, for each twin pair, how alike the two are and which of them changed
since a git revision (default: the last tag).

    python tools/twins.py                 since the last tag
    python tools/twins.py --since REV     since REV
    python tools/twins.py --diff NAME     the two copies of NAME (e.g. repair.py, js/ui.js) side by side as a diff
"""
import difflib
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEWER, WATER = "sewer_app", "water_app"


def pairs():
    """The relative paths found in both modules (Python files and the page's scripts)."""
    out = []
    for sub, ext in (("", ".py"), ("static/js", ".js"), ("static", ".js"), ("static", ".css"), ("static", ".html")):
        a, b = os.path.join(ROOT, SEWER, sub), os.path.join(ROOT, WATER, sub)
        if not (os.path.isdir(a) and os.path.isdir(b)):
            continue
        for f in sorted(set(os.listdir(a)) & set(os.listdir(b))):
            if f.endswith(ext) and f != "__init__.py" and os.path.isfile(os.path.join(a, f)):
                out.append(f"{sub}/{f}".lstrip("/"))
    return out


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
    print(f"{'file':28s} {'sewer':>6s} {'water':>6s} {'alike':>6s}  changed")
    for rel in pairs():
        a, b = lines(os.path.join(ROOT, SEWER, rel)), lines(os.path.join(ROOT, WATER, rel))
        r = alike(a, b)
        if r < 0.3:                                      # same name, different work (zoning, design...)
            continue
        cs, cw = f"{SEWER}/{rel}" in changed, f"{WATER}/{rel}" in changed
        mark = {(True, True): "both", (True, False): "sewer only", (False, True): "water only"}.get((cs, cw), "")
        print(f"{rel:28s} {len(a):6d} {len(b):6d} {r:6.0%}  {mark}")


def show(rel):
    a, b = os.path.join(ROOT, SEWER, rel), os.path.join(ROOT, WATER, rel)
    sys.stdout.writelines(l + "\n" for l in difflib.unified_diff(lines(a), lines(b), f"{SEWER}/{rel}",
                                                                   f"{WATER}/{rel}", lineterm=""))


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--diff":
        show(sys.argv[2])
    elif len(sys.argv) in (1, 3) and (len(sys.argv) == 1 or sys.argv[1] == "--since"):
        report(sys.argv[2] if len(sys.argv) == 3 else git("describe", "--tags", "--abbrev=0"))
    else:
        print(__doc__)
        sys.exit(2)
