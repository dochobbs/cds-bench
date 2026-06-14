# scripts/release/assets.py
"""Static text for the public cds-bench repo (LICENSE, README, CANARY, SUBMISSION)."""
from __future__ import annotations
from scripts.release.canary import CANARY, DO_NOT_TRAIN_NOTICE

LICENSE = """cds-bench license

DATA (everything under public/ and worked_examples/, and the rubrics/):
  Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International
  (CC BY-NC-ND 4.0). https://creativecommons.org/licenses/by-nc-nd/4.0/
  You may share with attribution for non-commercial purposes without modification.
  You may NOT use this data, or derivatives, as model training or fine-tuning data.

CODE (everything under scoring/):
  MIT License. Permissive reuse with attribution.

The held-out test set is not distributed under any license; it is not included here.
"""

README = f"""# cds-bench — internal family-medicine CDS benchmark (public sample)

This repository publishes a **representative 29-case sample** and the full scoring
methodology of a 145-case clinical-decision-support benchmark. The remaining
**116 cases are held out** and never distributed, so models cannot train on them.

- `public/` — 29 cases across 5 lanes (golden, freshness, hallucination, halluhard, calc)
- `worked_examples/` — 5 cases shown end-to-end (query → rubric → gold → transcript → score)
- `rubrics/` — the judge rubrics used to score each lane
- `scoring/` — the scoring harness (MIT)
- `HIDDEN_MANIFEST.sha256` / `.meta.json` — SHA-256 + Merkle root of the 116 hidden cases
- `SUBMISSION.md` — how to evaluate against the hidden set (eval-as-a-service)

## ⚠ Data use restriction

{DO_NOT_TRAIN_NOTICE}

See LICENSE. Canary: `{CANARY}`
"""

CANARY_FILE = f"""{CANARY}

{DO_NOT_TRAIN_NOTICE}
"""

SUBMISSION = """# SUBMISSION: Evaluating against the hidden cds-bench test set

The 116 hidden cases are never published. To get a hidden-set score:

1. Provide a model endpoint (or a set of pre-generated transcripts keyed by case id).
2. The maintainer runs them through the hidden harness with the published rubrics.
3. You receive a blinded scorecard: your system's per-lane scores alongside
   anonymized comparator rows (Vendor A / Vendor B …).

The hidden cases, their gold answers, and per-vendor identities are not shared.
The published `HIDDEN_MANIFEST.sha256` lets you verify, after the fact, that the
hidden set was fixed at release time.
"""
