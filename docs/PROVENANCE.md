# Provenance — proof of work

This repository is a **cleaned public snapshot**, first published June 2026, so its git
history begins at publication. The development predates that. The record below postmarks the
actual work done in the originating internal evaluation program — enough to corroborate the
Feb–Jun 2026 timeline without exposing the held-out set.

**What is redacted / omitted, and why**

- **Vendor / comparator names** are removed — the compared commercial CDS tools are under NDA.
- **Per-query clinical content** is omitted — some of those queries are now held-out test cases.
- **Private filesystem paths** are stripped.

What remains — dates, file mtimes, aggregate scores, and commit subjects — is sufficient to
show *the described work happened when it says it did*. It does **not** attempt to verify the
comparator numbers (those stay maintainer-attested; see the benchmark's Limitations).

## Postmarks

| Period | Verifiable evidence | What it shows |
|---|---|---|
| **Feb 2026** | 42 timestamped eval run-logs spanning **Feb 20–24, 2026** in the originating eval repo. Earliest: `eval_20260220_082102`, file mtime `2026-02-20 08:21` (matches its timestamp). | The golden set existed and was being scored in February — 10 golden queries, mean **75.2**, on the **same four-dimension rubric this repo ships** (clinical accuracy / completeness / specificity / citation quality). Redacted excerpt: [`provenance/eval_20260220_redacted.json`](provenance/eval_20260220_redacted.json). |
| **Mar 2026** | Untracked iteration (between the February run-logs and the April git-init). | No commit history for this gap — version control had not started yet; the bracketing Feb run-logs and April commits postmark the period on either side. |
| **Apr 2026** | Version control begins — **git-init Apr 3**, 34 commits that month. | The judge overhaul (median-of-3, low temperature, anti-anchoring, date-awareness, the `clinical_judgment` dimension) lands on day one. |
| **May 2026** | 37 commits. | Consolidation, adversarial lanes, judge calibration. |
| **Jun 2026** | 58 commits, through Jun 14. | Hardening, the HalluHard lane, and this public release. |

**Tracked development:** 129 family-medicine CDS commits, Apr 3 – Jun 14 2026 — density **34 / 37 / 58** by month. (The originating repo is a shared eval workspace; commits for unrelated parallel projects are omitted from this log.)
Full redacted log (dates + subjects): [`provenance/commit-log-redacted.txt`](provenance/commit-log-redacted.txt).

## The February run (redacted postmark)

A real scored run from **2026-02-20**, metadata + aggregate summary only:

```json
{
  "metadata": {
    "timestamp": "2026-02-20T08:21:02",
    "model": "claude-sonnet-4-6",
    "cds_prompt_path": "eval/prompts/cds_websearch.txt",
    "cds_prompt_hash": "0f3c0fe2",
    "total_queries": 10,
    "golden_queries": 10
  },
  "summary": {
    "scored_queries": 10,
    "overall": { "mean_score": 75.2, "ci_90": [71.23, 79.17], "pass_rate_80": 0.4 },
    "dimensions": {
      "clinical_accuracy": { "mean": 24.5 },
      "completeness":      { "mean": 21.5 },
      "specificity":       { "mean": 19.1 },
      "citation_quality":  { "mean": 10.1 }
    }
  }
}
```

The four scoring dimensions, the LLM-as-judge protocol, and a golden query set are all present
here — **five weeks before this repository's own git history begins.** That is the point of this
file: the commit log starts in April because version control started in April, not because the
work did.
