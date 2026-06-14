# scripts/release/split_selector.py
"""Carve the public sample out of the internal CDS bench.

select_public(cases, lane, seed) -> set[str]   (pure, deterministic, stratified, forced-id pinned)
apply_split(seed, bench_dir)                    (writes split=public|hidden onto each lane file)

Run: python -m scripts.release.split_selector --seed 20260614
"""
from __future__ import annotations
import argparse, json, random
from collections import defaultdict
from pathlib import Path
from scripts.release.lanes import LANES, BENCH_DIR, Lane

def select_public(cases: list[dict], lane: Lane, seed: int) -> set[str]:
  ids = [c[lane.id_field] for c in cases]
  assert lane.forced_public in ids, f"{lane.name}: forced id absent"
  chosen: set[str] = {lane.forced_public}

  groups: dict[str, list[str]] = defaultdict(list)
  for c in cases:
    groups[str(c.get(lane.strat_field, "_none"))].append(c[lane.id_field])

  rng = random.Random(f"{seed}:{lane.name}")
  # deterministic group order; shuffle members within each group
  order = sorted(groups)
  for k in order:
    rng.shuffle(groups[k])

  # round-robin one pick per group per pass until quota is met
  while len(chosen) < lane.public_count:
    progressed = False
    for k in order:
      if len(chosen) >= lane.public_count:
        break
      while groups[k]:
        cand = groups[k].pop()
        if cand not in chosen:
          chosen.add(cand)
          progressed = True
          break
    if not progressed:
      break  # exhausted (quota larger than case count) — should not happen
  return chosen

def apply_split(seed: int, bench_dir: str = BENCH_DIR) -> dict[str, int]:
  counts = {}
  for lane in LANES.values():
    path = Path(bench_dir) / lane.filename
    cases = json.load(open(path))
    pub = select_public(cases, lane, seed)
    for c in cases:
      c["split"] = "public" if c[lane.id_field] in pub else "hidden"
    json.dump(cases, open(path, "w"), indent=2, ensure_ascii=False)
    counts[lane.name] = len(pub)
  return counts

def main() -> int:
  ap = argparse.ArgumentParser()
  ap.add_argument("--seed", type=int, default=20260614)
  ap.add_argument("--bench-dir", default=BENCH_DIR)
  args = ap.parse_args()
  counts = apply_split(args.seed, args.bench_dir)
  total = sum(counts.values())
  total_cases = sum(l.total for l in LANES.values())
  print(f"split applied (seed={args.seed}): public={total} hidden={total_cases - total}  per-lane={counts}")
  return 0

if __name__ == "__main__":
  raise SystemExit(main())
