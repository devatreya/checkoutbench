# Scenario naming and UI-Venus integrity audit

This audit separates canonical checkout tasks from public display identities,
model adapters, execution software and isolated diagnostics. It does not treat
a model's poor performance as a reason to simplify the checkout tasks.

## Historical scope and findings

The reviewed range is `67e1ba7..438ed86`: the last unified-results change through
the completed CUA factorial investigation. No file under `scenarios/` or
`checkout_fixtures/` changed in that range. `backend/fixtures.py`, the objective
checkout scorer in `backend/evaluator/scoring.py`, and the historical V2 scorer
also remained identical. All 44 inventoried Git tree entries across those paths
match between the two commits.

The two frozen release records contain the same 174 scenario entries and the
same manifest hash:
`0f08c4d2c46d05e57484ec67f6b194af012488841355ce7451e1620d3fa93d97`.
Removing only `source_hashes`, `source_hash`, and `release_hash` from those records
leaves identical payloads. The earlier harness integration updated the source
binding and release hash because execution/scoring code changed; it did not
regenerate or modify scenario definitions. The current task preserves the
existing `research/release.json` bytes and release hash
`ca8a3a4d939fce39986e723d33203d9c76fb40bf5954e707204e252ab62332ee`.

| Changes | Classification | Audit conclusion |
| --- | --- | --- |
| `7951e51`, `f1709d4`, `d09b3fc`: bounded retries, state observations, correct checkbox/click intent, stale-target checks, provider-transition waits | Legitimate execution correctness | Changes the harness, not labels, field order, markup, expected answers or fixtures. Wrong model choices remain wrong; retries terminate with evidence. |
| `5683eb5`: native CUA state/hint encoding and role normalization, checkpoint/probability evidence | Legitimate adapter fidelity | Uses visible/public field state. The default path-v2 preserves original candidate order and values; checked state is not an oracle hint. |
| Optional document-v2 serialization in the adapter | Isolated diagnostic capability | Explicitly selected by the diagnostic harness; not silently enabled in the standard CUA controller. It does not mutate checkout labels or customer values. |
| `5683eb5`, `e5048ff`: action-aware semantic grading and richer decision/trace reporting | Legitimate measurement correctness | Adds explicit assignment, optional, unknown and repeated-decision denominators. Objective task success and private expected values remain unchanged. New measurement protocols must not be pooled with old ones merely because task content is identical. |
| `scripts/research/cua_diagnostics.py` and its synthetic count/order/state controls | Isolated diagnostics | Public input projections and separate post-inference scoring; synthetic controls are labelled separately from benchmark results. |
| `9cb0e8d`, `438ed86`: familiar-label transformations, serialization factorial and supplemental candidate controls | Isolated diagnostics | Mappings occur only in copied diagnostic snapshots. No original label, DOM, fixture state or official result was rewritten. The optional apartment mapping was excluded before inference on semantic grounds. |
| Regression tests, documentation and sanitized research evidence | Validation and reporting | Preserve failure evidence and explain limitations; test doubles are not real-model results. |

No inappropriate model-specific fixture accommodation was found in the reviewed
range, so no canonical fixture reversion is warranted. The existing reference
`semantic_value` helper is AST-identical between the two commits and is not a
new semantic correction for CUA. Its deterministic-reference/TinyClick-assistance
track remains distinct from CUA field decisions and end-to-end screenshot agents.

There is a documented existing ambiguity: the Shopify-inspired apartment/suite
field is evaluated against the shipping landmark entity. The CUA study retained
and disclosed this mismatch instead of rewriting the fixture to improve a score.
Correcting such a task later would require its own documented scenario revision;
the naming/UI-Venus work does not silently change it.

## Preserving canonical identity while adding public names

`research/scenario-integrity-baseline.json` inventories all 322 canonical scenario
objects at their existing default seed/profile and the original scenario/fixture
source files. Each object is hashed using the established scenario digest. A
public name belongs in the API/display envelope; canonical scenario objects,
stored canonical IDs, URLs and frozen task hashes remain unchanged.

The catalog resolver may accept an alias before calling the original canonical
generator. Its structural wrapper is permitted only when every original
canonical ID still generates its exact baseline object. The registry is a new
explicit `scenarios/identity.py` file with `scenarios/identities.json` data.
Both registry code and mapping data belong in the runtime source binding.
Existing scenario-generator and fixture
files remain protected. The full-object check covers field wording/order,
initial state, synthetic data, task goal and evaluator truth for every
inventoried canonical scenario; source protection additionally prevents changing
other seed/profile behavior inside the underlying generators.

## Separate runtime binding without rewriting the frozen release

New adapter and runner code legitimately changes the runtime source hash.
Rewriting `research/release.json` to make that change disappear would lose the
distinction between immutable task identity and execution protocol. Instead,
`backend/research/runtime_binding.py` validates an explicit
`research/runtime-binding.json` linked to the existing frozen release.

The artifact contains the frozen release/manifest/source hashes, the complete
new source map and its digest, an explicit before/after map for every changed
source, the canonical-scenario baseline hash/proof, and a review record. Its
`binding_hash` covers the entire payload. This is a repository audit record,
not a cryptographic publisher signature.

- Exact original sources retain the original identity and require no new binding.
- Changed sources require an exact matching reviewed artifact. Missing, pending,
  tampered, stale or different-release bindings fail closed.
- Candidate generation defaults to `review.status=pending`. Execution never
  generates or approves its own binding. Approval requires an explicit reviewer
  and review summary after the integration is inspected.
- Existing generator/fixture sources, newly added model-specific fixture sources,
  `backend/fixtures.py`, and objective checkout scoring cannot be approved as
  runtime-only changes. The catalog alias wrapper is the narrow exception,
  guarded by the complete canonical-object comparison.
- The frozen release file must match its baseline checksum. The runtime audit
  cannot authorize replacing that frozen file.
- Every new run must retain the runtime binding and current source identity;
  the protocol fingerprint and official dataset selector must include it.
  Keeping the old manifest hash does not make old/new execution protocols
  comparable. Legacy records remain readable and are never rewritten.

The binding verifier itself validates the scenario objects and protected files.
Its caller additionally checks the current active manifest against the frozen
manifest. An approved artifact matches the complete current source map, so any
later adapter, observer, action executor or scorer change requires another audit.

## Track comparability and UI-Venus review requirements

The screenshot model must receive its permitted screenshot/task/history inputs,
not DOM labels, private expected answers, target selectors or post-inference
corrections. DOM-based observation used by a deterministic CUA field controller
is a different declared model-execution track; its navigation assistance cannot
be presented as identical autonomy to UI-Venus.

Shared initial tasks, viewport, seed/profile, budgets, success verification and
runtime binding should be retained for matched comparisons. Model-native prompt,
coordinate conventions, image scaling, precision and history policy must be
recorded explicitly. Independent objective evaluation decides success even if
the model says it has finished. Unsupported actions, malformed output, inference
failures and valid-but-wrong actions require distinct evidence, not an invented
success or a silent retry under a different prompt.

## Validation record

The initial runtime-binding test run passed 19 tests. These cover original-source
compatibility, missing/pending approvals, source/release/manifest/artifact drift,
catalog alias output identity, protected source rejection, baseline changes and
all 322 original canonical scenario hashes. This audit does not claim that
UI-Venus inference or a full model benchmark has completed; those require their
own retained execution evidence from the integration owner.

The focused runner integration suite passed 16 tests. It verifies public-alias
normalization without changing caller configuration, canonical/public identity
persistence, runtime and scenario lineage for historical v2.1 diagnostics,
viewport/task/source metadata, explicit inference/unavailable/unsupported/invalid
output categories, and screenshot-agent stall attribution without attributing
model-selected navigation to the deterministic field controller. Browser and
inference doubles in this suite are explicitly labelled, saved only under test
temporary directories, and rejected as genuine inference evidence. These tests
do not constitute model performance measurements.

Final integration review identified two publication boundaries, both corrected
by the integration owner: official checkpoint identity now binds runtime
configuration such as image/history/token limits and native prompt/source/artifact
identity; `analysis.json` now applies the same per-run export allowlist as
`runs.json`. Eight focused publication tests passed, verifying rejection of seven
changed model execution contracts and exclusion of private diagnostic/raw-output
sentinels throughout the exported ZIP while preserving private run evidence.

The additional legacy-identity regression also passes after preserving the
original dictionary shape for checkpoints without Venus-specific fields. All
nine publication-boundary tests and seventeen runner-lineage tests pass. The
final runtime binding separately records this correction; the pilot retains its
original binding and an exact local source snapshot. Historical records were not
rewritten to obtain compatibility. Explicit invalid-output rate tests use only
completed genuine generations as the denominator, while inference failures use
all attempted calls.

Final model-contract review corrected an initial resized-pixel interpretation to
the UI-Venus 1.5 report's normalized 0–1000 coordinate contract. The initial
seven-case pilot is preserved and explicitly excluded from performance evidence;
its original classification labels are not rewritten. The same pilot plan must
be repeated with the corrected adapter. No fixture or prompt tuning accompanied
this correction.

A further metrics review preserves the shared inference exception class when
adapter metadata contains an underlying transport error, and counts only
already-loaded calls in warm inference timing. The focused final regression
suite passed 138 tests, including transport-cause accounting and two-request
cold/warm worker metrics with explicit model doubles.
