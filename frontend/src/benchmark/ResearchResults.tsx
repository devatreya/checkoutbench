import React, { useEffect, useState } from "react";
import {
  api,
  human,
  pct,
  seconds,
  money,
  familyName,
  download,
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
}: {
  view: string;
  onRun: (id: string) => void;
}) {
  const [data, setData] = useState<any>(null),
    [ready, setReady] = useState<any>(null),
    [protocol, setProtocol] = useState(""),
    [model, setModel] = useState("all"),
    [sub, setSub] = useState("Payment Method Ranking"),
    [dimension, setDimension] = useState("Tracks"),
    [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    Promise.all([
      api(
        "/research/analysis" +
          (protocol ? "?protocol=" + encodeURIComponent(protocol) : ""),
      ),
      api("/research/readiness"),
    ])
      .then(([a, b]) => {
        if (live) {
          setData(a);
          setReady(b);
        }
      })
      .catch((e) => setError(e.message));
    return () => {
      live = false;
    };
  }, [protocol]);
  if (error)
    return <Empty title="Research analysis unavailable">{error}</Empty>;
  if (!data) return <Empty title="Loading research measurements…" />;
  const rows = (key: string) =>
    (data[key] || []).filter((r: any) => model === "all" || r.model === model);
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
          label="Research protocol"
          value={protocol || data.selected_protocol || ""}
          onChange={setProtocol}
          options={
            data.protocols.length
              ? data.protocols.map((p: string) => [p, p.slice(0, 16)])
              : [["", "No verified model trials"]]
          }
        />
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
        <a
          className="button"
          href={
            "/api/research/export" +
            (data.selected_protocol
              ? "?protocol=" + encodeURIComponent(data.selected_protocol)
              : "")
          }
        >
          Research bundle ↓
        </a>
      </div>
      <p className="notice">
        {ready?.status} · {data.genuine_trials} eligible genuine trials ·{" "}
        {data.release}. Synthetic results only. Protocols and historical scores
        are never pooled.
      </p>
      <section className="panel grow scroll">
        {view === "Summary" ? (
          <>
            <h2>Three research questions, three separate scores</h2>
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
            <details>
              <summary>
                Publication blockers ({ready?.blockers?.length || 0})
              </summary>
              <ul>
                {ready?.blockers?.map((b: string) => (
                  <li key={b}>{human(b)}</li>
                ))}
              </ul>
            </details>
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
                Insufficient data for CUA versus TinyClick versus hybrid or
                other matched comparisons.
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
            {table(
              rows("scenarios").map((r: any) => ({ ...r, label: r.scenario })),
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
        {!data.genuine_trials && (
          <Empty title="Insufficient data — no verified model evaluations">
            Configure the exact checkpoints, run genuine smoke verification,
            then Run All. Reference and test-double records never populate
            research rankings. Exported charts remain clearly labelled
            templates.
          </Empty>
        )}
      </section>
    </div>
  );
}
