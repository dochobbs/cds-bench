# tests/release/test_submit.py
from scripts.release.submit import load_hidden, score_submission

def test_load_hidden_returns_116():
  hidden = load_hidden()
  assert len(hidden) == 116  # 48+24+24+12+8
  assert all("lane" in h and "id" in h and "case" in h for h in hidden)

def test_score_submission_blinds_and_aggregates():
  hidden = load_hidden()
  transcripts = {h["id"]: "some answer" for h in hidden}
  # fake scorer: returns 1.0 for everything
  fake = lambda case, answer, lane: 1.0
  card = score_submission(transcripts, scorer=fake, system_alias="SubmittedModel")
  assert card["system"] == "SubmittedModel"
  assert set(card["per_lane"]) == {"golden", "freshness", "hallucination", "halluhard", "calc"}
  assert card["per_lane"]["calc"]["n"] == 8  # hidden calc count
  assert card["per_lane"]["golden"]["mean"] == 1.0

def test_scorecard_contains_no_vendor_identities():
  hidden = load_hidden()
  transcripts = {h["id"]: "x" for h in hidden}
  card = score_submission(transcripts, scorer=lambda c, a, l: 0.5, system_alias="X")
  blob = str(card).lower()
  for forbidden in ("openevidence", "amboss", "lisa", "glass", "elation"):
    assert forbidden not in blob
  assert all(isinstance(v["mean"], (int, float, type(None))) for v in card["per_lane"].values())
  assert all(isinstance(v["n"], int) for v in card["per_lane"].values())

def test_none_score_treated_as_missing():
  hidden = load_hidden()
  transcripts = {h["id"]: "x" for h in hidden}
  scorer = lambda c, a, l: (None if l == "calc" else 1.0)
  card = score_submission(transcripts, scorer=scorer, system_alias="X")
  assert card["missing_count"] == 8           # all 8 hidden calc cases scored None -> missing
  assert card["per_lane"]["calc"]["mean"] is None
  assert card["per_lane"]["golden"]["mean"] == 1.0

def test_scorer_exception_is_tagged_with_case_id():
  import pytest
  hidden = load_hidden()
  transcripts = {h["id"]: "x" for h in hidden}
  def boom(c, a, l): raise ValueError("judge down")
  with pytest.raises(RuntimeError):
    score_submission(transcripts, scorer=boom, system_alias="X")
