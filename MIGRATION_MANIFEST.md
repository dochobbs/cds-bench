# Migration Manifest — cds-bench extracted from cds-eval

**Date:** 2026-06-14
**Why:** Silo the family-medicine CDS public-release work into its own repo, fully
independent of the cds-eval research monorepo and the in-flight `feature/pearl-publication-bench`
branch it was developed on. PEARL never touched `benchmarks/internal/`, so the extraction is clean.

**Source:** `/Users/dochobbs/Downloads/Consult/cds-eval` @ branch `feature/cds-bench-public-release`
(release work = 28 commits `bb7f23e`…`3110375`, all touching only release-scoped paths).

## What was copied (source → dest)

| Source (cds-eval) | Dest (cds-bench) |
|---|---|
| `scripts/release/` | `scripts/release/` |
| `tests/release/` | `tests/release/` |
| `release_clean/` | `release_clean/` |
| `benchmarks/internal/*.json` (split applied) | `benchmarks/internal/` |
| `eval/prompts/cds_ws2.txt` | `release_clean/scoring/cds_ws2.txt` *(relocated)* |
| `docs/superpowers/specs/2026-06-04-…` , `…/2026-06-14-…design.md` | `docs/superpowers/specs/` |
| `docs/superpowers/plans/2026-06-14-…` | `docs/superpowers/plans/` |

Nothing else from cds-eval was copied. No PEARL files, no `_PRIVATE_DECODER.md`, no vendor
handoffs, no `eval/` runners/evaluators (the only `eval/` dependency — `cds_ws2.txt` — was
relocated into `release_clean/scoring/`).

## Decoupling fixes applied (so the repo has zero `eval/` dependency)

1. `scripts/release/build_public.py` — `SCORING_SRCS[0]`: `eval/prompts/cds_ws2.txt` → `release_clean/scoring/cds_ws2.txt`.
2. `scripts/release/lanes.py` — each lane's `judge_rubric` repointed from `eval/prompts/*judge*.txt`
   to the curated blinded `release_clean/rubrics/<lane>.txt` that the builder actually ships
   (previously the eval/ paths were only used as truthy flags after Task 14).

## Verification (in this repo, against cds-eval's interpreter)

- `grep -rnE "eval/prompts|eval/evaluators|eval/runners" scripts/ tests/` → **none** (fully decoupled).
- `python -m pytest tests/release/ -q` → **59 passed**.
- `python -m scripts.release.validate_release` → **ALL GREEN** (29 public / 116 hidden).
- `build_public --out dist/public` → 29 cases; `dist/public/{scoring,rubrics}` grep for vendor/private-path tokens → **clean**.

## Notes / TODO for full standalone operation

- Create a dedicated venv: `python -m venv .venv && .venv/bin/pip install pytest` (only dev dep; runtime is stdlib-only).
- `scripts/release/find_scored.py` reads `results/internal/` (a cds-eval dir not copied) — it's a curation helper that simply returns nothing here; wire it to your scored-run location when curating worked examples.
- The cds-eval branch `feature/cds-bench-public-release` is left intact as the source of record; decide separately whether to retire it.
- Publish target: push `dist/public/` to the public `cds-bench` GitHub repo (the held-out cases stay here, private).
