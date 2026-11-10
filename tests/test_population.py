"""Population forecast (population.py) as the Riverside DPR: its census gives X, Y and r of sheet 'T', the three methods,
the floating population and the default rate without census (user decision 22-Oct-2026)."""
import pytest

from sewer_app import population as P

RIVERSIDE = [(1951, 376834), (1961, 498567), (1971, 672634), (1981, 825717), (1991, 1139236), (2001, 1374963),
             (2011, 1636569), (2025, 2679842)]


def test_growth_as_riverside_sheet_T():
    _, X, Y, r = P.growth(RIVERSIDE)
    assert round(X, 2) == 286418.57 and round(Y, 2) == 103910.33 and round(r * 100, 2) == 28.74   # 'T' L55, P55, U55


def test_methods_and_floating():
    f = P.forecast(2025, 2679842, RIVERSIDE, sewage_lpcd=120)          # water 150 lpcd -> floating at 45 / 150
    by = f["by_method"]
    # Riverside 'T' M102 / K130 / L157 project 1.7 decades from 2025 to 2042; here 1.5 and 3 decades from the base year
    assert by["arithmetical"]["mid"] == P.ceil5(2679842 + 1.5 * f["X"])
    assert by["incremental"]["ult"] == P.ceil5(2679842 + 3 * f["X"] + 3 * 4 * 0.5 * f["Y"])
    assert by["geometrical"]["ult"] == P.ceil5(2679842 * (1 + f["r"]) ** 3)
    assert f["method"] == "geometrical" and f["pop"] == by["geometrical"]
    assert f["floating"]["init"] == 267984 and f["equivalent"]["init"] == P.xround(267984 * 45 / 150)
    assert f["design"]["ult"] == f["pop"]["ult"] + f["equivalent"]["ult"]


def test_default_rate_and_parse():
    f = P.forecast(2027, 100000, None)
    assert f["default_rate"] and f["r"] == P.settings()["default_decadal_rate"] and "arithmetical" not in f["by_method"]
    assert P.parse_census("2001 1374963, 2011 1636569\n1991 1139236") == [(1991, 1139236), (2001, 1374963), (2011, 1636569)]
    with pytest.raises(ValueError):
        P.parse_census("2001 1374963, 2011")
