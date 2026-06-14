# scripts/release/lanes.py
"""Single source of truth for the internal CDS bench lanes and the public split quota."""
from __future__ import annotations
from dataclasses import dataclass

BENCH_DIR = "benchmarks/internal"

@dataclass(frozen=True)
class Lane:
  name: str
  filename: str
  id_field: str       # key holding the case id ("search_id" for golden, "id" elsewhere)
  strat_field: str    # key used to stratify the sample
  total: int
  public_count: int
  forced_public: str  # worked-example id that MUST land in the public set
  judge_rubric: str | None  # curated blinded rubric shipped into the public tree (None = deterministic lane)

LANES: dict[str, Lane] = {
  "golden":        Lane("golden",        "golden_60.json",        "search_id", "category",   60, 12, "G52",  "release_clean/rubrics/golden.txt"),
  "freshness":     Lane("freshness",     "freshness_30.json",     "id",        "category",   30,  6, "F19",  "release_clean/rubrics/freshness.txt"),
  "hallucination": Lane("hallucination", "hallucination_30.json", "id",        "category",   30,  6, "H11",  "release_clean/rubrics/hallucination.txt"),
  "halluhard":     Lane("halluhard",     "halluhard_15.json",     "id",        "category",   15,  3, "HH08", "release_clean/rubrics/halluhard.txt"),
  "calc":          Lane("calc",          "calc_micro_10.json",    "id",        "calculator", 10,  2, "C01",  None),
}

WORKED_DIR = "benchmarks/internal/worked"  # optional curated overlays: <ID>.json {transcript, scores, system}
SHOWCASE_IDS = ("G52", "F19", "H11", "HH08", "C01")  # forced-public showcase ids; worked-example files are copied wholesale from WORKED_DIR (not filtered by this tuple)
