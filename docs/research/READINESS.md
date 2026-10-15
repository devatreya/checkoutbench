# Research readiness — 3.0-pilot.1

**NOT READY** for publication of comparative model rankings. The software regression suite passes; research validity still needs independent evidence.

## Completed software verification

- 113 automated tests passed, covering legacy behavior, controlled matrices, new merchant fixtures, measurement, statistical guards, adapters and browser UI.
- 41 final scoring/UI checks passed after the last scoring-preservation and cohort-separation changes.
- 27 real desktop/mobile UI captures passed layout and JavaScript checks.
- All 313 pre-existing stored run records were preserved byte for byte.
- CUA-S1's exact checkpoint and loader were verified and genuine cold/warm inference executed. This is an inference-format smoke test, not a checkout accuracy evaluation.
- Frozen source hashes match the release. Research charts remain marked templates because no eligible comparative model evaluations were collected.

## Remaining blockers

- All 174 scenarios await independent human ground-truth review.
- TinyClick's identified repository does not provide the exact required weights. The hybrid consequently remains blocked. MAI-UI and UI-Venus require pinned local weights and genuine inference verification.
- The 11 client implementation families share infrastructure and count conservatively as one independence cluster. The target of at least 15 independent implementations and 60–100 independently prepared tasks is not met. Population confidence intervals and reliable best/worst claims are withheld.
- No independently authored, validated sealed final corpus has been supplied. Custodian sealing, commitments and one-use reservation tooling exist; they do not constitute an unseen evaluation dataset.
- Official provider sandbox browser validation remains pending access. The optional Stripe inspection tool does not establish completed payment-flow fidelity.
- No independent reproduction or controlled public model comparison has occurred.
- The repository has no owner-selected root code/data license; upstream model licenses and source attribution are documented separately.

See [validation evidence](../../research/validation-evidence.json), [machine-readable readiness](../../research/readiness.json), [limitations](LIMITATIONS.md) and [reproduction instructions](REPRODUCING.md). Reassess readiness after each external evidence submission; passing the reference executor alone never changes these gates.
