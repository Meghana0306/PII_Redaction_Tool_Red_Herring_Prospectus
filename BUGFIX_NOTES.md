# Bugfix notes (post-submission)

After the first version was submitted, a visual side-by-side check of the
cover page (original vs. redacted) showed the entire top table — including
the promoters' names, in ALL CAPS — completely unredacted. Investigating
that led to two real bugs, both now fixed in this version.

## Bug 1: paragraph-deduplication used a Python memory address, which can
be silently recycled

`redact.py` walks every paragraph in the document, including inside table
cells, and needs to make sure it doesn't process the same paragraph twice
when cells are merged. The original code used `id(paragraph._p)` — the
Python memory address of the paragraph's underlying XML element — as the
de-duplication key.

This is unsafe: `python-docx`/`lxml` create a **new, short-lived Python
wrapper object** every time you access `cell.paragraphs`. Once a previous
wrapper is garbage collected, CPython can hand that same memory address to
a completely unrelated object. In practice, this meant paragraphs that
had nothing to do with each other — e.g. a Registered Office address in
one cell, and an unrelated email/phone number cell two columns over — were
landing on the *same* `id()` purely by coincidence, and the second one was
being silently skipped as "already processed."

This wasn't a cosmetic issue confined to the cover page — re-running with
the fix increased the number of paragraphs actually scanned from **1,035
to 4,486**, meaning roughly three-quarters of the document's paragraphs
had never actually been checked for PII at all in the original run.

**Fix:** de-duplicate using the paragraph's absolute XML tree path
(`element.getroottree().getpath(element)`), a stable string identifier
that doesn't depend on object lifetime. Genuinely merged cells still
correctly share the same path (verified directly against this document's
cover-page table), so the original goal — not double-processing a true
merge — still works; it just no longer *falsely* merges unrelated cells.

## Bug 2: the NER model never recognizes ALL-CAPS names

Confirmed directly: `spacy`'s `en_core_web_sm` model returns **zero**
entities for a sentence containing `"KUSHAL SUBBAYYA HEGDE"` even with
full surrounding context. This document's cover page lists its promoters
entirely in ALL CAPS — exactly the highest-visibility PII on the whole
filing — and none of it was being caught, independent of Bug 1.

**Fix:** added `detect_allcaps_names()`, a separate heuristic detector
(not a NER model) that looks for runs of 2–4 ALL-CAPS words. To avoid
flagging section headers like `DEFINITIONS AND ABBREVIATIONS`, a run is
only treated as a name if it's either (a) part of a comma/slash-separated
list of 2+ such runs (the shape of a promoters/directors line), or (b)
immediately preceded by a name cue like `MR.`, `PROMOTERS:`, etc. A
stopword list filters out common ALL-CAPS boilerplate.

A related, smaller gap was also fixed: some addresses in this document
are split across **two separate paragraphs within the same table cell**
(street address + PIN code in one paragraph, state name in the next), and
the original address detector required both in the same paragraph. Added
a second pattern that also matches a short paragraph ending in a 6-digit
PIN code near an address-type keyword (Village/Road/Nagar/etc.), even
without the state name in that same paragraph.

## Numbers, before and after

| | Before fix | After fix |
|---|---|---|
| Unique paragraphs actually processed | 1,035 | 4,486 |
| Total redactions | 549 | 1,468 |
| — COMPANY | 365 | 999 |
| — PERSON | 116 | 355 |
| — EMAIL | 40 | 52 |
| — PHONE | 26 | 31 |
| — ADDRESS | 2 | 31 |

The cover page — the single most PII-dense page in the document — is now
fully redacted; this was visually re-verified by rendering the new output
to PDF and inspecting it directly (see `cover_page_after_fix.jpg`).

These fixes are already included in `redact.py` / `pii_detectors.py` in
this package; `redacted_prospectus.docx` and `audit_log.csv` reflect the
fixed run. `README.md` and `evaluation_report.md` describe the tool's
remaining known limitations (mainly: NER over-flags generic capitalized
legal/financial terms as company names — see COMPANY precision numbers).
