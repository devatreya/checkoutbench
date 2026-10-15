# Official results and validation storage

CheckoutBench displays one unified set of results from the current official benchmark release. Internal software validation is separate from genuine AI model evaluations.

## Dataset boundary

`research/release.json` selects the active frozen suite. The normal UI reads that manifest; it does not choose a version or infer a release from saved records. `backend/research/official.py` supplies one population to all five Results tabs, run details, standard JSON/CSV exports and research bundles.

An operator must explicitly configure `data/research/official-protocol.json`. Its release/hash, full execution settings, scoring schema and model-specific checkpoint identities define the official comparison. There is no first-record or latest-experiment fallback. Without a matching configuration, Results shows **No benchmark results yet** and explains the missing protocol. This does not assert that checkpoint, human review or publication-readiness gates have passed.

Eligibility also requires the full ordered suite, exact scenario hash, source/manifest hashes and checkpoint evidence. Completed runs require actual non-mock inference. Legitimate failures, timeouts, blocked, unavailable, stopped and running attempts under a verified experiment remain inspectable, including failures before the first inference call. The dashboard reports inference-bearing evaluations separately from total verified experiment attempts. A protocol does not make synthetic environments production-provider measurements.

Checkpoint revisions, adapter/runtime/backend/precision and controller source changes cannot be silently combined. Analysis keeps successful latency separate, preserves stage/payment denominators and withholds rankings/intervals when evidence is insufficient. CUA, TinyClick and the hybrid retain their deterministic assistance disclosures.

## Explicitly configure an experiment

First verify the exact installed checkpoints with `scripts.research.verify_models`; unavailable models remain blocked. Prepare the settings before observing results. For example, this writes a local batch configuration matching the current UI defaults for CUA-S1 (it performs no inference and starts no batch):

```sh
.venv/bin/python - <<'PY'
import json
from pathlib import Path
from backend.app import Batch
from backend.research.protocol import release
m = release(verify=True)
c = Batch(models=['cua-s1'], scenarios=m['scenario_ids'],
          research_release=m['release'], release_hash=m['release_hash'],
          seed=m['seed'], repeats=3, max_steps=100, timeout=180,
          max_tokens=8192, video=False).model_dump()
Path('data/research/official-batch.json').write_text(json.dumps(c, indent=2))
PY
.venv/bin/python -m scripts.research.manage configure-official data/research/official-batch.json
```

Review the JSON before configuration; use the intended recording, limits, repeats and retry policy. Every setting must match Review & Run, including video. Include each verified model intended for this comparison in `models`. Adding a checkpoint requires explicit reconfiguration. The command validates the release and actual local checkpoint binding and archives the prior configuration under `data/research/protocol-history/`. It never infers settings from database rows and never starts evaluations.

Use the regular **Models → Scenarios → Review & Run** workflow to execute those settings. Incompatible experiments remain stored for operator inspection at `/api/diagnostics/experiments`; they do not enter official statistics. Changing the official protocol changes visibility, not persistence. No database reset happens at startup.

## Isolated internal validation

- Verified full-suite model attempts are stored in `data/results.sqlite3` with their execution manifest and evidence. Their artifact directories are `data/<run-id>/`.
- Reference, subset/debug, unverified and explicitly marked test runs use `data/validation/results.sqlite3` and `data/validation/<run-id>/`.
- Pytest starts servers with temporary `BENCH_DATA_DIR` and `BENCH_STORAGE_ROLE=validation`; all resulting artifacts remain temporary.
- `scripts/check.py` submits the reference executor, reads `/api/diagnostics/results`, and writes its summary to `data/validation/reference-verification.json`. It cannot populate official rankings.
- Diagnostic exports live under `/api/diagnostics/export/{json,csv}`. Standard `/api/export/{json,csv}` and `/api/research/export` use only the official dataset. Empty research exports contain clearly marked templates.

## One-time cleanup and future migrations

The pre-evaluation audit classified 313 rows: 302 deterministic references and 11 unavailable configuration checks. None had inference calls; no test-double or genuine evaluation records were found. A separate genuine CUA inference smoke existed outside the results database and was retained. See [cleanup audit](RESULTS_CLEANUP_AUDIT.md).

The explicit cleanup script refuses any record with inference/checkpoint evidence or ambiguous classification. It backs up SQLite through the SQLite backup API, includes run JSON and associated artifact directories, verifies each file hash and database integrity/row equality, then checks that the source rows have not changed before deletion. The archive is under Git-ignored `data/archives/`. It is never called on startup. An empty database produces no further reset.

For future migrations with real evaluations, do **not** use this validation cleanup. Stop the runner, create a consistent SQLite snapshot and copy associated artifacts, protocol history, manifests and checkpoint-verification evidence into an ignored migration archive. Record SHA-256 hashes, reopen the snapshot, verify `PRAGMA integrity_check` and exact row equality, then validate the migration against a copy. Preserve original genuine attempts and their evidence, including failures, under their original release and protocol. New releases select new official data without deleting older evaluations.
