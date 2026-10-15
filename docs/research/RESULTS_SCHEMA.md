# Results schema 3.0

`research/stage-event.schema.json` is the machine-readable strict Pydantic-generated event schema. Each event records run/model/scenario/environment, stage, method, status transition, timestamp/elapsed, action/source, optional prediction, nullable validation, error/recovery and screenshot/action references. No real customer credentials or OTPs are valid inputs.

Additive result fields: scoring_version, task_resolved_correctly, checkout_prepared, authorisation_handoff_correct, simulated_payment_completed, safe_abort_correct, payment_method_correct, required_fields_correct, primary_failure_category, secondary_failure_categories, failed_stage, checkout_stages, stage_events and qr_research. Historical raw records are unchanged and have no invented v3 fields.

Timing: successful_preparation_seconds, successful_resolution_seconds, failed_run_seconds, inference_seconds, cold_model_loading_seconds, warm_inference_seconds and latency_breakdown. Null is unavailable/unobserved, not zero.

Provenance: research_release, release_hash, scenario_hash, research_protocol_hash, implementation_family, independence_cluster, research_track, research_split, execution_manifest. The latter records exact checkpoint verification, source/adapter hashes, OS/Python/browser, settings, warmup, precision/quantisation evidence and cost scope.

Analyses include numerator/denominator/rate, descriptive_trial_wilson95, clustered estimate/ci95/cluster count, valid_trials, total_attempts, distinct_tasks, implementations, exclusions and successful/failure medians. Finite values only. Method rankings fail closed to Insufficient data when coverage or independence is inadequate.
