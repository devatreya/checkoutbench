# CUA-S1-Forms: upstream distribution and vocabulary audit

This is source analysis for the [controlled generalization study](CUA_GENERALIZATION_STUDY.md), not a new model-performance result. The mappings below were communicated to the experiment owner before inference. No fixture, adapter, model weight, or official result was changed by this audit.

## Provenance and limits

The inspected checkout is clean at `trycua/cua` revision `6d82b3b1b21813ad047f966ab1384a1258c16170`. The checkpoint is `cua-ai/cua-s1-forms` revision `4a7a9f42a3d42e6dfbd111c0c843e37ac50f1332`. The four implementation sources are [schema.py](https://github.com/trycua/cua/blob/6d82b3b1b21813ad047f966ab1384a1258c16170/libs/cua-s1/python/src/cua_s1/schema.py), [synth.py](https://github.com/trycua/cua/blob/6d82b3b1b21813ad047f966ab1384a1258c16170/libs/cua-s1/python/src/cua_s1/synth.py), [concepts.py](https://github.com/trycua/cua/blob/6d82b3b1b21813ad047f966ab1384a1258c16170/libs/cua-s1/python/src/cua_s1/concepts.py), and [model.py](https://github.com/trycua/cua/blob/6d82b3b1b21813ad047f966ab1384a1258c16170/libs/cua-s1/python/src/cua_s1/model.py).

The current source generator is inspectable; the exact historical training corpus and its release manifest are not distributed with this component. Source defaults describe plausible training mechanisms, not proof of every example seen by these weights. The pinned Hugging Face card reports 10,000 synthetic training episodes, six epochs, AdamW, and a cosine schedule. It describes forms with 2–16 fields; the inspected generator starts with 4–16 sampled concepts and then appends hard-negative concepts and optional fields, so its final field count can exceed 16. Do not silently equate the present implementation and the unavailable historical corpus. [Pinned checkpoint card](https://huggingface.co/cua-ai/cua-s1-forms/blob/4a7a9f42a3d42e6dfbd111c0c843e37ac50f1332/README.md).

| Artifact | SHA-256 |
| --- | --- |
| `schema.py` | `89091773b050f538cb914a4da4cda59da0afa772b245b8e1264aa55e7e4b0e57` |
| `synth.py` | `ba01ad9c9942d7141680ba8cb3df8e55240512bbd6fbcce75bf1cc18e81aa03b` |
| `concepts.py` | `e5f7b87ca6eb8a07eb7d47f599ef7626b4e089873032d5d9acc9034ff88afbc4` |
| `model.py` | `7538cb4c9730d70a0b325050f370f981a9e109a1b182b8c66be3ba0fa2474344` |
| `training/train.py` | `c8c77c247246bdc09e15204fffb1b194bfbbe3d453e4a3d597b65b526351b80a` |
| `evals/metrics.py` | `49dccdeb4e2b456187cdc4491a6d78fabac6a45384272f8e3ec802a58872aa6e` |
| Upstream `MODEL_CARD.md` | `1c7cb81855c701755e377aa6e90a4d5af74ff0fe9cab822b484031160722de6a` |
| Pinned Hugging Face `README.md` | `854077f0ef3c89ea0a507a63e83ea9e16150c212cbfe7e01b021fafbb0fe5ca2` |
| Model tensors | `05954c1caf51c2fb6c13ea4acbfc88a2e7653dea192252bb51dc89e76a356ddc` |
| Model JSON sidecar | `62d31e2f9a001a8e9b6f8534c5194d07ebdd3f9d62ef1ac281906622992650ca` |

## Relevant exact catalogue vocabulary

The 55 concepts provide separate finite synonym lists for form labels and document labels. The generator samples each side independently, so matching across catalogue synonyms is trained. It does not generate unrestricted paraphrases or cross-language equivalents.

| Concept | Exact form labels | Exact document labels |
| --- | --- | --- |
| `full_name` | Full name; Name; Your name; Applicant name; Patient name; Legal name; Name (as on ID) | Name; Full name; Patient; Applicant; Legal name; Insured |
| `email` | Email address; Email; E-mail; Contact email; Your email; Email Address | Email; E-mail; Email address; Contact |
| `street` | Street address; Address; Address line 1; Street; Home address; Mailing address; Residential address | Address; Street; Home address; Residence; Address line 1 |
| `unit` | Address line 2; Apt / Suite; Apartment or unit; Unit number | Apt; Unit; Suite; Address line 2 |
| `city` | City; Town; City / Town; Town or city | City; Town |
| `zip` | ZIP code; Postal code; Zip; ZIP; Postcode; Zip / Postal code | ZIP; Zip code; Postal code; Postcode |

The complete concept keys are: `first_name`, `last_name`, `full_name`, `email`, `phone`, `work_phone`, `dob`, `street`, `unit`, `city`, `state`, `zip`, `country`, `insurer`, `policy`, `group_no`, `member_id`, `ec_name`, `ec_phone`, `ec_relation`, `employer`, `job_title`, `years`, `salary`, `start_date`, `linkedin`, `website`, `ssn`, `license`, `passport`, `car_make`, `car_model`, `car_year`, `plate`, `vin`, `bank`, `account`, `routing`, `university`, `degree`, `grad_year`, `reason`, `blood`, `allergies`, `medications`, `doctor`, `sex`, `marital`, `nationality`, `tax_id`, `company_reg`, `claim_no`, `incident_date`, `incident_desc`, and `cover`.

The absence of a positive concept does not imply that a label was unseen. `Discount code` is an exact member of `OPTIONAL_FIELDS`, whose elements never receive a document entity and are supervised as `skip`. That list also contains `Promo code (optional)`, `Coupon code`, `Confirmation code`, and `Voucher`. A checkout that supplies a legitimate discount value conflicts with this generator convention. `Landmark`, shipping service, and billing-versus-shipping distinctions have no corresponding positive concepts. `cover` is a job-application cover letter; its document synonyms include Message, but that does not establish a positive gift-message concept.

## Predeclared label intervention

Only the displayed label changes; the section title, role, value/state, candidate entities, ordering, and all other context remain fixed. No mapping is supplied as an instruction or extra model hint. Changed-label comparisons and already-familiar identity controls require separate denominators.

| Original label | Familiar label | Cases | Reason and limitation |
| --- | --- | --- | --- |
| Receipt email | Email address | G01 | Both request the email address for this checkout; purpose is retained in task context, but the receipt modifier is removed. |
| Recipient | Full name | G01, ST03 | A person receiving the delivery; scope remains Delivery. The original customer/traveller candidates remain, so competing names are not pruned. |
| Town / city | City | G01, ST03 | Equivalent locality concept. |
| Delivery PIN | Postal code | G01 | Delivery section establishes postal PIN rather than authentication PIN. |
| PIN code | Postal code | S01 | Delivery section establishes postal meaning. |

Already-familiar labels remain verbatim: S01 `Email`, `Full name`, `Address`, `City`; ST03 `Email address`, `ZIP code`. These six controls test deterministic condition isolation and serialization effects; they are not six successful vocabulary substitutions.

Excluded from label-effect denominators, but retained as unchanged observations in each condition:

| Original label | Cases | Why excluded |
| --- | --- | --- |
| House / flat / building | G01, ST03 | A building/unit component is not generally a complete street address. Neither Street address nor Apartment or unit is a defensible exact replacement. |
| Apartment, suite, etc. (optional) | S01 | The fixture expects its address2 value from the customer landmark entity, so the semantics are not a clean upstream apartment/unit match. Replacing the whole label also removes its optional cue. Independent review excluded this initially proposed mapping before inference; the fixture and truth remain unchanged. |
| Landmark | G01, ST03 | No positive upstream concept. |
| Delivery method | S01 | No positive shipping-service concept; the control also uses ComboBox rather than the generator's ordinary Edit role. |
| Discount code | S01 | Known skip-only training label, no positive value-assignment synonym. |
| Gift message (optional) | S01 | No corresponding positive concept; a cover letter is not a gift message. |
| Billing address | ST03 | Removing Billing loses the distinction from simultaneous delivery candidates. |
| Billing ZIP code | ST03 | Removing Billing loses the distinction from the simultaneous shipping postal code. |

Coverage is seven changed-label fields (G01 four, S01 one, ST03 two), six already-familiar controls, and ten excluded fields, across 23 unique case/field pairs. The inclusive familiar/eligible set is 13/23; the direct label-change effect uses 7/23. Shared labels across cases are correlated wording examples, not independent vocabulary samples. Eligibility is a semantic judgment declared before predictions, not proof that all role ambiguity disappears. The experiment owner froze this final set after semantic review and before inference.

## What differs from CheckoutBench

| Dimension | Pinned generator | CheckoutBench diagnostic |
| --- | --- | --- |
| Form wording | Samples catalogue synonyms and fixed optional/chrome/button wording | Merchant and portal wording, composite labels, role-qualified billing fields, regional PIN terminology |
| Document labels | Short independent concept synonyms | `path-v2`: full hierarchical paths rendered as space-separated words; `document-v2`: leaf first with parent qualifiers |
| Example candidate representation | `fill City: …` | `fill customer shipping city: …` versus `fill City (customer / shipping): …` |
| Candidate pool | Form-driven concepts, up to five extra concepts and three distractors, shuffled | All 75 scalar customer, delivery, traveller, appointment, payment and other public entities; no target-dependent pruning |
| Person/role structure | One primary synthetic person with explicit work/emergency confusers | Multiple people and billing/shipping roles can share concepts or values |
| Locale/value patterns | US city/state/ZIP triples, mostly English labels, 202 reserved phone forms; country sampled from seven choices | Indian customer/address/phone/PIN patterns alongside global merchant wording |
| Source presence | Each relevant concept omitted with probability 0.12 by default | Correct legitimate values generally retained; missing/empty and optional semantics handled separately |
| Skip supervision | Missing concept, optional-only fields, already-filled fields, browser chrome, non-submit buttons | Required empty checkout fields should be filled when a legitimate candidate exists |
| Ordinary field role | `episode_rows` creates Edit for every concept regardless of its kind | Edit and ComboBox visible controls; synthetic controls separately exercise checks and buttons |
| Form title | Sixteen application/intake/onboarding titles, optional browser suffix, sometimes generic/empty | Contact, Delivery, Billing, contact, delivery, shipping section titles |
| Evaluation unit | Per-element pointer/action choice | This study also uses per-field decisions, but actual CheckoutBench additionally requires browser execution, navigation and independently verified completion |

`document-v2` is not the upstream training representation exactly: it keeps every parent qualifier and uses generic leaf sentence casing, not a concept dictionary. Thus a serialization effect cannot establish that candidate strings have become fully in distribution.

A descriptive, inference-free sample of the current generator for seeds 0–999 produces 25,690 decisions: 11,179 fill, 12,651 skip, 860 check, and 1,000 click. Entity counts range 6–31 with median 17. Skip represents 49.25% of these generated rows. This sample describes source defaults, not the checkpoint's training-data composition. The sidecar's recorded best validation set has 22,054 decisions: 8,764 fill, 11,516 skip, 835 check, and 939 click.

## Architecture and possible failure mechanisms

The actual `tinyx` implementation uses 257 byte embeddings including padding, width/rank 128, a two-layer context Transformer, a separate one-layer option Transformer, four attention heads, and an option-attention scoring head. The JSON limits are 224 context bytes and 96 bytes per option. The `hf_model` string in the sidecar is unused by this architecture; no Qwen language model supplies semantic representations. Each field is scored independently, without previous-field memory, screenshot understanding, or generation of new values. The model selects a source entity or one of check/click/skip.

The model first encodes each option separately, mean-pools its contextual byte states, and uses the option as a query over context tokens. It computes one logit per option and softmaxes over the candidates. There is no candidate-to-candidate attention or global assignment constraint. Adding a distractor can win against the target or lower normalized confidence; it does not teach the model to reconcile two entities as a joint reasoning problem. In exact arithmetic, unchanged options retain their relative logits when other options are appended; changes in batching/padding can still cause small numerical differences.

This capacity and objective can support strong matching within a finite vocabulary without guaranteeing paraphrase or concept generalization. The broad skip class receives supervision from several distinct mechanisms, including absent entities and non-actionable controls. High skip probability is only a learned closed-set classification score, not a calibrated judgment that checkout is complete or out of distribution. Cross-entropy training and a finite-vocabulary dataset make overconfident transfer errors plausible. The architecture alone does not prove memorization, nor do the default skip prevalence or parameter count establish why a particular prediction failed. Our paired interventions must supply that evidence.

## What upstream reported accuracy establishes

The pinned Hugging Face card reports author-supplied 99.95% synthetic test accuracy on about 15,000 decisions, 100% on a 196-decision real demo set consisting of three forms and three PDFs, and 37% under shuffled context. It explicitly says the supporting results document is absent from the repository and these results are not reproduced by the component. The local sidecar records best-validation top-1 `0.9994105100631714`, not a new independently measured test result. [Pinned card](https://huggingface.co/cua-ai/cua-s1-forms/blob/4a7a9f42a3d42e6dfbd111c0c843e37ac50f1332/README.md).

The inspected split function hashes the sorted concept-set signature (plus optional labels) into train/validation/test. This prevents identical field sets crossing splits, but the same concept vocabulary and label synonyms remain available in every split. It tests recombination of familiar concepts, not held-out label paraphrases, languages, payment terminology, billing roles, or merchant workflows. A high per-decision number includes easy skip/chrome rows and does not equal end-to-end checkout success. The three-form demo cannot establish broad merchant or regional coverage. The shuffled-context degradation demonstrates use of context; it does not distinguish lexical association from transferable semantics.

The pinned upstream repository's own model card also reports an external diagnostic: 2,993/3,070 correct in-distribution synthetic decisions, 12/41 correct over five out-of-catalogue forms, 36/41 skip predictions with mean probability 0.974, and 11/11 correct after relabeling a subset. It warns that the out-of-distribution set is small. Those are prior reported results, not CheckoutBench measurements or additional independent observations in our experiment. The model card does not establish complete reproducible raw artifacts for that external subset. [Pinned upstream model card](https://github.com/trycua/cua/blob/6d82b3b1b21813ad047f966ab1384a1258c16170/libs/cua-s1/MODEL_CARD.md).

The training evaluator reports top-1, per-action accuracy, NLL and ten-bin ECE, with checkpoint selection on validation NLL. In-domain calibration cannot be assumed to transfer to unfamiliar inputs. Its bin predicate uses an exclusive upper edge, so literal probability 1.0 is not selected by the final bin; this is an implementation limitation of that evaluator, not proof the checkpoint's published ECE was affected. Our study should report raw incorrect-prediction probabilities directly and avoid recycling the upstream ECE as evidence of checkout calibration. [Pinned training evaluator](https://github.com/trycua/cua/blob/6d82b3b1b21813ad047f966ab1384a1258c16170/libs/cua-s1/training/train.py).

## Implications for next steps

Keeping this checkpoint as a narrow, verified form specialist is immediately feasible. Its model size makes local tests inexpensive, but familiar labels alone cannot guarantee correctness. A broader training programme would need independently held-out wording and form families, role-qualified candidates, real checkout value formats, positive optional-field examples, and explicit tests of out-of-domain skips. It should retain ambiguous and absent-entity cases rather than teach every field to fill.

A checkout-specific small model may improve these tasks with low inference cost, but needs separate training/development/held-out merchant distributions and can still overfit vocabulary. Evaluating CUA-S1-4B is a separate future experiment, not an assumed solution: the pinned upstream source describes a Qwen3.5-4B-backed closed-option LoRA scorer with a 26-option limit. The current 75 entities plus three actions cannot be sent through that contract unchanged; silently truncating or target-aware pruning would compromise this study's policy. Its roughly four-billion-parameter base also has substantially different local memory and latency costs from 706,048 parameters. No 4B weights or new model were used here. [Pinned upstream model card](https://github.com/trycua/cua/blob/6d82b3b1b21813ad047f966ab1384a1258c16170/libs/cua-s1/MODEL_CARD.md).
