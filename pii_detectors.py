"""
pii_detectors.py

Pluggable PII detection for the Red Herring Prospectus redaction tool.

Each detector is a function: (text: str) -> list[Span]
where Span = (start, end, label, matched_text)

Detectors are registered in DETECTORS (regex-based, cheap, run first) and
NER_DETECTOR (spaCy-based, run per-paragraph). detect_all() merges both,
resolving overlaps by priority (regex PII types are considered more
trustworthy / precise than generic NER tags for this document).
"""

import re
import spacy

# ---------------------------------------------------------------------------
# spaCy model (loaded once)
# ---------------------------------------------------------------------------
_NLP = spacy.load("en_core_web_sm")

Span = tuple  # (start, end, label, text)

# ---------------------------------------------------------------------------
# Regex detectors
# ---------------------------------------------------------------------------

EMAIL_RE = re.compile(r"[\w.\-]+@[\w\-]+\.[\w.\-]+")

# Indian phone numbers as they actually appear in this document:
# "+91 20 4505 3237", "91 22 40094400", "+91 81081 1494", bare 10-digit, etc.
PHONE_RE = re.compile(
    r"(?<!\d)"
    r"(?:\+?91[\s\-]?)?"
    r"(?:\(0\)[\s\-]?)?"
    r"\d{2,5}[\s\-]?\d{3,4}[\s\-]?\d{3,4}"
    r"(?!\d)"
)
# Guard: a bare match must contain at least 10 digits total to count as a phone
# (avoids matching things like page/paragraph numbers or plain dates).

# Physical address cue lines: "Registered Office: ...", "Corporate Office: ...",
# "Registered and Corporate Office: ...", up to the next semicolon/period that
# ends the address clause (bounded to a single sentence/clause, NOT the whole
# paragraph — an earlier version of this detector nuked entire multi-sentence
# paragraphs and had to be fixed).
ADDRESS_CUE_RE = re.compile(
    r"(Registered(?:\s+and\s+Corporate)?\s+Office|Corporate\s+Office|"
    r"Registered\s+Office\s+of\s+our\s+Company)\s*:\s*"
    r"([^.;\n]+)"
)

SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CREDIT_CARD_RE = re.compile(r"\b(?:\d[ -]?){13,16}\b")
IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
DOB_CUE_RE = re.compile(
    r"(?:Date of Birth|DOB|born on)\D{0,5}"
    r"((?:0?[1-9]|[12]\d|3[01])[/\-](?:0?[1-9]|1[0-2])[/\-](?:19|20)\d{2}"
    r"|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s+(?:19|20)\d{2})",
    re.IGNORECASE,
)


def detect_emails(text):
    return [(m.start(), m.end(), "EMAIL", m.group()) for m in EMAIL_RE.finditer(text)]


def detect_phones(text):
    spans = []
    for m in PHONE_RE.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if len(digits) >= 10:
            spans.append((m.start(), m.end(), "PHONE", m.group()))
    return spans


INDIAN_STATES = (
    "Maharashtra|Gujarat|Karnataka|Tamil Nadu|Delhi|Uttar Pradesh|"
    "West Bengal|Rajasthan|Telangana|Kerala|Punjab|Haryana|Bihar|"
    "Madhya Pradesh|Andhra Pradesh"
)

# Free-standing address blocks (no "Registered Office:" cue) -- these are
# short paragraphs that are ENTIRELY an address, typically ending in an
# Indian PIN code followed by a state name, e.g.
# "Bandra Kurla Complex, Bandra (E) Mumbai - 400 051, Maharashtra, India".
# Bounded to short paragraphs (<250 chars) and requiring no sentence-ending
# punctuation before the PIN, so this does not swallow prose paragraphs
# that merely mention a state in passing.
FREESTANDING_ADDRESS_RE = re.compile(
    r"^(?!.*[.!?]\s)[^.!?]{5,180}?\d{3}[\s\-]?\d{3},?\s*(?:" + INDIAN_STATES + r")\b[^.]{0,40}$"
)

# Variant for addresses that end in a PIN code but don't repeat the state
# name in the SAME paragraph -- this happens when a table cell splits an
# address across two paragraphs (e.g. "...Khed Pune - 410 501" as one
# paragraph, "Maharashtra, India" as a separate paragraph directly below
# it). Bounded tightly (short paragraph, ends in the PIN, no sentence
# punctuation) so it doesn't over-match ordinary prose containing numbers.
FREESTANDING_ADDRESS_NO_STATE_RE = re.compile(
    r"^(?!.*[.!?]\s)(?=.*\b(?:Village|Road|Nagar|Taluka|Building|Complex|"
    r"Street|Lane|Society|Colony|Chowk|Marg|Floor|Wing|Tower|Plot|Survey)\b)"
    r"[^.!?]{10,150}?\d{3}[\s\-]?\d{3}\s*$"
)


def detect_addresses(text):
    spans = []
    for m in ADDRESS_CUE_RE.finditer(text):
        # Only redact the address value (group 2), not the "Registered Office:" label
        spans.append((m.start(2), m.end(2), "ADDRESS", m.group(2)))

    if not spans:
        stripped = text.strip()
        if FREESTANDING_ADDRESS_RE.match(stripped) or FREESTANDING_ADDRESS_NO_STATE_RE.match(stripped):
            start = text.index(stripped)
            spans.append((start, start + len(stripped), "ADDRESS", stripped))
    return spans


def detect_ssn(text):
    return [(m.start(), m.end(), "SSN", m.group()) for m in SSN_RE.finditer(text)]


def detect_credit_card(text):
    spans = []
    for m in CREDIT_CARD_RE.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if 13 <= len(digits) <= 16:
            spans.append((m.start(), m.end(), "CREDIT_CARD", m.group()))
    return spans


def detect_ip(text):
    spans = []
    for m in IP_RE.finditer(text):
        parts = m.group().split(".")
        if all(0 <= int(p) <= 255 for p in parts):
            spans.append((m.start(), m.end(), "IP_ADDRESS", m.group()))
    return spans


def detect_dob(text):
    spans = []
    for m in DOB_CUE_RE.finditer(text):
        spans.append((m.start(1), m.end(1), "DOB", m.group(1)))
    return spans


# Regex detectors run on every paragraph, in priority order (earlier = higher
# priority when spans overlap). Populated after detect_allcaps_names is
# defined below (it's grouped with the regex detectors conceptually, even
# though it uses NLP-adjacent heuristics rather than a fixed regex).
DETECTORS = []

# ---------------------------------------------------------------------------
# NER detector (spaCy) for PERSON and ORG (company) names
# ---------------------------------------------------------------------------

# Generic capitalized legal/procedural/financial terms that spaCy's base
# English model frequently mistags as PERSON or ORG in this kind of dense
# financial/legal document. Built up during manual precision evaluation.
NER_STOPLIST = {
    "offer", "the offer", "promoters", "directors", "board", "company",
    "our company", "maharashtra", "india", "companies act", "sebi",
    "sebi icdr", "icdr regulations", "rbi", "nse", "bse", "gst", "roc",
    "trade payable", "trade payables", "marine insurance", "book running",
    "lead managers", "book running lead managers", "anchor investors",
    "qib", "nii", "rii", "kmp", "cfo", "ceo", "cs", "pan", "cin", "ifsc",
    "gstin", "tan", "din", "the company", "the board", "articles of association",
    "memorandum of association", "red herring prospectus", "draft red herring prospectus",
    "prospectus", "the offer document", "statutory auditors", "peer review",
    "registrar of companies", "stock exchanges", "designated stock exchange",
    "bid/offer closing day", "bid/offer opening day", "bid/offer period",
    "registrar of companies maharashtra", "definitions", "currency",
    "abbreviations", "reference rate", "selling shareholder", "pre-offer",
    "post-offer", "corporate office", "registered office",
    "registered and corporate office", "scra", "sebi act", "fema",
    "income tax act", "companies act, 2013", "companies act, 1956",
    "equity shares", "the equity shares", "our promoters", "our directors",
    "key managerial personnel", "senior management",
    # Place names in this document that spaCy's base model mistags as
    # ORG/PERSON when they appear outside an address context. Address
    # values themselves are still fully redacted by the ADDRESS detector;
    # this only prevents *standalone* mentions of these place names
    # elsewhere in the document from being wrongly redacted as company
    # or person names.
    "pune", "mumbai", "baner", "chakan", "khed", "gujarat",
    "chakan taluka", "chakan taluka - khed", "village birdewadi",
}


def detect_ner(text):
    spans = []
    doc = _NLP(text)
    for ent in doc.ents:
        if ent.label_ not in ("PERSON", "ORG"):
            continue
        norm = ent.text.strip().lower()
        if norm in NER_STOPLIST:
            continue
        if len(norm) < 3:
            continue
        # Skip single generic words that are almost certainly false positives
        if norm.split()[0] in ("the", "our", "such", "any", "an", "a"):
            continue
        label = "PERSON" if ent.label_ == "PERSON" else "COMPANY"
        spans.append((ent.start_char, ent.end_char, label, ent.text))
    return spans


# ---------------------------------------------------------------------------
# ALL-CAPS name detector
# ---------------------------------------------------------------------------
# spaCy's en_core_web_sm is trained overwhelmingly on mixed-case text and
# essentially never recognizes names written in ALL CAPS as PERSON entities
# (confirmed during evaluation: en_core_web_sm returns zero entities for
# "KUSHAL SUBBAYYA HEGDE" even in a full sentence). Indian prospectuses
# routinely list promoters/directors in ALL CAPS on the cover page and in
# section headers, which is exactly the highest-visibility PII in the
# document -- so this is handled with a dedicated heuristic rather than
# relying on the general NER model.
#
# Heuristic: a run of 2-4 ALL-CAPS words (letters only, each 2+ chars) is
# treated as a candidate name. To avoid flagging ALL-CAPS acronym strings
# or section headers ("DEFINITIONS AND ABBREVIATIONS"), a candidate is only
# kept if it does NOT match a small list of common ALL-CAPS boilerplate
# words, AND either (a) appears in a comma/slash-separated list of 2+ such
# runs (a strong signal this is a name list, e.g. a promoters/directors
# line), or (b) is immediately preceded by a name-introducing cue such as
# "MR.", "MS.", "OUR PROMOTERS:", "DIRECTORS:", etc.
ALLCAPS_STOPWORDS = {
    "AND", "THE", "OF", "FOR", "OUR", "US", "WE", "IN", "TO", "ON", "AT",
    "OFFER", "COMPANY", "LIMITED", "PRIVATE", "TRUST", "FAMILY", "INDIA",
    "PROMOTERS", "DIRECTORS", "REGISTERED", "OFFICE", "CORPORATE",
    "DETAILS", "PUBLIC", "TOTAL", "SIZE", "TYPE", "FRESH", "ISSUE",
    "ELIGIBILITY", "RESERVATION", "SALE", "MAHARASHTRA", "PUNE", "MUMBAI",
    "ABBREVIATIONS", "DEFINITIONS", "GENERAL", "TERMS", "CONVENTIONS",
    "FINANCIAL", "INFORMATION", "MARKET", "DATA", "CURRENCY",
    "PRESENTATION", "SECTION", "RISK", "FACTORS", "CONTACT", "PERSON",
    "TELEPHONE", "EMAIL", "WEBSITE",
}

ALLCAPS_WORD = r"[A-Z][A-Z]+"  # a single all-caps word, 2+ letters
ALLCAPS_RUN_RE = re.compile(rf"(?:{ALLCAPS_WORD}(?:\s+{ALLCAPS_WORD}){{1,3}})")
NAME_CUE_RE = re.compile(
    r"(?:OUR PROMOTERS|PROMOTERS|DIRECTORS|MR\.|MS\.|MRS\.|DR\.)\s*[:\-]?\s*"
)


def _looks_like_name(run):
    words = run.split()
    if any(w in ALLCAPS_STOPWORDS for w in words):
        return False
    return True


def detect_allcaps_names(text):
    spans = []
    # Only bother scanning paragraphs that contain a meaningful run of
    # all-caps words in the first place.
    candidates = [(m.start(), m.end(), m.group()) for m in ALLCAPS_RUN_RE.finditer(text)]
    if not candidates:
        return spans

    name_like = [c for c in candidates if _looks_like_name(c[2])]
    if not name_like:
        return spans

    # Signal (a): 2+ name-like runs separated by comma/slash within a short
    # span of each other -> treat the whole run as a name list.
    if len(name_like) >= 2:
        for start, end, run in name_like:
            spans.append((start, end, "PERSON", run))
        return spans

    # Signal (b): a single name-like run immediately preceded by a
    # name-introducing cue.
    start, end, run = name_like[0]
    prefix = text[max(0, start - 30):start]
    if NAME_CUE_RE.search(prefix):
        spans.append((start, end, "PERSON", run))

    return spans


DETECTORS.extend([
    detect_emails,
    detect_phones,
    detect_ssn,
    detect_credit_card,
    detect_ip,
    detect_dob,
    detect_addresses,
    detect_allcaps_names,
])


# ---------------------------------------------------------------------------
# Merge logic
# ---------------------------------------------------------------------------

# Priority order for resolving overlapping spans (lower index = higher priority)
_PRIORITY = ["EMAIL", "PHONE", "SSN", "CREDIT_CARD", "IP_ADDRESS", "DOB",
             "ADDRESS", "PERSON", "COMPANY"]
# (ALL-CAPS names and NER PERSON both use label "PERSON" and are merged
# by the normal overlap-resolution logic below -- whichever is longer
# wins when they overlap on the same text.)


def _overlaps(a, b):
    return a[0] < b[1] and b[0] < a[1]


def detect_all(text):
    """Run every detector on `text` and return a non-overlapping list of
    spans sorted by start position. Overlaps are resolved by priority
    (see _PRIORITY); ties go to the longer span."""
    spans = []
    for fn in DETECTORS:
        spans.extend(fn(text))
    spans.extend(detect_ner(text))

    if not spans:
        return []

    def rank(span):
        label = span[2]
        length = span[1] - span[0]
        return (_PRIORITY.index(label) if label in _PRIORITY else 99, -length)

    spans.sort(key=rank)

    kept = []
    for span in spans:
        if not any(_overlaps(span, k) for k in kept):
            kept.append(span)

    kept.sort(key=lambda s: s[0])
    return kept
