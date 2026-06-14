# scripts/release/validate_release.py
"""Release invariants for the internal CDS bench. Run: python -m scripts.release.validate_release
Exit 0 if all green, 1 otherwise."""
from __future__ import annotations
import json, sys
from pathlib import Path
from scripts.release.lanes import LANES, BENCH_DIR

def _cases(lane):
  return json.load(open(Path(BENCH_DIR) / lane.filename))

def checks() -> list[tuple[str, bool, list]]:
  results = []
  # 1. every case carries a valid split
  bad = []
  for lane in LANES.values():
    for c in _cases(lane):
      if c.get("split") not in ("public", "hidden"):
        bad.append(f"{lane.name}/{c[lane.id_field]}")
  results.append(("split_present", not bad, bad))
  # 2. per-lane public counts match quota
  wrong = []
  for lane in LANES.values():
    n = sum(c.get("split") == "public" for c in _cases(lane))
    if n != lane.public_count:
      wrong.append(f"{lane.name}:{n}!={lane.public_count}")
  results.append(("public_counts", not wrong, wrong))
  # 3. totals are exactly 27 public / 108 hidden
  pub = sum(sum(c.get("split") == "public" for c in _cases(l)) for l in LANES.values())
  hid = sum(sum(c.get("split") == "hidden" for c in _cases(l)) for l in LANES.values())
  ok = pub == 27 and hid == 108
  results.append(("totals_27_108", ok, [] if ok else [f"public={pub}", f"hidden={hid}"]))
  # 4. every forced-public/showcase id is labeled public
  miss = []
  for lane in LANES.values():
    for c in _cases(lane):
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
