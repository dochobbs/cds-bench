"""LLM-as-judge: score candidate clinical content against a gold-standard reference.

Runs 3 independent judge calls at low temperature and returns the median
score per dimension to reduce variance.
"""

import json
import statistics
from datetime import date
from pathlib import Path
from typing import Optional

from anthropic import Anthropic

from release_clean.scoring.base import DEFAULT_JUDGE_MODEL

JUDGE_RUBRIC_PATH = "release_clean/rubrics/golden.txt"
JUDGE_TEMPERATURE = 0.3
JUDGE_RUNS = 3


def _load_rubric() -> str:
  """Load the judge rubric, trying JUDGE_RUBRIC_PATH first, then the in-tree fallback.

  Fallback covers running the scorer from inside dist/public/ (a clean public clone),
  where rubrics/ lives at the repo root rather than release_clean/rubrics/.
  Raises FileNotFoundError naming both candidates if neither exists.
  """
  candidates = [JUDGE_RUBRIC_PATH, "rubrics/golden.txt"]
  for path in candidates:
    try:
      with open(path) as f:
        rubric = f.read().strip()
      return rubric.replace("{current_date}", date.today().isoformat())
    except FileNotFoundError:
      continue
  raise FileNotFoundError(
    f"judge rubric not found; tried: {candidates[0]!r} and {candidates[1]!r}"
  )


def _format_references(references: list[dict]) -> str:
  """Format a structured references array into readable text."""
  if not references:
    return ""
  lines = ["\n\n## References\n"]
  seen = set()
  for ref in references:
    idx = ref.get("index", "?")
    ref_type = ref.get("type", "unknown")
    if ref_type == "literature":
      title = ref.get("title", "Untitled")
      journal = ref.get("journal_title", "")
      year = ref.get("year", "")
      doi = ref.get("doi", "")
      authors = ref.get("authors", "")
      url = ref.get("url", "")
      doc_id = ref.get("doc_id", str(idx))
      if doc_id in seen:
        continue
      seen.add(doc_id)
      line = f"[{idx}] {authors} {title}"
      if journal:
        line += f" *{journal}*."
      if year:
        line += f" {year}."
      if doi:
        line += f" DOI: {doi}"
      if url:
        line += f" {url}"
      lines.append(line)
    elif ref_type == "compound":
      name = ref.get("generic_name", ref.get("manufactured_name", "Unknown drug"))
      url = ref.get("url", "")
      lines.append(f"[{idx}] Drug: {name} {url}")
  return "\n".join(lines)


def _single_judge_call(
  claude: Anthropic,
  rubric: str,
  user_msg: str,
  model: str,
) -> dict:
  """Execute one judge call and parse the result."""
  response = claude.messages.create(
    model=model,
    max_tokens=4096,
    temperature=JUDGE_TEMPERATURE,
    system=rubric,
    messages=[{"role": "user", "content": user_msg}],
  )

  text = response.content[0].text.strip()
  if text.startswith("```"):
    text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

  return json.loads(text)


SCORE_DIMS = [
  "clinical_accuracy", "completeness", "specificity",
  "citation_quality", "clinical_judgment",
]

REASONING_FIELDS = [
  "accuracy_reasoning", "completeness_reasoning",
  "specificity_reasoning", "citation_reasoning",
  "judgment_reasoning",
]


def _median_scores(runs: list[dict]) -> dict:
  """Take median of each score dimension across multiple judge runs.

  For reasoning fields, pick the reasoning from the run whose total_score
  is closest to the median total — the "median run."
  """
  result = {}

  # Median each score dimension
  for dim in SCORE_DIMS:
    values = [r.get(dim, 0) for r in runs]
    result[dim] = int(statistics.median(values))

  # Recalculate total from median dimensions
  result["total_score"] = (
    result["clinical_accuracy"]
    + result["completeness"]
    + result["specificity"]
    + result["citation_quality"]
  )

  # Find the median run (closest total to median total) for reasoning
  totals = [
    r.get("clinical_accuracy", 0) + r.get("completeness", 0)
    + r.get("specificity", 0) + r.get("citation_quality", 0)
    for r in runs
  ]
  median_total = statistics.median(totals)
  median_idx = min(range(len(totals)), key=lambda i: abs(totals[i] - median_total))
  median_run = runs[median_idx]

  # Copy reasoning from median run
  for field in REASONING_FIELDS:
    result[field] = median_run.get(field, "")

  # Copy list fields from median run
  result["critical_errors"] = median_run.get("critical_errors", [])
  result["missing_topics"] = median_run.get("missing_topics", [])

  # Store per-run scores for auditability
  result["_run_totals"] = totals
  result["_run_spread"] = max(totals) - min(totals)

  return result


def judge_query(
  query: str,
  gold_content: str,
  candidate_content: str,
  model: str = DEFAULT_JUDGE_MODEL,
  references: Optional[list[dict]] = None,
  web_citations: Optional[list[dict]] = None,
  gold_label: str = "the gold-standard reference",
  candidate_label: str = "candidate",
  num_runs: int = JUDGE_RUNS,
) -> dict:
  """Score a candidate clinical response against a gold standard.

  Runs the judge num_runs times at low temperature and returns the median
  score per dimension. This reduces variance from ~15 stdev to ~3-4 stdev
  on volatile queries.

  Args:
    query: The clinical question.
    gold_content: Gold standard content (from a curated reference).
    candidate_content: Candidate response text.
    model: Judge model to use.
    references: Optional structured references to append.
    web_citations: Optional list of URLs actually retrieved by web search.
    gold_label: Label for the gold standard source.
    candidate_label: Label for the candidate source.
    num_runs: Number of independent judge calls (default 3, median used).

  Returns dict with median dimension scores, per-dimension reasoning,
  total_score, clinical_judgment, critical_errors, missing_topics.
  """
  empty_result = {
    "clinical_accuracy": 0,
    "completeness": 0,
    "specificity": 0,
    "citation_quality": 0,
    "total_score": 0,
    "clinical_judgment": 0,
    "critical_errors": [],
    "missing_topics": [],
    "gold_label": gold_label,
    "candidate_label": candidate_label,
  }
  for field in REASONING_FIELDS:
    empty_result[field] = ""

  if not gold_content or not gold_content.strip():
    empty_result["accuracy_reasoning"] = f"{gold_label} returned no content — cannot score."
    empty_result["skipped"] = "gold_empty"
    return empty_result

  if not candidate_content or not candidate_content.strip():
    empty_result["missing_topics"] = ["All — candidate returned no content"]
    empty_result["accuracy_reasoning"] = "Candidate returned no content."
    empty_result["skipped"] = "candidate_empty"
    return empty_result

  # Prepare candidate text
  full_candidate = candidate_content[:25000]
  if references:
    ref_text = _format_references(references)
    full_candidate = candidate_content[:23000] + ref_text

  # Build retrieved URLs block
  retrieved_block = ""
  if web_citations:
    seen_urls = set()
    url_lines = []
    for c in web_citations:
      url = c.get("url", "")
      if url and url not in seen_urls:
        seen_urls.add(url)
        title = c.get("title", "")
        url_lines.append(f"- {url} — {title}" if title else f"- {url}")
    if url_lines:
      retrieved_block = (
        "\n\n<retrieved_urls>\n"
        "The following URLs were actually returned by the web search engine "
        "during candidate generation. These are verified retrievals, not "
        "fabricated citations:\n"
        + "\n".join(url_lines[:30])
        + "\n</retrieved_urls>\n\n"
      )

  claude = Anthropic()
  rubric = _load_rubric()

  user_msg = (
    f"<query>{query}</query>\n\n"
    f"<gold_standard>\n{gold_content[:25000]}\n</gold_standard>\n\n"
    f"<candidate>\n{full_candidate}\n</candidate>\n"
    f"{retrieved_block}"
    "Score the candidate clinical response against the gold standard.\n"
    "Return ONLY the JSON object."
  )

  # Run judge multiple times
  successful_runs = []
  errors = []
  for i in range(num_runs):
    try:
      result = _single_judge_call(claude, rubric, user_msg, model)
      successful_runs.append(result)
    except json.JSONDecodeError as e:
      errors.append(f"Run {i+1} parse error: {e}")
    except Exception as e:
      errors.append(f"Run {i+1} error: {e}")

  if not successful_runs:
    empty_result["accuracy_reasoning"] = f"All {num_runs} judge runs failed: {'; '.join(errors)}"
    empty_result["error"] = "all_runs_failed"
    return empty_result

  # If only 1 successful run, use it directly (no median)
  if len(successful_runs) == 1:
    result = successful_runs[0]
  else:
    result = _median_scores(successful_runs)

  # Recalculate total_score from first four dimensions
  result["total_score"] = (
    result.get("clinical_accuracy", 0)
    + result.get("completeness", 0)
    + result.get("specificity", 0)
    + result.get("citation_quality", 0)
  )
  result["gold_label"] = gold_label
  result["candidate_label"] = candidate_label

  if errors:
    result["_failed_runs"] = errors

  return result
