# Evaluation Report — PII Redaction Tool

## Document under test

`Red_Herring_Prospectus__1_.docx` — a real ~900-page Indian IPO filing
(KSH International Limited), 692 non-empty unique paragraphs after
deduplicating merged table cells, spanning 76 tables.

## Methodology

Exhaustively hand-annotating ground truth across a 900-page document is
not practical for this exercise, so evaluation uses **random sampling
with manual annotation**, a standard approach when no labeled dataset
exists:

1. A **uniform random sample of 60 paragraphs** was drawn (seed=7) from
   all 692 processed paragraphs — not just paragraphs the tool flagged,
   so that recall (missed PII) can be measured honestly and not just
   precision.
2. Each of the 60 paragraphs was read manually and every true PII
   instance in the assignment's 9 required categories was recorded as
   ground truth (`ground_truth.py`), following the explicit policy
   choices documented in `README.md` (e.g. regulatory IDs like CIN/SEBI
   registration numbers are not counted as PII; company/registered-office
   addresses are counted as PII).
3. The tool's detectors were run on the same 60 paragraphs and scored
   against ground truth (`evaluate.py`) with fuzzy substring matching, so
   a partial/truncated detection (e.g. tool finds "Bank Limited" for
   ground truth "ICICI Bank Limited") still counts as a correct
   detection of that entity. A detection that finds the right text but
   the **wrong label** (e.g. a person's name tagged COMPANY) is scored as
   both a false negative for the true label and a false positive for the
   predicted label, since that's the practical effect on the document.
4. **SSN, credit card, IP address, and date of birth** do not occur in
   this document at all (confirmed by grepping the full extracted text
   before building any detectors — an Indian corporate filing uses
   PAN/CIN, not SSNs, and has no consumer financial or network-log data).
   These 4 detectors are instead validated with **synthetic unit tests**
   (`test_synthetic.py`), all passing (6/6, including EMAIL/PHONE as a
   sanity check on the same file).

Sample size note: 60 paragraphs out of 692 (~8.7%) is a modest sample and
the resulting metrics, especially per-label ones with small counts
(e.g. ADDRESS has only 2 ground-truth instances in the sample), should be
read as indicative rather than statistically precise — the value of this
evaluation is mainly in identifying _systematic_ failure modes (see
Findings), which show up clearly even at this sample size and recur
consistently across the sample.

## Results

| Label       | TP     | FP     | FN    | Precision | Recall   | F1       |
| ----------- | ------ | ------ | ----- | --------- | -------- | -------- |
| ADDRESS     | 1      | 0      | 1     | 1.00      | 0.50     | 0.67     |
| COMPANY     | 5      | 49     | 0     | 0.09      | 1.00     | 0.17     |
| EMAIL       | 6      | 0      | 0     | 1.00      | 1.00     | 1.00     |
| PERSON      | 2      | 5      | 5     | 0.29      | 0.29     | 0.29     |
| PHONE       | 3      | 0      | 0     | 1.00      | 1.00     | 1.00     |
| **Overall** | **17** | **54** | **6** | **0.24**  | **0.74** | **0.36** |

(SSN / CREDIT_CARD / IP_ADDRESS / DOB: not present in sample; see synthetic
tests, 6/6 passed, in `test_synthetic.py`.)

"Accuracy" in the usual sense (correct labels / total predictions,
including true negatives) isn't a meaningful number for a span-detection
task like this one, since "true negatives" would mean every possible
non-PII substring that wasn't flagged — an unbounded and not-useful
quantity. Precision/recall/F1 per label, above, is the standard framing
for this kind of task and is what's reported.

## Findings

**Regex-based detectors (EMAIL, PHONE) perform essentially perfectly** —
1.00 precision and recall on the sample. This is expected: these have
fixed, learnable shapes and the document's actual emails/phone numbers
are unambiguous once you require an `@domain.tld` shape or a `+country
code` prefix.

**COMPANY detection has a serious precision problem (0.09).** Of 54
COMPANY predictions in the sample, only 5 were real company names; the
rest were spaCy's general-purpose NER model mistagging capitalized
financial/legal defined-terms as organizations:

```
'Offer Related Terms', 'Group Companies', 'ICAI', 'Ind AS',
'the Stock Exchanges for the Offer', 'Promoter Selling Shareholders',
'Marine Insurance', 'the Net Proceeds', 'ASBA', 'CDP', ...
```

A stoplist (`NER_STOPLIST` in `pii_detectors.py`) removes the most common
recurring offenders found during initial sampling, and materially helped
(pre-stoplist, the full-document run had 1957 COMPANY hits; post-stoplist, 558) — but a stoplist only catches terms already seen; it doesn't fix the
underlying issue that `en_core_web_sm` isn't tuned for this
document genre. Recall for COMPANY, by contrast, was perfect in this
sample (all 5 real company names were found, sometimes with an imprecise
boundary that fuzzy-matching still credited).

**Manual spot-check outside the sample surfaced the same pattern.** A
table header "NAME OF THE BOOK RUNNING LEAD MANAGER" was redacted to
"NAME OF THE Silverline Corp" — a false positive from the same
generic-phrase over-triggering described above. In the same table,
"ICICI Securities Limited" was left un-redacted entirely — a false
negative. Both are consistent with the systematic COMPANY
precision/recall issues measured in the sample above, not one-off
glitches.

**PERSON detection has both low precision and low recall (0.29 / 0.29).**
Two concrete, illustrative failures found during evaluation:

1. **ALL-CAPS text defeats the model almost entirely.** The document's
   own cover page lists the promoters as `KUSHAL SUBBAYYA HEGDE, PUSHPA
KUSHAL HEGDE, RAJESH KUSHAL HEGDE, ...` — none of these are detected.
   This was confirmed by rendering the redacted output to PDF and
   visually inspecting the cover page (see attached
   `redacted_prospectus.pdf` rendering / `cover-001.jpg` in the working
   files): the promoter names are the single most prominent piece of PII
   on the entire document's front page, and the tool misses all of them.
2. **Short, sparse-context fragments are missed even in normal case.**
   `"Contact Person: Prakash Boricha"` (isolated, no surrounding
   sentence) produces zero entities from spaCy at all — confirmed
   directly: `_NLP("Contact Person: Prakash Boricha").ents == []`.
   Longer-context mentions of names elsewhere in the document are
   generally caught; short table-cell-style fragments are not.
3. **Slash-separated name lists break span boundaries.**
   `"Contact Person: Eric Bacha/ Sachin Gawade/ Pravin Teli/ Siddharth
Jadhav/ Tushar Gavankar"` returns only two garbled spans
   (`'Eric Bacha/'` and `'Jadhav/ Tushar Gavankar'`), missing 3 of the 5
   names and mangling the boundary of a 4th.

**ADDRESS detection is precise (1.00) when it fires, but the heuristic
(PIN code + nearby keyword or place name, sentence-bounded) has real
recall gaps.** An address fragment split across multiple short paragraphs
in a table cell, or missing a 6-digit PIN code in the same sentence, is
missed. A separate, specific bug was found (not part of the 60-paragraph
sample, found during output verification): the cover page's own
Registered Office address, in a vertically-merged table cell, was
**skipped by the document traversal entirely** — root-caused to how
`python-docx` represents merged cells (the merge's continuation shares
the same underlying XML element as an earlier, empty cell, which the
traversal's merge-dedup logic marks "visited" first). This is a distinct
failure mode from the detector logic itself — the text never even reached
the detector.

## Precision/recall trade-off actually observed

This document is a clean illustration of the classic trade-off: the
regex-only categories (EMAIL, PHONE) sit at the ideal top-right corner
(precision=1, recall=1) because they have unambiguous shapes. The
NER-only categories (PERSON, COMPANY) sit at opposite ends of the
trade-off for different reasons — COMPANY over-fires (high recall, very
low precision) while PERSON under-fires on this document's ALL-CAPS/
sparse-context style (both precision and recall suffer). If this were a
production system, the next highest-value investment would be either (a)
a NER model fine-tuned on financial/legal filings, or (b) a rule layer
specifically targeting this document type's ALL-CAPS section headers and
tables, since that's where the highest-stakes PII (promoter/director
names) concentrates.

## Reproducing this evaluation

```
python3 redact.py input.docx output.docx --audit-log audit_log.csv   # full run
python3 evaluate.py                                                   # sample metrics
python3 test_synthetic.py                                             # synthetic coverage for rare types
```
