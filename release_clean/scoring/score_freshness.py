"""Currency (freshness) lane scorer for cds-bench.

Scores whether a candidate clinical response reflects the current operative
guideline for a query where the guidance has changed. Uses a PASS / PARTIAL /
FAIL verdict plus currency metadata fields.

Requires ANTHROPIC_API_KEY. Applies the shipped rubric at
  release_clean/rubrics/freshness.txt
(fallback: rubrics/freshness.txt for a clean public clone).

Published schema for score_currency():
  {
    "verdict":           "PASS" | "PARTIAL" | "FAIL",
    "currency":          "current" | "outdated" | "mixed" | "n/a",
    "recognized_change": true | false,
    "specific_concerns": [...],
    "reasoning":         "<paragraph>"
  }
"""

from __future__ import annotations

import json
import sys

from release_clean.scoring.base import (
  TRAP_JUDGE_MODEL,
  extract_json,
  load_rubric,
  make_client,
)

_RUBRIC_PRIMARY = "release_clean/rubrics/freshness.txt"
_RUBRIC_FALLBACK = "rubrics/freshness.txt"

_JUDGE_TEMPERATURE = 0.3
_JUDGE_MAX_TOKENS = 512
_JUDGE_RETRIES = 3


def score_currency(
  query: str,
  old_answer: str,
  new_answer: str,
  response: str,
  model: str = TRAP_JUDGE_MODEL,
  source_label: str = "candidate",
) -> dict:
  """Score one response for guideline currency.

  Args:
    query:        The clinical question.
    old_answer:   The outdated guideline answer (pre-change).
    new_answer:   The current guideline answer (post-change, with approximate date).
    response:     Candidate response text.
    model:        Judge model (default: TRAP_JUDGE_MODEL = claude-sonnet-4-6).
    source_label: Neutral label for the candidate in the judge prompt.

  Returns a dict with keys: verdict, currency, recognized_change,
  specific_concerns, reasoning. On persistent parse failure, verdict is "ERROR".
  """
  rubric = load_rubric(_RUBRIC_PRIMARY, fallback=_RUBRIC_FALLBACK)
  client = make_client()

  user_msg = (
    f"<query>{query}</query>\n\n"
    f"<old_answer>{old_answer}</old_answer>\n\n"
    f"<new_answer>{new_answer}</new_answer>\n\n"
    f"<candidate_response source=\"{source_label}\">\n{response[:15000]}\n</candidate_response>\n\n"
    "Score this response for guideline currency. Return ONLY the JSON object, nothing else."
  )

  last_err = ""
  for attempt in range(_JUDGE_RETRIES):
    try:
      resp = client.messages.create(
        model=model,
        max_tokens=_JUDGE_MAX_TOKENS,
        temperature=_JUDGE_TEMPERATURE,
        system=rubric,
        messages=[{"role": "user", "content": user_msg}],
      )
      return extract_json(resp.content[0].text)
    except (json.JSONDecodeError, IndexError) as e:
      last_err = str(e)

  return {
    "verdict": "ERROR",
    "currency": "n/a",
    "recognized_change": False,
    "specific_concerns": [],
    "reasoning": f"JSON parse failed after {_JUDGE_RETRIES} attempts: {last_err[:200]}",
  }


# ---------------------------------------------------------------------------
# CLI: score one case from a JSON argument
# ---------------------------------------------------------------------------

if __name__ == "__main__":
  import argparse

  parser = argparse.ArgumentParser(
    description=(
      "Score one freshness/currency case. "
      "Pass the case as a JSON string with keys: "
      "query, old_answer, new_answer, response. "
      "Optional: source_label."
    )
  )
  parser.add_argument("case_json", help="JSON string of the case to score")
  parser.add_argument("--model", default=TRAP_JUDGE_MODEL,
                      help=f"Judge model (default: {TRAP_JUDGE_MODEL})")
  args = parser.parse_args()

  case = json.loads(args.case_json)
  result = score_currency(
    query=case["query"],
    old_answer=case["old_answer"],
    new_answer=case["new_answer"],
    response=case["response"],
    model=args.model,
    source_label=case.get("source_label", "candidate"),
  )
  print(json.dumps(result, indent=2))
  sys.exit(0 if result.get("verdict") != "ERROR" else 1)
