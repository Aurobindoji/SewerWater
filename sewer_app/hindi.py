"""Hindi texts of the sewer design's warnings for the map page (user request 30-Oct-2026: the page's messages in Hindi,
the technical terms as they are; the report Excel and the log keep the English). The sewer module's own copy of the
idea of water_app/hindi.py (isolation of sewer and water, 21-Oct-2026). A warning not matched stays English.

    hi(text) -> the Hindi of one warning
"""
import re

PHRASES = [
    (r"stage population: (\S+) at \+(\d+) years is LESS than (\S+) at \+(\d+) years - check the population forecast "
     r"\(CPHEEO 2\.6, p2-9\)",
     r"stage की आबादी: +\2 वर्ष पर \1, +\4 वर्ष की \3 से कम - आबादी का forecast जाँचें (CPHEEO 2.6, p2-9)"),
    (r"cover (\S+) m over the crown is LESS than min_cover_m (\S+) m of design_criteria\.json \((.*?)\) - user decision "
     r"\(start depth (\S+) m\); check house connections and protection under roads",
     r"crown के ऊपर cover \1 m, design_criteria.json के min_cover_m \2 m (\3) से कम - आपका फ़ैसला (start depth \4 m); "
     r"house connections और सड़क के नीचे सुरक्षा जाँचें"),
    (r"data grade PFR \(not DPR\): (\d+) ground level\(s\) from DEM / assumed data, e\.g\. (.*) - survey levels are "
     r"needed for a DPR",
     r"data grade PFR (DPR नहीं): \1 GL DEM / अनुमान से, जैसे \2 - DPR के लिए survey levels चाहिए"),
    (r"(\d+) ground level\(s\) of (\d+) were not in the drawing and were interpolated along the sewer \((.*?)\) - depth "
     r"and cover there are uncertain; take levels on site before a DPR",
     r"\2 में से \1 GL drawing में नहीं थे, sewer के साथ interpolate किए (\3) - वहाँ गहराई और cover अनिश्चित; DPR से पहले "
     r"site पर levels लें"),
    (r"no ground level for: (.*) \(cover not controlled there\)", r"इनका GL नहीं: \1 (वहाँ cover नियंत्रित नहीं)"),
    (r"(\d+) new manhole\(s\) at bends lie on the designed straight grade: the (\S+) mm drop at a change of direction "
     r"\(CPHEEO 3\.20\.3\) is NOT made there - up to (\S+) m of drops in all; add them in the L-section where needed",
     r"मोड़ पर \1 नए manholes सीधी grade पर हैं: दिशा बदलने पर \2 mm का drop (CPHEEO 3.20.3) वहाँ नहीं दिया - कुल \3 m "
     r"तक drops; ज़रूरत हो तो L-section में जोड़ें"),
    (r"outfall (\S+): designed invert (\S+) m is BELOW the fixed level (\S+) m - gravity connection not possible "
     r"\(pumping or re-grading needed\)",
     r"outfall \1: design invert \2 m, तय level \3 m से नीचे - gravity से जुड़ना संभव नहीं (pumping या re-grading चाहिए)"),
    (r"check_basis '(.*)' needs a hydraulic solver - checked on uniform flow instead",
     r"check_basis '\1' के लिए hydraulic solver चाहिए - uniform flow पर जाँचा"),
    (r"(\S+): trunk diameter (\S+) mm is above Table 3\.31 - spacing not checked",
     r"\1: trunk व्यास \2 mm, Table 3.31 से ऊपर - spacing नहीं जाँची"),
    (r"trunk_conduits not found in the network: (.*)", r"trunk_conduits network में नहीं मिले: \1"),
    (r"(\d+) conduit\(s\) carry NO flow - velocity not checked \(no self-cleansing\): (.*)",
     r"\1 conduits में कोई flow नहीं - velocity नहीं जाँची (self-cleansing नहीं): \2"),
    (r"(\d+) conduit\(s\) smaller than the first row of Table 3\.13 - minimum slope not checked: (.*)",
     r"\1 conduits Table 3.13 की पहली पंक्ति से छोटे - न्यूनतम slope नहीं जाँचा: \2"),
    (r"(\d+) conduit\(s\) carry more than the pipe's maximum part-full capacity \(Manning\) - uniform-flow "
     r"velocity/d/D not computed: (.*)",
     r"\1 conduits में pipe की अधिकतम part-full क्षमता (Manning) से अधिक flow - uniform-flow velocity/d/D नहीं निकली: \2"),
    (r"(\d+) conduit\(s\) without node ground level - cover not checked: (.*)",
     r"\1 conduits के node का GL नहीं - cover नहीं जाँचा: \2"),
    (r"maximum sewer depth NOT checked - key '(.*)' not found in design_criteria\.json 'sewer'",
     r"sewer की अधिकतम गहराई नहीं जाँची - design_criteria.json 'sewer' में key '\1' नहीं"),
    (r"(\d+) manhole\(s\) deeper than (\S+) m - lift / pumping station needed \(key '(.*?)'\): (.*)",
     r"\1 manholes \2 m से गहरे - lift / pumping station चाहिए (key '\3'): \4"),
    (r"(\d+) manhole\(s\) deeper than (\S+) m \(CPHEEO\) - no lift stations: accepted up to (\S+) m, justify in the DPR "
     r"\(key '(.*?)'\): (.*)",
     r"\1 manholes \2 m (CPHEEO) से गहरे - lift stations नहीं: \3 m तक स्वीकार, DPR में औचित्य दें (key '\4'): \5"),
    (r"(\d+) manhole\(s\) deeper than the project limit (\S+) m - split into zones with pumping stations \(zoning\): (.*)",
     r"\1 manholes project सीमा \2 m से गहरे - pumping stations के साथ zones में बाँटें (zoning): \3"),
]
_RX = [(re.compile(a, re.S), b) for a, b in PHRASES]


def hi(text):
    """The Hindi of a warning (the first pattern that matches the whole of it); else the English as it is."""
    s = str(text or "")
    for rx, b in _RX:
        if rx.fullmatch(s):
            return rx.sub(b, s)
    return s
