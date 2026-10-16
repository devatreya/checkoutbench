import React, { useEffect, useState } from "react";
import {
  api,
  artifact,
  challenge,
  environments,
  familyName,
  human,
  num,
  seconds,
  shown,
  status,
  scenarioPublicId,
  scenarioTitle,
  type Run,
  type RunnerState,
  type Scenario,
  type Setup,
} from "./domain";
import { modelName, visibleModel, visibleRun } from "./policy";
import { Badge, Empty, Select } from "./shared";
import { ScenarioPreview } from "./SetupPages";
export function Live({
  state,
  onResults,
  report,
}: {
  state: RunnerState;
  onResults: () => void;
  report: (s: string) => void;
}) {
  const [now, setNow] = useState(Date.now()),
    [pending, setPending] = useState(false);
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  const safe =
    state.current &&
    visibleRun(state.current) &&
    (!state.batch?.config?.models ||
      state.batch.config.models.every(visibleModel));
  const run = safe ? state.current : undefined;
  const events = run?.events || [],
    last = events.at(-1),
    shot = artifact(run?.screenshot || last?.screenshot);
  const elapsed =
    run?.status === "running" && run.timestamp
      ? Math.max(0, (now - Date.parse(run.timestamp)) / 1000)
      : run?.wall_seconds;
  const control = async (action: string) => {
    setPending(true);
    try {
      await api("/control/" + action, {});
    } catch (e) {
      report((e as Error).message);
    } finally {
      setPending(false);
    }
  };
  if (!run)
    return (
      <section className="panel grow">
        <Empty
          title={
            state.running
              ? "Runner occupied by another session"
              : "No active specialist benchmark"
          }
        >
          {state.running
            ? "A separate backend session is using the runner. Its hidden system details are not shown in this workspace."
            : "Choose models and scenarios, then explicitly confirm the benchmark on Review & Run."}
        </Empty>
        <button onClick={onResults}>View Results →</button>
      </section>
    );
  return (
    <>
      <div className="toolbar">
        <Badge
          tone={run.success ? "good" : run.status === "running" ? "" : "warn"}
        >
          {state.paused ? "Paused" : status(run)}
        </Badge>
        <span>
          {modelName(run.model)} · {scenarioPublicId(run)} ·{" "}
          {scenarioTitle(run)}
        </span>
        <span className="push">
          {state.batch?.finished ?? 0} / {state.batch?.total ?? 1} evaluations
        </span>
        <button
          disabled={!state.running || pending}
          onClick={() => control(state.paused ? "resume" : "pause")}
        >
          {state.paused ? "Resume" : "Pause"}
        </button>
        <button
          disabled={!state.running || pending}
          onClick={() => control("stop")}
        >
          Stop benchmark
        </button>
        {!state.running && (
          <button className="primary" onClick={onResults}>
            View Results →
          </button>
        )}
      </div>
      <progress
        aria-label="Batch progress"
        value={state.batch?.finished ?? 0}
        max={state.batch?.total || 1}
      />
      <div className="live-layout grow">
        <section className="panel browser-panel">
          <div className="panel-title">
            <h2>{familyName(run.environment)}</h2>
            <small>
              Stage: {human(run.completion_stage || last?.action || "Starting")}
            </small>
          </div>
          <div className="browser-view">
            {shot ? (
              <img src={shot} alt="Live checkout browser screenshot" />
            ) : (
              <Empty title="Waiting for browser evidence">
                A screenshot appears when the runner records its first action.
              </Empty>
            )}
          </div>
        </section>
        <section className="panel execution-panel">
          <h2>Execution</h2>
          <div className="live-stats">
            <div>
              Recorded steps
              <b>
                {run.action_count ??
                  events.filter((e) => !["start", "finish"].includes(e.action))
                    .length}
              </b>
            </div>
            <div>
              Elapsed<b>{seconds(elapsed)}</b>
            </div>
            <div>
              Inference time<b>{seconds(run.inference_seconds)}</b>
            </div>
            <div>
              Validation errors<b>{shown(run.validation_errors)}</b>
            </div>
          </div>
          <p>
            <b>Current action:</b> {human(last?.action || "Waiting")}
          </p>
          <div className="scroll action-history">
            {events
              .slice()
              .reverse()
              .map((e, i) => (
                <div key={`${e.index}-${i}`}>
                  <b>{human(e.action)}</b>
                  <small>
                    {seconds(e.elapsed)} ·{" "}
                    {human(
                      e.detail?.selection_source ||
                        e.detail?.grounding_source ||
                        "Source not reported",
                    )}
                  </small>
                  <span>
                    {human(
                      e.detail?.target ||
                        e.detail?.field ||
                        e.detail?.description ||
                        "",
                    )}
                  </span>
                </div>
              ))}
          </div>
          <small>
            Pause takes effect at an action boundary. Stop cancels the active
            run and remaining queue. Authentication is synthetic.
          </small>
        </section>
      </div>
    </>
  );
}
export function Coverage({
  scenarios,
  setup,
}: {
  scenarios: Scenario[];
  setup: Setup;
}) {
  const [family, setFamily] = useState("shopify"),
    [selected, setSelected] = useState(""),
    [search, setSearch] = useState(""),
    [preview, setPreview] = useState(false);
  const rows = scenarios.filter(
    (s) =>
      s.family === family &&
      `${scenarioPublicId(s)} ${scenarioTitle(s)} ${s.description || ""}`
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  const row = rows.find((s) => s.id === selected) || rows[0];
  return (
    <>
      <div className="toolbar">
        <Select
          label="Research environment"
          value={family}
          onChange={setFamily}
          options={environments.map((e) => [e[0], e[1]] as [string, string])}
        />
        <input
          aria-label="Search coverage scenarios"
          placeholder="Search scenario names"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <Badge>{rows.length} simulated scenarios</Badge>
      </div>
      <div className="coverage-layout grow">
        <div className="panel scroll research-list">
          {rows.map((s) => (
            <button
              key={s.id}
              aria-pressed={s.id === row?.id}
              onClick={() => setSelected(s.id)}
            >
              <b>{scenarioPublicId(s)}</b>
              <span>{scenarioTitle(s)}</span>
            </button>
          ))}
          {!rows.length && <Empty title="No matching scenarios" />}
        </div>
        <section className="panel scroll">
          {row ? (
            <>
              <div className="panel-title">
                <h2>
                  {scenarioPublicId(row)} · {scenarioTitle(row)}
                </h2>
                <button onClick={() => setPreview(true)}>
                  Preview checkout
                </button>
              </div>
              <p>{row.description || challenge(row)}</p>
              <div className="facts">
                <div>
                  <dt>Supported payment methods</dt>
                  <dd>
                    {row.supported_payment_methods?.map(human).join(", ") ||
                      human(row.method)}
                  </dd>
                </div>
                <div>
                  <dt>Device</dt>
                  <dd>{human(row.platform)}</dd>
                </div>
                <div>
                  <dt>Difficulty dimensions</dt>
                  <dd>
                    {Object.entries(row.difficulty_config || {})
                      .map(([k, v]) => `${human(k)}: ${human(v)}`)
                      .join(" · ")}
                  </dd>
                </div>
                <div>
                  <dt>Fidelity classification</dt>
                  <dd>
                    {row.provenance?.fidelity_classification || "Not reported"}
                  </dd>
                </div>
                <div>
                  <dt>Source confidence</dt>
                  <dd>{row.provenance?.confidence || "Not reported"}</dd>
                </div>
                <div>
                  <dt>Source type / date</dt>
                  <dd>
                    {row.provenance?.source_type || "Not reported"} ·{" "}
                    {row.provenance?.source_date ||
                      "Publication date not verified"}
                  </dd>
                </div>
                <div>
                  <dt>Last source review</dt>
                  <dd>{row.provenance?.reviewed_at || "Not reported"}</dd>
                </div>
              </div>
              {row.provenance?.source_url && (
                <a
                  className="source-link"
                  href={
                    /^https?:\/\//.test(row.provenance.source_url)
                      ? row.provenance.source_url
                      : undefined
                  }
                  target="_blank"
                  rel="noreferrer"
                >
                  {row.provenance.provider_reference || "Official source"} ↗
                </a>
              )}
              <p className="notice">
                Local simulations reproduce selected documented behaviors and
                informed approximations. They are not authenticated production
                interfaces or official SDK deployments. Historical holdouts are
                regression cases, not a fresh unseen evaluation set.
              </p>
            </>
          ) : (
            <Empty title="Select an environment" />
          )}
        </section>
      </div>
      {preview && row && (
        <ScenarioPreview
          scenario={row}
          setup={setup}
          onClose={() => setPreview(false)}
        />
      )}
    </>
  );
}
