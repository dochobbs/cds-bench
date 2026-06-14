# tests/release/test_lanes.py
from scripts.release.lanes import LANES, BENCH_DIR

def test_quota_totals():
  assert sum(l.total for l in LANES.values()) == 135
  assert sum(l.public_count for l in LANES.values()) == 27

def test_four_lanes():
  """Exactly 4 lanes: golden, freshness, hallucination, halluhard."""
  assert set(LANES.keys()) == {"golden", "freshness", "hallucination", "halluhard"}

def test_each_lane_file_exists_and_counts_match():
  import json, pathlib
  for l in LANES.values():
    cases = json.load(open(pathlib.Path(BENCH_DIR) / l.filename))
    assert isinstance(cases, list)
    assert len(cases) == l.total, f"{l.name}: {len(cases)} != {l.total}"

def test_forced_public_ids_present_in_their_lane():
  import json, pathlib
  for l in LANES.values():
    cases = json.load(open(pathlib.Path(BENCH_DIR) / l.filename))
    ids = {c[l.id_field] for c in cases}
    assert l.forced_public in ids, f"{l.name}: forced id {l.forced_public} missing"
