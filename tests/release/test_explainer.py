# tests/release/test_explainer.py
"""Pure-string tests for the interactive explainer + public-case renderer.

No browser dependency — all assertions on string output only.
"""
from __future__ import annotations

import json
import pytest

from scripts.release.build_explainer import (
  _assert_no_private_path,
  load_public,
  render_html,
  render_markdown,
)
from scripts.release.lanes import LANES


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def public():
  return load_public()


@pytest.fixture(scope="module")
def rubrics() -> dict[str, str]:
  from pathlib import Path
  result = {}
  for lane_name, lane in LANES.items():
    if lane.judge_rubric:
      p = Path(lane.judge_rubric)
      if p.exists():
        result[lane_name] = p.read_text(encoding="utf-8")
  return result


@pytest.fixture(scope="module")
def html_out(public, rubrics):
  return render_html(public, rubrics=rubrics)


@pytest.fixture(scope="module")
def md_out(public):
  return render_markdown(public)


# ---------------------------------------------------------------------------
# load_public tests
# ---------------------------------------------------------------------------

def test_load_public_total_29(public):
  total = sum(len(v) for v in public.values())
  assert total == 29, f"Expected 29 public cases, got {total}"


def test_load_public_per_lane(public):
  expected = {
    "golden": 12,
    "freshness": 6,
    "hallucination": 6,
    "halluhard": 3,
    "calc": 2,
  }
  for lane_name, count in expected.items():
    assert lane_name in public, f"Lane {lane_name!r} missing from load_public()"
    got = len(public[lane_name])
    assert got == count, f"{lane_name}: expected {count} public cases, got {got}"


def test_load_public_case_dicts_have_split_public(public):
  """Every returned case must have split=='public'."""
  for lane_name, cases in public.items():
    for c in cases:
      assert c.get("split") == "public", (
        f"Non-public case found in {lane_name}: {c!r}"
      )


def test_load_public_case_has_id_field(public):
  """Each case must carry its lane's id_field key."""
  for lane_name, cases in public.items():
    lane = LANES[lane_name]
    for c in cases:
      assert lane.id_field in c, (
        f"{lane_name} case missing id field {lane.id_field!r}: {c!r}"
      )


# ---------------------------------------------------------------------------
# render_html — id presence / absence
# ---------------------------------------------------------------------------

def test_html_contains_all_29_public_ids(html_out, public):
  for lane_name, cases in public.items():
    lane = LANES[lane_name]
    for c in cases:
      cid = c[lane.id_field]
      assert cid in html_out, f"Public id {cid!r} missing from HTML"


def test_html_contains_no_hidden_golden_ids(html_out):
  """Known hidden golden ids must not appear in the HTML."""
  # Verified hidden from test run: G01, G02, G03, G05, G06 are hidden
  for hidden_id in ("G01", "G02", "G03", "G05", "G06"):
    assert hidden_id not in html_out, (
      f"Hidden golden id {hidden_id!r} found in HTML — leak!"
    )


def test_html_contains_no_hidden_freshness_ids(html_out):
  # F02, F04, F05 are hidden (public are F01, F03, F09, F17, F19, F21)
  for hidden_id in ("F02", "F04", "F05"):
    assert hidden_id not in html_out, (
      f"Hidden freshness id {hidden_id!r} found in HTML — leak!"
    )


def test_html_contains_no_hidden_hallucination_ids(html_out):
  # H01, H02, H03 are hidden
  for hidden_id in ("H01", "H02", "H03"):
    assert hidden_id not in html_out, (
      f"Hidden hallucination id {hidden_id!r} found in HTML — leak!"
    )


def test_html_contains_no_hidden_halluhard_ids(html_out):
  # HH01, HH02, HH03 are hidden (public are HH04, HH08, HH12)
  for hidden_id in ("HH01", "HH02", "HH03"):
    assert hidden_id not in html_out, (
      f"Hidden halluhard id {hidden_id!r} found in HTML — leak!"
    )


def test_html_contains_no_hidden_calc_ids(html_out):
  # C03 onward are hidden (public are C01, C02)
  for hidden_id in ("C03", "C04", "C05"):
    assert hidden_id not in html_out, (
      f"Hidden calc id {hidden_id!r} found in HTML — leak!"
    )


# ---------------------------------------------------------------------------
# render_html — structure
# ---------------------------------------------------------------------------

def test_html_all_five_lane_labels_present(html_out):
  for label in ("Golden", "Freshness", "Hallucination", "HalluHard", "Calc"):
    assert label in html_out, f"Lane label {label!r} missing from HTML"


def test_html_freshness_gold_fields_present(html_out, public):
  """A freshness case must show its new_answer in the HTML."""
  f_cases = public["freshness"]
  assert f_cases, "No freshness public cases found"
  # Check that at least one new_answer text appears
  found_any = False
  for c in f_cases:
    if c.get("new_answer") and c["new_answer"] in html_out:
      found_any = True
      break
  assert found_any, "No freshness new_answer found in HTML"


def test_html_halluhard_gold_fields_present(html_out, public):
  """A halluhard case must show its grounding_axis in the HTML."""
  hh_cases = public["halluhard"]
  assert hh_cases
  found_any = False
  for c in hh_cases:
    if c.get("grounding_axis") and c["grounding_axis"] in html_out:
      found_any = True
      break
  assert found_any, "No halluhard grounding_axis found in HTML"


def test_html_hallucination_trap_present(html_out, public):
  """A hallucination case must show its trap field."""
  h_cases = public["hallucination"]
  assert h_cases
  found_any = False
  for c in h_cases:
    if c.get("trap") and c["trap"] in html_out:
      found_any = True
      break
  assert found_any, "No hallucination trap value found in HTML"


def test_html_calc_calculator_present(html_out, public):
  """A calc case must show its calculator field."""
  c_cases = public["calc"]
  assert c_cases
  found_any = False
  for c in c_cases:
    if c.get("calculator") and c["calculator"] in html_out:
      found_any = True
      break
  assert found_any, "No calc calculator field found in HTML"


def test_html_canary_present(html_out):
  from scripts.release.canary import CANARY
  assert CANARY in html_out, "Canary GUID missing from HTML"


def test_html_do_not_train_notice_present(html_out):
  # Check a distinctive substring of the notice
  assert "Do NOT use it" in html_out or "do not train" in html_out.lower(), (
    "Do-not-train notice missing from HTML"
  )


def test_html_is_self_contained(html_out):
  """No external CDN src/href/url links."""
  import re
  # Must not load any external asset via src= or href= pointing to http(s)
  external_src = re.findall(r'(?:src|href)=["\']https?://', html_out, re.IGNORECASE)
  # Allow data: URIs but nothing else
  assert not external_src, f"External asset references found: {external_src}"


def test_html_no_cdn_link_tag(html_out):
  """No <link rel=stylesheet href=http..."""
  assert "rel=stylesheet href=http" not in html_out.lower()


# ---------------------------------------------------------------------------
# render_html — leak guards
# ---------------------------------------------------------------------------

def test_html_no_private_path(html_out):
  _assert_no_private_path(html_out, "html_out")  # must not raise


def test_md_no_private_path(md_out):
  _assert_no_private_path(md_out, "md_out")  # must not raise


def test_assert_no_private_path_raises_on_users(capsys):
  with pytest.raises(ValueError, match="private path"):
    _assert_no_private_path("Some text with /Users/dochobbs/x in it", "test")


def test_assert_no_private_path_raises_on_tmp_gemvenv(capsys):
  with pytest.raises(ValueError, match="private path"):
    _assert_no_private_path("path=/tmp/gemvenv/bin/python", "test")


def test_assert_no_private_path_raises_case_insensitive():
  with pytest.raises(ValueError):
    _assert_no_private_path("/USERS/someone/secret", "test")


def test_assert_no_private_path_passes_clean():
  _assert_no_private_path("This is clean text with no private paths.", "test_clean")


# ---------------------------------------------------------------------------
# render_markdown tests
# ---------------------------------------------------------------------------

def test_md_lists_29_cases(md_out):
  """Count ### headings (one per case)."""
  count = md_out.count("\n### ")
  assert count == 29, f"Expected 29 case headings in Markdown, got {count}"


def test_md_contains_all_29_public_ids(md_out, public):
  for lane_name, cases in public.items():
    lane = LANES[lane_name]
    for c in cases:
      cid = c[lane.id_field]
      assert cid in md_out, f"Public id {cid!r} missing from Markdown"


def test_md_header_contains_do_not_train(md_out):
  assert "do not train" in md_out.lower(), "do-not-train notice missing from Markdown header"


def test_md_has_five_lane_sections(md_out):
  for label in ("Golden", "Freshness", "Hallucination", "HalluHard", "Calc"):
    assert f"## {label}" in md_out, f"Lane section ## {label} missing from Markdown"


def test_md_freshness_old_new_answers_present(md_out, public):
  for c in public["freshness"]:
    if c.get("old_answer"):
      assert c["old_answer"] in md_out, f"Freshness old_answer missing from MD: {c['id']}"
    if c.get("new_answer"):
      assert c["new_answer"] in md_out, f"Freshness new_answer missing from MD: {c['id']}"


def test_md_halluhard_grounding_axis_present(md_out, public):
  for c in public["halluhard"]:
    if c.get("grounding_axis"):
      assert c["grounding_axis"] in md_out, (
        f"halluhard grounding_axis missing from MD for {c['id']}"
      )


# ---------------------------------------------------------------------------
# Cross-check: hidden ids not in HTML (loaded from actual bench files)
# ---------------------------------------------------------------------------

def test_html_contains_zero_hidden_ids_exhaustive(html_out):
  """Load every hidden id and assert none appears in the embedded JSON blob.

  We check the cases-data JSON blob specifically (not full HTML substring) to
  avoid false positives where short hidden IDs like 'H04' appear as a substring
  of a legitimate public ID like 'HH04'. The JSON blob contains explicit "id"
  values; a hidden id in the blob is a genuine leak.
  """
  import json as _json
  import re as _re
  from pathlib import Path

  hidden_ids: set[str] = set()
  for lane in LANES.values():
    raw = _json.loads(Path(
      lane.filename if "/" in lane.filename else f"benchmarks/internal/{lane.filename}"
    ).read_text())
    for c in raw:
      if c.get("split") == "hidden":
        hidden_ids.add(c[lane.id_field])

  # Extract the embedded JSON blob to check for actual data-level leaks
  m = _re.search(
    r'<script[^>]+id=["\']cases-data["\'][^>]*>(.*?)</script>',
    html_out,
    _re.DOTALL,
  )
  assert m, "cases-data script block not found in HTML"
  blob = _json.loads(m.group(1))
  blob_ids = {entry.get("id") or entry.get("search_id") for entry in blob}

  leaked = [hid for hid in hidden_ids if hid in blob_ids]
  assert not leaked, f"Hidden ids leaked into cases-data JSON blob: {leaked}"
