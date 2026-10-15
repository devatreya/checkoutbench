# Local validation record

Active release: `3.0-pilot.1`. Release hash: `6b385d58387d15ffdafc55d0b139acd94d64ef76309582411d91df8e391701c5`.

| Check | Result |
|---|---|
| Full regression run | 132 passed in 1086.14s (0:18:06) |
| Final Results, API, persistence and UI checks | 34 passed |
| Final backend measurement/official-data checks | 50 passed |
| Desktop/mobile real UI captures | 27 passed at widths 1440, 1280 and 390 |
| Frontend production build | Passed |
| One-time archival cleanup | 313 classified records and 5,722 artifact files verified in backup; zero active records |
| Live reference-storage check | Reference succeeded in validation storage; official Results and export stayed empty |
| CUA-S1 checkpoint binding | Preserved and reverified; no new model comparison performed |
| Frozen source verification | Passed |
| Targeted credential scan | No findings in 498 tracked/nonignored files |

The complete regression run and final focused checks cover the final implementation. Three additional API/configuration/restart tests were added after the full run collected its tests and passed in the focused set. Final frontend release-label, filtered-summary and empty-state refinements, plus atomic protocol configuration handling, were covered by focused checks. UI tests use synthetic intercepted API responses; these never enter stored research results.

The prior v3 validation record is retained in Git history. This change intentionally archives obsolete validation records instead of retaining them in the active database. Every archived raw row was compared with its SQLite source before cleanup. No genuine model-evaluation record was deleted. See [cleanup audit](../operations/RESULTS_CLEANUP_AUDIT.md) and [storage/protocol operations](../operations/RESULTS_DATASET.md).

Evidence log digests and gate values are in [validation-evidence.json](../../research/validation-evidence.json). The archive and credentials remain Git ignored. Targeted scans do not guarantee the absence of all possible sensitive information. Research readiness remains **NOT READY** pending the independent evidence described in [READINESS.md](READINESS.md).
