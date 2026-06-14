# Evolution of cds-bench

*Postmarks in the development of this family-medicine CDS benchmark (Feb–Jun 2026), and the prior work it builds on. The full field report lives in the originating cds-eval repository.*

---

## Timeline

- **Feb 2026 — Golden set.** `golden_60`: 60 bread-and-butter clinical queries scored on a four-dimension rubric (Clinical Accuracy /30, Completeness /30, Specificity /25, Citation Quality /15), with **dual-gold scoring** (each candidate judged against two independent reference standards). Golden serves as a floor — serious tools cluster at ~85–90% — so adversarial lanes were added to actually separate them.

- **March 2026 — adversarial lanes.**
  - `freshness_30`: queries on guidelines that changed in ~12 months, each with a hand-curated `{old_answer, new_answer, source}` triple; anchored to real updates from **ACIP/CDC**, **USPSTF**, **ADA**, **ACC/AHA**, and **AAP**. Separates retrieval-augmented from parametric systems.
  - `hallucination_30`: adversarial prompts that bait fabricated citations and false premises (pass / partial / fail). The program's sharpest clinical-safety discriminator — spread here is bimodal where Golden accuracy looks uniform.

- **April 2026 — LLM-as-judge plan evolved.** A physician blind review reshaped the judging approach: the judge moved to **median-of-3 (temp 0.3) + anti-anchoring + date-awareness + verifiable-only citations**, and **physician review was adopted as the arbiter over automated scores** (LLM-as-judge as a screening tool, per Zheng et al.). This calibration discipline ships as `calibrate_judge.py`.

- **Prompt methodology.** `ws2` (~2.8K chars) lifts every model 17–20 points over no prompt and zeroes hallucination fails on frontier models — establishing that the rubric and prompt move the score more than the base model. The parallel-search variant `ws5_parallel` takes its reason-in-parallel-then-summarize structure from HeavySkill (Wang et al., 2026).

- **May 2026 — hard hallucination lane.** `halluhard_15`, derived from **HalluHard** (Fan et al., 2026). Adopted into the schema (`rarity`, `grounding_axis`, `ground_truth_source`, `fail_modes`):
  - **reference-vs-content grounding split** — does the cited source exist, and does it actually support the claim? (Correct-cite/wrong-dose is only caught by the content axis.)
  - **rarity stratification** — niche / moderate / common.
  - **multi-turn self-conditioning** — whether a wrong claim repeats across turns.
  Positioned **orthogonal** to `hallucination_30`: HalluHard measures *active* hallucination (model fabricates); ours measures *passive* hallucination (model accepts a false premise).

- **May 2026 — calculators.** `calc_micro_10`: deterministic calculator/dosing checks (CHA₂DS₂-VASc, Cockcroft-Gault, CURB-65, Centor, eGFR CKD-EPI 2021, …), scored against exact expected behavior, not by judge.

- **Lineage.** Register (parent- vs clinician-facing) and rubric design were informed by **HealthBench** and **HealthBench Professional** (Arora, Wei et al., OpenAI, 2025). cds-bench is the narrow, freshness- and safety-opinionated, held-out counterpart.

- **June 2026 — publishable release.** Split **29 public / 116 held-out** (proportional ~20%/lane, fixed-seed stratified). Contamination-resistant by construction: **BIG-bench canary GUID + do-not-train notice** on every artifact; a never-distributed held-out set with a published **SHA-256 + Merkle-root manifest**; and **eval-as-a-service** for hidden-set scoring. See `docs/superpowers/specs/` and `MIGRATION_MANIFEST.md`.

---

## References

**ML / benchmark methodology**

- Fan, Z., Delsad, J., Flammarion, N., & Andriushchenko, M. (2026). *HalluHard: A Hard Multi-Turn Hallucination Benchmark.* arXiv:2602.01031. — basis for `halluhard_15`.
- Wang, et al. (2026). *HeavySkill: Heavy Thinking as the Inner Skill in Agentic Harness.* arXiv:2605.02396. — parallel-reason-then-summarize structure behind `ws5_parallel`.
- Srivastava, A., et al. (2022). *Beyond the Imitation Game (BIG-bench).* arXiv:2206.04615. — canary-GUID / do-not-train convention used in the release.
- Jimenez, C. E., et al. (2024). *SWE-bench: Can Language Models Resolve Real-World GitHub Issues?* arXiv:2310.06770. — held-out, contamination-resistant test-set precedent.
- Rein, D., et al. (2023). *GPQA: A Graduate-Level Google-Proof Q&A Benchmark.* arXiv:2311.12022. — held-out benchmark design precedent.
- Pimpale, et al. (2025). *How Can I Publish My LLM Benchmark Without Giving the True Answers Away?* arXiv:2505.18102. — the publish-without-leakage problem this release addresses.
- Zheng, L., et al. (2023). *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena.* arXiv:2306.05685. — LLM-as-judge reliability.

**Clinical LLM evaluation**

- Arora, R. K., Wei, J., et al. (OpenAI) (2025). *HealthBench: Evaluating Large Language Models Towards Improved Human Health.* arXiv:2505.08775.
- OpenAI (2025). *HealthBench Professional.* (Technical report.)

**Clinical guideline sources (freshness anchors)**

- CDC/ACIP immunization schedules; USPSTF recommendations; ADA *Standards of Care in Diabetes*; ACC/AHA cardiovascular & dyslipidemia guidelines; AAP policy statements.

*Note: arXiv identifiers for 2026 preprints (HalluHard, HeavySkill) are recorded as cited in the source program's literature review; confirm current versions before external publication.*
