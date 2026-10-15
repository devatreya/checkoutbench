import { root, boot, field, header, terminal, button, bind } from "./bridge.js";
boot((s) => {
  root.innerHTML =
    header("Ledger Supply · Purchase order") +
    (terminal() ??
      `<form><table><caption>Recipient and dispatch ledger</caption><thead><tr><th>Line</th><th>Delivery instruction</th></tr></thead><tbody>${s.fields.map((f, i) => `<tr><th>${i + 1}</th><td>${field(f)}</td></tr>`).join("")}</tbody></table><footer>${button("Review details", "continue")}</footer></form>`);
  root
    .querySelector("form")
    ?.addEventListener("submit", (e) => e.preventDefault());
  bind();
});
