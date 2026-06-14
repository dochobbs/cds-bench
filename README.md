# cds-bench — internal family-medicine CDS benchmark

**This repository is the private source of the benchmark (all 135 cases + tooling). The public sample is the build artifact in `dist/public/` — that is what gets published.**

This is a working internal benchmark (not a peer-reviewed publication) for evaluating
AI clinical-decision-support systems in US primary care. It publishes a
**representative public sample** while holding most cases back so models
can't directly train on the test set.

> **Private repo.** It contains all 135 cases (public + held-out). The *public* artifact
> is a build output (`dist/public/`, gitignored) that is published separately — only the
> 27-case sample, the methodology, and a hash manifest of the held-out set.

## The benchmark (`benchmarks/internal/`)

| Lane | n | Tests |
|---|---:|---|
| `golden_60.json` | 60 | core clinical QA (judge-scored vs rubric) |
| `freshness_30.json` | 30 | stale-guideline detection |
| `hallucination_30.json` | 30 | clinical-safety traps (false premises, dangerous reassurance, missed-diagnosis vignettes) |
| `halluhard_15.json` | 15 | multi-axis hallucination (rarity / grounding axis) |

Each case carries `split: "public" | "hidden"` — **27 public / 108 hidden**, a fixed-seed
(`20260614`) stratified per-lane carve (~20%/lane). `scripts/release/lanes.py` is the single
source of truth for the lanes and quotas.

## Building the public release

```bash
python -m scripts.release.build_public --out dist/public --date YYYY-MM-DD
```

Emits `dist/public/` containing: the 27 public cases, the 4 blinded judge
rubrics, the scoring harness, `LICENSE` (CC-BY-NC-ND data / MIT code),
`SUBMISSION.md`, and `HIDDEN_MANIFEST.sha256` + `.meta.json` (per-case SHA-256 + Merkle root
of the 108 held-out cases). A cleanliness gate refuses to ship any artifact containing a
vendor name or private path. That `dist/public/` tree is what gets pushed to the public repo.

## Other commands

```bash
python -m scripts.release.validate_release          # release invariants (27/108, showcase public, ...)
python -m scripts.release.find_scored <CASE_ID>     # locate scored runs to curate a worked example
python -m pytest tests/release/ -q                  # test suite
```

## Layout

- `scripts/release/` — the pipeline (lanes, split_selector, manifest, assets, build_public, submit, validate_release, find_scored)
- `release_clean/` — curated **blinded** methodology artifacts shipped into the public tree (vendor names redacted, no private paths)
- `tests/release/` — test suite (counts, no-leak, determinism, blinding, gate-catches-violations)
- `docs/EVOLUTION.md` — history of the benchmark + literature it builds on
- `docs/superpowers/` — design specs
- `MIGRATION_MANIFEST.md` — how this repo was extracted from the cds-eval monorepo

## Held-out evaluation

The 108 hidden cases are never published. Submitters get a hidden-set score via the
eval-as-a-service protocol in `SUBMISSION.md` (maintainer runs the model, returns a blinded
scorecard). The published hash manifest lets anyone verify the held-out set was fixed at
release time.

## Limitations

This is a working internal benchmark with known limitations — see `docs/EVOLUTION.md` for
the full list. Key ones: single-author curation, small n per lane, LLM-as-judge is a screening
tool, freshness items perish, gold may overlap models' training sources.
