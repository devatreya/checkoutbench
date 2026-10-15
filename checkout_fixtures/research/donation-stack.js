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
let section = 0;
function paint(s) {
  const end = terminal();
  root.innerHTML =
    header("Community Kit · Supply donation") +
    (end ??
      `<p>Section ${section + 1} of ${Math.ceil(s.fields.length / 2)}</p><form><fieldset><legend>Donation delivery</legend>${s.fields
        .slice(section * 2, section * 2 + 2)
        .map(field)
        .join(
          "",
        )}</fieldset><button type="button" id="next">Continue to shipping</button></form>`);
  root.querySelector("#next")?.addEventListener("click", () => {
    capture();
    if (!root.querySelector("form").reportValidity()) return;
    if ((section + 1) * 2 < s.fields.length) {
      section++;
      paint(s);
      bind();
    } else act("continue");
  });
}
boot(paint);
