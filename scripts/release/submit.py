# scripts/release/submit.py
"""Eval-as-a-service: score a submitter's transcripts against the hidden set, return a blinded card.

The scorer is injected: scorer(case: dict, answer: str, lane: str) -> float.
Hidden cases, gold answers, and vendor identities never appear in the returned scorecard.
"""
from __future__ import annotations
import json
from pathlib import Path
from statistics import mean
from typing import Callable
from scripts.release.lanes import LANES, BENCH_DIR

Scorer = Callable[[dict, str, str], float]

def load_hidden(bench_dir: str = BENCH_DIR) -> list[dict]:
  """Load the 116 hidden cases as [{lane, id, case}]. INTERNAL — the raw `case` includes
  gold answers; never return this to submitters, only feed it to a server-side scorer."""
  out = []
  for lane in LANES.values():
    cases = json.load(open(Path(bench_dir) / lane.filename))
    for c in cases:
      if c.get("split") == "hidden":
        out.append({"lane": lane.name, "id": c[lane.id_field], "case": c})
  return out

def score_submission(transcripts: dict[str, str], scorer: Scorer,
                     system_alias: str, bench_dir: str = BENCH_DIR) -> dict:
  hidden = load_hidden(bench_dir)
  by_lane: dict[str, list[float]] = {l: [] for l in LANES}
  missing = []
  for h in hidden:
    ans = transcripts.get(h["id"])
    if ans is None:
      missing.append(h["id"])
      continue
    try:
      score = scorer(h["case"], ans, h["lane"])
    except Exception as e:
      raise RuntimeError(f"scorer failed on {h['lane']}/{h['id']}") from e
    if score is None:
      missing.append(h["id"])
      continue
    by_lane[h["lane"]].append(score)
  per_lane = {l: {"n": len(v), "mean": (mean(v) if v else None)} for l, v in by_lane.items()}
  return {
    "system": system_alias,                  # caller-chosen alias only
    "per_lane": per_lane,
    "missing_count": len(missing),
    "overall_mean": (mean([s for v in by_lane.values() for s in v])
                     if any(by_lane.values()) else None),
  }
