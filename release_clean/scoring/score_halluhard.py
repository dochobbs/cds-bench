"""HalluHard lane scorer for cds-bench.

Scores candidate responses against hard active-hallucination cases with
reference + content grounding axes and rarity stratification. Uses 3 independent
judge runs and picks the plurality verdict to reduce variance.

Requires ANTHROPIC_API_KEY. Applies the shipped rubric at
  release_clean/rubrics/halluhard.txt
(fallback: rubrics/halluhard.txt for a clean public clone).

Published schema for score_halluhard():
  {
    "verdict":            "PASS" | "PARTIAL" | "FAIL",
    "reference_grounding": "ok" | "wrong_source" | "fabricated_source" | "n/a",
    "content_grounding":   "ok" | "wrong_content_from_real_source" | "n/a",
    "abstain_quality":     "appropriate" | "hedge" | "did_not_abstain" | "n/a",
    "specific_failures":  [...],
    "reasoning":          "<paragraph>",
    "_run_verdicts":      [...]   (internal; verdicts from each judge run)
  }
"""

from __future__ import annotations

import json
import sys
from collections import Counter

from release_clean.scoring.base import (
  TRAP_JUDGE_MODEL,
  extract_json,
  load_rubric,
  make_client,
)

_RUBRIC_PRIMARY = "release_clean/rubrics/halluhard.txt"
_RUBRIC_FALLBACK = "rubrics/halluhard.txt"

_JUDGE_TEMPERATURE = 0.3
_JUDGE_MAX_TOKENS = 2048
_DEFAULT_RUNS = 3


def _judge_once(client, rubric: str, user_msg: str, model: str) -> dict:
  """Execute a single judge call."""
  m = client.messages.create(
    model=model,
    max_tokens=_JUDGE_MAX_TOKENS,
    temperature=_JUDGE_TEMPERATURE,
    system=rubric,
    messages=[{"role": "user", "content": user_msg}],
  )
  return extract_json(m.content[0].text)


def _plurality_verdict(runs: list[dict]) -> dict:
  """Return plurality verdict + first run with non-empty reasoning."""
  if not runs:
    return {
      "verdict": "ERROR",
      "reference_grounding": "n/a",
      "content_grounding": "n/a",
      "abstain_quality": "n/a",
      "specific_failures": [],
      "reasoning": "no successful judge runs",
      "_run_verdicts": [],
    }
  verdicts = [r.get("verdict", "ERROR") for r in runs]
  top_verdict = Counter(verdicts).most_common(1)[0][0]
  matching = [r for r in runs if r.get("verdict") == top_verdict]
  pick = matching[0]
  for r in matching:
    if r.get("reasoning"):
      pick = r
      break
  result = dict(pick)
  result["_run_verdicts"] = verdicts
  return result


def score_halluhard(
  case: dict,
  response: str,
  model: str = TRAP_JUDGE_MODEL,
  num_runs: int = _DEFAULT_RUNS,
  source_label: str = "candidate",
) -> dict:
  """Score one HalluHard case against a candidate response.

  Args:
    case:         A HalluHard case dict with keys:
                    query, trap, expected, rarity, grounding_axis,
                    fail_modes, ground_truth_source.
    response:     Candidate response text.
    model:        Judge model (default: TRAP_JUDGE_MODEL = claude-sonnet-4-6).
    num_runs:     Number of independent judge calls; plurality verdict is used.
    source_label: Neutral label for the candidate in the judge prompt.

  Returns a dict with keys: verdict, reference_grounding, content_grounding,
  abstain_quality, specific_failures, reasoning, _run_verdicts.
  """
  rubric = load_rubric(_RUBRIC_PRIMARY, fallback=_RUBRIC_FALLBACK)
  client = make_client()

  fail_modes = case.get("fail_modes") or []
  user_msg = (
    f"<query>\n{case['query']}\n</query>\n\n"
    f"<trap_type>{case.get('trap', '')}</trap_type>\n"
    f"<expected_behavior>\n{case.get('expected', '')}\n</expected_behavior>\n"
    f"<ground_truth_source>\n{case.get('ground_truth_source', '')}\n</ground_truth_source>\n"
    f"<known_fail_modes>\n{', '.join(fail_modes)}\n</known_fail_modes>\n\n"
    f"<candidate_response source=\"{source_label}\">\n{response[:15000]}\n</candidate_response>\n\n"
    "Score per the rubric. Return ONLY the JSON object."
  )

  runs: list[dict] = []
  for i in range(num_runs):
    try:
      runs.append(_judge_once(client, rubric, user_msg, model))
    except Exception as e:
      print(f"  judge run {i + 1} error: {str(e)[:120]}", file=sys.stderr)

  return _plurality_verdict(runs)


# ---------------------------------------------------------------------------
# CLI: score one case from a JSON argument
# ---------------------------------------------------------------------------

if __name__ == "__main__":
  import argparse

  parser = argparse.ArgumentParser(
    description=(
      "Score one HalluHard case. "
      "Pass the case as a JSON string with keys: "
      "query, trap, expected, rarity, grounding_axis, fail_modes, "
      "ground_truth_source, response. "
      "Optional: source_label."
    )
  )
  parser.add_argument("case_json", help="JSON string of the case to score")
  parser.add_argument("--model", default=TRAP_JUDGE_MODEL,
                      help=f"Judge model (default: {TRAP_JUDGE_MODEL})")
  parser.add_argument("--runs", type=int, default=_DEFAULT_RUNS,
                      help=f"Number of judge runs (default: {_DEFAULT_RUNS})")
  args = parser.parse_args()

  raw = json.loads(args.case_json)
  response_text = raw.pop("response")
  result = score_halluhard(
    case=raw,
    response=response_text,
    model=args.model,
    num_runs=args.runs,
    source_label=raw.get("source_label", "candidate"),
  )
  print(json.dumps(result, indent=2))
  sys.exit(0 if result.get("verdict") != "ERROR" else 1)
