# Guided dashboard update

This update separates software validation from AI evaluation and gives each dashboard section a clear purpose. The checkout fixtures, model adapters, private scoring rules and stored historical runs are unchanged. The full regression attempt also exposed a legacy-controller navigation interruption, addressed below.

## User workflow

- **Overview:** a starting point with quick/full v2.1 reference presets, an explanation of decision-making versus browser execution versus scoring, and links to the next step. Presets configure a batch and require explicit review before starting.
- **Models:** dedicated system selection, visible availability reasons, explanation of specialist roles, and a next-step button. The available-frontier shortcut selects only available API models.
- **Scenarios:** dedicated task selection with descriptive names, a scrollable list, selected-system summary, clear-selection and reset-setup actions, and an independent preview. Hidden selections outside the active filters are counted explicitly.
- **Coverage:** source provenance, synthetic/approximate behavior, author criteria and reference validation. Labels explain that its inventory spans all versions and that resetting affects only the preview.
- **Live session:** active execution and queue controls, with explanations of pause and stop semantics.
- **Results:** version and reference/AI filters consistently apply to system rows, scenario matrix and run history. Reference validation is labelled separately; migrated holdouts are not described as fresh unseen tasks. Link comparisons keep their independent pairing rules. Exports remain complete history snapshots.

The overview counts reference passes and AI evaluations separately. It does not present reference success as an AI success rate. The reference review dialog explicitly says it makes no model inference calls.

## Fresh-start behavior

Every scored trial already gets fresh browser and checkout state. The UI explains three different actions: reset a practice preview, reset batch setup, and start a server with a new results directory. It does not introduce a destructive history-clear endpoint. Existing SQLite data, local credentials and artifacts remain intact.

## System description

The dashboard configures the runner. A reference script or a real model adapter selects actions, browser tooling executes them in Chromium against local simulated fixtures, and a private evaluator scores the resulting state. SQLite stores results; screenshots, traces and optional videos provide evidence. Reference execution and controlled model test doubles validate this apparatus, not model intelligence or exact production-site fidelity.

The README includes architecture, a section-by-section guide, software-check/model-evaluation instructions, and commands for isolated result directories. Actual specialist checkpoints, official SDK validation and current authenticated government interfaces remain outside the evidence supplied by this UI update.

## Legacy navigation regression

The first full-suite attempt reported an `invalid_browser_action` in a preserved v2 authentication-return path even though its fields were correct and it had reached `gateway_return`. The behavior was intermittent: a separate 24-run S06/L08 diagnostic batch completed successfully.

A forced-interruption regression test demonstrated that v2 observation did not recover from a detached frame or an execution context destroyed by navigation. The controller now re-observes public browser state for these specific errors, or when an authentication popup closes while the original page remains open. Permanent action errors still propagate. This changes runtime resilience only; it does not change scenario definitions, expected answers, scoring, historical result records or model predictions.

Before the fix, the two navigation-recovery cases failed and the permanent-error case passed. All three pass after the fix. The final complete regression run follows this correction; the earlier interrupted attempt is disclosed in the validation record.

## Validation evidence

**Final full suite: 70 passed in 652.00 seconds (10m 51s).** The production build passed. All 12 dashboard captures had zero document overflow and zero JavaScript errors. See [validation.json](validation.json) and [pytest output](pytest.txt) for evidence. The two added Playwright tests exercise behavior: presets require review without starting a batch, reset setup restores one reference scenario, and result filters separate model/reference runs and historical versions. Model calls are not needed.

[Visual inspection](screenshots/inspection.json) covers Overview, Models, Scenarios, Coverage, Live session and Results at 1440×1000 and 390×844. Full-page captures include scrollable lists/tables in their initial scroll positions. Screenshots show the existing local history at capture time; they are not outputs from the isolated pytest database.

- [Desktop overview](screenshots/overview-1440.png)
- [Phone overview](screenshots/overview-390.png)
- [System selection](screenshots/models-1440.png)
- [Scenario setup](screenshots/scenarios-1440.png)
- [Coverage](screenshots/coverage-1440.png)
- [Results](screenshots/results-1440.png)

To reproduce the dashboard captures against the running app:

```sh
.venv/bin/python -m scripts.visual_dashboard
```

The script opens each section at both widths, waits for visible checkout frames, records browser errors/overflow, and captures the page. It creates practice previews only and never starts a model or reference batch.
