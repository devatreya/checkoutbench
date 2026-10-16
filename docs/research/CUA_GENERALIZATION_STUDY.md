# CUA-S1-Forms generalization study

Experiment `cua-generalization-factorial-v1`, based on CheckoutBench `4df772d`.
Development diagnostics only; these interventions are not unmodified benchmark
performance or a comparative model ranking.

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

## Model architecture assessment

The pinned `tinyx` implementation embeds UTF-8 bytes in 128 dimensions, uses
two context Transformer layers and one option Transformer layer, then scores
each candidate against the context through an attention head. It reads up to
224 context bytes and 96 bytes per option. It selects an entity pointer or
`check`, `click`, `skip`; it does not generate a new value. The sidecar's legacy
Qwen metadata does not mean a pretrained Qwen language model is loaded.

The upstream generator samples form and document synonyms from a 55-concept
catalogue, adds missing entities, partial values and distractors, and assigns
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

## Execution status

Protocol and methodology are being finalized before genuine study inference.
Results, independent review, integrity verification and exact reproduction
commands will be recorded below after execution.
