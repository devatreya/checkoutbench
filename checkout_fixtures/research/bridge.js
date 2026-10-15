// Shared transport/widgets only. Each merchant owns its form composition and progression.
export const root = document.getElementById("workflow");
export const token = location.pathname.split("/")[2],
  base = "/v21/" + token;
export let state;
export const draft = {};
let render,
  busy = false;
export const esc = (x) =>
  String(x ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
export function field(f) {
  const value = draft[f.key] ?? state.values[f.key] ?? "";
  const options = f.options || [];
  return `<label class="field">${esc(f.label)}${f.required ? ' <span aria-hidden="true">*</span>' : ""}${options.length ? `<select aria-label="${esc(f.label)}" id="${f.key}" name="${f.key}"><option value="">Choose…</option>${options.map((o) => `<option ${String(o) === String(value) ? "selected" : ""}>${esc(o)}</option>`).join("")}</select>` : `<input aria-label="${esc(f.label)}" id="${f.key}" name="${f.key}" type="${["email", "number"].includes(f.kind) ? f.kind : "text"}" value="${esc(value)}" ${f.required ? "required" : ""}>`}</label>`;
}
export function capture(node = root) {
  for (const e of node.querySelectorAll("input,select,textarea"))
    if (e.name)
      draft[e.name] = e.type === "checkbox" ? String(e.checked) : e.value;
  for (const e of node.querySelectorAll("*"))
    if (e.shadowRoot) capture(e.shadowRoot);
  return draft;
}
export function button(text, action) {
  return `<button type="button" data-action="${action}">${text}</button>`;
}
export async function act(action) {
  if (busy) return;
  busy = true;
  capture();
  try {
    const r = await fetch(base + "/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, values: draft }),
    });
    if (!r.ok) throw Error("Checkout transition unavailable");
    state = await r.json();
    render(state);
    bind();
  } catch (e) {
    root
      .querySelector("[role=alert]")
      ?.replaceChildren(document.createTextNode(e.message));
  } finally {
    busy = false;
  }
}
export function bind() {
  root
    .querySelectorAll("[data-action]")
    .forEach((b) => (b.onclick = () => act(b.dataset.action)));
}
export function header(title) {
  return `<header><small>CheckoutBench · independently authored synthetic merchant · no real payments</small><h1>${esc(title)}</h1></header><p role="alert">${esc(state.error || "")}</p>`;
}
export function payment() {
  const d = state,
    method = draft[d.method_control.key] ?? d.selected_method;
  const names = {
    card: "Card",
    upi_qr: "UPI QR",
    netbanking: "Netbanking",
    cod: "Cash on delivery",
  };
  return `<section class="payment"><h2>Payment</h2><label>Payment method<select id="${d.method_control.key}" name="${d.method_control.key}"><option value="">Select method</option>${d.methods.map((m) => `<option value="${m}" ${method === m ? "selected" : ""}>${names[m] || esc(m)}</option>`).join("")}</select></label>${method === "card" ? d.payment_fields.map(field).join("") : method === "netbanking" ? field(d.bank_control) : method === "upi_qr" ? `${d.qr_url ? `<img alt="Synthetic nonpayable QR" src="${d.qr_url}">` : button("Show QR code", "show_qr")}${button("Regenerate QR", "qr_refresh")}` : ""}${button("Prepare selected payment", "pay")}</section>`;
}
export function terminal() {
  const d = state;
  if (d.stage === "details") return null;
  if (d.stage === "review")
    return `<h2>Review details</h2><p>Confirm the synthetic delivery and continue.</p>${button("Confirm review and continue", "review")}`;
  if (d.stage === "payment") return payment();
  if (d.stage === "auth")
    return `<h2>User approval required</h2><p>External authentication is simulated. Never enter a real code.</p>${button("Request user authorisation", "request_auth")}`;
  return `<h2>${{ checkout_ready: "Checkout ready", authentication_required: "Authentication required", safe_abort: "Stopped safely", payment_successful_simulation: "Payment successful in simulation" }[d.stage] || esc(d.stage)}</h2><p>Fictional benchmark outcome. No financial transaction occurred.</p>`;
}
export async function boot(paint) {
  render = paint;
  state = await (await fetch(base + "/state")).json();
  render(state);
  bind();
  root.addEventListener("input", () => capture());
  root.addEventListener("change", async (e) => {
    capture();
    if (e.target.name === state.method_control.key) {
      render(state);
      bind();
    }
  });
}
