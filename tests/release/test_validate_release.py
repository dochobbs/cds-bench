# tests/release/test_validate_release.py
from scripts.release.validate_release import checks

def test_all_invariants_pass():
  failures = {name: offenders for name, ok, offenders in checks() if not ok}
  assert not failures, f"release invariant violations: {failures}"

import scripts.release.validate_release as mod

def _checks_after(monkeypatch, mutate):
  original = mod._cases
  def patched(lane):
    cases = [dict(c) for c in original(lane)]
    mutate(lane, cases)
    return cases
  monkeypatch.setattr(mod, "_cases", patched)
  return {name: ok for name, ok, _ in mod.checks()}

def test_catches_missing_split(monkeypatch):
  def mutate(lane, cases):
    if lane.name == "golden":
      cases[0].pop("split", None)
  assert not _checks_after(monkeypatch, mutate)["split_present"]

def test_catches_wrong_public_count(monkeypatch):
  def mutate(lane, cases):
    if lane.name == "golden":
      for c in cases:
        if c.get("split") == "public" and c[lane.id_field] != lane.forced_public:
          c["split"] = "hidden"  # drop one public -> count + totals break
          break
  res = _checks_after(monkeypatch, mutate)
  assert not res["public_counts"]
  assert not res["totals_27_108"]

def test_catches_showcase_not_public(monkeypatch):
  def mutate(lane, cases):
    for c in cases:
      if c[lane.id_field] == lane.forced_public:
        c["split"] = "hidden"
  assert not _checks_after(monkeypatch, mutate)["showcase_public"]
