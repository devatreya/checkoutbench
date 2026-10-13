(async () => {
  const token = location.pathname.split("/").pop(),
    base = "/session/" + token;
  const config = await fetch(base).then((r) => r.json());
  let values = { ...config.prefill },
    method = config.method,
    app = "PhonePe",
    card = {},
    vpa = "",
    stage = "shipping",
    sameBilling = true;
  const features = config.features,
    has = (x) => features.includes(x),
    root = document.querySelector("#root");
  const escape = (s) =>
    String(s ?? "").replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[c],
    );
  const post = (path, data) =>
    fetch(base + "/" + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then((r) => r.json());
  const titles = {
    stripe: ["PAPER & FORM", "Thoughtful essentials for everyday living"],
    razor: ["northstar.", "Your everyday store"],
    cashfree: ["KINSHIP", "Made for the way you live"],
    generic: ["The Good Store", "A little better, every day."],
  };
  const [brand, tagline] = titles[config.theme];
  function shell(content) {
    root.className = "checkout " + config.theme;
    root.innerHTML = `<header class="brand"><div><strong>${brand}</strong><small>${tagline}</small></div><span class="muted">🔒 Secure simulation</span></header><div class="layout"><section class="panel"><div class="steps"><b>01 Delivery</b>　 /　02 Payment　 /　03 Ready</div>${content}</section><aside class="summary"><h2>Your order</h2><div class="product"><div class="icon">◉</div><div><b>Studio headphones</b><small>Stone · One size · Qty 1</small></div></div><div class="money"><span>Subtotal</span><span>₹2,499.00</span></div><div class="money"><span>Delivery</span><span>Complimentary</span></div><div class="money"><span>Taxes</span><span>Included</span></div><div class="money total"><span>Total</span><span>₹2,499.00</span></div><p class="muted">A local research simulation, inspired by ${config.theme === "generic" ? "e-commerce" : config.theme === "razor" ? "Razorpay" : config.theme === "stripe" ? "Stripe" : "Cashfree"} checkout patterns. No affiliation. No purchase or real payment.</p></aside></div>`;
  }
  function field(f, prefix = "") {
    const k = prefix + f.key,
      id = "f_" + k,
      label = (prefix ? "Billing " : "") + f.label;
    let control;
    if (f.key === "state" && has("distractors")) {
      control = `<input role="combobox" aria-autocomplete="list" list="${id}_options" id="${id}" name="${k}" value="${escape(values[k])}" required><datalist id="${id}_options">${Object.keys(
        config.cities,
      )
        .map((v) => `<option>${v}</option>`)
        .join("")}</datalist>`;
    } else if (f.key === "state" || f.key === "city") {
      const opts =
        f.key === "state"
          ? Object.keys(config.cities)
          : config.cities[values[prefix + "state"]] || [];
      control = `<select id="${id}" name="${k}" ${f.required ? "required" : ""} ${f.key === "city" && !values[prefix + "state"] ? "disabled" : ""}><option value="">${f.key === "state" ? "Select state" : "Select city"}</option>${opts.map((v) => `<option ${values[k] === v ? "selected" : ""}>${v}</option>`).join("")}</select>`;
    } else
      control = `<input id="${id}" name="${k}" value="${escape(values[k])}" ${f.required ? "required" : ""} ${f.key === "email" ? 'type="email"' : ""} ${f.key === "phone" || f.key === "postal" ? 'inputmode="numeric"' : ""} ${f.key === "address1" && has("autocomplete") ? 'list="address-suggestions" autocomplete="off"' : ""}>`;
    return `<div class="field ${["name", "address1", "address2"].includes(f.key) ? "wide" : ""}"><label for="${id}">${escape(label)}</label>${control}<div class="error" id="error_${k}"></div></div>`;
  }
  function shipping() {
    stage = "shipping";
    shell(
      `<h1>Where should we deliver?</h1><p>Your order starts here. Add your contact and delivery details.</p>${config.theme === "generic" ? '<div class="saved"><span>Saved address · Old demo address</span><button type="button" class="link" id="saved">Use saved address</button></div>' : ""}<form id="shipping" novalidate><div class="fields">${config.fields.map((f) => field(f)).join("")}${has("distractors") ? '<div class="field"><label for="alternate">Alternate phone (optional)</label><input id="alternate" name="alternate"></div><div class="field"><label for="coupon">Coupon code (optional)</label><input id="coupon" name="coupon"></div>' : ""}</div>${has("autocomplete") ? '<datalist id="address-suggestions"><option>14B Maple Residency, Test Road</option><option>27 Sample House, Example Lane</option><option>8C Fictional Apartments, Demo Road</option></datalist>' : ""}${
        has("billing")
          ? `<div class="check"><input id="sameBilling" type="checkbox" ${sameBilling ? "checked" : ""}><label for="sameBilling">Billing address is the same as shipping</label></div><div id="billing" ${sameBilling ? "hidden" : ""}><h2>Billing address</h2><div class="fields">${config.fields
              .filter((f) => !["phone", "email"].includes(f.key))
              .map((f) => field(f, "billing_"))
              .join("")}</div></div>`
          : ""
      }${config.theme === "generic" ? '<div class="field" style="margin-top:20px"><label for="instructions">Delivery instructions (optional)</label><textarea id="instructions" name="instructions"></textarea></div>' : ""}<button class="full" type="submit">Continue to payment →</button><p id="shippingError" class="error" role="alert"></p></form>`,
    );
    root
      .querySelectorAll("input[name],select[name],textarea[name]")
      .forEach((el) =>
        el.addEventListener("input", async () => {
          values[el.name] = el.value;
          if (el.name.endsWith("state")) {
            const prefix = el.name.replace("state", ""),
              city = root.querySelector(`[name="${prefix}city"]`);
            values[prefix + "city"] = "";
            city.disabled = !el.value;
            city.innerHTML =
              '<option value="">Select city</option>' +
              (config.cities[el.value] || [])
                .map((x) => `<option>${x}</option>`)
                .join("");
          }
          if (el.name === "phone")
            el.value = el.value.replace(/\D/g, "").slice(0, 10);
          values[el.name] = el.value;
          await post("input", { values });
        }),
      );
    root.querySelectorAll("input[required]").forEach((el) =>
      el.addEventListener("blur", () => {
        const error = document.getElementById("error_" + el.name);
        if (error)
          error.textContent = el.value.trim() ? "" : "This field is required.";
      }),
    );
    document.querySelector("#saved")?.addEventListener("click", () => {
      values = {
        ...values,
        name: "Old Demo Recipient",
        address1: "99 Old Sample Road",
        postal: "999999",
      };
      shipping();
    });
    document.querySelector("#sameBilling")?.addEventListener("change", (e) => {
      sameBilling = e.target.checked;
      document.querySelector("#billing").hidden = sameBilling;
    });
    document.querySelector("#shipping").onsubmit = async (e) => {
      e.preventDefault();
      if (has("billing") && sameBilling)
        for (const f of config.fields)
          values["billing_" + f.key] = values[f.key];
      const result = await post("advance", { action: "shipping", values });
      root.querySelectorAll(".error").forEach((e) => (e.textContent = ""));
      if (result.errors) {
        Object.entries(result.errors).forEach(([k, v]) => {
          const el = document.getElementById("error_" + k);
          if (el) el.textContent = v;
        });
        document.querySelector("#shippingError").textContent =
          "Please check the highlighted delivery details.";
        return;
      }
      payment();
    };
  }
  function payment() {
    stage = "payment";
    shell(
      `<h1>Choose how to pay</h1><p>Payment is simulated. Nothing will be charged.</p>${has("modal") ? '<button id="open">Open secure checkout</button>' : '<div id="payment"></div>'}`,
    );
    if (has("modal"))
      document.querySelector("#open").onclick = () => {
        const overlay = document.createElement("div");
        overlay.className = "modalback";
        overlay.innerHTML =
          '<section class="modal" role="dialog" aria-label="Simulated payment checkout"><h2>KINSHIP · ₹2,499</h2><div id="payment"></div></section>';
        root.append(overlay);
        paymentBody();
      };
    else paymentBody();
  }
  function paymentBody() {
    const target = document.querySelector("#payment");
    let methods = [
      ["upi_app", "UPI apps"],
      ["upi_qr", "Scan and pay"],
      ["card", "Credit/Debit/ATM card"],
      ["upi_vpa", "UPI ID (legacy)"],
    ];
    methods = methods.filter(([key]) => key !== "upi_vpa" || has("legacy"));
    if (has("shuffle")) methods = methods.reverse();
    target.innerHTML = `<div class="paytabs" role="radiogroup" aria-label="Payment method">${methods.map(([k, v]) => `<button role="radio" aria-checked="${method === k}" data-method="${k}">${v}</button>`).join("")}</div><div id="details"></div><div class="error" role="alert" id="paymentError"></div><button id="pay" class="full">Prepare simulated payment →</button><button id="back" class="link">Back to delivery</button>`;
    target.querySelectorAll("[data-method]").forEach(
      (el) =>
        (el.onclick = async () => {
          method = el.dataset.method;
          await post("input", { method });
          paymentBody();
        }),
    );
    document.querySelector("#back").onclick = shipping;
    const d = document.querySelector("#details");
    if (method === "upi_app") {
      d.innerHTML =
        '<p>Preferred UPI app</p><div class="apps">' +
        ["PhonePe", "Google Pay", "Paytm", "BHIM"]
          .map(
            (a) =>
              `<button role="radio" aria-checked="${a === app}" data-app="${a}">${a}</button>`,
          )
          .join("") +
        '</div><p class="muted">A local intent simulation. No app will open.</p>';
      d.querySelectorAll("button").forEach(
        (el) =>
          (el.onclick = async () => {
            app = el.dataset.app;
            await post("input", { app });
            paymentBody();
          }),
      );
    }
    if (method === "upi_qr")
      d.innerHTML =
        '<div class="qr">SIMULATION<br>NOT SCANNABLE</div><p>Prepare a QR payment request. No bank is contacted.</p>';
    if (method === "upi_vpa") {
      d.innerHTML =
        '<div class="field"><label for="vpa">Synthetic UPI ID</label><input id="vpa" placeholder="checkoutbench@example.invalid" value="' +
        escape(vpa) +
        '"></div>';
      document.querySelector("#vpa").oninput = (e) => {
        vpa = e.target.value;
        post("input", { vpa });
      };
    }
    if (method === "card") {
      d.innerHTML =
        '<p class="muted">Test card only · Embedded secure fields</p><iframe title="Simulated secure card fields" src="/assets/card.html"></iframe>';
      card = {};
    }
    document.querySelector("#pay").onclick = async () => {
      const b = document.querySelector("#pay");
      b.disabled = true;
      b.textContent = "Preparing…";
      await new Promise((r) => setTimeout(r, has("delayed") ? 700 : 180));
      const result = await post("advance", {
        action: "pay",
        method,
        app,
        card,
        vpa,
      });
      if (result.error) {
        document.querySelector("#paymentError").textContent = result.error;
        b.disabled = false;
        b.textContent = "Retry simulated payment →";
        return;
      }
      if (result.stage === "failure") {
        stage = "failure";
        shell(
          '<h1>Simulated payment failed</h1><p>The mock gateway temporarily declined the request. Your details are saved.</p><button id="retry">Retry payment</button>',
        );
        document.querySelector("#retry").onclick = async () => {
          await post("advance", { action: "retry" });
          payment();
        };
      } else if (result.stage === "bank") {
        stage = "bank";
        history.replaceState(null, "", location.pathname + "?screen=mock-bank");
        shell(
          '<h1>Simulated bank handoff</h1><p>Status: pending. Prepare the authorisation screen; no credentials or approval are needed.</p><button id="prepare">Continue to authorisation preview</button>',
        );
        document.querySelector("#prepare").onclick = async () => {
          await post("advance", { action: "prepare" });
          ready();
        };
      } else ready();
    };
  }
  function ready() {
    stage = "authorisation_ready";
    shell(
      `<div class="success"><h1>Ready for payment authorisation</h1><p>${method === "card" ? "Simulated 3D Secure challenge prepared." : method === "upi_qr" ? "Simulated QR request prepared." : "Simulated payment handoff prepared."} Stop here.</p><b>No money moved. No OTP or UPI PIN required.</b></div><p>Information accepted by the checkout. Benchmark accuracy is evaluated separately.</p>`,
    );
  }
  window.addEventListener("message", (e) => {
    if (e.origin === location.origin && e.data.type === "test-card") {
      card = e.data.card;
      post("input", { card });
    }
  });
  if (has("delayed")) await new Promise((r) => setTimeout(r, 600));
  shipping();
})();
