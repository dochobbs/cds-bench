# tests/release/test_lane_scorers.py
"""Offline tests for the four lane scorers.

No API calls are made. Tests verify:
  - All 4 scorer modules import cleanly.
  - base.py model constants are correct.
  - Each new scorer loads its rubric without error; rubric is non-empty.
  - freshness rubric contains no "12-24 month" recency-window language.
  - All 4 scorer filenames are in SCORING_SRCS.
"""
from __future__ import annotations

import importlib

import pytest


# ---------------------------------------------------------------------------
# 1. All 4 scorer modules import cleanly
# ---------------------------------------------------------------------------

def test_base_importable():
  mod = importlib.import_module("release_clean.scoring.base")
  assert mod is not None


def test_score_freshness_importable():
  mod = importlib.import_module("release_clean.scoring.score_freshness")
  assert mod is not None


def test_score_hallucination_importable():
  mod = importlib.import_module("release_clean.scoring.score_hallucination")
  assert mod is not None


def test_score_halluhard_importable():
  mod = importlib.import_module("release_clean.scoring.score_halluhard")
  assert mod is not None


# ---------------------------------------------------------------------------
# 2. Model constants
# ---------------------------------------------------------------------------

def test_default_judge_model_constant():
  """The unified default judge is claude-sonnet-4-6 across all four lanes."""
  from release_clean.scoring.base import DEFAULT_JUDGE_MODEL
  assert DEFAULT_JUDGE_MODEL == "claude-sonnet-4-6"


def test_golden_judge_model_is_unified():
  """GOLDEN_JUDGE_MODEL is now an alias of DEFAULT_JUDGE_MODEL (= claude-sonnet-4-6).
  Golden originally used claude-sonnet-4-20250514 (Sonnet 4) and moved to 4.6."""
  from release_clean.scoring.base import GOLDEN_JUDGE_MODEL, DEFAULT_JUDGE_MODEL
  assert GOLDEN_JUDGE_MODEL == DEFAULT_JUDGE_MODEL
  assert GOLDEN_JUDGE_MODEL == "claude-sonnet-4-6"


def test_trap_judge_model_is_unified():
  """TRAP_JUDGE_MODEL is an alias of DEFAULT_JUDGE_MODEL (= claude-sonnet-4-6)."""
  from release_clean.scoring.base import TRAP_JUDGE_MODEL, DEFAULT_JUDGE_MODEL
  assert TRAP_JUDGE_MODEL == DEFAULT_JUDGE_MODEL
  assert TRAP_JUDGE_MODEL == "claude-sonnet-4-6"


def test_no_scorer_defaults_to_old_sonnet4():
  """No scorer should default to the old claude-sonnet-4-20250514 model."""
  from release_clean.scoring.base import GOLDEN_JUDGE_MODEL, TRAP_JUDGE_MODEL, DEFAULT_JUDGE_MODEL
  for const in (DEFAULT_JUDGE_MODEL, GOLDEN_JUDGE_MODEL, TRAP_JUDGE_MODEL):
    assert const != "claude-sonnet-4-20250514", (
      f"A model constant still points to the old Sonnet 4 judge: {const!r}"
    )


# ---------------------------------------------------------------------------
# 3. Rubric loading: non-empty, no forbidden language
# ---------------------------------------------------------------------------

def test_freshness_rubric_non_empty():
  from release_clean.scoring.base import load_rubric
  text = load_rubric(
    "release_clean/rubrics/freshness.txt",
    fallback="rubrics/freshness.txt",
  )
  assert len(text.strip()) > 50


def test_freshness_rubric_no_recency_window_language():
  """The freshness rubric must NOT contain '12-24 month' recency-window language
  (it was deliberately reframed to test guideline *currency*, any era)."""
  from release_clean.scoring.base import load_rubric
  text = load_rubric(
    "release_clean/rubrics/freshness.txt",
    fallback="rubrics/freshness.txt",
  )
  assert "12-24 month" not in text.lower()
  assert "12 to 24 month" not in text.lower()


def test_hallucination_rubric_non_empty():
  from release_clean.scoring.base import load_rubric
  text = load_rubric(
    "release_clean/rubrics/hallucination.txt",
    fallback="rubrics/hallucination.txt",
  )
  assert len(text.strip()) > 50


def test_halluhard_rubric_non_empty():
  from release_clean.scoring.base import load_rubric
  text = load_rubric(
    "release_clean/rubrics/halluhard.txt",
    fallback="rubrics/halluhard.txt",
  )
  assert len(text.strip()) > 50


# ---------------------------------------------------------------------------
# 4. All 4 scorer filenames are in SCORING_SRCS
# ---------------------------------------------------------------------------

def test_all_scorer_filenames_in_scoring_srcs():
  from scripts.release.build_public import SCORING_SRCS
  names = {p.split("/")[-1] for p in SCORING_SRCS}
  for expected in ("judge.py", "base.py", "score_freshness.py",
                   "score_hallucination.py", "score_halluhard.py"):
    assert expected in names, f"{expected} missing from SCORING_SRCS"


# ---------------------------------------------------------------------------
# 5. Public scorer functions are importable and have expected signatures
# ---------------------------------------------------------------------------

def test_score_currency_callable():
  from release_clean.scoring.score_freshness import score_currency
  import inspect
  sig = inspect.signature(score_currency)
  params = set(sig.parameters.keys())
  assert "query" in params
  assert "old_answer" in params
  assert "new_answer" in params
  assert "response" in params


def test_score_hallucination_callable():
  from release_clean.scoring.score_hallucination import score_hallucination
  import inspect
  sig = inspect.signature(score_hallucination)
  params = set(sig.parameters.keys())
  assert "query" in params
  assert "trap" in params
  assert "expected" in params
  assert "response" in params


def test_score_halluhard_callable():
  from release_clean.scoring.score_halluhard import score_halluhard
  import inspect
  sig = inspect.signature(score_halluhard)
  params = set(sig.parameters.keys())
  assert "case" in params
  assert "response" in params
  assert "num_runs" in params
