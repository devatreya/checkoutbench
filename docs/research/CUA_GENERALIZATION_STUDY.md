# CUA-S1-Forms generalization study

Experiment `cua-generalization-factorial-v1`, based on CheckoutBench `4df772d`.
Development diagnostics only; these interventions are not unmodified benchmark
performance or a comparative model ranking.

## Executive summary

The strongest explanation supported here is **sensitivity to both field wording
and candidate representation, with a substantial residual generalization gap**.
Familiar labels alone did not fix any of the seven changed-label fields. Neither
did document formatting alone on those same seven. Together they corrected
three: G01 email and recipient, and ST03 recipient. This is an observed positive
interaction on these paired inputs, not evidence that vocabulary alone explains
the failures.

Across all 23 checkout fields, effective-value accuracy was **3/23, 3/23, 5/23,
and 8/23** in A/B/C/D; strict assignment accuracy was **1/23, 1/23, 3/23, and
6/23**. Two empty optional fields are correctly skipped in every condition,
which explains the difference between those metrics. Even the combined
intervention leaves 11/18 required fields skipped. Familiar synthetic contracts
work, but several checkout fields with already-familiar labels fail.

All 244 planned passes used the pinned local model. No inputs were truncated,
all condition invariants passed, and four repeated distributions were exactly
identical on this runtime. The results identify causal effects of these
particular input interventions; the sample is too small and correlated to
estimate broad checkout performance or prove training-example memorization.

## Experimental methodology

The protocol is [machine-readable](../../research/cua-generalization-protocol.json).
It uses the three previously designated development cases V21-G01, V21-S01 and
V21-ST03, seed 2026, profile `aditi`. Every scenario field is projected into a
reproducible empty synthetic snapshot with its original public label, role and
section. These are independent model decisions, not an initial browser screen
or a sequential checkout rollout. No model action changes a subsequent input.
No sealed holdout or additional benchmark scenario is used.

Each snapshot receives four real local forward passes with the same pinned
706,048-parameter model, float32 CPU execution and one field per call:

| Condition | Field labels | Candidate serialization |
| --- | --- | --- |
| A | Original | path-v2 |
| B | Familiar equivalents where eligible | path-v2 |
| C | Original | document-v2 |
| D | Familiar equivalents where eligible | document-v2 |

All 75 original scalar candidates remain in their original order. The
document-v2 intervention changes capitalization, word order and punctuation;
it retains every parent qualifier. It is not an exact reconstruction of the
training document distribution. The experiment tests this serialization bundle,
not a particular punctuation change or target-specific candidate filtering.

There are 23 checkout fields: 18 required and five optional. Seven fields have
changed labels: Receipt email → Email address (G01); Recipient → Full name
(G01/ST03); Town / city → City (G01/ST03); Delivery PIN → Postal code (G01);
PIN code → Postal code (S01). Six already-familiar labels remain unchanged.
Ten fields have no defensible substitution for this study and remain controls.
The primary label-effect denominator is seven; the inclusive familiar cohort
is 13; serialization can be compared on all 23. Duplicate concepts across forms
are distinct scenario-field pairs but are not independent semantic samples.

Building components are not replaced with full street addresses. Billing
qualifiers are retained because shipping candidates coexist. Landmark and
delivery method have no positive upstream counterpart. Discount code occurs
in the upstream skip-only optional list, which differs from being unseen.
The S01 apartment field stays unchanged: pre-inference review found its
evaluator target is a landmark value and that removing `(optional)` would
also change an explicit cue. The fixture and its scoring remain untouched.

Seven existing synthetic contract snapshots are reported separately: three
empty familiar text fields, a prefilled email state, two checkbox states and a
submit button. Multiple states of one conceptual control are explicitly
observations, not independent fields. A supplemental candidate-confusion control
appends the same six plausible entities to every profile: emergency contact
email/name, employer address, birth city, previous postal code and work phone.
It preserves all original entities and runs every condition. It jointly tests
these distractors and the six-candidate increase; it cannot identify a pure
candidate-count effect.

Four extra forward passes repeat the first G01 field once per condition to
check same-runtime reproducibility. They are excluded from accuracy counts.
The planned total is 244 actual forward passes: 92 checkout, 28 contract,
120 supplemental and four repeats. Predictions from unit-test doubles never
enter these artifacts.

### Scoring and integrity

Private expected values are used only after inference. Field-value accuracy
uses the existing semantic-2 action-aware effective-value metric. Strict
assignment requires a correct fill/check; a correct skip is not an assignment.
Empty optional skips can be acceptable while remaining value-incorrect.
Required-empty skip rate uses only required, initially empty observations.
Wrong-value rate is reported both over all scored fields and over selected
fills. A button is an action-contract observation, excluded from field-value
denominators. Selected entity keys are retained, but value matches are not
claimed as proven entity-identity matches.

All paired effects use the same field IDs. The interaction is
`(D − C) − (B − A)` on the seven changed-label pairs. Exact counts and transition
directions accompany percentages. This is a descriptive case study of three
known development cases and one profile; no statistical significance or
population-level confidence claim is made.

The runner checks unchanged ordered entity key/value pairs, unchanged public
state except label, identical A/B and C/D option bytes, and identical A/C and
B/D context bytes. Input hashes, truncation, probabilities and execution
provenance are recorded. Raw values and byte encodings stay in exclusively
created mode-0600 files under ignored `data/`; committed evidence omits them.

The study entry point lives under `scripts/diagnostics/` and reuses
`scripts.research.cua_diagnostics` and the existing adapter. Extending the
original entry point would alter the frozen `scripts/research` source set.
This placement preserves the benchmark freeze without weakening its checks.

## Results

The primary results below exclude supplemental distractors and repeated calls.
The [machine-readable evidence](../../research/cua-generalization-evidence.json)
retains every prediction, complete distributions, top three alternatives,
selected source keys, confidence, timing, input hashes and scoring outcomes.
Raw selected values are only in the protected local artifact.

| Condition | Value accuracy, all fields | Strict assignment | Required-empty skips | Wrong fills / all fields | Wrong fills / fills | Optional acceptable |
| --- | --- | --- | --- | --- | --- | --- |
| A: original/path | 3/23 (13.0%) | 1/23 (4.3%) | 15/18 (83.3%) | 2/23 | 2/3 | 5/5 |
| B: familiar/path | 3/23 (13.0%) | 1/23 (4.3%) | 16/18 (88.9%) | 1/23 | 1/2 | 5/5 |
| C: original/document | 5/23 (21.7%) | 3/23 (13.0%) | 13/18 (72.2%) | 2/23 | 2/5 | 5/5 |
| D: familiar/document | 8/23 (34.8%) | 6/23 (26.1%) | 11/18 (61.1%) | 1/23 | 1/7 | 5/5 |

| Paired cohort | Coverage | A | B | C | D |
| --- | --- | --- | --- | --- | --- |
| Changed labels: primary label analysis | 7/23 | 0/7 | 0/7 | 0/7 | 3/7 |
| Already-familiar, unchanged controls | 6/23 | 1/6 | 1/6 | 3/6 | 3/6 |
| Inclusive familiar cohort | 13/23 | 1/13 | 1/13 | 3/13 | 6/13 |
| Excluded from label substitution | 10/23 | 2/10 | 2/10 | 2/10 | 2/10 |

The excluded cohort's two successes are correct skips on Discount code and
Gift message, whose expected values are empty in this selected profile. It has
zero correct assignments in all four conditions. Thus this study does **not**
demonstrate an incorrect Discount-code skip on a nonempty requested coupon;
the upstream skip-only supervision is a plausible future conflict, not an
observed error on this case.

### Paired transition counts

I/C mean incorrect/correct effective-value decisions. All terms in a row use
the same paired fields, and all failed predictions are retained.

| Cohort and contrast | I→C | C→I | I→I | C→C | Accuracy change |
| --- | --- | --- | --- | --- | --- |
| Changed 7: B−A, labels with path | 0 | 0 | 7 | 0 | 0/7 = 0 pp |
| Changed 7: D−C, labels with document | 3 | 0 | 4 | 0 | +3/7 = +42.9 pp |
| Changed 7: C−A, format with original labels | 0 | 0 | 7 | 0 | 0/7 = 0 pp |
| Changed 7: D−B, format with familiar labels | 3 | 0 | 4 | 0 | +3/7 = +42.9 pp |
| All 23: B−A | 0 | 0 | 20 | 3 | 0/23 = 0 pp |
| All 23: D−C | 3 | 0 | 15 | 5 | +3/23 = +13.0 pp |
| All 23: C−A | 2 | 0 | 18 | 3 | +2/23 = +8.7 pp |
| All 23: D−B | 5 | 0 | 15 | 3 | +5/23 = +21.7 pp |

The primary interaction `(D−C)−(B−A)` is **+3/7 = +42.9 percentage points**.
The two serialization-only recoveries outside the changed-label cohort are
S01 Full name and ST03 Email address. Averaging over already-familiar and
excluded fields would dilute the primary label contrast; those denominators
are shown separately rather than substituted for seven.

### Per-field paired predictions

`✓` means effective-value correct; `✗` means incorrect. A correct skip remains
strict-assignment incorrect. Candidate names below are source entity keys,
not customer values. `email` abbreviates `customer.email`, `name` abbreviates
`customer.full_name`, `landmark` abbreviates `customer.shipping.landmark`,
`registration` abbreviates `payment.registration_authorised`, `traveller name`
abbreviates `travellers.1.full_name`, and `traveller age` abbreviates
`travellers.1.age`. All other decisions in this table are skips.

| Field ID / original label | A | B | C | D |
| --- | --- | --- | --- | --- |
| G01:0 Receipt email | landmark ✗ | skip ✗ | registration ✗ | email ✓ |
| G01:1 Recipient | skip ✗ | skip ✗ | skip ✗ | name ✓ |
| G01:2 House / flat / building | skip ✗ | skip ✗ | skip ✗ | skip ✗ |
| G01:3 Town / city | skip ✗ | skip ✗ | skip ✗ | skip ✗ |
| G01:4 Delivery PIN | skip ✗ | skip ✗ | skip ✗ | skip ✗ |
| G01:5 Landmark | skip ✗ | skip ✗ | skip ✗ | skip ✗ |
| S01:0 Email | email ✓ | email ✓ | email ✓ | email ✓ |
| S01:1 Full name | skip ✗ | skip ✗ | name ✓ | name ✓ |
| S01:2 Address | traveller name ✗ | traveller name ✗ | skip ✗ | skip ✗ |
| S01:3 Apartment, suite, etc. (optional) | skip ✗ | skip ✗ | skip ✗ | skip ✗ |
| S01:4 City | skip ✗ | skip ✗ | skip ✗ | skip ✗ |
| S01:5 PIN code | skip ✗ | skip ✗ | skip ✗ | skip ✗ |
| S01:6 Delivery method | skip ✗ | skip ✗ | skip ✗ | skip ✗ |
| S01:7 Discount code | skip ✓ | skip ✓ | skip ✓ | skip ✓ |
| S01:8 Gift message (optional) | skip ✓ | skip ✓ | skip ✓ | skip ✓ |
| ST03:0 Email address | skip ✗ | skip ✗ | email ✓ | email ✓ |
| ST03:1 Recipient | skip ✗ | skip ✗ | skip ✗ | name ✓ |
| ST03:2 House / flat / building | skip ✗ | skip ✗ | skip ✗ | skip ✗ |
| ST03:3 Town / city | skip ✗ | skip ✗ | skip ✗ | skip ✗ |
| ST03:4 ZIP code | skip ✗ | skip ✗ | skip ✗ | skip ✗ |
| ST03:5 Landmark | skip ✗ | skip ✗ | skip ✗ | skip ✗ |
| ST03:6 Billing address | skip ✗ | skip ✗ | traveller age ✗ | traveller age ✗ |
| ST03:7 Billing ZIP code | skip ✗ | skip ✗ | skip ✗ | skip ✗ |

The two Landmark skips and apartment skip are optional-acceptable despite
being value-incorrect. G01 has six initial unique fields here, so its A result
is 0/6; the historical 0/7 included a second observation after an incorrect
email fill. The present design deliberately excludes that dependent revisit.

### Confidence and abstention

| Condition | Incorrect predictions | Mean selected confidence | Range | Incorrect confidence >0.99 | Incorrect required skips | Mean skip confidence |
| --- | --- | --- | --- | --- | --- | --- |
| A | 20 | 0.8466 | 0.3584–1.0000 | 11/20 | 15 | 0.8890 |
| B | 20 | 0.8692 | 0.3584–1.0000 | 11/20 | 16 | 0.8854 |
| C | 18 | 0.8475 | 0.3278–1.0000 | 6/18 | 13 | 0.8378 |
| D | 15 | 0.8815 | 0.3278–1.0000 | 6/15 | 11 | 0.8916 |

For example, G01 Receipt email chooses a landmark at 0.3806 in A, skip at
0.7513 in B, a payment-registration flag at 0.9475 in C, and the correct email
at 0.8593 in D. Serialization can therefore create a confident wrong fill
without changing binary correctness. S01 Delivery method receives skip
probability rounded to 1.0 in every condition. These are softmax probabilities,
not calibrated probabilities of completing checkout correctly. The mean
confidence of remaining errors rises in D even while error count falls; it
must not be read as improved calibration.

### Synthetic and supplemental controls

All four conditions achieve 6/6 effective-value accuracy, 5/6 strict assignment
accuracy and 7/7 action-contract accuracy on the seven familiar synthetic
observations. The already-checked checkbox is correctly skipped, explaining
the strict-assignment difference. The prefilled email is filled again with the
same correct value; this is a value success, not proof of optimal no-op behavior.
These seven observations cover five conceptual controls and are not a
reproduction of the publisher's large synthetic evaluation.

Adding six plausible distractors changes checkout candidate count from 75 to
81 and synthetic count from three to nine. Checkout accuracy stays 3/23,
3/23, 5/23 and 8/23 in A/B/C/D; synthetic scores also remain unchanged.
There are zero I→C or C→I transitions in any condition. All 23 pairs per
condition retain their correctness state: A/B have 20 I→I and three C→C;
C has 18 I→I and five C→C; D has 15 I→I and eight C→C.

Nevertheless, one of the 120 paired supplemental predictions changes entity:
G01 Receipt email in A switches from the original landmark to the added
Employer address (confidence 0.3085), still wrong. Candidate interference is
observable, but this control does not establish it as the main source of the
accuracy deficit. It also does not rule out confusion among the original 75
candidates or other kinds of distractor.

## Causal interpretation

| Hypothesis | What this experiment establishes | What remains unresolved |
| --- | --- | --- |
| Vocabulary memorization | Familiar wording alone gives 0/7 recovery with path-v2; with document-v2 it recovers 3/7. Labels matter conditionally. | The data do not prove memorization or a vocabulary-only cause. The training corpus is unavailable. |
| Entity serialization | At original labels, document-v2 recovers two already-familiar controls among all 23. | Capitalization, word order and punctuation changed together; parent qualifiers remain unlike many training options. |
| Interaction | Three fields require both interventions for recovery; the paired interaction is +3/7. | These three include the same Recipient wording in two similar forms, not three independent semantic discoveries. |
| Overconfident abstention | Incorrect required skips frequently have near-one probability, including familiar labels and supplied candidates. | Skip supervision, locale and representation shifts are plausible mechanisms; this experiment does not isolate their training contributions. |
| Unseen concepts | Excluded fields have no correct assignments; unsupported concepts remain a limitation. | Familiar City, ZIP code and Address also fail, so absence from the catalogue is not a sufficient explanation. Exclusions include semantic ambiguities, not just unseen labels. |
| Candidate confusion | One added plausible entity replaces another wrong choice; accuracy remains unchanged. | Candidate count and semantic content change together. More predeclared distractor sets and role/locale controls are needed. |

Further discriminating evidence would require a new predeclared study that
independently varies section titles, regional value formats, hierarchical
qualifiers and role-confusable candidates, with multiple customer profiles and
held-out label families. A matched familiar-label training-format dataset would
help separate representation shift from missing semantic capacity. Training
ablation would be needed to assign causality to the skip supervision policy.
Neither semantic repair of current predictions nor adaptive label tuning on
these same cases would answer those questions.

## Model architecture assessment

The pinned `tinyx` implementation embeds UTF-8 bytes in 128 dimensions, uses
two context Transformer layers and one option Transformer layer, then scores
each candidate against the context through an attention head. It reads up to
224 context bytes and 96 bytes per option. It selects an entity pointer or
`check`, `click`, `skip`; it does not generate a new value. The sidecar's legacy
Qwen metadata does not mean a pretrained Qwen language model is loaded.

The upstream generator samples form and document synonyms from a 55-concept
catalogue, omits some relevant entities, adds partial values and distractors, and assigns
evaluation splits by concept-set signature. That can test new combinations
without withholding the vocabulary. Skip is supervised for missing entities,
already-filled values and certain optional fields. These facts make narrow
lexical associations and confident out-of-distribution skips plausible; they
do not prove memorization or that parameter count causes any observed failure.
The actual checkpoint training corpus is unavailable. See the
[upstream audit](CUA_GENERALIZATION_UPSTREAM.md) for source identities and the
distinction between publisher-reported results and reproduced evidence.

## Engineering recommendations

1. **Keep CUA as a narrow specialist.** Preserve the current honest failure
   reporting and bounded controller. Use separately evaluated in-scope tasks;
   do not interpret high skip confidence as evidence that checkout is complete.
   This retains the small model's low local execution cost without claiming
   general checkout reliability.
2. **Broaden training data before choosing a new small-model recipe.** Include
   merchant wording, distinct shipping/billing and recipient roles, regional
   addresses, legitimate optional fills, several candidate representations and
   realistic confusable documents. Reserve label families, merchant templates
   and customer profiles for genuinely unseen evaluation. Data diversity is
   useful whether adapting this checkpoint or training a replacement.
3. **Then compare fine-tuning and retraining a small checkout model.** A 706K
   scorer is feasible to experiment with locally, but more examples cannot
   guarantee that its capacity or byte limits suffice. Measure catastrophic
   forgetting, unsupported concepts and skip calibration against untouched
   development partitions. No training was performed in this study.
4. **Evaluate a 4B reference challenger on a small separate pilot.** The
   [official CUA-S1-4B-0.2 card](https://huggingface.co/cua-ai/cua-s1-4b-0.2/raw/main/README.md)
   describes LoRA adapters on Qwen3.5-4B with separate text and multimodal modes.
   Pretrained language representations could improve semantic transfer, but
   CheckoutBench gains must be measured. This is a different decision interface,
   not a drop-in replacement for the 706K scorer. The
   [pinned upstream setup](https://github.com/trycua/cua/blob/6d82b3b1b21813ad047f966ab1384a1258c16170/libs/cua-s1/README.md)
   lists about 9.34 GB for the base plus 187 MB of adapters, estimates at least
   16 GB free memory, and requires a separate Transformers 5 environment.
   That has substantially greater memory and latency costs than the 2.8 MB
   Forms checkpoint; the benefit remains untested here. The pinned 4B option
   interface also accepts at most 26 choices, whereas this task has 75 entities
   plus three actions. A future pilot needs an explicitly audited interface;
   silently dropping candidates would invalidate the comparison.

## Reproduction and evidence identity

Protocol and implementation were committed **before inference** as `9cb0e8d`.
The value-free [freeze manifest](../../research/cua-generalization-freeze.json)
records protocol, input-design and source hashes. The runner rejects changes
to any frozen source/input or the pinned checkpoint/catalogue identity. The
actual run used Python 3.12.12, torch 2.14.1, safetensors 0.8.0, float32 CPU,
four threads, macOS 27.0.1 arm64, evaluation mode and no remote endpoint.

- Protocol SHA-256: `2709476363a733c674c5c9c5a67680eb6319801e5793ee8d26d5c6524a5b04a4`.
- Freeze file SHA-256: `505291b4a77e6fe49c731bb14a6db32f369dc879988ba467dd40355b33db686c`.
- Protected exact artifact SHA-256: `fb8a7d19e30ec56659eb2878f1ef84c3beea07f9824971cc51f948fd63dd27e6`.
- Public evidence SHA-256: `0c2de1000b4ab2bc3e5688e271d9a34454a64145b5505700b6c4c11dca6c714a`.

All 244 calls report `actual_model`. None of their contexts or options was
truncated. Four G01-email repeats had identical inputs, selected actions/keys
and every probability (maximum absolute difference 0). This checks a selected
snapshot in each condition on this runtime, not universal determinism.
Deterministic-algorithm enforcement was off; other hardware or runtimes may
produce numerical differences. A future rerun must not be counted as new
independent accuracy samples.

Every record includes measured latency. Median forward time was 9.62 ms across
the 120 primary passes and 10.27 ms across the 120 supplemental passes. These
mix checkout and synthetic candidate counts; regression tests ran concurrently
during part of execution. The timings are diagnostic observations, not a
controlled speed comparison.

From the repository root, with the already installed audited CUA runtime and
local checkpoint, use new output names to preserve previous evidence:

```sh
.venv/bin/python -m scripts.diagnostics.cua_generalization \
  --model-path "$PWD/data/research/checkpoints/cua-s1" \
  --device cpu \
  --freeze-manifest research/cua-generalization-freeze.json \
  --include-sensitive \
  --output data/research/cua-generalization/reproduction-exact.json \
  --summary-output data/research/cua-generalization/reproduction-summary.json

RUN_CUA_REAL=1 RUN_CUA_GENERALIZATION_REAL=1 \
CUA_S1_MODEL_PATH="$PWD/data/research/checkpoints/cua-s1" \
  .venv/bin/pytest -q tests/test_cua_generalization.py \
  tests/test_cua_fidelity.py tests/test_adapters.py tests/test_harness.py \
  tests/test_evaluator.py tests/test_official_results.py
```

To reproduce the original inference-free preregistration step on unchanged
sources, use `--write-freeze data/research/cua-generalization/new-freeze.json`.
It must reproduce the committed manifest exactly. Creating a different freeze
after modifying mappings would define a new experiment, not reproduce this one.

## Validation and preservation

The complete relevant test run passed **110 tests**, including genuine pinned
inference and deterministic repeat checks. Tests cover mappings, candidate and
state invariance, public-only input boundaries, paired matching and denominators,
optional scoring, redaction and the existing adapter/browser/evaluator/result
contracts. Four upstream nested-tensor optimization warnings were informational.
The full 174-scenario benchmark was not launched.

Final [integrity evidence](../../research/cua-generalization-integrity.json)
confirms all 87 frozen source files remain identical, as does release hash
`ca8a3a4d939fce39986e723d33203d9c76fb40bf5954e707204e252ab62332ee`.
The official database remains empty; all ten diagnostic database rows are
byte-for-byte unchanged. The original failure record and all 82 of its
artifacts match their preservation hashes. No model weights, original labels,
expected answers, execution defaults or official metrics were modified.

The [independent review](CUA_GENERALIZATION_REVIEW.md) verified raw/public
artifact identities, paired inputs, argmax/decoding, all 188 checkout grades
(including supplemental and repeat records), transition counts and control
interpretations. No blocking validity or leakage issue was found. A pre-commit
secret scan found no matches; exact customer/payment values remain in ignored
local storage.
