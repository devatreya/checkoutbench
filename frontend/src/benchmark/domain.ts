export type Model = {
  id: string;
  name?: string;
  kind?: string;
  parameters?: number;
  available?: boolean;
  status?: string;
  backend?: string;
  reason?: string;
  pricing?: Record<string, string>;
  reasoning_levels?: string[];
};
export type Scenario = {
  id: string;
  canonical_id?: string;
  public_id?: string;
  display_name?: string;
  description?: string;
  title: string;
  family: string;
  benchmark_version: string;
  difficulty?: string;
  difficulty_config?: Record<string, any>;
  method: string;
  features: string[];
  platform?: string;
  requires_auth?: boolean;
  authentication_method?: string;
  auth_surface?: string;
  expected_outcome?: string;
  success_conditions?: string[];
  required_fields?: string[];
  optional_fields?: string[];
  supported_payment_methods?: string[];
  provenance?: Record<string, any>;
  qr?: string;
  [key: string]: any;
};
export type Run = {
  id: string;
  model: string;
  scenario: string;
  canonical_id?: string;
  public_id?: string;
  display_name?: string;
  description?: string;
  status: string;
  success?: boolean;
  timestamp?: string;
  benchmark_version?: string;
  environment?: string;
  config?: Record<string, any>;
  events?: Action[];
  [key: string]: any;
};
export type Action = {
  index?: number;
  elapsed?: number;
  action: string;
  detail?: Record<string, any>;
  screenshot?: string;
  [key: string]: any;
};
export type RunnerState = {
  running: boolean;
  paused?: boolean;
  batch?: {
    id?: string;
    total: number;
    finished: number;
    status: string;
    config?: Record<string, any>;
    spent?: number;
  };
  current?: Run;
};
export type Setup = {
  models: string[];
  scenarios: string[];
  repeats: number;
  profile: string | null;
  seed: number;
  max_steps: number;
  timeout: number;
  max_tokens: number;
  reasoning: string;
  spending_cap: number | null;
  video: boolean;
  infrastructure_retries: number;
  agent_mode: string;
};
export const defaults: Setup = {
  models: [],
  scenarios: [],
  repeats: 3,
  profile: null,
  seed: 2026,
  max_steps: 100,
  timeout: 180,
  max_tokens: 8192,
  reasoning: "default",
  spending_cap: null,
  video: false,
  infrastructure_retries: 1,
  agent_mode: "standard",
};
export async function api(path: string, body?: unknown) {
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
      typeof d.detail === "string"
        ? d.detail
        : JSON.stringify(d.detail || "Request failed"),
    );
  return d;
}
export const human = (v: unknown) =>
  typeof v === "string"
    ? v.replaceAll("_", " ").replaceAll("-", " ")
    : v === undefined || v === null
      ? "Not reported"
      : String(v);
// The API owns the registry. Never guess aliases by stripping release prefixes.
export const scenarioPublicId = (row?: Record<string, any>) =>
  row?.public_id || row?.scenario_public_id || "Unmapped scenario";
export const scenarioTitle = (row?: Record<string, any>) =>
  row?.display_name ||
  row?.title ||
  row?.scenario_title ||
  "Scenario details unavailable";
export const num = (v: unknown): v is number =>
  typeof v === "number" && Number.isFinite(v);
export const pct = (v: unknown) =>
  num(v) ? `${(v * 100).toFixed(1)}%` : "Not reported";
export const seconds = (v: unknown) =>
  num(v) ? `${v.toFixed(2)}s` : "Not reported";
export const money = (v: unknown) =>
  num(v) ? `$${v.toFixed(4)}` : "Not reported";
export const date = (v?: string) =>
  v && !Number.isNaN(Date.parse(v))
    ? new Date(v).toLocaleString()
    : "Not reported";
export const shown = (v: unknown) =>
  v === null || v === undefined
    ? "Not reported"
    : typeof v === "object"
      ? JSON.stringify(v)
      : typeof v === "boolean"
        ? v
          ? "Yes"
          : "No"
        : String(v);
export function artifact(v?: string) {
  if (!v) return undefined;
  try {
    const u = new URL(v, location.origin);
    return u.origin === location.origin && u.pathname.startsWith("/artifacts/")
      ? u.href
      : undefined;
  } catch {
    return undefined;
  }
}
export function download(name: string, data: unknown, csv = false) {
  const blob = new Blob([csv ? String(data) : JSON.stringify(data, null, 2)], {
    type: csv ? "text/csv;charset=utf-8" : "application/json",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function csv(rows: Record<string, unknown>[]) {
  if (!rows.length) return "";
  const keys = [...new Set(rows.flatMap((r) => Object.keys(r)))];
  const cell = (v: unknown) => {
    let t =
      v === undefined || v === null
        ? ""
        : typeof v === "object"
          ? JSON.stringify(v)
          : String(v);
    if (/^[=+@\-\t\r]/.test(t)) t = "'" + t;
    return '"' + t.replaceAll('"', '""') + '"';
  };
  return [
    keys.map(cell).join(","),
    ...rows.map((r) => keys.map((k) => cell(r[k])).join(",")),
  ].join("\r\n");
}
export const environments = [
  [
    "stripe",
    "Stripe-inspired",
    "Simulated card entry, embedded components, authentication",
  ],
  ["razor", "Razorpay-inspired", "Simulated UPI, cards and payment modals"],
  [
    "cashfree",
    "Cashfree-inspired",
    "Simulated hosted checkout, popups and redirects",
  ],
  ["generic", "Indian E-commerce", "Addresses, PIN codes and saved details"],
  [
    "shopify",
    "Shopify-inspired",
    "Simulated merchants, layouts and extensions",
  ],
  ["railway", "IRCTC-inspired", "Dense passenger forms and payment navigation"],
  [
    "passport",
    "Passport Seva-inspired",
    "Appointments, forms and payment redirects",
  ],
  [
    "echallan",
    "eChallan-inspired",
    "Verification, handoff and transaction status",
  ],
  [
    "link",
    "Stripe Link-inspired",
    "Simulated autofill and returning customers",
  ],
] as const;
export const familyName = (f?: string) =>
  environments.find((e) => e[0] === f)?.[1] || human(f);
export const requiresAuth = (s: Scenario) =>
  Boolean(
    s.requires_auth ||
    (s.authentication_method && s.authentication_method !== "none") ||
    s.expected_outcome === "authentication_required",
  );
export const challenge = (s: Scenario) =>
  [
    ...(s.features || []).filter((f) => f !== "holdout"),
    ...Object.values(s.difficulty_config || {}).filter(
      (v) =>
        typeof v === "string" && !["normal", "standard", s.method].includes(v),
    ),
  ]
    .slice(0, 4)
    .map(human)
    .join(" · ") ||
  environments.find((e) => e[0] === s.family)?.[2] ||
  "Field matching and checkout progression";
export function status(r?: Run) {
  if (!r) return "Idle";
  if (r.status === "unavailable") return "Model unavailable";
  if (
    r.failure_reason === "timeout" ||
    r.failure_reason === "browser_action_timeout"
  )
    return "Timed out";
  if (r.failure_reason === "infrastructure_error" || r.status === "blocked")
    return "Infrastructure error";
  if (
    r.status === "running" &&
    (r.completion_stage === "authentication_required" ||
      r.events
        ?.at(-1)
        ?.detail?.target?.toLowerCase?.()
        .includes("authorisation"))
  )
    return "Awaiting simulated authentication";
  if (r.status === "completed" && r.success) return "Completed successfully";
  return human(r.status);
}
