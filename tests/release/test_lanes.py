# tests/release/test_lanes.py
import json, pathlib
from pathlib import Path
from scripts.release.lanes import LANES, PUBLIC_DIR, HIDDEN_DIR

def test_quota_totals():
  assert sum(l.total for l in LANES.values()) == 135
  assert sum(l.public_count for l in LANES.values()) == 27

def test_four_lanes():
  """Exactly 4 lanes: golden, freshness, hallucination, halluhard."""
  assert set(LANES.keys()) == {"golden", "freshness", "hallucination", "halluhard"}

def test_public_dir_has_correct_counts():
  """PUBLIC_DIR must exist and hold exactly public_count cases per lane."""
  for l in LANES.values():
    path = pathlib.Path(PUBLIC_DIR) / l.filename
    assert path.exists(), f"public file missing: {path}"
    cases = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(cases, list)
    assert len(cases) == l.public_count, (
      f"{l.name}: expected {l.public_count} public cases, got {len(cases)}"
    )
    for c in cases:
      assert c.get("split") == "public", f"{l.name}: non-public case in PUBLIC_DIR"

def test_hidden_dir_has_correct_counts():
  """HIDDEN_DIR must exist and hold exactly (total - public_count) cases per lane."""
  if not Path(HIDDEN_DIR).exists():
    import pytest; pytest.skip("hidden set not present (public clone)")
  for l in LANES.values():
    path = pathlib.Path(HIDDEN_DIR) / l.filename
    assert path.exists(), f"hidden file missing: {path}"
    cases = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(cases, list)
    expected = l.total - l.public_count
    assert len(cases) == expected, (
      f"{l.name}: expected {expected} hidden cases, got {len(cases)}"
    )
    for c in cases:
      assert c.get("split") == "hidden", f"{l.name}: non-hidden case in HIDDEN_DIR"

def test_forced_public_ids_present_in_public_dir():
  for l in LANES.values():
    cases = json.loads((pathlib.Path(PUBLIC_DIR) / l.filename).read_text(encoding="utf-8"))
    ids = {c[l.id_field] for c in cases}
    assert l.forced_public in ids, f"{l.name}: forced id {l.forced_public} missing from PUBLIC_DIR"
