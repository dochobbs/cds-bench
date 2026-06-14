# tests/release/test_release_clean.py
import json, pytest
from scripts.release.build_public import _assert_clean, build_public

def test_assert_clean_passes_on_clean_text():
  _assert_clean("a generic gold-standard reference judge", "x")  # no raise

def test_assert_clean_raises_on_vendor_name():
  with pytest.raises(ValueError):
    _assert_clean("scored against AMBOSS gold", "x")

def test_assert_clean_raises_on_private_path():
  with pytest.raises(ValueError):
    _assert_clean('ROOT = "/Users/dochobbs/x"', "x")

def test_assert_clean_allows_words_that_contain_vendor_substrings():
  # word-boundary: 'elation' in 'correlation', 'wren' in 'wrench' must NOT trip
  _assert_clean("pearson correlation coefficient; tighten the wrench", "x")  # no raise

def test_worked_example_vendor_system_rejected(tmp_path):
  wd = tmp_path / "worked"; wd.mkdir()
  (wd / "F19.json").write_text(json.dumps({"id": "F19", "system": "OpenEvidence", "transcript": "x"}))
  out = tmp_path / "cds-bench"
  with pytest.raises(ValueError):
    build_public(str(out), seed=20260614, generated="2026-06-14", worked_dir=str(wd))

def test_worked_example_blinded_system_accepted(tmp_path):
  wd = tmp_path / "worked"; wd.mkdir()
  (wd / "F19.json").write_text(json.dumps({"id": "F19", "system": "Vendor A", "transcript": "x"}))
  out = tmp_path / "cds-bench"
  build_public(str(out), seed=20260614, generated="2026-06-14", worked_dir=str(wd))
  assert (out / "worked_examples" / "F19.json").exists()
