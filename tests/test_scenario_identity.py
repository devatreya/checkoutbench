"""Presentation aliases never alter canonical tasks or historical records."""

from copy import deepcopy
import json
from pathlib import Path
import re

import pytest

from scenarios.catalog import SPECS as LEGACY, scenario
from scenarios.identity import enrich, identities, identity, resolve_id, validate_registry
from scenarios.research import SPECS, build_manifest, digest
from scenarios.v2 import V2_SPECS
from scenarios.v21 import V21_SPECS


def test_complete_deterministic_registry_and_two_way_compatibility():
    rows = identities()
    expected = {x[0] for x in LEGACY} | {
        x["id"] for x in V2_SPECS + V21_SPECS + SPECS
    }
    assert len(rows) == len(expected) == 322
    assert {r["canonical_id"] for r in rows} == expected
    assert len({r["public_id"] for r in rows}) == len(rows)
    assert not {r["public_id"] for r in rows} & expected
    assert identities() == rows
    for row in rows:
        assert resolve_id(row["public_id"]) == row["canonical_id"]
        assert resolve_id(row["canonical_id"]) == row["canonical_id"]
        assert identity(row["public_id"]) == row
        assert not re.search(r"(?:^|-)V\d", row["public_id"])
        assert "simulated" in row["description"].lower()
        assert "No real transaction" in row["description"]


def test_explicit_examples_and_cross_generation_collisions():
    examples = {
        "V3-ST03": "STRIPE-03",
        "V3-RZ01": "RAZORPAY-01",
        "V3-CF01": "CASHFREE-01",
        "V3-G01": "GENERIC-01",
        "V3-S01": "SHOPIFY-01",
        "V3-QR-razor-2": "RAZORPAY-QR-02",
        "V3-AUTH-modal-otp_expired-handoff": "AUTH-MODAL-EXPIRED-HANDOFF",
        "V21-G01": "GENERIC-01-CLASSIC",
        "V21-S01": "SHOPIFY-01-CLASSIC",
        "S01": "SHOPIFY-01-FOUNDATION",
    }
    assert {cid: identity(cid)["public_id"] for cid in examples} == examples
    assert identity("V3-Q00")["public_id"] != identity("V3-QR-razor-0")["public_id"]


@pytest.mark.parametrize(
    "change", ["public_duplicate", "canonical_duplicate", "namespace", "version", "empty"]
)
def test_invalid_registry_rejected(change):
    rows = identities()[:2]
    if change == "public_duplicate":
        rows[1]["public_id"] = rows[0]["public_id"]
    elif change == "canonical_duplicate":
        rows[1]["canonical_id"] = rows[0]["canonical_id"]
    elif change == "namespace":
        rows[1]["public_id"] = rows[0]["canonical_id"]
    elif change == "version":
        rows[1]["public_id"] = "V3-GENERIC-01"
    else:
        rows[1]["description"] = ""
    with pytest.raises(ValueError):
        validate_registry(rows)


@pytest.mark.parametrize("unknown", ["GENERIC-999", "V3-NOT-REAL", "", None, []])
def test_unknown_ids_fail_closed(unknown):
    with pytest.raises(ValueError):
        resolve_id(unknown)


def test_overlay_is_detached_and_cannot_rewrite_historical_record():
    record = {"id": "old-run", "scenario": "V21-G01", "events": [{"action": "fill"}]}
    before = deepcopy(record)
    decorated = enrich(record, "scenario")
    assert record == before
    assert decorated["id"] == "old-run"
    assert decorated["scenario"] == "V21-G01"
    assert decorated["public_id"] == "GENERIC-01-CLASSIC"
    decorated["events"][0]["action"] = "changed"
    decorated["display_name"] = "changed"
    identities()[0]["public_id"] = "changed"
    assert record == before
    assert identity("V21-G01")["display_name"] != "changed"
    assert identities()[0]["public_id"] != "changed"


def test_every_overlay_preserves_canonical_scenario_and_frozen_manifest():
    frozen = json.loads((Path(__file__).resolve().parents[1] / "research/release.json").read_text())
    assert build_manifest()["manifest_hash"] == frozen["manifest_hash"]
    for row in identities():
        original = scenario(row["canonical_id"], 2026)
        fingerprint = digest(original)
        decorated = enrich(original)
        assert {k: decorated[k] for k in original} == original
        assert digest(original) == fingerprint
        assert scenario(resolve_id(row["public_id"]), 2026) == original
        assert scenario(row["public_id"], 2026) == original
        assert not {"canonical_id", "public_id", "display_name", "description"} & original.keys()
    assert build_manifest()["scenarios"] == frozen["scenarios"]
