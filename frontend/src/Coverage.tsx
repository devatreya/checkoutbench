import React, { useEffect, useState } from "react";

type Row = {
  id: string;
  title: string;
  family: string;
  variant: string;
  benchmark_version: string;
  features: string[];
  method: string;
  difficulty_config?: Record<string, unknown>;
  success_conditions: string[];
  reference_status: string;
  native_autofill?: boolean;
  link_eligible?: boolean;
  auth_surface?: string;
  authentication_method?: string;
  qr?: string;
  merchant?: string;
  agent_modes?: string[];
  expected_outcome?: string;
  platform?: string;
  supported_payment_methods?: string[];
  integrity_class?: string;
  provenance?: {
    provider_reference: string;
    source_url: string;
    source_type: string;
    source_date: string | null;
    confidence: string;
    reviewed_at: string;
    fidelity_classification: string;
  };
  viewport?: { width: number; height: number };
};
const call = async (path: string, body?: unknown) => {
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
  const d = await r.json();
  if (!r.ok)
    throw Error(
      typeof d.detail === "string" ? d.detail : JSON.stringify(d.detail),
    );
  return d;
};
export default function Coverage() {
  const [data, setData] = useState<{
      scenarios: Row[];
      families: string[];
      variants: number;
      matrix: any[];
    } | null>(null),
    [id, setId] = useState("V21-S01"),
    [family, setFamily] = useState("all"),
    [version, setVersion] = useState("2.1"),
    [seed, setSeed] = useState(2026),
    [preview, setPreview] = useState<any>(null),
    [message, setMessage] = useState(""),
    [mobile, setMobile] = useState(false),
    [arm, setArm] = useState("standard");
  const load = () =>
    call("/coverage")
      .then(setData)
      .catch((e) => setMessage(e.message));
  const reset = () =>
    call(`/preview/${id}?seed=${seed}&agent_mode=${arm}`, {})
      .then(setPreview)
      .catch((e) => setMessage(e.message));
  useEffect(() => {
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, []);
  useEffect(() => {
    reset();
  }, [id, seed, arm]);
  const row = data?.scenarios.find((s) => s.id === id);
  const run = () =>
    call("/batches", {
      models: ["reference"],
      scenarios: [id],
      seed,
      repeats: 1,
      max_steps: 150,
      timeout: 180,
      agent_mode: arm,
    })
      .then(() =>
        setMessage(
          "Reference running. Follow screenshots in Live session; coverage updates on completion.",
        ),
      )
      .catch((e) => setMessage(e.message));
  return (
    <div className="coverage-page">
      <section className="card">
        <div className="cardhead">
          <h2>Scenario coverage</h2>
          <span className="tag">
            {data?.families.length || 0} families · {data?.variants || 0}{" "}
            variants
          </span>
        </div>
        <p className="table-caption">
          All-version inventory for benchmark authors. The filters below apply
          to the scenario list. Expected criteria and fault configurations are
          never sent to the agent browser. Unverified rows need reference
          validation.
        </p>
        <div className="tablewrap">
          <table>
            <thead>
              <tr>
                <th>FAMILY</th>
                <th>VARIANTS</th>
                <th>CORE</th>
                <th>HOLDOUT</th>
                <th>PAYMENTS</th>
                <th>VALIDATION GAP</th>
              </tr>
            </thead>
            <tbody>
              {data?.matrix.map((m) => (
                <tr key={m.family}>
                  <td>
                    <b>{m.family}</b>
                  </td>
                  <td>{m.variants.length}</td>
                  <td>{m.core}</td>
                  <td>{m.holdouts}</td>
                  <td>{m.payments.join(", ")}</td>
                  <td>
                    {m.unverified
                      ? `${m.unverified} need validation`
                      : "All reference paths passed"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <div className="coverage-workbench">
        <section className="card">
          <div className="coverage-filters">
            <label>
              Version
              <select
                value={version}
                onChange={(e) => setVersion(e.target.value)}
              >
                <option value="2.1">v2.1</option>
                <option value="2.0">v2.0</option>
                <option value="1.0">v1.0</option>
                <option value="all">All, labelled</option>
              </select>
            </label>
            <label>
              Environment
              <select
                value={family}
                onChange={(e) => setFamily(e.target.value)}
              >
                <option value="all">All families</option>
                {data?.families.map((f) => (
                  <option key={f}>{f}</option>
                ))}
              </select>
            </label>
          </div>
          <div className="coverage-list">
            {data?.scenarios
              .filter(
                (s) =>
                  (version === "all" || s.benchmark_version === version) &&
                  (family === "all" || s.family === family),
              )
              .map((s) => (
                <button
                  className={id === s.id ? "active" : ""}
                  key={s.id}
                  onClick={() => setId(s.id)}
                >
                  <span>
                    <b>{s.id}</b>
                    <small>
                      v{s.benchmark_version} ·{" "}
                      {s.features.includes("holdout") ? "Holdout" : "Core"}
                    </small>
                  </span>
                  <strong>{s.title}</strong>
                  <small>
                    {s.family} / {s.variant} · {s.reference_status}
                  </small>
                </button>
              ))}
          </div>
        </section>
        <section className="card coverage-detail">
          <div className="cardhead">
            <h2>
              {row?.id} · {row?.title}
            </h2>
          </div>
          <div className="coverage-tools">
            <label>
              Seed
              <input
                type="number"
                value={seed}
                onChange={(e) => setSeed(Number(e.target.value))}
              />
            </label>
            <label>
              Experimental arm
              <select value={arm} onChange={(e) => setArm(e.target.value)}>
                <option value="standard">Standard</option>
                {row?.family === "link" && (
                  <>
                    <option value="native_link">
                      A · Native Link test user
                    </option>
                    <option value="agent_without_link">
                      B · Agent without Link
                    </option>
                    <option value="agent_with_link">C · Agent with Link</option>
                  </>
                )}
              </select>
            </label>
            <button
              className="button secondary"
              onClick={() => setMobile(!mobile)}
            >
              {mobile ? "Desktop" : "Mobile"} preview
            </button>
            <button className="button secondary" onClick={reset}>
              Reset preview
            </button>
            <button className="button primary" onClick={run}>
              Validate this scenario
            </button>
          </div>
          {message && (
            <p role="status" className="coverage-message">
              {message}
            </p>
          )}
          <div className="coverage-tags">
            <span className="tag">{row?.method}</span>
            <span className="tag">
              Autofill {row?.native_autofill ? "available" : "off"}
            </span>
            <span className="tag">
              Link {row?.link_eligible ? "eligible" : "off"}
            </span>
            <span className="tag">
              Auth{" "}
              {row?.authentication_method || row?.auth_surface || "v1 handoff"}
            </span>
            {row?.qr && <span className="tag">{row.qr}</span>}
          </div>
          <div className="coverage-preview">
            <iframe
              key={preview?.url}
              title="Scenario author preview"
              src={preview?.url}
              style={{
                width: mobile ? 390 : "100%",
                maxWidth: "100%",
                height: 844,
              }}
            />
          </div>
          <div className="coverage-tools">
            <a href={preview?.url} target="_blank" rel="noreferrer">
              Open checkout separately ↗
            </a>
            <button
              className="button secondary"
              onClick={() =>
                preview &&
                call("/test-user/" + preview.token, {})
                  .then(() =>
                    setMessage(
                      "Test-user approval processed. Return to the checkout challenge.",
                    ),
                  )
                  .catch((e) => setMessage(e.message))
              }
            >
              Provide requested test-user approval
            </button>
          </div>
          <details className="coverage-doc" open>
            <summary>Source fidelity and task</summary>
            <p>
              {row?.platform || "Legacy platform unspecified"} ·{" "}
              {row?.integrity_class}
            </p>
            {row?.provenance && (
              <p>
                <a
                  href={row.provenance.source_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  {row.provenance.provider_reference}
                </a>
                <br />
                {row.provenance.source_type} ·{" "}
                {row.provenance.fidelity_classification}
                <br />
                Source date:{" "}
                {row.provenance.source_date || "Not published / not verified"} ·
                reviewed {row.provenance.reviewed_at}
                <br />
                Confidence: {row.provenance.confidence}
              </p>
            )}
            <p>
              Device-supported payment methods:{" "}
              {row?.supported_payment_methods?.join(", ") ||
                "Historical configuration"}
            </p>
            <p>
              Reference passes verify fixture solvability. They are not evidence
              of AI performance. v1/v2 and v2.1 results are not comparable.
            </p>
            <p>{preview?.task?.instruction}</p>
            <ul>
              {row?.success_conditions.map((x) => (
                <li key={x}>{x}</li>
              ))}
            </ul>
            <p>
              Reference: <b>{row?.reference_status}</b> · Outcome:{" "}
              <b>{row?.expected_outcome || "authorisation_ready"}</b>
            </p>
          </details>
          <details className="coverage-doc">
            <summary>
              Author-only challenge configuration and customer preferences
            </summary>
            <pre>
              {JSON.stringify(
                {
                  difficulty: row?.difficulty_config,
                  viewport: row?.viewport,
                  task: preview?.task,
                },
                null,
                2,
              )}
            </pre>
          </details>
        </section>
      </div>
    </div>
  );
}
