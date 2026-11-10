"""The page's messages in Hindi (user request 30-Oct-2026), the technical terms as they are; files and logs keep the
English. Water design checks and sewer design warnings."""
from sewer_app import hindi as shi
from water_app import hindi as whi


def test_water_check_texts():
    c = whi.check_hi({"check": "velocity >= 0.3 m/s (flushing below)",
                      "detail": "12553 pipes slower (mostly at the minimum diameter - scour valves)"})
    assert c["check_hi"] == "velocity >= 0.3 m/s (कम हो तो flushing)"
    assert c["detail_hi"] == "12553 pipes धीमे (अधिकतर न्यूनतम व्यास पर - scour valves)"
    assert whi.hi("Barrier 1 (Railway line): 19 pipes cut, ending 1 m short of the line on both sides") == \
        "Barrier 1 (रेलवे लाइन): 19 pipes कटे, रेखा से दोनों ओर 1 m पहले बंद"
    assert whi.check_hi({"check": "x", "detail": "y", "check_hi": "क", "detail_hi": "ख"})["check_hi"] == "क"   # kept


def test_sewer_warning_texts():
    w = ("3 manhole(s) deeper than the project limit 5 m - split into zones with pumping stations (zoning): "
         "MH-1, MH-2, MH-3")
    assert shi.hi(w) == "3 manholes project सीमा 5 m से गहरे - pumping stations के साथ zones में बाँटें (zoning): MH-1, MH-2, MH-3"
    assert shi.hi("no ground level for: MH-9 (cover not controlled there)") == "इनका GL नहीं: MH-9 (वहाँ cover नियंत्रित नहीं)"
    assert shi.hi("a message not known") == "a message not known"                     # stays English
