# Pre-evaluation cleanup audit

Audit and reset date: 2026-10-15. The local runner was idle and stopped before the snapshot and reset.

| Classification | Records | Evidence |
|---|---:|---|
| Deterministic reference | 302 | Model and kind both reference; zero inference calls/time |
| Unconfigured model availability checks | 11 | Six missing API-key checks and five missing specialist weight/dependency checks; status unavailable, empty calls/events, zero inference time |
| Explicit test doubles in active DB | 0 | No matching records |
| Genuine model evaluations | 0 | No recorded calls or checkpoint-backed evaluation evidence |
| Ambiguous records | 0 | Every row classified before reset |

Versions: 66 unversioned legacy rows, 18 explicit v1.0 rows, 79 v2.0 rows and 150 v2.1 rows. The research release and protocols were inspected separately. No official evaluation protocol was configured. The CUA-S1 checkpoint and genuine cold/warm smoke evidence in `data/research/` were preserved; they are not benchmark evaluations.

Verified backup: `data/archives/pre-evaluation-validation-20261015T113455Z/backup.tar.gz` (Git ignored). It contains the SQLite snapshot, all 313 run metadata records, audit classifications, SHA-256 manifest and **5,722 associated artifact files**. Verification reopened the archive, checked all member hashes, ran SQLite integrity checking, and compared every raw database row with the source. Source rows were checked again under a transaction before deletion.

Backup SHA-256: `a199e0a0b216097be628c9fcea0b6fd64e597e9feb3fab619636b934b1175b31`.

After reset: **0 active records**. Archived run artifact directories were removed from active storage only after verification. Scenarios, fixtures, private scoring, adapters, tests, model checkpoints, research definitions, documentation and Git history were retained. No genuine model-evaluation record was deleted. Future experiments are never reset automatically.
