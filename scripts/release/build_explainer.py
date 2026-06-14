#!/usr/bin/env python
# scripts/release/build_explainer.py
"""Interactive HTML explainer + readable Markdown render of the 27 public cds-bench cases.

Run:  python -m scripts.release.build_explainer
Writes:
  index.html         — self-contained interactive explainer (repo root)
  docs/PUBLIC_CASES.md — git-diffable plain-text render of the 27 cases
"""
from __future__ import annotations

import html
import json
from pathlib import Path

from scripts.release.lanes import BENCH_DIR, LANES

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
RUBRIC_CLEAN_DIR = "release_clean/rubrics"

_DATA_USE_REQUEST = (
  "Please don't use the public sample as training data; note this is a request, "
  "not a technical control — see the held-back set below."
)

# Concise timeline data for evolution section (no markdown-parser needed).
TIMELINE: list[dict] = [
  {
    "date": "Feb 2026",
    "title": "Golden set",
    "body": (
      "<code>golden_60</code>: 60 bread-and-butter clinical queries scored on a "
      "four-dimension rubric (Clinical Accuracy /30, Completeness /30, Specificity /25, "
      "Citation Quality /15), with dual-gold scoring. Serious tools cluster at 85&ndash;90%; "
      "adversarial lanes added to separate them."
    ),
  },
  {
    "date": "Mar 2026",
    "title": "Adversarial lanes",
    "body": (
      "<code>freshness_30</code>: queries on guidelines that changed in ~12 months, each "
      "with a hand-curated <em>old_answer &rarr; new_answer (source)</em> triple anchored to "
      "real ACIP/CDC, USPSTF, ADA, ACC/AHA, and AAP updates. "
      "<code>hallucination_30</code>: clinical-safety traps (false premises, dangerous "
      "reassurance, missed-diagnosis vignettes the model must catch). Sharpest clinical-safety "
      "discriminator."
    ),
  },
  {
    "date": "Apr 2026",
    "title": "LLM-as-judge protocol",
    "body": (
      "Physician blind review reshaped judging: median-of-3 (temp 0.3) + anti-anchoring "
      "+ date-awareness + verifiable-only citations. Physician review adopted as arbiter "
      "over automated scores (Zheng et al.). Calibration ships as <code>calibrate_judge.py</code>."
    ),
  },
  {
    "date": "May 2026",
    "title": "HalluHard lane",
    "body": (
      "<code>halluhard_15</code> derived from Fan et al. (2026): reference-vs-content "
      "grounding split, rarity stratification, multi-turn self-conditioning. Orthogonal "
      "to <code>hallucination_30</code>: HalluHard tests active fabrication; "
      "<code>hallucination_30</code> tests accepting unsafe premises / missing red flags."
    ),
  },
  {
    "date": "Jun 2026",
    "title": "Working release",
    "body": (
      "27 public / 108 held-out (proportional ~20%/lane, fixed-seed stratified). "
      "SHA-256 + Merkle-root manifest of the held-out set; "
      "eval-as-a-service for hidden-set scoring. "
      "This is a working internal benchmark, not a formally peer-reviewed publication."
    ),
  },
]

REFERENCES: list[dict] = [
  {
    "key": "Fan2026",
    "cite": (
      "Fan, Z., Delsad, J., Flammarion, N., &amp; Andriushchenko, M. (2026). "
      "<em>HalluHard: A Hard Multi-Turn Hallucination Benchmark.</em> arXiv:2602.01031. "
      "&mdash; halluhard lane. (2026 preprint.)"
    ),
  },
  {
    "key": "Zheng2023",
    "cite": (
      "Zheng, L., et al. (2023). "
      "<em>Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena.</em> arXiv:2306.05685. "
      "&mdash; judge protocol."
    ),
  },
  {
    "key": "Jimenez2024",
    "cite": (
      "Jimenez, C. E., et al. (2024). "
      "<em>SWE-bench: Can Language Models Resolve Real-World GitHub Issues?</em> arXiv:2310.06770. "
      "&mdash; held-out test-set precedent."
    ),
  },
  {
    "key": "Rein2023",
    "cite": (
      "Rein, D., et al. (2023). "
      "<em>GPQA: A Graduate-Level Google-Proof Q&amp;A Benchmark.</em> arXiv:2311.12022. "
      "&mdash; held-out / google-proof precedent."
    ),
  },
  {
    "key": "Arora2025",
    "cite": (
      "Arora, R. K., Wei, J., et al. (OpenAI) (2025). "
      "<em>HealthBench: Evaluating Large Language Models Towards Improved Human Health.</em> "
      "arXiv:2505.08775. &mdash; clinical-eval lineage."
    ),
  },
  {
    "key": "Pimpale2025",
    "cite": (
      "Pimpale et al. (2025). "
      "<em>How Can I Publish My LLM Benchmark Without Giving the True Answers Away?</em> "
      "arXiv:2505.18102. &mdash; publish-without-leakage."
    ),
  },
]

# Per-lane metadata for the methodology table.
LANE_META: list[dict] = [
  {
    "id": "golden",
    "label": "Golden",
    "n_total": 60,
    "n_public": 12,
    "tests": "Clinical accuracy · Completeness · Specificity · Citation quality",
    "judge": "LLM-as-judge, median of 3, temp 0.3",
    "color": "teal",
  },
  {
    "id": "freshness",
    "label": "Freshness",
    "n_total": 30,
    "n_public": 6,
    "tests": "Currency of guideline knowledge vs. curated old&rarr;new triples",
    "judge": "PASS / PARTIAL / FAIL verdict",
    "color": "blue",
  },
  {
    "id": "hallucination",
    "label": "Hallucination",
    "n_total": 30,
    "n_public": 6,
    "tests": "Clinical-safety traps: false premises, dangerous reassurance, and missed-diagnosis vignettes the model must catch",
    "judge": "PASS / PARTIAL / FAIL + clinical_safety",
    "color": "coral",
  },
  {
    "id": "halluhard",
    "label": "HalluHard",
    "n_total": 15,
    "n_public": 3,
    "tests": "Active hallucination under rarity stress; reference + content grounding axes",
    "judge": "PASS / PARTIAL / FAIL + grounding axes",
    "color": "amber",
  },
]


# ---------------------------------------------------------------------------
# Public loader
# ---------------------------------------------------------------------------

def load_public(bench_dir: str = BENCH_DIR) -> dict[str, list[dict]]:
  """Return {lane_name: [case, ...]} for split=='public' cases only.

  Mirrors scripts.release.submit.load_hidden in structure.
  """
  result: dict[str, list[dict]] = {}
  for lane in LANES.values():
    raw = json.loads(Path(bench_dir, lane.filename).read_text(encoding="utf-8"))
    result[lane.name] = [c for c in raw if c.get("split") == "public"]
  return result


# ---------------------------------------------------------------------------
# Leak guard
# ---------------------------------------------------------------------------

def _assert_no_private_path(text: str, label: str) -> None:
  """Raise ValueError if text contains a private path fragment."""
  lowered = text.lower()
  for token in ("/users/", "/tmp/gemvenv"):
    if token in lowered:
      raise ValueError(
        f"private path token {token!r} found in {label}; refusing to write."
      )


# ---------------------------------------------------------------------------
# Shared CSS/JS design system (derived from cds_eval_explainer.html)
# ---------------------------------------------------------------------------

_CSS = """
/* ============ DESIGN SYSTEM — editorial medical journal ============ */
:root{
  --paper:#FAF6EE;
  --paper-deep:#F3EDE0;
  --card:#FFFDF7;
  --ink:#1C2733;
  --ink-soft:#54616F;
  --ink-faint:#5E6A75;
  --line:#DCD2C0;
  --line-soft:#EAE2D2;
  --teal:#0E6F66;
  --teal-deep:#0A5048;
  --teal-wash:#E4EFEA;
  --coral:#BE4438;
  --coral-wash:#F7E6E2;
  --amber:#A97B1F;
  --amber-wash:#F6EDD8;
  --green:#2F7D4F;
  --green-wash:#E4F0E6;
  --blue:#2B5BA8;
  --blue-wash:#E6EDF7;
  --serif:"Iowan Old Style","Palatino Linotype",Palatino,"Book Antiqua",Georgia,serif;
  --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
  --maxw:880px;
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
@media(prefers-reduced-motion:reduce){
  html{scroll-behavior:auto}
  *,*::before,*::after{animation-duration:.01ms!important;transition-duration:.01ms!important}
}
body{
  font-family:var(--serif);color:var(--ink);background:var(--paper);
  font-size:17px;line-height:1.65;
  background-image:radial-gradient(rgba(28,39,51,.022) 1px,transparent 1px);
  background-size:22px 22px;
}
::selection{background:var(--teal);color:#fff}

/* visible focus for keyboard users */
:focus-visible{outline:2px solid var(--teal);outline-offset:2px}

/* progress bar */
#progress{position:fixed;top:0;left:0;height:3px;background:var(--teal);width:0%;z-index:99;transition:width .1s linear}

/* nav rail */
#rail{position:fixed;right:18px;top:50%;transform:translateY(-50%);z-index:90;display:flex;flex-direction:column;gap:10px}
#rail a{display:block;width:9px;height:9px;border-radius:50%;background:var(--ink-faint);opacity:.45;position:relative;transition:all .25s}
#rail a:hover,#rail a.active{background:var(--teal);opacity:1;transform:scale(1.35)}
#rail a span{position:absolute;right:20px;top:50%;transform:translateY(-50%);white-space:nowrap;font-size:11.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-soft);background:var(--card);border:1px solid var(--line);padding:3px 9px;border-radius:3px;opacity:0;pointer-events:none;transition:opacity .2s}
#rail a:hover span{opacity:1}
@media(max-width:1080px){#rail{display:none}}

/* layout */
.wrap{max-width:var(--maxw);margin:0 auto;padding:0 28px}
section.part{padding:88px 0 30px;border-top:1px solid var(--line-soft)}
section.part:first-of-type{border-top:none}

/* typography */
.kicker{font-size:12px;letter-spacing:.22em;text-transform:uppercase;color:var(--teal);font-weight:600;display:flex;align-items:center;gap:14px;margin-bottom:18px}
.kicker::after{content:"";flex:1;height:1px;background:var(--line)}
.partnum{font-size:96px;line-height:1;color:transparent;-webkit-text-stroke:1.2px var(--line);font-weight:700;font-variant-numeric:tabular-nums;user-select:none;margin-bottom:-14px}
h1{font-size:clamp(40px,6vw,64px);line-height:1.06;font-weight:700;letter-spacing:-.015em}
h2{font-size:clamp(28px,4vw,38px);line-height:1.12;font-weight:700;letter-spacing:-.01em;margin-bottom:22px}
h3{font-size:21px;margin:34px 0 10px;font-weight:700}
h4{font-size:17px;margin:20px 0 6px}
p{margin:0 0 16px;max-width:70ch}
p.lede{font-size:21px;line-height:1.55;color:var(--ink);max-width:62ch}
.muted{color:var(--ink-soft)}
.small{font-size:14px}
.mono{font-family:var(--mono);font-size:.88em}
strong{font-weight:700}
em{font-style:italic}
a{color:var(--teal-deep)}
ul,ol{margin:0 0 16px 22px;max-width:68ch}
li{margin-bottom:7px}

/* hero */
header.hero{padding:84px 0 64px;border-bottom:1px solid var(--line)}
.hero .eyebrow{font-size:13px;letter-spacing:.26em;text-transform:uppercase;color:var(--ink-soft);margin-bottom:26px}
.hero .eyebrow b{color:var(--teal)}
.hero h1 .accent{color:var(--teal);font-style:italic}
.hero .sub{font-size:20px;color:var(--ink-soft);max-width:60ch;margin-top:24px}
.statrow{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;background:var(--line);border:1px solid var(--line);margin-top:48px}
.stat{background:var(--card);padding:20px 18px}
.stat .n{font-family:var(--mono);font-size:34px;font-weight:700;color:var(--teal-deep);line-height:1.1}
.stat .l{font-size:12.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-soft);margin-top:5px}
.hero .notice{margin-top:34px;font-size:14.5px;color:var(--ink-soft);border-left:3px solid var(--coral);padding:8px 0 8px 16px;background:var(--coral-wash)}

/* cards & callouts */
.card{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:24px 26px;margin:22px 0}
.callout{border-left:4px solid var(--teal);background:var(--teal-wash);padding:16px 20px;margin:24px 0;border-radius:0 6px 6px 0}
.callout.warn{border-color:var(--coral);background:var(--coral-wash)}
.callout.gold{border-color:var(--amber);background:var(--amber-wash)}
.callout .tag{font-size:11px;letter-spacing:.18em;text-transform:uppercase;font-weight:700;color:var(--teal-deep);display:block;margin-bottom:6px}
.callout.warn .tag{color:var(--coral)}
.callout.gold .tag{color:var(--amber)}
.callout p:last-child{margin-bottom:0}

/* tables */
table{border-collapse:collapse;width:100%;margin:18px 0;font-size:15px;background:var(--card)}
th{font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-soft);text-align:left;border-bottom:2px solid var(--ink);padding:8px 10px;font-weight:700}
td{padding:9px 10px;border-bottom:1px solid var(--line-soft);vertical-align:top}
td.num,th.num{text-align:right;font-family:var(--mono);font-size:14px;font-variant-numeric:tabular-nums}
.tablewrap{overflow-x:auto}

/* pills */
.pill{display:inline-block;font-family:var(--mono);font-size:11.5px;font-weight:700;letter-spacing:.06em;padding:2px 9px;border-radius:20px;vertical-align:1px}
.pill.teal{background:var(--teal-wash);color:var(--teal-deep);border:1px solid var(--teal)}
.pill.blue{background:var(--blue-wash);color:var(--blue);border:1px solid var(--blue)}
.pill.coral{background:var(--coral-wash);color:var(--coral);border:1px solid var(--coral)}
.pill.amber{background:var(--amber-wash);color:var(--amber);border:1px solid var(--amber)}
.pill.green{background:var(--green-wash);color:var(--green);border:1px solid var(--green)}
.pill.neutral{background:var(--paper-deep);color:var(--ink-soft);border:1px solid var(--line)}

/* case browser */
#browser-controls{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin-bottom:28px}
.filter-btn{font-family:var(--serif);font-size:14px;font-weight:700;padding:7px 16px;border-radius:4px;border:1.5px solid var(--line);background:var(--card);cursor:pointer;transition:all .15s;color:var(--ink-soft)}
.filter-btn:hover{border-color:var(--teal);color:var(--teal-deep)}
.filter-btn.active{border-color:var(--teal);background:var(--teal);color:#fff}
#search-box{font-family:var(--serif);font-size:15px;padding:7px 14px;border:1.5px solid var(--line);border-radius:4px;background:var(--card);flex:1;min-width:180px;color:var(--ink)}
#search-box:focus{outline:none;border-color:var(--teal)}
#case-count{font-size:14px;color:var(--ink-soft);font-family:var(--mono)}

.case-card{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:22px 24px;margin-bottom:16px;transition:border-color .15s}
.case-card:hover{border-color:var(--teal)}
.case-card.hidden{display:none}
.case-header{display:flex;align-items:center;gap:10px;margin-bottom:14px;flex-wrap:wrap}
.case-id{font-family:var(--mono);font-size:13px;font-weight:700;color:var(--teal-deep)}
.case-cat{font-size:12.5px;color:var(--ink-soft)}
.query-block{background:var(--paper-deep);border-left:3px solid var(--teal);padding:12px 16px;border-radius:0 4px 4px 0;margin-bottom:14px;font-size:15.5px;line-height:1.55}
.gold-fields{display:flex;flex-direction:column;gap:8px;font-size:14.5px}
.gf-row{display:grid;grid-template-columns:120px 1fr;gap:10px}
.gf-label{font-size:11.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-soft);font-weight:700;padding-top:2px;align-self:start}
.gf-value{color:var(--ink);line-height:1.5}
.gf-value code{font-family:var(--mono);font-size:13px;background:var(--paper-deep);padding:1px 5px;border-radius:3px}
.gf-arrow{color:var(--teal);font-weight:700;margin:0 4px}
@media(max-width:640px){.gf-row{grid-template-columns:1fr;gap:2px}}

/* worked examples */
.worked-card{background:var(--card);border:1.5px solid var(--teal);border-radius:6px;padding:26px 28px;margin:28px 0;box-shadow:4px 4px 0 var(--teal-wash)}
.worked-card.hidden{display:none}
.worked-card h4{color:var(--teal-deep);margin-top:0}
.rubric-block{background:var(--paper-deep);border:1px solid var(--line);border-radius:4px;padding:14px 18px;margin:14px 0;font-size:13.5px;line-height:1.55;white-space:pre-wrap;font-family:var(--mono);max-height:320px;overflow-y:auto}
.rubric-toggle{font-family:var(--serif);font-size:13.5px;font-weight:700;color:var(--teal-deep);background:none;border:1px solid var(--teal);border-radius:4px;padding:5px 14px;cursor:pointer;margin-bottom:10px;transition:all .15s}
.rubric-toggle:hover{background:var(--teal-wash)}

/* results table */
.results-table td.score{text-align:right;font-family:var(--mono);font-weight:700;color:var(--teal-deep)}

/* timeline */
#tl{display:flex;gap:0;overflow-x:auto;padding:26px 4px 18px;margin:18px -4px}
.tlnode{flex:none;width:152px;position:relative;cursor:pointer;padding-top:26px}
.tlnode::before{content:"";position:absolute;top:7px;left:0;right:0;height:2px;background:var(--line)}
.tlnode::after{content:"";position:absolute;top:0;left:8px;width:15px;height:15px;border-radius:50%;background:var(--card);border:2.5px solid var(--ink-faint);transition:all .2s}
.tlnode:hover::after,.tlnode.active::after{border-color:var(--teal);background:var(--teal)}
.tlnode .d{font-family:var(--mono);font-size:11.5px;color:var(--teal-deep);font-weight:700}
.tlnode .t{font-size:13.5px;font-weight:700;line-height:1.3;padding-right:14px}
.tldetail{border:1.5px solid var(--teal);border-radius:6px;background:var(--card);padding:20px 24px;min-height:120px}

/* footer */
footer{border-top:1px solid var(--line-soft);padding:48px 0 60px;margin-top:80px}
.footer-links{display:flex;gap:22px;flex-wrap:wrap;margin-top:18px}
.footer-links a{font-size:14.5px;color:var(--teal-deep)}

@keyframes fadeup{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
""".strip()


def _js_timeline(tl: list[dict]) -> str:
  """Render inline JS for timeline interactivity."""
  items_js = json.dumps([{"date": e["date"], "title": e["title"], "body": e["body"]} for e in tl])
  return f"""
const TL_DATA = {items_js};
const tldetail = document.getElementById('tldetail');
const tlnodes = document.querySelectorAll('.tlnode');
function showTl(i) {{
  tlnodes.forEach((n,j) => n.classList.toggle('active', i===j));
  tldetail.innerHTML = `<strong class="mono">${{TL_DATA[i].date}}</strong><h4 style="margin:6px 0 12px">${{TL_DATA[i].title}}</h4><p style="max-width:none;margin:0">${{TL_DATA[i].body}}</p>`;
  tldetail.style.animation = 'none'; void tldetail.offsetWidth; tldetail.style.animation = 'fadeup .35s ease';
}}
tlnodes.forEach((n,i) => n.addEventListener('click', () => showTl(i)));
showTl(0);
""".strip()


def _static_case_card_html(c: dict, lane_name: str) -> str:
  """Return the static HTML for one case card (mirrors JS buildCard logic)."""
  pill_colors = {"golden": "teal", "freshness": "blue", "hallucination": "coral",
                 "halluhard": "amber", "calc": "green"}
  color = pill_colors.get(lane_name, "neutral")
  lane_obj = LANES[lane_name]
  cid = c[lane_obj.id_field]
  query = c.get("query", "")
  category = c.get("category", "")

  # search text for data-text attr (JS uses this for keyword filter)
  text_search = (query + " " + cid + " " + category).lower()

  if lane_name == "golden":
    gold_html = (
      f'<div class="gf-row"><span class="gf-label">Category</span>'
      f'<span class="gf-value">{html.escape(category)}</span></div>'
      f'<div class="gf-row"><span class="gf-label">Query type</span>'
      f'<span class="gf-value"><em>Bread-and-butter CDS query &mdash; scored on 4-dimension rubric '
      f'(Accuracy / Completeness / Specificity / Citations)</em></span></div>'
    )
  elif lane_name == "freshness":
    gold_html = (
      f'<div class="gf-row"><span class="gf-label">Old answer</span>'
      f'<span class="gf-value">{html.escape(c.get("old_answer", ""))}</span></div>'
      f'<div class="gf-row"><span class="gf-label">New answer</span>'
      f'<span class="gf-value"><strong>{html.escape(c.get("new_answer", ""))}</strong></span></div>'
      f'<div class="gf-row"><span class="gf-label">Source</span>'
      f'<span class="gf-value">{html.escape(c.get("source", ""))}</span></div>'
    )
  elif lane_name == "hallucination":
    gold_html = (
      f'<div class="gf-row"><span class="gf-label">Trap</span>'
      f'<span class="gf-value"><code>{html.escape(c.get("trap", ""))}</code></span></div>'
      f'<div class="gf-row"><span class="gf-label">Expected</span>'
      f'<span class="gf-value">{html.escape(c.get("expected", ""))}</span></div>'
    )
  elif lane_name == "halluhard":
    fms = " ".join(f"<code>{html.escape(f)}</code>" for f in (c.get("fail_modes") or []))
    gold_html = (
      f'<div class="gf-row"><span class="gf-label">Rarity</span>'
      f'<span class="gf-value"><code>{html.escape(c.get("rarity", ""))}</code></span></div>'
      f'<div class="gf-row"><span class="gf-label">Grounding axis</span>'
      f'<span class="gf-value"><code>{html.escape(c.get("grounding_axis", ""))}</code></span></div>'
      f'<div class="gf-row"><span class="gf-label">Fail modes</span>'
      f'<span class="gf-value">{fms}</span></div>'
      f'<div class="gf-row"><span class="gf-label">Ground truth</span>'
      f'<span class="gf-value">{html.escape(c.get("ground_truth_source", ""))}</span></div>'
    )
  elif lane_name == "calc":
    inputs = " &middot; ".join(f"<code>{html.escape(i)}</code>" for i in (c.get("inputs_in_query") or []))
    gold_html = (
      f'<div class="gf-row"><span class="gf-label">Calculator</span>'
      f'<span class="gf-value"><code>{html.escape(c.get("calculator", ""))}</code></span></div>'
      f'<div class="gf-row"><span class="gf-label">Inputs</span>'
      f'<span class="gf-value">{inputs}</span></div>'
      f'<div class="gf-row"><span class="gf-label">Expected</span>'
      f'<span class="gf-value">{html.escape(c.get("expected_behavior", ""))}</span></div>'
    )
  else:
    gold_html = ""

  return (
    f'<div class="case-card" data-lane="{html.escape(lane_name)}" '
    f'data-text="{html.escape(text_search)}">\n'
    f'  <div class="case-header">\n'
    f'    <span class="case-id">{html.escape(cid)}</span>\n'
    f'    <span class="pill {color}">{html.escape(lane_name)}</span>\n'
    f'    <span class="case-cat">{html.escape(category)}</span>\n'
    f'  </div>\n'
    f'  <div class="query-block">{html.escape(query)}</div>\n'
    f'  <div class="gold-fields">{gold_html}</div>\n'
    f'</div>\n'
  )


def _js_case_browser(total: int) -> str:
  return f"""
// JS enhances the pre-rendered static cards for filter/search.
// With JS off, all cards are visible (no .hidden class set).
const grid = document.getElementById('case-grid');
const cards = Array.from(grid.querySelectorAll('.case-card'));
const worked = Array.from(document.querySelectorAll('.worked-card'));
const countEl = document.getElementById('case-count');
let activeFilter = 'all';
let searchVal = '';

function render() {{
  let shown = 0;
  cards.forEach(card => {{
    const laneOk = activeFilter === 'all' || card.dataset.lane === activeFilter;
    const searchOk = !searchVal || card.dataset.text.includes(searchVal);
    const visible = laneOk && searchOk;
    card.classList.toggle('hidden', !visible);
    if (visible) shown++;
  }});
  // Lane pills also filter the worked examples (by lane only, not search).
  worked.forEach(w => w.classList.toggle('hidden', activeFilter !== 'all' && w.dataset.lane !== activeFilter));
  countEl.textContent = shown + ' of {total} cases';
}}

document.querySelectorAll('.filter-btn').forEach(btn => {{
  btn.addEventListener('click', () => {{
    activeFilter = btn.dataset.lane;
    document.querySelectorAll('.filter-btn').forEach(b => {{
      const isActive = b === btn;
      b.classList.toggle('active', isActive);
      b.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    }});
    render();
  }});
}});

document.getElementById('search-box').addEventListener('input', e => {{
  searchVal = e.target.value.toLowerCase();
  render();
}});

// Initial count update (all visible on load)
countEl.textContent = '{total} of {total} cases';
""".strip()


# ---------------------------------------------------------------------------
# HTML renderer
# ---------------------------------------------------------------------------

def render_html(public: dict, *, rubrics: dict[str, str]) -> str:
  """Return the full self-contained index.html string."""

  total_public = sum(len(v) for v in public.values())

  # Build static case cards HTML
  static_cards_html = ""
  for lane_name, cases in public.items():
    for c in cases:
      static_cards_html += _static_case_card_html(c, lane_name)

  # Lane filter buttons HTML
  filter_btns = f'<button class="filter-btn active" data-lane="all" aria-pressed="true">All ({total_public})</button>\n'
  for m in LANE_META:
    if m["id"] in public:
      filter_btns += (
        f'<button class="filter-btn" data-lane="{m["id"]}" aria-pressed="false">'
        f'{m["label"]} ({m["n_public"]})</button>\n'
      )

  # Lane methodology table
  lane_rows = ""
  for m in LANE_META:
    color = m["color"]
    lane_rows += (
      f'<tr>'
      f'<td><span class="pill {color}">{html.escape(m["label"])}</span></td>'
      f'<td class="num">{m["n_total"]}</td>'
      f'<td class="num"><strong>{m["n_public"]}</strong></td>'
      f'<td>{m["tests"]}</td>'
      f'<td class="muted small">{html.escape(m["judge"])}</td>'
      f'</tr>\n'
    )

  # Timeline nodes
  tl_nodes = ""
  for i, e in enumerate(TIMELINE):
    tl_nodes += (
      f'<button class="tlnode{" active" if i == 0 else ""}" tabindex="0">'
      f'<div class="d">{html.escape(e["date"])}</div>'
      f'<div class="t">{html.escape(e["title"])}</div>'
      f'</button>\n'
    )

  # References
  ref_items = ""
  for r in REFERENCES:
    ref_items += f'<li>{r["cite"]}</li>\n'

  # Worked examples
  worked_html = _build_worked_html(public, rubrics)

  # Rubric summary for methodology section (first 18 lines of golden rubric for brevity)
  golden_rubric_preview = rubrics.get("golden", "")
  rubric_preview_lines = golden_rubric_preview.strip().split("\n")[:18]
  rubric_preview = html.escape("\n".join(rubric_preview_lines))

  html_out = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>cds-bench &mdash; Family-Medicine CDS Benchmark (Public Sample)</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' rx='18' fill='%230E6F66'/><text x='50' y='72' font-size='62' text-anchor='middle' fill='%23FAF6EE' font-family='Georgia'>&#x2713;</text></svg>">
<style>
{_CSS}
</style>
</head>
<body>
<div id="progress"></div>
<nav id="rail">
  <a href="#hero"><span>Overview</span></a>
  <a href="#results"><span>Results</span></a>
  <a href="#methodology"><span>Methodology</span></a>
  <a href="#browser"><span>Cases</span></a>
  <a href="#worked"><span>Worked Examples</span></a>
  <a href="#evolution"><span>Evolution</span></a>
  <a href="#limitations"><span>Limitations</span></a>
</nav>

<!-- ===== HERO ===== -->
<header class="hero" id="hero">
<div class="wrap">
  <div class="eyebrow">cds-bench &mdash; <b>internal family-medicine CDS benchmark</b> &mdash; public sample &middot; June 2026</div>
  <h1>The <span class="accent">cds-bench</span><br>public sample</h1>
  <p class="sub">
    {total_public} representative cases from a 135-case working benchmark for evaluating
    AI clinical-decision-support systems in US primary care.
    The 108 held-out cases are never distributed; see SUBMISSION.md for
    evaluation-as-a-service.
  </p>
  <div class="statrow">
    <div class="stat"><div class="n">135</div><div class="l">Total cases</div></div>
    <div class="stat"><div class="n">{total_public}</div><div class="l">Public (this sample)</div></div>
    <div class="stat"><div class="n">108</div><div class="l">Held out (never distributed)</div></div>
    <div class="stat"><div class="n">4</div><div class="l">Evaluation lanes</div></div>
  </div>
  <div class="hero notice">
    <strong>Data use request.</strong> {html.escape(_DATA_USE_REQUEST)}
  </div>
</div>
</header>

<main>

<!-- ===== RESULTS ===== -->
<section class="part" id="results">
<div class="wrap">
  <div class="kicker">Part 1</div>
  <div class="partnum">01</div>
  <h2>Results</h2>
  <p class="lede">
    Six clinical-decision-support tools at full sample on one internal suite
    (Core / Edge / Freshness / Hallucination) &mdash; a May 2026 snapshot.
  </p>

  <h3>Six CDS tools, full sample</h3>
  <div class="tablewrap">
  <table class="results-table">
    <thead>
      <tr><th>Source</th><th class="num">Core /100</th><th class="num">Edge /100</th><th class="num">Fresh /2</th><th class="num">Halluc P/PR/F</th></tr>
    </thead>
    <tbody>
      <tr><td>Sonnet 4.6 + prompt + 3 web searches</td><td class="score"><strong>92.6</strong></td><td class="score"><strong>95.5</strong></td><td class="score">1.80</td><td class="score">25/4/1</td></tr>
      <tr><td>Sonnet 4.6 + prompt + 1 web search</td><td class="score">87.9</td><td class="score">91.7</td><td class="score">1.77</td><td class="score"><strong>27/3/0</strong></td></tr>
      <tr><td>Sonnet 4.6 + prompt (no search)</td><td class="score">88.8</td><td class="score">84.7</td><td class="score">1.37</td><td class="score"><strong>27/3/0</strong></td></tr>
      <tr><td>OpenEvidence</td><td class="score">85.9</td><td class="score">91.4</td><td class="score">1.83</td><td class="score">22/6/2</td></tr>
      <tr><td>ChatGPT for Clinicians</td><td class="score">84.7</td><td class="score">84.7</td><td class="score"><strong>1.87</strong></td><td class="score">21/8/1</td></tr>
      <tr><td>UpToDate Expert AI</td><td class="score">65.4</td><td class="score">69.1</td><td class="score">1.70</td><td class="score">20/9/1</td></tr>
    </tbody>
  </table>
  </div>
  <p class="muted small">Core/Edge: independent Sonnet 4.6 judge vs a curated reference (0&ndash;115 normalized to 100).
  Freshness 0&ndash;2. Hallucination = PASS / PARTIAL / FAIL over 30 false-premise traps. Higher is better except FAIL.</p>

  <h4>What it shows</h4>
  <ul>
    <li><strong>The structured prompt is the biggest single lever</strong> &mdash; raw model &rarr; model + clinical prompt is <strong>+17 on Core</strong> (reproduces on GPT-5.4 +20, Opus 4.6 +17, Gemini 3.1 +12). Pick the prompt before the model.</li>
    <li><strong>One web search is the best value</strong> &mdash; Core stays flat, but Freshness +0.4 and Edge +7. The third search buys a little quality and costs the zero-hallucination floor.</li>
    <li><strong>OpenEvidence and ChatGPT for Clinicians are clinical-quality peers</strong> (~85 Core); <strong>ChatGPT for Clinicians leads freshness (1.87)</strong>. OE is bimodal (mostly 85&ndash;100, ~5% catastrophic misses), so its full-sample mean is below the outlier-trimmed "92" sometimes quoted.</li>
    <li><strong>UpToDate Expert AI trails by ~20 points on Core/Edge</strong> &mdash; partly a real gap, partly a style penalty (its concise-bullet surface scores lower on a prose-oriented rubric; see caveats).</li>
    <li>Only the no-search and 1-search prompt configs held the <strong>0-hallucination floor</strong> at n=30; every retrieval-heavy tool (incl. OE, ChatGPT for Clinicians, UpToDate) picked up at least one fail.</li>
  </ul>

  <div class="callout warn">
    <span class="tag">Caveats</span>
    <p>May-2026 snapshot; models, harnesses, and guidelines all move &mdash; rankings shift on re-run.</p>
    <p>n=30 on freshness/hallucination: differences of 5+ on Core or 0.10+ on Freshness are reliable; tighter ones aren't. The hallucination set is 30 constructed traps &mdash; a relative comparison, not a generic lie-rate.</p>
    <p>Single LLM judge (Sonnet 4.6, ~93% physician-panel agreement) against a prose-style curated reference &mdash; this favors prose tools and penalizes UpToDate's concise-bullet output. Web tools tested through one personal subscription each.</p>
    <p style="margin-bottom:0">These results come from the internal eval program cds-bench derives from (its suite included an Edge set); the public cds-bench sample ships the Golden, Freshness, Hallucination, and HalluHard lanes.</p>
  </div>
</div>
</section>

<!-- ===== METHODOLOGY ===== -->
<section class="part" id="methodology">
<div class="wrap">
  <div class="kicker">Part 2</div>
  <div class="partnum">02</div>
  <h2>Methodology</h2>
  <p class="lede">
    Four lanes, a fixed-seed proportional split, a calibrated LLM-as-judge protocol,
    and an honest account of what the held-back set does and doesn&rsquo;t do.
  </p>

  <h3>Lane overview</h3>
  <div class="tablewrap">
  <table>
    <thead>
      <tr>
        <th>Lane</th><th class="num">Total</th><th class="num">Public</th>
        <th>What it tests</th><th>Scoring method</th>
      </tr>
    </thead>
    <tbody>
{lane_rows}    </tbody>
  </table>
  </div>
  <p class="muted small">Hallucination lane note: orthogonal to HalluHard &mdash; HalluHard
  tests active fabrication; this lane tests accepting unsafe premises / missing red flags.</p>

  <h3>Fixed-seed proportional split</h3>
  <div class="card">
    <p>Public cases are selected by a deterministic stratified sample (seed 20260614).
    Each lane contributes ~20% of its cases to the public set, stratified by
    <code>category</code>.
    Forced-public anchors ensure the showcase cases always land in the
    public set regardless of stratification.</p>
    <p style="margin-bottom:0">The remaining ~80% are held out and covered by a
    SHA-256 + Merkle-root manifest (<code>HIDDEN_MANIFEST.sha256</code> /
    <code>HIDDEN_MANIFEST.meta.json</code>), enabling verifiable integrity
    without distribution.</p>
  </div>

  <h3>What we hold back &mdash; and what it does and doesn&rsquo;t do</h3>
  <ul>
    <li><strong>108 of 135 cases are held out and never distributed</strong> &mdash;
        limits direct optimization against the full set and the gold/rubric pairings.</li>
    <li><strong>Honest limit:</strong> the held-out <em>clinical knowledge</em> (e.g., a BP
        threshold) is public and already in any model&rsquo;s training data; holding our items
        back does NOT stop a model from knowing the answer. What it protects is the specific
        phrasings, traps, and gold/rubric pairings from being memorized and gamed.</li>
    <li><strong>Integrity manifest:</strong> SHA-256 + Merkle root of the held-out set,
        published at release, lets a third party verify the test set wasn&rsquo;t altered
        after publication.</li>
    <li><strong>Eval-as-a-service:</strong> hidden-set scoring is run by the maintainer;
        hidden cases and gold never leave.</li>
  </ul>

  <h3>Judge protocol</h3>
  <div class="card">
    <p><strong>Median-of-3, temperature 0.3.</strong> Each candidate response is
    scored by three independent judge calls; the median score per dimension is taken
    to reduce variance.</p>
    <p><strong>Anti-anchoring.</strong> Judge calls are randomized; no judge sees
    another&rsquo;s score before scoring.</p>
    <p><strong>Date-aware.</strong> The judge is told the evaluation date and
    instructed not to penalize citations for recency. Newer guideline updates
    that supersede the gold standard are noted, not penalized.</p>
    <p style="margin-bottom:0"><strong>Verifiable-only citations.</strong> Vague
    attribution (&ldquo;per AHA guidelines&rdquo;) does not count as a citation; the judge
    requires a named document, year, and link or DOI.</p>
  </div>

  <h3>Golden rubric (excerpt)</h3>
  <p class="muted small">First 18 lines of the blinded judge rubric shipped with this release.</p>
  <pre class="rubric-block">{rubric_preview}</pre>
</div>
</section>

<!-- ===== CASE BROWSER ===== -->
<section class="part" id="browser">
<div class="wrap">
  <div class="kicker">Part 3</div>
  <div class="partnum">03</div>
  <h2>Case browser</h2>
  <p class="lede">All {total_public} public cases. Filter by lane or search by keyword.</p>

  <div id="browser-controls">
    {filter_btns}
    <input id="search-box" type="search" placeholder="Search cases&hellip;" aria-label="Search cases">
    <span id="case-count">{total_public} of {total_public} cases</span>
  </div>
  <div id="case-grid">
{static_cards_html}  </div>
</div>
</section>

<!-- ===== WORKED EXAMPLES ===== -->
<section class="part" id="worked">
<div class="wrap">
  <div class="kicker">Part 4</div>
  <div class="partnum">04</div>
  <h2>Worked examples</h2>
  <p class="lede">
    Showcase cases &mdash; one per lane &mdash; shown end-to-end: query, rubric, and gold.
    Transcript + score are shown when a curated overlay is available.
  </p>
{worked_html}
</div>
</section>

<!-- ===== EVOLUTION ===== -->
<section class="part" id="evolution">
<div class="wrap">
  <div class="kicker">Part 5</div>
  <div class="partnum">05</div>
  <h2>Evolution &amp; references</h2>
  <p class="lede">
    The benchmark grew in phases from Feb&ndash;Jun 2026.
    See <a href="docs/EVOLUTION.md"><code>docs/EVOLUTION.md</code></a> for the full narrative.
  </p>

  <div id="tl">
{tl_nodes}  </div>
  <div class="tldetail" id="tldetail"></div>

  <h3>References</h3>
  <ul>
{ref_items}  </ul>
</div>
</section>

<!-- ===== LIMITATIONS ===== -->
<section class="part" id="limitations">
<div class="wrap">
  <div class="kicker">Part 6</div>
  <div class="partnum">06</div>
  <h2>Limitations</h2>
  <p class="lede">
    This is a working internal benchmark, not a peer-reviewed publication.
    Known limitations:
  </p>
  <ul>
    <li><strong>Single-author authored and curated</strong> (LLM-assisted); no external
        clinician validation cohort yet.</li>
    <li><strong>Small n per lane</strong> (3&ndash;12 public; 12&ndash;60 total) &mdash;
        per-lane numbers are noisy.</li>
    <li><strong>LLM-as-judge is a screening tool, not ground truth</strong>; risk of
        same-model-family grading bias.</li>
    <li><strong>Freshness items perish</strong> and require periodic re-validation
        (per-case <code>validated</code> dates in the source data).</li>
    <li><strong>Gold may overlap models&rsquo; training sources</strong> (circularity) &mdash;
        guideline knowledge is public and likely in any model&rsquo;s training data.</li>
    <li><strong>Not IRB-reviewed, not prospective, no patient-outcome validation.</strong></li>
  </ul>
</div>
</section>

</main>

<!-- ===== FOOTER ===== -->
<footer>
<div class="wrap">
  <p class="muted small">
    <strong>cds-bench</strong> public sample &mdash; {total_public} of 135 cases &mdash; June 2026.
    Data: CC BY-NC-ND 4.0. Code: MIT.
    {html.escape(_DATA_USE_REQUEST)}
  </p>
  <div class="footer-links">
    <a href="docs/EVOLUTION.md">Evolution</a>
    <a href="SUBMISSION.md">Submission</a>
    <a href="docs/PUBLIC_CASES.md">PUBLIC_CASES.md</a>
    <a href="HIDDEN_MANIFEST.sha256">Hidden manifest</a>
    <a href="LICENSE">License</a>
  </div>
</div>
</footer>

<script>
// ── Progress bar ──────────────────────────────────────────────────────────
(function() {{
  const bar = document.getElementById('progress');
  function upd() {{
    const s = document.documentElement;
    const pct = 100 * s.scrollTop / (s.scrollHeight - s.clientHeight);
    bar.style.width = Math.min(100, pct) + '%';
  }}
  document.addEventListener('scroll', upd, {{passive:true}});
}})();

// ── Nav rail ──────────────────────────────────────────────────────────────
(function() {{
  const links = document.querySelectorAll('#rail a');
  const sections = Array.from(links).map(l => document.querySelector(l.getAttribute('href')));
  function upd() {{
    const y = window.scrollY + 120;
    let active = 0;
    sections.forEach((s, i) => {{ if (s && s.offsetTop <= y) active = i; }});
    links.forEach((l, i) => l.classList.toggle('active', i === active));
  }}
  document.addEventListener('scroll', upd, {{passive:true}});
  upd();
}})();

// ── Timeline ─────────────────────────────────────────────────────────────
{_js_timeline(TIMELINE)}

// ── Case browser (JS enhances static cards) ───────────────────────────────
{_js_case_browser(total_public)}

// ── Rubric toggles ───────────────────────────────────────────────────────
document.querySelectorAll('.rubric-toggle').forEach(btn => {{
  btn.addEventListener('click', () => {{
    const target = document.getElementById(btn.dataset.target);
    const shown = target.style.display !== 'none';
    target.style.display = shown ? 'none' : 'block';
    btn.textContent = shown ? 'Show rubric' : 'Hide rubric';
  }});
}});
</script>
</body>
</html>"""

  _assert_no_private_path(html_out, "render_html output")
  return html_out


def _build_worked_html(public: dict, rubrics: dict[str, str]) -> str:
  """Build HTML for the showcase worked-example cards."""
  from scripts.release.lanes import SHOWCASE_IDS, WORKED_DIR
  showcase_map: dict[str, tuple[str, dict]] = {}
  for lane_name, cases in public.items():
    lane = LANES[lane_name]
    for c in cases:
      cid = c[lane.id_field]
      if cid in SHOWCASE_IDS:
        showcase_map[cid] = (lane_name, c)

  color_map = {"golden": "teal", "freshness": "blue", "hallucination": "coral",
               "halluhard": "amber", "calc": "green"}
  label_map = {"golden": "Golden", "freshness": "Freshness",
               "hallucination": "Hallucination", "halluhard": "HalluHard", "calc": "Calc"}

  cards = ""
  for cid in SHOWCASE_IDS:
    if cid not in showcase_map:
      cards += f'<div class="callout warn"><span class="tag">Missing</span><p>Showcase case {html.escape(cid)} not found in public set.</p></div>\n'
      continue
    lane_name, c = showcase_map[cid]
    color = color_map.get(lane_name, "neutral")
    label = label_map.get(lane_name, lane_name)
    lane_obj = LANES[lane_name]
    query = c.get("query", "")

    gold_html = _gold_fields_html(lane_name, c)

    rubric_text = rubrics.get(lane_name, "")
    if rubric_text:
      rubric_id = f"rubric-{cid}"
      rubric_section = f"""
<button class="rubric-toggle" data-target="{rubric_id}">Show rubric</button>
<pre class="rubric-block" id="{rubric_id}" style="display:none">{html.escape(rubric_text[:3000])}</pre>"""
    else:
      rubric_section = '<p class="muted small"><em>Deterministic lane &mdash; no judge rubric.</em></p>'

    # Worked overlay (graceful absence)
    overlay_path = Path(WORKED_DIR) / f"{cid}.json"
    overlay_html = ""
    if overlay_path.exists():
      try:
        overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
        transcript = html.escape(str(overlay.get("transcript", "")))
        scores = html.escape(json.dumps(overlay.get("scores", {}), indent=2))
        overlay_html = f"""
<h4 style="margin-top:24px">Transcript</h4>
<pre class="rubric-block">{transcript[:2000]}</pre>
<h4>Scores</h4>
<pre class="rubric-block">{scores}</pre>"""
      except Exception:
        overlay_html = '<p class="muted small"><em>Overlay parse error.</em></p>'

    cards += f"""
<div class="worked-card" data-lane="{html.escape(lane_name)}">
  <div class="case-header">
    <span class="case-id">{html.escape(cid)}</span>
    <span class="pill {color}">{html.escape(label)}</span>
    <span class="case-cat">{html.escape(c.get('category', ''))}</span>
  </div>
  <h4>Query</h4>
  <div class="query-block">{html.escape(query)}</div>
  <h4 style="margin-top:18px">Gold</h4>
  <div class="gold-fields">{gold_html}</div>
  <h4 style="margin-top:18px">Judge rubric</h4>
  {rubric_section}
  {overlay_html}
</div>
"""

  return cards


def _gold_fields_html(lane_name: str, c: dict) -> str:
  """Return HTML for lane-specific gold fields in worked examples."""
  if lane_name == "golden":
    return (
      '<div class="gf-row"><span class="gf-label">Category</span>'
      f'<span class="gf-value">{html.escape(c.get("category", ""))}</span></div>'
      '<div class="gf-row"><span class="gf-label">Scored on</span>'
      '<span class="gf-value">Accuracy /30 &middot; Completeness /30 &middot; Specificity /25 &middot; Citations /15</span></div>'
    )
  elif lane_name == "freshness":
    return (
      '<div class="gf-row"><span class="gf-label">Old answer</span>'
      f'<span class="gf-value">{html.escape(c.get("old_answer", ""))}</span></div>'
      '<div class="gf-row"><span class="gf-label">New answer</span>'
      f'<span class="gf-value"><strong>{html.escape(c.get("new_answer", ""))}</strong></span></div>'
      '<div class="gf-row"><span class="gf-label">Source</span>'
      f'<span class="gf-value">{html.escape(c.get("source", ""))}</span></div>'
    )
  elif lane_name == "hallucination":
    return (
      '<div class="gf-row"><span class="gf-label">Trap</span>'
      f'<span class="gf-value"><code>{html.escape(c.get("trap", ""))}</code></span></div>'
      '<div class="gf-row"><span class="gf-label">Expected</span>'
      f'<span class="gf-value">{html.escape(c.get("expected", ""))}</span></div>'
    )
  elif lane_name == "halluhard":
    fms = " &middot; ".join(f"<code>{html.escape(f)}</code>" for f in (c.get("fail_modes") or []))
    return (
      '<div class="gf-row"><span class="gf-label">Rarity</span>'
      f'<span class="gf-value"><code>{html.escape(c.get("rarity", ""))}</code></span></div>'
      '<div class="gf-row"><span class="gf-label">Grounding</span>'
      f'<span class="gf-value"><code>{html.escape(c.get("grounding_axis", ""))}</code></span></div>'
      f'<div class="gf-row"><span class="gf-label">Fail modes</span><span class="gf-value">{fms}</span></div>'
      '<div class="gf-row"><span class="gf-label">Ground truth</span>'
      f'<span class="gf-value">{html.escape(c.get("ground_truth_source", ""))}</span></div>'
    )
  elif lane_name == "calc":
    inputs = " &middot; ".join(f"<code>{html.escape(i)}</code>" for i in (c.get("inputs_in_query") or []))
    return (
      '<div class="gf-row"><span class="gf-label">Calculator</span>'
      f'<span class="gf-value"><code>{html.escape(c.get("calculator", ""))}</code></span></div>'
      f'<div class="gf-row"><span class="gf-label">Inputs</span><span class="gf-value">{inputs}</span></div>'
      '<div class="gf-row"><span class="gf-label">Expected</span>'
      f'<span class="gf-value">{html.escape(c.get("expected_behavior", ""))}</span></div>'
    )
  return ""


# ---------------------------------------------------------------------------
# Markdown renderer
# ---------------------------------------------------------------------------

def render_markdown(public: dict) -> str:
  """Return docs/PUBLIC_CASES.md content: 27 cases grouped by lane."""
  total = sum(len(v) for v in public.values())
  lines: list[str] = [
    f"# cds-bench public sample ({total} of 135) — data use request",
    "",
    f"> {_DATA_USE_REQUEST}",
    "",
    "---",
    "",
  ]

  lane_labels = {"golden": "Golden", "freshness": "Freshness",
                 "hallucination": "Hallucination", "halluhard": "HalluHard", "calc": "Calc"}
  lane_descs = {
    "golden": "Bread-and-butter CDS queries scored on a 4-dimension rubric.",
    "freshness": "Queries on recently-changed guidelines; hand-curated old → new triples.",
    "hallucination": "Clinical-safety traps: false premises, dangerous reassurance, and missed-diagnosis vignettes the model must catch. Orthogonal to HalluHard (which tests active fabrication).",
    "halluhard": "Hard active-hallucination cases with reference + content grounding axes.",
    "calc": "Deterministic calculator/dosing checks; expected behavior is to refuse to compute.",
  }

  for lane_name, cases in public.items():
    label = lane_labels.get(lane_name, lane_name)
    desc = lane_descs.get(lane_name, "")
    count = len(cases)
    lines += [
      f"## {label} ({count} public cases)",
      "",
      desc,
      "",
    ]
    lane_obj = LANES[lane_name]
    for c in cases:
      cid = c[lane_obj.id_field]
      query = c.get("query", "")
      lines += [
        f"### {cid}",
        "",
        f"**Query:** {query}",
        "",
      ]
      if lane_name == "freshness":
        lines += [
          f"- **Old answer:** {c.get('old_answer', '')}",
          f"- **New answer:** {c.get('new_answer', '')}",
          f"- **Source:** {c.get('source', '')}",
          "",
        ]
      elif lane_name == "hallucination":
        lines += [
          f"- **Trap:** `{c.get('trap', '')}`",
          f"- **Expected:** {c.get('expected', '')}",
          "",
        ]
      elif lane_name == "halluhard":
        fms = ", ".join(f"`{f}`" for f in (c.get("fail_modes") or []))
        lines += [
          f"- **Rarity:** `{c.get('rarity', '')}`",
          f"- **Grounding axis:** `{c.get('grounding_axis', '')}`",
          f"- **Fail modes:** {fms}",
          f"- **Ground truth source:** {c.get('ground_truth_source', '')}",
          "",
        ]
      elif lane_name == "calc":
        inputs = ", ".join(f"`{i}`" for i in (c.get("inputs_in_query") or []))
        lines += [
          f"- **Calculator:** `{c.get('calculator', '')}`",
          f"- **Inputs in query:** {inputs}",
          f"- **Expected behavior:** {c.get('expected_behavior', '')}",
          "",
        ]
      else:  # golden
        lines += [
          f"- **Category:** {c.get('category', '')}",
          f"- **Rubric:** Accuracy /30 · Completeness /30 · Specificity /25 · Citations /15",
          "",
        ]

    lines += ["---", ""]

  md = "\n".join(lines)
  _assert_no_private_path(md, "render_markdown output")
  return md


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
  """Write index.html and docs/PUBLIC_CASES.md."""
  public = load_public()
  total = sum(len(v) for v in public.values())
  print(f"Loaded {total} public cases across {len(public)} lanes.")

  # Read blinded rubrics
  rubrics: dict[str, str] = {}
  for lane_name, lane in LANES.items():
    if lane.judge_rubric:
      rubric_path = Path(lane.judge_rubric)
      if rubric_path.exists():
        rubrics[lane_name] = rubric_path.read_text(encoding="utf-8")
      else:
        print(f"  Warning: rubric not found: {rubric_path}")

  html_out = render_html(public, rubrics=rubrics)
  md_out = render_markdown(public)

  # Write committed copies
  repo_root = Path(__file__).parent.parent.parent
  index_path = repo_root / "index.html"
  md_path = repo_root / "docs" / "PUBLIC_CASES.md"

  index_path.write_text(html_out, encoding="utf-8")
  print(f"Wrote {index_path} ({len(html_out):,} bytes)")

  md_path.parent.mkdir(parents=True, exist_ok=True)
  md_path.write_text(md_out, encoding="utf-8")
  print(f"Wrote {md_path} ({len(md_out):,} bytes)")


if __name__ == "__main__":
  main()
