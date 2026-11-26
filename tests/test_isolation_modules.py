"""sewer_app and water_app share no code (user decision 21-Oct-2026, restated 26-Nov-2026: when both were one code a
change for one broke the other). Neither imports the other, the launcher only starts their servers, and nothing in
the app imports from tests/ or tools/. Imports inside functions count too."""
import ast
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULES = ("sewer_app", "water_app")
# what the launcher may take of each module: its server, to start it (water's in web/ since rewrite stage 3)
LAUNCHER_MAY = {"sewer_app.ui", "water_app.web.server"}


def _imports(path):
    """The absolute names a file imports (relative imports resolved from the file's own package)."""
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), path)
    here = os.path.relpath(os.path.dirname(path), ROOT).replace(os.sep, ".")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name, node.lineno
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = here.split(".")[: len(here.split(".")) - node.level + 1]
                mod = ".".join(base + ([node.module] if node.module else []))
            else:
                mod = node.module or ""
            yield mod, node.lineno
            for a in node.names:
                yield f"{mod}.{a.name}", node.lineno


def _files(top):
    for d, _, fs in os.walk(os.path.join(ROOT, top)):
        if "__pycache__" in d:
            continue
        for f in fs:
            if f.endswith(".py"):
                yield os.path.join(d, f)


def _top(name):
    return name.split(".")[0]


def test_sewer_and_water_never_import_each_other():
    bad = []
    for mod in MODULES:
        other = [m for m in MODULES if m != mod][0]
        for path in _files(mod):
            for name, line in _imports(path):
                if _top(name) in (other, "tests", "tools", "launcher"):
                    bad.append(f"{os.path.relpath(path, ROOT)}:{line} imports {name}")
    assert not bad, "\n".join(bad)


def test_the_launcher_only_starts_the_modules():
    bad = []
    for path in list(_files("launcher")) + [os.path.join(ROOT, "app.py")]:
        for name, line in _imports(path):
            # `from sewer_app import ui` gives "sewer_app" (the package) and "sewer_app.ui" (what is taken)
            # (and "water_app.web", the package of water's server)
            parent_of_allowed = any(m.startswith(name + ".") for m in LAUNCHER_MAY)
            if _top(name) in MODULES and name not in LAUNCHER_MAY and name not in MODULES and not parent_of_allowed:
                bad.append(f"{os.path.relpath(path, ROOT)}:{line} imports {name}")
    assert not bad, "\n".join(bad)
