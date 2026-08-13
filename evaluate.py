"""
evaluate.py

Scores the redaction tool's detections against the manually-annotated
ground truth (ground_truth.py) for the 60-paragraph random sample
(eval_sample.json), and prints a precision/recall/F1 report per PII
label and overall.

Matching rule: a predicted span counts as a match for a ground-truth item
if one is a substring of the other (case-insensitive), which credits
partial/truncated detections (e.g. tool finds "Bank Limited" for ground
truth "ICICI Bank Limited") as a correct detection of that entity while
still counting a *wrong-label* match (e.g. a person's name predicted as
COMPANY) as both a false negative for the true label and a false positive
for the predicted label -- since that is what actually happens to the
document: the entity is redacted, but analytics grouped by category would
be wrong, which matters for an audit trail.
"""

import json
from collections import defaultdict

from pii_detectors import detect_all
from ground_truth import GROUND_TRUTH

sample = dict(json.load(open("eval_sample.json")))


def norm(s):
    return s.strip().lower()


def fuzzy_match(a, b):
    a, b = norm(a), norm(b)
    return a in b or b in a


tp = defaultdict(int)
fp = defaultdict(int)
fn = defaultdict(int)

fp_examples = defaultdict(list)
fn_examples = defaultdict(list)

for idx_str, text in sample.items():
    idx = int(idx_str)
    gt_items = GROUND_TRUTH.get(idx, [])
    predicted = [(s.label, s.text) for s in detect_all(text)]

    gt_matched = [False] * len(gt_items)
    pred_matched = [False] * len(predicted)

    # First pass: exact-label matches
    for pi, (plabel, ptext) in enumerate(predicted):
        for gi, (glabel, gtext) in enumerate(gt_items):
            if gt_matched[gi] or pred_matched[pi]:
                continue
            if plabel == glabel and fuzzy_match(ptext, gtext):
                tp[plabel] += 1
                gt_matched[gi] = True
                pred_matched[pi] = True

    # Second pass: wrong-label matches (entity found, mislabeled)
    for pi, (plabel, ptext) in enumerate(predicted):
        if pred_matched[pi]:
            continue
        for gi, (glabel, gtext) in enumerate(gt_items):
            if gt_matched[gi]:
                continue
            if fuzzy_match(ptext, gtext):
                # entity was found but under the wrong label
                fn[glabel] += 1
                fp[plabel] += 1
                fn_examples[glabel].append(f"para{idx}: '{gtext}' (missed as {glabel}, "
                                            f"tool said {plabel}='{ptext}')")
                fp_examples[plabel].append(f"para{idx}: '{ptext}' (should be {glabel} "
                                            f"'{gtext}', tool said {plabel})")
                gt_matched[gi] = True
                pred_matched[pi] = True

    # Remaining unmatched predictions -> false positives
    for pi, (plabel, ptext) in enumerate(predicted):
        if not pred_matched[pi]:
            fp[plabel] += 1
            fp_examples[plabel].append(f"para{idx}: '{ptext}'")

    # Remaining unmatched ground truth -> false negatives
    for gi, (glabel, gtext) in enumerate(gt_items):
        if not gt_matched[gi]:
            fn[glabel] += 1
            fn_examples[glabel].append(f"para{idx}: '{gtext}'")

labels = sorted(set(list(tp) + list(fp) + list(fn)))

print(f"{'LABEL':12s} {'TP':>4s} {'FP':>4s} {'FN':>4s} {'Precision':>10s} {'Recall':>8s} {'F1':>6s}")
tot_tp = tot_fp = tot_fn = 0
for label in labels:
    t, f, n = tp[label], fp[label], fn[label]
    tot_tp += t; tot_fp += f; tot_fn += n
    prec = t / (t + f) if (t + f) else float("nan")
    rec = t / (t + n) if (t + n) else float("nan")
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) and prec == prec and rec == rec and (prec+rec)>0 else float("nan")
    print(f"{label:12s} {t:4d} {f:4d} {n:4d} {prec:10.2f} {rec:8.2f} {f1:6.2f}")

prec = tot_tp / (tot_tp + tot_fp) if (tot_tp + tot_fp) else float("nan")
rec = tot_tp / (tot_tp + tot_fn) if (tot_tp + tot_fn) else float("nan")
f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else float("nan")
print(f"{'OVERALL':12s} {tot_tp:4d} {tot_fp:4d} {tot_fn:4d} {prec:10.2f} {rec:8.2f} {f1:6.2f}")

print("\n--- False positive examples (up to 5 per label) ---")
for label, examples in fp_examples.items():
    print(f"{label}:")
    for e in examples[:5]:
        print("  ", e)

print("\n--- False negative examples ---")
for label, examples in fn_examples.items():
    print(f"{label}:")
    for e in examples[:5]:
        print("  ", e)
