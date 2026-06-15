# Evolution of cds-bench

*Postmarks in the development of this family-medicine CDS working benchmark (Feb–Jun 2026), and the prior work it builds on. The full field report lives in the originating internal evaluation program.*

---

## Timeline

- **Feb 2026 — Golden set.** `golden_60`: 60 bread-and-butter clinical queries scored on a four-dimension rubric (Clinical Accuracy /30, Completeness /30, Specificity /25, Citation Quality /15), scored by an LLM judge against a curated rubric (the judge defers to current US guidelines where the reference is stale — see Limitations). Golden serves as a floor — serious tools cluster at ~75–90% — so adversarial lanes were added to actually separate them.

- **March 2026 — adversarial lanes.**
  - `freshness_30` (**guideline currency**): queries where the current operative guideline differs from an outdated answer — the change may be months or years old, so this lane tests *currency*, not recency. Anchored to real updates from **ACIP/CDC** (incl. the 2026 schedule litigation and stay), **USPSTF**, **ADA**, **ACC/AHA**, and **AAP**. Separates retrieval-augmented from parametric systems.
  - `hallucination_30`: clinical-safety traps — false premises, dangerous reassurance, and missed-diagnosis vignettes the model must catch (PASS / PARTIAL / FAIL). Designed as the clinical-safety discriminator (n=30; per-lane numbers are noisy — see Limitations). **Orthogonal to HalluHard**: HalluHard tests active fabrication; this lane tests accepting unsafe premises / missing red flags.

- **April 2026 — LLM-as-judge protocol evolved.** A physician blind review reshaped the judging approach: the judge moved to **median-of-3 (temp 0.3) + anti-anchoring + date-awareness + verifiable-only citations**. A physician blind-review **calibrated** the judge — the shipped scorer is the automated LLM judge (**Claude Sonnet 4** (`claude-sonnet-4-20250514`)), with physician review used for calibration, **not** as a per-run arbiter (LLM-as-judge as a screening tool, per Zheng et al.). This calibration discipline ships as `calibrate_judge.py`. Note: the physician review was a qualitative blind-review that shaped the judge protocol; formal physician-agreement statistics (MAE / Pearson r / n) are not published in this sample.

- **Prompt methodology.** In our runs (a single internal run, not a controlled multi-seed study), the `ws2` prompt (~2.8K chars) added roughly **17–20 Core points** over no prompt and reduced hallucination failures on frontier models. Because the prompt moves scores this much, the bench measures the **system+prompt configuration**, not raw model capability — see Limitations (construct validity). Both `ws2` and the parallel-search `ws5` ship under `release_clean/scoring/` so you can judge the scaffolding directly.

- **May 2026 — hard hallucination lane.** `halluhard_15`, derived from **HalluHard** (Fan et al., 2026). Adopted into the schema (`rarity`, `grounding_axis`, `ground_truth_source`, `fail_modes`):
  - **reference-vs-content grounding split** — does the cited source exist, and does it actually support the claim? (Correct-cite/wrong-dose is only caught by the content axis.)
  - **rarity stratification** — niche / moderate / common.
  - **multi-turn self-conditioning** — whether a wrong claim repeats across turns.
  Positioned **orthogonal** to `hallucination_30`: HalluHard measures *active* hallucination (model fabricates); ours measures *passive* hallucination (accepting a false premise / missing a red flag).

- **Lineage.** Register (parent- vs clinician-facing) and rubric design were informed by **HealthBench** and **HealthBench Professional** (Arora, Wei et al., OpenAI, 2025). cds-bench is the narrow, freshness- and safety-opinionated, held-out counterpart.

- **June 2026 — working release.** Split **27 public / 108 held-out** (proportional ~20%/lane, fixed-seed stratified, 4 lanes; calc lane removed). This is a working benchmark, not a formally peer-reviewed publication. salted SHA-256 + Merkle-root manifest of the held-out set (salt revealed at scoring); eval-as-a-service for hidden-set scoring. The public/hidden split was a fixed-seed (20260614) stratified ~20%/lane carve, now frozen as the `benchmarks/public/` and `benchmarks/hidden/` directories (previously encoded by a `split` field in a single mixed-case file; `split_selector.py` generated it but is no longer needed).

---

## Limitations

- Single-author authored and curated (LLM-assisted); no external clinician validation cohort yet.
- Small n per lane (3–12 public; 12–60 total) — per-lane numbers are noisy.
- LLM-as-judge is a screening tool, not ground truth; risk of same-model-family grading bias.
- Freshness items perish and require periodic re-validation (per-case `validated` dates in the source data).
- Gold may overlap models' training sources (circularity) — guideline knowledge is public and likely in any model's training data.
- Not IRB-reviewed, not prospective, no patient-outcome validation.
- Golden is judge-parametric: the public sample ships no fixed reference answer, and the rubric defers to current guidelines, so Golden scores depend on the judge model and are not independently reproducible from this repo alone.
- Pediatric skew: the clinical-safety lanes over-weight peds (author is a pediatrician); not a representative US primary-care case mix.
- Construct validity: a structured prompt moves scores ~17–20 Core points, so results reflect the system+prompt configuration, not raw model capability.
- Verifiability: hidden-set scores and comparator rows are maintainer-attested; only the question set is cryptographically fixed. Comparator tools are under NDA, so per-vendor identities cannot be disclosed.
- Minor schema drift across lanes (Golden uses `search_id`; others use `id`).
- Physician calibration was qualitative: it shaped the judge protocol, but no formal physician-agreement statistics (MAE / r / n) are published in this sample (`calibrate_judge.py` is a reference harness with no bundled data).

---

## References

**ML / benchmark methodology**

- Fan, Z., Delsad, J., Flammarion, N., & Andriushchenko, M. (2026). *HalluHard: A Hard Multi-Turn Hallucination Benchmark.* arXiv:2602.01031. — basis for `halluhard_15`. (2026 preprint.)
- Zheng, L., et al. (2023). *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena.* arXiv:2306.05685. — judge protocol.
- Jimenez, C. E., et al. (2024). *SWE-bench: Can Language Models Resolve Real-World GitHub Issues?* arXiv:2310.06770. — held-out, contamination-resistant test-set precedent.
- Rein, D., et al. (2023). *GPQA: A Graduate-Level Google-Proof Q&A Benchmark.* arXiv:2311.12022. — held-out benchmark design precedent.
- Pimpale, et al. (2025). *How Can I Publish My LLM Benchmark Without Giving the True Answers Away?* arXiv:2505.18102. — the publish-without-leakage problem this release addresses.

**Clinical LLM evaluation**

- Arora, R. K., Wei, J., et al. (OpenAI) (2025). *HealthBench: Evaluating Large Language Models Towards Improved Human Health.* arXiv:2505.08775. — clinical-eval lineage.
- OpenAI (2025). *HealthBench Professional.* (Technical report.)

**Clinical guideline sources (freshness anchors)**

- CDC/ACIP immunization schedules; USPSTF recommendations; ADA *Standards of Care in Diabetes*; ACC/AHA cardiovascular & dyslipidemia guidelines; AAP policy statements.
