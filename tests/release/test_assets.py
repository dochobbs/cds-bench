# tests/release/test_assets.py
from scripts.release.assets import LICENSE, README, CANARY_FILE, SUBMISSION
from scripts.release.canary import CANARY

def test_license_is_cc_by_nc_nd_plus_mit_code():
  assert "CC BY-NC-ND" in LICENSE
  assert "MIT" in LICENSE  # code carve-out

def test_readme_states_no_train_and_split():
  assert "DO NOT" in README.upper()
  assert "29" in README and "116" in README

def test_canary_file_contains_the_guid():
  assert CANARY in CANARY_FILE

def test_readme_embeds_canary():
  assert CANARY in README

def test_submission_describes_eval_as_a_service():
  assert "blinded scorecard" in SUBMISSION
  assert "maintainer" in SUBMISSION
  assert "hidden" in SUBMISSION.lower()
