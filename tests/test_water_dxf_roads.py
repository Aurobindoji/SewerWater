"""A survey drawing's roads as the map's layout (17-Nov-2026): the road centreline layer and the survey points'
heights become a KML of roads and GL points (netedit.dxf_roads_kml) that the page opens as a project of its own."""
import xml.etree.ElementTree as ET

import ezdxf
import pytest

from water_app.net import netedit

X0, Y0 = 500000.0, 2800000.0                     # UTM 44N (mock place)
NS = {"k": "http://www.opengis.net/kml/2.2"}


def _survey(path):
    doc = ezdxf.new()
    msp = doc.modelspace()
    for lay in ("CENTER LINE", "BOE", "Unknown_Point_Feature", "Elev10"):
        doc.layers.add(lay)
    for i in range(4):                                                   # a road grid, 100 m apart
        msp.add_lwpolyline([(X0, Y0 + 100 * i), (X0 + 300, Y0 + 100 * i)], dxfattribs={"layer": "CENTER LINE"})
        msp.add_lwpolyline([(X0 + 100 * i, Y0), (X0 + 100 * i, Y0 + 300)], dxfattribs={"layer": "CENTER LINE"})
        msp.add_lwpolyline([(X0, Y0 + 100 * i + 4), (X0 + 300, Y0 + 100 * i + 4)], dxfattribs={"layer": "BOE"})
    k = 0
    for i in range(7):                                                   # survey points with their height
        for j in range(7):
            z = 78.0 + 0.01 * k
            msp.add_point((X0 + 50 * i, Y0 + 50 * j, z), dxfattribs={"layer": "Unknown_Point_Feature"})
            msp.add_text(f"{z:.3f}", dxfattribs={"layer": "Elev10", "height": 0.5, "insert": (X0 + 50 * i + 1, Y0 + 50 * j)})
            k += 1
    msp.add_point((X0 + 10, Y0 + 10, 778.1), dxfattribs={"layer": "Unknown_Point_Feature"})      # a typing error
    doc.saveas(path)


def test_roads_and_levels_to_kml(tmp_path):
    path = str(tmp_path / "survey.dxf")
    _survey(path)
    r = netedit.dxf_roads_kml(path, ["CENTER LINE"])
    assert r["roads"] == 8 and r["spots"] == 2 * 49 and r["far"] == 1
    root = ET.fromstring(r["kml"].split("\n", 1)[1])
    lines = root.findall(".//k:LineString", NS)
    gl = [float(v.text) for v in root.findall(".//k:Data[@name='GL']/k:value", NS)]
    assert len(lines) == 8 and len(gl) == 98 and 78.0 <= min(gl) and max(gl) < 79
    lon, lat = map(float, lines[0].find("k:coordinates", NS).text.split()[0].split(","))
    assert 80.9 < lon < 81.1 and 25.2 < lat < 25.4                      # on the map (UTM 44N -> lon / lat)


def test_only_the_chosen_level_layer(tmp_path):
    path = str(tmp_path / "survey.dxf")
    _survey(path)
    r = netedit.dxf_roads_kml(path, ["CENTER LINE"], ["Unknown_Point_Feature"])
    assert r["spots"] == 49 and r["far"] == 1


def test_a_local_drawing_is_refused(tmp_path):
    path = str(tmp_path / "survey.dxf")
    _survey(path)
    with pytest.raises(ValueError):
        netedit.dxf_roads_kml(path, ["CENTER LINE"], epsg=None)
    with pytest.raises(ValueError):
        netedit.dxf_roads_kml(path, ["NO SUCH LAYER"])
