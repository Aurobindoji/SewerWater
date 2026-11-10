"""The Excel report is written and holds the expected sheets (the cell-by-cell comparison with the
SewerGEMS-era oakdale_B workbook is tools/compare_with_agent_report.py - it needs the original scripts)."""
import openpyxl

from sewer_app import pipeline, report

from synthetic import INP, synth


def test_report_with_fixed_outfall(tmp_path):
    net = synth()
    free = pipeline.run(net, INP, log=lambda s: None)["node_info"]["OUT"]["invert"]
    out = pipeline.run(net, dict(INP, fixed={"OUT": free + 0.15}), log=lambda s: None)
    path = report.write_report(out, str(tmp_path / "synthetic_sewer_design.xlsx"), source="synthetic")
    wb = openpyxl.load_workbook(path, read_only=True)
    for name in ("Summary", "Cost", "Design", "Manholes", "Upsized for fall", "Length by size", "Depth bands",
                 "Qty sewer", "Flows", "Population", "Check"):
        assert name in wb.sheetnames, name
    assert wb["Design"].max_row == len(out["res"]) + 1
    assert wb["Check"].max_row == len(out["net_split"]["conduits"]) + 1
