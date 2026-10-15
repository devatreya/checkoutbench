import React, { useState } from "react";
import {
  artifact,
  date,
  download,
  human,
  money,
  num,
  pct,
  seconds,
  shown,
  status,
  type Run,
  type Scenario,
} from "./domain";
import { modelName } from "./policy";
import { Badge, Empty, Tabs } from "./shared";
function Facts({ rows }: { rows: [string, unknown][] }) {
  return (
    <dl className="facts">
      {rows.map(([k, v]) => (
        <div key={k}>
          <dt>{k}</dt>
          <dd>{shown(v)}</dd>
        </div>
      ))}
    </dl>
  );
}
export default function RunDetails({
  run,
  scenario,
}: {
  run: Run;
  scenario?: Scenario;
}) {
  const [tab, setTab] = useState("Outcome"),
    [step, setStep] = useState(0);
  const events = run.events || [],
    event = events[step],
    shot = artifact(event?.screenshot || run.screenshot);
  const images = (
    <div className="replay-image">
      {shot ? (
        <img
          src={shot}
          alt={`Browser evidence: action ${step + 1} ${event?.action || "final state"}`}
        />
      ) : (
        <Empty title="Screenshot not reported">
          This record has no local image for the selected action.
        </Empty>
      )}
    </div>
  );
  const control = (
    <div className="pager">
      <button
        disabled={!events.length || step === 0}
        onClick={() => setStep(step - 1)}
      >
        Previous action
      </button>
      <span>
        {events.length
          ? `${step + 1} / ${events.length}`
          : "No recorded actions"}
      </span>
      <button
        disabled={!events.length || step >= events.length - 1}
        onClick={() => setStep(step + 1)}
      >
        Next action
      </button>
    </div>
  );
  return (
    <>
      <div className="toolbar">
        <div>
          <Badge tone={run.success ? "good" : "warn"}>{status(run)}</Badge>
          <small className="run-id">{run.id}</small>
        </div>
        <button onClick={() => download(`run-${run.id}.json`, run)}>
          Individual run JSON
        </button>
        <button
          onClick={() =>
            download(`trace-${run.id}.json`, {
              run_id: run.id,
              events: run.events ?? null,
              workflow_events: run.workflow_events ?? null,
            })
          }
        >
          Action trace JSON
        </button>
      </div>
      <Tabs
        label="Run detail views"
        items={[
          "Outcome",
          "Action timeline",
          "Visual replay",
          "Fields",
          "Payment & authentication",
          "Stages & failure",
          "Performance",
        ]}
        value={tab}
        onChange={setTab}
      />
      <div className="panel grow scroll">
        {tab === "Outcome" && (
          <>
            <h2>Outcome summary</h2>
            <Facts
              rows={[
                ["Model", modelName(run.model)],
                [
                  "Scenario",
                  `${run.scenario} · ${run.scenario_title || scenario?.title || "Not reported"}`,
                ],
                ["Result", status(run)],
                ["Final checkout stage", run.completion_stage],
                [
                  "Scenario objective",
                  run.expected_outcome ?? scenario?.expected_outcome,
                ],
                ["Duration", seconds(run.wall_seconds)],
                ["Started", date(run.timestamp)],
                [
                  "Failure reason",
                  run.failure_reason ?? (run.success ? "None" : "Not reported"),
                ],
                ["Version", run.benchmark_version],
                ["Conditions cohort", run.cohort],
                ["Evaluation mode", run.evaluation_mode],
                ["Device", run.platform],
                ["Agent mode", run.agent_mode],
              ]}
            />
            <p className="notice">
              A successful handoff or checkout-ready result is not a completed
              financial transaction. Any payment confirmation in this benchmark
              is simulated.
            </p>
            <details>
              <summary>Recorded configuration</summary>
              <pre>{JSON.stringify(run.config ?? "Not reported", null, 2)}</pre>
            </details>
          </>
        )}
        {tab === "Stages & failure" && (
          <section>
            <h2>Stage evidence</h2>
            <Facts
              rows={[
                ["Task resolved correctly", run.task_resolved_correctly],
                ["Checkout prepared", run.checkout_prepared],
                [
                  "Correct authorisation handoff",
                  run.authorisation_handoff_correct,
                ],
                [
                  "Simulated payment completed",
                  run.simulated_payment_completed,
                ],
                ["Correct safe abort", run.safe_abort_correct],
                ["Primary failure", run.primary_failure_category],
                ["Secondary failures", run.secondary_failure_categories],
                ["Failed stage", run.failed_stage],
                ["Cold loading", run.cold_model_loading_seconds],
                ["Warm inference", run.warm_inference_seconds],
              ]}
            />
            <p>
              Stages branch; not applicable and not reached are distinct. Events
              report observed browser/server transitions, not unobserved model
              cognition.
            </p>
            {run.stage_events?.length ? (
              <table>
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Stage</th>
                    <th>Status</th>
                    <th>Action / source</th>
                    <th>Error / recovery</th>
                  </tr>
                </thead>
                <tbody>
                  {run.stage_events.map((e: any, i: number) => (
                    <tr key={i}>
                      <td>{seconds(e.elapsed)}</td>
                      <td>{e.stage_id}</td>
                      <td>{human(e.status)}</td>
                      <td>
                        {human(e.action_attempted)} · {e.action_source}
                      </td>
                      <td>
                        {human(e.error_type)} / {human(e.recovery_outcome)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <Empty title="Stage events not reported" />
            )}
            <details>
              <summary>Reproducibility and complete event payloads</summary>
              <pre>
                {JSON.stringify(
                  {
                    manifest: run.execution_manifest,
                    events: run.stage_events,
                  },
                  null,
                  2,
                )}
              </pre>
            </details>
          </section>
        )}
        {tab === "Action timeline" && (
          <div className="evidence-grid">
            <div className="scroll">
              <h2>Chronological actions</h2>
              {events.length ? (
                events.map((e, i) => (
                  <button
                    key={i}
                    className={"timeline-item " + (step === i ? "chosen" : "")}
                    onClick={() => setStep(i)}
                  >
                    <b>
                      {i + 1}. {human(e.action)}
                    </b>
                    <small>
                      {seconds(e.elapsed)} ·{" "}
                      {human(
                        e.detail?.selection_source ||
                          e.detail?.grounding_source ||
                          "Not reported",
                      )}
                    </small>
                    <small>Result: {shown(e.detail?.result ?? e.result)}</small>
                  </button>
                ))
              ) : (
                <Empty title="Action timeline not reported" />
              )}
            </div>
            <div className="replay-column">
              {images}
              <pre className="action-detail">
                {event
                  ? JSON.stringify(event.detail || {}, null, 2)
                  : "Action details not reported"}
              </pre>
            </div>
          </div>
        )}
        {tab === "Visual replay" && (
          <div className="replay-column">
            <h2>Visual replay</h2>
            {images}
            {control}
            <p>
              {event
                ? `${human(event.action)} · ${seconds(event.elapsed)} · ${human(event.detail?.selection_source || event.detail?.grounding_source || "Source not reported")}`
                : "No actions recorded"}
            </p>
            {run.videos?.filter((v: string) => artifact(v)).length ? (
              <details>
                <summary>Recorded browser video</summary>
                {run.videos.map(
                  (v: string) =>
                    artifact(v) && (
                      <video
                        key={v}
                        controls
                        src={artifact(v)}
                        preload="metadata"
                      />
                    ),
                )}
              </details>
            ) : (
              <small>Browser video: Not reported</small>
            )}
          </div>
        )}
        {tab === "Fields" && (
          <>
            <h2>Field-level analysis</h2>
            <p>
              Required-field scoring may report only correct/incorrect. Missing
              values are distinguished only when explicitly recorded; they are
              not guessed from a failed score.
            </p>
            <table>
              <thead>
                <tr>
                  <th>Field</th>
                  <th>Requirement</th>
                  <th>Recorded result</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(run.field_results || {}).map(([k, v]) => (
                  <tr key={k}>
                    <td>{human(k)}</td>
                    <td>Required</td>
                    <td>
                      {v === true
                        ? "Correct"
                        : v === false
                          ? run.missing_fields?.includes(k)
                            ? "Missing"
                            : "Incorrect or missing — not distinguished"
                          : shown(v)}
                    </td>
                  </tr>
                ))}
                {Object.entries(run.optional_results || {}).map(([k, v]) => (
                  <tr key={k}>
                    <td>{human(k)}</td>
                    <td>Optional</td>
                    <td>
                      {v === true
                        ? "Correct or acceptably blank"
                        : v === false
                          ? "Incorrect optional value"
                          : shown(v)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!Object.keys(run.field_results || {}).length && (
              <p>Field results: Not reported</p>
            )}
            <Facts
              rows={[
                ["Required-field accuracy", pct(run.required_field_accuracy)],
                ["Optional fields correct", run.optional_correct],
                [
                  "Incorrect saved values recorded",
                  run.incorrect_autofill_values,
                ],
                [
                  "Incorrect saved values detected",
                  run.incorrect_autofill_detection,
                ],
                [
                  "Semantic classification accuracy",
                  pct(run.field_classification_accuracy),
                ],
                ["Grounding accuracy", pct(run.grounding_accuracy)],
              ]}
            />
          </>
        )}
        {tab === "Payment & authentication" && (
          <>
            <h2>Payment & authentication</h2>
            <Facts
              rows={[
                [
                  "Requested method (record, otherwise scenario configuration)",
                  run.requested_payment_method ??
                    (run.agent_mode === "agent_without_link"
                      ? "card"
                      : scenario?.method),
                ],
                [
                  "Actual selected method",
                  run.actual_payment_method ?? run.selected_payment_method,
                ],
                [
                  "Payment-method selection accuracy",
                  pct(
                    run.payment_method_accuracy ??
                      run.payment_selection_accuracy,
                  ),
                ],
                [
                  "Recorded payment validation accuracy",
                  pct(run.payment_accuracy),
                ],
                ["Payment prepared", run.stage_completion?.payment_prepared],
                ["Authentication handoffs", run.authentication_handoffs],
                ["Handoff accuracy", pct(run.authorisation_handoff_accuracy)],
                [
                  "Authentication simulated",
                  run.stage_completion?.authentication_simulated,
                ],
                ["QR recovery accuracy", pct(run.qr_recovery_accuracy)],
                ["Transaction count", run.transaction_count],
                ["Final simulated outcome", run.completion_stage],
                ["Duplicate attempts avoided", run.duplicate_payment_avoidance],
              ]}
            />
            <p className="notice">
              Recorded payment validation may include credentials or QR validity
              in addition to method selection. The narrower method-only metric
              is shown only when separately recorded.
            </p>
            <h3>QR evidence</h3>
            <pre>
              {JSON.stringify(run.qr_metrics ?? "Not reported", null, 2)}
            </pre>
            <details>
              <summary>Recorded workflow events</summary>
              <pre>
                {JSON.stringify(run.workflow_events ?? "Not reported", null, 2)}
              </pre>
            </details>
          </>
        )}
        {tab === "Performance" && (
          <>
            <h2>Performance breakdown</h2>
            <Facts
              rows={[
                ["Model inference", seconds(run.inference_seconds)],
                [
                  "Browser execution",
                  seconds(run.latency_breakdown?.browser_execution_seconds),
                ],
                [
                  "Model screenshot capture",
                  seconds(run.latency_breakdown?.model_screenshot_seconds),
                ],
                [
                  "Artifact capture",
                  seconds(run.latency_breakdown?.artifact_capture_seconds),
                ],
                [
                  "Artifact storage",
                  seconds(run.latency_breakdown?.artifact_storage_seconds),
                ],
                [
                  "Controller computation",
                  seconds(run.latency_breakdown?.controller_compute_seconds),
                ],
                [
                  "Browser setup",
                  seconds(run.latency_breakdown?.browser_setup_seconds),
                ],
                [
                  "Other observation / wait / teardown",
                  seconds(
                    run.latency_breakdown
                      ?.other_wait_observation_teardown_seconds,
                  ),
                ],
                ["Total wall-clock time", seconds(run.wall_seconds)],
                ["Model calls", run.model_call_count],
                ["Browser actions", run.action_count],
                ["Validation errors", run.validation_errors],
                ["Retries", run.retries],
                [
                  "Inference cost",
                  money(run.cost_kind === "not_reported" ? null : run.cost),
                ],
                ["Cost measurement", run.cost_kind],
              ]}
            />
            <p>
              {run.latency_measurement ||
                "Detailed measurement boundaries: Not reported"}
            </p>
            <details>
              <summary>Recorded model calls and action attribution</summary>
              <pre>
                {JSON.stringify(
                  {
                    calls: run.calls ?? "Not reported",
                    attribution: run.action_attribution ?? "Not reported",
                  },
                  null,
                  2,
                )}
              </pre>
            </details>
          </>
        )}
      </div>
    </>
  );
}
