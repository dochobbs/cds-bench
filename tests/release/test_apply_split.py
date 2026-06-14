# tests/release/test_apply_split.py
import json, pathlib, shutil
from scripts.release.lanes import LANES, BENCH_DIR
from scripts.release.split_selector import apply_split

def _fixture(tmp_path):
  dst = tmp_path / "internal"
  dst.mkdir()
  for lane in LANES.values():
    shutil.copy(pathlib.Path(BENCH_DIR) / lane.filename, dst / lane.filename)
  return str(dst)

def test_apply_writes_split_field_and_is_idempotent(tmp_path):
  d = _fixture(tmp_path)
  first = apply_split(20260614, d)
  # every case now has a valid split
  for lane in LANES.values():
    cases = json.load(open(pathlib.Path(d) / lane.filename))
    assert all(c.get("split") in ("public", "hidden") for c in cases)
    assert sum(c["split"] == "public" for c in cases) == lane.public_count
  before = {lane.name: json.load(open(pathlib.Path(d) / lane.filename)) for lane in LANES.values()}
  second = apply_split(20260614, d)  # re-run with same seed
  after = {lane.name: json.load(open(pathlib.Path(d) / lane.filename)) for lane in LANES.values()}
  assert first == second        # same per-lane counts
  assert before == after        # same exact on-disk split assignments (true idempotency)

def test_totals(tmp_path):
  d = _fixture(tmp_path)
  counts = apply_split(20260614, d)
  assert sum(counts.values()) == 29
