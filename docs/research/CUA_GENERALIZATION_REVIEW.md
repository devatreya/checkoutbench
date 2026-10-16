# Independent review of the CUA generalization study

This review is separate from experiment implementation. The reviewer did not run inference, change model inputs, edit benchmark fixtures, or alter evaluator truth. It covers the predeclared protocol, scoring implementation and retained genuine prediction evidence.

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

## Independent prediction and artifact audit

After all 244 genuine forward passes, the reviewer inspected both the protected exact artifact and [public evidence](../../research/cua-generalization-evidence.json). No additional inference was executed. The final protocol contains seven changed-label fields, six identity controls and ten excluded fields. The optional apartment mapping was removed before inference; it was not selected or rejected using prediction outcomes.

Verified identities:

| Artifact | SHA-256 |
| --- | --- |
| Protocol | `2709476363a733c674c5c9c5a67680eb6319801e5793ee8d26d5c6524a5b04a4` |
| Preregistered freeze | `505291b4a77e6fe49c731bb14a6db32f369dc879988ba467dd40355b33db686c` |
| Public evidence | `0c2de1000b4ab2bc3e5688e271d9a34454a64145b5505700b6c4c11dca6c714a` |
| Protected exact evidence | `fb8a7d19e30ec56659eb2878f1ef84c3beea07f9824971cc51f948fd63dd27e6` |

The exact artifact hash agrees with the public evidence; its embedded freeze agrees with the preregistered file. Every record reports the actual local model path with a positive model-forward duration. There are 120 primary passes, 120 supplemental passes and four excluded repeat passes. For all 60 group/field snapshot pairs, candidate keys, label-only option invariants and serialization-only context invariants hold. Unchanged labels yield identical probability vectors between A/B and C/D. None of the 244 contexts or their options is truncated. Selected indices match probability argmax, selected confidence matches the selected probability, and public input hashes and top-three alternatives match the exact artifact.

The reviewer independently reconstructed effective-value and assignment grades from original scenario truth for all 188 checkout records, including supplemental and repeat records. Every grade matched the stored result. Aggregate counts were separately recomputed from individual records rather than accepted only from the analysis summary:

| Primary checkout metric | A | B | C | D |
| --- | --- | --- | --- | --- |
| Field-value accuracy | 3/23 | 3/23 | 5/23 | 8/23 |
| Strict assignment accuracy | 1/23 | 1/23 | 3/23 | 6/23 |
| Required-empty skips | 15/18 | 16/18 | 13/18 | 11/18 |
| Wrong fills / all fields | 2/23 | 1/23 | 2/23 | 1/23 |
| Wrong fills / fills | 2/3 | 1/2 | 2/5 | 1/7 |
| Optional acceptability | 5/5 | 5/5 | 5/5 | 5/5 |
| Incorrect required skips with probability >0.99 | 10/15 | 10/16 | 5/13 | 5/11 |

Two of the three baseline value successes are empty optional skips for Discount code and Gift message. They are not successful assignments; the remaining baseline success is S01 Email. The synthetic controls are separately 6/6 value-correct and 7/7 action-contract-correct in every primary condition, with 5/6 strict assignments because the already-checked checkbox is skipped. The prefilled email is filled again: this is a correct value and accepted action, but is not evidence of perfect no-op behavior.

On the seven changed-label pairs, A, B and C each score 0/7, while D scores 3/7. B−A has seven incorrect→incorrect transitions. D−C has three incorrect→correct and four incorrect→incorrect transitions, with no regressions. Thus the observed interaction is +3/7 (42.9 percentage points), and the label-only gain under path-v2 is zero. Across all 23 fields, C−A gains two fields and D−B gains five, again with no correct→incorrect transitions.

The three changed-label gains are G01 Receipt email and the two Recipient fields in G01/ST03. These represent two changed label types, not three independent new concepts. The two additional serialization gains are unchanged-label S01 Full name and ST03 Email address. All six assignments that are correct in D belong to email or full-name fields. City, postal and address fields remain incorrect even when they have familiar labels. This supports a conditional label/serialization interaction and narrow concept success; it does not support a vocabulary-only explanation or broad checkout generalization.

The supplemental distractors change just one selected entity: G01 condition A switches from the wrong landmark entity to the wrong Employer address entity. No primary-to-supplemental correctness transition occurs in any condition, and synthetic control actions remain correct. This confirms that candidate semantics can influence an erroneous selection, while providing no evidence of an accuracy loss from this particular six-entity addition. It does not establish general resistance to candidate confusion.

All four designated repeat checks have identical inputs, predictions and distributions, with maximum probability difference 0.0. The runtime reports CPU float32 with four threads and deterministic algorithms disabled. The verified reproducibility claim is limited to these selected same-runtime repeats; it does not establish cross-device reproducibility or independent statistical replication.

## Review conclusion

No blocking scoring, pairing, candidate-preservation or inference-envelope leakage defect was found in the retained study. The evidence warrants a descriptive conclusion that label and entity representation interact on a few familiar concepts, while substantial failures remain. It does not prove memorization, isolate all distribution-shift causes, or measure end-to-end completion after either intervention. Keep these diagnostics separate from official benchmark results and preserve the original fixture/label mismatch as an explicit limitation.
