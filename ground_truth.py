"""
ground_truth.py

Manually-reviewed ground truth PII annotations for the 60-paragraph random
evaluation sample (eval_sample.json), drawn from the Red Herring
Prospectus. Each paragraph's original text was read and every true PII
instance falling into the assignment's 9 required categories was recorded.

Policy decisions made while annotating (documented here so the evaluation
is reproducible and the reasoning is explicit, per the assignment's
request to "be explicit about your choice"):

  - Regulatory/registration identifiers (SEBI registration numbers, CIN)
    are NOT counted as PII -- they are business license numbers, not one
    of the 9 required categories, and are routinely public record for any
    India-incorporated company.
  - Company / registered-office addresses ARE counted as PII under
    "Physical/mailing addresses", even though they are business rather
    than personal addresses, since the assignment's category is broad and
    the redaction tool is designed to treat them the same way (documented
    also in README.md).
  - Generic role references ("our Promoters", "our Directors") without an
    accompanying named individual are NOT counted -- there is no specific
    identifiable person in the sentence.
  - Website URLs and generic financial figures/percentages are out of
    scope (not one of the 9 required categories).

Format: {para_idx: [(label, representative_text), ...]}
"""

GROUND_TRUTH = {
    519: [("PERSON", "Prakash Boricha")],
    544: [
        ("PHONE", "+91 22 30752929"),
        ("PHONE", "+91 22 30752928"),
        ("PHONE", "+91 22 30752914"),
    ],
    560: [
        ("PERSON", "Eric Bacha"),
        ("PERSON", "Sachin Gawade"),
        ("PERSON", "Pravin Teli"),
        ("PERSON", "Siddharth Jadhav"),
        ("PERSON", "Tushar Gavankar"),
    ],
    564: [("COMPANY", "ICICI Bank Limited")],
    570: [("COMPANY", "HDFC Bank Limited")],
    573: [
        ("EMAIL", "siddharth.jadhav@hdfcbank.com"),
        ("EMAIL", "sachin.gawade@hdfcbank.com"),
        ("EMAIL", "eric.bacha@hdfcbank.com"),
        ("EMAIL", "tushar.gavankar@hdfcbank.com"),
        ("EMAIL", "pravin.teli2@hdfcbank.com"),
    ],
    596: [("COMPANY", "Kirtane & Pandit")],
    599: [("ADDRESS", "Pune – 411 038")],
    633: [("EMAIL", "manisha.shukla@hdfcbank.com")],
    642: [("PERSON", "Ashish Mathew Pulloor")],
    645: [("COMPANY", "Bajaj Finance Limited")],
    654: [("COMPANY", "CARE Ratings Limited")],
    # Partial address (no PIN code in this fragment) -- included to test
    # recall on incomplete address mentions.
    381: [("ADDRESS", "Chakan, Pune, Maharashtra")],
}

# Every other paragraph in the sample (0-39 minus the ones above, etc.) is
# annotated as containing no PII in the 9 required categories.
