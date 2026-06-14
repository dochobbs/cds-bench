# scripts/release/build_public.py
"""Assemble the public cds-bench repo tree. Emits ONLY what is listed here.

Run: python -m scripts.release.build_public --out ../cds-bench --seed 20260614 --date 2026-06-14
"""
from __future__ import annotations
import argparse, json, re, shutil
from pathlib import Path
from scripts.release.lanes import LANES, PUBLIC_DIR, HIDDEN_DIR, WORKED_DIR
from scripts.release import assets
from scripts.release.manifest import build_manifest
from scripts.release.build_explainer import load_public, render_html, render_markdown

# MIT-shipped methodology artifacts (spec §8): reference scorer, prompt template, calibration runner
RUBRIC_CLEAN_DIR = "release_clean/rubrics"
SCORING_SRCS = [
  "release_clean/scoring/cds_ws2.txt",   # prompt template (already clean)
  "release_clean/scoring/judge.py",      # blinded copy
  "release_clean/scoring/calibrate_judge.py",
]

# Path tokens are always enforced (no word boundaries — path fragments have none).
# Built dynamically so the literals don't appear verbatim in published source.
_PATH_TOKENS = ("/" + "users" + "/", "/tmp/" + "gem" + "venv")


def _load_vendor_tokens(path: str = "release_clean/vendor_denylist.txt") -> list[str]:
  """Load vendor/brand tokens from the gitignored maintainer denylist.

  Returns an empty list when the file is absent (public clone — path-only gating applies).
  """
  p = Path(path)
  if not p.exists():
    return []
  return [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _build_vendor_re(tokens: list[str]) -> re.Pattern | None:
  """Build a regex matching vendor tokens. Multi-word tokens match as substrings;
  single-word tokens use word boundaries (avoids token-in-superstring false positives)."""
  if not tokens:
    return None
  single = [re.escape(t) for t in tokens if " " not in t]
  multi = [re.escape(t) for t in tokens if " " in t]
  parts = []
  if single:
    parts.append(r"\b(" + "|".join(single) + r")\b")
  if multi:
    parts.append("(" + "|".join(multi) + ")")
  return re.compile("|".join(parts), re.IGNORECASE) if parts else None


# Build at module load time from the denylist file (empty list if absent)
_VENDOR_TOKENS = _load_vendor_tokens()
_VENDOR_NAME_RE = _build_vendor_re(_VENDOR_TOKENS)


def _assert_clean(text: str, label: str) -> None:
  """Refuse to ship any artifact leaking a vendor name or a private path."""
  vendor_hits: list[str] = []
  if _VENDOR_NAME_RE is not None:
    vendor_hits = sorted({m.group(0).lower() for m in _VENDOR_NAME_RE.finditer(text)})
  path_hits = sorted({t for t in _PATH_TOKENS if t in text.lower()})
  hits = vendor_hits + path_hits
  if hits:
    raise ValueError(f"refusing to ship {label}: forbidden tokens {hits} (vendor name or private path)")

def _write_json(path: Path, obj) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def _emit_public_case(c: dict) -> dict:
  """Return a copy of the public case with release-management fields stripped."""
  out = {k: v for k, v in c.items() if k not in ("split", "validated")}
  return out

def build_public(out_dir: str, seed: int, generated: str,
                 public_dir: str = PUBLIC_DIR, hidden_dir: str = HIDDEN_DIR,
                 worked_dir: str = WORKED_DIR) -> dict:
  out = Path(out_dir)
  if out.exists():
    contents = {p.name for p in out.iterdir()}
    markers = {"public", "rubrics", "scoring", "LICENSE", "SUBMISSION.md",
               "README.md", "HIDDEN_MANIFEST.sha256", "HIDDEN_MANIFEST.meta.json"}
    if contents and not (markers & contents):
      raise ValueError(
        f"Refusing to rmtree {out}: exists, non-empty, and has no cds-bench markers — "
        "pass a dedicated output path.")
    shutil.rmtree(out)
  out.mkdir(parents=True)

  counts = {}
  for lane in LANES.values():
    cases = json.load(open(Path(public_dir) / lane.filename))
    # All cases in public_dir are public by construction; filter by split field for safety
    public = [c for c in cases if c.get("split") == "public"]
    counts[lane.name] = len(public)
    for c in public:
      emitted = _emit_public_case(c)
      emitted_json = json.dumps(emitted, indent=2, ensure_ascii=False)
      _assert_clean(emitted_json, f"public/{lane.name}/{c[lane.id_field]}.json")
      _write_json(out / "public" / lane.name / f"{c[lane.id_field]}.json", emitted)
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
  (out / "SUBMISSION.md").write_text(assets.SUBMISSION, encoding="utf-8")

  # worked-example overlays (optional; curated by hand into benchmarks/internal/worked/)
  (out / "worked_examples").mkdir(parents=True, exist_ok=True)
  wd = Path(worked_dir)
  if wd.exists():
    for f in sorted(wd.glob("*.json")):
      _assert_clean(f.read_text(encoding="utf-8"), f"worked_examples/{f.name}")  # whole overlay must be blinded
      shutil.copy(f, out / "worked_examples" / f.name)

  # hidden manifest
  build_manifest(str(out), seed=seed, generated=generated, hidden_dir=hidden_dir)

  # interactive explainer + readable markdown (shared renderers — no duplicated logic)
  pub = load_public(public_dir)
  rubrics_for_render: dict[str, str] = {}
  for lane_name, lane in LANES.items():
    if lane.judge_rubric:
      rubric_path = out / "rubrics" / f"{lane_name}.txt"
      if rubric_path.exists():
        rubrics_for_render[lane_name] = rubric_path.read_text(encoding="utf-8")
  (out / "index.html").write_text(render_html(pub, rubrics=rubrics_for_render), encoding="utf-8")
  (out / "PUBLIC_CASES.md").write_text(render_markdown(pub), encoding="utf-8")

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
