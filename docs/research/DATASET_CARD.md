# Dataset card — 3.0-pilot.1

174 active synthetic tasks: 74 migrated regression tasks, 18 controlled QR cases, 32 authentication combinations, 10 paired layout cases and 40 tasks across ten new merchant clients. Nine environment labels; three tracks. Profile data is fictional and test payment data is non-production.

11 client implementation families: original shared v2.1 renderer plus ledger table, parcel wizard, native payment dialog, subscription tabs, grocery accordion, open-shadow custom elements, furniture drawer, inline book checkout, donation form fragments and two-column travel checkout. These vary DOM, client progression and interaction, but reuse transport/widgets/server logic. They are **not 11 proven independent websites** and are one conservative statistical cluster. The target of at least 15 independent implementations / 60–100 independently prepared tasks is not yet met.

Development contains the shared renderer and six new clients. Validation contains furniture-drawer, books-inline, donation-stack and travel-columns. IDs and client families are disjoint across those two splits; shared lower-level infrastructure remains disclosed. Validation is for development selection, not an unseen final-test claim. Migrated historical holdout labels are regression cases only.

No independently authored and reviewed final holdout has been supplied. The sealing tool accepts a custodian bundle only after independent author/reviewer attestations and no client-family overlap. It publishes SHA-256 commitments, keeps contents in ignored private storage and reserves final evaluation once. It does not magically make agent-authored cases unseen. Ordinary preview/API manifests cannot register sealed IDs. Final execution remains a custodian-controlled external operation; no final corpus has been consumed.

Each active definition records ID, family, release, seed, profile, hash, creation date, automated author, source class, split and pending review. `research/release.json` contains metadata; export includes exact synthetic scenario definitions. Expected answers are private to model execution, not secret from human researchers or the published development release. Origin/path allowlists isolate scored model sessions from control/evaluation APIs.

Provider-inspired or government-inspired interfaces are not live provider pages. Government portals are never transacted with. UI variants and QR seeds do not count as independent sites. Labels/addresses are predominantly English and do not cover the full geographic or accessibility diversity of real checkout.
