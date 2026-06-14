# scripts/release/manifest.py
"""Hidden-set hash manifest: per-case SHA-256 + Merkle root, content-only (split excluded).

Run: python -m scripts.release.manifest --out <cds-bench dir> --seed 20260614
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

# fields we add for release management — never part of the hashed case content
HASH_EXCLUDE = ("split", "validated")

def canonical_bytes(case: dict, exclude: tuple[str, ...] = HASH_EXCLUDE) -> bytes:
  c = {k: v for k, v in case.items() if k not in exclude}
  return json.dumps(c, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

def case_hash(case: dict) -> str:
  return hashlib.sha256(canonical_bytes(case)).hexdigest()

def merkle_root(leaves_hex: list[str]) -> str:
  """Binary Merkle root over an ordered list of hex leaf hashes. Odd level duplicates the last node.

  Odd-level duplication follows the Bitcoin/RFC-6962 convention; safe here because the leaf set
  and count are fixed and published alongside the root (not used for adversarial membership proofs).
  """
  if not leaves_hex:
    return hashlib.sha256(b"").hexdigest()
  level = [bytes.fromhex(h) for h in leaves_hex]
  while len(level) > 1:
    if len(level) % 2:
      level.append(level[-1])
    level = [hashlib.sha256(level[i] + level[i + 1]).digest() for i in range(0, len(level), 2)]
  return level[0].hex()

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
    "hash": "sha256 over canonical JSON, split/validated excluded",
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
