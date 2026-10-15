# Local validation record

Release: `3.0-pilot.1`

Release hash: `0eb464ed3f8029e0564189055aee087eb4127114998e190a20ec54a9ffc7a978`

| Check | Result |
|---|---|
| Complete automated suite | 113 passed in 1209.47 seconds |
| Final scoring and dashboard checks | 41 passed in 26.15 seconds |
| Async Stripe Link transition regression | 2 passed |
| Desktop/mobile real UI captures | 27 passed at widths 1440, 1280 and 390 |
| Frontend production build | Passed |
| Historical records | All 313 raw database records unchanged |
| CUA-S1 exact-weight cold/warm inference | Passed; no comparative accuracy claim |
| Frozen source verification | Passed |
| Targeted credential scan | No findings in tracked/nonignored files or 372 reachable historical Git blobs |

The initial full run exposed a Stripe Link navigation race: the controller could execute a button against a changed page while using an older observation. It now re-observes changed public page text before advancing; a deterministic race regression and the fresh complete suite passed.

The final raw-success preservation change and frontend scoring-version cohort separation were covered by the additional 41-test run. Tests use isolated temporary result storage. Controlled layout solvability uses a private test oracle and does not count as AI performance. Adapter test doubles are likewise excluded from research rankings.

Evidence log digests and gate values are recorded in [validation-evidence.json](../../research/validation-evidence.json). Credential scans are targeted checks, not a guarantee that arbitrary sensitive information cannot exist. All research limitations remain in [READINESS.md](READINESS.md).
