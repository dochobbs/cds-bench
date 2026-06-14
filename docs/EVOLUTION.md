# Evolution of cds-bench

*A brief history of how this family-medicine clinical-decision-support (CDS) benchmark came to be, and the prior work it builds on. The full blow-by-blow field report (≈1,800 lines, Feb–May 2026) lives in the originating cds-eval repository; this is the condensed lineage relevant to the benchmark itself.*

---

## Origin — February 2026: the Golden set

The benchmark began not as a research artifact but as a practicing pediatrician's question: *does an AMBOSS MCP server make a Claude CDS pipeline measurably better, and which tool should I trust at the point of care?* Answering it forced a measurement instrument into existence.

The first lane was **`golden_60`** — 60 bread-and-butter clinical queries (immunizations, dosing, screening, chronic-disease management) drawn from a February triple-source comparison (AMBOSS vs Glass vs web-search-augmented Claude), each scored on a four-dimension rubric: **Clinical Accuracy /30, Completeness /30, Specificity /25, Citation Quality /15**. Two design choices from this period are load-bearing today:

- **Dual-gold scoring** — every candidate scored against two independent reference standards, to avoid one source's house style defining "correct."
- **Golden is a floor, not a discriminator** — once the citation rubric was sane, all serious tools cluster at ~85–90% here. Golden catches gross failures; it doesn't separate good from great. That realization motivated the adversarial lanes.

## March 2026: the adversarial lanes

Two lanes were added specifically because Golden couldn't differentiate tools:

- **`freshness_30`** — queries where a guideline changed in the last ~12 months, each with a hand-curated `{old_answer, new_answer, source}` triple. Scoring asks: did the response cite the *current* guidance or a deprecated version? Anchors are real guideline updates from **ACIP/CDC** immunization schedules, **USPSTF** screening recommendations, **ADA** Standards of Care, **ACC/AHA** cardiovascular guidelines, and **AAP** policy. This lane is where retrieval-augmented pipelines pulled away from parametric models.
- **`hallucination_30`** — adversarial prompts engineered to bait fabricated citations and accept false premises ("cite the AAP 2024 policy statement on…" for a statement that doesn't exist). Scored pass / partial / fail. This turned out to be the single best clinical-safety discriminator the program built: on standard accuracy benchmarks every commercial tool looks similar; on the adversarial set the spread is dramatic and bimodal.

## April 2026: the methodology correction

A physician blind review (10 pediatric queries, sources ranked blind) returned a result the automated judge had completely missed: the prompt-only Claude the judge ranked highest won **zero** queries, because its fluent answers were built on *training-cutoff* guidelines the judge couldn't tell were stale. This produced the program's governing principle — **LLM-as-judge is a screening tool, not ground truth** — consistent with the cautions in the LLM-as-judge literature (Zheng et al., *MT-Bench / Chatbot Arena*). The judge was rebuilt:

- **median-of-3 at temperature 0.3** (a single notorious query had swung 29 points between identical runs at temp 1.0; the spread dropped to 0–6 after the fix),
- **anti-anchoring** (score each dimension independently),
- **date-awareness** (flag answers citing guidelines >12 months stale on freshness-sensitive topics),
- **a strict citation standard** (only verifiable references — DOI/URL/specific title — earn citation points; name-drops do not).

This calibration discipline is shipped with the public release as `calibrate_judge.py` (median-of-3 + per-dimension MAE/agreement vs a frozen reference judge).

## The scoring prompt, and a note on prompt methodology

A compact structured prompt (`ws2`, ~2.8K chars) lifted every model 17–20 points over no prompt and zeroed out hallucination fails on frontier models — establishing that **the rubric and the prompt, not the base model, move the score most**. A later parallel-search variant (`ws5_parallel`: issue several differently-framed queries up front, then synthesize) was directly informed by the *reason-in-parallel-then-summarize* structure of HeavySkill (Wang et al., 2026); its RL-training thesis is not actionable for vendor-API work, but the structural insight ported cleanly.

## May 2026: HalluHard and the hard hallucination lane

**`halluhard_15`** is the program's response to HalluHard (Fan, Delsad, Flammarion & Andriushchenko, 2026), a hard multi-turn hallucination benchmark. We adopted three of its design moves into our schema (`rarity`, `grounding_axis`, `ground_truth_source`, `fail_modes`):

- **Reference-vs-content grounding split** — score two binary axes per case: does the cited source *exist/resolve*, and does the real source actually *support the claim*? The dominant clinical failure mode (correct citation, wrong dose) is only caught by the content axis.
- **Rarity stratification** — niche / moderate / common, because hallucination rate scales with knowledge rarity.
- **Multi-turn / self-conditioning awareness** — the most predictive variable in HalluHard is whether a wrong claim in turn *N* repeats in turn *N+1*; clinical conversations are multi-turn, so single-turn benchmarks under-measure this.

We deliberately position our work as **orthogonal** to HalluHard, not competitive: HalluHard measures *active* hallucination (the model fabricates), whereas our `hallucination_30` measures *passive* hallucination (the model accepts a user-supplied false premise). Both failure modes are real and co-occur; `halluhard_15` is where the two literatures meet.

**`calc_micro_10`** rounds out the suite with deterministic calculator/dosing checks (CHA₂DS₂-VASc, Cockcroft-Gault, CURB-65, Centor, eGFR CKD-EPI 2021, etc.), scored against exact expected behavior rather than by judge.

## Lineage

The benchmark consolidated work that also drew on the broader clinical-LLM-evaluation literature — notably **HealthBench** and **HealthBench Professional** (Arora, Wei et al., OpenAI, 2025), whose physician-authored rubric methodology and professional-tier framing informed how we think about register (parent- vs clinician-facing) and rubric design. Where HealthBench is open and broad, cds-bench is narrow (family-medicine CDS), opinionated about freshness and adversarial safety, and built around a held-out core.

## June 2026: the publishable release

To publish the benchmark without letting models train on it, the suite is split **29 public / 116 held-out** (proportional ~20% per lane, fixed-seed stratified). The release methodology follows established contamination-resistant practice:

- **Canary GUID + do-not-train notice** on every released artifact — the convention introduced by **BIG-bench** (Srivastava et al., 2022), whose canary string lets researchers filter benchmark data out of web-scraped training corpora and post-hoc detect contamination.
- **A held-out test set that is never distributed**, with a published SHA-256 + Merkle-root manifest proving the hidden set was fixed at release time — the same posture as contamination-aware benchmarks like **SWE-bench** (Jimenez et al., 2024) and **GPQA** (Rein et al., 2023), and the benchmark-publication-without-leakage problem framed by Pimpale et al. (2025).
- **Eval-as-a-service** for the hidden set (maintainer runs submitted models, returns a blinded scorecard) so held-out cases, gold answers, and vendor identities never leave maintainer control.

See the design spec (`docs/superpowers/specs/2026-06-04-cds-bench-public-release-design.md`) and `MIGRATION_MANIFEST.md` for details.

---

## References

**ML / benchmark methodology**

- Fan, Z., Delsad, J., Flammarion, N., & Andriushchenko, M. (2026). *HalluHard: A Hard Multi-Turn Hallucination Benchmark.* arXiv:2602.01031. — design basis for `halluhard_15` (reference-vs-content grounding, rarity stratification, multi-turn self-conditioning).
- Wang, et al. (2026). *HeavySkill: Heavy Thinking as the Inner Skill in Agentic Harness.* arXiv:2605.02396. — parallel-reason-then-summarize structure informing `ws5_parallel`.
- Srivastava, A., et al. (2022). *Beyond the Imitation Game: Quantifying and extrapolating the capabilities of language models (BIG-bench).* arXiv:2206.04615. — canary-GUID / do-not-train convention used in the public release.
- Jimenez, C. E., et al. (2024). *SWE-bench: Can Language Models Resolve Real-World GitHub Issues?* arXiv:2310.06770 (ICLR 2024). — held-out, contamination-resistant test-set precedent.
- Rein, D., et al. (2023). *GPQA: A Graduate-Level Google-Proof Q&A Benchmark.* arXiv:2311.12022. — held-out / google-proof benchmark design precedent.
- Pimpale, et al. (2025). *How Can I Publish My LLM Benchmark Without Giving the True Answers Away?* arXiv:2505.18102. — the publish-without-leakage problem this release addresses.
- Zheng, L., et al. (2023). *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena.* arXiv:2306.05685. — LLM-as-judge reliability, motivating median-of-3 + physician review.

**Clinical LLM evaluation**

- Arora, R. K., Wei, J., et al. (OpenAI) (2025). *HealthBench: Evaluating Large Language Models Towards Improved Human Health.* arXiv:2505.08775. — physician-rubric clinical evaluation lineage.
- OpenAI (2025). *HealthBench Professional.* (Technical report.) — professional-tier framing.

**Clinical guideline sources (freshness anchors)**

- CDC/ACIP immunization schedules; U.S. Preventive Services Task Force (USPSTF) recommendations; American Diabetes Association (ADA) *Standards of Care in Diabetes*; ACC/AHA cardiovascular & dyslipidemia guidelines; American Academy of Pediatrics (AAP) policy statements.

*Note: arXiv identifiers for 2026 preprints (HalluHard, HeavySkill) are recorded as cited in the source program's literature review; confirm current versions before external publication.*
