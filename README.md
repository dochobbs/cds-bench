# cds-bench — internal family-medicine CDS benchmark

The authoritative source for a 145-case clinical-decision-support benchmark and the
tooling that publishes a **representative public sample** while holding the bulk of the
questions back so models can't train on them.

> **Private repo.** It contains all 145 cases (public + held-out). The *public* artifact
> is a build output (`dist/public/`, gitignored) that is published separately — only the
> 29-case sample, the methodology, and a hash manifest of the held-out set.

## The benchmark (`benchmarks/internal/`)

| Lane | n | Tests |
|---|---:|---|
| `golden_60.json` | 60 | core clinical QA (judge-scored vs rubric) |
| `freshness_30.json` | 30 | stale-guideline detection |
| `hallucination_30.json` | 30 | adversarial citation-bait traps |
| `halluhard_15.json` | 15 | multi-axis hallucination (rarity / grounding axis) |
| `calc_micro_10.json` | 10 | calculator / dosing correctness |

Each case carries `split: "public" | "hidden"` — **29 public / 116 hidden**, a fixed-seed
(`20260614`) stratified per-lane carve (~20%/lane). `scripts/release/lanes.py` is the single
source of truth for the lanes and quotas.

## Building the public release

```bash
python -m scripts.release.build_public --out dist/public --date YYYY-MM-DD
```

Emits `dist/public/` containing: the 29 public cases (canary-stamped), the 4 blinded judge
rubrics, the scoring harness, `LICENSE` (CC-BY-NC-ND data / MIT code), `CANARY`,
`SUBMISSION.md`, and `HIDDEN_MANIFEST.sha256` + `.meta.json` (per-case SHA-256 + Merkle root
of the 116 held-out cases). A cleanliness gate refuses to ship any artifact containing a
vendor name or private path. That `dist/public/` tree is what gets pushed to the public repo.

## Other commands

```bash
python -m scripts.release.validate_release          # release invariants (29/116, showcase public, …)
python -m scripts.release.find_scored <CASE_ID>     # locate scored runs to curate a worked example
python -m pytest tests/release/ -q                  # 59 tests
```

## Layout

- `scripts/release/` — the pipeline (lanes, split_selector, manifest, canary, assets, build_public, submit, validate_release, find_scored)
- `release_clean/` — curated **blinded** methodology artifacts shipped into the public tree (vendor names redacted, no private paths)
- `tests/release/` — 59 tests (counts, no-leak, determinism, blinding, gate-catches-violations)
- `docs/EVOLUTION.md` — brief history of the benchmark + literature it builds on (HalluHard, BIG-bench canary, HealthBench, …)
- `docs/superpowers/` — the design spec + implementation plan
- `MIGRATION_MANIFEST.md` — how this repo was extracted from the cds-eval monorepo

## Held-out evaluation

The 116 hidden cases are never published. Submitters get a hidden-set score via the
eval-as-a-service protocol in `SUBMISSION.md` (maintainer runs the model, returns a blinded
scorecard). The published hash manifest lets anyone verify the held-out set was fixed at
release time.
