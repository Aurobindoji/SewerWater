"""The layers of each module (user decision 15-Nov-2026: the app restructured in stages; water in folders since rewrite
stage 3, 26-Nov-2026): a module imports only from its own layer or the ones below it - core (calculations) < net
(the network read and mended) < project (a project's files) < output (DPR, report, drawings) < service (the work
behind a page call) < web (the server). The imports that break the rule today are listed in KNOWN; a new break, or a
fixed one still listed, fails here, and so does a new module without a layer. Imports inside functions count too,
relative or absolute."""
import ast
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORDER = ["core", "net", "project", "output", "service", "web"]
PACKAGE = {"", "HOME", "DATA_DIR", "DesignError", "PKG", "ROOT"}   # the package's own __init__: below every layer

LAYERS = {
    "water_app": {
        "core": "core.geo core.hindi core.network core.spacing core.store core.zone_geom "
                "engine.barriers engine.demand engine.design engine.hydraulics engine.population engine.prv "
                "engine.rising engine.simulate engine.zoning intze.design intze.calc",
        "net": "net.cad net.dxf_extract net.dxf_inspect net.layout net.netedit net.repair",
        "project": "data.city_wards data.project data.rates data.wards",
        "output": "out.dpr intze.drawing",
        "service": "run.design_run intze.api out.kmlmap run.layout_cmd run.results run.sim_run out.wdxf "
                   "run.zone_lines run.zoning_run",
        "web": "web.server __main__",
    },
    "sewer_app": {
        "core": "core.geo core.hindi core.network core.spacing core.store "
                "engine.barriers engine.check engine.criteria engine.design engine.edits engine.flows engine.hydraulics "
                "engine.pipeline engine.population engine.pumping engine.quantities engine.rising_main engine.zoning",
        "net": "net.dxf_extract net.dxf_inspect net.layout net.netedit net.repair",
        "project": "data.inputs data.project data.results",
        "output": "out.cad out.dpr out.lsection out.report out.zone_export out.zoning_out",
        "service": "run.design_run run.layout_cmd run.zoning_run",
        "web": "web.server __main__",
    },
}
# the breaks of today, each to go in a stage of the restructure
KNOWN = {
    "water_app": set(),
    "sewer_app": set(),
}
UNITS = {"water_app": {"out.dpr", "net.netedit", "net.dxf_inspect"}, "sewer_app": {"out.dpr"}}   # subpackages counted as one module


def _modules(pkg):
    """{dotted module inside the package: file}"""
    out = {}
    base = os.path.join(ROOT, pkg)
    for d, _, fs in os.walk(base):
        if "__pycache__" in d:
            continue
        for f in fs:
            if f.endswith(".py"):
                rel = os.path.relpath(os.path.join(d, f), base)[:-3].replace(os.sep, ".")
                out[rel] = os.path.join(d, f)
    return out


def _unit(pkg, mod):
    """The layered unit a dotted module belongs to ('' for the package's and its folders' __init__)."""
    if mod == "__init__" or mod.endswith(".__init__"):
        return "" if mod.count(".") <= 1 else _unit(pkg, mod[:-9])
    for u in UNITS[pkg]:
        if mod == u or mod.startswith(u + "."):
            return u
    return mod


def imports(pkg):
    """{unit: the package's units it imports} (absolute and relative imports, those inside functions too)."""
    mods = _modules(pkg)
    known = set(mods) | {m[:-9] for m in mods if m.endswith(".__init__")}
    out = {}
    for mod, path in mods.items():
        me = _unit(pkg, mod)
        if me == "":
            continue
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        parts = mod.split(".")
        here = parts[:-1]                                    # the folder the file is in
        names = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom):
                if n.level:
                    base = here[:len(here) - (n.level - 1)]
                    target = ".".join(base + ([n.module] if n.module else []))
                elif n.module and (n.module == pkg or n.module.startswith(pkg + ".")):
                    target = n.module[len(pkg) + 1:] if n.module != pkg else ""
                else:
                    continue
                for a in n.names:
                    full = f"{target}.{a.name}" if target else a.name
                    names.add(full if full in known else target)
            elif isinstance(n, ast.Import):
                for a in n.names:
                    if a.name.startswith(pkg + "."):
                        names.add(a.name[len(pkg) + 1:])
        units = {_unit(pkg, x) for x in names if x in known or x == ""} - {"", me}
        out.setdefault(me, set()).update(u for u in units if u not in PACKAGE)
    return out


@pytest.mark.parametrize("pkg", sorted(LAYERS))
def test_layers(pkg):
    layer = {m: ORDER.index(k) for k, ms in LAYERS[pkg].items() for m in ms.split()}
    graph = imports(pkg)
    assert not set(graph) - set(layer), f"modules without a layer: {sorted(set(graph) - set(layer))}"
    breaks = {(m, i) for m, deps in graph.items() for i in deps
              if i in layer and (layer[i] > layer[m] or i == "__main__")}
    assert not breaks - KNOWN[pkg], f"new imports against the layers: {sorted(breaks - KNOWN[pkg])}"
    assert not KNOWN[pkg] - breaks, f"fixed - take out of KNOWN: {sorted(KNOWN[pkg] - breaks)}"


@pytest.mark.parametrize("pkg", sorted(LAYERS))
def test_every_folder_holds_one_kind_of_work(pkg):
    """Rewrite stages 3-4: the folders of each module keep to their layers - core/ and engine/ calculations, net/ the
    network, data/ the project's files, out/ what the app gives out, run/ the page calls' work, web/ the server."""
    allowed = {"core": {"core"}, "engine": {"core"}, "net": {"net"}, "data": {"project"}, "out": {"output", "service"},
               "run": {"service"}, "web": {"web"}, "intze": {"core", "output", "service"}}
    layer = {m: k for k, ms in LAYERS[pkg].items() for m in ms.split()}
    bad = [m for m in layer if "." in m and layer[m] not in allowed[m.split(".")[0]]]
    assert not bad, bad
