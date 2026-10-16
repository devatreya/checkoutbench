# Independent review of the CUA generalization study

This review is separate from experiment implementation. The reviewer did not run inference, change model inputs, edit benchmark fixtures, or alter evaluator truth. It covers the predeclared protocol, scoring implementation and, once available, retained prediction evidence.

## Methodology review before inference

The designated development set contains 23 scenario-field pairs: 18 required and five optional fields, drawn from G01, S01 and ST03 with one fixed synthetic customer profile. These are reproducible empty field snapshots, including fields that might occur at different checkout stages. They are not a browser rollout or a representative random sample of checkout tasks. Four conditions on the same field are paired observations, not four independent samples.

The primary label contrast must include only fields whose labels actually change under a defensible equivalent-label mapping. Already familiar labels are unchanged controls; excluded concepts remain in separately reported serialization comparisons. The interaction must use the same field cohort for every term: `(D - C) - (B - A)`. Synthetic contract controls and deterministic repeat checks must not inflate the checkout denominator.

The mappings preserve source-role distinctions where needed: building/flat fields cannot simply become street-address fields, Landmark has no positive upstream counterpart, and removing a Billing qualifier would erase a distinction between competing customer entities. A pre-inference review additionally identified that replacing `Apartment, suite, etc. (optional)` with `Apartment or unit` removes an explicit optionality cue. This field should remain outside the primary label intervention. Read-only inspection also confirmed that its existing S01 evaluator target matches `customer.shipping.landmark`, which is not an apartment/unit entity. That fixture mismatch is a limitation to report, not an instruction to change benchmark truth during the study.

The two serializers are bundles of surface changes: document-v2 changes capitalization, word order and punctuation while retaining parent qualifiers. A measured effect identifies this declared bundle; it does not isolate one punctuation or ordering mechanism. Candidate keys, underlying values and ordering must be identical across the factorial conditions, with context/options hashes establishing the intended isolation. Supplemental distractors must be appended using one task-wide policy, without target-dependent pruning.

## Scoring checks

- Value accuracy requires both an appropriate action and an effective value matching the independent evaluator. Strict assignment additionally requires fill/check; an already-correct skip can therefore be value-correct without being an assignment.
- Empty optional skips may be acceptable without matching a nonempty document value. Their acceptability must not be renamed strict accuracy.
- Required-empty skip rate uses required fields whose initial state is empty. Prefilled synthetic controls do not belong in that denominator.
- Wrong fills divided by all scored fields and wrong fills divided by selected fills answer different questions and need separate denominators.
- Repeated warm checks, condition-dependent revisits and multiple observations of one control are not additional unique checkout fields.
- Strict value/assignment scores are not strict entity-identity scores. Equal-valued candidate entities can match the target value without establishing the intended source identity.
- Inference construction may use only the public field snapshot and customer document. Private expected values and field mappings belong solely in post-inference scoring.

## Interpretation limits

The selected cases are known development examples and only one profile is evaluated. Exact transition counts and paired deltas are appropriate; population-level significance claims are not. Negative or small label effects do not establish that vocabulary never matters. Positive serialization effects do not prove that the model understands the underlying checkout concepts. Near-one skip probabilities document confident errors on these inputs, but do not establish a calibrated estimate of correctness or explain the training mechanism that produced them.

The official upstream generator and catalogue are inspectable evidence of distribution design. Without the exact training corpus and held-out training lineage, they do not prove that a particular checkpoint memorized individual examples. A 706,048-parameter byte-level scorer plausibly has limited semantic generalization, but parameter count alone is not a causal result of this experiment.

## Evidence review status

Pre-inference methodology review completed. Actual-result verification will be appended after the experiment artifacts are available; no outcome claims are made in this version.
