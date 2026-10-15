import { defaults, type Run, type Setup } from "./domain";
// The only normal-UI visibility policy. Backend integrations and raw data remain intact.
export const systems = [
  {
    id: "cua-s1",
    name: "CUA-S1-Forms + Playwright",
    short: "CUA-S1",
    capability: "Semantic field matching and form filling",
    description:
      "An extremely small model matching webpage fields to saved customer information.",
    operation:
      "CUA chooses field values; Playwright executes them with deterministic workflow navigation.",
  },
  {
    id: "tinyclick",
    name: "TinyClick + Controller",
    short: "TinyClick",
    capability: "Screenshot-based element localisation",
    description:
      "A visual grounding model that identifies where to click on a screenshot.",
    operation:
      "The controller selects values and workflow steps; TinyClick predicts click coordinates.",
  },
  {
    id: "hybrid",
    name: "CUA-S1 + TinyClick Hybrid",
    short: "CUA + TinyClick",
    capability: "Field understanding + visual grounding",
    description:
      "Combines semantic field understanding with visual interaction.",
    operation:
      "CUA chooses values and TinyClick locates targets; shared lifecycle assistance is recorded.",
  },
  {
    id: "mai-ui",
    name: "MAI-UI-2B",
    short: "MAI-UI",
    capability: "GUI interaction and navigation",
    description:
      "A compact visual GUI agent that interacts with multiple screens.",
    operation:
      "The model proposes screenshot-based actions; the browser executes its validated action format.",
  },
  {
    id: "ui-venus",
    name: "UI-Venus-1.5-2B",
    short: "UI-Venus",
    capability: "Multi-step GUI automation",
    description:
      "A small GUI agent designed for multi-step interface navigation.",
    operation:
      "The model proposes visual actions through its native parser and controlled browser executor.",
  },
] as const;
const ids = new Set<string>(systems.map((s) => s.id));
export const visibleModel = (id: string) => ids.has(id);
export const modelName = (id: string) =>
  systems.find((m) => m.id === id)?.name || "Unavailable system";
export const shortName = (id: string) =>
  systems.find((m) => m.id === id)?.short || "Unavailable system";
export function visibleRun(r: Run) {
  if (
    !visibleModel(r.model) ||
    r.kind === "reference" ||
    r.is_test_double ||
    r.test_double ||
    r.test_only ||
    (r.action_attribution?.deterministic_reference ?? 0) > 0
  )
    return false;
  const markers = [
    r.evaluation_claim,
    r.record_source,
    r.inference_backend,
    r.model_metadata?.backend,
    ...(Array.isArray(r.calls) ? r.calls.map((c) => c.backend) : []),
  ];
  return !markers.some(
    (x) =>
      typeof x === "string" &&
      /test[-_ ]?double|scripted|mock|fixture verification/i.test(x),
  );
}
const key = "checkoutbench.setup.v2.2";
export function loadSetup(): Setup {
  try {
    const x = JSON.parse(localStorage.getItem(key) || "null");
    if (!x) return { ...defaults };
    const n = (k: keyof Setup, min: number, max: number) =>
      Number.isFinite(x[k])
        ? Math.max(min, Math.min(max, Math.round(x[k])))
        : defaults[k];
    return {
      ...defaults,
      models: Array.isArray(x.models) ? x.models.filter(visibleModel) : [],
      scenarios: Array.isArray(x.scenarios)
        ? x.scenarios.filter((s: unknown) => typeof s === "string")
        : [],
      profile: typeof x.profile === "string" ? x.profile : null,
      repeats: n("repeats", 1, 100) as number,
      seed: n("seed", 0, 2147483647) as number,
      max_steps: n("max_steps", 5, 500) as number,
      timeout: n("timeout", 10, 1800) as number,
      max_tokens: n("max_tokens", 256, 131072) as number,
      infrastructure_retries: n("infrastructure_retries", 0, 3) as number,
      video: x.video === true,
      spending_cap:
        typeof x.spending_cap === "number" && x.spending_cap > 0
          ? x.spending_cap
          : null,
      reasoning: typeof x.reasoning === "string" ? x.reasoning : "default",
      agent_mode: [
        "standard",
        "agent_with_link",
        "agent_without_link",
      ].includes(x.agent_mode)
        ? x.agent_mode
        : "standard",
    };
  } catch {
    return { ...defaults };
  }
}
export function saveSetup(setup: Setup) {
  try {
    localStorage.setItem(
      key,
      JSON.stringify({ ...setup, models: setup.models.filter(visibleModel) }),
    );
    return true;
  } catch {
    return false;
  }
}
