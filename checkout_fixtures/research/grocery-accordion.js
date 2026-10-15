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
    header("Corner Grocery · Delivery basket") +
    (terminal() ??
      `<form>${["Contact", "Delivery"]
        .map(
          (name, i) =>
            `<details open><summary>${name}</summary>${s.fields
              .filter((f, j) => (i === 0 ? j < 3 : j >= 3))
              .map(field)
              .join("")}</details>`,
        )
        .join(
          "",
        )}<p id="validation-summary"></p><button type="button" id="check">Review details</button></form>`);
  root.querySelector("#check")?.addEventListener("click", () => {
    capture();
    const bad = [...root.querySelectorAll("input")].filter(
      (e) => !e.checkValidity(),
    );
    root.querySelector("#validation-summary").textContent = bad.length
      ? `${bad.length} fields need attention`
      : "";
    if (bad.length) {
      bad[0].closest("details").open = true;
      bad[0].reportValidity();
    } else act("continue");
  });
  bind();
});
