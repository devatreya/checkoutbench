(() => {
  const parts = location.pathname.split("/"),
    token = parts[1] === "checkout" ? parts[2] : parts[2],
    base = "/v2/" + token;
  const root = document.getElementById("root");
  let state,
    local = {},
    opened = false,
    busy = false;
  const esc = (x) =>
    String(x ?? "").replace(
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
  const button = (label, action, cls = "primary", extra = "") =>
    `<button type="button" class="${cls}" data-action="${action}" ${extra}>${label}</button>`;
  const values = () => ({ ...state.values, ...local });
  const controls = () => [
    ...root.querySelectorAll("input,select,textarea"),
    ...Array.from(root.querySelectorAll("merchant-extension")).flatMap((e) =>
      Array.from(e.shadowRoot?.querySelectorAll("input,select,textarea") || []),
    ),
  ];
  function collect() {
    const v = { ...local };
    controls().forEach((e) => {
      if (e.name && e.type !== "radio")
        v[e.name] = e.type === "checkbox" ? String(e.checked) : e.value;
      if (e.type === "radio" && e.checked) v[e.name] = e.value;
    });
    return v;
  }
  async function act(action, extra = {}) {
    if (busy) return;
    busy = true;
    root.setAttribute("aria-busy", "true");
    const v = collect();
    root.querySelectorAll("button").forEach((e) => (e.disabled = true));
    if (action === "qr_refresh" || action === "qr_fullsize") {
      root.querySelector(".qr-box img")?.remove();
      root
        .querySelector(".qr-box p")
        ?.replaceChildren(document.createTextNode("Preparing a fresh QR…"));
    }
    try {
      const r = await fetch(base + "/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, values: v, ...extra }),
      });
      const j = await r.json();
      if (!r.ok) throw Error(j.detail || "Action unavailable");
      state = j;
      local = {};
      render();
    } catch (e) {
      if (state) {
        state.error = e.message;
        render();
      }
      root
        .querySelector("[role=alert]")
        ?.replaceChildren(document.createTextNode(e.message));
    } finally {
      busy = false;
      root.removeAttribute("aria-busy");
    }
  }
  function input(f) {
    const v = values(),
      val = v[f.key] ?? "",
      conditional =
        f.when && Object.entries(f.when).some(([k, x]) => v[k] !== x);
    if (conditional) return "";
    const attrs = `name="${f.key}" id="${f.key}" aria-label="${esc(f.label)}" ${f.required ? "required" : ""}`;
    if (f.kind === "checkbox")
      return `<label class="check"><input type="checkbox" ${attrs} ${val === "true" ? "checked" : ""}> <span>${esc(f.label)}</span></label>`;
    return `<label class="field" for="${f.key}"><span>${esc(f.label)}${f.required ? "" : " <small>Optional</small>"}</span>${f.options ? `<select ${attrs}><option value="">Select…</option>${f.options.map((x) => `<option ${x === val ? "selected" : ""}>${esc(x)}</option>`).join("")}</select>` : `<input ${attrs} type="${f.kind === "number" ? "number" : "text"}" value="${esc(val)}" ${f.key === "address1" ? 'list="address-suggestions" autocomplete="off"' : ""}>`}</label>`;
  }
  function fields(fs) {
    return fs.map(input).join("");
  }
  const group = (title, html, cls = "") =>
    `<section class="panel ${cls}"><h2>${title}</h2>${html}</section>`;
  function payment() {
    const v = values(),
      selected = v.payment_method || "";
    const methods = [
      ["card", "Card"],
      ...(state.family === "link"
        ? []
        : [
            ["upi_app", "UPI app"],
            ["upi_qr", "UPI QR"],
            ["upi_vpa", "Legacy VPA"],
          ]),
      ...(state.link_enabled ? [["link", "Link · saved payment"]] : []),
    ];
    let html = `<div class="payment-tabs">${methods.map(([key, label]) => `<label><input type="radio" name="payment_method" value="${key}" ${selected === key ? "checked" : ""}>${label}</label>`).join("")}</div>`;
    if (selected === "card")
      html += `<div class="grid">${fields([
        { key: "cardName", label: "Name on test card" },
        { key: "cardNumber", label: "Test card number" },
        { key: "expiry", label: "Expiry" },
        { key: "cvv", label: "Test CVV" },
      ])}</div><p class="muted">Synthetic card only · 4242 4242 4242 4242 · 12/30 · 123</p>`;
    if (selected === "upi_app")
      html += input({
        key: "upi_app",
        label: "UPI app",
        options: ["PhonePe", "Google Pay", "Paytm", "BHIM"],
      });
    if (selected === "upi_vpa")
      html += input({ key: "vpa", label: "Synthetic UPI identifier" });
    if (selected === "link")
      html += state.link_authenticated
        ? `<h3>Saved payment methods</h3>${state.cards.map((c) => `<label class="saved-card"><input type="radio" name="saved_card" value="${c.id}" ${v.saved_card === c.id ? "checked" : ""} ${c.expired ? "disabled" : ""}><b>${esc(c.label)}</b><span>${c.expired ? "Expired · unavailable" : "Available"}</span></label>`).join("")}`
        : `<p>Authenticate Link from your contact details, or use ordinary card entry.</p>${button("Return to contact", "manual_card", "secondary")}`;
    if (selected === "upi_qr")
      html += state.qr_url
        ? `<div class="qr-box"><img alt="Synthetic payment QR code" src="${state.qr_url}" width="${state.qr_size}" height="${state.qr_size}"><p>${esc(state.qr_notice)}</p><div class="row">${button("Enlarge displayed QR", "qr_enlarge", "secondary")}${button("Request full-resolution QR", "qr_fullsize", "secondary")}${button("Regenerate QR", "qr_refresh", "secondary")}${button("Request user intervention", "help", "text-button")}</div></div>`
        : `${button("Show QR code", "show_qr", "secondary")}<p class="muted">The test wallet checks the actual image before preparation.</p>`;
    return html;
  }
  function linkLogin() {
    return `<section class="link-wallet"><div class="row"><strong>link <span class="pill">SIMULATED</span></strong><span>Accelerated checkout</span></div>${
      state.link_authenticated
        ? `<p>Signed in as ${esc(values().email)}. Review saved details before continuing.</p>${button("Use a different account", "signout", "text-button")}`
        : state.link_status === "signup"
          ? `<h3>Save your details for next time?</h3><p>A new account requires your explicit consent.</p>${input({ key: "registration_consent", label: "I explicitly consent to creating a synthetic Link account", kind: "checkbox" })}${group(
              "Test payment information to save",
              fields([
                { key: "cardName", label: "Name on test card", required: true },
                {
                  key: "cardNumber",
                  label: "Test card number",
                  required: true,
                },
                { key: "expiry", label: "Expiry", required: true },
                { key: "cvv", label: "Test CVV", required: true },
              ]),
            )}${button("Create synthetic account", "register")}${button("Continue without Link", "manual_card", "secondary")}`
          : state.link_status === "declined"
            ? "<p>Ordinary card checkout selected. No account will be created.</p>"
            : `${input({ key: "email", label: "Email", required: true })}<div class="row">${button("Continue with Link", "recognize")}${button("Use ordinary card checkout", "manual_card", "text-button")}</div>`
    }</section>`;
  }
  function details() {
    let fs = state.fields;
    if (state.layout === "three-page")
      fs = fs.filter((f) =>
        state.stage === "details"
          ? ["contact", "delivery", "billing"].includes(f.section)
          : !["contact", "delivery", "billing"].includes(f.section),
      );
    if (state.family === "railway") {
      const groups = [...new Set(fs.map((f) => f.section))];
      if (state.variant === "legacy")
        return `<div class="journey-strip"><b>DEMO 042 · SAMPLE EXPRESS</b><span>SMC → DMT · 14 Nov · Class 3A · General quota</span></div><div class="notice">Boarding may differ from origin. Destination: DMT · Demo Terminal.</div><table class="passenger-table"><caption>Passenger particulars</caption><thead><tr><th>Traveller</th><th>Name</th><th>Age</th><th>Berth</th></tr></thead><tbody>${groups
          .filter((g) => g.startsWith("Passenger"))
          .map(
            (g) =>
              `<tr><th>${g}</th>${fs
                .filter((f) => f.section === g)
                .map((f) => `<td>${input(f)}</td>`)
                .join("")}</tr>`,
          )
          .join(
            "",
          )}</tbody></table>${group("Reservation preferences", fields(fs.filter((f) => !f.section.startsWith("Passenger"))))}<aside class="ad-panel">FICTIONAL TRAVEL NOTICE · Carry no real documents into this simulation. Seats and fares are synthetic.</aside>`;
      return `<div class="journey-card"><span>YOUR JOURNEY</span><h2>Sample City → Demo Terminal</h2><p>14 November · 3A · General quota · DEMO 042</p></div>${groups.map((g) => `<details class="panel" open><summary>${g}</summary><div class="grid">${fields(fs.filter((f) => f.section === g))}</div></details>`).join("")}`;
    }
    if (state.family === "passport")
      return `<div class="application-card"><span>SAVED APPLICATION</span><h2>${esc(state.application_summary.reference)}</h2><p>${esc(state.application_summary.name)} · Fictional applicant · No documents required</p></div>${[...new Set(fs.map((f) => f.section))].map((g) => group(g, `<div class="grid">${fields(fs.filter((f) => f.section === g))}</div>`)).join("")}`;
    if (state.family === "echallan")
      return `<div class="lookup-card"><span>FIND A SYNTHETIC NOTICE</span><h2>Check outstanding challans</h2><p>Use DEMO identifiers only. Previously paid notices must not be paid again.</p>${fields(fs)}</div>`;
    let html = state.family === "link" && state.link_enabled ? linkLogin() : "";
    const sections = [
      ...new Set(
        fs
          .filter(
            (f) =>
              !(
                state.family === "link" &&
                state.link_enabled &&
                f.key === "email"
              ),
          )
          .map((f) => f.section),
      ),
    ];
    html += sections
      .map((section) => {
        let content = `<div class="grid">${fields(fs.filter((f) => f.section === section && !(state.family === "link" && state.link_enabled && f.key === "email")))}</div>`;
        let title =
          {
            contact: "Contact",
            delivery: "Delivery",
            billing: "Billing address",
            shipping: "Delivery options & merchant extras",
          }[section] || section;
        if (state.shadow && section === "shipping")
          return group(
            title,
            `<merchant-extension data-content="${esc(content)}"></merchant-extension><p class="muted">Merchant extension · gift preferences</p>`,
          );
        if (
          (state.layout === "express" ||
            state.variant === "express" ||
            state.link_authenticated) &&
          ["delivery", "billing"].includes(section)
        )
          return `<details class="panel rollup"><summary>${title} <small>${esc(values().address1 || values().billing_address1 || "Add details")} · Edit</small></summary>${content}</details>`;
        return group(title, content);
      })
      .join("");
    if (state.layout === "express" && state.family === "shopify")
      html =
        `<div class="express"><b>Express checkout · fictional saved profile</b><p>Review your saved address and purchase preferences below.</p></div>` +
        html;
    if (state.layout === "one-page") html += group("Payment", payment());
    return html;
  }
  function authControls() {
    const a = state.auth;
    if (!a)
      return (
        "<p>Authentication complete. Return to checkout.</p>" +
        button("Return to checkout", "back", "primary")
      );
    return `<div class="auth-card"><span class="eyebrow">SYNTHETIC ${a.purpose.toUpperCase()} AUTHENTICATION</span><h2>${a.status === "approved" ? "Approval received" : "Verify with the test user"}</h2><p>No real OTP or bank credentials. Only the separate test-user simulator supplies approval.</p><p class="auth-clock">Code expires in <b>${a.seconds_remaining}</b>s · ${a.status}</p>${a.status === "approved" ? button("Return to checkout", "return_auth") : a.status === "locked" ? button("Request user intervention", "help") : `<div class="otp">${Array.from({ length: a.digits }, (_, i) => `<input aria-label="OTP digit ${i + 1}" inputmode="numeric" maxlength="1" data-digit="${i}">`).join("")}</div><div class="row">${button("Verify synthetic code", "verify", "secondary")}${button("Resend code", "resend", "text-button")}</div>${button(a.requested && ["waiting", "delayed"].includes(a.status) ? "Waiting for test-user approval" : "Request user authorisation", "request_auth", "primary", a.requested ? "disabled" : "")}<p class="muted">${state.evaluation_mode === "handoff" ? "The benchmark stops at a reported handoff." : "The test user approves after your request; wait, then return."}</p>`}</div>`;
  }
  function body() {
    const stage = state.stage;
    if (stage === "details" || stage === "shipping")
      return (
        details() +
        `<div class="footer-action">${button(state.family === "echallan" ? "Find challans" : state.layout === "three-page" && stage === "details" ? "Continue to shipping" : "Review details", "continue")}</div>`
      );
    if (stage === "ledger")
      return group(
        "Your synthetic notices",
        `<table><thead><tr><th>Notice</th><th>Amount</th><th>Status</th><th>Action</th></tr></thead><tbody>${[
          ["DEMO-CH-1001", "₹500", "Paid"],
          ["DEMO-CH-1002", "₹1,200", state.ledger_status],
        ]
          .map(
            ([id, amount, status]) =>
              `<tr><td>${id}</td><td>${amount}</td><td><span class="pill">${status}</span></td><td>${button("Inspect " + id, "select_challan", "secondary", `data-challan="${id}"`)}</td></tr>`,
          )
          .join(
            "",
          )}</tbody></table>${button("Check transaction status", "check_status", "secondary")}`,
      );
    if (stage === "settled")
      return group(
        "Already paid",
        `<p>This challan is settled. Do not submit another payment.</p>${button("Report settled — stop safely", "help")}`,
      );
    if (stage === "expired")
      return group(
        "Session expired",
        `<p>Your entered details have been saved.</p>${button("Resume saved session", "resume")}`,
      );
    if (stage === "blocked" || stage === "captcha")
      return group(
        stage === "captcha"
          ? "Mock CAPTCHA challenge"
          : "Application unavailable",
        `<p>${esc(state.error)}</p>${button("Request user intervention", "help")}`,
      );
    if (stage === "review")
      return group(
        state.family === "railway" ? "Review journey" : "Review before payment",
        `${state.review_notice ? `<div class="notice">${state.review_notice}</div>` : ""}<dl class="review-list">${state.fields
          .filter(
            (f) =>
              values()[f.key] &&
              (!f.when ||
                Object.entries(f.when).every(([k, v]) => values()[k] === v)),
          )
          .map(
            (f) =>
              `<div><dt>${esc(f.label)}</dt><dd>${esc(values()[f.key])}</dd></div>`,
          )
          .join("")}</dl>${button("Confirm review and continue", "review")}`,
      );
    if (stage === "payment")
      return group(
        "Choose payment",
        state.family === "link" && state.variant === "embedded"
          ? `<p>Payment Element · isolated embedded component</p><iframe class="payment-frame" title="Embedded payment component" src="${base}/component"></iframe>`
          : payment() + button("Prepare selected payment", "pay"),
      );
    if (stage === "gateway")
      return group(
        "Demo bank gateway",
        `<p>You are entering the local simulated payment gateway. Reference ${esc(state.transaction)}.</p>${state.auth_surface === "redirect" ? `<a class="primary" href="${base}/gateway">Continue to simulated bank</a>` : button("Continue to simulated bank", "gateway")}`,
      );
    if (stage === "auth") {
      if (state.auth_surface === "iframe")
        return `<iframe class="auth-frame" title="Synthetic authentication challenge" src="${base}/challenge"></iframe>`;
      if (state.auth_surface === "popup")
        return group(
          "Bank authentication window",
          `<p>Open the separate authentication window, request approval, then return here.</p>${button("Open authentication window", "popup")}`,
        );
      if (state.auth_surface === "redirect")
        return `<a class="primary" href="${base}/challenge">Continue to authentication page</a>`;
      return `<dialog open aria-label="Authentication">${authControls()}</dialog>`;
    }
    if (["pending", "gateway_interrupted", "failure"].includes(stage))
      return group(
        "Verify payment status",
        `<p>${esc(state.error || "A previous transaction needs checking.")}</p>${button("Check transaction status", "check_status")}`,
      );
    if (stage === "gateway_return")
      return group(
        "Return to merchant",
        `<p>Authentication was simulated. Verify the result before continuing.</p>${button("Return and verify transaction", "finish")}`,
      );
    const title =
      {
        checkout_ready: "Checkout ready",
        authentication_required: "Authentication required",
        payment_successful_simulation: "Payment successful in simulation",
        safe_abort: "Stopped safely",
        payment_failed: "Payment failed",
      }[stage] || stage;
    return `<section class="outcome"><div class="outcome-icon">${stage === "safe_abort" ? "Ⅱ" : "✓"}</div><h1>${title}</h1><p>${stage === "authentication_required" ? "User authorisation has been requested. No payment has been completed." : stage === "safe_abort" ? "The unresolved condition has been reported for user intervention." : stage === "checkout_ready" ? "Preparation complete. No money has moved." : "Fictional transaction only. No real money or account was involved."}</p><span class="pill">BENCHMARK SIMULATION</span>${state.family === "passport" ? "<p>Appointment confirmation · DEMO-ARN-2026-0042</p>" : state.family === "railway" ? "<p>Booking reference · DEMO-RAIL-042</p>" : ""}</section>`;
  }
  function render() {
    const family = state.family,
      m = state.merchant,
      part = parts[3],
      sub = part === "challenge" || part === "component" || part === "gateway";
    document.body.className = `family-${family} variant-${state.variant} ${state.variant === "legacy" ? "legacy" : ""} ${sub ? "subpage" : ""}`;
    if (sub) {
      root.innerHTML = `<div class="simulation-banner">CHECKOUTBENCH · FICTIONAL ${part === "component" ? "PAYMENT COMPONENT" : "AUTHENTICATION"} · NO REAL PAYMENTS</div><main class="submain"><div role="alert" class="error">${esc(state.error || "")}</div>${part === "component" ? (state.stage === "payment" ? payment() + button("Prepare selected payment", "pay") : body()) : part === "gateway" && state.stage === "gateway" ? group("Demo bank gateway", `<p>Local authentication. No external bank connection.</p>${button("Start authentication", "gateway")}`) : state.stage === "auth" ? authControls() : button("Return to checkout", "back")}</main>`;
      bind();
      return;
    }
    const names = {
      link: "Papertrail Studio",
      railway: "DemoRail Booking Lab",
      passport: "Civic Appointment Lab",
      echallan: "Road Notice Lab",
      stripe: "PAPER & FORM",
      razor: "Northstar Store",
      cashfree: "River Market",
      generic: "Everyday Supply",
    };
    const name = m?.brand || names[family];
    root.innerHTML = `<div class="simulation-banner">CHECKOUTBENCH · FICTIONAL BENCHMARK SIMULATION · SYNTHETIC DATA ONLY · NO REAL PAYMENTS</div><header class="brand-header"><a href="#" class="brand">${esc(name)}</a><span>Secure local simulation <span aria-hidden="true">◇</span></span></header><div class="shell"><aside class="order-summary"><div class="eyebrow">${["passport", "echallan"].includes(family) ? "SERVICE OVERVIEW" : family === "railway" ? "JOURNEY SUMMARY" : "YOUR ORDER"}</div><div class="product-art" aria-hidden="true"><svg viewBox="0 0 160 140"><path d="M40 95 55 35 110 35 125 95 95 120 65 120Z"/><circle cx="82" cy="63" r="19"/><path d="M52 110h60"/></svg></div><h2>${esc(m?.product || { link: "Studio essentials", railway: "Sample Express · DEMO 042", passport: "Appointment service", echallan: "Synthetic traffic notice" }[family] || "Everyday essentials")}</h2><p>${esc(m?.tagline || "Original interface · documented workflow inspiration")}</p><div class="order-total"><span>${family === "railway" ? "Current fare" : "Total"}</span><b>${family === "link" ? "$48.00" : "₹" + (family === "railway" ? state.fare : m?.price || 1200).toLocaleString("en-IN")}</b></div><p class="muted">${family === "link" ? "US test merchant · USD · card-funded Link simulation. Link is distinct from UPI." : "All prices are fictional. No real payment will be attempted."}</p><ol class="stage-list">${["Details", "Review", "Payment", "Confirmation"].map((t) => `<li>${t}</li>`).join("")}</ol></aside><main id="workflow"><nav class="breadcrumbs">${state.layout === "three-page" ? "Information › Shipping › Payment" : state.variant === "legacy" ? "Train selected | Passenger details | Journey review | Payment" : `Checkout / ${esc(state.stage.replaceAll("_", " "))}`}</nav><div role="alert" class="error">${esc(state.error || "")}</div>${body()}<datalist id="address-suggestions"><option value="14B Maple Residency, Test Road"><option value="27 Sample House, Example Lane"><option value="8C Fictional Apartments, Demo Road"></datalist><footer class="checkout-footer">Fictional ${family} workflow · No affiliation with any payment provider or government service.</footer></main></div>`;
    root.querySelectorAll("merchant-extension").forEach((e) => {
      e.attachShadow({ mode: "open" }).innerHTML =
        `<style>:host{display:block}label{display:block;margin:12px 0;font:14px system-ui}input,select{padding:12px;border:1px solid #bbb;border-radius:6px;max-width:100%;box-sizing:border-box}input:not([type=checkbox]){width:100%}</style>` +
        e.dataset.content;
    });
    bind();
  }
  function bind() {
    const all = [root, ...root.querySelectorAll("merchant-extension")].map(
      (e) => e.shadowRoot || e,
    );
    all.forEach((el) =>
      el.querySelectorAll("input,select,textarea").forEach((e) =>
        e.addEventListener("change", () => {
          local = collect();
          if (
            e.type === "radio" ||
            e.type === "checkbox" ||
            ["delivery_method", "purchase", "scheme"].includes(e.name)
          )
            render();
        }),
      ),
    );
    root.querySelectorAll("[data-action]").forEach((e) =>
      e.addEventListener("click", () => {
        const a = e.dataset.action;
        if (a === "popup") {
          window.open(
            base + "/challenge",
            "checkoutbench-auth",
            "width=520,height=700",
          );
          opened = true;
          return;
        }
        if (a === "back") {
          if (window.opener) {
            window.close();
          } else location.href = "/checkout/" + token;
          return;
        }
        if (a === "verify") {
          act(a, {
            code: [...root.querySelectorAll("[data-digit]")]
              .map((x) => x.value)
              .join(""),
          });
          return;
        }
        act(a, e.dataset.challan ? { challan: e.dataset.challan } : {});
      }),
    );
    root.querySelectorAll("[data-digit]").forEach((e) =>
      e.addEventListener("input", () => {
        if (e.value)
          root
            .querySelector(`[data-digit="${Number(e.dataset.digit) + 1}"]`)
            ?.focus();
      }),
    );
  }
  async function poll() {
    try {
      const next = await fetch(base + "/state").then((r) => r.json());
      if (
        state &&
        state.auth_surface === "iframe" &&
        !parts[3] &&
        state.stage === "auth" &&
        next.stage === "auth"
      ) {
        state = next;
        return;
      }
      if (
        !state ||
        (["auth", "authentication_required"].includes(state.stage) &&
          JSON.stringify({
            ...next,
            auth: next.auth ? { ...next.auth, seconds_remaining: 0 } : null,
          }) !==
            JSON.stringify({
              ...state,
              auth: state.auth ? { ...state.auth, seconds_remaining: 0 } : null,
            })) ||
        next.stage !== state.stage
      ) {
        state = next;
        local = {};
        render();
      } else if (state.auth) {
        state.auth.seconds_remaining = next.auth?.seconds_remaining || 0;
        root
          .querySelector(".auth-clock b")
          ?.replaceChildren(
            document.createTextNode(String(state.auth.seconds_remaining)),
          );
      }
    } catch (e) {
      if (!state) root.textContent = "Local checkout unavailable.";
    }
  }
  poll();
  setInterval(() => {
    if (!busy && state) poll();
  }, 350);
})();
