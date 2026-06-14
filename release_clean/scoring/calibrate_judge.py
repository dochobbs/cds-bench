# calibrate_judge.py
"""Reference implementation of the cds-bench judge-calibration protocol.

Calibrate a candidate LLM judge against a frozen reference judge before trusting it:
  - median-of-3 sampling at temperature ~0.3 (anti-anchoring)
  - per-dimension MAE + Pearson r vs the reference scores
A candidate judge is only usable if its Pearson r against the reference is high enough
(it tracks the reference's rank order) AND it tracks it in absolute terms (low MAE).
"Cheap" stops counting below an agreement floor on r.

Self-contained reference; wire `judge_fn` to your own model call.
"""
from __future__ import annotations
from statistics import median, mean
from typing import Callable

JudgeFn = Callable[[str], float]  # judge_fn(prompt) -> score for one criterion

def median_of_3(judge_fn: JudgeFn, prompt: str) -> float:
  """Sample the judge 3x (caller sets temperature ~0.3) and take the median — robust to one-off swings."""
  return median([judge_fn(prompt) for _ in range(3)])

def pearson_r(xs: list[float], ys: list[float]) -> float:
  n = len(xs)
  if n < 2:
    return 0.0
  mx, my = mean(xs), mean(ys)
  cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
  vx = sum((x - mx) ** 2 for x in xs) ** 0.5
  vy = sum((y - my) ** 2 for y in ys) ** 0.5
  return cov / (vx * vy) if vx and vy else 0.0

def calibrate(candidate_scores: list[float], reference_scores: list[float]) -> dict:
  """Compare a candidate judge's scores against the frozen reference judge's scores."""
  assert len(candidate_scores) == len(reference_scores)
  mae = mean(abs(c - r) for c, r in zip(candidate_scores, reference_scores))
  return {"mae": round(mae, 2), "pearson_r": round(pearson_r(candidate_scores, reference_scores), 3),
          "n": len(candidate_scores)}
