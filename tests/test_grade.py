"""Data grade (user decision 12-Oct-2026): one ground level from a DEM / assumed data makes the run a PFR,
and that is printed on the report and the drawing."""
import ezdxf
import openpyxl

from sewer_app import cad, pipeline, report

from synthetic import INP, synth


def test_survey_levels_give_dpr():
    out = pipeline.run(synth(), INP, log=lambda s: None)
    assert out["grade"] == "DPR"


def test_one_dem_level_makes_it_pfr(tmp_path):
    net = synth()
    net["nodes"]["M5"]["gl_source"] = "DEM (SRTM 30 m)"
    out = pipeline.run(net, INP, log=lambda s: None)
    assert out["grade"] == "PFR"
    assert any("data grade PFR" in w for w in out["warnings"])
    xl = report.write_report(out, str(tmp_path / "d.xlsx"))
    ws = openpyxl.load_workbook(xl, read_only=True)["Summary"]
    first = next(ws.iter_rows(values_only=True))
    assert first[0] == "DATA GRADE" and "NOT VALID FOR A DPR" in first[1]
    p = str(tmp_path / "d.dxf")
    cad.design_drawing(out, p, text_height=1.0)
    titles = [e.dxf.text for e in ezdxf.readfile(p).modelspace().query("TEXT[layer=='SEW_TITLE']")]
    assert titles and "PFR" in titles[0]


def test_pfr_asked_for():
    out = pipeline.run(synth(), dict(INP, data_grade="PFR"), log=lambda s: None)
    assert out["grade"] == "PFR"
