# tests/release/test_worked_examples.py
import json
from scripts.release.build_public import build_public
from scripts.release.lanes import SHOWCASE_IDS

def test_overlay_emitted_to_worked_examples(tmp_path):
  wd = tmp_path / "worked"
  wd.mkdir()
  (wd / "F19.json").write_text(json.dumps({
    "id": "F19", "system": "Vendor A",
    "transcript": "…answer…", "scores": {"freshness": 2}}), encoding="utf-8")
  out = tmp_path / "cds-bench"
  build_public(str(out), seed=20260614, generated="2026-06-14", worked_dir=str(wd))
  emitted = out / "worked_examples" / "F19.json"
  assert emitted.exists()
  assert json.loads(emitted.read_text())["id"] == "F19"

def test_showcase_ids_are_all_forced_public():
  from scripts.release.lanes import LANES
  forced = {l.forced_public for l in LANES.values()}
  assert set(SHOWCASE_IDS) == forced
