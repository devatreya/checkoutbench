import React, { useState, useEffect } from "react";
import {
  api,
  challenge,
  date,
  environments,
  familyName,
  human,
  money,
  requiresAuth,
  seconds,
  status,
  scenarioPublicId,
  scenarioTitle,
  type Model,
  type Run,
  type Scenario,
  type Setup,
} from "./domain";
import { systems, modelName, visibleRun } from "./policy";
import { Badge, Empty, Modal, Select, Stat, Tabs } from "./shared";
export function Overview({
  models,
  runs,
  scenarios,
  start,
}: {
  models: Model[];
  runs: Run[];
  scenarios: Scenario[];
  start: () => void;
}) {
  const completed = runs.filter((r) =>
    ["completed", "failed"].includes(r.status),
  );
  return (
    <div className="overview-layout">
      <section className="hero panel">
        <div>
          <Badge>Specialist AI benchmarking</Badge>
          <h2>
            From field understanding
            <br />
            to checkout completion.
          </h2>
          <p>
            Compare lightweight AI systems on checkout automation tasks across
            payment gateways, e-commerce websites, and government-inspired
            portals. Measure completion accuracy, speed, reliability, and
            recovery from difficult interfaces.
          </p>
          <button className="primary" onClick={start}>
            Start Benchmark →
          </button>
        </div>
        <div className="hero-aside">
          <span>UNDERSTAND</span>
          <b>Fields & customer intent</b>
          <span>INTERACT</span>
          <b>Forms, frames & redirects</b>
          <span>EVALUATE</span>
          <b>Outcomes & recorded evidence</b>
          <small>Local simulations · synthetic payments</small>
        </div>
      </section>
      <div className="stats four">
        <Stat
          label="Specialist configurations available"
          value={models.filter((m) => m.available).length}
          note="5 configurations · availability is not verified inference"
        />
        <Stat
          label="Checkout environments"
          value={new Set(scenarios.map((s) => s.family)).size}
        />
        <Stat
          label="Benchmark scenarios"
          value={scenarios.length}
          note="Active frozen release"
        />
        <Stat
          label="Completed AI evaluations"
          value={completed.length}
          note="Current official evaluation dataset"
        />
      </div>
      <section className="panel grow">
        <div className="panel-title">
          <h2>Recent AI activity</h2>
          <small>Latest 4 specialist attempts</small>
        </div>
        {runs.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Model</th>
                  <th>Scenario</th>
                  <th>Result</th>
                  <th>Duration</th>
                  <th>Date</th>
                </tr>
              </thead>
              <tbody>
                {runs.slice(0, 4).map((r) => (
                  <tr key={r.id}>
                    <td>{modelName(r.model)}</td>
                    <td>
                      {scenarioPublicId(r)}
                      <small>{scenarioTitle(r)}</small>
                    </td>
                    <td>{status(r)}</td>
                    <td>{seconds(r.wall_seconds)}</td>
                    <td>{date(r.timestamp)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty title="Your first benchmark starts here">
            Choose specialist systems and checkout tasks. Recorded AI results
            will appear after your first benchmark.
          </Empty>
        )}
      </section>
    </div>
  );
}
export function Models({
  models,
  setup,
  update,
}: {
  models: Model[];
  setup: Setup;
  update: (v: Partial<Setup>) => void;
}) {
  const [query, setQuery] = useState("");
  return (
    <>
      <div className="toolbar">
        <label className="search">
          Search specialist configurations
          <input
            aria-label="Search specialist configurations"
            placeholder="Search names or capabilities"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <Badge>{setup.models.length} selected</Badge>
      </div>
      <div className="model-grid scroll">
        {systems
          .filter((s) =>
            [s.name, s.capability]
              .join(" ")
              .toLowerCase()
              .includes(query.toLowerCase()),
          )
          .map((s) => {
            const m = models.find((m) => m.id === s.id);
            const selected = setup.models.includes(s.id);
            return (
              <article
                key={s.id}
                className={"model-card panel " + (selected ? "selected" : "")}
              >
                <label className="model-select">
                  <input
                    type="checkbox"
                    aria-label={s.name}
                    checked={selected}
                    onChange={() =>
                      update({
                        models: selected
                          ? setup.models.filter((id) => id !== s.id)
                          : [...setup.models, s.id],
                      })
                    }
                  />
                  <h2>{s.name}</h2>
                </label>
                <Badge tone={m?.available ? "" : "warn"}>
                  {m?.available
                    ? m.status === "ready" || m.status === "verified"
                      ? "Inference verified"
                      : "Configured · inference unverified"
                    : "Unavailable"}
                </Badge>
                <p className="capability">{s.capability}</p>
                <p>{s.description}</p>
                <small>{s.operation}</small>
                <div className="model-meta">
                  <span>
                    Parameters{" "}
                    <b>
                      {typeof m?.parameters === "number"
                        ? m.parameters >= 1e9
                          ? `${(m.parameters / 1e9).toFixed(2)}B`
                          : `${(m.parameters / 1e6).toFixed(2)}M`
                        : "Not reported"}
                    </b>
                  </span>
                  <span>
                    Inference backend <b>{m?.backend || "Not configured"}</b>
                  </span>
                </div>
                {!m?.available && (
                  <details>
                    <summary>Why unavailable?</summary>
                    <p>
                      {m?.reason || "Model metadata is loading or unavailable."}
                    </p>
                  </details>
                )}
              </article>
            );
          })}
      </div>
      <p className="footnote">
        You can plan with unavailable systems. Review will require their
        verified exact checkpoints before research execution. Genuine cold/warm
        smoke evidence is required; availability alone is insufficient.
      </p>
    </>
  );
}
export function ScenarioPreview({
  scenario,
  setup,
  onClose,
}: {
  scenario: Scenario;
  setup: Setup;
  onClose: () => void;
}) {
  const [data, setData] = useState<any>(null),
    [error, setError] = useState(""),
    [tab, setTab] = useState("Checkout");
  useEffect(() => {
    let active = true;
    api(
      `/preview/${encodeURIComponent(scenario.public_id || scenario.id)}?seed=${setup.seed}${setup.profile ? "&profile=" + encodeURIComponent(setup.profile) : ""}&agent_mode=${setup.agent_mode}`,
      {},
    )
      .then((d) => active && setData(d))
      .catch((e) => active && setError(e.message));
    return () => {
      active = false;
    };
  }, [scenario.id, setup.seed, setup.profile, setup.agent_mode]);
  return (
    <Modal
      title={`${scenarioPublicId(scenario)} · Preview`}
      onClose={onClose}
      wide
    >
      <Tabs
        label="Preview views"
        items={["Checkout", "Customer profile", "Task & challenges"]}
        value={tab}
        onChange={setTab}
      />
      {error && (
        <p role="alert" className="notice error">
          {error}
        </p>
      )}
      {!data ? (
        <Empty title="Loading preview…" />
      ) : tab === "Checkout" ? (
        <iframe
          className="checkout-frame"
          title="Checkout preview"
          src={data.url}
        />
      ) : tab === "Customer profile" ? (
        <div className="scroll modal-body">
          <p>
            Synthetic customer information, shown only in this operator preview.
          </p>
          <pre>{JSON.stringify(data.task?.profile, null, 2)}</pre>
        </div>
      ) : (
        <div className="scroll modal-body">
          <h3>Task objective</h3>
          <p>
            {data.task?.instruction ||
              data.task?.task ||
              "Follow the supplied synthetic customer request."}
          </p>
          <h3>Main challenges</h3>
          <p>{scenario.description || challenge(scenario)}</p>
          <h3>Success condition</h3>
          <p>{human(scenario.expected_outcome)}</p>
          <ul>
            {scenario.success_conditions?.map((x) => (
              <li key={x}>{human(x)}</li>
            ))}
          </ul>
          <p>
            Author criteria here do not change what model sessions receive. This
            preview is separate from scored trials.
          </p>
        </div>
      )}
    </Modal>
  );
}
export function Scenarios({
  scenarios,
  setup,
  releaseName,
}: {
  releaseName: string;
  scenarios: Scenario[];
  setup: Setup;
  update: (v: Partial<Setup>) => void;
}) {
  const active = scenarios;
  const families = new Set(active.map((s) => s.implementation_family));
  return (
    <div className="coverage-workspace">
      <div className="stats four">
        <Stat
          label="Environment families"
          value={9}
          note="Provider-inspired and government simulations"
        />
        <Stat
          label="Client implementation families"
          value={families.size}
          note="Shared infrastructure; independent validation pending"
        />
        <Stat
          label="Frozen active tasks"
          value={active.length}
          note="Development + validation; sealed tests excluded"
        />
        <Stat
          label="Research tracks"
          value={3}
          note="Core · Resilience · Complex portals"
        />
      </div>
      <section className="panel grow scroll">
        <div className="panel-title">
          <h2>Understand the coverage. Run the whole suite.</h2>
          <span className="badge">{releaseName}</span>
        </div>
        <p>
          Every selected model receives all {active.length} tasks in the same
          frozen order, with identical synthetic customer data. Repetitions
          measure variability; they do not add independent websites.
        </p>
        <div className="environment-grid">
          {environments.map(([id, name, description]) => (
            <article key={id}>
              <b>{name}</b>
              <small>{description}</small>
            </article>
          ))}
        </div>
        <div className="coverage-tracks">
          {[
            [
              "A",
              "Core Checkout",
              "Contact, addresses, optional fields, billing and payment preparation.",
            ],
            [
              "B",
              "Checkout Resilience",
              "QR degradation, authentication, redirects, validation and recovery.",
            ],
            [
              "C",
              "Complex / Legacy Portals",
              "Railway passengers, appointments and challan verification.",
            ],
          ].map(([id, title, desc]) => (
            <section key={id}>
              <h3>
                {id} · {title}
              </h3>
              <p>{desc}</p>
              <small>
                {active.filter((s) => s.research_track === id).length} assigned
                tasks
              </small>
            </section>
          ))}
        </div>
        <details>
          <summary>Browse scenario IDs and tasks</summary>
          <p>
            Presentation names identify each simulated task. The frozen suite
            and execution order are unchanged.
          </p>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Scenario</th>
                  <th>Task</th>
                  <th>Device / payment</th>
                </tr>
              </thead>
              <tbody>
                {active.map((s) => (
                  <tr key={s.id}>
                    <td>{scenarioPublicId(s)}</td>
                    <td>
                      {scenarioTitle(s)}
                      <small>{s.description}</small>
                    </td>
                    <td>
                      {human(s.platform)}
                      <small>{human(s.method)}</small>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
        <details>
          <summary>Payment methods and authentication</summary>
          <p>
            Card · UPI QR · mobile UPI intent · legacy VPA where supported ·
            Netbanking · Stripe Link · cash on delivery. OTP and 3DS are
            authentication mechanisms attached to funding methods, not separate
            payment methods. Unsupported combinations follow predefined safe
            handling.
          </p>
        </details>
        <details>
          <summary>What the scores mean</summary>
          <p>
            Preparation, safe abort, authentication handoff and simulated
            completion are separate outcomes. No real financial transaction
            occurs. These synthetic environments do not measure
            production-provider success. Human ground-truth review and
            checkpoint verification are required before publication.
          </p>
        </details>
      </section>
      <p className="notice">
        {active.length * setup.repeats} trials per model ·{" "}
        {active.length * setup.repeats * setup.models.length} total. Runtime and
        hosting cost are unknown until measured; this may take hours. Review
        before starting, then pause or stop from Live Benchmark.
      </p>
    </div>
  );
}
export function Review({
  models,
  scenarios,
  profiles,
  setup,
  update,
  issues,
}: {
  models: Model[];
  scenarios: Scenario[];
  profiles: { id: string; name: string }[];
  setup: Setup;
  update: (v: Partial<Setup>) => void;
  issues: string[];
}) {
  const [estimate, setEstimate] = useState<any>(null),
    [error, setError] = useState("");
  useEffect(() => {
    setEstimate(null);
    setError("");
    let active = true;
    const timer = setTimeout(() => {
      if (!setup.models.length || !setup.scenarios.length) return;
      api("/estimate", setup)
        .then((d) => active && setEstimate(d))
        .catch((e) => active && setError(e.message));
    }, 250);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [JSON.stringify(setup)]);
  const selected = scenarios.filter((s) => setup.scenarios.includes(s.id));
  const number = (
    key: keyof Setup,
    label: string,
    min: number,
    max: number,
  ) => (
    <label className="control">
      {label}
      <input
        aria-label={label}
        type="number"
        min={min}
        max={max}
        value={setup[key] as number}
        onChange={(e) => update({ [key]: e.target.valueAsNumber })}
      />
    </label>
  );
  const unknown = setup.models.filter(
    (id) => !models.find((m) => m.id === id)?.pricing,
  );
  return (
    <div className="review-grid">
      <section className="panel scroll">
        <h2>Experiment summary</h2>
        <div className="summary-list">
          <p>
            <b>Systems</b>
            <span>
              {setup.models.map(modelName).join(", ") || "None selected"}
            </span>
          </p>
          <p>
            <b>Scenarios</b>
            <span>{setup.scenarios.length} tasks · active frozen manifest</span>
          </p>
          <p>
            <b>Total evaluations</b>
            <span>
              {setup.models.length * setup.scenarios.length * setup.repeats}
            </span>
          </p>
          <p>
            <b>Customer</b>
            <span>
              {profiles.find((p) => p.id === setup.profile)?.name ||
                "Scenario default synthetic profile"}
            </span>
          </p>
        </div>
        <div className="cost-box">
          <h3>Estimated inference expenditure</h3>
          <strong>
            {unknown.length
              ? "Not reported"
              : estimate
                ? money(estimate.estimated_cost)
                : "Calculating…"}
          </strong>
          <p>
            {unknown.length
              ? `Pricing is not available for ${unknown.map(modelName).join(", ")}. Local GPU/hosting expense is not an API charge and is not estimated.`
              : estimate?.assumption}
          </p>
          <p>
            {setup.spending_cap
              ? `Batch cap: ${money(setup.spending_cap)}`
              : "No spending cap configured."}
          </p>
        </div>
        {error && (
          <p role="alert" className="notice error">
            Estimate unavailable: {error}
          </p>
        )}
        <p className="notice">
          {selected.filter(requiresAuth).length} selected scenarios require
          authentication or user handoff. Approval is fictional and runner-owned
          in simulated-completion tests. Checkout-ready does not mean a
          completed financial transaction.
        </p>
        {issues.length ? (
          <div className="notice error" role="status">
            <b>Resolve before starting</b>
            <ul>
              {issues.map((x) => (
                <li key={x}>{x}</li>
              ))}
            </ul>
          </div>
        ) : (
          <p className="notice">
            Conditions are ready for review. Verified systems will attempt real
            inference only after you explicitly confirm Run All.
          </p>
        )}
      </section>
      <section className="panel scroll">
        <h2>Evaluation conditions</h2>
        <div className="form-grid">
          {number("repeats", "Repetitions per scenario", 1, 100)}
          <p className="notice">
            Frozen seed 2026 · scenario-default profiles · full active manifest
          </p>
          {number("max_steps", "Maximum actions", 5, 500)}
          {number("timeout", "Timeout (seconds)", 10, 1800)}
        </div>
        <details className="advanced">
          <summary>Advanced settings</summary>
          <div className="form-grid">
            {number("max_tokens", "Output token budget", 256, 131072)}
            <Select
              label="Reasoning configuration"
              value={setup.reasoning}
              onChange={(v) => update({ reasoning: v })}
              options={["default"]}
            />
            <label className="control">
              Spending cap (USD)
              <input
                aria-label="Spending cap (USD)"
                type="number"
                min="0.01"
                step="0.01"
                placeholder="No cap"
                value={setup.spending_cap ?? ""}
                onChange={(e) =>
                  update({
                    spending_cap:
                      e.target.value === "" ? null : e.target.valueAsNumber,
                  })
                }
              />
            </label>
            {number("infrastructure_retries", "Infrastructure retries", 0, 3)}
          </div>
          <p className="footnote">
            These specialist adapters do not advertise configurable reasoning
            effort. Remote specialist costs are unreported; a spending cap
            cannot bound those endpoints.
          </p>
          <label className="check">
            <input
              type="checkbox"
              checked={setup.video}
              onChange={(e) => update({ video: e.target.checked })}
            />
            Record browser video
          </label>
        </details>
        <p className="footnote">
          Same task, customer, scenario seed and viewport across selected
          systems. Runs execute sequentially with fresh browser sessions.
          Model-selected actions and controller assistance remain separately
          attributed.
        </p>
      </section>
    </div>
  );
}
