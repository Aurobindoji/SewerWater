"""Hindi texts of the design's messages for the map page (user request 30-Oct-2026: the page's messages in Hindi, the
technical terms as they are; the files and logs keep the English). Phrases replaced in order; a message not matched
stays English.

    c = check_hi(c)      a design check {"check", "detail", ...} with "check_hi" / "detail_hi" added
"""
import re

PHRASES = [
    (r"^lowest (\S+) m$", r"सबसे कम \1 m"),
    (r"(\d[\d,]*) junctions below", r"\1 junctions 17 m से कम"),
    (r", its staging (\S+) m is (\S+) m short", r", इसकी staging \1 m, \2 m कम"),
    (r" - no pipe size helps (\d+) of them \(on the way to lower ground\)",
     r" - इनमें से \1 के लिए कोई pipe size काम नहीं आता (नीची ज़मीन के रास्ते में)"),
    (r" - (\d+) not reached in (\d+) rounds of upsizing", r" - \1 पर upsizing के \2 दौर में भी नहीं पहुँचा"),
    (r"(\d+) pipes faster", r"\1 pipes अधिक तेज़"),
    (r"^highest (\S+) m/s$", r"सबसे अधिक \1 m/s"),
    (r"velocity >= (\S+) m/s \(flushing below\)", r"velocity >= \1 m/s (कम हो तो flushing)"),
    (r"(\d+) pipes slower \(mostly at the minimum diameter - scour valves\)",
     r"\1 pipes धीमे (अधिकतर न्यूनतम व्यास पर - scour valves)"),
    (r"residual head well above (\S+) m", r"residual head \1 m से बहुत ऊपर"),
    (r"(\d+) junctions above (\S+) m - consider PRV / smaller staging",
     r"\1 junctions \2 m से ऊपर - PRV या कम staging पर विचार करें"),
    (r"^every junction connected to an OHT$", "हर junction किसी OHT से जुड़ा"),
    (r"(\d+) nodes on (\d+) road piece\(s\) joined to no OHT's pipes - join them to the roads on the map "
     r"\(✎ / a road from them\) or place an OHT there; shown on the map as grey dashed circles",
     r"\1 junctions (\2 सड़क-टुकड़ों पर) किसी OHT के pipes से नहीं जुड़े - उन्हें नक्शे पर सड़कों से जोड़ें "
     r"(✎ / उनसे एक सड़क) या वहाँ OHT रखें; नक्शे पर धूसर बिंदीदार घेरे"),
    (r"(\d+) junctions without a path to an OHT", r"\1 junctions का किसी OHT तक रास्ता नहीं"),
    (r"^barrier lines: no pipe crosses$", "रुकावट रेखाएँ: कोई pipe पार नहीं करता"),
    (r"\(Railway line\)", "(रेलवे लाइन)"), (r"\(Canal / nala\)", "(नहर / नाला)"), (r"\(Other\)", "(अन्य)"),
    (r"(\d+) pipes cut, ending (\S+) m short of the line on both sides", r"\1 pipes कटे, रेखा से दोनों ओर \2 m पहले बंद"),
    (r"new pipe (\S+)", r"नया pipe \1"),
    (r" go\(es\) through", " आर-पार (नहीं कटा)"),
    (r"it crosses no barrier line / zone loop", "किसी रुकावट रेखा / zone लूप को नहीं काटता"),
    (r"no junction within (\S+) m of each of its ends: no pipe made", r"दोनों सिरों के \1 m भीतर junction नहीं - pipe नहीं बना"),
    (r"^(.+): higher ground to new OHTs$", r"\1: ऊँची ज़मीन नई OHTs को"),
    (r"its staging cannot give 17 m there - taken by ", "इसकी staging वहाँ 17 m नहीं दे सकती - ले लिया: "),
    (r"; (\d+) junctions on the way stay with it \(below 17 m\)", r"; रास्ते के \1 junctions इसी के पास (17 m से कम)"),
    (r"^stage population$", "stage की आबादी"),
    (r"(\S+) at \+(\d+) years is less than (\S+) before it", r"+\2 वर्ष पर \1, पहले की \3 से कम"),
    (r"more than 30 m - consider another site \(higher ground\) or a booster",
     "30 m से अधिक - दूसरी जगह (ऊँची ज़मीन) या booster पर विचार करें"),
    (r"^(.+): VFD pump at the outlet$", r"\1: outlet पर VFD pump"),
    (r"\+(\S+) m at (\S+) L/s \(peak\), about (\S+) kW \(efficiency (\S+)\) - its staging (\S+) m cannot give 17 m; the "
     r"OZ stays what its capacity serves, the pump takes the staging as suction head, stops when the tank runs dry, "
     r"bypass inlet-outlet, run from a sensor at the critical node",
     r"+\1 m, \2 L/s (peak) पर, लगभग \3 kW (efficiency \4) - इसकी staging \5 m से 17 m नहीं मिलता; OZ उतना ही जितना "
     r"इसकी क्षमता देती है, pump staging को suction head लेता है, टंकी खाली होने पर रुकता है, inlet-outlet bypass, "
     r"critical node के sensor से चलता है"),
    # a PRV on the map that does nothing (prv.apply)
    (r"no pipe within (\S+) m \(nearest (\S+) m\)", r"\1 m के भीतर कोई pipe नहीं (सबसे पास \2 m)"),
    (r"no pipe within (\S+) m", r"\1 m के भीतर कोई pipe नहीं"),
    (r"a closed pipe \(OZ / DMA boundary valve\)", "बंद pipe (OZ / DMA सीमा का valve)"),
    (r"the area beyond is fed by other pipes too \(a loop\) - no effect; close them or add PRVs there",
     "आगे का इलाका दूसरे pipes से भी पानी पाता है (loop) - कोई असर नहीं; उन्हें बंद करें या वहाँ भी PRV रखें"),
    (r"no junction beyond it", "आगे कोई junction नहीं"),
    (r"not needed - its area's weakest junction has (\S+) m", r"ज़रूरत नहीं - आगे के सबसे कमज़ोर junction पर \1 m"),
    (r"inactive - (\S+) m reaches it, less than its setting", r"निष्क्रिय - वहाँ \1 m पहुँचता है, setting से कम"),
    # the new tube wells (rising.py)
    (r"tube well (.+): its nearest junction (\S+) is in no OZ - not designed",
     r"tube well \1: सबसे पास का junction \2 किसी OZ में नहीं - design नहीं हुआ"),
    (r"(\S+): (\d+) of the (\d+) new tube wells found no site (\S+) m from the others - place them on the map",
     r"\1: \3 में से \2 नए tube wells को दूसरों से \4 m दूर जगह नहीं मिली - नक्शे पर रखें"),
    (r"tube well (.+): no road from it to the OHT of (\S+)", r"tube well \1: वहाँ से \2 की OHT तक कोई सड़क नहीं"),
]
_RX = [(re.compile(a), b) for a, b in PHRASES]


def hi(text):
    """The Hindi of an English message (phrase by phrase); unmatched parts stay as they are."""
    s = str(text or "")
    for rx, b in _RX:
        s = rx.sub(b, s)
    return s


def check_hi(c):
    """A design check with its Hindi texts (kept when already given)."""
    c.setdefault("check_hi", hi(c.get("check")))
    c.setdefault("detail_hi", hi(c.get("detail")))
    return c
