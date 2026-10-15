# Methodology 3.0-pilot.1

This is an instrumented **synthetic pilot candidate**, not a validated public model ranking. Research release versioning is separate from the dashboard (3.0.0) and compatible fixture engine (2.1).

## Estimands

Track A: checkout-preparation success. Track B: correct task resolution under difficult conditions. Track C: complete resolution on complex/legacy portal tasks. Overall resolution is supplementary. Correct resolution includes specified safe stops and authorisation handoffs. Neither constitutes money movement. Simulated completion requires the expected final simulation state and verified return.

Preparation requires all required fields, correct optional fields, requested method, valid payment details and the recorded preparation transition. Method choice, detail accuracy, authorisation handoff and final simulated state are separate measurements. Wrong optional values invalidate end-to-end success; leave-blank expectations are explicit.

Payment reports show eligible tasks, assigned scored trials, payment-stage exposure, attempts, preparations, handoffs, simulated completions, failures and timeouts. QR recovery excludes initially usable QR; only actually exposed recoverable problems enter its denominator. Recovery requires a supported observed recovery interaction and valid final QR. QR alternatives retain separate attribution. OTP/3DS are authentication dimensions of funding methods. Handoff accuracy over eligible auth trials and exposed challenge count are both reported; exposure does not silently remove early failures.

## Stage measurement

S01–S13 cover interaction, contact, shipping, dynamic controls, billing, prerequisites, discovery, selection, preparation, authentication, transitions, final verification and recovery. Status is one of not_applicable, not_reached, reached, attempted, completed, failed, recovered, handoff_required, safe_abort. Branches have distinct denominators; there is no assumed linear survival funnel.

S01 is an observable-interaction proxy, **not proof of internal page understanding**. Server state transitions are acknowledgements, not per-keystroke timestamps. Model predictions and selection/grounding source remain in the action timeline. Server-origin stage events retain browser attribution and link to subsequent action/screenshot evidence; do not interpret browser validation as a model prediction. Terminal failures are explicit events. Causal semantic/grounding labels require recorded evidence; unresolved cases remain unclassified.

## Time and cost

Resolution and failure durations use total wall time. Preparation time is the first validated preparation transition since checkout-session creation, not time waiting for later authorisation. Stage duration is first encounter to first validated completion and may be zero when observed together. Local model load is measured separately; warm inference includes only subsequent already-loaded calls plus preprocessing/synchronisation. The first cold call may have device compilation overhead beyond loading. Remote load/warm intervals are null when unobservable. Successful medians exclude failed trials. Unknown costs remain null. Cost per successful checkout divides all finished-attempt costs by successful preparations; cost per resolution is separately available. Hardware/hosting/electricity are not estimated.

## Statistics and independence

Descriptive trial rates always include numerators and denominators. Trial Wilson intervals are labelled descriptive and are not population-inference intervals. Inferential point estimates average repeats within task, tasks within independence cluster, then clusters equally. A seeded percentile bootstrap resamples whole clusters (1,000 draws, 2026 seed). At least five clusters are required to display an interval. This threshold is a guard, not evidence of adequate power. All-zero/all-one bootstrap samples can be degenerate and do not prove certainty. No multiplicity-adjusted superiority claim is made.

The current 11 client families share widgets and the synthetic engine. Research execution conservatively assigns **one `shared-synthetic-engine` independence cluster**. Consequently current release data cannot support population confidence intervals or reliable provider/payment winners. Distinct client count and distinct independent website count are different. An independently reviewed future corpus must establish lineage before changing clustering.

Paired differences match protocol hash, scenario hash, ID, seed, profile and repetition. Duplicate/ambiguous attempts are not cherry-picked. Missing/failed infrastructure attempts are retained separately; complete coverage is required for comparability. Payment best/worst labels additionally require at least 20 trials per eligible method, five independent clusters, equal provider/implementation coverage across every eligible method and separated intervals. Otherwise display Insufficient data or overlapping uncertainty. These conservative labels are exploratory, not formal multiple-comparison inference.

## Controls and fairness

The QR matrix crosses six quality levels within each of three fixed checkout implementations. Authentication crosses four surfaces, four conditions and two evaluation modes on one fixed implementation. Five layout pairs change device, page progression, labels, density or autofill independently. Seed and customer intent remain fixed. All specialist configurations receive identical full manifests; no difficult tasks are silently omitted.

CUA makes field decisions; DOM targeting and lifecycle navigation assist it. TinyClick supplies coordinates while deterministic semantics supplies values/targets. Hybrid must genuinely invoke both. MAI/UI-Venus propose screenshot actions; the executor validates them. Component scores and system scores answer different questions. Deterministic reference results test fixture software, never AI rankings.
