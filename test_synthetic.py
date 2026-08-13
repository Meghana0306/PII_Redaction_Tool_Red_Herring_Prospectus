"""
test_synthetic.py

The source document (an Indian corporate IPO filing) contains zero
instances of SSNs, credit card numbers, IP addresses, or dates of birth --
confirmed by grepping the full extracted text before building the
detectors (India uses PAN/Aadhaar rather than SSNs, and a prospectus has
no consumer financial or IP-logging data). Recall for these 4 categories
therefore cannot be measured against the real document. This file
validates that the detectors work correctly against synthetic examples
matching the assignment's stated categories, so the pipeline's coverage
of all 9 required PII types is still demonstrated and testable.

Run: python3 test_synthetic.py
"""

from pii_detectors import detect_all

CASES = [
    ("My SSN is 523-11-4877 for the loan application.", "SSN", "523-11-4877"),
    ("Card number: 4539148803436467 exp 09/27.", "CREDIT_CARD", "4539148803436467"),
    ("The server logged the request from 192.168.1.44 at midnight.", "IP_ADDRESS", "192.168.1.44"),
    ("Date of Birth: 14/03/1985", "DOB", "14/03/1985"),
    ("Contact John Smith at john.smith@example.com or +1 415 555 0199.", "EMAIL", "john.smith@example.com"),
    ("Contact John Smith at john.smith@example.com or +1 415 555 0199.", "PHONE", "+1 415 555 0199"),
]

passed = 0
for text, expected_label, expected_text in CASES:
    spans = detect_all(text)
    match = any(
        s.label == expected_label and expected_text.lower() in s.text.lower()
        for s in spans
    )
    status = "PASS" if match else "FAIL"
    if match:
        passed += 1
    print(f"[{status}] {expected_label:12s} expected '{expected_text}' in: {text}")
    print(f"       got: {[(s.label, s.text) for s in spans]}")

print(f"\n{passed}/{len(CASES)} synthetic cases passed.")
