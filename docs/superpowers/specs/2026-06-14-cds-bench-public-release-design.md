# Internal CDS Bench — Public Release Design Spec

**Date:** 2026-06-14
**Status:** Approved for planning (brainstorming complete)
**Owner:** Michael (Doc Hobbs)
**Topic:** Release the internal family-medicine CDS evaluation benchmark as a methods paper + companion public repo, exposing a representative sample and full methodology while holding the bulk of the questions in a private, contamination-protected test set.

> **Scope note:** This concerns the **internal fam-med CDS bench** at `benchmarks/internal/` only. It is **not** PEARL (the pediatric benchmark), which has its own separate publication track (`2026-06-04-pearl-publication-bench-design.md`).

---

## 1. Goal

Publish the internal CDS bench in a form that simultaneously:

1. **Protects against training contamination** — the majority of questions are never released, so models can't train on them, and leakage is detectable after the fact.
2. **Demonstrates the methodology** — the full scoring instrument (rubrics, judge protocol, code) is open and reproducible.
3. **Shares a meaningful sample for review** — a representative, per-lane-proportional public sample lets reviewers and the community inspect the actual questions and reproduce our scores.

The end state is a **benchmark methods paper + companion public GitHub repo**, with a **private held-out test set** (the SWE-bench / GPQA pattern: open methodology, open sample, protected test data).

## 2. Relationship to prior planning

This design is the **operational successor to `docs/PUBLISHABILITY_AUDIT.md`** (2026-05-03). The audit established the publishability *tiers* for project artifacts in the abstract and recommended releasing `freshness_30` and `hallucination_30` **in full** as open datasets (§4.2, §2.5).

**This design revises that recommendation.** To meet Goal #1, we hold back ~80% of every lane — including freshness and hallucination — and release only a proportional sample. The audit's tier judgments (what's PUBLIC vs PRIVATE vs DO-NOT-PUBLISH) and its vendor-anonymization guidance still govern; only the "release the full adversarial sets" call is superseded.

## 3. The bench (current state)

`benchmarks/internal/` — 5 lanes, 145 cases, flat JSON files:

| Lane | File | n | Schema (top-level keys) | What it tests |
|---|---|---:|---|---|
| Golden | `golden_60.json` | 60 | `search_id`, `category`, `amboss_query`, `original_query` | Core clinical QA, judge-scored vs rubric |
| Freshness | `freshness_30.json` | 30 | `id`, `query`, `old_answer`, `new_answer`, `source`, `category` | Stale-guideline detection (hand-curated old/new pairs) |
| Hallucination | `hallucination_30.json` | 30 | `id`, `query`, `trap`, `category`, `expected` | Adversarial citation-bait traps |
| HalluHard | `halluhard_15.json` | 15 | `id`, `query`, `trap`, `category`, `expected`, `rarity`, `grounding_axis`, `ground_truth_source`, `fail_modes` | Harder multi-axis hallucination |
| Calc | `calc_micro_10.json` | 10 | `id`, `calculator`, `query`, `inputs_in_query`, `expected_behavior` | Calculator / dosing correctness |

Scoring is **judge-based** (rubrics + LLM-as-judge), not embedded in the case files. The rubrics, judge prompts, and calibration protocol live in `eval/` and are documented in the audit (§2.3, §4.3).

## 4. Decisions locked (from brainstorming)

| Decision | Choice |
|---|---|
| Release venue | **Academic paper + companion public repo**; held-out set stays private |
| Split construction | **Proportional per-lane, ~20% public** (stratified random, fixed seed, hand-audited) |
| Public sample depth | **5 fully worked illustrative cases** (one per lane) + remaining 24 as **query + rubric + gold answer key** |
| Held-out guardrails | **Canary GUID + do-not-train notice**, **published SHA-256 hashes + Merkle root**, **eval-as-a-service** (protocol, not platform) |
| *Not* chosen | Gated request-access to the hidden set — hidden cases are **never distributed**, even under agreement; the only path to hidden-set scores is eval-as-a-service |
| Methodology openness | Scoring code, judge prompts, rubric schema, calibration protocol, ws2 prompt template — **all open** (carried from audit, tier PUBLIC) |
| Vendor handling | **Blinded-comparator design** (audit §2.2); name the openly-used tool if desired, blind commercial comparators; per-vendor itemized error lists stay private |
| Data license | **CC-BY-NC-ND** for the public sample; **MIT** for the code |
| Public repo target | **New separate public repo** `cds-bench` (github.com/dochobbs/cds-bench); build tooling stays in `cds-eval` and emits the public tree. Mirrors the PEARL → own-repo separation; keeps `_PRIVATE_DECODER.md` / hidden cases out of the public artifact |
| Worked-example showcase | **Adult fam-med rebalanced:** `G52` (tirzepatide titration), `F19` (HTN threshold), `H11` (fabricated USPSTF lung-CT), `HH08` (ADA HbA1c, content axis), `C01` (CHA₂DS₂-VASc). Alt for halluhard: `HH06` (fabricated PEDS-VITAL-7) if the reference-axis demo is preferred over adult-consistency |

## 5. The split

Stratified-random sample within each lane, with a **fixed seed** logged for auditability, then hand-audited to guarantee category coverage and to remove any public case that is near-duplicate of a hidden case.

| Lane | Total | Public | Hidden |
|---|---:|---:|---:|
| golden_60 | 60 | 12 | 48 |
| freshness_30 | 30 | 6 | 24 |
| hallucination_30 | 30 | 6 | 24 |
| halluhard_15 | 15 | 3 | 12 |
| calc_micro_10 | 10 | 2 | 8 |
| **Total** | **145** | **29** | **116** |

A `split: "public" | "hidden"` field is written onto every case (mirrors PEARL's `scripts/pearl/apply_split.py` pattern). The carve is idempotent and re-runnable.

## 6. What the public 29 expose

- **5 fully worked illustrative cases — one per lane** — shown end-to-end in the paper and the repo: `query → rubric → gold → example model transcript → judge score`. This makes each lane's scoring mechanism concrete. **Reuses existing scored runs** from `results/internal/` (low authoring cost). Comparator transcripts in worked examples are blinded per §4 vendor handling.
  - **Selected (adult fam-med showcase):** `G52` tirzepatide dose-titration (golden), `F19` HTN diagnostic threshold (freshness), `H11` fabricated USPSTF lung-CT recommendation (hallucination), `HH08` ADA HbA1c target / content axis (halluhard), `C01` CHA₂DS₂-VASc (calc).
  - Spread of failure modes covered: dosing/titration, guideline currency, fabricated-premise refusal, content-grounding, deterministic calculation.
  - **Open swap:** `HH08 → HH06` (fabricated PEDS-VITAL-7) trades adult-consistency for a more vivid *reference-axis* demonstration; confirm during build.
- **Remaining 24 ship as `query + rubric + gold answer key`** (no model transcripts). Sufficient for reviewers to reproduce our exact scores; standard benchmark dev-set depth.

Rationale: the public 29 are **sacrificial by design** — once released they are assumed contaminated. Full transparency on them maximizes review value and reproducibility. All contamination protection lives on the hidden 116.

## 7. Held-out guardrails

1. **Canary GUID + do-not-train notice.** A unique canary string (BIG-bench style) and an explicit no-train / no-redistribute statement embedded in every released artifact — the paper, the repo README, and each public case file. Enables later probing of models for memorization of the canary.
2. **Published hashes.** SHA-256 of each hidden case (over a canonicalized JSON serialization) plus a **Merkle root**, committed to the public repo as `HIDDEN_MANIFEST.sha256` at release. Proves the held-out set existed and was frozen on the release date without revealing content; enables future contamination audits ("here is the hash of the case the model answered verbatim").
3. **Eval-as-a-service — protocol, not platform.** A documented submission process (`SUBMISSION.md`): a submitter provides a model endpoint or pre-generated transcripts; we run them through the hidden harness and return a **blinded scorecard**. Hidden cases never leave our control. **No web service is built** — this is a manual/scripted operator workflow (YAGNI).

The hidden set is **never distributed**. There is deliberately no gated-access path; eval-as-a-service is the sole route to hidden-set numbers.

## 8. Methodology shipped open

All tier-PUBLIC per the audit; clean of project-specific identifiers before release:

- Scoring runner(s) for each lane.
- Judge prompts and the **rubric schema**.
- The **judge-calibration protocol**: median-of-3, temperature 0.3, anti-anchoring instructions, date-awareness, calibration set sampled across the score range, MAE + Pearson r + parse-fail tracked per dimension (audit §2.3). Reference runner: `eval/runners/cheap_judge_smoke.py`.
- The **ws2 prompt template** (`eval/prompts/cds_ws2.txt`) — structure, length target, citation discipline, freshness instruction.

Reproducibility bar: anyone can score the public 29 with the released code and reproduce our reported numbers on that sample.

## 9. Components (single-purpose units)

Each unit has one job, a defined interface, and is independently testable.

| Unit | Responsibility | Input → Output |
|---|---|---|
| `split_selector` | Choose the public 29 via stratified-random + fixed seed; write `split` field | lane files + seed → annotated lane files + selection log |
| `canary_injector` | Stamp canary GUID + do-not-train notice onto released artifacts | case files + canary → stamped files |
| `hidden_manifest` | Canonicalize + SHA-256 every hidden case; emit per-case hashes + Merkle root | hidden case files → `HIDDEN_MANIFEST.sha256` |
| `public_release_builder` | Assemble the public repo tree: 29 cases (5 worked + 24 query/rubric/gold), rubrics, scoring code, README, LICENSE, manifest | annotated bench + scored runs → `cds-bench/` repo tree |
| `submission_harness` | Eval-as-a-service: run a submitter's model/transcripts against the hidden set, emit a blinded scorecard | submitter endpoint/transcripts → scorecard |
| `paper` | The methods paper (Markdown/LaTeX source) | design + results → manuscript |

Boundaries: `split_selector` is the only unit that decides public vs hidden; everything downstream reads the `split` field. `hidden_manifest` and `public_release_builder` are independent (hashes don't depend on the public build and vice versa). `submission_harness` reuses the existing lane scorers unchanged — it only wraps them with a hidden-set loader and blinded output.

## 10. Repo & paper shape

**Repo (`cds-bench/` — new standalone public repo, `github.com/dochobbs/cds-bench`):** built by `public_release_builder` (§9), which runs inside `cds-eval` and writes into a checkout of this separate repo. Nothing from `cds-eval`'s private tree is copied except what the builder explicitly emits.
```
public/
  golden/        # 12 cases (1 worked)
  freshness/     # 6 cases (1 worked)
  hallucination/ # 6 cases (1 worked)
  halluhard/     # 3 cases (1 worked)
  calc/          # 2 cases (1 worked)
rubrics/         # rubric schema + per-lane rubrics
scoring/         # lane runners + judge prompts + calibration runner
worked_examples/ # 5 end-to-end (transcript + judge score), comparators blinded
HIDDEN_MANIFEST.sha256
CANARY
SUBMISSION.md    # eval-as-a-service protocol
LICENSE          # CC-BY-NC-ND (data) + MIT (code), clearly scoped
README.md        # methodology overview + do-not-train notice
```

**Paper outline:**
1. Motivation — the audit's headline findings as the "why this instrument" case: rubric > model, prompt > model, freshness needs retrieval, hallucination is bimodal.
2. The instrument — 5 lanes, case schema, dual-rubric where applicable, judge-calibration protocol.
3. Public sample — the 29, with the 5 worked examples illustrating per-lane scoring.
4. Held-out protocol — split rationale, canary, hashes/Merkle root, eval-as-a-service.
5. Results — blinded cross-system leaderboard on the full bench.
6. Limitations — sample size, single-site authorship, judge-family dependence, what we did not measure.

## 11. Non-goals

- Releasing the hidden set under any agreement (out of scope by design — eval-as-a-service only).
- Building a hosted eval-as-a-service web platform (protocol/manual workflow only for v1).
- PEARL release (separate track).
- New benchmark lanes or new prompt variants — this packages the existing bench, it does not grow it.
- Re-running the full leaderboard from scratch unless release requires fresh comparator numbers.

## 12. Open items (resolve during implementation)

1. **Worked-example confirmation** — selection is locked to the §6 showcase (G52/F19/H11/HH08/C01); remaining call is the `HH08 → HH06` swap, and confirming each pick has a clean existing scored run before reuse.
2. **Comparator naming in the paper** — confirm whether the openly-used tool is named or also blinded; confirm the Vendor A/B mapping is kept only in the gitignored decoder.
3. **License text exactness** — final CC-BY-NC-ND data clause wording + the explicit no-train sentence; confirm code MIT is acceptable.
4. **Canonicalization rule for hashing** — exact JSON serialization (key order, whitespace, unicode) so hashes are reproducible by third parties.
5. **Venue** — preprint (arXiv) first vs. direct submission; affects formatting only.

## 13. Sequencing / milestones

- **M1 — Split:** implement `split_selector`, carve 29/116, hand-audit, commit annotated bench + selection log.
- **M2 — Hidden manifest:** implement `hidden_manifest`, produce `HIDDEN_MANIFEST.sha256` + Merkle root.
- **M3 — Canary + license:** implement `canary_injector`; finalize LICENSE + do-not-train notice.
- **M4 — Public release build:** implement `public_release_builder`; assemble `cds-bench/` tree; pick + render the 5 worked examples (blinded).
- **M5 — Submission harness:** implement `submission_harness` + write `SUBMISSION.md`.
- **M6 — Paper:** draft the methods paper against the released sample + blinded leaderboard.
