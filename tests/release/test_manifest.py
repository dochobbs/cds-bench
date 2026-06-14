# tests/release/test_manifest.py
from scripts.release.manifest import canonical_bytes, case_hash, merkle_root

def test_canonical_excludes_split():
  a = {"id": "X1", "query": "q", "split": "hidden"}
  b = {"id": "X1", "query": "q", "split": "public"}
  assert canonical_bytes(a) == canonical_bytes(b)

def test_canonical_is_key_order_independent():
  a = {"id": "X1", "query": "q"}
  b = {"query": "q", "id": "X1"}
  assert canonical_bytes(a) == canonical_bytes(b)

def test_canonical_excludes_canary_and_notice():
  bare = {"id": "X1", "query": "q"}
  stamped = {"id": "X1", "query": "q", "canary": "CANARY-XYZ", "_notice": "do not train"}
  assert canonical_bytes(bare) == canonical_bytes(stamped)
  assert case_hash(bare) == case_hash(stamped)

def test_canonical_is_compact_utf8():
  out = canonical_bytes({"id": "X1", "q": "café"})
  assert isinstance(out, bytes)
  assert b", " not in out and b'": ' not in out  # compact separators

def test_case_hash_is_stable_sha256_hex():
  h = case_hash({"id": "X1", "query": "q", "split": "hidden"})
  assert len(h) == 64 and all(c in "0123456789abcdef" for c in h)
  assert h == case_hash({"id": "X1", "query": "q", "split": "public"})

def test_different_content_different_hash():
  assert case_hash({"id": "X1", "query": "a"}) != case_hash({"id": "X1", "query": "b"})

def test_merkle_root_deterministic_and_order_sensitive():
  leaves = ["aa"*32, "bb"*32, "cc"*32]
  assert merkle_root(leaves) == merkle_root(leaves)
  assert len(merkle_root(leaves)) == 64
  assert merkle_root(["aa"*32, "bb"*32]) != merkle_root(["bb"*32, "aa"*32])

def test_merkle_root_empty_is_sha256_of_empty():
  import hashlib
  assert merkle_root([]) == hashlib.sha256(b"").hexdigest()

def test_merkle_root_changes_when_a_leaf_changes():
  base = ["aa"*32, "bb"*32]
  changed = ["aa"*32, "bc"*32]
  assert merkle_root(base) != merkle_root(changed)

def test_merkle_root_single_leaf_equals_leaf():
  assert merkle_root(["aa"*32]) == "aa"*32

import json as _json, pathlib
from scripts.release.manifest import build_manifest

def test_build_manifest_hidden_only(tmp_path):
  out = tmp_path / "cds-bench"
  out.mkdir()
  meta = build_manifest(str(out), seed=20260614, generated="2026-06-14")
  lines = (out / "HIDDEN_MANIFEST.sha256").read_text().strip().splitlines()
  assert len(lines) == 116, f"expected 116 hidden, got {len(lines)}"
  # sha256sum format: "<64hex>  <lane>/<id>"
  for ln in lines:
    h, name = ln.split("  ", 1)
    assert len(h) == 64 and "/" in name
  m = _json.loads((out / "HIDDEN_MANIFEST.meta.json").read_text())
  assert m["hidden_count"] == 116 and len(m["merkle_root"]) == 64
  assert m["seed"] == 20260614 and m["generated"] == "2026-06-14"

def test_manifest_lists_no_public_ids(tmp_path):
  out = tmp_path / "cds-bench"; out.mkdir()
  build_manifest(str(out), seed=20260614, generated="2026-06-14")
  lines = (out / "HIDDEN_MANIFEST.sha256").read_text().strip().splitlines()
  # Extract exact id token (after the "<lane>/" prefix)
  names = {ln.split("  ", 1)[1].split("/", 1)[1] for ln in lines}
  for fp_id in ("G52", "F19", "H11", "HH08", "C01"):
    assert fp_id not in names, f"forced-public {fp_id} appeared in hidden manifest"
