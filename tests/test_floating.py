"""Floating population: 10 % by default, editable per project on the page (user decision 11-Nov-2026; CPHEEO
Annexure 2.8 suggests 1-3 % when no figures are available) - sewer forecast and water criteria."""
import pytest

from sewer_app import population as P
from water_app import ui_api as W


def test_sewer_forecast_takes_the_page_share():
    d = P.forecast(2027, 100000, None, sewage_lpcd=120)
    assert d["floating_share"] == 0.10 and d["floating"]["init"] == 10000
    f = P.forecast(2027, 100000, None, sewage_lpcd=120, floating_share=P.floating_share_of("3"))
    assert f["floating_share"] == 0.03 and f["floating"]["init"] == 3000
    assert f["equivalent"]["init"] == P.xround(3000 * 45 / 150)
    assert f["design"]["ult"] < d["design"]["ult"]
    assert P.settings()["floating_share"] == 0.10                     # the file's default is not changed
    assert P.floating_share_of("") is None and P.floating_share_of(None) is None
    assert P.floating_share_of("0") == 0.0
    for bad in ("abc", "-1", "60"):
        with pytest.raises(ValueError):
            P.floating_share_of(bad)


def test_water_criteria_take_the_page_share():
    assert W._crit({})["floating_share"]["value"] == 0.10
    assert W._crit({"floating_pct": "10"})["floating_share"]["value"] == 0.10
    c = W._crit({"floating_pct": "2.5"})
    assert c["floating_share"]["value"] == 0.025 and "page" in c["floating_share"]["ref"]
    for bad in ("x", "70"):
        with pytest.raises(ValueError):
            W._crit({"floating_pct": bad})
