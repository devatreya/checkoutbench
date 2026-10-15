import { num, type Run } from "./domain";
export const scored = (r: Run) => ["completed", "failed"].includes(r.status);
export const mean = (a: unknown[]) => {
  const xs = a.filter(num);
  return xs.length ? xs.reduce((x, y) => x + y, 0) / xs.length : null;
};
export const median = (a: unknown[]) => {
  const xs = a.filter(num).sort((x, y) => x - y);
  return xs.length
    ? (xs[Math.floor((xs.length - 1) / 2)] + xs[Math.floor(xs.length / 2)]) / 2
    : null;
};
export function conditions(r: Run) {
  const c = r.config || {};
  // Unknown historical conditions get an individual group, never an inferred pooled cohort.
  if (!r.cohort || !r.config) return `unreported:${r.id}`;
  return JSON.stringify([
    r.benchmark_version,
    r.cohort,
    r.platform,
    r.integrity_class,
    r.agent_mode,
    r.evaluation_mode,
    c.reasoning,
    c.max_tokens,
    c.max_steps,
    c.timeout,
    c.seed,
    c.profile,
    c.repeats,
  ]);
}
export function conditionLabel(r: Run) {
  const c = r.config;
  return c
    ? `${r.cohort || "Unreported cohort"} · ${r.platform || "unknown device"} · ${r.agent_mode || "standard"} · ${r.evaluation_mode || "unknown mode"} · ${c.max_steps ?? "?"} actions / ${c.timeout ?? "?"}s`
    : `Unreported conditions · ${r.id.slice(0, 8)}`;
}
export function stats(rows: Run[]) {
  const rs = rows.filter(scored),
    n = rs.length,
    k = rs.filter((r) => r.success).length,
    p = n ? k / n : null,
    z = 1.96;
  const centre =
      p === null ? null : (p + (z * z) / (2 * n)) / (1 + (z * z) / n),
    half =
      p === null
        ? null
        : (z * Math.sqrt((p * (1 - p)) / n + (z * z) / (4 * n * n))) /
          (1 + (z * z) / n);
  // Charges on stopped or infrastructure-failed attempts still count as expenditure.
  const costRows = rows.filter((r) => r.status !== "running");
  const costs = costRows.map((r) =>
    r.cost_kind === "not_reported" ? null : r.cost,
  );
  const cost =
    costRows.length && costs.every(num)
      ? (costs as number[]).reduce((a, b) => a + b, 0)
      : null;
  return {
    n,
    k,
    success: p,
    ci:
      centre !== null && half !== null
        ? [Math.max(0, centre - half), Math.min(1, centre + half)]
        : null,
    duration: median(rs.map((r) => r.wall_seconds)),
    field: mean(rs.map((r) => r.required_field_accuracy)),
    payment: mean(
      rs.map((r) => r.payment_method_accuracy ?? r.payment_selection_accuracy),
    ),
    paymentValidation: mean(rs.map((r) => r.payment_accuracy)),
    recovery: mean(rs.map((r) => r.recovery_success_rate)),
    cost,
    costPerSuccess: k && cost !== null ? cost / k : null,
    reportedFields: rs.filter((r) => num(r.required_field_accuracy)).length,
    reportedPayment: rs.filter((r) =>
      num(r.payment_method_accuracy ?? r.payment_selection_accuracy),
    ).length,
  };
}
export function comparable(groups: Run[][]) {
  if (groups.length < 2 || groups.some((rs) => rs.filter(scored).length < 5))
    return false;
  const signature = (rows: Run[]) =>
    JSON.stringify(
      rows
        .filter(scored)
        .map((r) => [r.scenario, r.seed, r.profile_id, r.repeat].join("|"))
        .sort(),
    );
  return groups.every((g) => signature(g) === signature(groups[0]));
}
