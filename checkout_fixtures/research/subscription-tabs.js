import {
  root,
  boot,
  field,
  header,
  terminal,
  capture,
  bind,
  act,
} from "./bridge.js";
let active = 0;
function paint(s) {
  root.innerHTML =
    header("Monthly Pantry · Subscription setup") +
    (terminal() ??
      `<div class="tabs" role="tablist"><button role="tab" id="contact-tab" aria-selected="${active === 0}">Contact</button><button role="tab" id="delivery-tab" aria-selected="${active === 1}">Delivery</button></div><form role="tabpanel">${s.fields
        .filter((f, i) => (active === 0 ? i < 2 : i >= 2))
        .map(field)
        .join(
          "",
        )}<button type="button" id="next">Continue to shipping</button></form>`);
  for (const [id, n] of [
    ["contact-tab", 0],
    ["delivery-tab", 1],
  ])
    root.querySelector("#" + id)?.addEventListener("click", () => {
      capture();
      active = n;
      paint(s);
      bind();
    });
  root.querySelector("#next")?.addEventListener("click", () => {
    capture();
    if (!root.querySelector("form").reportValidity()) return;
    if (active === 0) {
      active = 1;
      paint(s);
      bind();
    } else act("continue");
  });
}
boot(paint);
