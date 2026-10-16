# Scenario names and historical compatibility

The dashboard presents versionless scenario IDs and descriptive simulated-task names. Canonical IDs remain the source of truth for fixtures, stored results, manifests, hashes, and joins. Names are an API presentation overlay; they do not modify checkout labels or tasks.

`scenarios/identities.json` is the explicit compatibility registry for all 322 registered scenarios: 174 current tasks and 148 historical tasks. `scenarios/identity.py` validates the entire registry before use and resolves either identifier to its canonical ID. New scenarios require explicit entries; existing public IDs must not be renumbered or reassigned.

| Canonical ID | Public ID |
| --- | --- |
| `V3-G01` | `GENERIC-01` |
| `V21-G01` | `GENERIC-01-CLASSIC` |
| `V3-S01` | `SHOPIFY-01` |
| `V21-S01` | `SHOPIFY-01-CLASSIC` |
| `S01` | `SHOPIFY-01-FOUNDATION` |
| `V3-ST03` | `STRIPE-03` |
| `V3-QR-razor-2` | `RAZORPAY-QR-02` |
| `V3-AUTH-modal-otp_expired-handoff` | `AUTH-MODAL-EXPIRED-HANDOFF` |

`CLASSIC` and `FOUNDATION` identify separate historical snapshots. They prevent old and current tasks with similar source IDs from resolving to one another. The initial task collection uses `LEGACY-TASK` and `LEGACY-HOLDOUT`; historical holdouts remain historical regression evidence. The inherited QR and authentication cases use `QR-REGRESSION` and `AUTH-REGRESSION` to distinguish them from the separately defined factorial cases. None of these names imply that historical tasks are identical to current tasks.

Each identity supplies `canonical_id`, `public_id`, `display_name`, and `description`. Existing `id`, `scenario`, and `title` fields retain their established meaning. API enrichment returns detached copies, never edits database rows, and never feeds presentation text into inference. Technical exports and expandable metadata retain canonical IDs so historical runs remain traceable.

Provider names are qualified as inspired simulations. Stripe, Razorpay, Cashfree, Shopify, Stripe Link, IRCTC, Passport Seva and eChallan labels do not imply a production integration or a real financial transaction.

The frontend consumes registry fields from the API; it does not strip prefixes or duplicate the mapping. Unknown missing presentation metadata is shown as an unmapped scenario rather than guessing a potentially colliding ID. Tests verify complete coverage, collision rejection, both identifier namespaces, historical-record immutability, and equality of the canonical scenario manifest before and after presentation enrichment.

```sh
.venv/bin/pytest -q tests/test_scenario_identity.py tests/test_dashboard.py
npm --prefix frontend run build
```
