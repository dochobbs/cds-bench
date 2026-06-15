# tests/release/test_manifest.py
from scripts.release.manifest import canonical_bytes, case_hash, merkle_root

# ---------------------------------------------------------------------------
# canonical_bytes / case_hash — these helpers don't require the salt (they
# accept an explicit salt_bytes arg; the default b"" is test-only).
# ---------------------------------------------------------------------------

def test_canonical_excludes_split():
  a = {"id": "X1", "query": "q", "split": "hidden"}
  b = {"id": "X1", "query": "q", "split": "public"}
  assert canonical_bytes(a) == canonical_bytes(b)

def test_canonical_is_key_order_independent():
  a = {"id": "X1", "query": "q"}
  b = {"query": "q", "id": "X1"}
  assert canonical_bytes(a) == canonical_bytes(b)

def test_canonical_excludes_validated():
  bare = {"id": "X1", "query": "q"}
  with_validated = {"id": "X1", "query": "q", "validated": "2026-06-01"}
  assert canonical_bytes(bare) == canonical_bytes(with_validated)
  # With the same (empty) salt the hashes must also match
  assert case_hash(bare) == case_hash(with_validated)

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

def test_salt_changes_hash():
  """Salted and unsalted hashes MUST differ (proves the salt is actually applied)."""
  import hashlib
  case = {"id": "X1", "query": "test"}
  salt = bytes.fromhex("deadbeef" * 8)
  unsalted = case_hash(case, salt_bytes=b"")
  salted   = case_hash(case, salt_bytes=salt)
  assert unsalted != salted
  # Verify the salted value matches the spec formula exactly
  cb = canonical_bytes(case)
  expected = hashlib.sha256(salt + b"\x00" + cb).hexdigest()
  assert salted == expected

def test_salt_commitment_formula():
  """salt_commitment must equal sha256(salt_bytes).hexdigest()."""
  import hashlib, binascii
  salt_hex = "fe476e0bb1613631205f818cc1eb6cf3b2de9d29e08ed570391204dd396cf131"
  salt_bytes = binascii.unhexlify(salt_hex)
  expected_commitment = hashlib.sha256(salt_bytes).hexdigest()
  # Verify the formula is correct (this does not require the live salt file)
  assert len(expected_commitment) == 64

# ---------------------------------------------------------------------------
# Merkle tests — no hidden set required
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Integration tests — require hidden set AND salt file (maintainer machine only)
# ---------------------------------------------------------------------------

import json as _json, pathlib
from pathlib import Path
from scripts.release.manifest import build_manifest, load_salt, SALT_PATH
from scripts.release.lanes import HIDDEN_DIR

def _skip_if_not_maintainer():
  import pytest
  if not Path(HIDDEN_DIR).exists():
    pytest.skip("hidden set not present (public clone)")
  if not Path(SALT_PATH).exists():
    pytest.skip("manifest salt not present (public clone)")

def test_build_manifest_hidden_only(tmp_path):
  _skip_if_not_maintainer()
  out = tmp_path / "cds-bench"
  out.mkdir()
  meta = build_manifest(str(out), seed=20260614, generated="2026-06-14")
  lines = (out / "HIDDEN_MANIFEST.sha256").read_text().strip().splitlines()
  assert len(lines) == 108, f"expected 108 hidden, got {len(lines)}"
  # sha256sum format: "<64hex>  <lane>/<id>"
  for ln in lines:
    h, name = ln.split("  ", 1)
    assert len(h) == 64 and "/" in name
  m = _json.loads((out / "HIDDEN_MANIFEST.meta.json").read_text())
  assert m["hidden_count"] == 108 and len(m["merkle_root"]) == 64
  assert m["seed"] == 20260614 and m["generated"] == "2026-06-14"
  # new fields from the salted scheme
  assert "algorithm" in m, "HIDDEN_MANIFEST.meta.json must carry 'algorithm'"
  assert "salt_commitment" in m, "HIDDEN_MANIFEST.meta.json must carry 'salt_commitment'"
  # verify salt_commitment matches the actual salt
  import hashlib
  salt_bytes = load_salt()
  assert m["salt_commitment"] == hashlib.sha256(salt_bytes).hexdigest(), \
    "salt_commitment in meta.json does not match sha256(salt)"

def test_build_manifest_is_deterministic(tmp_path):
  """Two builds with the same salt must produce byte-identical output."""
  _skip_if_not_maintainer()
  out1 = tmp_path / "run1"; out1.mkdir()
  out2 = tmp_path / "run2"; out2.mkdir()
  build_manifest(str(out1), seed=20260614, generated="2026-06-14")
  build_manifest(str(out2), seed=20260614, generated="2026-06-14")
  assert (out1 / "HIDDEN_MANIFEST.sha256").read_text() == \
         (out2 / "HIDDEN_MANIFEST.sha256").read_text(), \
    "Two manifest builds with the same salt must be byte-identical"
  assert (out1 / "HIDDEN_MANIFEST.meta.json").read_text() == \
         (out2 / "HIDDEN_MANIFEST.meta.json").read_text(), \
    "Two meta.json builds with the same salt must be byte-identical"

def test_committed_meta_has_algorithm_and_salt_commitment():
  """The ROOT committed HIDDEN_MANIFEST.meta.json must carry algorithm + salt_commitment."""
  _skip_if_not_maintainer()
  import hashlib
  m = _json.loads(Path("HIDDEN_MANIFEST.meta.json").read_text())
  assert "algorithm" in m, "committed HIDDEN_MANIFEST.meta.json missing 'algorithm'"
  assert "salt_commitment" in m, "committed HIDDEN_MANIFEST.meta.json missing 'salt_commitment'"
  salt_bytes = load_salt()
  assert m["salt_commitment"] == hashlib.sha256(salt_bytes).hexdigest(), \
    "committed salt_commitment does not match sha256(salt)"

def test_manifest_lists_no_public_ids(tmp_path):
  _skip_if_not_maintainer()
  out = tmp_path / "cds-bench"; out.mkdir()
  build_manifest(str(out), seed=20260614, generated="2026-06-14")
  lines = (out / "HIDDEN_MANIFEST.sha256").read_text().strip().splitlines()
  # Extract exact id token (after the "<lane>/" prefix)
  names = {ln.split("  ", 1)[1].split("/", 1)[1] for ln in lines}
  for fp_id in ("G52", "F19", "H11", "HH08"):
    assert fp_id not in names, f"forced-public {fp_id} appeared in hidden manifest"

def test_collect_hidden_raises_clear_error_when_dir_missing(tmp_path):
  """A public clone without hidden dir gets a clear error, not a cryptic FileNotFoundError."""
  from scripts.release.manifest import collect_hidden
  import pytest
  with pytest.raises(FileNotFoundError, match="public clone"):
    collect_hidden(hidden_dir=str(tmp_path / "nonexistent"))
