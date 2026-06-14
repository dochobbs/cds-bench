# CDS Bench Public Release — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the tooling that carves a 29-case public sample out of the 145-case internal fam-med CDS bench, protects the 116 hidden cases with a canary + hash manifest, and emits a clean public `cds-bench` repo tree — leaving the private `cds-eval` repo untouched.

**Architecture:** A new `scripts/release/` package of small, single-purpose, mostly-pure modules driven by one lane registry (`lanes.py`). Logic is separated from I/O so it is unit-testable without API calls or network. The public-tree builder *emits* into a configurable output directory (a checkout of the separate public repo); it never copies anything from `cds-eval` except what it is explicitly told to. The eval-as-a-service harness takes an injectable scorer so it is testable with a fake.

**Tech Stack:** Python 3.13 (`.venv`), pytest, stdlib only (`json`, `hashlib`, `random`, `pathlib`, `shutil`, `datetime`). Conventions copied from `scripts/pearl/`: 2-space indent, `from __future__ import annotations`, modules run as `python -m scripts.release.<mod>`, tests under `tests/release/`, run with `.venv/bin/python -m pytest`.

**Out of scope (separate follow-on, not code/TDD):** the methods paper (spec §10 M6); creating/pushing the GitHub repo (a manual release-time step); choosing the final transcript for each worked example (curation, see Task 10).

**Spec:** `docs/superpowers/specs/2026-06-14-cds-bench-public-release-design.md`

---

## File Structure

| File | Responsibility |
|---|---|
| `scripts/release/__init__.py` | package marker |
| `scripts/release/lanes.py` | **single source of truth**: per-lane path, id field, strat field, totals, public quota, forced-public id, judge-rubric path |
| `scripts/release/split_selector.py` | choose the public 29 (pure `select_public`) + `apply_split` (writes `split` onto lane files) |
| `scripts/release/manifest.py` | `canonical_bytes`, `case_hash`, `merkle_root`, `build_manifest` (hidden-only SHA-256 manifest + meta) |
| `scripts/release/canary.py` | canary GUID + do-not-train notice constants + `stamp_case` |
| `scripts/release/assets.py` | text of static release files (LICENSE, README, CANARY, SUBMISSION.md) |
| `scripts/release/build_public.py` | assemble the `cds-bench/` public tree |
| `scripts/release/find_scored.py` | helper: locate scored runs for a showcase id (worked-example curation aid) |
| `scripts/release/submit.py` | eval-as-a-service: load hidden + run injected scorer → blinded scorecard |
| `scripts/release/validate_release.py` | release invariants (analogue of `scripts/pearl/validate_inventory.py`) |
| `tests/release/__init__.py` + `tests/release/test_*.py` | one test module per unit |

---

## Task 1: Package scaffold + lane registry

**Files:**
- Create: `scripts/release/__init__.py` (empty)
- Create: `scripts/release/lanes.py`
- Create: `tests/release/__init__.py` (empty)
- Test: `tests/release/test_lanes.py`

- [ ] **Step 1: Create empty package markers**

```bash
mkdir -p scripts/release tests/release
: > scripts/release/__init__.py
: > tests/release/__init__.py
```

- [ ] **Step 2: Write the failing test**

`tests/release/test_lanes.py`:
```python
# tests/release/test_lanes.py
from scripts.release.lanes import LANES, BENCH_DIR

def test_quota_totals():
  assert sum(l.total for l in LANES.values()) == 145
  assert sum(l.public_count for l in LANES.values()) == 29

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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/release/test_lanes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.release.lanes'`

- [ ] **Step 4: Write the registry**

`scripts/release/lanes.py`:
```python
# scripts/release/lanes.py
"""Single source of truth for the internal CDS bench lanes and the public split quota."""
from __future__ import annotations
from dataclasses import dataclass

BENCH_DIR = "benchmarks/internal"

@dataclass(frozen=True)
class Lane:
  name: str
  filename: str
  id_field: str       # key holding the case id ("search_id" for golden, "id" elsewhere)
  strat_field: str    # key used to stratify the sample
  total: int
  public_count: int
  forced_public: str  # worked-example id that MUST land in the public set
  judge_rubric: str | None  # rubric file to ship into cds-bench/rubrics/ (None = deterministic lane)

LANES: dict[str, Lane] = {
  "golden":        Lane("golden",        "golden_60.json",        "search_id", "category",   60, 12, "G52",  "eval/prompts/judge_rubric.txt"),
  "freshness":     Lane("freshness",     "freshness_30.json",     "id",        "category",   30,  6, "F19",  "eval/prompts/freshness_v1v2_judge.txt"),
  "hallucination": Lane("hallucination", "hallucination_30.json", "id",        "category",   30,  6, "H11",  "eval/prompts/halluc30_v1v2_judge.txt"),
  "halluhard":     Lane("halluhard",     "halluhard_15.json",     "id",        "category",   15,  3, "HH08", "eval/prompts/halluhard_judge.txt"),
  "calc":          Lane("calc",          "calc_micro_10.json",    "id",        "calculator", 10,  2, "C01",  None),
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/release/test_lanes.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add scripts/release/__init__.py scripts/release/lanes.py tests/release/__init__.py tests/release/test_lanes.py
git commit -m "FEATURE: release lane registry (single source of truth for 29/116 split)"
```

---

## Task 2: Public selection logic (`select_public`)

Pure function: given a lane's cases + a seed, return the set of public ids — deterministic, stratified across `strat_field`, with the forced-public id always included.

**Files:**
- Create: `scripts/release/split_selector.py`
- Test: `tests/release/test_split_selector.py`

- [ ] **Step 1: Write the failing test**

`tests/release/test_split_selector.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/release/test_split_selector.py -v`
Expected: FAIL with `ImportError: cannot import name 'select_public'`

- [ ] **Step 3: Write the implementation**

`scripts/release/split_selector.py`:
```python
# scripts/release/split_selector.py
"""Carve the public sample out of the internal CDS bench.

select_public(cases, lane, seed) -> set[str]   (pure, deterministic, stratified, forced-id pinned)
apply_split(seed, bench_dir)                    (writes split=public|hidden onto each lane file)

Run: python -m scripts.release.split_selector --seed 20260614
"""
from __future__ import annotations
import argparse, glob, json, random
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
  print(f"split applied (seed={args.seed}): public={total} hidden={145 - total}  per-lane={counts}")
  return 0

if __name__ == "__main__":
  raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/release/test_split_selector.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/release/split_selector.py tests/release/test_split_selector.py
git commit -m "FEATURE: deterministic stratified public-sample selector (forced worked-example ids pinned)"
```

---

## Task 3: Apply split to the real bench files

`apply_split` already exists from Task 2. This task adds an **idempotency test against a temp fixture** (so we never mutate the real bench in tests) and then runs it for real once.

**Files:**
- Test: `tests/release/test_apply_split.py`

- [ ] **Step 1: Write the failing test**

`tests/release/test_apply_split.py`:
```python
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
  second = apply_split(20260614, d)  # re-run
  assert first == second

def test_totals(tmp_path):
  d = _fixture(tmp_path)
  counts = apply_split(20260614, d)
  assert sum(counts.values()) == 29
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/release/test_apply_split.py -v`
Expected: FAIL (the test file is new; it fails only if logic is wrong — if Task 2 is correct it will PASS. If it PASSES immediately, that is acceptable: the behavior was already implemented and the test now locks it in.)

- [ ] **Step 3: Run the real split once and verify**

```bash
.venv/bin/python -m scripts.release.split_selector --seed 20260614
```
Expected output: `split applied (seed=20260614): public=29 hidden=116  per-lane={'golden': 12, 'freshness': 6, 'hallucination': 6, 'halluhard': 3, 'calc': 2}`

- [ ] **Step 4: Sanity-check the bench files changed as expected**

Run:
```bash
.venv/bin/python -c "import json,glob; print(sum(c['split']=='public' for f in glob.glob('benchmarks/internal/*.json') for c in json.load(open(f))))"
```
Expected: `29`

- [ ] **Step 5: Commit**

```bash
git add tests/release/test_apply_split.py benchmarks/internal/*.json
git commit -m "FEATURE: apply public/hidden split to internal bench (29 public / 116 hidden, seed 20260614)"
```

---

## Task 4: Canonicalization + per-case hash

**Files:**
- Create: `scripts/release/manifest.py`
- Test: `tests/release/test_manifest.py`

- [ ] **Step 1: Write the failing test**

`tests/release/test_manifest.py`:
```python
# tests/release/test_manifest.py
from scripts.release.manifest import canonical_bytes, case_hash

def test_canonical_excludes_split_and_is_key_order_independent():
  a = {"id": "X1", "query": "q", "split": "hidden"}
  b = {"query": "q", "id": "X1", "split": "public"}  # different order + different split
  assert canonical_bytes(a) == canonical_bytes(b)

def test_canonical_is_compact_utf8():
  out = canonical_bytes({"id": "X1", "q": "café"})
  assert isinstance(out, bytes)
  assert b", " not in out and b'": ' not in out  # compact separators

def test_case_hash_is_stable_sha256_hex():
  h = case_hash({"id": "X1", "query": "q", "split": "hidden"})
  assert len(h) == 64 and all(c in "0123456789abcdef" for c in h)
  assert h == case_hash({"id": "X1", "query": "q", "split": "public"})

def test_different_content_different_hash():
  assert case_hash({"id": "X1", "query": "a"}) != case_hash({"id": "X1", "query": "b"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/release/test_manifest.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.release.manifest'`

- [ ] **Step 3: Write the implementation (hash functions only for now)**

`scripts/release/manifest.py`:
```python
# scripts/release/manifest.py
"""Hidden-set hash manifest: per-case SHA-256 + Merkle root, content-only (split excluded).

Run: python -m scripts.release.manifest --out <cds-bench dir> --seed 20260614
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

# fields we add for release management — never part of the hashed case content
HASH_EXCLUDE = ("split", "canary", "_notice")

def canonical_bytes(case: dict, exclude: tuple[str, ...] = HASH_EXCLUDE) -> bytes:
  c = {k: v for k, v in case.items() if k not in exclude}
  return json.dumps(c, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

def case_hash(case: dict) -> str:
  return hashlib.sha256(canonical_bytes(case)).hexdigest()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/release/test_manifest.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/release/manifest.py tests/release/test_manifest.py
git commit -m "FEATURE: content-only canonicalization + SHA-256 case hashing"
```

---

## Task 5: Merkle root

**Files:**
- Modify: `scripts/release/manifest.py` (add `merkle_root`)
- Test: `tests/release/test_manifest.py` (add cases)

- [ ] **Step 1: Add failing tests**

Append to `tests/release/test_manifest.py`:
```python
from scripts.release.manifest import merkle_root

def test_merkle_root_deterministic_and_order_sensitive():
  leaves = ["aa"*32, "bb"*32, "cc"*32]
  assert merkle_root(leaves) == merkle_root(leaves)
  assert len(merkle_root(leaves)) == 64

def test_merkle_root_empty_is_sha256_of_empty():
  import hashlib
  assert merkle_root([]) == hashlib.sha256(b"").hexdigest()

def test_merkle_root_changes_when_a_leaf_changes():
  base = ["aa"*32, "bb"*32]
  changed = ["aa"*32, "bc"*32]
  assert merkle_root(base) != merkle_root(changed)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/release/test_manifest.py -k merkle -v`
Expected: FAIL with `ImportError: cannot import name 'merkle_root'`

- [ ] **Step 3: Add the implementation**

Append to `scripts/release/manifest.py`:
```python
def merkle_root(leaves_hex: list[str]) -> str:
  """Binary Merkle root over an ordered list of hex leaf hashes. Odd level duplicates the last node."""
  if not leaves_hex:
    return hashlib.sha256(b"").hexdigest()
  level = [bytes.fromhex(h) for h in leaves_hex]
  while len(level) > 1:
    if len(level) % 2:
      level.append(level[-1])
    level = [hashlib.sha256(level[i] + level[i + 1]).digest() for i in range(0, len(level), 2)]
  return level[0].hex()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/release/test_manifest.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/release/manifest.py tests/release/test_manifest.py
git commit -m "FEATURE: deterministic Merkle root over hidden-case hashes"
```

---

## Task 6: Manifest writer (hidden-only)

Writes `HIDDEN_MANIFEST.sha256` (sha256sum-style lines, hidden cases only) + `HIDDEN_MANIFEST.meta.json` (merkle root, count, seed, generated date).

**Files:**
- Modify: `scripts/release/manifest.py` (add `collect_hidden`, `build_manifest`, `main`)
- Test: `tests/release/test_manifest.py` (add cases)

- [ ] **Step 1: Add failing tests**

Append to `tests/release/test_manifest.py`:
```python
import json as _json, pathlib
from scripts.release.manifest import build_manifest

def test_build_manifest_hidden_only(tmp_path):
  out = tmp_path / "cds-bench"
  out.mkdir()
  meta = build_manifest(str(out), seed=20260614, generated="2026-06-14")
  lines = (out / "HIDDEN_MANIFEST.sha256").read_text().strip().splitlines()
  assert len(lines) == 116, f"expected 116 hidden, got {len(lines)}"
  # sha256sum format: "<64hex>  <lane>/<id>"
  for ln in lines:
    h, name = ln.split("  ", 1)
    assert len(h) == 64 and "/" in name
  m = _json.loads((out / "HIDDEN_MANIFEST.meta.json").read_text())
  assert m["hidden_count"] == 116 and len(m["merkle_root"]) == 64
  assert m["seed"] == 20260614 and m["generated"] == "2026-06-14"

def test_manifest_lists_no_public_ids(tmp_path):
  out = tmp_path / "cds-bench"; out.mkdir()
  build_manifest(str(out), seed=20260614, generated="2026-06-14")
  names = (out / "HIDDEN_MANIFEST.sha256").read_text()
  assert "G52" not in names and "F19" not in names  # forced-public ids must not appear
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/release/test_manifest.py -k build_manifest -v`
Expected: FAIL with `ImportError: cannot import name 'build_manifest'`

- [ ] **Step 3: Add the implementation**

Append to `scripts/release/manifest.py`:
```python
from scripts.release.lanes import LANES, BENCH_DIR

def collect_hidden(bench_dir: str = BENCH_DIR) -> list[tuple[str, str]]:
  """Return ordered [(name, hash)] for every hidden case, name = '<lane>/<id>', sorted by name."""
  rows: list[tuple[str, str]] = []
  for lane in LANES.values():
    cases = json.load(open(Path(bench_dir) / lane.filename))
    for c in cases:
      if c.get("split") == "hidden":
        rows.append((f"{lane.name}/{c[lane.id_field]}", case_hash(c)))
  rows.sort(key=lambda r: r[0])
  return rows

def build_manifest(out_dir: str, seed: int, generated: str, bench_dir: str = BENCH_DIR) -> dict:
  rows = collect_hidden(bench_dir)
  out = Path(out_dir)
  (out / "HIDDEN_MANIFEST.sha256").write_text(
    "".join(f"{h}  {name}\n" for name, h in rows), encoding="utf-8")
  meta = {
    "benchmark": "cds-bench (internal fam-med CDS)",
    "hidden_count": len(rows),
    "merkle_root": merkle_root([h for _, h in rows]),
    "seed": seed,
    "generated": generated,
    "hash": "sha256 over canonical JSON, split/canary excluded",
  }
  (out / "HIDDEN_MANIFEST.meta.json").write_text(
    json.dumps(meta, indent=2) + "\n", encoding="utf-8")
  return meta

def main() -> int:
  ap = argparse.ArgumentParser()
  ap.add_argument("--out", required=True, help="cds-bench output dir")
  ap.add_argument("--seed", type=int, default=20260614)
  ap.add_argument("--date", required=True, help="release date YYYY-MM-DD (pass explicitly)")
  args = ap.parse_args()
  meta = build_manifest(args.out, args.seed, args.date)
  print(f"manifest: {meta['hidden_count']} hidden, merkle={meta['merkle_root'][:12]}…")
  return 0

if __name__ == "__main__":
  raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/release/test_manifest.py -v`
Expected: PASS (9 passed). Requires Task 3 to have run (cases carry `split`).

- [ ] **Step 5: Commit**

```bash
git add scripts/release/manifest.py tests/release/test_manifest.py
git commit -m "FEATURE: hidden-only SHA-256 manifest + Merkle meta (116 cases, no public ids leaked)"
```

---

## Task 7: Canary module

**Files:**
- Create: `scripts/release/canary.py`
- Test: `tests/release/test_canary.py`

- [ ] **Step 1: Write the failing test**

`tests/release/test_canary.py`:
```python
# tests/release/test_canary.py
from scripts.release.canary import CANARY, DO_NOT_TRAIN_NOTICE, stamp_case

def test_canary_is_a_fixed_guid_string():
  assert CANARY.startswith("CDS-BENCH-CANARY-")
  assert "DO-NOT-TRAIN" in CANARY

def test_stamp_adds_canary_and_notice_without_dropping_content():
  case = {"id": "X1", "query": "q"}
  out = stamp_case(case)
  assert out["id"] == "X1" and out["query"] == "q"
  assert out["canary"] == CANARY
  assert out["_notice"] == DO_NOT_TRAIN_NOTICE

def test_stamp_does_not_mutate_input():
  case = {"id": "X1"}
  stamp_case(case)
  assert "canary" not in case
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/release/test_canary.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.release.canary'`

- [ ] **Step 3: Write the implementation**

`scripts/release/canary.py`:
```python
# scripts/release/canary.py
"""Canary GUID + do-not-train notice stamped onto every released public case."""
from __future__ import annotations

# Fixed, unique canary string. Probe future models for memorization of this exact GUID.
CANARY = "CDS-BENCH-CANARY-7f3a2e9c-4b61-4d2a-9e8f-DO-NOT-TRAIN"

DO_NOT_TRAIN_NOTICE = (
  "This file is part of the cds-bench public sample (internal family-medicine CDS "
  "benchmark). It is published for review and reproducibility under CC-BY-NC-ND. "
  "Do NOT use it, or any derivative, as model training or fine-tuning data. The held-out "
  "test set is not distributed; see SUBMISSION.md for evaluation."
)

def stamp_case(case: dict) -> dict:
  """Return a copy of case with the canary + notice attached (input left unmodified)."""
  out = dict(case)
  out["canary"] = CANARY
  out["_notice"] = DO_NOT_TRAIN_NOTICE
  return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/release/test_canary.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/release/canary.py tests/release/test_canary.py
git commit -m "FEATURE: canary GUID + do-not-train notice stamping"
```

---

## Task 8: Static release-asset text

**Files:**
- Create: `scripts/release/assets.py`
- Test: `tests/release/test_assets.py`

- [ ] **Step 1: Write the failing test**

`tests/release/test_assets.py`:
```python
# tests/release/test_assets.py
from scripts.release.assets import LICENSE, README, CANARY_FILE, SUBMISSION
from scripts.release.canary import CANARY

def test_license_is_cc_by_nc_nd_plus_mit_code():
  assert "CC BY-NC-ND" in LICENSE
  assert "MIT" in LICENSE  # code carve-out

def test_readme_states_no_train_and_split():
  assert "DO NOT" in README.upper()
  assert "29" in README and "116" in README

def test_canary_file_contains_the_guid():
  assert CANARY in CANARY_FILE

def test_submission_describes_eval_as_a_service():
  assert "SUBMISSION" in SUBMISSION.upper() or "submit" in SUBMISSION.lower()
  assert "hidden" in SUBMISSION.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/release/test_assets.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.release.assets'`

- [ ] **Step 3: Write the implementation**

`scripts/release/assets.py`:
```python
# scripts/release/assets.py
"""Static text for the public cds-bench repo (LICENSE, README, CANARY, SUBMISSION)."""
from __future__ import annotations
from scripts.release.canary import CANARY, DO_NOT_TRAIN_NOTICE

LICENSE = """cds-bench license

DATA (everything under public/ and worked_examples/, and the rubrics/):
  Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International
  (CC BY-NC-ND 4.0). https://creativecommons.org/licenses/by-nc-nd/4.0/
  You may share with attribution for non-commercial purposes without modification.
  You may NOT use this data, or derivatives, as model training or fine-tuning data.

CODE (everything under scoring/):
  MIT License. Permissive reuse with attribution.

The held-out test set is not distributed under any license; it is not included here.
"""

README = f"""# cds-bench — internal family-medicine CDS benchmark (public sample)

This repository publishes a **representative 29-case sample** and the full scoring
methodology of a 145-case clinical-decision-support benchmark. The remaining
**116 cases are held out** and never distributed, so models cannot train on them.

- `public/` — 29 cases across 5 lanes (golden, freshness, hallucination, halluhard, calc)
- `worked_examples/` — 5 cases shown end-to-end (query → rubric → gold → transcript → score)
- `rubrics/` — the judge rubrics used to score each lane
- `scoring/` — the scoring harness (MIT)
- `HIDDEN_MANIFEST.sha256` / `.meta.json` — SHA-256 + Merkle root of the 116 hidden cases
- `SUBMISSION.md` — how to evaluate against the hidden set (eval-as-a-service)

## {DO_NOT_TRAIN_NOTICE}

See LICENSE. Canary: `{CANARY}`
"""

CANARY_FILE = f"""{CANARY}

{DO_NOT_TRAIN_NOTICE}
"""

SUBMISSION = """# Evaluating against the hidden cds-bench test set

The 116 hidden cases are never published. To get a hidden-set score:

1. Provide a model endpoint (or a set of pre-generated transcripts keyed by case id).
2. The maintainer runs them through the hidden harness with the published rubrics.
3. You receive a blinded scorecard: your system's per-lane scores alongside
   anonymized comparator rows (Vendor A / Vendor B …).

The hidden cases, their gold answers, and per-vendor identities are not shared.
The published `HIDDEN_MANIFEST.sha256` lets you verify, after the fact, that the
hidden set was fixed at release time.
"""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/release/test_assets.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/release/assets.py tests/release/test_assets.py
git commit -m "FEATURE: static release assets (CC-BY-NC-ND license, README, CANARY, SUBMISSION)"
```

---

## Task 9: Public-tree builder

Assembles the `cds-bench/` tree: stamped public cases per lane, the lane judge rubrics, the scoring harness, static assets, and the hidden manifest. Worked-example overlays are handled in Task 10; here the builder emits all 29 public cases as stamped `query + rubric-context + gold` JSON.

**Files:**
- Create: `scripts/release/build_public.py`
- Test: `tests/release/test_build_public.py`

- [ ] **Step 1: Write the failing test**

`tests/release/test_build_public.py`:
```python
# tests/release/test_build_public.py
import json, pathlib
from scripts.release.lanes import LANES
from scripts.release.canary import CANARY
from scripts.release.build_public import build_public

def _build(tmp_path):
  out = tmp_path / "cds-bench"
  build_public(str(out), seed=20260614, generated="2026-06-14")
  return out

def test_emits_29_public_cases(tmp_path):
  out = _build(tmp_path)
  n = sum(len(list((out / "public" / lane).glob("*.json"))) for lane in LANES)
  assert n == 29

def test_per_lane_counts(tmp_path):
  out = _build(tmp_path)
  for lane in LANES.values():
    got = len(list((out / "public" / lane.name).glob("*.json")))
    assert got == lane.public_count, f"{lane.name}: {got}"

def test_every_public_case_is_stamped(tmp_path):
  out = _build(tmp_path)
  for lane in LANES:
    for f in (out / "public" / lane).glob("*.json"):
      assert json.loads(f.read_text())["canary"] == CANARY

def test_no_hidden_case_leaks_into_public(tmp_path):
  out = _build(tmp_path)
  for lane in LANES:
    for f in (out / "public" / lane).glob("*.json"):
      assert json.loads(f.read_text())["split"] == "public"

def test_rubrics_shipped_for_judge_lanes(tmp_path):
  out = _build(tmp_path)
  # 4 lanes have a judge rubric; calc is deterministic (None)
  shipped = list((out / "rubrics").glob("*"))
  assert len(shipped) == 4

def test_static_assets_present(tmp_path):
  out = _build(tmp_path)
  for name in ("LICENSE", "README.md", "CANARY", "SUBMISSION.md",
               "HIDDEN_MANIFEST.sha256", "HIDDEN_MANIFEST.meta.json"):
    assert (out / name).exists(), name

def test_scoring_artifacts_shipped(tmp_path):
  out = _build(tmp_path)
  for name in ("judge.py", "cds_ws2.txt", "cheap_judge_smoke.py"):
    assert (out / "scoring" / name).exists(), name
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/release/test_build_public.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.release.build_public'`

- [ ] **Step 3: Write the implementation**

`scripts/release/build_public.py`:
```python
# scripts/release/build_public.py
"""Assemble the public cds-bench repo tree. Emits ONLY what is listed here.

Run: python -m scripts.release.build_public --out ../cds-bench --seed 20260614 --date 2026-06-14
"""
from __future__ import annotations
import argparse, json, shutil
from pathlib import Path
from scripts.release.lanes import LANES, BENCH_DIR
from scripts.release.canary import stamp_case
from scripts.release import assets
from scripts.release.manifest import build_manifest

# MIT-shipped methodology artifacts (spec §8): reference scorer, prompt template, calibration runner
SCORING_SRCS = [
  "eval/evaluators/judge.py",
  "eval/prompts/cds_ws2.txt",
  "eval/runners/cheap_judge_smoke.py",
]

def _write_json(path: Path, obj) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def build_public(out_dir: str, seed: int, generated: str, bench_dir: str = BENCH_DIR) -> dict:
  out = Path(out_dir)
  if out.exists():
    shutil.rmtree(out)
  out.mkdir(parents=True)

  counts = {}
  for lane in LANES.values():
    cases = json.load(open(Path(bench_dir) / lane.filename))
    public = [c for c in cases if c.get("split") == "public"]
    counts[lane.name] = len(public)
    for c in public:
      _write_json(out / "public" / lane.name / f"{c[lane.id_field]}.json", stamp_case(c))
    if lane.judge_rubric:
      dst = out / "rubrics" / f"{lane.name}__{Path(lane.judge_rubric).name}"
      dst.parent.mkdir(parents=True, exist_ok=True)
      shutil.copy(lane.judge_rubric, dst)

  # scoring harness + methodology artifacts (MIT)
  (out / "scoring").mkdir(parents=True, exist_ok=True)
  for src in SCORING_SRCS:
    shutil.copy(src, out / "scoring" / Path(src).name)

  # static assets
  (out / "LICENSE").write_text(assets.LICENSE, encoding="utf-8")
  (out / "README.md").write_text(assets.README, encoding="utf-8")
  (out / "CANARY").write_text(assets.CANARY_FILE, encoding="utf-8")
  (out / "SUBMISSION.md").write_text(assets.SUBMISSION, encoding="utf-8")

  # hidden manifest
  build_manifest(str(out), seed=seed, generated=generated, bench_dir=bench_dir)
  return counts

def main() -> int:
  ap = argparse.ArgumentParser()
  ap.add_argument("--out", required=True)
  ap.add_argument("--seed", type=int, default=20260614)
  ap.add_argument("--date", required=True, help="release date YYYY-MM-DD")
  args = ap.parse_args()
  counts = build_public(args.out, args.seed, args.date)
  print(f"public tree built at {args.out}: {sum(counts.values())} cases  {counts}")
  return 0

if __name__ == "__main__":
  raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/release/test_build_public.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/release/build_public.py tests/release/test_build_public.py
git commit -m "FEATURE: public-tree builder (29 stamped cases, rubrics, scoring, assets, manifest)"
```

---

## Task 10: Worked-example overlay + curation helper

The 5 showcase cases ship with a transcript + judge score overlay. Selecting which transcript is a human judgment, so this task (a) defines the overlay schema and makes the builder include it when present, and (b) ships a helper that locates candidate scored runs for a showcase id.

**Files:**
- Create: `scripts/release/find_scored.py`
- Modify: `scripts/release/build_public.py` (include `worked_examples/` when overlays exist)
- Modify: `scripts/release/lanes.py` (add `WORKED_DIR` constant)
- Test: `tests/release/test_worked_examples.py`

- [ ] **Step 1: Add the overlay dir constant**

Append to `scripts/release/lanes.py`:
```python
WORKED_DIR = "benchmarks/internal/worked"  # optional curated overlays: <ID>.json {transcript, scores, system}
SHOWCASE_IDS = ("G52", "F19", "H11", "HH08", "C01")
```

- [ ] **Step 2: Write the failing test**

`tests/release/test_worked_examples.py`:
```python
# tests/release/test_worked_examples.py
import json
from pathlib import Path
from scripts.release.build_public import build_public
from scripts.release.lanes import WORKED_DIR, SHOWCASE_IDS

def test_overlay_emitted_to_worked_examples(tmp_path):
  # seed a fake overlay for one showcase id
  wd = Path(WORKED_DIR); wd.mkdir(parents=True, exist_ok=True)
  overlay = wd / "F19.json"
  created = not overlay.exists()
  if created:
    overlay.write_text(json.dumps({
      "id": "F19", "system": "Vendor A",
      "transcript": "…answer…", "scores": {"freshness": 2}}), encoding="utf-8")
  try:
    out = tmp_path / "cds-bench"
    build_public(str(out), seed=20260614, generated="2026-06-14")
    emitted = out / "worked_examples" / "F19.json"
    assert emitted.exists()
    assert json.loads(emitted.read_text())["id"] == "F19"
  finally:
    if created:
      overlay.unlink()

def test_showcase_ids_are_all_forced_public():
  from scripts.release.lanes import LANES
  forced = {l.forced_public for l in LANES.values()}
  assert set(SHOWCASE_IDS) == forced
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/release/test_worked_examples.py -v`
Expected: FAIL (`worked_examples/F19.json` not emitted — builder has no overlay logic yet)

- [ ] **Step 4: Add overlay emission to the builder**

First, extend the existing `lanes` import line in `scripts/release/build_public.py` to include `WORKED_DIR`:
```python
from scripts.release.lanes import LANES, BENCH_DIR, WORKED_DIR
```
Then insert this block in `build_public`, immediately before the `# hidden manifest` comment:
```python
  # worked-example overlays (optional; curated by hand — see find_scored.py)
  (out / "worked_examples").mkdir(parents=True, exist_ok=True)
  wd = Path(WORKED_DIR)
  if wd.exists():
    for f in sorted(wd.glob("*.json")):
      shutil.copy(f, out / "worked_examples" / f.name)
```

- [ ] **Step 5: Write the curation helper**

`scripts/release/find_scored.py`:
```python
# scripts/release/find_scored.py
"""Locate scored runs mentioning a showcase id, to curate worked-example overlays.

Run: python -m scripts.release.find_scored F19
Prints candidate result files that reference the id (newest first).
"""
from __future__ import annotations
import glob, os, sys

def find(case_id: str, root: str = "results/internal") -> list[str]:
  hits = []
  for f in glob.glob(f"{root}/**/*.json", recursive=True):
    try:
      with open(f, encoding="utf-8") as fh:
        if case_id in fh.read():
          hits.append(f)
    except (OSError, UnicodeDecodeError):
      continue
  hits.sort(key=os.path.getmtime, reverse=True)
  return hits

def main() -> int:
  if len(sys.argv) != 2:
    print("usage: python -m scripts.release.find_scored <CASE_ID>")
    return 2
  for f in find(sys.argv[1]):
    print(f)
  return 0

if __name__ == "__main__":
  raise SystemExit(main())
```

- [ ] **Step 6: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/release/test_worked_examples.py -v`
Expected: PASS (2 passed)

- [ ] **Step 7: Commit**

```bash
git add scripts/release/lanes.py scripts/release/build_public.py scripts/release/find_scored.py tests/release/test_worked_examples.py
git commit -m "FEATURE: worked-example overlays + scored-run curation helper"
```

---

## Task 11: Eval-as-a-service submission harness

Loads the hidden cases and scores a submitter's transcripts via an **injectable scorer** (so it is testable without API calls), then emits a blinded scorecard. The real scorer adapter (wrapping `eval/evaluators/judge.py`) is wired at call time; tests use a fake.

**Files:**
- Create: `scripts/release/submit.py`
- Test: `tests/release/test_submit.py`

- [ ] **Step 1: Write the failing test**

`tests/release/test_submit.py`:
```python
# tests/release/test_submit.py
from scripts.release.submit import load_hidden, score_submission

def test_load_hidden_returns_116():
  hidden = load_hidden()
  assert len(hidden) == 116
  assert all("lane" in h and "id" in h and "case" in h for h in hidden)

def test_score_submission_blinds_and_aggregates():
  hidden = load_hidden()
  transcripts = {h["id"]: "some answer" for h in hidden}
  # fake scorer: returns 1.0 for everything
  fake = lambda case, answer, lane: 1.0
  card = score_submission(transcripts, scorer=fake, system_alias="SubmittedModel")
  assert card["system"] == "SubmittedModel"
  assert set(card["per_lane"]) == {"golden", "freshness", "hallucination", "halluhard", "calc"}
  assert card["per_lane"]["calc"]["n"] == 8  # hidden calc count
  assert card["per_lane"]["golden"]["mean"] == 1.0

def test_scorecard_contains_no_vendor_identities():
  hidden = load_hidden()
  transcripts = {h["id"]: "x" for h in hidden}
  card = score_submission(transcripts, scorer=lambda c, a, l: 0.5, system_alias="X")
  blob = str(card).lower()
  for forbidden in ("openevidence", "amboss", "lisa", "glass", "elation"):
    assert forbidden not in blob
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/release/test_submit.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.release.submit'`

- [ ] **Step 3: Write the implementation**

`scripts/release/submit.py`:
```python
# scripts/release/submit.py
"""Eval-as-a-service: score a submitter's transcripts against the hidden set, return a blinded card.

The scorer is injected: scorer(case: dict, answer: str, lane: str) -> float.
Hidden cases, gold answers, and vendor identities never appear in the returned scorecard.
"""
from __future__ import annotations
import json
from pathlib import Path
from statistics import mean
from typing import Callable
from scripts.release.lanes import LANES, BENCH_DIR

Scorer = Callable[[dict, str, str], float]

def load_hidden(bench_dir: str = BENCH_DIR) -> list[dict]:
  out = []
  for lane in LANES.values():
    cases = json.load(open(Path(bench_dir) / lane.filename))
    for c in cases:
      if c.get("split") == "hidden":
        out.append({"lane": lane.name, "id": c[lane.id_field], "case": c})
  return out

def score_submission(transcripts: dict[str, str], scorer: Scorer,
                     system_alias: str, bench_dir: str = BENCH_DIR) -> dict:
  hidden = load_hidden(bench_dir)
  by_lane: dict[str, list[float]] = {l: [] for l in LANES}
  missing = []
  for h in hidden:
    ans = transcripts.get(h["id"])
    if ans is None:
      missing.append(h["id"])
      continue
    by_lane[h["lane"]].append(scorer(h["case"], ans, h["lane"]))
  per_lane = {l: {"n": len(v), "mean": (mean(v) if v else None)} for l, v in by_lane.items()}
  return {
    "system": system_alias,                  # caller-chosen alias only
    "per_lane": per_lane,
    "missing_count": len(missing),
    "overall_mean": (mean([s for v in by_lane.values() for s in v])
                     if any(by_lane.values()) else None),
  }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/release/test_submit.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/release/submit.py tests/release/test_submit.py
git commit -m "FEATURE: eval-as-a-service harness (hidden loader + injectable scorer + blinded scorecard)"
```

---

## Task 12: Release invariants validator

A single command that asserts the release is well-formed — the analogue of `scripts/pearl/validate_inventory.py`.

**Files:**
- Create: `scripts/release/validate_release.py`
- Test: `tests/release/test_validate_release.py`

- [ ] **Step 1: Write the failing test**

`tests/release/test_validate_release.py`:
```python
# tests/release/test_validate_release.py
from scripts.release.validate_release import checks

def test_all_invariants_pass():
  failures = {name: offenders for name, ok, offenders in checks() if not ok}
  assert not failures, f"release invariant violations: {failures}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/release/test_validate_release.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.release.validate_release'`

- [ ] **Step 3: Write the implementation**

`scripts/release/validate_release.py`:
```python
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
  # 3. totals are exactly 29 / 116
  pub = sum(sum(c.get("split") == "public" for c in _cases(l)) for l in LANES.values())
  results.append(("totals_29_116", pub == 29, [] if pub == 29 else [f"public={pub}"]))
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
    print(f"[{'PASS' if passed else 'FAIL'}] {name}" + ("" if passed else f"  {offenders[:12]}"))
    ok = ok and passed
  print("ALL GREEN" if ok else "RELEASE HAS VIOLATIONS")
  return 0 if ok else 1

if __name__ == "__main__":
  sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/release/test_validate_release.py -v`
Expected: PASS (1 passed). Requires Task 3 to have run.

- [ ] **Step 5: Commit**

```bash
git add scripts/release/validate_release.py tests/release/test_validate_release.py
git commit -m "FEATURE: release invariants validator (split present, counts, totals, showcase public)"
```

---

## Task 13: Full-suite verification + end-to-end dry build

- [ ] **Step 1: Run the entire release test suite**

Run: `.venv/bin/python -m pytest tests/release/ -v`
Expected: all PASS (no failures across the 8 test modules).

- [ ] **Step 2: Run the full existing suite to confirm no regressions**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: previously-passing tests still pass (the PEARL foundation suite + new release suite).

- [ ] **Step 3: Do a real end-to-end public build into a scratch dir**

Run: `.venv/bin/python -m scripts.release.build_public --out /tmp/cds-bench-dryrun --date 2026-06-14`
Expected: `public tree built at /tmp/cds-bench-dryrun: 29 cases  {'golden': 12, 'freshness': 6, 'hallucination': 6, 'halluhard': 3, 'calc': 2}`

- [ ] **Step 4: Verify the dry-run tree shape + no hidden leak**

Run:
```bash
.venv/bin/python - <<'PY'
import json, glob
n = sum(1 for f in glob.glob("/tmp/cds-bench-dryrun/public/**/*.json", recursive=True))
hidden_lines = open("/tmp/cds-bench-dryrun/HIDDEN_MANIFEST.sha256").read().strip().splitlines()
print("public cases:", n, "| hidden manifest lines:", len(hidden_lines))
# assert no hidden id string appears in any public file name or content
PY
```
Expected: `public cases: 29 | hidden manifest lines: 116`

- [ ] **Step 5: Run the invariants validator**

Run: `.venv/bin/python -m scripts.release.validate_release`
Expected: `ALL GREEN`

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "CHORE: release pipeline end-to-end verified (29/116, ALL GREEN)"
```

---

## Post-plan manual steps (not code)

These happen at release time, after the pipeline is built and green:

1. **Curate the 5 worked-example overlays** — for each showcase id (G52/F19/H11/HH08/C01), run `python -m scripts.release.find_scored <ID>`, pick a representative scored transcript, blind the system name, and save to `benchmarks/internal/worked/<ID>.json`. Re-run `build_public` so they land in `worked_examples/`.
2. **Confirm the HH08 → HH06 decision** (spec §6 open swap) before locking the showcase.
3. **Create the public GitHub repo** `github.com/dochobbs/cds-bench`, point `build_public --out` at its checkout, commit + push.
4. **Finalize license wording** (spec §12.3) and **canonicalization note** (§12.4) with fresh eyes.
5. **Write the methods paper** (spec §10) — separate effort.
