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
  id: string;
  title: string;
  theme: string;
  difficulty: string;
  features: string[];
  method: string;
  app?: string;
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
  id: string;
  model: string;
  scenario: string;
  status: string;
  success: boolean;
  wall_seconds?: number;
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
    [chosen, setChosen] = useState(["T01"]),
    [focus, setFocus] = useState("T01"),
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
    [catalogNote, setCatalogNote] = useState("");
  const config = {
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
    successes = completed.filter((r) => r.success),
    live = state.current;
  const [filter, setFilter] = useState("all");
  const visibleRuns = runs.filter(
    (r) =>
      filter === "all" ||
      (filter === "success"
        ? r.success
        : filter === "blocked"
          ? ["unavailable", "blocked"].includes(r.status)
          : !r.success && ["completed", "failed"].includes(r.status)),
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
            ["Live session", Monitor],
            ["Results", Activity],
          ].map(([label, Icon]) => (
            <button
              key={String(label)}
              className={tab === label ? "active" : ""}
              onClick={() => setTab(String(label))}
            >
              <Icon size={17} />
              {String(label)}
              {label === "Live session" && state.running && (
                <span className="live-dot" />
              )}
              {label === "Scenarios" && <small>18</small>}
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
            CHECKOUTBENCH <span>v1.0</span>
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
                <p>
                  {tab === "Overview"
                    ? "Find the most reliable path from checkout to payment-ready."
                    : tab === "Models"
                      ? "Compare architectures, with capability and reliability first."
                      : tab === "Scenarios"
                        ? "Reproducible checkout conditions. Four stores. Eighteen challenges."
                        : tab === "Live session"
                          ? "Follow every browser action as the run unfolds."
                          : "Objective outcomes, recorded actions, and reproducible exports."}
                </p>
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
          {error && (
            <div className="alert">
              <b>Unable to complete request</b> {error}
              <button onClick={() => setError("")}>
                <X size={14} />
              </button>
            </div>
          )}
          {(tab === "Overview" || tab === "Results") && (
            <div className="stats">
              <Stat
                label="Completed evaluations"
                value={String(completed.length)}
                note={`${runs.filter((r) => ["blocked", "unavailable"].includes(r.status)).length} unavailable / blocked`}
                icon={<FlaskConical />}
              />
              <Stat
                label="Checkout-ready success"
                value={
                  completed.length
                    ? percent(successes.length / completed.length)
                    : "—"
                }
                note="Required fields + payment + stage"
                icon={<Check />}
              />
              <Stat
                label="Test environments"
                value="04"
                note="15 core scenarios + 3 holdouts"
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
          {(tab === "Overview" || tab === "Models" || tab === "Scenarios") && (
            <div className="configuration-grid">
              <section className="card configuration">
                <div className="cardhead">
                  <div>
                    <span className="section-number">01</span>
                    <h2>Configure an experiment</h2>
                  </div>
                  <span className="tag">Sequential execution</span>
                </div>
                <div className="cardbody">
                  <div className="labelrow">
                    <label>Models & architectures</label>
                    <button
                      className="textbutton"
                      onClick={() =>
                        setSelected(
                          models
                            .filter((m) => m.kind === "openrouter")
                            .map((m) => m.id),
                        )
                      }
                    >
                      Select frontier shortlist
                    </button>
                  </div>
                  <div className="model-list">
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
                  <div className="form-divider" />
                  <div className="labelrow">
                    <label>Checkout scenarios</label>
                    <div>
                      <button
                        className="textbutton"
                        onClick={() =>
                          setChosen(
                            scenarios
                              .filter((s) => !s.features.includes("holdout"))
                              .map((s) => s.id),
                          )
                        }
                      >
                        All core
                      </button>
                      <button
                        className="textbutton"
                        onClick={() => setChosen(scenarios.map((s) => s.id))}
                      >
                        Include holdouts
                      </button>
                    </div>
                  </div>
                  <div className="scenario-chips">
                    {scenarios.map((s) => (
                      <button
                        title={s.title}
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
                        {s.id}
                        {chosen.includes(s.id) && <Check size={11} />}
                      </button>
                    ))}
                  </div>
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
                  <div className="launchrow">
                    <div>
                      <b>
                        {selected.length * chosen.length * repeats} evaluations
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
              </section>
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
                    {scenarios.map((s) => (
                      <option value={s.id} key={s.id}>
                        {s.id} — {s.title}
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
                    Complete the synthetic delivery details and prepare{" "}
                    {scenario?.app || scenario?.method.replace("upi_", "UPI ")}.
                    Stop at the simulated authorisation stage.
                  </p>
                  <details>
                    <summary>View the synthetic agent task</summary>
                    <pre>{previewTask}</pre>
                  </details>
                </div>
                <div className="fairness">
                  <ShieldCheck size={18} />
                  <p>
                    <b>Same conditions. Fair comparisons.</b> Every trial starts
                    with a fresh browser, the same 1280 × 900 viewport, profile,
                    and seed.
                  </p>
                </div>
              </section>
            </div>
          )}
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
          {(tab === "Overview" || tab === "Results") && (
            <section className="card leaderboard">
              <div className="cardhead">
                <div>
                  <BarChart3 size={18} />
                  <h2>Performance leaderboard</h2>
                </div>
                <span className="tag">Reliability first</span>
              </div>
              <p className="table-caption">
                Ranked by checkout-ready success, confidence, successful-run
                latency, then actions and cost. Compare rows on matching
                scenarios and settings.
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
                    {board.map((r, i) => (
                      <tr key={r.model + r.reasoning + i}>
                        <td>
                          <b>{displayName(r.model)}</b>
                          <small>
                            {r.kind === "reference"
                              ? "Fixture validation baseline"
                              : r.reasoning + " reasoning"}{" "}
                            · {r.runs} runs · cohort {r.cohort}
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
                {!board.length && (
                  <div className="empty compact">
                    <FlaskConical size={26} />
                    <h3>No benchmark results yet</h3>
                    <p>
                      Start with the reference executor to validate the
                      environments.
                    </p>
                  </div>
                )}
              </div>
            </section>
          )}
          {tab === "Results" && (
            <>
              <section className="card">
                <div className="cardhead">
                  <h2>Success by scenario</h2>
                  <span className="tag">Core + unseen holdouts</span>
                </div>
                <div className="tablewrap">
                  <table className="matrix">
                    <thead>
                      <tr>
                        <th>System</th>
                        {scenarios.map((s) => (
                          <th key={s.id}>{s.id}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {board.map((b, i) => (
                        <tr key={i}>
                          <td>{displayName(b.model)}</td>
                          {scenarios.map((s) => (
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
          <section className="dialog">
            <button className="close" onClick={() => setEstimate(null)}>
              <X size={18} />
            </button>
            <div className="eyebrow">READY TO BENCHMARK</div>
            <h2>{estimate.runs} evaluations, identical conditions.</h2>
            <p>{selected.map(displayName).join(", ")}</p>
            <div className="estimate">
              <span>Estimated inference expenditure</span>
              <b>{money(estimate.estimated_cost)}</b>
            </div>
            <p className="fieldnote">{estimate.assumption}</p>
            {estimate.unknown.length > 0 && (
              <p className="notice">
                Pricing unavailable for {estimate.unknown.join(", ")}. Missing
                models will be recorded as unavailable.
              </p>
            )}
            <p>
              {cap ? `Spending cap: $${cap}` : "No spending cap configured."}{" "}
              Three or more trials are recommended for initial comparisons.
            </p>
            <button
              className="button primary full"
              disabled={loading}
              onClick={launch}
            >
              <Play size={15} />
              Start benchmark
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
