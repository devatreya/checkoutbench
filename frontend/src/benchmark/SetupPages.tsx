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
          value={
            new Set(
              scenarios
                .filter((s) => s.benchmark_version === "2.1")
                .map((s) => s.family),
            ).size
          }
        />
        <Stat
          label="Benchmark scenarios"
          value={scenarios.filter((s) => s.benchmark_version === "2.1").length}
          note="Validated v2.1 suite"
        />
        <Stat
          label="Completed AI evaluations"
          value={completed.length}
          note="Specialist runs across saved versions"
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
                    <td>{r.scenario}</td>
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
        checkpoints or endpoints before execution. Configured systems are
        validated by their first explicit inference run.
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
      `/preview/${encodeURIComponent(scenario.id)}?seed=${setup.seed}${setup.profile ? "&profile=" + encodeURIComponent(setup.profile) : ""}&agent_mode=${setup.agent_mode}`,
      {},
    )
      .then((d) => active && setData(d))
      .catch((e) => active && setError(e.message));
    return () => {
      active = false;
    };
  }, [scenario.id, setup.seed, setup.profile, setup.agent_mode]);
  return (
    <Modal title={`${scenario.id} · Preview`} onClose={onClose} wide>
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
          <p>{challenge(scenario)}</p>
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
  update,
}: {
  scenarios: Scenario[];
  setup: Setup;
  update: (v: Partial<Setup>) => void;
}) {
  const [family, setFamily] = useState("all"),
    [difficulty, setDifficulty] = useState("all"),
    [method, setMethod] = useState("all"),
    [type, setType] = useState("all"),
    [auth, setAuth] = useState("all"),
    [device, setDevice] = useState("all"),
    [query, setQuery] = useState(""),
    [version, setVersion] = useState("2.1"),
    [preview, setPreview] = useState<Scenario | null>(null),
    [filters, setFilters] = useState(false);
  const suite = scenarios.filter((s) => s.benchmark_version === version);
  const visible = suite.filter(
    (s) =>
      (family === "all" || s.family === family) &&
      (difficulty === "all" || s.difficulty === difficulty) &&
      (method === "all" || s.method === method) &&
      (type === "all" ||
        (type === "core"
          ? !s.features.includes("holdout")
          : type === "holdout"
            ? s.features.includes("holdout")
            : s.provenance?.fidelity_classification?.includes("stress") ||
              s.variant?.includes("stress"))) &&
      (auth === "all" ||
        (auth === "qr"
          ? s.method === "upi_qr" || !!s.qr
          : auth === "auth"
            ? requiresAuth(s)
            : !requiresAuth(s))) &&
      (device === "all" || s.platform === device) &&
      `${s.id} ${s.title} ${challenge(s)}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );
  const choose = (rows: Scenario[]) =>
    update({ scenarios: rows.map((s) => s.id) });
  return (
    <>
      <div className="environment-grid">
        {environments.map(([id, name, description]) => (
          <button
            key={id}
            className={family === id ? "chosen" : ""}
            aria-pressed={family === id}
            onClick={() => setFamily(family === id ? "all" : id)}
          >
            <b>{name}</b>
            <small>{description}</small>
          </button>
        ))}
      </div>
      <div className="toolbar compact">
        <input
          aria-label="Search scenarios"
          placeholder="Search scenarios or capabilities"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <Select
          label="Environment"
          value={family}
          onChange={setFamily}
          options={[
            ["all", "All environments"],
            ...environments.map((e) => [e[0], e[1]] as [string, string]),
          ]}
        />
        <button onClick={() => setFilters(!filters)} aria-expanded={filters}>
          Filters & versions
        </button>
      </div>
      {filters && (
        <div className="filters compact">
          <Select
            label="Difficulty"
            value={difficulty}
            onChange={setDifficulty}
            options={[
              "all",
              ...new Set(suite.map((s) => s.difficulty || "standard")),
            ]}
          />
          <Select
            label="Payment method"
            value={method}
            onChange={setMethod}
            options={["all", ...new Set(suite.map((s) => s.method))]}
          />
          <Select
            label="Scenario type"
            value={type}
            onChange={setType}
            options={["all", "core", "holdout", "stress"]}
          />
          <Select
            label="QR / authentication"
            value={auth}
            onChange={setAuth}
            options={[
              "all",
              ["qr", "QR"],
              ["auth", "OTP / authentication"],
              ["none", "No authentication"],
            ]}
          />
          <Select
            label="Device"
            value={device}
            onChange={setDevice}
            options={["all", "desktop_web", "mobile_web"]}
          />
          <Select
            label="Advanced: benchmark version"
            value={version}
            onChange={(v) => {
              setVersion(v);
              setMethod("all");
              setDifficulty("all");
            }}
            options={[
              "2.1",
              ["2.0", "2.0 · historical preview"],
              ["1.0", "1.0 · historical preview"],
            ]}
          />
        </div>
      )}
      <div className="toolbar selection-tools">
        <button
          onClick={() =>
            choose(suite.filter((s) => family === "all" || s.family === family))
          }
        >
          Select environment
        </button>
        <button
          onClick={() =>
            choose(suite.filter((s) => !s.features.includes("holdout")))
          }
        >
          All core
        </button>
        <button
          onClick={() =>
            choose(
              ["V21-S01", "V21-G02", "V21-RZ01", "V21-ST03", "V21-R01"].flatMap(
                (id) => scenarios.filter((s) => s.id === id),
              ),
            )
          }
        >
          Quick benchmark · 5
        </button>
        <button onClick={() => choose(suite)}>
          Full suite · {suite.length}
        </button>
        <button onClick={() => update({ scenarios: [] })}>
          Clear selection
        </button>
      </div>
      <div className="panel grow scroll scenario-collection">
        <div className="scenario-list">
          {visible.map((s) => (
            <article
              key={s.id}
              className={setup.scenarios.includes(s.id) ? "selected" : ""}
            >
              <label>
                <input
                  type="checkbox"
                  aria-label={`${s.id} ${s.title}`}
                  checked={setup.scenarios.includes(s.id)}
                  onChange={() =>
                    update({
                      scenarios: setup.scenarios.includes(s.id)
                        ? setup.scenarios.filter((x) => x !== s.id)
                        : [...setup.scenarios, s.id],
                    })
                  }
                />
                <div>
                  <b>
                    {s.id} · {s.title}
                  </b>
                  <p>{challenge(s)}</p>
                  <div className="tags">
                    <Badge>{s.difficulty || "standard"}</Badge>
                    <Badge>{human(s.method)}</Badge>
                    <Badge>{human(s.platform || "legacy web")}</Badge>
                    <Badge>
                      {requiresAuth(s)
                        ? human(
                            s.authentication_method || "authentication handoff",
                          )
                        : "No authentication"}
                    </Badge>
                  </div>
                </div>
              </label>
              <button onClick={() => setPreview(s)}>Preview</button>
            </article>
          ))}
          {!visible.length && (
            <Empty title="No matching scenarios">
              Adjust your filters to see more tasks.
            </Empty>
          )}
        </div>
      </div>
      <small>
        {setup.scenarios.length} selected ·{" "}
        {
          setup.scenarios.filter((id) => !visible.some((s) => s.id === id))
            .length
        }{" "}
        outside current filters. Quick-selection buttons replace the selection.
        Historical suites are previewable; model execution requires v2.1.
      </small>
      {preview && (
        <ScenarioPreview
          scenario={preview}
          setup={setup}
          onClose={() => setPreview(null)}
        />
      )}
    </>
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
            <span>
              {setup.scenarios.length} · version{" "}
              {[...new Set(selected.map((s) => s.benchmark_version))].join(
                ", ",
              ) || "Not selected"}
            </span>
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
            Conditions are ready for review. Configured but unverified systems
            will attempt real inference only after you explicitly confirm Start.
          </p>
        )}
      </section>
      <section className="panel scroll">
        <h2>Evaluation conditions</h2>
        <div className="form-grid">
          {number("repeats", "Repetitions per scenario", 1, 100)}
          <Select
            label="Customer profile"
            value={setup.profile || ""}
            onChange={(v) => update({ profile: v || null })}
            options={[
              ["", "Scenario default"],
              ...profiles.map((p) => [p.id, p.name] as [string, string]),
            ]}
          />
          {number("max_steps", "Maximum actions", 5, 500)}
          {number("timeout", "Timeout (seconds)", 10, 1800)}
        </div>
        <details className="advanced">
          <summary>Advanced settings</summary>
          <div className="form-grid">
            {number("seed", "Random seed", 0, 2147483647)}
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
            <Select
              label="Link execution arm"
              value={setup.agent_mode}
              onChange={(v) => update({ agent_mode: v })}
              options={[
                ["standard", "Standard benchmark"],
                ["agent_with_link", "AI with Link"],
                ["agent_without_link", "AI without Link"],
              ]}
            />
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
