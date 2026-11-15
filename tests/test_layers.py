"""The layers of each module (user decision 15-Nov-2026: the app restructured in stages): a module imports only from
its own layer or the ones below it - core (calculations) < net (the network read and mended) < output (DPR, report,
drawings) < service (the work behind a page call) < web (the server). The imports that break the rule today are
listed in KNOWN; each stage of the restructure takes some out. A new break, or a fixed one still listed, fails here,
and so does a new module without a layer. Imports inside functions count too."""
import ast
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORDER = ["core", "net", "output", "service", "web"]
PACKAGE = {"HOME", "DATA_DIR", "DesignError"}           # the package's own __init__ names: below every layer

LAYERS = {
    "water_app": {
        "core": "barriers demand design geo hindi hydraulics intze intze_calc network population prv rising spacing "
                "zone_geom zoning",
        "net": "cad dxf_extract dxf_inspect layout netedit repair",
        "output": "dpr dpr_civil dpr_em dpr_emd dpr_format dpr_front dpr_more dpr_rm dpr_tech intze_dwg rates wdxf",
        "service": "city_wards intze_api layout_cmd ui_api",
        "web": "server __main__",
    },
    "sewer_app": {
        "core": "barriers check criteria design edits flows geo hindi hydraulics network pipeline population pumping "
                "rising_main spacing zoning",
        "net": "dxf_extract dxf_inspect layout netedit repair",
        "output": "cad dpr dpr_em dpr_format dpr_front dpr_more lsection report zone_export",
        "service": "",
        "web": "ui __main__",
    },
}
# the breaks of today (15-Nov-2026), each to go in a stage of the restructure
KNOWN = {
    "water_app": {("city_wards", "server"), ("intze_api", "server"), ("ui_api", "server"), ("wdxf", "server"),
                  ("wdxf", "ui_api"), ("dpr_tech", "ui_api")},
    "sewer_app": {("zoning", "cad"), ("zoning", "report"), ("ui", "__main__")},
}


def imports(pkg):
    out = {}
    folder = os.path.join(ROOT, pkg)
    for f in sorted(os.listdir(folder)):
        if not f.endswith(".py") or f == "__init__.py":
            continue
        with open(os.path.join(folder, f), encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        names = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom) and n.level == 1:
                names.update([n.module.split(".")[0]] if n.module else [a.name for a in n.names])
        out[f[:-3]] = names - PACKAGE
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
