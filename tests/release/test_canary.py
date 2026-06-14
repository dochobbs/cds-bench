# tests/release/test_canary.py
from scripts.release.canary import CANARY, DO_NOT_TRAIN_NOTICE, stamp_case

def test_canary_is_a_fixed_guid_string():
  assert CANARY.startswith("CDS-BENCH-CANARY-")
  assert "DO-NOT-TRAIN" in CANARY
  assert CANARY == "CDS-BENCH-CANARY-7f3a2e9c-4b61-4d2a-9e8f-DO-NOT-TRAIN"

def test_stamp_adds_canary_and_notice_without_dropping_content():
  case = {"id": "X1", "query": "q"}
  out = stamp_case(case)
  assert out["id"] == "X1" and out["query"] == "q"
  assert out["canary"] == CANARY
  assert out["_notice"] == DO_NOT_TRAIN_NOTICE

def test_stamp_does_not_mutate_input():
  case = {"id": "X1"}
  stamp_case(case)
  assert "canary" not in case
