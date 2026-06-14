# tests/release/test_release_clean.py
import json, pytest
from scripts.release.build_public import _assert_clean, _load_vendor_tokens, build_public

_VENDOR_TOKENS = _load_vendor_tokens()

def test_assert_clean_passes_on_clean_text():
  _assert_clean("a generic gold-standard reference judge", "x")  # no raise

def test_assert_clean_raises_on_vendor_name():
  if not _VENDOR_TOKENS:
    pytest.skip("vendor denylist not present (public clone)")
  token = _VENDOR_TOKENS[0]
  with pytest.raises(ValueError):
    _assert_clean(f"scored against {token.upper()} gold", "x")

def test_assert_clean_raises_on_private_path():
  # Construct the private-path token dynamically so the literal doesn't appear in source.
  private_path = "/" + "users" + "/local/x"
  with pytest.raises(ValueError):
    _assert_clean(f'ROOT = "{private_path}"', "x")

def test_assert_clean_allows_words_that_contain_vendor_substrings():
  # word-boundary: single-word tokens must NOT trip on superstring words
  _assert_clean("pearson correlation coefficient; tighten the wrench", "x")  # no raise

def test_worked_example_vendor_system_rejected(tmp_path):
  if not _VENDOR_TOKENS:
    pytest.skip("vendor denylist not present (public clone)")
  vendor_name = _VENDOR_TOKENS[0].capitalize()
  wd = tmp_path / "worked"; wd.mkdir()
  (wd / "F19.json").write_text(json.dumps({"id": "F19", "system": vendor_name, "transcript": "x"}))
  out = tmp_path / "cds-bench"
  with pytest.raises(ValueError):
    build_public(str(out), seed=20260614, generated="2026-06-14", worked_dir=str(wd))

def test_worked_example_blinded_system_accepted(tmp_path):
  wd = tmp_path / "worked"; wd.mkdir()
  (wd / "F19.json").write_text(json.dumps({"id": "F19", "system": "Vendor A", "transcript": "x"}))
  out = tmp_path / "cds-bench"
  build_public(str(out), seed=20260614, generated="2026-06-14", worked_dir=str(wd))
  assert (out / "worked_examples" / "F19.json").exists()
