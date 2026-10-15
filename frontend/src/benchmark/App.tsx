import React, { useEffect, useRef, useState } from "react";
import {
  api,
  defaults,
  num,
  type Model,
  type Run,
  type RunnerState,
  type Scenario,
  type Setup,
} from "./domain";
import {
  loadSetup,
  modelName,
  saveSetup,
  systems,
  visibleModel,
  visibleRun,
} from "./policy";
import { Overview, Models, Scenarios, Review } from "./SetupPages";
import { Coverage, Live } from "./ResearchLive";
import Results from "./Results";
import { Empty, Modal } from "./shared";
const pages = {
  overview: [
    "Overview",
    "CheckoutBench",
    "Benchmark specialised AI models on real-world-inspired checkout workflows.",
  ],
  models: [
    "Models",
    "Models",
    "Choose the AI systems you want to benchmark. Some specialise in understanding form fields, others in visual interaction or end-to-end navigation.",
  ],
  scenarios: [
    "Scenarios",
    "Benchmark Coverage",
    "CheckoutBench evaluates each model across a standardised suite of checkout environments. Every model faces the same tasks, allowing us to compare accuracy, speed, payment-method handling, and recovery fairly.",
  ],
  review: [
    "Review & Run",
    "Review & Run",
    "Review your systems and checkout tasks, configure evaluation conditions, and start a reproducible benchmark.",
  ],
  live: [
    "Live Benchmark",
    "Live Benchmark",
    "Watch the selected AI model interact with checkout. Monitor actions, progress and failures as they happen.",
  ],
  results: [
    "Results",
    "Results",
    "Analyse accuracy, speed and reliability across checkout tasks, then inspect the evidence behind each outcome.",
  ],
  coverage: [
    "Coverage & Sources",
    "Coverage & Sources",
    "Explore the checkout environments, scenario coverage, and source references used to design the benchmark.",
  ],
} as const;
type Page = keyof typeof pages;
function route() {
  const [p, id] = location.hash.replace(/^#\/?/, "").split("/");
  return {
    page: (p in pages ? p : "overview") as Page,
    runId: p === "results" && id ? id : undefined,
  };
}
export default function App() {
  const [where, setWhere] = useState(route),
    [setup, setSetup] = useState<Setup>(loadSetup),
    [models, setModels] = useState<Model[]>([]),
    [scenarios, setScenarios] = useState<Scenario[]>([]),
    [release, setRelease] = useState<any>(null),
    [readiness, setReadiness] = useState<any>(null),
    [profiles, setProfiles] = useState<{ id: string; name: string }[]>([]),
    [runs, setRuns] = useState<Run[]>([]),
    [state, setState] = useState<RunnerState>({ running: false }),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [confirm, setConfirm] = useState(false),
    [launching, setLaunching] = useState(false),
    [menu, setMenu] = useState(false),
    [connected, setConnected] = useState(true);
  const lock = useRef(false),
    lastResult = useRef("");
  const navigate = (p: Page, id?: string) => {
    location.hash = "/" + p + (id ? "/" + encodeURIComponent(id) : "");
    setMenu(false);
  };
  useEffect(() => {
    const h = () => {
      setWhere(route());
      setConfirm(false);
    };
    window.addEventListener("hashchange", h);
    return () => window.removeEventListener("hashchange", h);
  }, []);
  useEffect(() => {
    if (!saveSetup(setup))
      setError(
        "Setup could not be saved in browser storage. Keep this page open while preparing the benchmark.",
      );
  }, [setup]);
  const refreshRuns = () =>
    api("/results")
      .then((d) => setRuns((d.runs || []).filter(visibleRun)))
      .catch((e) => setError(e.message));
  useEffect(() => {
    let live = true;
    Promise.all([
      api("/models"),
      api("/scenarios"),
      api("/profiles"),
      api("/results"),
      api("/state"),
      api("/research/release"),
      api("/research/readiness"),
    ])
      .then(([m, s, p, r, st, rel, ready]) => {
        if (!live) return;
        setModels((m.models || []).filter((x: Model) => visibleModel(x.id)));
        setScenarios(
          s.filter((x: Scenario) => rel.scenario_ids.includes(x.id)),
        );
        setProfiles(p);
        setRuns((r.runs || []).filter(visibleRun));
        setState(st);
        setRelease(rel);
        setReadiness(ready);
        setSetup((old) => ({
          ...old,
          scenarios: rel.scenario_ids,
          seed: rel.seed,
          profile: null,
          agent_mode: "standard",
        }));
      })
      .catch((e) => live && setError(e.message))
      .finally(() => live && setLoading(false));
    const source = new EventSource("/api/events");
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);
    source.onmessage = (e) => {
      try {
        const next = JSON.parse(e.data);
        setState(next);
        setConnected(true);
        const marker = [
          next.batch?.id,
          next.batch?.finished,
          next.current?.id,
          next.current?.status,
        ].join("|");
        if (lastResult.current !== marker) {
          lastResult.current = marker;
          refreshRuns();
        }
      } catch {
        setError("Could not read a runner update. Reload to reconnect.");
      }
    };
    return () => {
      live = false;
      source.close();
    };
  }, []);
  const update = (v: Partial<Setup>) => {
    setSetup((s) => ({ ...s, ...v }));
    setConfirm(false);
  };
  const chosen = scenarios.filter((s) => setup.scenarios.includes(s.id));
  const issues: string[] = [];
  if (!setup.models.length)
    issues.push("Select at least one specialist configuration.");
  for (const id of setup.models) {
    const m = models.find((m) => m.id === id);
    if (!m?.available)
      issues.push(
        `${modelName(id)} is unavailable. ${m?.reason || "Configuration metadata is not available."}`,
      );
  }
  if (
    !release ||
    JSON.stringify(setup.scenarios) !== JSON.stringify(release.scenario_ids)
  )
    issues.push("The complete frozen manifest is required.");
  for (const id of setup.models)
    if (!readiness?.checkpoints?.[id]?.verified)
      issues.push(
        `${modelName(id)}: checkpoint hashes and genuine smoke inference must be verified before Run All.`,
      );
  for (const [k, min, max] of [
    ["repeats", 1, 100],
    ["seed", 0, 2147483647],
    ["max_steps", 5, 500],
    ["timeout", 10, 1800],
    ["max_tokens", 256, 131072],
    ["infrastructure_retries", 0, 3],
  ] as const) {
    if (
      !num(setup[k]) ||
      !Number.isInteger(setup[k]) ||
      setup[k] < min ||
      setup[k] > max
    )
      issues.push(
        `${k.replaceAll("_", " ")} must be an integer between ${min} and ${max}.`,
      );
  }
  if (
    setup.spending_cap !== null &&
    (!num(setup.spending_cap) || setup.spending_cap <= 0)
  )
    issues.push("Spending cap must be a positive amount.");
  if (
    setup.spending_cap &&
    setup.models.some((id) =>
      models.find((m) => m.id === id)?.backend?.includes("remote"),
    )
  )
    issues.push(
      "The runner cannot enforce a spending cap on remote specialist endpoints with unreported costs. Configure endpoint-side quotas or use local inference.",
    );
  if (setup.reasoning !== "default")
    issues.push("The selected specialists support default reasoning only.");
  if (state.running)
    issues.push(
      "The runner is busy. Wait for the active batch or use Live Benchmark controls.",
    );
  const start = async () => {
    if (lock.current || issues.length) return;
    lock.current = true;
    setLaunching(true);
    setError("");
    try {
      await api("/batches", {
        ...setup,
        models: setup.models.filter(visibleModel),
        research_release: release.release,
        release_hash: release.release_hash,
      });
      setConfirm(false);
      navigate("live");
      setState(await api("/state"));
    } catch (e) {
      setError(
        `${(e as Error).message}. If the start response was interrupted, inspect Live Benchmark before retrying.`,
      );
    } finally {
      lock.current = false;
      setLaunching(false);
    }
  };
  const { page, runId } = where;
  const step = ["models", "scenarios", "review", "live", "results"].indexOf(
    page,
  );
  return (
    <div className="shell">
      <aside className={menu ? "sidebar open" : "sidebar"}>
        <a className="brand" href="#/overview">
          <span>▱</span> CheckoutBench <small>v3.0</small>
        </a>
        <p className="sidebar-label">AI BENCHMARK WORKSPACE</p>
        <nav aria-label="Main navigation">
          {(
            [
              "overview",
              "models",
              "scenarios",
              "review",
              "live",
              "results",
            ] as Page[]
          ).map((p) => (
            <a
              key={p}
              href={"#/" + p}
              aria-current={page === p ? "page" : undefined}
              onClick={() => setMenu(false)}
            >
              <span>
                {p === "overview"
                  ? "⌂"
                  : String(
                      [
                        "models",
                        "scenarios",
                        "review",
                        "live",
                        "results",
                      ].indexOf(p) + 1,
                    ).padStart(2, "0")}
              </span>
              {pages[p][0]}
              {p === "live" && state.running && <i className="live-dot" />}
            </a>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <a
            href="#/coverage"
            aria-current={page === "coverage" ? "page" : undefined}
            onClick={() => setMenu(false)}
          >
            Coverage & Sources ↗
          </a>
          <small>
            Synthetic profiles
            <br />
            Local checkout simulations
            <br />
            No real payments
          </small>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <button
            className="menu-button"
            aria-label="Toggle navigation"
            aria-expanded={menu}
            onClick={() => setMenu(!menu)}
          >
            ☰
          </button>
          <span>
            Workspace / <b>{pages[page][0]}</b>
          </span>
          <span className="connection">
            {connected ? "● Local runner" : "○ Reconnecting to runner"}
          </span>
        </header>
        <main>
          <header className="page-title">
            <div>
              <span className="eyebrow">
                {page === "overview"
                  ? "CHECKOUT AUTOMATION RESEARCH"
                  : step >= 0
                    ? `STEP ${step + 1} OF 5`
                    : "RESEARCH REFERENCE"}
              </span>
              <h1>{runId ? "Run Details" : pages[page][1]}</h1>
              <p>
                {runId
                  ? "Inspect the recorded outcome, actions, field scores, payment state and performance of one specialist attempt."
                  : pages[page][2]}
              </p>
            </div>
          </header>
          {step >= 0 && (
            <nav className="progress-nav" aria-label="Benchmark progress">
              {(
                ["models", "scenarios", "review", "live", "results"] as Page[]
              ).map((p, i) => (
                <a
                  key={p}
                  href={"#/" + p}
                  aria-current={page === p ? "step" : undefined}
                >
                  <span>{i + 1}</span>
                  {["Models", "Scenarios", "Review", "Run", "Results"][i]}
                </a>
              ))}
            </nav>
          )}
          {error && (
            <div role="alert" className="notice error global-error">
              {error}
              <button aria-label="Dismiss error" onClick={() => setError("")}>
                ×
              </button>
            </div>
          )}
          <div className="page-body">
            {loading ? (
              <Empty title="Loading benchmark workspace…" />
            ) : page === "overview" ? (
              <Overview
                models={models}
                runs={runs}
                scenarios={scenarios}
                start={() => navigate("models")}
              />
            ) : page === "models" ? (
              <Models models={models} setup={setup} update={update} />
            ) : page === "scenarios" ? (
              <Scenarios
                scenarios={scenarios}
                setup={setup}
                update={update}
                releaseName={release?.release || "Active release"}
              />
            ) : page === "review" ? (
              <Review
                models={models}
                scenarios={scenarios}
                profiles={profiles}
                setup={setup}
                update={update}
                issues={issues}
              />
            ) : page === "live" ? (
              <Live
                state={state}
                onResults={() => {
                  refreshRuns();
                  navigate("results");
                }}
                report={setError}
              />
            ) : page === "results" ? (
              <Results
                runs={runs}
                scenarios={scenarios}
                runId={runId}
                onRun={(id) => navigate("results", id)}
                onBack={() => navigate("results")}
                onStart={() => navigate("models")}
              />
            ) : (
              <Coverage scenarios={scenarios} setup={setup} />
            )}
          </div>
          {["models", "scenarios", "review"].includes(page) && (
            <footer className="step-footer">
              <button
                onClick={() =>
                  navigate(
                    page === "models"
                      ? "overview"
                      : page === "scenarios"
                        ? "models"
                        : "scenarios",
                  )
                }
              >
                ← Back
              </button>
              <div>
                <b>
                  {setup.models.length} systems · {setup.scenarios.length}{" "}
                  scenarios
                </b>
                <small>
                  {setup.models.length *
                    setup.scenarios.length *
                    (num(setup.repeats) ? setup.repeats : 0)}{" "}
                  planned evaluations · setup saved in this browser
                </small>
              </div>
              <button
                className="primary"
                disabled={
                  loading ||
                  launching ||
                  (page === "models"
                    ? !setup.models.length
                    : page === "scenarios"
                      ? !setup.scenarios.length || !setup.models.length
                      : !!issues.length)
                }
                onClick={() =>
                  page === "review"
                    ? setConfirm(true)
                    : navigate(page === "models" ? "scenarios" : "review")
                }
              >
                {page === "models"
                  ? "Continue to Scenarios →"
                  : page === "scenarios"
                    ? "Continue to Review →"
                    : "Run All →"}
              </button>
            </footer>
          )}
        </main>
      </div>
      {confirm && (
        <Modal
          title="Confirm benchmark start"
          onClose={() => !launching && setConfirm(false)}
        >
          <div className="modal-body">
            <p>
              <b>
                {setup.models.length * setup.scenarios.length * setup.repeats}{" "}
                evaluations
              </b>{" "}
              using {setup.models.map(modelName).join(", ")}.
            </p>
            <p>
              This starts real model inference using your configured checkpoints
              or endpoints. API or hosting charges may apply; specialist costs
              are not necessarily reported.
            </p>
            <p>
              All checkout and payment interactions remain synthetic. Refreshing
              or navigating never starts another batch automatically.
            </p>
            {issues.length > 0 && (
              <p className="notice error">
                Configuration changed or the runner is busy. Close this dialog
                and review the warnings.
              </p>
            )}
            <div className="toolbar">
              <button disabled={launching} onClick={() => setConfirm(false)}>
                Cancel
              </button>
              <button
                className="primary"
                disabled={launching || !!issues.length}
                onClick={start}
              >
                {launching ? "Starting…" : "Confirm and start"}
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
