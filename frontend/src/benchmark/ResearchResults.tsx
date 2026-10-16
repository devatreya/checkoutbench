import React, { useState } from "react";
import {
  date,
  csv,
  human,
  pct,
  seconds,
  money,
  familyName,
  download,
  scenarioPublicId,
  scenarioTitle,
} from "./domain";
import { modelName, systems } from "./policy";
import { Empty, Select, Tabs } from "./shared";
const ci = (v: any) =>
  v?.ci95
    ? `${pct(v.ci95[0])}–${pct(v.ci95[1])}`
    : "Insufficient independent data";
function Rate({ value }: { value: any }) {
  return (
    <span>
      {pct(value?.rate)}
      <small>
        {value?.numerator ?? 0} / {value?.denominator ?? 0} trials · clustered{" "}
        {pct(value?.clustered?.estimate)}
        <br />
        95% CI: {ci(value?.clustered)}
      </small>
    </span>
  );
}
export default function ResearchResults({
  view,
  onRun,
  onStart,
  data,
}: {
  view: string;
  onRun: (id: string) => void;
  onStart: () => void;
  data: any;
}) {
  const [model, setModel] = useState("all"),
    [sub, setSub] = useState("Payment Method Ranking"),
    [dimension, setDimension] = useState("Tracks"),
    [scenarioDimension, setScenarioDimension] = useState("Scenario"),
    [vendor, setVendor] = useState("all"),
    [method, setMethod] = useState("all"),
    [outcome, setOutcome] = useState("all"),
    [stage, setStage] = useState("all"),
    [search, setSearch] = useState("");
  const attempts = (data.runs || []).filter(
    (r: any) =>
      (model === "all" || r.model === model) &&
      (vendor === "all" || r.environment === vendor) &&
      (method === "all" || r.requested_payment_method === method) &&
      (outcome === "all" || r.status === outcome) &&
      (stage === "all" || r.failed_stage === stage) &&
      (!search ||
        [r.id, r.model, scenarioPublicId(r), scenarioTitle(r), r.failure_reason]
          .join(" ")
          .toLowerCase()
          .includes(search.toLowerCase())),
  );
  const rows = (key: string) =>
    (data[key] || []).filter((r: any) => model === "all" || r.model === model);
  const summary =
    model === "all"
      ? data.summary
      : data.models.find((r: any) => r.model === model) || {};
  const methods = [
    "Payment Method Ranking",
    "Checkout Funnel",
    "Failure Breakdown",
    "Vendor × Payment Method",
  ];
  const comparison =
    dimension === "Providers"
      ? rows("providers")
      : dimension === "Implementations"
        ? rows("implementations")
        : dimension === "Models"
          ? rows("models")
          : rows("models").flatMap((r: any) =>
              Object.entries(r.tracks).map(([track, s]: any) => ({
                ...s,
                model: r.model,
                label: {
                  A: "Core Checkout",
                  B: "Checkout Resilience",
                  C: "Complex / Legacy Portals",
                }[track as "A" | "B" | "C"],
              })),
            );
  const table = (rs: any[]) => (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Model / scope</th>
            <th>Tasks / implementations / trials</th>
            <th>Task resolution</th>
            <th>Checkout preparation</th>
            <th>Required field accuracy</th>
            <th>Successful median / inference</th>
            <th>Payment / recovery / grounding</th>
            <th>Cost / success</th>
          </tr>
        </thead>
        <tbody>
          {rs.map((r: any, i: number) => (
            <tr key={i}>
              <td>
                {modelName(r.model)}
                <small>
                  {r.label ||
                    (r.provider && familyName(r.provider)) ||
                    r.implementation ||
                    "Overall synthetic"}
                </small>
              </td>
              <td>
                {r.distinct_tasks} / {r.implementations} / {r.valid_trials}
              </td>
              <td>
                <Rate value={r.task_resolution} />
              </td>
              <td>
                <Rate value={r.checkout_preparation} />
              </td>
              <td>
                {pct(r.required_field_accuracy?.estimate)}
                <small>{ci(r.required_field_accuracy)}</small>
              </td>
              <td>
                {seconds(r.median_successful_seconds)} /{" "}
                {seconds(r.median_inference_seconds)}
              </td>
              <td>
                Method <Rate value={r.payment_method} />
                <small>
                  Details {pct(r.payment_detail?.rate)} · QR recovery{" "}
                  {pct(r.qr_recovery?.rate)} · model-wide grounding{" "}
                  {pct(
                    data.components?.find((c: any) => c.model === r.model)
                      ?.grounding_accuracy,
                  )}
                </small>
              </td>
              <td>{money(r.cost_per_success)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
  return (
    <div className="research-workspace">
      <div className="filters">
        <Select
          label="Research model"
          value={model}
          onChange={setModel}
          options={[
            "all",
            ...systems.map((s) => [s.id, s.short] as [string, string]),
          ]}
        />
        <button onClick={() => download("research-analysis.json", data)}>
          Analysis JSON
        </button>
        <a className="button" href="/api/research/export">
          Research bundle ↓
        </a>
      </div>
      <details className="metrics-explained">
        <summary>Metrics Explained</summary>
        <p>
          Task resolution includes correct safe aborts and authorisation
          handoffs; checkout preparation and simulated payment completion are
          separate outcomes. No real payment is made. Payment-method selection,
          payment-detail accuracy and OTP/3DS authentication are distinct. QR
          recovery includes only encountered recoverable problems; clean QR
          cases receive no recovery credit. Conditional stage success uses
          encountered applicable stages; end-to-end rates use assigned scored
          trials. Successful median time excludes failures. Confidence intervals
          resample independent implementation clusters, not repeated trials;
          insufficient independent coverage means no population interval or
          winner. Cost per successful preparation includes reported costs of all
          finished attempts and stays unknown when costs are missing.
        </p>
      </details>
      <p className="notice">
        Active release {data.release} · {data.genuine_trials} evaluations with
        inference · {data.total_attempts} verified experiment attempts.
        Synthetic checkout environments.
      </p>
      <section className="panel grow scroll">
        {!data.total_attempts && (
          <Empty title="No benchmark results yet">
            <p>
              CheckoutBench is ready to collect results from genuine AI model
              evaluations. Select your models and run the benchmark to start
              comparing checkout accuracy, payment handling, speed, and
              reliability.
            </p>
            <button className="primary" onClick={onStart}>
              Start Benchmark →
            </button>
            {data.empty_reason && <p className="muted">{data.empty_reason}</p>}
          </Empty>
        )}

        {!data.total_attempts &&
        view !== "Payment & Stage Analysis" ? null : view === "Summary" ? (
          <>
            <h2>Official evaluation summary</h2>
            {data.total_attempts > 0 && (
              <div className="coverage-tracks">
                <section>
                  <h3>Task resolution</h3>
                  <Rate value={summary.task_resolution} />
                  <p>
                    Checkout preparation{" "}
                    <Rate value={summary.checkout_preparation} />
                  </p>
                </section>
                <section>
                  <h3>Accuracy and successful time</h3>
                  <p>
                    Required fields{" "}
                    {pct(summary.required_field_accuracy?.estimate)}
                  </p>
                  <p>
                    Payment selection <Rate value={summary.payment_method} />
                  </p>
                  <p>
                    Successful median{" "}
                    {seconds(summary.median_successful_seconds)}
                  </p>
                </section>
                <section>
                  <h3>Distinct outcomes</h3>
                  <p>
                    Safe abort <Rate value={summary.safe_abort} />
                  </p>
                  <p>
                    Handoff <Rate value={summary.authorisation_handoff} />
                  </p>
                  <p>
                    Simulated completion{" "}
                    <Rate value={summary.simulated_completion} />
                  </p>
                </section>
              </div>
            )}
            <h3>Three research tracks</h3>
            <div className="coverage-tracks">
              {[
                ["A", "Core Checkout", "Correct checkout preparation"],
                [
                  "B",
                  "Checkout Resilience",
                  "Correct resolution under difficulty",
                ],
                ["C", "Complex / Legacy Portals", "Complete task resolution"],
              ].map(([key, name, description]) => (
                <section key={key}>
                  <h3>{name}</h3>
                  <p>{description}</p>
                  {rows("models").map((r: any) => (
                    <p key={r.model}>
                      {modelName(r.model)}{" "}
                      <Rate
                        value={
                          r.tracks[key][
                            key === "A"
                              ? "checkout_preparation"
                              : "task_resolution"
                          ]
                        }
                      />
                    </p>
                  ))}
                  {!rows("models").length && <b>Insufficient data</b>}
                </section>
              ))}
            </div>
            {table(rows("models"))}
            <p>
              Strengths and weaknesses remain unreported until verified model
              trials establish comparable coverage. A passing reference executor
              checks the benchmark software.
            </p>
          </>
        ) : view === "Model Comparison" ? (
          <>
            <Tabs
              label="Comparison dimension"
              items={["Tracks", "Providers", "Implementations", "Models"]}
              value={dimension}
              onChange={setDimension}
            />
            <p>
              CUA-S1 performs semantic matching through Playwright. TinyClick
              grounds clicks with deterministic semantic/controller assistance.
              The hybrid invokes both. MAI-UI and UI-Venus generate visual GUI
              actions. Inspect action attribution before crediting a decision to
              a model.
            </p>
            {table(comparison)}
            <h3>Paired comparisons</h3>
            {data.paired_comparisons.length ? (
              data.paired_comparisons.map((p: any) => (
                <p key={p.left + p.right}>
                  {modelName(p.left)} − {modelName(p.right)}: {p.matched_pairs}{" "}
                  matched pairs; {pct(p.difference.estimate)} difference, CI{" "}
                  {ci(p.difference)}.{" "}
                  {p.publication_comparable
                    ? "Coverage matched; uncertainty still applies."
                    : "Insufficient comparable coverage."}
                </p>
              ))
            ) : (
              <p>
                Insufficient comparable data for CUA versus TinyClick versus
                hybrid or other matched comparisons.
              </p>
            )}
          </>
        ) : view === "Scenario Analysis" ? (
          <>
            <h2>Task and environment weaknesses</h2>
            <p>
              Sorted by observed end-to-end task-resolution rate. Shared
              implementation variants are correlated, not independent
              replications.
            </p>
            <Tabs
              label="Scenario breakdown"
              items={["Scenario", "Provider", "Track", "Difficulty"]}
              value={scenarioDimension}
              onChange={setScenarioDimension}
            />
            {table(
              scenarioDimension === "Provider"
                ? rows("providers")
                : scenarioDimension === "Difficulty"
                  ? rows("difficulties").map((r: any) => ({
                      ...r,
                      label: r.difficulty,
                    }))
                  : scenarioDimension === "Track"
                    ? rows("models").flatMap((r: any) =>
                        Object.entries(r.tracks).map(([track, s]: any) => ({
                          ...s,
                          model: r.model,
                          label: track,
                        })),
                      )
                    : rows("scenarios").map((r: any) => ({
                        ...r,
                        label: `${scenarioPublicId(r)} · ${scenarioTitle(r)}`,
                      })),
            )}
            <h3>Failures by category</h3>
            {rows("failures").map((r: any) => (
              <p key={r.model + r.category}>
                {modelName(r.model)} · {human(r.category)}: {r.count}{" "}
                <button onClick={() => onRun(r.run_ids[0])}>
                  Inspect first run
                </button>
              </p>
            ))}
          </>
        ) : view === "Run Explorer" ? (
          <>
            <div className="toolbar">
              <input
                aria-label="Search run records"
                placeholder="Run ID, model, scenario or failure"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              <Select
                label="Vendor"
                value={vendor}
                onChange={setVendor}
                options={[
                  "all",
                  ...(Array.from(
                    new Set(data.runs.map((r: any) => r.environment)),
                  ) as string[]),
                ]}
              />
              <Select
                label="Payment method"
                value={method}
                onChange={setMethod}
                options={["all", ...data.payment_methods]}
              />
              <Select
                label="Run status"
                value={outcome}
                onChange={setOutcome}
                options={[
                  "all",
                  "completed",
                  "failed",
                  "blocked",
                  "unavailable",
                  "stopped",
                  "running",
                ]}
              />
              <Select
                label="Failed stage"
                value={stage}
                onChange={setStage}
                options={[
                  "all",
                  ...Array.from(
                    { length: 13 },
                    (_, i) => `S${String(i + 1).padStart(2, "0")}`,
                  ),
                ]}
              />
              <button
                onClick={() =>
                  download("official-runs.json", { runs: attempts })
                }
              >
                Export run JSON
              </button>
              <button
                onClick={() =>
                  download(
                    "official-runs.csv",
                    csv(
                      attempts.map((r: any) => ({
                        id: r.id,
                        model: r.model,
                        scenario: scenarioPublicId(r),
                        canonical_id: r.canonical_id || r.scenario,
                        display_name: scenarioTitle(r),
                        status: r.status,
                        task_resolved_correctly: r.task_resolved_correctly,
                        checkout_prepared: r.checkout_prepared,
                        failed_stage: r.failed_stage,
                        wall_seconds: r.wall_seconds,
                      })),
                    ),
                    true,
                  )
                }
              >
                Export filtered summaries CSV
              </button>
            </div>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Run / started</th>
                    <th>Model / scenario</th>
                    <th>Environment / method</th>
                    <th>Outcome / failed stage</th>
                    <th>Duration / cost</th>
                    <th>Evidence</th>
                  </tr>
                </thead>
                <tbody>
                  {attempts.map((r: any) => (
                    <tr key={r.id}>
                      <td className="mono">
                        {r.id}
                        <small>{date(r.timestamp)}</small>
                      </td>
                      <td>
                        {modelName(r.model)}
                        <small>{scenarioPublicId(r)}</small>
                        <small>{scenarioTitle(r)}</small>
                      </td>
                      <td>
                        {familyName(r.environment)}
                        <small>{human(r.requested_payment_method)}</small>
                      </td>
                      <td>
                        {human(r.status)}
                        <small>
                          {r.task_resolved_correctly === true
                            ? "Task resolved"
                            : r.failure_reason || "No resolution recorded"}
                        </small>
                        <small>{r.failed_stage}</small>
                      </td>
                      <td>
                        {seconds(r.wall_seconds)}
                        <small>
                          {money(
                            r.cost_kind === "not_reported" ? null : r.cost,
                          )}
                        </small>
                      </td>
                      <td>
                        <button
                          aria-label={`Open run ${r.id}`}
                          onClick={() => onRun(r.id)}
                        >
                          Open run →
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!!data.total_attempts && !attempts.length && (
              <Empty title="No matching evaluation attempts" />
            )}
          </>
        ) : (
          <>
            <Tabs
              label="Payment analysis views"
              items={methods}
              value={sub}
              onChange={setSub}
            />
            {sub === "Payment Method Ranking" ? (
              <>
                <h2>Payment preparation by model</h2>
                <p>
                  Assigned-trial preparation rates answer end-to-end
                  reliability; the funnel below conditions on stages
                  encountered. Best/worst labels require comparable coverage and
                  separated uncertainty.
                </p>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Model / method</th>
                        <th>Eligible tasks / exposed / attempts</th>
                        <th>Preparations / failed resolutions</th>
                        <th>Preparation rate / CI</th>
                        <th>Handoffs / simulated completions</th>
                        <th>Successful median</th>
                        <th>Evidence</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows("payments").map((r: any) => (
                        <tr key={r.model + r.method}>
                          <td>
                            {modelName(r.model)}
                            <small>{human(r.method)}</small>
                          </td>
                          <td>
                            {r.eligible_tasks} / {r.exposed_opportunities} /{" "}
                            {r.attempted_trials}
                          </td>
                          <td>
                            {r.checkout_preparation.numerator} /{" "}
                            {r.valid_trials - r.task_resolution.numerator}
                          </td>
                          <td>
                            <Rate value={r.checkout_preparation} />
                          </td>
                          <td>
                            {r.authorisation_handoff.numerator} /{" "}
                            {r.simulated_completion.numerator}
                          </td>
                          <td>{seconds(r.median_successful_seconds)}</td>
                          <td>
                            {r.method_ranking}
                            <small>
                              {r.common_failure || "No observed failure"}
                            </small>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <h3>Authentication attached to funding method</h3>
                <p>OTP/3DS are challenge dimensions, not payment methods.</p>
                {rows("authentication").map((r: any) => (
                  <p key={r.model + r.challenge + r.method}>
                    {modelName(r.model)} · {human(r.method)} ·{" "}
                    {human(r.challenge)}: {r.exposed} exposed / {r.valid_trials}{" "}
                    eligible trials · handoff <Rate value={r.authentication} />
                  </p>
                ))}
              </>
            ) : sub === "Checkout Funnel" ? (
              <>
                <h2>Branching checkout stages</h2>
                <p>
                  {data.branching_note} S01 measures observable interaction, not
                  internal understanding.
                </p>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Model / stage</th>
                        <th>Entered / applicable</th>
                        <th>Completed / conditional rate</th>
                        <th>Failed / handoff / safe abort</th>
                        <th>Not reached / N/A</th>
                        <th>Completed stage median</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows("stages").map((r: any) => (
                        <tr key={r.model + r.stage_id}>
                          <td>
                            {modelName(r.model)}
                            <small>
                              {r.stage_id} · {r.name}
                            </small>
                          </td>
                          <td>
                            {r.entered} / {r.applicable}
                          </td>
                          <td>
                            {r.completed} · {pct(r.conditional_success)}
                            <div className="bar-track">
                              <div
                                style={{
                                  width: `${100 * (r.conditional_success || 0)}%`,
                                }}
                              />
                            </div>
                            <small>95% CI: {ci(r.conditional_clustered)}</small>
                          </td>
                          <td>
                            {r.failed} / {r.handoff} / {r.safe_abort}
                          </td>
                          <td>
                            {r.not_reached} / {r.not_applicable}
                          </td>
                          <td>{seconds(r.median_stage_seconds)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : sub === "Failure Breakdown" ? (
              <>
                <h2>Reviewable failures</h2>
                <p>
                  Labels describe observed evidence. Semantic or grounding
                  errors are not inferred from outcome alone.
                </p>
                {rows("failures").map((r: any) => (
                  <details key={r.model + r.category}>
                    <summary>
                      {modelName(r.model)} · {human(r.group)} ·{" "}
                      {human(r.category)}: {r.count}
                    </summary>
                    <div className="toolbar">
                      {r.run_ids.map((id: string) => (
                        <button key={id} onClick={() => onRun(id)}>
                          {id}
                        </button>
                      ))}
                    </div>
                  </details>
                ))}
              </>
            ) : (
              <>
                <h2>Vendor × payment method</h2>
                <p>
                  Provider-inspired simulations; N/A means no eligible task in
                  this release, not a model failure.
                </p>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Model / environment</th>
                        {data.payment_methods?.map((m: string) => (
                          <th key={m}>{human(m)}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {rows("providers").map((r: any) => (
                        <tr key={r.model + r.provider}>
                          <td>
                            {modelName(r.model)}
                            <small>{familyName(r.provider)}</small>
                          </td>
                          {data.payment_methods?.map((m: string) => {
                            const cell = data.vendor_payment.find(
                              (c: any) =>
                                c.model === r.model &&
                                c.provider === r.provider &&
                                c.method === m,
                            );
                            return (
                              <td key={m}>
                                {cell?.supported ? (
                                  <Rate value={cell.checkout_preparation} />
                                ) : (
                                  "N/A"
                                )}
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </>
        )}
      </section>
    </div>
  );
}
