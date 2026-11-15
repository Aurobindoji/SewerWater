"""Every relative import in the app's packages names a module or a name that exists there (restructure, 15-Nov-2026:
code moved between modules must not leave an import - often one inside a function, run only on some path - asking
the old module for it)."""
import ast
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def modules(pkg):
    """{dotted name inside the package ("" = its __init__): file}"""
    base = os.path.join(ROOT, pkg)
    out = {}
    for dp, _, fs in os.walk(base):
        if "__pycache__" in dp:
            continue
        for f in fs:
            if f.endswith(".py"):
                rel = os.path.relpath(os.path.join(dp, f), base)[:-3].replace(os.sep, ".")
                if rel == "__init__":
                    rel = ""
                elif rel.endswith(".__init__"):
                    rel = rel[:-9]
                out[rel] = os.path.join(dp, f)
    return out


def top_names(path):
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    out = set()
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                out |= {e.id for e in ast.walk(t) if isinstance(e, ast.Name)}
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            out |= {(a.asname or a.name).split(".")[0] for a in n.names}
    return out


@pytest.mark.parametrize("pkg", ["sewer_app", "water_app", "launcher"])
def test_relative_imports_resolve(pkg):
    mods = modules(pkg)
    bad = []
    for mod, path in mods.items():
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        here = mod.split(".") if mod else []
        parent0 = here if path.endswith("__init__.py") else here[:-1]
        for n in ast.walk(tree):
            if not (isinstance(n, ast.ImportFrom) and n.level):
                continue
            parent = parent0[:len(parent0) - (n.level - 1)]
            target = ".".join(parent + ([n.module] if n.module else []))
            if target not in mods:
                bad.append(f"{mod}:{n.lineno}: no module {target!r}")
                continue
            names = top_names(mods[target])
            for a in n.names:
                if a.name != "*" and a.name not in names and ".".join(filter(None, [target, a.name])) not in mods:
                    bad.append(f"{mod}:{n.lineno}: {a.name} not in {target or pkg}")
    assert not bad, bad
