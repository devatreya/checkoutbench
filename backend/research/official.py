"""Single, explicit dataset boundary for dashboard, run explorer and exports."""

import json
from backend.storage.database import DATA
from backend.research.protocol import release, protocol_hash, runtime_identity
from backend.research.statistics import eligible_attempt, analyse, summary
from scenarios.research import digest


def checkpoint_identity(record):
    if not record or not record.get("verified"):
        return None
    if record.get("components"):
        components = [checkpoint_identity(x) for x in record["components"]]
        return {"components": components} if all(components) else None
    return {
        k: record.get(k)
        for k in (
            "repository", "revision", "checkpoint_hashes", "adapter_hash",
            "loader_hash", "runtime_versions", "backend", "precision",
            "quantisation", "device",
        )
    } | {
        k: record[k] for k in (
            "runtime_config", "prompt_sha256", "code_source_hashes",
            "artifact_id", "checkpoint_revision",
        ) if k in record
    }


def configuration(manifest):
    path = DATA / "research/official-protocol.json"
    if not path.exists():
        return None, "No official evaluation protocol is configured. Configure it before collecting official comparisons."
    try:
        c = json.loads(path.read_text())
        if not isinstance(c, dict):
            raise ValueError("Expected a protocol object")
    except (ValueError, OSError):
        return None, "The official protocol could not be read. Repair its configuration before collecting comparisons."
    if (
        c.get("release_hash") != manifest["release_hash"]
        or c.get("research_release") != manifest["release"]
    ):
        return None, "The official protocol belongs to another frozen release. Its evidence is preserved; configure this release explicitly."
    expected = protocol_hash(c.get("settings"), manifest["release_hash"], c.get("runtime"))
    if c.get("research_protocol_hash") != expected:
        return None, "Official protocol settings failed integrity verification."
    return c, None


def select(rows, manifest=None, config=None):
    m = manifest or release()
    c, reason = configuration(m) if config is None else (config, None)
    if not c:
        return [], reason
    selected = []
    scenarios = {s["id"]: s for s in m["scenarios"]}
    for r in rows:
        ex = r.get("execution_manifest") or {}
        identity = checkpoint_identity(ex.get("checkpoint"))
        scenario = scenarios.get(r.get("scenario"))
        if (
            eligible_attempt(r, m)
            and r.get("scoring_version") == c.get("scoring_version")
            and r.get("research_protocol_hash") == c.get("research_protocol_hash")
            and ex.get("settings") == c.get("settings")
            and identity
            and identity == c.get("checkpoints", {}).get(r.get("model"))
            and scenario
            and r.get("scenario_hash") == scenario.get("scenario_hash")
            and ex.get("scenario_manifest_hash") == m["manifest_hash"]
            and ex.get("source_hash") == m["source_hash"]
            and (not c.get("runtime") or all(ex.get(k) == v for k, v in c["runtime"].items()))
        ):
            selected.append(r)
    return selected, reason


def dataset(rows):
    m = release()
    # One configuration snapshot for eligibility, metrics and returned attempts.
    c, reason = configuration(m)
    selected = select(rows, m, c)[0] if c else []
    a = analyse(selected, m, c["research_protocol_hash"] if c else None)
    difficulties = []
    for model in sorted({r["model"] for r in selected}):
        groups = {}
        for r in selected:
            if r["model"] != model:
                continue
            key = str((r.get("difficulty_config") or {}).get("reliability", "unspecified"))
            groups.setdefault(key, []).append(r)
        difficulties.extend(
            {"model": model, "difficulty": key, **summary(rs)}
            for key, rs in groups.items()
        )
    a.update(
        difficulties=difficulties, runs=selected, summary=summary(selected),
        official_protocol_configured=c is not None, empty_reason=reason,
        release_hash=m["release_hash"],
    )
    return a


def configure(config):
    """Explicit operator action from a complete batch config, never inferred from runs."""
    from backend.research.protocol import validate_standard, checkpoint_records

    m = validate_standard(config)
    settings = {
        k: v for k, v in config.items()
        if k not in ("models", "scenarios", "spending_cap")
    }
    records = checkpoint_records()
    runtime = runtime_identity(m, require_audit=True)
    identities = {k: checkpoint_identity(records.get(k)) for k in config["models"]}
    if not all(identities.values()):
        raise ValueError("Verified specialist checkpoints required")
    c = {
        "research_release": m["release"], "release_hash": m["release_hash"],
        "scoring_version": "3.0", "settings": settings,
        "research_protocol_hash": protocol_hash(settings, m["release_hash"], runtime),
        "runtime": runtime,
        "checkpoints": identities,
    }
    path = DATA / "research/official-protocol.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        old = json.loads(path.read_text())
        archive = path.parent / "protocol-history"
        archive.mkdir(exist_ok=True)
        (archive / (digest(old) + ".json")).write_text(json.dumps(old, indent=2) + "\n")
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(c, indent=2) + "\n")
    temporary.replace(path)
    return c
