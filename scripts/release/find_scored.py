# scripts/release/find_scored.py
"""Locate scored runs mentioning a showcase id, to curate worked-example overlays.

Run: python -m scripts.release.find_scored F19
Prints candidate result files that reference the id (newest first).
"""
from __future__ import annotations
import glob, os, re, sys

def find(case_id: str, root: str = "results/internal") -> list[str]:
  hits = []
  for f in glob.glob(f"{root}/**/*.json", recursive=True):
    try:
      with open(f, encoding="utf-8") as fh:
        if re.search(rf"\b{re.escape(case_id)}\b", fh.read()):
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
