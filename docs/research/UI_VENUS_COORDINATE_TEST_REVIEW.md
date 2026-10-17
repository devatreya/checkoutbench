# Independent UI-Venus coordinate/executor review

**Historical pre-fix v2 review.** The findings and49-test result below describe the initial audit snapshot. V3 resolutions are recorded at the end.

Reviewed 2026-10-17 on `codex/scenario-identity-ui-venus`. This review audits the
repository's declared native normalized `[0,1000]` contract, implementation, and
physical browser execution. It does not establish that the model actually emits
that contract; genuine model evidence belongs to the separate diagnostic suite.

## Reproducible validation

```sh
.venv/bin/python -m pytest tests/test_venus_coordinate_audit.py -q
```

Result: **49 passed in 9.93 seconds**. No model was loaded or inferred. Tests own
only test code; fixture pages, scorer, runtime, and existing tests were unchanged.

The tests independently use exact `Fraction` arithmetic to check flooring and
endpoint clamping, rather than borrowing the parser's float conversion. They cover
all five native spatial actions, list/tuple syntax, both drag endpoints, fractional
rounding, origin, inclusive 1000, just-outside bounds, booleans, nonfinite numbers,
wrong arity, original/resized dimension independence, desktop/wide/tall/mobile,
and a one-pixel image.

Real Chromium execution traverses `VenusAdapter.act` preprocessing and parsing,
`run_visual` validation, and the shared mouse/keyboard executor. An explicit
scripted transport supplies native text; resulting usage is labeled
`scripted_native_executor_test` and `actual_model: false`. Five viewport shapes
(1280x900, 1920x480, 480x1920, 390x844, 101x99) assert recorded physical mouse
`clientX/clientY`, target identity, focused-input text insertion, bottom-right
edge targeting, actual screenshot sizes, and decoded worker payload image sizes.
All use DPR 1, matching the persistent Chromium context in the production runner.

A separate test uses the existing, unmodified T01 checkout and physically clicks
and types into its public email input. A DOM bounding box supplies the scripted
point **in test setup only**. That proves executor delivery and field focus; it is
not model grounding, autonomous checkout, or benchmark-success evidence.

The popup test opens a real Chromium 730x510 popup while the parent is 1280x900.
The popup screenshot was actually 730x510; the adapter maps coordinates from that
screenshot, targets the popup, and types successfully. Tests do not supply DOM
information to the adapter or replace the shared progress monitor.

## Findings

1. **Native arithmetic and pointer delivery are correct for tested normalized
   coordinates and production-style DPR 1 contexts.** A prior resized-pixel
   interpretation would fail these tests. Native completion still does not set
   verifier success.
2. **Popup protocol metadata can be stale.** `run_visual` records
   `visual_protocol.viewport` from `ctl.run['viewport']` once. A popup can have a
   different viewport (730x510 in the live test). Per-call `image_size` and actual
   coordinate execution remain correct, but that protocol viewport still reports
   the parent's 1280x900. Consumers must use per-observation image dimensions for
   popup coordinate reconstruction. Updating metadata is outside this test-only
   review's ownership.
3. **The resize helper can exceed an accepted configured pixel cap for extreme
   aspect ratios.** Exact reproduction:

   ```python
   image_size_for_model((20000, 100), 65536) == (3616, 32)
   # 115712 pixels > 65536; transposed input has the same defect.
   ```

   Both ratio 200 and cap 65536 pass the helper's input checks. Independent
   clamping of the short side to 32 after scaling causes the cap violation.
   The tested normal desktop/mobile configurations do not trigger this case.
   The helper should either honor the cap after grid adjustment or reject this
   dimension/cap combination explicitly. No runtime code was changed here.

## V3 resolution and final review

The lead fixed stale popup metadata by retaining initial dimensions and recording each active observation size; added CSS-scale screenshot capture after a real DPR2 regression demonstrated misdirected actions; and rejected resize outputs that cannot satisfy the configured area bounds on the32-pixel grid. Native normalized arithmetic, model prompts/decoding, weights, fixtures and scoring remain unchanged. Four pre-fix regressions failed and pass after the fixes. The focused adapter/visual/coordinate run passed181 tests before the final evaluator additions. The final three coordinate modules collect114 tests (including10 evaluator browser tests); their complete final result is recorded in the [integrated audit](UI_VENUS_COORDINATE_AUDIT.md). These remain software tests, not model-accuracy results.

Independent final review approved the runtime geometry changes and verified closure of three diagnostic findings: trusted physical target/label delivery, active evaluator source snapshots, and frozen input-image hash checks. All18 case transformations, aggregate counts, published PNG hashes and checkout summary were independently recomputed against retained raw evidence without discrepancy.
