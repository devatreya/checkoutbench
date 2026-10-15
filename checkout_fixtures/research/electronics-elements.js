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
class DeliveryCard extends HTMLElement {
  connectedCallback() {
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this.shadowRoot.innerHTML =
      "<style>label{display:block;margin:12px}input,select{display:block;padding:10px;width:90%;font:inherit}</style>" +
      this.dataset.content;
    this.shadowRoot.addEventListener("input", () => capture(this.shadowRoot));
    this.shadowRoot.addEventListener("change", () => capture(this.shadowRoot));
  }
}
customElements.define("delivery-card", DeliveryCard);
boot((s) => {
  const end = terminal();
  root.innerHTML =
    header("Circuit House · Electronics") +
    (end ??
      '<div class="card-grid" id="cards"></div><button id="submit">Review details</button>');
  if (!end) {
    for (const fields of [s.fields.slice(0, 3), s.fields.slice(3)]) {
      const card = document.createElement("delivery-card");
      card.dataset.content = fields.map(field).join("");
      root.querySelector("#cards").append(card);
    }
    root.querySelector("#submit").onclick = () => {
      capture();
      act("continue");
    };
  }
  bind();
});
