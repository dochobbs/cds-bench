# tests/release/test_build_public.py
import json, pathlib
from scripts.release.lanes import LANES
from scripts.release.build_public import build_public

def _build(tmp_path):
  out = tmp_path / "cds-bench"
  build_public(str(out), seed=20260614, generated="2026-06-14")
  return out

def test_emits_27_public_cases(tmp_path):
  out = _build(tmp_path)
  n = sum(len(list((out / "public" / lane).glob("*.json"))) for lane in LANES)
  assert n == 27

def test_per_lane_counts(tmp_path):
  out = _build(tmp_path)
  for lane in LANES.values():
    got = len(list((out / "public" / lane.name).glob("*.json")))
    assert got == lane.public_count, f"{lane.name}: {got}"

def test_no_canary_or_notice_in_public_cases(tmp_path):
  """Public cases must NOT contain canary or _notice fields."""
  out = _build(tmp_path)
  for lane in LANES:
    for f in (out / "public" / lane).glob("*.json"):
      d = json.loads(f.read_text())
      assert "canary" not in d, f"{f.name} still contains 'canary'"
      assert "_notice" not in d, f"{f.name} still contains '_notice'"

def test_no_hidden_case_leaks_into_public(tmp_path):
  out = _build(tmp_path)
  for lane in LANES:
    for f in (out / "public" / lane).glob("*.json"):
      d = json.loads(f.read_text())
      # split field is stripped from emitted cases (not present)
      assert "split" not in d, f"split field leaked into {f.name}"

def test_rubrics_shipped_for_judge_lanes(tmp_path):
  out = _build(tmp_path)
  shipped = {f.name for f in (out / "rubrics").glob("*")}
  assert shipped == {f"{l.name}.txt" for l in LANES.values() if l.judge_rubric}
  assert len(shipped) == 4

def test_static_assets_present(tmp_path):
  out = _build(tmp_path)
  for name in ("LICENSE", "README.md", "SUBMISSION.md",
               "HIDDEN_MANIFEST.sha256", "HIDDEN_MANIFEST.meta.json"):
    assert (out / name).exists(), name

def test_no_canary_file(tmp_path):
  """CANARY file must not be emitted."""
  out = _build(tmp_path)
  assert not (out / "CANARY").exists(), "CANARY file should not be emitted"

def test_scoring_artifacts_shipped(tmp_path):
  out = _build(tmp_path)
  for name in ("judge.py", "cds_ws2.txt", "calibrate_judge.py"):
    assert (out / "scoring" / name).exists(), name

def test_shipped_methodology_is_vendor_clean(tmp_path):
  from scripts.release.build_public import _assert_clean
  out = _build(tmp_path)
  for sub in ("scoring", "rubrics"):
    for f in (out / sub).glob("*"):
      _assert_clean(f.read_text(encoding="utf-8"), f"{sub}/{f.name}")  # raises if any leak

def test_public_cases_are_vendor_clean(tmp_path):
  """Each emitted public case JSON must pass the vendor-clean gate."""
  from scripts.release.build_public import _assert_clean
  out = _build(tmp_path)
  for lane in LANES:
    for f in (out / "public" / lane).glob("*.json"):
      _assert_clean(f.read_text(encoding="utf-8"), f"public/{lane}/{f.name}")

def test_internal_calibration_runner_not_shipped(tmp_path):
  out = _build(tmp_path)
  assert not (out / "scoring" / "cheap_judge_smoke.py").exists()

def test_build_refuses_non_cds_bench_dir(tmp_path):
  import pytest
  victim = tmp_path / "not-cds-bench"
  victim.mkdir()
  (victim / "important.txt").write_text("do not delete")
  with pytest.raises(ValueError):
    build_public(str(victim), seed=20260614, generated="2026-06-14")
  assert (victim / "important.txt").exists()  # guard left it untouched

def test_manifest_is_wellformed(tmp_path):
  out = _build(tmp_path)
  meta = json.loads((out / "HIDDEN_MANIFEST.meta.json").read_text())
  assert meta["hidden_count"] == 108
  assert len(meta["merkle_root"]) == 64 and all(c in "0123456789abcdef" for c in meta["merkle_root"])
