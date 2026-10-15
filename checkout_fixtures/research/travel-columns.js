import {
  root,
  boot,
  field,
  header,
  terminal,
  button,
  bind,
  capture,
  act,
} from "./bridge.js";
boot((s) => {
  root.innerHTML =
    header("Weekend Desk · Travel supplies") +
    (terminal() ??
      `<form><div class="columns"><section><h2>Who is travelling?</h2>${s.fields.slice(0, 2).map(field).join("")}</section><section><h2>Where should we deliver?</h2>${s.fields.slice(2).map(field).join("")}</section></div><aside id="review-note">Review the reservation details before continuing.</aside><button type="button" id="confirm">Review details</button></form>`);
  root.querySelector("#confirm")?.addEventListener("click", () => {
    capture();
    const form = root.querySelector("form");
    if (form.reportValidity()) act("continue");
    else
      root.querySelector("#review-note").textContent =
        "Complete the marked required fields.";
  });
  bind();
});
