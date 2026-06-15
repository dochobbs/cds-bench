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


def test_html_contains_no_hidden_ids(html_out):
  """No held-out case id may appear in the public HTML.

  Hidden ids are derived at runtime from the local (gitignored) hidden set, so no
  hidden id is hardcoded/committed in this test. Skipped in a public clone where the
  hidden set is absent by design.
  """
  import re
  from pathlib import Path
  from scripts.release.lanes import HIDDEN_DIR
  if not Path(HIDDEN_DIR).exists():
    pytest.skip("hidden set not present (public clone)")
  checked = 0
  for lane in LANES.values():
    p = Path(HIDDEN_DIR, lane.filename)
    if not p.exists():
      continue
    for c in json.loads(p.read_text(encoding="utf-8")):
      cid = c.get(lane.id_field)
      assert cid and not re.search(rf"\b{re.escape(cid)}\b", html_out), \
        f"hidden id {cid!r} leaked into the public HTML"
      checked += 1
  assert checked == 108, f"expected to check 108 hidden ids, checked {checked}"


# ---------------------------------------------------------------------------
# render_html — structure
# ---------------------------------------------------------------------------

def test_html_four_lane_labels_present(html_out):
  for label in ("Golden", "Currency", "Hallucination", "HalluHard"):
    assert label in html_out, f"Lane label {label!r} missing from HTML"


def test_html_no_canary_present(html_out):
  """Canary GUID must not appear in the HTML."""
  assert "CDS-BENCH-CANARY" not in html_out, "Canary GUID found in HTML — should be removed"
  assert "DO-NOT-TRAIN" not in html_out, "DO-NOT-TRAIN text found in HTML — should be removed"


def test_html_data_use_request_present(html_out):
  """Data use request phrasing must be present."""
  assert "Please don" in html_out or "data use request" in html_out.lower() or "training data" in html_out.lower()


def test_html_results_section_present(html_out):
  """Results section (six-source full-sample table, anonymized) must be present."""
  assert "92.6" in html_out, "top Core score missing"
  for label in ("Commercial CDS tool A", "Commercial CDS tool B", "Commercial CDS tool C"):
    assert label in html_out, f"anonymized row missing: {label}"

def test_html_results_fully_anonymized(html_out):
  """No tool/vendor/model brand names anywhere in the explainer (results table included)."""
  import re as _re
  from scripts.release.build_public import _load_vendor_tokens, _build_vendor_re
  vendor_tokens = _load_vendor_tokens()
  if not vendor_tokens:
    pytest.skip("vendor denylist not present (public clone)")
  pattern = _build_vendor_re(vendor_tokens)
  if pattern is None:
    pytest.skip("vendor denylist produced no regex (public clone)")
  hits = sorted({m.group(0).lower() for m in pattern.finditer(html_out)})
  assert not hits, f"brand names leaked into explainer HTML: {hits}"


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
  # Construct the private-path token dynamically so the literal doesn't appear in source.
  private_path = "/" + "users" + "/local/x"
  with pytest.raises(ValueError, match="private path"):
    _assert_no_private_path(f"Some text with {private_path} in it", "test")


def test_assert_no_private_path_raises_on_tmp_venv(capsys):
  # Construct path token dynamically so the literal doesn't appear in source.
  venv_path = "/tmp/" + "gem" + "venv" + "/bin/python"
  with pytest.raises(ValueError, match="private path"):
    _assert_no_private_path(f"path={venv_path}", "test")


def test_assert_no_private_path_raises_case_insensitive():
  upper_path = "/" + "USERS" + "/someone/secret"
  with pytest.raises(ValueError):
    _assert_no_private_path(upper_path, "test")


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
  for label in ("Golden", "Currency", "Hallucination", "HalluHard"):
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
  """Load every hidden id from HIDDEN_DIR and assert none appears in the static card HTML.

  We scan the case-card blocks in the static HTML. Hidden ids in .case-card
  data attributes or content is a genuine data leak.
  Skipped on a public clone where the hidden set is absent by design.
  """
  import json as _json
  import re as _re
  from pathlib import Path
  from scripts.release.lanes import HIDDEN_DIR
  if not Path(HIDDEN_DIR).exists():
    pytest.skip("hidden set not present (public clone)")

  hidden_ids: set[str] = set()
  for lane in LANES.values():
    path = Path(HIDDEN_DIR) / lane.filename
    raw = _json.loads(path.read_text())
    for c in raw:
      hidden_ids.add(c[lane.id_field])

  # Find all case-card blocks in static HTML and extract their IDs
  # Each card has: <span class="case-id">XXXX</span>
  blob_ids = set(_re.findall(r'<span class="case-id">([^<]+)</span>', html_out))

  leaked = [hid for hid in hidden_ids if hid in blob_ids]
  assert not leaked, f"Hidden ids leaked into static case cards: {leaked}"
