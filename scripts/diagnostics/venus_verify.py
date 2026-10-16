"""Create/recheck local UI-Venus evidence; register explicitly in the active app."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from backend.adapters.venus_verification import create_record, verify_record


def register_record(record: dict, data_dir: Path | None = None) -> Path:
    """Merge only the active UI-Venus entry, preserving other checkpoint records."""
    root = data_dir or Path(os.getenv("BENCH_DATA_DIR") or "data").resolve()
    path = root / "research/checkpoint-verification.json"
    records = json.loads(path.read_text()) if path.exists() else {}
    if not isinstance(records, dict):
        raise ValueError("Active checkpoint registry must be a model-keyed object")
    records["ui-venus"] = record
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, prefix=".checkpoint-verification-", suffix=".tmp", delete=False) as file:
            temporary = Path(file.name)
            file.write(json.dumps(records, indent=2) + "\n")
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return path


def main():
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", type=Path)
    parser.add_argument("--check", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--register", action="store_true", help="Explicitly merge ui-venus into BENCH_DATA_DIR/research/checkpoint-verification.json")
    args = parser.parse_args()
    if bool(args.smoke) == bool(args.check):
        parser.error("Specify exactly one of --smoke or --check")
    record = verify_record(json.loads(args.check.read_text())) if args.check else create_record(args.smoke)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(record, indent=2) + "\n")
    registered = register_record(record) if args.register else None
    print(json.dumps({"verified": record["verified"], "artifact_id": record["artifact_id"], "revision": record["checkpoint_revision"], "scope": record["verification_scope"], "registered": str(registered) if registered else None}))


if __name__ == "__main__":
    main()
