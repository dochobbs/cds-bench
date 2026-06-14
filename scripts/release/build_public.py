# scripts/release/build_public.py
"""Assemble the public cds-bench repo tree. Emits ONLY what is listed here.

Run: python -m scripts.release.build_public --out ../cds-bench --seed 20260614 --date 2026-06-14
"""
from __future__ import annotations
import argparse, json, re, shutil
from pathlib import Path
from scripts.release.lanes import LANES, BENCH_DIR, WORKED_DIR
from scripts.release.canary import stamp_case
from scripts.release import assets
from scripts.release.manifest import build_manifest

# MIT-shipped methodology artifacts (spec §8): reference scorer, prompt template, calibration runner
RUBRIC_CLEAN_DIR = "release_clean/rubrics"
SCORING_SRCS = [
  "release_clean/scoring/cds_ws2.txt",   # prompt template (already clean)
  "release_clean/scoring/judge.py",      # blinded copy
  "release_clean/scoring/calibrate_judge.py",
]

# Vendor names: word-boundary match (avoids elation⊂correlation, wren⊂wrench, etc.)
_VENDOR_NAME_RE = re.compile(r"\b(amboss|openevidence|lisa|glass|elation|wren)\b", re.IGNORECASE)
_PATH_TOKENS = ("/users/", "/tmp/gemvenv")  # substrings: path fragments have no word boundaries

def _assert_clean(text: str, label: str) -> None:
  """Refuse to ship any artifact leaking a vendor name or a private path."""
  vendor_hits = sorted({m.group(0).lower() for m in _VENDOR_NAME_RE.finditer(text)})
  path_hits = sorted({t for t in _PATH_TOKENS if t in text.lower()})
  hits = vendor_hits + path_hits
  if hits:
    raise ValueError(f"refusing to ship {label}: forbidden tokens {hits} (vendor name or private path)")

def _write_json(path: Path, obj) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def build_public(out_dir: str, seed: int, generated: str, bench_dir: str = BENCH_DIR, worked_dir: str = WORKED_DIR) -> dict:
  out = Path(out_dir)
  if out.exists():
    contents = {p.name for p in out.iterdir()}
    markers = {"public", "rubrics", "scoring", "LICENSE", "SUBMISSION.md", "CANARY",
               "README.md", "HIDDEN_MANIFEST.sha256", "HIDDEN_MANIFEST.meta.json"}
    if contents and not (markers & contents):
      raise ValueError(
        f"Refusing to rmtree {out}: exists, non-empty, and has no cds-bench markers — "
        "pass a dedicated output path.")
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
      src = Path(RUBRIC_CLEAN_DIR) / f"{lane.name}.txt"
      text = src.read_text(encoding="utf-8")
      _assert_clean(text, f"rubrics/{lane.name}.txt")
      dst = out / "rubrics" / f"{lane.name}.txt"
      dst.parent.mkdir(parents=True, exist_ok=True)
      dst.write_text(text, encoding="utf-8")

  # scoring harness + methodology artifacts (MIT)
  (out / "scoring").mkdir(parents=True, exist_ok=True)
  for src in SCORING_SRCS:
    text = Path(src).read_text(encoding="utf-8")
    _assert_clean(text, f"scoring/{Path(src).name}")
    (out / "scoring" / Path(src).name).write_text(text, encoding="utf-8")

  # static assets
  (out / "LICENSE").write_text(assets.LICENSE, encoding="utf-8")
  (out / "README.md").write_text(assets.README, encoding="utf-8")
  (out / "CANARY").write_text(assets.CANARY_FILE, encoding="utf-8")
  (out / "SUBMISSION.md").write_text(assets.SUBMISSION, encoding="utf-8")

  # worked-example overlays (optional; curated by hand — see find_scored.py)
  (out / "worked_examples").mkdir(parents=True, exist_ok=True)
  wd = Path(worked_dir)
  if wd.exists():
    for f in sorted(wd.glob("*.json")):
      _assert_clean(f.read_text(encoding="utf-8"), f"worked_examples/{f.name}")  # whole overlay must be blinded
      shutil.copy(f, out / "worked_examples" / f.name)

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
