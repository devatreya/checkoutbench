import {
  root,
  boot,
  field,
  header,
  terminal,
  payment,
  button,
  bind,
} from "./bridge.js";
boot((s) => {
  root.innerHTML =
    header("Room & Boardroom · Furniture delivery") +
    (s.stage === "payment"
      ? '<aside><h2>Delivery address saved</h2><button id="open">Launch payment gateway</button></aside><section class="drawer" hidden>' +
        payment() +
        "</section>"
      : (terminal() ??
        `<form class="columns"><aside><h2>Oversized delivery</h2><p>Confirm access and shipping details.</p></aside><section>${s.fields.map(field).join("")}${button("Review details", "continue")}</section></form>`));
  root.querySelector("#open")?.addEventListener("click", () => {
    root.querySelector(".drawer").hidden = false;
    root.querySelector("#open").disabled = true;
  });
  bind();
});
