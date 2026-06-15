"""Shared helpers for cds-bench lane scorers.

Provides:
  - make_client()     — returns anthropic.Anthropic()
  - load_rubric()     — reads a rubric file, substitutes {current_date}
  - extract_json()    — strips markdown fences, extracts first {...} block
  - GOLDEN_JUDGE_MODEL — model used by the golden scorer (claude-sonnet-4-20250514)
  - TRAP_JUDGE_MODEL   — model used by the trap lanes (claude-sonnet-4-6)

Requires ANTHROPIC_API_KEY in the environment. No vendor-specific logic here.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from anthropic import Anthropic

# ---------------------------------------------------------------------------
# Model constants — keep these accurate; they drive reproducible scoring.
# ---------------------------------------------------------------------------

# Golden lane: scored by Claude Sonnet 4 (the judge used in the published run).
GOLDEN_JUDGE_MODEL = "claude-sonnet-4-20250514"

# Currency, Hallucination, and HalluHard lanes: scored by Claude Sonnet 4.6
# (the model used in the internal evaluation program; do NOT unify with golden).
TRAP_JUDGE_MODEL = "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------

def make_client() -> Anthropic:
  """Return a configured Anthropic client (reads ANTHROPIC_API_KEY from env)."""
  return Anthropic()


# ---------------------------------------------------------------------------
# Rubric loader
# ---------------------------------------------------------------------------

def load_rubric(path: str, fallback: str | None = None) -> str:
  """Load a rubric file and substitute {current_date} with today's ISO date.

  Tries `path` first, then `fallback` if provided. This mirrors judge.py's
  _load_rubric robustness: when running from inside dist/public/ (a clean
  clone), `release_clean/rubrics/<lane>.txt` is absent, but `rubrics/<lane>.txt`
  lives at the repo root — pass that as fallback.

  Raises FileNotFoundError naming both candidates if neither exists.
  """
  today = date.today().isoformat()
  candidates = [path]
  if fallback is not None:
    candidates.append(fallback)

  for p in candidates:
    try:
      text = Path(p).read_text(encoding="utf-8").strip()
      return text.replace("{current_date}", today)
    except FileNotFoundError:
      continue

  tried = repr(path) + (f" and {fallback!r}" if fallback else "")
  raise FileNotFoundError(f"rubric not found; tried: {tried}")


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------

def extract_json(text: str) -> dict:
  """Strip markdown fences and extract the first {...} JSON block.

  Raises json.JSONDecodeError if no valid JSON object can be found.
  """
  t = text.strip()
  if t.startswith("```"):
    t = t.split("\n", 1)[1].rsplit("```", 1)[0].strip()
  start = t.find("{")
  end = t.rfind("}") + 1
  if start >= 0 and end > start:
    return json.loads(t[start:end])
  return json.loads(t)
