# scripts/release/canary.py
"""Canary GUID + do-not-train notice stamped onto every released public case."""
from __future__ import annotations

# Fixed, unique canary string. Probe future models for memorization of this exact GUID.
CANARY = "CDS-BENCH-CANARY-7f3a2e9c-4b61-4d2a-9e8f-DO-NOT-TRAIN"

DO_NOT_TRAIN_NOTICE = (
  "This file is part of the cds-bench public sample (internal family-medicine CDS "
  "benchmark). It is published for review and reproducibility under CC-BY-NC-ND. "
  "Do NOT use it, or any derivative, as model training or fine-tuning data. The held-out "
  "test set is not distributed; see SUBMISSION.md for evaluation."
)

def stamp_case(case: dict) -> dict:
  """Return a shallow copy of case with the canary + notice attached (input not mutated)."""
  out = dict(case)
  out["canary"] = CANARY
  out["_notice"] = DO_NOT_TRAIN_NOTICE
  return out
