# Local validation record

Active release: `3.0-pilot.1`. Release hash: `ca8a3a4d939fce39986e723d33203d9c76fb40bf5954e707204e252ab62332ee`.

189 distinct tests verified passing across the complete run and focused reruns. The initial complete run had 180 passes, six CUA import skips, one CUA import failure, and one V21-ST03 provider refresh race. A bounded settling wait fixes that race, with a new delayed-transition test and the complete affected browser groups rerun successfully. The regular-wheel runtime repair preserved exact loader/weight hashes; all 52 fidelity/adapter tests, including those seven cases, then passed. No failing case was waived.

| Check | Result |
| --- | --- |
| Combined harness/model/adapter checks | 73 passed, including real pinned CPU inference |
| V2.1 browser regressions | 23 passed including research-browser matrices |
| Complete regression coverage after affected-test rerun | 189 distinct tests verified passing |
| Genuine V21-G01 evaluations | Three runs; each seven inference calls, four browser actions, three validation errors; unsuccessful checkout, bounded `no_progress` stop |
| Browser execution integrity | Wrong email preserved; required skips blank; no semantic correction; independent evaluator rejects checkout |
| Original evidence preservation | Original failed record and all 82 artifacts byte-identical |
| Source freeze | Verified; scenario manifest and 174 scenario IDs unchanged |

The macOS runtime repeatedly marked editable-package `.pth` files hidden. Installing the same audited CUA source as a regular wheel fixed fresh-process imports without changing loader or model-weight hashes. The final fresh-server browser replay reproduced the same decisions and a byte-identical screenshot. Tests using deterministic scorers are explicitly separate from genuine model inference.

See [harness operations and exact commands](../operations/CUA_HARNESS.md), [model fidelity audit](CUA_MODEL_FIDELITY.md), [integration evidence](../../research/harness-integration-evidence.json), and [log digests](../../research/validation-evidence.json). Previous validation and cleanup evidence remain in commit `67e1ba7` and the [cleanup audit](../operations/RESULTS_CLEANUP_AUDIT.md); no cleanup was performed during this integration.

Research readiness remains **NOT READY**. A single-scenario checkout integration check does not establish comparative model performance, independent fixture validity, or publication readiness.
