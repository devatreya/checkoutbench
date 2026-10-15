# Specialist model cards

The normal UI retains CUA-S1-Forms + Playwright (706,048), TinyClick + deterministic controller (270M advertised), hybrid (~270.7M combined), MAI-UI-2B and UI-Venus-1.5-2B. No substitutes are accepted. Frontier/OpenRouter/direct-provider adapters remain available through developer APIs.

`research/model-provenance.json` records exact repositories, immutable revisions, weight hashes, metadata and declared licenses. `research/checkpoint-smoke-evidence.json` records this machine's verification outcome, not transferable certification of another machine. Local execution records are in ignored data/research/checkpoint-verification.json; run-time validation rehashes configured weights/config and adapter before research execution. Remote endpoint identity is not verifiable from its own text response and is blocked for research until independent deployment attestation exists.

| Configuration | Source and license | Status / limitations |
|---|---|---|
| CUA-S1 | [official forms checkpoint](https://huggingface.co/cua-ai/cua-s1-forms), MIT | Pinned safe tensor pair loaded; real cold and warm field-scoring smoke, 706,048 parameters. Produces probabilities over supplied entities/actions, not text or coordinates. Smoke validates output contract, not field accuracy or end-to-end ability. |
| TinyClick | [identified original repository](https://huggingface.co/kzawistowsk/TinyClick), declared MIT | No original weight files in pinned snapshot. BLOCKED. No Florence/base-model substitution. |
| Hybrid | CUA + exact TinyClick | BLOCKED until both components verify and both execute genuine smoke. No hybrid performance claim. |
| MAI-UI | [official 2B checkpoint](https://huggingface.co/Tongyi-MAI/MAI-UI-2B), Apache-2.0 | Metadata/hashes identified; local weights/runtime smoke not configured. Browser adaptation of mobile actions is a limitation. |
| UI-Venus | [official 1.5 2B checkpoint](https://huggingface.co/inclusionAI/UI-Venus-1.5-2B), Apache-2.0 | Metadata/hashes identified; local weights/runtime smoke not configured. Native coordinate/action grammar must be preserved. |

CUA loader source is pinned to trycua/cua revision 6d82b3b1b21813ad047f966ab1384a1258c16170. Its safe checkpoint loader validates the tensor/config signature. No pickle weights are loaded. The source checkpoint is a research-family artifact; do not relabel it as another mapped release. See upstream model cards for training data and upstream claims; those claims are not CheckoutBench results.

Controlled system comparisons: CUA vs reference semantics; TinyClick vs DOM targeting; hybrid vs each component configuration; MAI vs UI-Venus. Historical reference scores may aid software diagnostics but do not enter public AI leaderboards. Component `field_classification_accuracy` / `grounding_accuracy` use recorded decisions and explicit coverage. Lifecycle navigation remains controller-assisted in the first three configurations.
