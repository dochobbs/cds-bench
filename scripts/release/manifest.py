# scripts/release/manifest.py
"""Hidden-set hash manifest: per-case salted SHA-256 + Merkle root, content-only (split excluded).

Run: python -m scripts.release.manifest --out <cds-bench dir> --seed 20260614 --date YYYY-MM-DD

The per-case hash is salted with a per-release secret stored at release_clean/manifest_salt.txt
(gitignored; maintainer-only). Only the salt_commitment (sha256 of the salt) is committed.
The salt is revealed at scoring time so anyone can recompute and verify the held-out set was
fixed at release.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

SALT_PATH = "release_clean/manifest_salt.txt"

# fields we add for release management — never part of the hashed case content
HASH_EXCLUDE = ("split", "validated")

def load_salt(path: str = SALT_PATH) -> bytes:
  """Load the per-release secret salt from the gitignored maintainer file.

  Raises RuntimeError with a clear, actionable message when the file is absent (e.g., a
  public clone).  Never silently falls back to unsalted hashing.
  """
  p = Path(path)
  if not p.exists():
    raise RuntimeError(
      "manifest salt required at release_clean/manifest_salt.txt to (re)build the manifest — "
      "this is a maintainer-only operation; public clones use the committed manifest"
    )
  hex_str = p.read_text(encoding="utf-8").strip()
  return bytes.fromhex(hex_str)

def canonical_bytes(case: dict, exclude: tuple[str, ...] = HASH_EXCLUDE) -> bytes:
  c = {k: v for k, v in case.items() if k not in exclude}
  return json.dumps(c, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

def case_hash(case: dict, salt_bytes: bytes = b"") -> str:
  """Return the salted (or unsalted when salt_bytes==b'') SHA-256 of the canonical case JSON.

  Production callers MUST pass salt_bytes from load_salt().  The salt_bytes=b'' default exists
  only so that tests that exercise canonical_bytes / Merkle structure without the hidden set can
  still call this function; it is never used on the maintainer machine (which always has the salt).
  """
  payload = salt_bytes + b"\x00" + canonical_bytes(case) if salt_bytes else canonical_bytes(case)
  return hashlib.sha256(payload).hexdigest()

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

from scripts.release.lanes import LANES, HIDDEN_DIR

def collect_hidden(hidden_dir: str = HIDDEN_DIR, salt_bytes: bytes = b"") -> list[tuple[str, str]]:
  """Return ordered [(name, hash)] for every hidden case, name = '<lane>/<id>', sorted by name.

  Raises FileNotFoundError with a clear message if hidden_dir is absent — this is the expected
  state in a public clone where the held-out cases are maintainer-private.
  salt_bytes MUST be provided (loaded via load_salt()) on the maintainer machine.
  """
  hdir = Path(hidden_dir)
  if not hdir.exists():
    raise FileNotFoundError(
      f"hidden set not present at {hidden_dir!r} — this looks like a public clone; "
      "the held-out cases are maintainer-private"
    )
  rows: list[tuple[str, str]] = []
  for lane in LANES.values():
    cases = json.load(open(hdir / lane.filename))
    for c in cases:
      # All cases in hidden_dir are hidden by construction; split field kept for integrity check
      rows.append((f"{lane.name}/{c[lane.id_field]}", case_hash(c, salt_bytes=salt_bytes)))
  rows.sort(key=lambda r: r[0])
  return rows

def build_manifest(out_dir: str, seed: int, generated: str, hidden_dir: str = HIDDEN_DIR) -> dict:
  salt_bytes = load_salt()
  salt_commitment = hashlib.sha256(salt_bytes).hexdigest()
  rows = collect_hidden(hidden_dir, salt_bytes=salt_bytes)
  out = Path(out_dir)
  (out / "HIDDEN_MANIFEST.sha256").write_text(
    "".join(f"{h}  {name}\n" for name, h in rows), encoding="utf-8")
  meta = {
    "benchmark": "cds-bench (internal fam-med CDS)",
    "hidden_count": len(rows),
    "merkle_root": merkle_root([h for _, h in rows]),
    "seed": seed,
    "generated": generated,
    "algorithm": "salted-SHA256 (per-release secret salt; salt revealed at scoring time)",
    "salt_commitment": salt_commitment,
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
