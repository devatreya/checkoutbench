// Restricted supported-control approximation. No access to the parent DOM or network.
(() => {
  let state = JSON.parse(document.querySelector("#context").textContent);
  const root = document.querySelector("#extension");
  const esc = (x) =>
    String(x ?? "").replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[c],
    );
  function render() {
    root.innerHTML =
      '<p class="muted">Merchant options · Plus-style placement · local sandbox approximation</p>' +
      state.fields
        .filter(
          (f) =>
            !f.when ||
            Object.entries(f.when).every(([k, v]) => state.values[k] === v),
        )
        .map((f) => {
          const v = state.values[f.key] || "",
            a = `id="${f.key}" name="${f.key}" aria-label="${esc(f.label)}"`;
          return `<label class="field" for="${f.key}"><span>${esc(f.label)}</span>${f.kind === "checkbox" ? `<input type="checkbox" ${a} ${v === "true" ? "checked" : ""}>` : f.options ? `<select ${a}><option value="">Select…</option>${f.options.map((o) => `<option ${o === v ? "selected" : ""}>${esc(o)}</option>`).join("")}</select>` : `<input ${a} value="${esc(v)}">`}</label>`;
        })
        .join("");
    root.querySelectorAll("input,select").forEach((e) =>
      e.addEventListener("change", () => {
        state.values[e.id] =
          e.type === "checkbox" ? String(e.checked) : e.value;
        parent.postMessage(
          {
            type: "merchant-extension-change",
            values: Object.fromEntries(
              state.fields.map((f) => [f.key, state.values[f.key] || ""]),
            ),
          },
          "*",
        );
        if (e.type === "checkbox" || e.tagName === "SELECT") render();
      }),
    );
    parent.postMessage(
      { type: "merchant-extension-size", height: document.body.scrollHeight },
      "*",
    );
  }
  window.addEventListener("message", (e) => {
    if (e.source !== parent || e.data?.type !== "merchant-extension-context")
      return;
    state.values = { ...state.values, ...e.data.values };
    render();
  });
  render();
})();
