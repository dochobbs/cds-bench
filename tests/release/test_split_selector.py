# tests/release/test_split_selector.py
import json, pathlib
from scripts.release.lanes import LANES, BENCH_DIR
from scripts.release.split_selector import select_public

SEED = 20260614

def _cases(lane):
  return json.load(open(pathlib.Path(BENCH_DIR) / lane.filename))

def test_counts_match_quota():
  for lane in LANES.values():
    pub = select_public(_cases(lane), lane, SEED)
    assert len(pub) == lane.public_count, f"{lane.name}: {len(pub)}"

def test_forced_public_always_included():
  for lane in LANES.values():
    pub = select_public(_cases(lane), lane, SEED)
    assert lane.forced_public in pub

def test_deterministic_same_seed():
  lane = LANES["golden"]
  assert select_public(_cases(lane), lane, SEED) == select_public(_cases(lane), lane, SEED)

def test_different_seed_changes_selection():
  lane = LANES["golden"]
  a = select_public(_cases(lane), lane, SEED)
  b = select_public(_cases(lane), lane, SEED + 1)
  assert a != b  # forced id is in both, but the sampled remainder differs

def test_selected_ids_are_real():
  for lane in LANES.values():
    cases = _cases(lane)
    ids = {c[lane.id_field] for c in cases}
    assert select_public(cases, lane, SEED) <= ids

def test_stratified_spreads_across_groups():
  # golden public_count=12 over many categories -> should touch >=6 distinct categories
  lane = LANES["golden"]
  cases = _cases(lane)
  pub = select_public(cases, lane, SEED)
  by_id = {c[lane.id_field]: c for c in cases}
  cats = {by_id[i][lane.strat_field] for i in pub}
  assert len(cats) >= 6
