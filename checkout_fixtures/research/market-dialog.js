import {
  root,
  boot,
  field,
  header,
  terminal,
  button,
  bind,
  payment,
} from "./bridge.js";
boot((s) => {
  root.innerHTML =
    header("Night Market · Merchant checkout") +
    (s.stage === "payment"
      ? '<p>Delivery saved. Prepare payment in the secure simulation window.</p><button id="launch">Launch payment gateway</button><dialog aria-label="Payment gateway">' +
        payment() +
        "</dialog>"
      : (terminal() ??
        `<div class="columns"><form><fieldset><legend>Delivery details</legend>${s.fields.map(field).join("")}</fieldset>${button("Review details", "continue")}</form><aside><h2>Order</h2><p>Handmade market goods</p><p>Test order only</p></aside></div>`));
  root.querySelector("#launch")?.addEventListener("click", () => {
    root.querySelector("dialog").showModal();
    root.querySelector("#launch").hidden = true;
  });
  bind();
});
