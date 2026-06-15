# SUBMISSION: Evaluating against the hidden cds-bench test set

The 108 hidden cases are never published. To get a hidden-set score:

1. Provide a model endpoint (or a set of pre-generated transcripts keyed by case id).
2. The maintainer runs them through the hidden harness with the published rubrics.
3. You receive a blinded scorecard: your system's per-lane scores alongside
   anonymized comparator rows (Vendor A / Vendor B ...).

The hidden cases, their gold answers, and per-vendor identities are not shared.
The published `HIDDEN_MANIFEST.sha256` lets you verify, after the fact, that the
hidden set was fixed at release time.

## On verifiability

Comparator tools are evaluated under NDA. Their identities and the A/B/C mapping
cannot be disclosed, and the comparator rows — like your hidden-set score — are
**maintainer-attested**: the published `HIDDEN_MANIFEST` proves the question set was
fixed at release time, but it does not, and cannot, independently verify the scores.
For an auditable result, run the 12 public **Golden** cases yourself with the shipped golden scorer (`release_clean/scoring/judge.py`). The Currency, Hallucination, and HalluHard lanes ship their rubric *criteria* under `release_clean/rubrics/` but not a runnable harness in this sample — their scoring is documented, not yet executable from this repo alone.

The per-case hashes in `HIDDEN_MANIFEST.sha256` are salted with a per-release secret
held by the maintainer. The salt is revealed when results are scored and published, at
which point anyone can verify `sha256(salt) == salt_commitment` (published in
`HIDDEN_MANIFEST.meta.json`) and recompute the per-case hashes to confirm the
held-out set was fixed at release time. This prevents guess-and-confirm reconstruction
of held-out answers before scoring.
