import {
  root,
  boot,
  field,
  header,
  terminal,
  button,
  capture,
  act,
  bind,
} from "./bridge.js";
let review = false;
function paint(s) {
  root.innerHTML =
    header("Paper Route · Bookshop") +
    (terminal() ??
      `<form><div class="card-grid">${s.fields.map((f) => `<article class="form-card">${field(f)}</article>`).join("")}</div>${review ? '<p>Review the visible address before continuing.</p><button type="button" id="confirm">Confirm review and continue</button>' : '<button type="button" id="review">Review details</button>'}</form>`);
  root.querySelector("#review")?.addEventListener("click", () => {
    capture();
    review = true;
    paint(s);
    bind();
  });
  root
    .querySelector("#confirm")
    ?.addEventListener("click", () => act("continue"));
}
boot(paint);
