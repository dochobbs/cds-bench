# scripts/release/validate_release.py
"""Release invariants for the internal CDS bench. Run: python -m scripts.release.validate_release
Exit 0 if all green, 1 otherwise.

In a public clone (benchmarks/hidden/ absent), the hidden-count assertion is skipped —
the public-count assertion (==27) always runs.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
from scripts.release.lanes import LANES, PUBLIC_DIR, HIDDEN_DIR

def _cases(lane):
  """Load all public cases for a lane from PUBLIC_DIR.

  Named _cases (not _public_cases) so that existing tests can monkeypatch it.
  """
  return json.load(open(Path(PUBLIC_DIR) / lane.filename))

def _hidden_cases(lane):
  return json.load(open(Path(HIDDEN_DIR) / lane.filename))

def checks() -> list[tuple[str, bool, list]]:
  results = []
  hidden_available = Path(HIDDEN_DIR).exists()

  # 1. every public case carries split=='public'
  bad = []
  for lane in LANES.values():
    for c in _cases(lane):
      if c.get("split") != "public":
        bad.append(f"{lane.name}/{c[lane.id_field]}")
  results.append(("split_present", not bad, bad))

  # 2. per-lane public counts match quota
  wrong = []
  for lane in LANES.values():
    n = sum(c.get("split") == "public" for c in _cases(lane))
    if n != lane.public_count:
      wrong.append(f"{lane.name}:{n}!={lane.public_count}")
  results.append(("public_counts", not wrong, wrong))

  # 3. totals — public==27 always; hidden==108 only if hidden dir is present
  pub = sum(sum(c.get("split") == "public" for c in _cases(l)) for l in LANES.values())
  if hidden_available:
    hid = sum(len(_hidden_cases(l)) for l in LANES.values())
    ok = pub == 27 and hid == 108
    results.append(("totals_27_108", ok, [] if ok else [f"public={pub}", f"hidden={hid}"]))
  else:
    ok = pub == 27
    results.append(("totals_27_108", ok, [] if ok else [f"public={pub}", "hidden=<not present>"]))

  # 4. every forced-public/showcase id is labeled public and present
  miss = []
  for lane in LANES.values():
    cases = _cases(lane)
    pub_ids = {c[lane.id_field] for c in cases}
    if lane.forced_public not in pub_ids:
      miss.append(f"{lane.forced_public}(missing)")
    else:
      for c in cases:
        if c[lane.id_field] == lane.forced_public and c.get("split") != "public":
          miss.append(lane.forced_public)
  results.append(("showcase_public", not miss, miss))
  return results

def main() -> int:
  ok = True
  for name, passed, offenders in checks():
    print(f"[{'PASS' if passed else 'FAIL'}] {name}" + ("" if passed else f"  ({len(offenders)}): {offenders[:12]}"))
    ok = ok and passed
  print("ALL GREEN" if ok else "RELEASE HAS VIOLATIONS")
  return 0 if ok else 1

if __name__ == "__main__":
  sys.exit(main())
