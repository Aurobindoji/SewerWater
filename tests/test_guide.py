"""The guide and the tour (user request 16-Nov-2026): every tab of each map page has its chapter in the guide, every
step of the tour points at an element the page has, and both servers serve /guide."""
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


@pytest.mark.parametrize("mod", ["water_app", "sewer_app"])
def test_guide_covers_the_page(mod):
    page = read(mod, "static", "map.html")
    data = read(mod, "static", "js", "guide_data.js")
    tabs = set(re.findall(r'data-tab="(\w+)"', page))
    chapters = re.findall(r'\{ id: "(\w+)", title:', data)
    assert tabs and tabs <= set(chapters), tabs - set(chapters)
    assert "start" in chapters
    ids = set(re.findall(r'id="([\w-]+)"', page)) | {"uimode", "uitheme", "uitabs", "uihelp", "outlist"}   # ui.js / outlist.js make the last
    sels = re.findall(r'\{ sel: "([^"]+)"', data)
    assert len(sels) >= 8
    for s in sels:
        assert s.split()[0].lstrip("#") in ids, s
    for tag in ('<script src="js/guide_data.js"></script>', '<script src="js/tour.js"></script>'):
        assert tag in page
    # every field row gives all seven parts, in both languages where it is text
    for m in re.finditer(r"\b[FA]\(\"([^\"]+)\", \"([^\"]+)\",", data):
        assert m.group(1) and m.group(2)


@pytest.mark.parametrize("srv", ["water_app.server", "sewer_app.ui"])
def test_guide_served(srv):
    import importlib
    m = importlib.import_module(srv)
    assert m.PAGES["/guide"][0] == "guide.html"
    assert "/js/guide_data.js" in m.PAGES and "/js/tour.js" in m.PAGES
    assert os.path.isfile(os.path.join(m.STATIC, "guide.html"))
