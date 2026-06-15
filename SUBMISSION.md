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
For a fully auditable result, run the 27 public cases yourself with the shipped
rubrics and judge (`release_clean/`).
