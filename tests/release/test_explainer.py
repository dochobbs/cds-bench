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

def test_load_public_total_27(public):
  total = sum(len(v) for v in public.values())
  assert total == 27, f"Expected 27 public cases, got {total}"


def test_load_public_per_lane(public):
  expected = {
    "golden": 12,
    "freshness": 6,
    "hallucination": 6,
    "halluhard": 3,
  }
  for lane_name, count in expected.items():
    assert lane_name in public, f"Lane {lane_name!r} missing from load_public()"
    got = len(public[lane_name])
    assert got == count, f"{lane_name}: expected {count} public cases, got {got}"


def test_load_public_no_calc_lane(public):
  """calc lane was removed; must not be present."""
  assert "calc" not in public, "calc lane should not be present in 4-lane bench"


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

def test_html_contains_all_27_public_ids(html_out, public):
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


# ---------------------------------------------------------------------------
# render_html — structure
# ---------------------------------------------------------------------------

def test_html_four_lane_labels_present(html_out):
  for label in ("Golden", "Freshness", "Hallucination", "HalluHard"):
    assert label in html_out, f"Lane label {label!r} missing from HTML"


def test_html_no_canary_present(html_out):
  """Canary GUID must not appear in the HTML."""
  assert "CDS-BENCH-CANARY" not in html_out, "Canary GUID found in HTML — should be removed"
  assert "DO-NOT-TRAIN" not in html_out, "DO-NOT-TRAIN text found in HTML — should be removed"


def test_html_data_use_request_present(html_out):
  """Data use request phrasing must be present."""
  assert "Please don" in html_out or "data use request" in html_out.lower() or "training data" in html_out.lower()


def test_html_results_section_present(html_out):
  """Results section (six-source full-sample table) must be present."""
  assert "92.6" in html_out, "top Core score missing"
  assert "OpenEvidence" in html_out, "OpenEvidence row missing"
  assert "ChatGPT for Clinicians" in html_out, "ChatGPT for Clinicians row missing"
  assert "UpToDate" in html_out, "UpToDate row missing"

def test_html_results_blinds_commercial_partners(html_out):
  """Named public tools are allowed; commercial-partner gold/comparators must stay blinded."""
  low = html_out.lower()
  for forbidden in ("amboss", "lisa", "glass health", "clinical insights"):
    assert forbidden not in low, f"commercial-partner name leaked: {forbidden}"


def test_html_limitations_section_present(html_out):
  """Limitations section must be present."""
  assert "Limitations" in html_out


def test_html_no_publication_grade(html_out):
  """Must not claim publication-grade."""
  assert "publication-grade" not in html_out.lower()
  assert "publishable" not in html_out.lower()


def test_html_fresh_counts(html_out):
  """HTML must contain the correct 27/108/135/4 counts, not old 29/116/145/5."""
  assert "135" in html_out
  assert "27" in html_out
  assert "108" in html_out
  # Old counts must not appear
  assert "145" not in html_out
  assert "116" not in html_out


def test_html_freshness_gold_fields_present(html_out, public):
  """A freshness case must show its new_answer in the HTML."""
  f_cases = public["freshness"]
  assert f_cases, "No freshness public cases found"
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


def test_html_static_case_cards_present(html_out, public):
  """Static case cards must be in the HTML (no-JS readable)."""
  count = html_out.count('class="case-card"')
  total = sum(len(v) for v in public.values())
  assert count == total, f"Expected {total} static case cards in HTML, got {count}"


def test_html_is_self_contained(html_out):
  """No external CDN src/href/url links."""
  import re
  external_src = re.findall(r'(?:src|href)=["\']https?://', html_out, re.IGNORECASE)
  assert not external_src, f"External asset references found: {external_src}"


def test_html_no_cdn_link_tag(html_out):
  """No <link rel=stylesheet href=http..."""
  assert "rel=stylesheet href=http" not in html_out.lower()


def test_html_filter_buttons_have_aria_pressed(html_out):
  """Filter buttons must have aria-pressed attribute."""
  assert 'aria-pressed="true"' in html_out
  assert 'aria-pressed="false"' in html_out


def test_html_focus_visible_rule(html_out):
  """CSS must include a :focus-visible rule."""
  assert ":focus-visible" in html_out


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

def test_md_lists_27_cases(md_out):
  """Count ### headings (one per case)."""
  count = md_out.count("\n### ")
  assert count == 27, f"Expected 27 case headings in Markdown, got {count}"


def test_md_contains_all_27_public_ids(md_out, public):
  for lane_name, cases in public.items():
    lane = LANES[lane_name]
    for c in cases:
      cid = c[lane.id_field]
      assert cid in md_out, f"Public id {cid!r} missing from Markdown"


def test_md_header_contains_data_use_request(md_out):
  assert "training data" in md_out.lower() or "data use request" in md_out.lower()


def test_md_no_canary(md_out):
  assert "CDS-BENCH-CANARY" not in md_out


def test_md_has_four_lane_sections(md_out):
  for label in ("Golden", "Freshness", "Hallucination", "HalluHard"):
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
# Cross-check: hidden ids not in HTML
# ---------------------------------------------------------------------------

def test_html_contains_zero_hidden_ids_exhaustive(html_out):
  """Load every hidden id and assert none appears in the static card HTML.

  We scan the case-card blocks in the static HTML. Hidden ids in .case-card
  data attributes or content is a genuine data leak.
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

  # Find all case-card blocks in static HTML and extract their IDs
  # Each card has: <span class="case-id">XXXX</span>
  blob_ids = set(_re.findall(r'<span class="case-id">([^<]+)</span>', html_out))

  leaked = [hid for hid in hidden_ids if hid in blob_ids]
  assert not leaked, f"Hidden ids leaked into static case cards: {leaked}"
