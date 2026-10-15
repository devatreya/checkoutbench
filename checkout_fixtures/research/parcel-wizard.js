import {
  root,
  boot,
  field,
  header,
  terminal,
  button,
  capture,
  bind,
  act,
} from "./bridge.js";
let step = 0;
function paint(s) {
  const groups = [s.fields.slice(0, 3), s.fields.slice(3)];
  root.innerHTML =
    header("Parcel Studio · Guided delivery") +
    (terminal() ??
      `<ol class="progress"><li class="${step === 0 ? "active" : ""}">Recipient</li><li class="${step === 1 ? "active" : ""}">Address and delivery</li></ol><form>${groups[step].map(field).join("")}<button type="button" id="advance">Continue to shipping</button></form>`);
  const next = root.querySelector("#advance");
  if (next)
    next.onclick = () => {
      capture();
      if (!root.querySelector("form").reportValidity()) return;
      if (step === 0) {
        step = 1;
        paint(s);
        bind();
      } else act("continue");
    };
}
boot(paint);
