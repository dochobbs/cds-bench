# tests/release/test_assets.py
from scripts.release.assets import LICENSE, README, SUBMISSION

def test_license_is_cc_by_nc_nd_plus_mit_code():
  assert "CC BY-NC-ND" in LICENSE
  assert "MIT" in LICENSE  # code carve-out

def test_readme_states_data_use_request_and_counts():
  # Must have data use request language
  assert "training data" in README.lower() or "don't use" in README.lower()
  # Must use correct 27/108 counts
  assert "27" in README
  assert "108" in README
  # Must not use old 29/116 counts
  assert "29-case" not in README and '" 29 "' not in README

def test_readme_has_private_source_note():
  assert "private source" in README.lower() or "all 135 cases" in README

def test_no_canary_in_assets():
  """No CANARY_FILE or canary GUID in any asset string."""
  for name, text in [("LICENSE", LICENSE), ("README", README), ("SUBMISSION", SUBMISSION)]:
    assert "CDS-BENCH-CANARY" not in text, f"{name} still contains canary GUID"
    assert "DO-NOT-TRAIN" not in text, f"{name} still contains DO-NOT-TRAIN"

def test_submission_describes_eval_as_a_service():
  assert "blinded scorecard" in SUBMISSION
  assert "maintainer" in SUBMISSION
  assert "hidden" in SUBMISSION.lower()
  assert "108" in SUBMISSION
