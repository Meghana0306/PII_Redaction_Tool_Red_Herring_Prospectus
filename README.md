# PII Redaction Tool — README

## Approach

Hybrid regex + NER pipeline, applied paragraph-by-paragraph (including
paragraphs nested inside table cells) across the `.docx` document.

- **Structured PII** (email, phone, SSN, credit card, IP address, date of
  birth, physical addresses) is detected with **regex**, because these
  have a fixed, learnable shape. Credit card matches are additionally
  validated with a Luhn checksum to cut down on false positives from other
  long numeric IDs in the document (CINs, ISINs, etc.).
- **Free-form PII** (person names, company names) is detected with
  **spaCy's `en_core_web_sm`** NER model (`PERSON` and `ORG` entity
  types), because there is no fixed pattern for a name.
- **Consistency**: every unique original value maps to exactly one fake
  value for the whole document (e.g. every occurrence of "Rashi Patil"
  becomes the same fake name everywhere), using a persistent
  `(label, normalized_original) -> fake` dictionary built with `Faker`,
  seeded for reproducible output.
- **Redacted `.docx`**: paragraphs are rewritten in place with
  `python-docx`, preserving the document's structure (headings, tables,
  paragraph-level formatting). Runs within a redacted paragraph are
  collapsed into one — see trade-offs below.

## Files

| File | Purpose |
|---|---|
| `redact.py` | Entry point / CLI. Walks the document, applies detectors, writes output + audit log. |
| `pii_detectors.py` | All detection logic (regex + NER), pluggable registry. |
| `pii_faker.py` | Consistent fake-value generation. |
| `ground_truth.py` / `evaluate.py` / `eval_sample.json` | Evaluation harness (see `evaluation_report.md`). |

## Usage

```
python3 redact.py input.docx output.docx --audit-log audit.csv
```

## Extending to a new PII type

1. Add a `detect_x(text) -> list[PIISpan]` function to `pii_detectors.py`.
2. Register it in `ALL_DETECTORS`.
3. Add a branch for its label in `PIIFaker.fake_for()` in `pii_faker.py`
   describing how to fake a value of that type.

`redact.py` itself never needs to change — it just calls `detect_all()`.

## Explicit policy choices

The assignment allows either choice on ambiguous categories as long as
it's stated, so:

- **Regulatory/registration IDs** (SEBI registration numbers, Corporate
  Identity Numbers) are **not** treated as PII. They aren't one of the 9
  required categories, and are routine public-record identifiers for any
  India-incorporated company, unlike an SSN or credit card number.
- **Company/registered-office addresses are treated as PII** under
  "Physical/mailing addresses," even though they're business rather than
  personal addresses — the assignment's category is broad and doesn't
  exclude them. A narrower design could exempt corporate addresses and
  redact only individuals' addresses; this is a judgment call, stated here
  explicitly.
- **The document's own subject company name is redacted like any other
  company name.** Because "Company names" is an explicit required
  category, `KSH International Limited` gets redacted everywhere it
  appears, including the cover page — which, note, makes the output far
  less readable/coherent as a document, since it's the actual subject of
  the entire filing. A production tool built for this specific document
  type would probably want an allow-list to exempt the filer's own name
  and only redact third parties (directors, other companies mentioned).
  This tool does not do that, to stay literal to the assignment's stated
  category list — flagged here as a design trade-off worth revisiting
  depending on intended use.

## Trade-offs and known limitations (found during evaluation — see
`evaluation_report.md` for the numbers)

1. **spaCy's general-purpose NER has real precision and recall problems
   on this document type.** This is a dense financial/legal filing full
   of capitalized defined terms ("the Offer", "Promoter Group", "Trade
   Payable Days"), and the pretrained model frequently mistags these as
   ORG or PERSON. A stoplist (`NER_STOPLIST` in `pii_detectors.py`) was
   added for the most common recurring false positives found while
   sampling output, but this is a blunt fix, not a real solution — a
   domain-fine-tuned NER model would do meaningfully better.
2. **spaCy misses names in ALL-CAPS text almost entirely**, and this
   document's cover page and headers are heavily capitalized (e.g. none
   of the promoter names "KUSHAL SUBBAYYA HEGDE, PUSHPA KUSHAL HEGDE, ..."
   on the cover page are detected). This is a significant recall gap for
   exactly the kind of prominent, high-visibility PII a redaction tool
   should catch first.
3. **Slash-separated name lists break NER span boundaries** — e.g.
   "Contact Person: Eric Bacha/ Sachin Gawade/ Pravin Teli/ Siddharth
   Jadhav/ Tushar Gavankar" is only partially and messily detected (see
   evaluation report for the exact spans returned).
4. **Address detection is regex/keyword-heuristic based** (PIN code +
   nearby address keyword or place name, sentence-bounded) and will miss
   addresses that lack a 6-digit Indian PIN code in the same sentence, or
   that are split across multiple short paragraphs (e.g. one word per
   line, as happens in some of this document's cover-page table cells).
5. **Merged table cells** in complex layouts (this document's cover page
   uses a nested/merged grid) can, in one specific case found during
   evaluation, cause a paragraph to be skipped by the traversal
   entirely — root-caused to how `python-docx` represents
   vertically-merged cells (the same underlying XML element is shared by
   the merge's continuation cells, and an earlier, empty continuation can
   get marked "visited" before the content-bearing instance is reached).
   Confirmed on the Registered Office address in the cover-page table.
6. **Paragraph-level rewriting collapses multi-run formatting.** If a
   paragraph originally had e.g. one bold word among plain text, the
   redacted paragraph keeps the paragraph's own style (heading level,
   alignment) but not that internal run-level formatting, since the whole
   paragraph's text is rewritten into a single run. Table/heading/list
   structure is preserved; word-level styling within a redacted paragraph
   is not.
7. **No SSN / credit card / IP address / date-of-birth instances exist in
   this particular source document** (it's an Indian corporate filing,
   which uses PAN/CIN rather than SSNs, and has no consumer financial
   data). Those four detectors could not be evaluated for recall against
   this document and were instead unit-tested against synthetic examples
   (see `evaluation_report.md`).
