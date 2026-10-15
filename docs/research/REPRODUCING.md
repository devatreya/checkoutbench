# Reproduction

Use the repository commit recorded with validation evidence, Python 3.12 and the committed uv.lock / frontend package-lock.json. Install core/test/browser dependencies as in README. `uv sync` without specialist extras can remove separately installed ML packages.

```sh
uv sync --python 3.12 --extra test --extra agent --extra specialists
.venv/bin/playwright install chromium
npm --prefix frontend ci
npm --prefix frontend run build
.venv/bin/pytest -q
.venv/bin/python -m scripts.research.manage readiness
./scripts/start.sh
```

For CUA, install `cua_s1` from the pinned upstream source in MODEL_CARDS.md (package path libs/cua-s1/python). Download only cua-s1-forms.safetensors and cua-s1-forms.json from the exact model-provenance revision. Set the local ignored CUA_S1_MODEL_PATH and verify before any research run. Other models require exact files listed in provenance; TinyClick is blocked until an authorised original distribution is identified. Do not download a substitute and preserve its advertised name.

```sh
.venv/bin/python -m scripts.research.verify_models --model cua-s1
.venv/bin/python -m scripts.research.manage review-packet
.venv/bin/python -m scripts.research.manage export --output data/research/export.zip
```

Software-only checks use deterministic reference execution, never AI success:

```sh
.venv/bin/python scripts/check.py --suite 3.0 --repeats 1
```

Development APIs may debug individual unsealed cases. The ordinary UI uses the full manifest. API limits, model inputs, browser allowlists and evaluator truth separation remain enforced. Existing result data is never rewritten. A clean isolated run can set BENCH_DATA_DIR to a fresh directory before startup; this hides previous runs from that instance without deleting them. Keep the old directory as an archive.

Exports include definitions, source files, dependency locks, schema, provenance, long-form CSV/JSON analysis and SVG charts. Missing model data generates explicitly marked templates. Local UI screenshot checks and deterministic regression are not independent reproduction. Reproduction by another team is still pending.

The deterministic reference policy can fail unfamiliar-label tasks; that measures its own coverage, not fixture solvability. The full pytest suite additionally uses a private test oracle to validate all ten controlled layout cases. Those oracle checks never count as AI evaluations.
