"""Read-only scenario identity overlays for API and result presentation."""
from scenarios.identity import identity


def present(value):
    if isinstance(value, list):
        return [present(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {k: present(v) for k, v in value.items()}
    for key in ("scenario", "canonical_id", "id"):
        candidate = value.get(key)
        if isinstance(candidate, str):
            try:
                result.update(identity(candidate))
                break
            except ValueError:
                pass
    return result
