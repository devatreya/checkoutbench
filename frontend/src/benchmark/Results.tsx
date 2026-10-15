import React, { useState, useEffect } from "react";
import {
  challenge,
  csv,
  date,
  download,
  environments,
  familyName,
  human,
  money,
  num,
  pct,
  seconds,
  status,
  type Run,
  type Scenario,
} from "./domain";
import { modelName, shortName, systems } from "./policy";
import {
  comparable,
  conditionLabel,
  conditions,
  median,
  scored,
  stats,
} from "./analysis";
import { Empty, Modal, Pager, Select, Stat, Tabs } from "./shared";
import RunDetails from "./RunDetails";
import ResearchResults from "./ResearchResults";
const metricDefinitions = [
  [
    "Checkout success rate",
    "Fraction of scored completed/failed runs reaching the correct scenario endpoint. Unavailable, blocked, stopped and running attempts are excluded.",
  ],
  [
    "Field accuracy",
    "Average recorded fraction of required fields filled correctly. Missing instrumentation is omitted and reported-count coverage is shown.",
  ],
  [
    "Payment-method accuracy",
    "Whether the requested method was selected. Shown only when separately instrumented. The existing payment validation score can also check credentials, saved methods or QR validity.",
  ],
  [
    "Completion time",
    "Median recorded wall-clock duration from test start to final outcome, including failures, browser setup and overhead.",
  ],
  [
    "Inference latency",
    "Time recorded in model inference. May include lazy model loading and client processing; it is not pure hardware compute time.",
  ],
  [
    "Recovery rate",
    "Average recorded recovery_success_rate over runs that report it; not inferred from retries or overall success.",
  ],
  [
    "Confidence interval",
    "95% Wilson interval around the observed checkout success fraction. Small samples produce wide intervals; this is not a significance test between models.",
  ],
  [
    "Cost per successful checkout",
    "Total reported inference cost over all finished attempts, including stopped or infrastructure-failed attempts, divided by scored successful outcomes. Not reported if any cost is missing or there are no successes. Local hosting costs may not be included.",
  ],
  [
    "Action count",
    "Recorded number of browser interactions. Deterministic and model-selected actions remain separately attributed in Run Details.",
  ],
  [
    "Reliability",
    "Consistency across repeated runs and scenarios. Judge distributions, failures and uncertainty; no invented composite reliability score is shown.",
  ],
];
function Metrics({ close }: { close: () => void }) {
  return (
    <Modal title="Metrics Explained" onClose={close}>
      <div className="scroll modal-body">
        <section>
          <h3>Research v3.0 definitions</h3>
          <p>
            Task resolution includes valid safe stops and handoffs. Preparation
            requires correct fields, method and payment details. Neither means
            money moved. QR recovery uses only encountered recoverable problems;
            clean QR trials are excluded. OTP/3DS handoff accuracy is separate
            from the funding method. Stage success is conditional on
            encountering that applicable stage; end-to-end success uses all
            scored assigned trials. Successful latency excludes failures.
            Research intervals resample implementation clusters after averaging
            repetitions within tasks. Fewer than five clusters: insufficient
            data. Shared infrastructure limits generalisation even with more
            clusters. Cost per success includes all finished attempts and
            remains unknown if any cost is missing.
          </p>
        </section>
        <h3>Historical v1–v2.1 definitions</h3>
        {metricDefinitions.map(([k, v]) => (
          <section key={k}>
            <h3>{k}</h3>
            <p>{v}</p>
          </section>
        ))}
        <p className="notice">
          A completed checkout-ready state is not a completed financial
          transaction. UPI app approval and OTP/3DS are synthetic handoffs or
          runner-owned simulated authorisation.
        </p>
      </div>
    </Modal>
  );
}
function Chart({ groups }: { groups: [string, Run[]][] }) {
  return (
    <div
      className="performance-chart"
      role="img"
      aria-label="Observed checkout success by model"
    >
      {groups.map(([id, rows]) => {
        const s = stats(rows);
        return (
          <div key={id}>
            <span>
              {shortName(id)}
              <small>{s.n} scored runs</small>
            </span>
            <div className="bar-track">
              <div style={{ width: `${(s.success ?? 0) * 100}%` }} />
            </div>
            <b>{pct(s.success)}</b>
          </div>
        );
      })}
    </div>
  );
}
export default function Results({
  runs,
  scenarios,
  runId,
  onRun,
  onBack,
}: {
  runs: Run[];
  scenarios: Scenario[];
  runId?: string;
  onRun: (id: string) => void;
  onBack: () => void;
}) {
  const [view, setView] = useState("Summary"),
    [version, setVersion] = useState("3.0"),
    [cohort, setCohort] = useState(""),
    [family, setFamily] = useState("all"),
    [difficulty, setDifficulty] = useState("all"),
    [method, setMethod] = useState("all"),
    [more, setMore] = useState(false),
    [search, setSearch] = useState(""),
    [outcome, setOutcome] = useState("all"),
    [page, setPage] = useState(0),
    [metrics, setMetrics] = useState(false),
    [compare, setCompare] = useState<string[]>(systems.map((s) => s.id)),
    [scenarioId, setScenarioId] = useState("");
  const meta = (r: Run) => scenarios.find((s) => s.id === r.scenario);
  const versionRows = runs.filter(
    (r) => version === "all" || (r.benchmark_version || "1.0") === version,
  );
  const conditionMap = new Map<string, Run>();
  versionRows.forEach((r) => {
    if (!conditionMap.has(conditions(r))) conditionMap.set(conditions(r), r);
  });
  const activeCohort =
    view === "Run Explorer" && cohort === "all"
      ? "all"
      : conditionMap.has(cohort)
        ? cohort
        : [...conditionMap.keys()][0] || "";
  const filtered = versionRows.filter(
    (r) =>
      (activeCohort === "all" || conditions(r) === activeCohort) &&
      (family === "all" || (r.environment || meta(r)?.family) === family) &&
      (difficulty === "all" ||
        (meta(r)?.difficulty || r.difficulty_config?.reliability) ===
          difficulty) &&
      (method === "all" ||
        (r.requested_payment_method || meta(r)?.method) === method),
  );
  const analysisRows =
    version === "all" && view !== "Run Explorer" ? [] : filtered;
  const groups = systems
    .map(
      (s) =>
        [s.id, analysisRows.filter((r) => r.model === s.id)] as [string, Run[]],
    )
    .filter(([, r]) => r.length);
  const selectedGroups = groups.filter(([id]) => compare.includes(id));
  const matched = comparable(selectedGroups.map(([, rs]) => rs));
  const totals = stats(analysisRows);
  const history = filtered.filter(
    (r) =>
      (outcome === "all" || r.status === outcome) &&
      [
        r.id,
        modelName(r.model),
        r.scenario,
        r.scenario_title,
        familyName(r.environment),
        r.failure_reason,
      ]
        .join(" ")
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  const scenarioGroups = [...new Set(analysisRows.map((r) => r.scenario))].map(
    (id) => {
      const rs = analysisRows.filter((r) => r.scenario === id);
      const failures = new Map<string, number>();
      rs.filter((r) => scored(r) && !r.success).forEach((r) =>
        failures.set(
          r.failure_reason || "Not reported",
          (failures.get(r.failure_reason || "Not reported") || 0) + 1,
        ),
      );
      return {
        id,
        rs,
        stat: stats(rs),
        failure:
          [...failures].sort((a, b) => b[1] - a[1])[0]?.[0] || "None recorded",
        meta: meta(rs[0]),
      };
    },
  );
  useEffect(
    () => setPage(0),
    [view, version, activeCohort, family, difficulty, method, search, outcome],
  );
  const current = runs.find((r) => r.id === runId);
  const summaryExport = history.map((r) => ({
    run_id: r.id,
    model: r.model,
    scenario: r.scenario,
    environment: r.environment,
    benchmark_version: r.benchmark_version,
    cohort: r.cohort,
    start_time: r.timestamp,
    status: r.status,
    success: r.success,
    duration_seconds: r.wall_seconds,
    inference_cost: r.cost_kind === "not_reported" ? null : r.cost,
    cost_kind: r.cost_kind,
    failure_category: r.failure_reason,
  }));
  const comparisonExport = selectedGroups.map(([id, rs]) => {
    const s = stats(rs);
    return {
      model: id,
      benchmark_version: version,
      conditions: activeCohort,
      runs: s.n,
      success_rate: s.success,
      confidence_interval: s.ci,
      median_duration: s.duration,
      field_accuracy: s.field,
      payment_method_accuracy: s.payment,
      payment_validation_accuracy: s.paymentValidation,
      recovery_rate: s.recovery,
      cost_per_success: s.costPerSuccess,
    };
  });
  const insight =
    matched && selectedGroups.length > 1
      ? (() => {
          const rank = selectedGroups
            .map(([id, rs]) => ({ id, s: stats(rs) }))
            .sort((a, b) => (b.s.success ?? 0) - (a.s.success ?? 0));
          return rank[0].s.success !== rank[1].s.success
            ? `${shortName(rank[0].id)} has the highest observed success rate in these matched trials (${pct(rank[0].s.success)}). This observation is not evidence of statistical significance.`
            : "The selected systems have equal observed success rates in these matched trials.";
        })()
      : "No overall winner is inferred. Compare matched scenario/seed/profile/repetition coverage and at least five scored trials per system; even then, confidence intervals are not a significance test.";
  return (
    <>
      <div className="toolbar results-top">
        {runId ? (
          <button onClick={onBack}>← Back to results</button>
        ) : (
          <Tabs
            label="Results views"
            items={[
              "Summary",
              "Model Comparison",
              "Scenario Analysis",
              "Payment & Stage Analysis",
              "Run Explorer",
            ]}
            value={view}
            onChange={(v) => {
              setView(v);
              setScenarioId("");
            }}
          />
        )}
        <button onClick={() => setMetrics(true)}>Metrics Explained</button>
        {!runId && (
          <button
            onClick={() =>
              download("all-specialist-runs.json", {
                scope:
                  "All saved specialist runs; all versions; excludes hidden systems and test records",
                runs,
              })
            }
          >
            Export all specialist runs JSON
          </button>
        )}
      </div>
      {metrics && <Metrics close={() => setMetrics(false)} />}{" "}
      {runId ? (
        current ? (
          <RunDetails run={current} scenario={meta(current)} />
        ) : (
          <Empty title="Run unavailable in this workspace">
            Choose a specialist record from Run Explorer.
          </Empty>
        )
      ) : (
        <>
          <div className="filters">
            <Select
              label="Results version"
              value={version}
              onChange={setVersion}
              options={[
                "3.0",
                "2.1",
                "2.0",
                "1.0",
                ...(view === "Run Explorer"
                  ? [["all", "All saved versions"] as [string, string]]
                  : []),
              ]}
            />
            {(version !== "3.0" || view === "Run Explorer") && (
              <>
                <Select
                  label="Scenario cohort / conditions"
                  value={activeCohort}
                  onChange={setCohort}
                  options={[
                    ...(view === "Run Explorer"
                      ? [["all", "All configurations"] as [string, string]]
                      : []),
                    ...(!conditionMap.size
                      ? [["", "No recorded conditions"] as [string, string]]
                      : []),
                    ...[...conditionMap].map(
                      ([k, r]) => [k, conditionLabel(r)] as [string, string],
                    ),
                  ]}
                />
                <button aria-expanded={more} onClick={() => setMore(!more)}>
                  Filter runs
                </button>
              </>
            )}
          </div>
          {more && (version !== "3.0" || view === "Run Explorer") && (
            <div className="filters">
              <Select
                label="Results environment"
                value={family}
                onChange={setFamily}
                options={[
                  "all",
                  ...environments.map((e) => [e[0], e[1]] as [string, string]),
                ]}
              />
              <Select
                label="Results difficulty"
                value={difficulty}
                onChange={setDifficulty}
                options={[
                  "all",
                  ...new Set(scenarios.map((s) => s.difficulty || "standard")),
                ]}
              />
              <Select
                label="Results payment method"
                value={method}
                onChange={setMethod}
                options={["all", ...new Set(scenarios.map((s) => s.method))]}
              />
              <button
                onClick={() => {
                  setFamily("all");
                  setDifficulty("all");
                  setMethod("all");
                  setSearch("");
                  setOutcome("all");
                }}
              >
                Clear filters
              </button>
            </div>
          )}
          {version === "3.0" && view !== "Run Explorer" ? (
            <ResearchResults view={view} onRun={onRun} />
          ) : view === "Payment & Stage Analysis" ? (
            <Empty title="Stage analytics require research scoring v3.0">
              Historical raw records are preserved without retroactive stage
              reconstruction. Select version 3.0.
            </Empty>
          ) : version === "all" && view !== "Run Explorer" ? (
            <Empty title="Choose one benchmark version">
              Summary and comparisons never pool benchmark versions.
            </Empty>
          ) : view === "Summary" ? (
            <div className="summary-workspace">
              <div className="stats six">
                <Stat
                  label="Checkout success rate"
                  value={pct(totals.success)}
                  note={`${totals.k} successful / ${totals.n} scored runs`}
                />
                <Stat
                  label="Median completion time"
                  value={seconds(totals.duration)}
                  note="Recorded final outcomes, including failures"
                />
                <Stat
                  label="Required-field accuracy"
                  value={pct(totals.field)}
                  note={`${totals.reportedFields} of ${totals.n} runs report this metric`}
                />
                <Stat
                  label="Payment-method accuracy"
                  value={pct(totals.payment)}
                  note={`${totals.reportedPayment} runs report method-only accuracy`}
                />
                <Stat
                  label="Completed evaluations"
                  value={totals.n}
                  note={`${analysisRows.length - totals.n} other attempts excluded from rates`}
                />
                <Stat
                  label="Inference expenditure"
                  value={money(totals.cost)}
                  note="Includes reported/estimated cost; missing costs stay unknown"
                />
              </div>
              <section className="panel grow scroll">
                <h2>Observed checkout success</h2>
                {groups.length ? (
                  <Chart groups={groups} />
                ) : (
                  <Empty title="No AI evaluations in this scope">
                    Run configured specialists, or select a recorded version and
                    conditions cohort.
                  </Empty>
                )}
                <p className="footnote">
                  Only the selected version and execution conditions are
                  aggregated. Payment validation scores can include more than
                  method selection; inspect individual runs for the recorded
                  evidence. Reference and test-double records are excluded.
                </p>
              </section>
            </div>
          ) : view === "Model Comparison" ? (
            <>
              <div className="compare-select">
                {systems.map((s) => (
                  <label key={s.id}>
                    <input
                      type="checkbox"
                      checked={compare.includes(s.id)}
                      onChange={() =>
                        setCompare(
                          compare.includes(s.id)
                            ? compare.filter((x) => x !== s.id)
                            : [...compare, s.id],
                        )
                      }
                    />
                    {s.short}
                  </label>
                ))}
              </div>
              <div className="panel grow scroll">
                <div className="panel-title">
                  <h2>Model comparison</h2>
                  <button
                    onClick={() =>
                      download(
                        "filtered-comparison.csv",
                        csv(comparisonExport),
                        true,
                      )
                    }
                  >
                    Export filtered comparison CSV
                  </button>
                </div>
                {selectedGroups.length ? (
                  <>
                    <Chart groups={selectedGroups} />
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>Model / runs</th>
                            <th>Success / 95% CI</th>
                            <th>Median time</th>
                            <th>Fields</th>
                            <th>Method / payment validation</th>
                            <th>Recovery</th>
                            <th>Cost / success</th>
                          </tr>
                        </thead>
                        <tbody>
                          {selectedGroups.map(([id, rows]) => {
                            const s = stats(rows),
                              best =
                                matched &&
                                s.success ===
                                  Math.max(
                                    ...selectedGroups.map(
                                      ([, r]) => stats(r).success ?? -1,
                                    ),
                                  );
                            const metric = (
                              key: keyof ReturnType<typeof stats>,
                              text: React.ReactNode,
                              lower = false,
                            ) => {
                              const values = selectedGroups.map(
                                ([, r]) => stats(r)[key],
                              );
                              const value = s[key];
                              const rawKey = (
                                {
                                  duration: "wall_seconds",
                                  field: "required_field_accuracy",
                                  paymentValidation: "payment_accuracy",
                                  recovery: "recovery_success_rate",
                                } as Record<string, string>
                              )[key];
                              const complete =
                                !rawKey ||
                                selectedGroups.every(([, rows]) =>
                                  rows
                                    .filter(scored)
                                    .every(
                                      (r) =>
                                        typeof r[rawKey] === "number" &&
                                        Number.isFinite(r[rawKey]),
                                    ),
                                );
                              const bestMetric =
                                matched &&
                                complete &&
                                typeof value === "number" &&
                                values.every((v) => typeof v === "number") &&
                                value ===
                                  (lower
                                    ? Math.min(...(values as number[]))
                                    : Math.max(...(values as number[])));
                              return (
                                <td
                                  className={
                                    bestMetric ? "metric-best" : undefined
                                  }
                                >
                                  {text}
                                  {bestMetric && (
                                    <small>
                                      {key === "paymentValidation"
                                        ? "Best observed validation"
                                        : "Best observed"}
                                      {values.filter((v) => v === value)
                                        .length > 1
                                        ? " · tied"
                                        : ""}
                                    </small>
                                  )}
                                </td>
                              );
                            };
                            return (
                              <tr key={id}>
                                <td>
                                  {shortName(id)}
                                  <small>
                                    {s.n} scored runs{" "}
                                    {best ? "· Highest observed success" : ""}
                                  </small>
                                </td>
                                <td>
                                  {pct(s.success)}
                                  <small>
                                    {s.ci
                                      ? `${pct(s.ci[0])}–${pct(s.ci[1])}`
                                      : "Not reported"}
                                  </small>
                                </td>
                                {metric("duration", seconds(s.duration), true)}
                                {metric("field", pct(s.field))}
                                {metric(
                                  "paymentValidation",
                                  <>
                                    {pct(s.payment)}
                                    <small>
                                      Validation: {pct(s.paymentValidation)}
                                    </small>
                                  </>,
                                )}
                                {metric("recovery", pct(s.recovery))}
                                {metric(
                                  "costPerSuccess",
                                  money(s.costPerSuccess),
                                  true,
                                )}
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </>
                ) : (
                  <Empty title="No model comparisons in this scope">
                    Select systems and recorded conditions with comparable
                    trials.
                  </Empty>
                )}
                <p className="notice">{insight}</p>
              </div>
            </>
          ) : view === "Scenario Analysis" ? (
            <div className="panel grow flex-panel">
              <div className="panel-title">
                <h2>
                  {scenarioId
                    ? `${scenarioId} · performance across systems`
                    : "Scenario analysis"}
                </h2>
                {scenarioId && (
                  <button onClick={() => setScenarioId("")}>
                    Back to scenario list
                  </button>
                )}
              </div>
              {scenarioId ? (
                <div className="scroll">
                  <p>{scenarios.find((s) => s.id === scenarioId)?.title}</p>
                  <Chart
                    groups={systems
                      .map(
                        (s) =>
                          [
                            s.id,
                            analysisRows.filter(
                              (r) =>
                                r.model === s.id && r.scenario === scenarioId,
                            ),
                          ] as [string, Run[]],
                      )
                      .filter(([, r]) => r.length)}
                  />
                  <p>
                    {challenge(
                      scenarios.find((s) => s.id === scenarioId) || {
                        id: scenarioId,
                        title: "",
                        family: "",
                        features: [],
                        method: "",
                        benchmark_version: version,
                      },
                    )}
                  </p>
                  <button
                    onClick={() => {
                      setView("Run Explorer");
                      setSearch(scenarioId);
                    }}
                  >
                    Inspect these runs
                  </button>
                </div>
              ) : (
                <>
                  <div className="table-scroll grow">
                    <table>
                      <thead>
                        <tr>
                          <th>Scenario / environment</th>
                          <th>Difficulty</th>
                          <th>Attempts / successes</th>
                          <th>Most common failure</th>
                          <th>Median time</th>
                          <th>Inspect</th>
                        </tr>
                      </thead>
                      <tbody>
                        {scenarioGroups
                          .slice(page * 8, page * 8 + 8)
                          .map((x) => (
                            <tr key={x.id}>
                              <td>
                                {x.id} ·{" "}
                                {x.meta?.title || x.rs[0].scenario_title}
                                <small>
                                  {familyName(
                                    x.meta?.family || x.rs[0].environment,
                                  )}
                                </small>
                              </td>
                              <td>{x.meta?.difficulty || "Not reported"}</td>
                              <td>
                                {x.stat.n} / {x.stat.k}
                                <small>
                                  {x.rs.length - x.stat.n} unavailable /
                                  unscored attempts
                                </small>
                              </td>
                              <td>{human(x.failure)}</td>
                              <td>{seconds(x.stat.duration)}</td>
                              <td>
                                <button onClick={() => setScenarioId(x.id)}>
                                  Analyse
                                </button>
                              </td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                    {!scenarioGroups.length && (
                      <Empty title="No scenario outcomes in this scope" />
                    )}
                  </div>
                  <Pager
                    page={page}
                    total={scenarioGroups.length}
                    onChange={setPage}
                  />
                </>
              )}
            </div>
          ) : (
            <>
              <div className="toolbar">
                <input
                  aria-label="Search run records"
                  placeholder="Run ID, system, scenario or failure"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
                <Select
                  label="Run status"
                  value={outcome}
                  onChange={setOutcome}
                  options={[
                    "all",
                    "completed",
                    "failed",
                    "unavailable",
                    "blocked",
                    "stopped",
                    "running",
                  ]}
                />
                <button
                  onClick={() =>
                    download(
                      "filtered-run-summaries.csv",
                      csv(summaryExport),
                      true,
                    )
                  }
                >
                  Export filtered summaries CSV
                </button>
              </div>
              <div className="panel grow flex-panel">
                <div className="table-scroll grow">
                  <table>
                    <thead>
                      <tr>
                        <th>Run / started</th>
                        <th>Model / scenario</th>
                        <th>Environment / method</th>
                        <th>Result / failure</th>
                        <th>Duration / cost</th>
                        <th>Evidence</th>
                      </tr>
                    </thead>
                    <tbody>
                      {history.slice(page * 8, page * 8 + 8).map((r) => (
                        <tr key={r.id}>
                          <td className="mono">
                            {r.id}
                            <small>{date(r.timestamp)}</small>
                          </td>
                          <td>
                            {shortName(r.model)}
                            <small>{r.scenario}</small>
                          </td>
                          <td>
                            {familyName(r.environment || meta(r)?.family)}
                            <small>
                              {human(
                                r.requested_payment_method || meta(r)?.method,
                              )}
                            </small>
                          </td>
                          <td>
                            {status(r)}
                            {r.failed_stage && (
                              <small>Failed stage: {r.failed_stage}</small>
                            )}
                            <small>
                              {r.failure_reason
                                ? human(r.failure_reason)
                                : "No failure recorded"}
                            </small>
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
                  {!history.length && (
                    <Empty title="No matching run records">
                      Choose another version, conditions cohort or filter. Every
                      saved specialist attempt remains accessible here.
                    </Empty>
                  )}
                </div>
                <Pager page={page} total={history.length} onChange={setPage} />
              </div>
              <small>
                Showing the selected filters. Individual JSON and trace exports
                are available inside a run. All-specialist JSON includes every
                saved specialist version and configuration.
              </small>
            </>
          )}
        </>
      )}
    </>
  );
}
