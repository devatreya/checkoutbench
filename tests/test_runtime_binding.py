"""Integrity controls, not model-performance tests."""

import copy
import hashlib
import json

import pytest

from backend.research import runtime_binding as rb
from scenarios.research import digest


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    monkeypatch.setattr(rb, "ROOT", tmp_path)
    canonical = {"T01": "original-scenario", "V3-G01": "another-scenario"}
    monkeypatch.setattr(rb, "current_canonical_hashes", lambda: dict(canonical))
    protected = {
        "research/release.json": b"immutable release\n",
        "scenarios/catalog.py": b"original catalog\n",
        "scenarios/v21.py": b"original scenarios\n",
        "checkout_fixtures/checkout.js": b"original labels\n",
    }
    for name, content in protected.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    file_hashes = {name: hashlib.sha256(content).hexdigest() for name, content in protected.items()}
    baseline = {"canonical_scenario_hashes": canonical, "file_hashes": file_hashes}
    (tmp_path / rb.BASELINE_FILE).write_text(json.dumps(baseline))
    original = {name: value for name, value in file_hashes.items() if name != "research/release.json"}
    original["backend/browser/execution.py"] = "old-browser"
    manifest = {"release_hash": "release", "manifest_hash": "manifest",
                "source_hashes": original, "source_hash": digest(original)}
    current = {**original, "backend/browser/execution.py": "new-browser",
               "backend/research/runtime_binding.py": "new-audit-module"}
    return tmp_path, manifest, current, canonical


def approve(runtime, **kwargs):
    root, manifest, current, _ = runtime
    binding = rb.create_binding(manifest, current, review={
        "status": "approved", "reviewer": "test-reviewer", "summary": "Reviewed test runtime changes",
    }, **kwargs)
    (root / rb.BINDING_FILE).write_text(json.dumps(binding))
    return binding


def test_original_runtime_needs_no_new_audit(runtime):
    _, manifest, _, _ = runtime
    assert rb.audited_runtime(manifest, manifest["source_hashes"]) is None


def test_missing_or_pending_audit_never_self_approves(runtime):
    root, manifest, current, _ = runtime
    with pytest.raises(ValueError, match="explicit reviewed"):
        rb.audited_runtime(manifest, current)
    pending = rb.create_binding(manifest, current)
    assert pending["review"] == {"status": "pending"}
    (root / rb.BINDING_FILE).write_text(json.dumps(pending))
    with pytest.raises(ValueError, match="final review"):
        rb.audited_runtime(manifest, current)


def test_exact_reviewed_runtime_has_distinct_binding(runtime):
    _, manifest, current, _ = runtime
    binding = approve(runtime)
    assert rb.audited_runtime(manifest, current) == binding
    assert binding["source_hash"] != manifest["source_hash"]
    assert binding["changes"]["backend/browser/execution.py"] == {"before": "old-browser", "after": "new-browser"}
    assert binding["scenario_integrity"]["canonical_scenario_count"] == 2


@pytest.mark.parametrize("mutate", ["source", "release", "manifest", "binding", "removed_file"])
def test_any_drift_rejects_existing_binding(runtime, mutate):
    root, manifest, current, _ = runtime
    binding = approve(runtime)
    manifest = copy.deepcopy(manifest)
    current = dict(current)
    if mutate == "source":
        current["backend/browser/execution.py"] = "unreviewed-browser"
    elif mutate == "release":
        manifest["release_hash"] = "different-release"
    elif mutate == "manifest":
        manifest["manifest_hash"] = "different-manifest"
    elif mutate == "binding":
        binding["review"]["summary"] = "tampered"
        (root / rb.BINDING_FILE).write_text(json.dumps(binding))
    else:
        current.pop("backend/browser/execution.py")
    with pytest.raises(ValueError):
        rb.audited_runtime(manifest, current)


def test_catalog_alias_wrapper_requires_all_canonical_outputs_unchanged(runtime):
    root, manifest, current, canonical = runtime
    (root / "scenarios/catalog.py").write_text("alias wrapper\n")
    current["scenarios/catalog.py"] = hashlib.sha256(b"alias wrapper\n").hexdigest()
    current["scenarios/identity.py"] = "display-only-registry"
    current["scenarios/identities.json"] = "explicit-display-only-mapping"
    approve(runtime)
    assert rb.audited_runtime(manifest, current)
    canonical["T01"] = "changed-label-or-truth"
    with pytest.raises(ValueError, match="scenario objects"):
        rb.audited_runtime(manifest, current)


@pytest.mark.parametrize("path", ["scenarios/v21.py", "checkout_fixtures/checkout.js", "research/release.json"])
def test_canonical_files_cannot_be_approved_as_runtime_changes(runtime, path):
    root, manifest, current, _ = runtime
    (root / path).write_text("model-accommodated fixture\n")
    with pytest.raises(ValueError):
        rb.create_binding(manifest, current, review={"status": "approved"})


@pytest.mark.parametrize("path", ["scenarios/model_fixture.py", "checkout_fixtures/model.html", "backend/fixtures.py", "backend/evaluator/scoring.py"])
def test_new_or_changed_protected_sources_rejected(runtime, path):
    _, manifest, current, _ = runtime
    current[path] = "forbidden-source"
    with pytest.raises(ValueError, match="fixture/scoring"):
        rb.create_binding(manifest, current)


def test_baseline_rewrite_cannot_reuse_an_existing_approval(runtime):
    root, manifest, current, _ = runtime
    approve(runtime)
    path = root / rb.BASELINE_FILE
    baseline = json.loads(path.read_text())
    baseline["extra"] = "changed evidence"
    path.write_text(json.dumps(baseline))
    with pytest.raises(ValueError, match="differs"):
        rb.audited_runtime(manifest, current)


def test_display_mapping_change_requires_another_review(runtime):
    _, manifest, current, _ = runtime
    current["scenarios/identities.json"] = "reviewed-mapping"
    approve(runtime)
    current["scenarios/identities.json"] = "changed-mapping"
    with pytest.raises(ValueError, match="differs"):
        rb.audited_runtime(manifest, current)


def test_full_current_catalog_hashes_match_preserved_baseline():
    baseline = json.loads((rb.ROOT / rb.BASELINE_FILE).read_text())
    assert rb.current_canonical_hashes() == baseline["canonical_scenario_hashes"]
    assert len(baseline["canonical_scenario_hashes"]) == 322
