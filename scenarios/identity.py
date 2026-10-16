"""Presentation identities, independent of canonical fixtures and manifests.

IDs in identities.json are an explicit compatibility contract. Never renumber
them when adding a scenario. Public IDs resolve to canonical IDs before fixture
generation; presentation metadata is added only to returned API copies.
"""

from copy import deepcopy
import json
from pathlib import Path
import re

FIELDS = ("canonical_id", "public_id", "display_name", "description")


def validate_registry(rows):
    """Reject ambiguity in either identifier namespace before serving any row."""
    canonical, public = {}, {}
    for row in rows:
        if set(row) != set(FIELDS) or any(
            not isinstance(row[k], str) or not row[k].strip() for k in FIELDS
        ):
            raise ValueError("Scenario identity requires four nonempty string fields")
        cid, pid = row["canonical_id"], row["public_id"]
        if cid in canonical or pid in public:
            raise ValueError("Duplicate canonical or public scenario identity")
        if not re.fullmatch(r"[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*", pid):
            raise ValueError("Public scenario identity must be an uppercase slug")
        if re.search(r"(?:^|-)V\d", pid):
            raise ValueError("Public scenario identity contains a release prefix")
        canonical[cid] = dict(row)
        public[pid] = cid
    if set(canonical) & set(public):
        raise ValueError("Canonical and public scenario namespaces overlap")
    return canonical, public


_CANONICAL, _PUBLIC = validate_registry(
    json.loads(Path(__file__).with_name("identities.json").read_text())
)


def resolve_id(identifier: str) -> str:
    """Resolve a registered public alias or preserve a historical canonical ID."""
    if not isinstance(identifier, str):
        raise ValueError("Unknown scenario identifier")
    if identifier in _CANONICAL:
        return identifier
    try:
        return _PUBLIC[identifier]
    except (KeyError, TypeError):
        raise ValueError("Unknown scenario identifier") from None


def identity(identifier: str) -> dict:
    return dict(_CANONICAL[resolve_id(identifier)])


def identities() -> list[dict]:
    """Return ordered independent copies of the complete compatibility table."""
    return [dict(row) for row in _CANONICAL.values()]


def enrich(record: dict, id_field: str = "id") -> dict:
    """Overlay metadata without mutating fixture data or persisted result rows."""
    return {**deepcopy(record), **identity(record[id_field])}
