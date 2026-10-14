import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  BarChart3,
  Check,
  ChevronRight,
  CircleHelp,
  Cpu,
  FlaskConical,
  Layers,
  LoaderCircle,
  Monitor,
  Pause,
  Play,
  Plus,
  RefreshCw,
  ShieldCheck,
  Square,
  Terminal,
  X,
} from "lucide-react";
import "./style.css";
import Coverage from "./Coverage";
import Guide, { sectionHelp, WorkspaceHelp } from "./Guide";
type Model = {
  status?: string;
  id: string;
  name: string;
  kind: string;
  backend: string;
  available: boolean;
  reason?: string;
  parameters?: number;
  parameter_count?: number;
  pricing?: Record<string, string>;
  reasoning?: boolean;
  reasoning_levels?: string[];
  vision?: boolean;
  tools?: boolean;
};
type Scenario = {
  benchmark_version?: string;
  family?: string;
  variant?: string;
  id: string;
  title: string;
  theme: string;
  difficulty: string;
  features: string[];
  method: string;
  app?: string;
  expected_outcome?: string;
  seed: number;
};
type Event = {
  index: number;
  elapsed: number;
  action: string;
  detail: Record<string, unknown>;
  screenshot: string;
};
type Run = {
  benchmark_version?: string;
  agent_mode?: string;
  id: string;
  model: string;
  scenario: string;
  status: string;
  success: boolean;
  wall_seconds?: number;
  platform?: string;
  integrity_class?: string;
  evaluation_claim?: string;
  latency_breakdown?: Record<string, number>;
  latency_measurement?: string;
  required_field_accuracy?: number;
  cost: number;
  failure_reason?: string;
  events: Event[];
  screenshot?: string;
  action_count?: number;
  inference_seconds?: number;
  grounding_accuracy?: number;
  field_classification_accuracy?: number;
  videos?: string[];
  cost_kind?: string;
};
type Board = {
  benchmark_version?: string;
  agent_mode?: string;
  duration_stddev: number | null;
  cohort: string;
  holdout_success_rate: number | null;
  recovery_success_rate: number | null;
  model: string;
  reasoning: string;
  runs: number;
  successes: number;
  success_rate: number;
  ci95: number[];
  median_seconds: number | null;
  platform?: string;
  integrity_class?: string;
  field_accuracy: number;
  actions: number;
  cost_per_success: number | null;
  kind: string;
  scenarios: Record<string, { runs: number; successes: number }>;
};
type State = {
  running: boolean;
  paused: boolean;
  batch?: { total: number; finished: number; status: string; spent: number };
  current?: Run;
};
const api = async (path: string, body?: unknown) => {
  const r = await fetch(
    "/api" + path,
    body === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  const data = await r.json();
  if (!r.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail),
    );
  return data;
};
const money = (v?: number | null) =>
    v === null || v === undefined ? "—" : "$" + v.toFixed(4),
  percent = (v?: number) => (v === undefined ? "—" : Math.round(v * 100) + "%");
function App() {
  const [tab, setTab] = useState("Overview"),
    [models, setModels] = useState<Model[]>([]),
    [scenarios, setScenarios] = useState<Scenario[]>([]),
    [selected, setSelected] = useState(["reference"]),
    [chosen, setChosen] = useState(["V21-S01"]),
    [focus, setFocus] = useState("V21-S01"),
    [profile, setProfile] = useState(""),
    [profiles, setProfiles] = useState<{ id: string; name: string }[]>([]),
    [repeats, setRepeats] = useState(3),
    [seed, setSeed] = useState(2026),
    [steps, setSteps] = useState(80),
    [timeout, setTimeoutValue] = useState(180),
    [tokens, setTokens] = useState(8192),
    [reasoning, setReasoning] = useState("default"),
    [cap, setCap] = useState(""),
    [video, setVideo] = useState(false),
    [state, setState] = useState<State>({ running: false, paused: false }),
    [runs, setRuns] = useState<Run[]>([]),
    [board, setBoard] = useState<Board[]>([]),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(false),
    [preview, setPreview] = useState(""),
    [previewTask, setPreviewTask] = useState(""),
    [estimate, setEstimate] = useState<{
      estimated_cost: number;
      assumption: string;
      runs: number;
      unknown: string[];
    } | null>(null),
    [search, setSearch] = useState(""),
    [searchModels, setSearchModels] = useState<Model[]>([]),
    [inspect, setInspect] = useState<Run | null>(null),
    [replay, setReplay] = useState(0),
    [catalogNote, setCatalogNote] = useState(""),
    [boardVersion, setBoardVersion] = useState("2.1"),
    [agentMode, setAgentMode] = useState("standard"),
    [suite, setSuite] = useState("2.1"),
    [environment, setEnvironment] = useState("all"),
    [linkComparisons, setLinkComparisons] = useState<any[]>([]);
  const visibleScenarios = scenarios.filter(
    (s) =>
      (suite === "all" || s.benchmark_version === suite) &&
      (environment === "all" || s.family === environment),
  );
  const config = {
    agent_mode: agentMode,
    models: selected,
    scenarios: chosen,
    profile: profile || null,
    repeats,
    seed,
    max_steps: steps,
    timeout,
    max_tokens: tokens,
    reasoning,
    spending_cap: cap ? Number(cap) : null,
    video,
  };
  const loadResults = () =>
    api("/results")
      .then((d) => {
        setRuns(d.runs);
        setBoard(d.leaderboard);
        setLinkComparisons(d.link_comparisons || []);
      })
      .catch((e) => setError(e.message));
  const loadModels = () =>
    api("/models")
      .then((d) => {
        setModels(d.models);
        setCatalogNote(
          d.catalogue_error ||
            `${d.catalogue_count} exact model IDs in live catalogue · ${d.credentials_configured ? "API key configured" : "No OpenRouter API key configured"}`,
        );
      })
      .catch((e) => setError(e.message));
  useEffect(() => {
    loadModels();
    api("/scenarios").then(setScenarios);
    api("/profiles").then(setProfiles);
    loadResults();
    const source = new EventSource("/api/events");
    source.onmessage = (e) => {
      const next = JSON.parse(e.data);
      setState(next);
      if (next.current?.status !== "running") loadResults();
    };
    return () => source.close();
  }, []);
  useEffect(() => {
    api(
      `/preview/${focus}?seed=${seed}${profile ? "&profile=" + profile : ""}`,
      {},
    )
      .then((d) => {
        setPreview(d.url);
        setPreviewTask(JSON.stringify(d.task, null, 2));
      })
      .catch((e) => setError(e.message));
  }, [focus, seed, profile]);
  useEffect(() => {
    setEstimate(null);
  }, [JSON.stringify(config)]);
  const toggle = (x: string, arr: string[], set: (v: string[]) => void) =>
    set(arr.includes(x) ? arr.filter((v) => v !== x) : [...arr, x]);
  const prepare = async () => {
    setError("");
    setLoading(true);
    try {
      setEstimate(await api("/estimate", config));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };
  const launch = async () => {
    setLoading(true);
    setError("");
    try {
      await api("/batches", config);
      setEstimate(null);
      setTab("Live session");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };
  const control = async (action: string) => {
    try {
      setState(await api("/control/" + action, {}));
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const displayName = (id: string) =>
    models.find((m) => m.id === id)?.name || id;
  const scenario = scenarios.find((s) => s.id === focus),
    completed = runs.filter((r) => ["completed", "failed"].includes(r.status)),
    live = state.current;
  const [filter, setFilter] = useState("all");
  const [resultKind, setResultKind] = useState("all");
  const matchesResult = (r: { model: string; benchmark_version?: string }) =>
    (boardVersion === "all" ||
      (r.benchmark_version || "1.0") === boardVersion) &&
    (resultKind === "all" ||
      (resultKind === "reference"
        ? r.model === "reference"
        : r.model !== "reference"));
  const visibleBoard = board.filter(matchesResult);
  const resultScenarios = scenarios.filter(
    (s) => boardVersion === "all" || s.benchmark_version === boardVersion,
  );
  const referenceRuns = completed.filter((r) => r.model === "reference");
  const modelRuns = completed.filter((r) => r.model !== "reference");
  const setupReference = (full = false) => {
    setSelected(["reference"]);
    setChosen(
      full
        ? scenarios
            .filter((s) => s.benchmark_version === "2.1")
            .map((s) => s.id)
        : ["V21-S01"],
    );
    setFocus("V21-S01");
    setSuite("2.1");
    setEnvironment("all");
    setAgentMode("standard");
    setProfile("");
    setRepeats(1);
    setSeed(2026);
    setSteps(100);
    setTimeoutValue(180);
    setTokens(8192);
    setReasoning("default");
    setCap("");
    setVideo(false);
    setEstimate(null);
    setError("");
    setTab("Scenarios");
  };
  const visibleRuns = runs.filter(
    (r) =>
      matchesResult(r) &&
      (filter === "all" ||
        (filter === "success"
          ? r.success
          : filter === "blocked"
            ? ["unavailable", "blocked"].includes(r.status)
            : !r.success && ["completed", "failed"].includes(r.status))),
  );
  return (
    <div className="app">
      <aside className="sidebar">
        <a className="logo" href="/">
          <span className="logoicon">
            <Layers size={20} />
          </span>
          Checkout<span>Bench</span>
        </a>
        <div className="workspace">
          <span className="avatar">L</span>
          <div>
            Local workspace<small>Research environment</small>
          </div>
          <span className="dot" />
        </div>
        <div className="navlabel">WORKSPACE</div>
        <nav>
          {[
            ["Overview", BarChart3],
            ["Models", Cpu],
            ["Scenarios", Layers],
            ["Coverage", FlaskConical],
            ["Live session", Monitor],
            ["Results", Activity],
          ].map(([label, Icon]) => (
            <button
              key={String(label)}
              aria-current={tab === label ? "page" : undefined}
              title={sectionHelp[String(label)].purpose}
              className={tab === label ? "active" : ""}
              onClick={() => setTab(String(label))}
            >
              <Icon size={17} />
              {String(label)}
              {label === "Live session" && state.running && (
                <span className="live-dot" />
              )}
              {label === "Scenarios" && <small>{scenarios.length}</small>}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="simulation">
            <ShieldCheck size={20} />
            <b>Simulation only</b>
            <p>Synthetic profiles. Local checkouts. No real payments.</p>
          </div>
          <a href="/docs" target="_blank">
            <CircleHelp size={16} /> API documentation <ArrowRight size={14} />
          </a>
          <div className="version">
            CHECKOUTBENCH <span>v2.1</span>
          </div>
        </div>
      </aside>
      <div className="main">
        <header className="topbar">
          <div>
            Workspace <ChevronRight size={13} /> <b>{tab}</b>
          </div>
          <div className="topstatus">
            <span className="dot" />
            Local environment
            <span className="divider" />
            <span className="avatar small">CB</span>
          </div>
        </header>
        <main className="content">
          <div className="pageheading">
            <div className="eyebrow">CHECKOUT AUTOMATION RESEARCH</div>
            <div className="title-row">
              <div>
                <h1>{tab === "Overview" ? "Benchmark lab" : tab}</h1>
                <p>{sectionHelp[tab].purpose}</p>
              </div>
              <div className="actions">
                <a className="button secondary" href="/api/export/json">
                  <ArrowDownToLine size={15} />
                  Export JSON
                </a>
                {tab === "Overview" && (
                  <button
                    onClick={() => setTab("Results")}
                    className="button secondary"
                  >
                    View results
                    <ArrowRight size={15} />
                  </button>
                )}
              </div>
            </div>
          </div>
          <p className="section-help">{sectionHelp[tab].next}</p>
          {tab === "Overview" && (
            <Guide
              navigate={setTab}
              setup={setupReference}
              ready={scenarios.length > 0}
            />
          )}
          {error && (
            <div className="alert">
              <b>Unable to complete request</b> {error}
              <button onClick={() => setError("")}>
                <X size={14} />
              </button>
            </div>
          )}
          {(tab === "Models" || tab === "Scenarios") && (
            <div className="arm-control">
              <label>
                Experimental arm{" "}
                <select
                  aria-label="Experimental arm"
                  value={agentMode}
                  onChange={(e) => setAgentMode(e.target.value)}
                >
                  <option value="standard">Standard benchmark</option>
                  <option value="native_link">
                    A · Native Link only (select reference)
                  </option>
                  <option value="agent_without_link">
                    B · Agent without Link
                  </option>
                  <option value="agent_with_link">C · Agent with Link</option>
                  <option value="paired_link">
                    Paired A / B / C Link comparison
                  </option>
                </select>
              </label>
              <span>
                Link comparisons require Link scenarios. Same profile, seed and
                resource budgets across arms.
              </span>
            </div>
          )}
          {(tab === "Overview" || tab === "Results") && (
            <div className="stats">
              <Stat
                label="Reference checks passed"
                value={`${referenceRuns.filter((r) => r.success).length} / ${referenceRuns.length}`}
                note="Software validation · all saved versions"
                icon={<FlaskConical />}
              />
              <Stat
                label="AI evaluations completed"
                value={String(modelRuns.length)}
                note={
                  modelRuns.length
                    ? `${modelRuns.filter((r) => r.success).length} successful · compare matched cohorts in Results`
                    : "No completed model evaluations yet"
                }
                icon={<Check />}
              />
              <Stat
                label="Test environments"
                value="09"
                note={`${scenarios.length} scenarios · v1 and v2 preserved`}
                icon={<Layers />}
              />
              <Stat
                label="Inference expenditure"
                value={money(runs.reduce((n, r) => n + r.cost, 0))}
                note="Actual or explicitly estimated"
                icon={<Activity />}
              />
            </div>
          )}
          {(tab === "Models" || tab === "Scenarios") && (
            <div
              className={
                "configuration-grid " + (tab === "Models" ? "models-only" : "")
              }
            >
              <section className="card configuration">
                <div className="cardhead">
                  <div>
                    <span className="section-number">
                      {tab === "Models" ? "01" : "02"}
                    </span>
                    <h2>
                      {tab === "Models"
                        ? "Choose systems"
                        : "Choose tasks and run settings"}
                    </h2>
                  </div>
                  <span className="tag">Sequential execution</span>
                </div>
                <div className="cardbody">
                  {tab === "Scenarios" && (
                    <div className="selection-summary">
                      <b>
                        Selected systems:{" "}
                        {selected.map(displayName).join(", ") || "None"}
                      </b>
                      <button
                        className="textbutton"
                        onClick={() => setTab("Models")}
                      >
                        Change systems
                      </button>
                      <p>
                        {selected.length === 1 && selected[0] === "reference"
                          ? "Software validation only · no model inference calls"
                          : "Model decisions and deterministic assistance are attributed separately."}
                      </p>
                    </div>
                  )}
                  <div hidden={tab !== "Models"}>
                    <p className="fieldnote">
                      The deterministic reference is a programmed software
                      check. CUA selects field values; TinyClick locates clicks;
                      the hybrid calls both. MAI-UI and UI-Venus propose visual
                      actions; API agents plan browser actions.
                    </p>
                    <div className="labelrow">
                      <label>Models & architectures</label>
                      <button
                        className="textbutton"
                        onClick={() =>
                          setSelected(
                            models
                              .filter(
                                (m) => m.kind === "openrouter" && m.available,
                              )
                              .map((m) => m.id),
                          )
                        }
                      >
                        Select available frontier models
                      </button>
                    </div>
                    <p className="fieldnote">
                      Scroll the list to see all API models and specialist
                      systems.
                    </p>
                    <div
                      className="model-list"
                      role="group"
                      aria-label="Available systems"
                      tabIndex={0}
                    >
                      {models.map((m) => (
                        <label
                          className={
                            "model-option " +
                            (selected.includes(m.id) ? "selected" : "")
                          }
                          key={m.id}
                        >
                          <input
                            type="checkbox"
                            checked={selected.includes(m.id)}
                            onChange={() => toggle(m.id, selected, setSelected)}
                          />
                          <span className={"model-symbol " + m.kind}>
                            {m.kind === "reference" ? (
                              <Terminal size={17} />
                            ) : m.kind === "specialist" ? (
                              <Cpu size={17} />
                            ) : m.id.startsWith("openai") ? (
                              "◎"
                            ) : (
                              "✳"
                            )}
                          </span>
                          <div>
                            <b>{m.name}</b>
                            {m.kind === "reference" && (
                              <small>
                                Programmed rules · software validation · no AI
                                inference
                              </small>
                            )}
                            {!m.available && m.reason && (
                              <small className="availability-reason">
                                {m.reason}
                              </small>
                            )}
                            <small>
                              {m.backend}
                              {m.parameters || m.parameter_count
                                ? ` · ${((m.parameters || m.parameter_count)! / 1e6).toFixed(2)}M params`
                                : ""}
                            </small>
                            {tab === "Models" && (
                              <small>
                                {m.id} ·{" "}
                                {m.pricing
                                  ? `${money(Number(m.pricing.prompt) * 1e6)}/M input · ${money(Number(m.pricing.completion) * 1e6)}/M output`
                                  : "Pricing: local / unavailable"}{" "}
                                {m.vision ? "· Vision" : ""}{" "}
                                {m.reasoning ? "· Reasoning" : ""}
                              </small>
                            )}
                          </div>
                          <span
                            title={m.reason}
                            className={
                              "availability " + (m.available ? "yes" : "")
                            }
                          >
                            {m.available
                              ? m.status === "configured_unverified"
                                ? "Configured"
                                : "Ready"
                              : "Unavailable"}
                          </span>
                        </label>
                      ))}
                    </div>
                    <p className="fieldnote">
                      {catalogNote}. Unavailable selections are recorded
                      separately, never substituted.
                    </p>
                    <div className="searchrow">
                      <input
                        aria-label="Search exact model catalogue"
                        placeholder="Find another exact model ID…"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                      />
                      <button
                        className="button secondary"
                        onClick={async () => {
                          try {
                            const d = await api(
                              "/models?q=" + encodeURIComponent(search),
                            );
                            setSearchModels(d.search || []);
                          } catch (e) {
                            setError((e as Error).message);
                          }
                        }}
                      >
                        Search
                      </button>
                      <button
                        title="Refresh live catalogue"
                        className="iconbutton"
                        onClick={async () => {
                          setLoading(true);
                          try {
                            await api("/models/refresh", {});
                            await loadModels();
                          } finally {
                            setLoading(false);
                          }
                        }}
                      >
                        <RefreshCw size={16} />
                      </button>
                    </div>
                    {searchModels.length > 0 && (
                      <div className="searchresults">
                        {searchModels.map((m) => (
                          <button
                            key={m.id}
                            onClick={() => {
                              setModels((old) =>
                                old.some((x) => x.id === m.id)
                                  ? old
                                  : [...old, m],
                              );
                              setSelected((old) =>
                                old.includes(m.id) ? old : [...old, m.id],
                              );
                              setSearchModels([]);
                            }}
                          >
                            <Plus size={14} />
                            {m.id}
                          </button>
                        ))}
                      </div>
                    )}
                    <button
                      className="button primary"
                      disabled={!selected.length}
                      onClick={() => setTab("Scenarios")}
                    >
                      Next: choose scenarios →
                    </button>
                  </div>
                  <div hidden={tab !== "Scenarios"}>
                    <div className="labelrow">
                      <label>Checkout scenarios</label>
                      <div>
                        <button
                          className="textbutton"
                          onClick={() =>
                            setChosen(
                              visibleScenarios
                                .filter((s) => !s.features.includes("holdout"))
                                .map((s) => s.id),
                            )
                          }
                        >
                          All core
                        </button>
                        <button
                          className="textbutton"
                          onClick={() =>
                            setChosen(visibleScenarios.map((s) => s.id))
                          }
                        >
                          Select all shown
                        </button>
                        <button
                          className="textbutton"
                          onClick={() => setChosen([])}
                        >
                          Clear selection
                        </button>
                      </div>
                    </div>
                    <div className="formrow">
                      <label>
                        Benchmark suite
                        <select
                          value={suite}
                          onChange={(e) => setSuite(e.target.value)}
                        >
                          <option value="1.0">v1.0 · preserved suite</option>
                          <option value="2.1">
                            v2.1 · isolated customer intent
                          </option>
                          <option value="2.0">
                            v2.0 · historical, non-comparable
                          </option>
                          <option value="all">All · version labelled</option>
                        </select>
                      </label>
                      <label>
                        Environment
                        <select
                          value={environment}
                          onChange={(e) => setEnvironment(e.target.value)}
                        >
                          <option value="all">All environments</option>
                          {[...new Set(scenarios.map((s) => s.family))].map(
                            (f) => (
                              <option key={f}>{f}</option>
                            ),
                          )}
                        </select>
                      </label>
                    </div>
                    <div
                      className="scenario-chips"
                      role="group"
                      aria-label="Scenario selection"
                      tabIndex={0}
                    >
                      {visibleScenarios.map((s) => (
                        <button
                          title={`v${s.benchmark_version} · ${s.family} · ${s.title}`}
                          key={s.id}
                          className={
                            (chosen.includes(s.id) ? "selected " : "") +
                            (s.features.includes("holdout") ? "holdout" : "")
                          }
                          onClick={() => {
                            toggle(s.id, chosen, setChosen);
                            setFocus(s.id);
                          }}
                        >
                          <span>
                            <b>{s.id}</b> · {s.title}
                          </span>
                          {chosen.includes(s.id) && <Check size={11} />}
                        </button>
                      ))}
                    </div>
                    <p className="fieldnote">
                      Scroll to browse all tasks. {chosen.length} selected ·{" "}
                      {
                        chosen.filter(
                          (id) => !visibleScenarios.some((s) => s.id === id),
                        ).length
                      }{" "}
                      outside the current filters. Filters do not change your
                      selection. Each trial starts with a fresh browser.
                    </p>
                    <div className="formrow">
                      <label>
                        Synthetic customer
                        <select
                          value={profile}
                          onChange={(e) => setProfile(e.target.value)}
                        >
                          <option value="">Scenario default profile</option>
                          {profiles.map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.name}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Trials per scenario
                        <input
                          aria-label="Trials per scenario"
                          type="number"
                          min="1"
                          max="100"
                          value={repeats}
                          onChange={(e) => setRepeats(+e.target.value)}
                        />
                      </label>
                    </div>
                    <details>
                      <summary>
                        Advanced experiment settings <Plus size={14} />
                      </summary>
                      <div className="formrow">
                        <label>
                          Scenario seed
                          <input
                            type="number"
                            value={seed}
                            onChange={(e) => setSeed(+e.target.value)}
                          />
                        </label>
                        <label>
                          Maximum actions
                          <input
                            type="number"
                            value={steps}
                            onChange={(e) => setSteps(+e.target.value)}
                          />
                        </label>
                        <label>
                          Timeout / seconds
                          <input
                            type="number"
                            value={timeout}
                            onChange={(e) => setTimeoutValue(+e.target.value)}
                          />
                        </label>
                        <label>
                          Output token budget
                          <input
                            type="number"
                            value={tokens}
                            onChange={(e) => setTokens(+e.target.value)}
                          />
                        </label>
                        <label>
                          Reasoning effort
                          <select
                            value={reasoning}
                            onChange={(e) => setReasoning(e.target.value)}
                          >
                            {[
                              "default",
                              "none",
                              "minimal",
                              "low",
                              "medium",
                              "high",
                              "xhigh",
                              "max",
                            ].map((r) => (
                              <option key={r}>{r}</option>
                            ))}
                          </select>
                        </label>
                        <label>
                          Batch spending cap / USD
                          <input
                            placeholder="No cap"
                            value={cap}
                            onChange={(e) => setCap(e.target.value)}
                            type="number"
                            step="0.01"
                            min="0.01"
                          />
                        </label>
                      </div>
                      <p className="fieldnote">
                        Reasoning is passed only when advertised.
                        Provider-rejected effort levels are reported; they are
                        never silently lowered.
                      </p>
                      <label className="checkboxline">
                        <input
                          type="checkbox"
                          checked={video}
                          onChange={(e) => setVideo(e.target.checked)}
                        />
                        Record browser video
                      </label>
                    </details>
                    <button
                      className="textbutton"
                      onClick={() => setupReference(false)}
                    >
                      Reset setup to one software check
                    </button>
                    <div className="launchrow">
                      <div>
                        <b>
                          {(agentMode === "paired_link"
                            ? 1 + 2 * selected.length
                            : selected.length) *
                            chosen.length *
                            repeats}{" "}
                          evaluations
                        </b>
                        <small>
                          {selected.length} models · {chosen.length} scenarios ·{" "}
                          {repeats} trials
                        </small>
                      </div>
                      <button
                        className="button primary"
                        disabled={
                          loading ||
                          state.running ||
                          !selected.length ||
                          !chosen.length
                        }
                        onClick={prepare}
                      >
                        {loading ? (
                          <LoaderCircle className="spin" size={16} />
                        ) : (
                          <Play size={15} />
                        )}
                        Review & run
                      </button>
                    </div>
                  </div>
                </div>
              </section>
              {tab === "Scenarios" && (
                <section className="card previewcard">
                  <div className="cardhead">
                    <div>
                      <span className="section-number">02</span>
                      <h2>Scenario preview</h2>
                    </div>
                    <button
                      className="iconbutton"
                      title="Reset scenario preview"
                      onClick={() =>
                        api(
                          `/preview/${focus}?seed=${seed}${profile ? "&profile=" + profile : ""}`,
                          {},
                        ).then((d) => {
                          setPreview(d.url);
                          setPreviewTask(JSON.stringify(d.task, null, 2));
                        })
                      }
                    >
                      <RefreshCw size={15} />
                    </button>
                  </div>
                  <div className="preview-intro">
                    <select
                      aria-label="Preview scenario"
                      value={focus}
                      onChange={(e) => setFocus(e.target.value)}
                    >
                      {resultScenarios.map((s) => (
                        <option value={s.id} key={s.id}>
                          v{s.benchmark_version} · {s.id} — {s.title}
                        </option>
                      ))}
                    </select>
                    <div className="tags">
                      <span className={"tag theme-" + scenario?.theme}>
                        {scenario?.theme === "razor"
                          ? "Razorpay"
                          : scenario?.theme === "cashfree"
                            ? "Cashfree"
                            : scenario?.theme === "stripe"
                              ? "Stripe"
                              : "Indian commerce"}{" "}
                        inspired
                      </span>
                      <span className="tag">{scenario?.difficulty}</span>
                      <span className="tag">Seed {seed}</span>
                    </div>
                  </div>
                  <div className="browserchrome">
                    <span />
                    <span />
                    <span />
                    <small>localhost · isolated checkout</small>
                    <ShieldCheck size={12} />
                  </div>
                  <div className="preview-window">
                    {preview ? (
                      <iframe
                        title="Interactive checkout preview"
                        src={preview}
                      />
                    ) : (
                      <div className="empty">Loading preview…</div>
                    )}
                  </div>
                  <div className="previewfooter">
                    <div>
                      <span className="dot" />
                      Fully local, interactive preview
                    </div>
                    <a href={preview} target="_blank">
                      Open checkout <ArrowRight size={13} />
                    </a>
                  </div>
                  <div className="objective">
                    <h3>Task objective</h3>
                    <p>
                      {scenario?.title}. Expected endpoint:{" "}
                      {scenario?.expected_outcome ||
                        "authorisation preparation"}
                      . This practice preview is separate from scored runs.
                    </p>
                    <details>
                      <summary>View the synthetic agent task</summary>
                      <pre>{previewTask}</pre>
                    </details>
                  </div>
                  <div className="fairness">
                    <ShieldCheck size={18} />
                    <p>
                      <b>Same conditions. Fair comparisons.</b> Every trial
                      starts with a fresh browser and the scenario’s fixed
                      viewport, profile, and seed.
                    </p>
                  </div>
                </section>
              )}
            </div>
          )}
          {tab === "Scenarios" && <WorkspaceHelp />}
          {tab === "Coverage" && <Coverage />}
          {(tab === "Live session" ||
            (tab === "Overview" && state.running)) && (
            <section className="card">
              <div className="cardhead">
                <div>
                  <span className={state.running ? "live-dot" : "dot"} />
                  <h2>
                    {live
                      ? `${displayName(live.model)} · ${live.scenario}`
                      : "Live execution"}
                  </h2>
                </div>
                <div className="actions">
                  <span className="tag">
                    {state.batch
                      ? `${state.batch.finished} / ${state.batch.total}`
                      : "No active batch"}
                  </span>
                  <button
                    className="button secondary"
                    disabled={!state.running}
                    onClick={() => control(state.paused ? "resume" : "pause")}
                  >
                    {state.paused ? <Play size={14} /> : <Pause size={14} />}{" "}
                    {state.paused ? "Resume" : "Pause"}
                  </button>
                  <button
                    className="button secondary"
                    disabled={!state.running}
                    onClick={() => control("stop")}
                  >
                    <Square size={13} />
                    Stop
                  </button>
                </div>
              </div>
              <div className="livegrid">
                <div className="liveimage">
                  {live?.screenshot ? (
                    <img
                      src={live.screenshot}
                      alt="Latest benchmark browser screenshot"
                    />
                  ) : (
                    <div className="empty">
                      <Monitor size={40} />
                      <h3>Your browser session will appear here</h3>
                      <p>
                        Configure an experiment and start the reference executor
                        or an available model.
                      </p>
                      <button
                        className="button primary"
                        onClick={() => setTab("Overview")}
                      >
                        Configure experiment <ArrowRight size={14} />
                      </button>
                    </div>
                  )}
                </div>
                <div className="timeline">
                  <div className="labelrow">
                    <label>Action stream</label>
                    <span className="tag">
                      {live?.events.length || 0} events
                    </span>
                  </div>
                  {live?.events.map((e) => (
                    <div className="event" key={e.index}>
                      <span className="eventnumber">{e.index + 1}</span>
                      <div>
                        <b>{e.action.replaceAll("_", " ")}</b>
                        <small>
                          {String(
                            e.detail.field ||
                              e.detail.target ||
                              e.detail.reason ||
                              "Browser state captured",
                          )}
                        </small>
                      </div>
                      <time>{e.elapsed.toFixed(1)}s</time>
                    </div>
                  ))}
                  {live?.failure_reason && (
                    <div className="failure">{live.failure_reason}</div>
                  )}
                  <div className="sessionstatus">
                    {state.paused
                      ? "Paused between actions"
                      : state.running
                        ? "Running sequentially"
                        : live?.status || "Idle"}{" "}
                    · Batch spend {money(state.batch?.spent)}
                  </div>
                </div>
              </div>
            </section>
          )}
          {tab === "Results" && (
            <section className="card leaderboard">
              <div className="cardhead">
                <div>
                  <BarChart3 size={18} />
                  <h2>Saved results by system</h2>
                </div>
                <div className="leaderboard-controls">
                  <label>
                    Suite{" "}
                    <select
                      aria-label="Leaderboard version"
                      value={boardVersion}
                      onChange={(e) => setBoardVersion(e.target.value)}
                    >
                      <option value="all">Combined · versions labelled</option>
                      <option value="1.0">v1.0 · historical</option>
                      <option value="2.1">
                        v2.1 · isolated customer intent
                      </option>
                      <option value="2.0">v2.0</option>
                    </select>
                  </label>
                  <label>
                    Result type{" "}
                    <select
                      aria-label="Result type"
                      value={resultKind}
                      onChange={(e) => setResultKind(e.target.value)}
                    >
                      <option value="all">All systems, labelled</option>
                      <option value="reference">Reference checks only</option>
                      <option value="models">AI systems only</option>
                    </select>
                  </label>
                </div>
              </div>
              <p className="table-caption">
                These filters apply to the system table, scenario matrix and run
                history below. Saved runs aggregate by matching configuration;
                compare the same scenarios and budgets. Reference results
                validate fixtures and are not AI capability scores.
              </p>
              <div className="tablewrap">
                <table>
                  <thead>
                    <tr>
                      <th>MODEL / SYSTEM</th>
                      <th>SUCCESS RATE</th>
                      <th>95% INTERVAL</th>
                      <th>MEDIAN TIME</th>
                      <th>FIELD ACCURACY</th>
                      <th>COST / SUCCESS</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleBoard.map((r, i) => (
                      <tr key={r.model + r.reasoning + i}>
                        <td>
                          <b>{displayName(r.model)}</b>
                          <small>
                            v{r.benchmark_version || "1.0"} ·{" "}
                            {r.agent_mode || "standard"}
                          </small>
                          <small>
                            {r.kind === "reference"
                              ? "Fixture validation baseline"
                              : r.reasoning + " reasoning"}{" "}
                            · {r.runs} runs ·{" "}
                            {r.platform || "legacy unspecified"} ·{" "}
                            {r.integrity_class || "historical, non-comparable"}{" "}
                            · cohort {r.cohort}
                          </small>
                        </td>
                        <td>
                          <div className="rate">
                            <b>{percent(r.success_rate)}</b>
                            <div>
                              <i style={{ width: percent(r.success_rate) }} />
                            </div>
                          </div>
                        </td>
                        <td>
                          {percent(r.ci95[0])}–{percent(r.ci95[1])}
                        </td>
                        <td>
                          {r.median_seconds === null
                            ? "—"
                            : r.median_seconds.toFixed(1) + "s"}
                        </td>
                        <td>{percent(r.field_accuracy)}</td>
                        <td>{money(r.cost_per_success)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!visibleBoard.length && (
                  <div className="empty compact">
                    <FlaskConical size={26} />
                    <h3>No results match these filters</h3>
                    <p>
                      Choose Reference checks to see software validation, or run
                      a configured model to collect AI results.
                    </p>
                  </div>
                )}
              </div>
            </section>
          )}
          {tab === "Results" && (
            <section className="card">
              <div className="cardhead">
                <h2>Native Link versus agent autofill</h2>
              </div>
              <p className="table-caption">
                Only equivalent scenario, profile, seed, viewport and budgets
                are paired. Native autofill is credited separately. Reference
                comparisons validate plumbing, not AI performance.
              </p>
              <div className="tablewrap">
                <table>
                  <thead>
                    <tr>
                      <th>Scenario</th>
                      <th>System</th>
                      <th>Pairing</th>
                      <th>Success gain over native</th>
                      <th>User interactions saved</th>
                    </tr>
                  </thead>
                  <tbody>
                    {linkComparisons.map((x, i) => (
                      <tr key={i}>
                        <td>{x.scenario}</td>
                        <td>{displayName(x.model)}</td>
                        <td>{x.paired ? "Complete A/B/C" : "Missing arm"}</td>
                        <td>{x.incremental_success ?? "—"}</td>
                        <td>{x.user_interactions_saved ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!linkComparisons.length && (
                  <p className="table-caption">
                    Run the three Link arms from the experiment selector to
                    populate paired results.
                  </p>
                )}
              </div>
            </section>
          )}
          {tab === "Results" && (
            <>
              <section className="card">
                <div className="cardhead">
                  <h2>Success by scenario</h2>
                  <span className="tag">
                    Core + labelled regression holdouts
                  </span>
                </div>
                <div className="tablewrap">
                  <table className="matrix">
                    <thead>
                      <tr>
                        <th>System</th>
                        {resultScenarios.map((s) => (
                          <th key={s.id}>{s.id}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {visibleBoard.map((b, i) => (
                        <tr key={i}>
                          <td>{displayName(b.model)}</td>
                          {resultScenarios.map((s) => (
                            <td key={s.id}>
                              <span
                                className={
                                  b.scenarios[s.id]
                                    ? b.scenarios[s.id].successes ===
                                      b.scenarios[s.id].runs
                                      ? "cellpass"
                                      : "cellfail"
                                    : "cellnone"
                                }
                                title={
                                  b.scenarios[s.id]
                                    ? `${b.scenarios[s.id].successes}/${b.scenarios[s.id].runs}`
                                    : "Not evaluated"
                                }
                              >
                                {b.scenarios[s.id]
                                  ? percent(
                                      b.scenarios[s.id].successes /
                                        b.scenarios[s.id].runs,
                                    )
                                  : "—"}
                              </span>
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
              <section className="card">
                <div className="cardhead">
                  <h2>Evaluation history</h2>
                  <div className="actions">
                    <select
                      aria-label="Filter run status"
                      value={filter}
                      onChange={(e) => setFilter(e.target.value)}
                    >
                      <option value="all">All runs</option>
                      <option value="success">Successful</option>
                      <option value="failure">Failed</option>
                      <option value="blocked">Unavailable / blocked</option>
                    </select>
                    <a className="button secondary" href="/api/export/csv">
                      <ArrowDownToLine size={14} />
                      CSV
                    </a>
                  </div>
                </div>
                <div className="tablewrap">
                  <table>
                    <thead>
                      <tr>
                        <th>MODEL</th>
                        <th>SCENARIO</th>
                        <th>OUTCOME</th>
                        <th>TIME</th>
                        <th>ACTIONS</th>
                        <th>COST</th>
                        <th>REPLAY</th>
                      </tr>
                    </thead>
                    <tbody>
                      {visibleRuns.map((r) => (
                        <tr key={r.id}>
                          <td>
                            <b>{displayName(r.model)}</b>
                            <small>
                              v{r.benchmark_version || "1.0"} ·{" "}
                              {r.agent_mode || "standard"}
                            </small>
                            <small>{r.id.slice(0, 8)}</small>
                          </td>
                          <td>{r.scenario}</td>
                          <td>
                            <span
                              className={
                                "outcome " +
                                (r.success
                                  ? "pass"
                                  : r.status === "unavailable" ||
                                      r.status === "blocked"
                                    ? "neutral"
                                    : "fail")
                              }
                            >
                              {r.success ? "Success" : r.status}
                            </span>
                            <small>{r.failure_reason}</small>
                          </td>
                          <td>{r.wall_seconds?.toFixed(1)}s</td>
                          <td>{r.action_count ?? "—"}</td>
                          <td>
                            {money(
                              r.cost_kind === "not_reported" ? null : r.cost,
                            )}
                            <small>{r.cost_kind}</small>
                          </td>
                          <td>
                            <button
                              className="textbutton"
                              onClick={() => {
                                setInspect(r);
                                setReplay(0);
                              }}
                            >
                              Inspect <ArrowRight size={13} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </>
          )}
          <footer className="footer">
            <span>
              <ShieldCheck size={13} />
              Synthetic data · Simulated payments · No provider affiliation
            </span>
            <span>Built for capability. Measured for reliability.</span>
          </footer>
        </main>
      </div>
      {estimate && (
        <div className="overlay">
          <section
            className="dialog"
            role="dialog"
            aria-modal="true"
            aria-label="Review batch"
          >
            <button
              className="close"
              aria-label="Cancel"
              onClick={() => setEstimate(null)}
            >
              <X size={18} />
            </button>
            <div className="eyebrow">REVIEW BEFORE STARTING</div>
            <h2>
              {estimate.runs}{" "}
              {estimate.runs === 1 ? "evaluation" : "evaluations"}, identical
              conditions.
            </h2>
            <p>{selected.map(displayName).join(", ")}</p>
            <div className="estimate">
              <span>Estimated inference expenditure</span>
              <b>{money(estimate.estimated_cost)}</b>
            </div>
            <p className="fieldnote">
              {selected.every((id) => id === "reference")
                ? "Software validation only. Programmed rules drive the browser; no model inference is requested. A pass is not an AI score."
                : estimate.assumption}
            </p>
            {estimate.unknown.length > 0 && (
              <p className="notice">
                Pricing unavailable for {estimate.unknown.join(", ")}. Missing
                models will be recorded as unavailable.
              </p>
            )}
            <p>
              {selected.every((id) => id === "reference")
                ? "One trial per scenario is a useful software check. Each trial gets a fresh browser and checkout session."
                : `${cap ? `Spending cap: $${cap}.` : "No spending cap configured."} Three or more trials are recommended for initial model comparisons.`}
            </p>
            <button
              className="button primary full"
              disabled={loading}
              onClick={launch}
            >
              <Play size={15} />
              {selected.every((id) => id === "reference")
                ? "Start software check"
                : "Start benchmark"}
            </button>
          </section>
        </div>
      )}
      {inspect && (
        <div className="overlay">
          <section className="dialog replay">
            <button className="close" onClick={() => setInspect(null)}>
              <X size={18} />
            </button>
            <h2>
              {displayName(inspect.model)} · {inspect.scenario}
            </h2>
            <p>
              {inspect.success
                ? "Checkout-ready success"
                : inspect.failure_reason || inspect.status}{" "}
              · Field accuracy {percent(inspect.required_field_accuracy)} ·
              Grounding {percent(inspect.grounding_accuracy)} · Field
              classification {percent(inspect.field_classification_accuracy)}
            </p>
            <p>
              {inspect.evaluation_claim} · {inspect.platform} ·{" "}
              {inspect.integrity_class}
            </p>
            {inspect.latency_breakdown && (
              <details>
                <summary>Measured latency breakdown</summary>
                <p>{inspect.latency_measurement}</p>
                <pre>{JSON.stringify(inspect.latency_breakdown, null, 2)}</pre>
              </details>
            )}
            {inspect.events.length > 0 ? (
              <>
                <img
                  src={inspect.events[replay]?.screenshot}
                  alt={`Action ${replay + 1} screenshot`}
                />
                <input
                  aria-label="Replay action"
                  type="range"
                  min={0}
                  max={inspect.events.length - 1}
                  value={replay}
                  onChange={(e) => setReplay(+e.target.value)}
                />
                <pre>{JSON.stringify(inspect.events[replay], null, 2)}</pre>
              </>
            ) : (
              <p>No browser actions were performed.</p>
            )}
            {inspect.videos?.map((v) => (
              <video key={v} src={v} controls />
            ))}
            <a
              className="button secondary"
              href={"/api/results/" + inspect.id}
              target="_blank"
            >
              Full run JSON <ArrowRight size={14} />
            </a>
          </section>
        </div>
      )}
    </div>
  );
}
function Stat({
  label,
  value,
  note,
  icon,
}: {
  label: string;
  value: string;
  note: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="stat">
      <div>
        <span>{label}</span>
        {icon}
      </div>
      <strong>{value}</strong>
      <small>{note}</small>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
