# cds-bench — a family-medicine CDS benchmark (public sample)

A working benchmark for evaluating AI clinical-decision-support (CDS) systems in US primary care.
This repository publishes a **representative 27-case public sample** plus the full scoring
methodology; the remaining **108 cases are held out** — never published — so models can't train on the
held-out *phrasing*. (This protects the trap lanes most; the guideline facts behind Golden and
Currency are public — see [Limitations](#limitations).)

**Start here:** open [`index.html`](index.html) (the interactive explainer), or browse
[`docs/PUBLIC_CASES.md`](docs/PUBLIC_CASES.md).

- `benchmarks/public/` — the 27 public cases (4 lanes)
- **held-out set** — 108 cases, never published; their existence is verifiable via the committed
  `HIDDEN_MANIFEST.sha256` (per-case SHA-256 + Merkle root). To score against the held-out set,
  see [`SUBMISSION.md`](SUBMISSION.md) (eval-as-a-service).

> A working benchmark, **not** a peer-reviewed publication — see [Limitations](#limitations).

## The benchmark

| Lane | Total | Public | Tests |
|---|---:|---:|---|
| `golden_60.json` | 60 | 12 | core clinical QA (judge-scored vs rubric) |
| `freshness_30.json` | 30 | 6 | stale-guideline detection |
| `hallucination_30.json` | 30 | 6 | clinical-safety traps (false premises, dangerous reassurance, missed-diagnosis vignettes) |
| `halluhard_15.json` | 15 | 3 | multi-axis hallucination (rarity / grounding axis) |

The public/hidden split is a fixed-seed (`20260614`) stratified ~20%/lane carve. The public
cases live in `benchmarks/public/`; the held-out cases are kept private and are not part of this
repository. `scripts/release/lanes.py` is the single source of truth for the lanes and quotas.

## What's published

This repository **is** the public artifact — these are committed at the root:

- `index.html` — interactive explainer (**open this first**)
- `docs/PUBLIC_CASES.md` — the 27 public cases as readable Markdown
- `benchmarks/public/` — the 27 public cases (JSON)
- `release_clean/` — the 4 blinded judge rubrics + scoring harness
- `LICENSE` (CC-BY-NC-ND data / MIT code) · `SUBMISSION.md` (eval-as-a-service)
- `HIDDEN_MANIFEST.sha256` + `.meta.json` — SHA-256 + Merkle root of the 108 held-out cases

To regenerate these (after editing rubrics/cases), or to produce a standalone copy:

```bash
python -m scripts.release.build_explainer                                   # index.html + docs/PUBLIC_CASES.md
python -m scripts.release.build_public --out dist/public --date YYYY-MM-DD  # standalone public tree
```

A maintainer-side cleanliness gate runs at build time against a local vendor denylist (kept private — the comparators are under NDA) and refuses to emit any artifact containing a vendor name or private path. The denylist is not part of this repo, so this is a maintainer build control, not something a clone re-runs; the artifacts published here are already cleaned.

## Other commands

```bash
python -m scripts.release.validate_release          # release invariants (27/108, showcase public, ...)
python -m pytest tests/release/ -q                  # test suite
```

## Layout

- root — `index.html`, `LICENSE`, `SUBMISSION.md`, `HIDDEN_MANIFEST.sha256` + `.meta.json` (the published artifact)
- `benchmarks/public/` — committed; 27 public cases across 4 lane files
- held-out set — 108 cases kept private (not in this repository)
- `scripts/release/` — the pipeline (lanes, manifest, assets, build_public, build_explainer, submit, validate_release)
- `release_clean/` — curated **blinded** methodology artifacts: rubrics + scoring harness
- `tests/release/` — test suite (counts, no-leak, determinism, blinding, gate-catches-violations)
- `docs/EVOLUTION.md` — history of the benchmark + literature it builds on
- `docs/PUBLIC_CASES.md` — the 27 public cases as readable Markdown

## Held-out evaluation

The 108 hidden cases are never published. Submitters get a hidden-set score via the
eval-as-a-service protocol in `SUBMISSION.md` (maintainer runs the model, returns a blinded
scorecard). The published hash manifest lets anyone verify the held-out set was fixed at
release time. Hidden-set scores and comparator rows are maintainer-attested — the manifest proves the question set was fixed at release time, not that the scores are correct.

## Limitations

This is a working benchmark with known limitations — see `docs/EVOLUTION.md` for
the full list. Key ones: single-author curation, small n per lane, LLM-as-judge is a screening
tool, freshness items perish, gold may overlap models' training sources; golden is judge-parametric (no fixed public reference answer); the safety lanes skew pediatric; a structured prompt moves scores ~17–20 points (the bench measures system+prompt, not raw model); hidden-set and comparator scores are maintainer-attested.
