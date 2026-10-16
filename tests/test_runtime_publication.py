"""Publication-boundary regressions using serialized fixtures, never inference."""

import copy
import io
import json
import zipfile

import pytest

from backend.research import export, official
from tests.test_official_results import sample


def venus_sample():
    manifest, config, row = sample()
    checkpoint = row["execution_manifest"]["checkpoint"]
    checkpoint.update(
        runtime_config={"max_pixels": 262144, "history_limit": 4, "max_tokens": 128},
        prompt_sha256="prompt-a", code_source_hashes={"worker.py": "worker-a"},
        artifact_id="fixture-artifact", checkpoint_revision="checkpoint-a",
    )
    row.update(model="ui-venus", status="blocked", calls=[])
    config["checkpoints"] = {"ui-venus": official.checkpoint_identity(checkpoint)}
    return manifest, config, row


@pytest.mark.parametrize("key,value", [
    ("runtime_config", {"max_pixels": 524288, "history_limit": 4, "max_tokens": 128}),
    ("runtime_config", {"max_pixels": 262144, "history_limit": 8, "max_tokens": 128}),
    ("runtime_config", {"max_pixels": 262144, "history_limit": 4, "max_tokens": 256}),
    ("prompt_sha256", "prompt-b"),
    ("code_source_hashes", {"worker.py": "worker-b"}),
    ("artifact_id", "other-artifact"),
    ("checkpoint_revision", "checkpoint-b"),
])
def test_official_selection_does_not_pool_changed_venus_inference_contract(key, value):
    manifest, config, row = venus_sample()
    assert official.select([row], manifest, config)[0] == [row]
    changed = copy.deepcopy(row)
    changed["execution_manifest"]["checkpoint"][key] = value
    # Settings and protocol/source hashes remain identical: checkpoint binding
    # must independently exclude this changed model execution contract.
    assert official.select([changed], manifest, config)[0] == []
    assert official.select([row], manifest, config)[0] == [row]


def test_legacy_checkpoint_identity_retains_original_dictionary_shape():
    manifest, config, row = sample()
    original_keys = {
        "repository", "revision", "checkpoint_hashes", "adapter_hash",
        "loader_hash", "runtime_versions", "backend", "precision",
        "quantisation", "device",
    }
    checkpoint = row["execution_manifest"]["checkpoint"]
    config["checkpoints"]["cua-s1"] = {key: checkpoint.get(key) for key in original_keys}
    assert official.select([row], manifest, config)[0] == [row]


def test_analysis_and_runs_exports_apply_the_same_public_allowlist(tmp_path, monkeypatch):
    manifest, config, row = venus_sample()
    row.update(
        inference_error_detail="PRIVATE_LOCAL_WORKER_DIAGNOSTIC_SENTINEL",
        raw_model_output="PRIVATE_NATIVE_OUTPUT_SENTINEL",
        arbitrary_private_field={"value": "PRIVATE_UNKNOWN_SENTINEL"},
        outcome_category="infrastructure_failure",
    )
    monkeypatch.setattr(official, "configuration", lambda manifest: (config, None))
    monkeypatch.setattr(export, "release", lambda **kwargs: manifest)
    monkeypatch.setattr(export, "readiness", lambda: {"status": "NOT READY", "blockers": []})
    monkeypatch.setattr(export, "runtime_identity", lambda manifest: {"runtime_audited": False})
    monkeypatch.setattr(export, "source_hashes", lambda: {})
    monkeypatch.setattr(export, "ROOT", tmp_path)
    monkeypatch.setattr(export, "chart", lambda *args: "<svg/>")
    monkeypatch.setattr(export, "scatter", lambda *args: "<svg/>")
    expected = official.dataset([row])
    with zipfile.ZipFile(io.BytesIO(export.bundle([row]))) as archive:
        analysis = json.loads(archive.read("analysis.json"))
        runs = json.loads(archive.read("runs.json"))
        assert analysis["runs"] == runs
        assert [item["id"] for item in runs] == [row["id"]]
        assert runs[0]["outcome_category"] == "infrastructure_failure"
        assert analysis["summary"] == expected["summary"]
        assert set(runs[0]) <= set(export.RUN_FIELDS)
        for name in archive.namelist():
            data = archive.read(name)
            assert b"PRIVATE_LOCAL_WORKER_DIAGNOSTIC_SENTINEL" not in data
            assert b"PRIVATE_NATIVE_OUTPUT_SENTINEL" not in data
            assert b"PRIVATE_UNKNOWN_SENTINEL" not in data
    # Publication filtering must not discard the retained private evidence.
    assert row["inference_error_detail"] == "PRIVATE_LOCAL_WORKER_DIAGNOSTIC_SENTINEL"
