# CheckoutBench v2.2 — AI-first interface

This release replaces the software-validation dashboard with dedicated **Overview → Models → Scenarios → Review & Run → Live Benchmark → Results** pages. The interface version is 2.2; the validated benchmark remains **v2.1 (74 scenarios)**. No benchmark backend, scenario, fixture, adapter, QR/OTP simulator, evaluator or storage implementation was changed.

## Delivered experience

- A compact overview with one Start Benchmark action, four AI statistics and recent specialist attempts.
- Five specialist configurations, their sizes, operation, backend and availability. Configured-but-unverified systems are explicitly distinguished from verified inference; missing setup remains visible.
- Nine selectable environment families, scenario filters, quick/core/environment/full selections and a separate checkout/customer/task preview. Historical suites are previewable but blocked for new AI batches by the existing engine contract.
- Persistent model/scenario/settings selections in browser storage. Dedicated review with common settings first, advanced settings collapsed, unknown expenditure shown honestly, compatibility checks and an explicit confirmation dialog. Refresh and navigation never POST a batch.
- Two-column live browser/execution view with internally scrolling action history, timing, progress and pause/resume/stop. Hidden-system sessions disclose runner occupancy without their model or evidence details.
- Four Results tabs: Summary, Model Comparison, Scenario Analysis and Run Explorer. Six run-detail tabs: Outcome, Action timeline, Visual replay, Fields, Payment & authentication, Performance.
- Metric definitions available throughout Results; raw single-run and trace JSON, filtered summary/comparison CSV and all-visible-specialist JSON exports.
- Secondary Coverage & Sources page for scenario capabilities, source provenance/confidence and fidelity qualifications.
- Desktop/laptop screen-height shells with internal collections; mobile natural page scrolling, a contained scenario list and persistent setup actions. Focus trapping in dialogs and keyboard arrow navigation for tabs.

## Data and visibility boundaries

`frontend/src/benchmark/policy.ts` is the central allowlist for `cua-s1`, `tinyclick`, `hybrid`, `mai-ui` and `ui-venus`. Reference, frontier/direct-provider and explicit test-double records are excluded from normal UI statistics, searches, live evidence, deep links and exports. Test markers include recorded call backends, record/evaluation flags and deterministic-reference attribution.

The backend catalogue, OpenRouter/direct integration, credentials, pricing and execution remain intact. Developer raw exports still include hidden records. UI filtering never deletes or rewrites stored results.

[History verification](history-preservation.json) compares every original `(id, raw JSON)` pair: **313 records before and after; zero changed, missing or added records**, with matching SHA-256 digests. The running application's data directory was not used by pytest. Test servers use temporary storage on ports 8765/8766.

## Honest analysis

- Aggregates select one benchmark version and execution-conditions cohort, including device, integrity class, experimental arm, evaluation mode and relevant run budgets/settings. Missing cohort/configuration gets a separate unreported group rather than inferred pooling.
- Completed/failed scored attempts determine success rates. Unavailable, blocked, stopped and running attempts remain inspectable but do not enter that denominator.
- Observed leaders require at least two systems, five scored trials each and identical scenario/seed/profile/repetition coverage. This is a display safeguard, not a statistical significance test. Per-metric highlights also require complete numeric reporting across scored trials.
- Wilson 95% intervals express uncertainty. No overall winner or statistically significant superiority is declared automatically.
- Median duration includes scored final outcomes, including failures. Field and recovery averages use recorded values; Summary shows required-field reporting coverage.
- Expenditure includes reported charges on all finished attempts, including stopped/infrastructure-failed attempts. Unknown cost stays unknown. Cost per success is unreported without successful outcomes or with incomplete cost data.
- The existing composite `payment_accuracy` is labelled payment validation. Method-only accuracy is shown only when separately instrumented; missing actual payment-method values stay unreported.
- Required-field false values cannot always distinguish incorrect from missing. The interface states that limitation rather than inventing a missing-field classification. Optional-field success can mean correct or blank.
- Playback uses original screenshot/video paths. Raw records and action traces retain their evidence without frontend metric fabrication.

## Verification

**79 tests passed in 751.05 seconds** in the complete regression run. After final frontend refinements, **all 11 UI tests passed again in 20.79 seconds**. The TypeScript/Vite production build passed. See [validation.json](validation.json), [complete pytest output](pytest-full.txt), [final UI output](pytest-ui-final.txt) and [production build output](frontend-build.txt).

The 11 browser checks cover:

| Area | Evidence |
| --- | --- |
| AI-first entry and central policy | One Start action; no software-check controls; exactly five models; hidden frontier search produces no cards |
| Availability honesty | Configured/unverified text; no inferred verified status; unavailable starts blocked |
| Full setup journey | Models → Scenarios → Review → confirmation → Live; refresh preserves settings and does not start again |
| Live controls | Progress, pause, resume, stop and finished-results navigation using intercepted batch/control requests |
| Scenario research | Environment/device/payment filters, actual preview interface, synthetic profile and success condition |
| Analysis | Known summary arithmetic; exact conditions; comparison minimum/matched coverage; scenario drilldown |
| Missing metrics/costs | Method-only data stays unreported; blocked costs count without changing scored denominators; unknown cost stays unknown |
| Investigation/export | Individual run opens, screenshot stepping, attribution, field/payment/performance details; original JSON equality; filtered CSV and all-visible JSON scope |
| Hidden data | Reference/frontier/direct/test records excluded; stale saved hidden selections removed; hidden run deep links unavailable |
| Responsive/accessibility | All pages have purposes; no page horizontal overflow; desktop heights/footer fit; cards contain their content; mobile scenario list bounded; keyboard tabs |
| Backend preservation | Original frontier and reference catalogue entries remain alongside the five specialists |

The complete regression suite also exercises original browser checkout flows, negative scoring, isolation, authentication/QR, specialist parsers/contracts, intentionally wrong model responses, cancellation, exports and the preserved v2.1 integrity tests. These are software checks, not weights-backed AI results.

## Screenshot evidence

[Inspection index](screenshots/inspection.json) contains **57 captures** at **1440 × 900**, **1280 × 800** and **390 × 844**:

- 21 captures of the seven main/research pages against the actual workspace APIs.
- 36 captures of populated review/live/results/detail states using synthetic UI responses, visibly labelled **UI TEST DATA · no model evaluation**.
- Zero JavaScript errors, document horizontal overflows or desktop document scrolling in the capture checks.

Fixture-prefixed images are layout evidence only. Their scores/actions are synthetic API responses held in the test browser; the replay image is existing fixture artwork. They are not model performance evidence and were never inserted into SQLite. Actual workspace images correctly show zero completed AI evaluations and unavailable specialist setup.

Manual inspection covered desktop overview, laptop model cards/scenario selection, review safeguards, live view, summary/comparison, detail performance/timeline and mobile scenarios. This caught and corrected model-card compression and an overly long mobile scenario collection that document-overflow checks alone did not detect.

Representative pages:

- [Overview, desktop](screenshots/overview-1440.png)
- [Models, laptop](screenshots/models-1280.png)
- [Scenarios, mobile](screenshots/scenarios-390.png)
- [Review, desktop](screenshots/review-1440.png)
- [Live, laptop — synthetic UI data](screenshots/fixture-live-1280.png)
- [Comparison, desktop — synthetic UI data](screenshots/fixture-results-model-comparison-1440.png)
- [Run timeline, mobile — synthetic UI data](screenshots/fixture-detail-action-timeline-390.png)
- [Coverage, desktop](screenshots/coverage-1440.png)

## Limits and reproducibility

All five specialist configurations in this workspace still require checkpoint/dependency or endpoint setup. No paid or weights-backed inference was performed to implement this release. Unit/browser test doubles establish integration behavior only; the new UI cannot establish model capability by itself.

The benchmark's existing fidelity limitations remain: local provider/government approximations, simulated payments/authentication, web rather than native mobile, controller assistance for CUA/TinyClick systems, and historical holdouts treated as regression cases. Real model evaluation, hardware profiling and fresh unseen test sets require separate experiments.

Reproduce from the repository root:

```sh
npm --prefix frontend run build
.venv/bin/pytest -q
# With the normal application running on 8000/8001:
.venv/bin/python -m scripts.visual_dashboard
```

The README documents checkpoint/endpoint configuration, the complete user journey, metrics/exports, safe new data directories and developer-only reference/frontier workflows. Runtime data and secrets remain ignored. A publishable-file scan found no matches for configured secret values or common credential patterns; this is a targeted check, not a claim that arbitrary secrets can always be detected.
