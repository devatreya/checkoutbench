(() => {
  const parts = location.pathname.split("/"),
    token = parts[1] === "checkout" ? parts[2] : parts[2],
    base = "/v21/" + token;
  const root = document.getElementById("root");
  let state,
    local = {},
    opened = false,
    expandedSummaries = new Set(),
    busy = false,
    revision = 0;
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
    revision++;
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
      if (action === "launch" && state.family === "cashfree") {
        if (state.variant === "popup")
          window.open(
            base + "/provider",
            "checkoutbench-provider",
            "width=650,height=820",
          );
        else if (state.variant !== "inline") location.href = base + "/provider";
      }
      if (
        action === "finish" &&
        state.stage === "payment_successful_simulation" &&
        parts[3]
      ) {
        if (window.opener) window.close();
        else if (window.top === window.self)
          location.href = "/checkout/" + token;
      }
      if (action === "open_verification")
        location.href = base + "/verification";
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
    return `<label class="field" for="${f.key}"><span>${esc(f.label)}${f.required ? "" : " <small>Optional</small>"}</span>${f.options ? `<select ${attrs}><option value="">Select…</option>${f.options.map((x) => `<option ${x === val ? "selected" : ""}>${esc(x)}</option>`).join("")}</select>` : `<input ${attrs} type="${["number", "email"].includes(f.kind) ? f.kind : "text"}" value="${esc(val)}" ${f.label.toLowerCase().includes("address") ? 'list="address-suggestions" autocomplete="off"' : ""}>`}</label>`;
  }
  function fields(fs) {
    return fs
      .map((f) => {
        let html = input(f);
        if (state.accessibility_defect)
          html = html
            .replace(/ aria-label="[^"]*"/g, "")
            .replace(/<label/g, "<div")
            .replace(/<\/label>/g, "</div>")
            .replace(/ for="[^"]*"/g, "");
        return html;
      })
      .join("");
  }
  const group = (title, html, cls = "") =>
    `<section class="panel ${cls}"><h2>${title}</h2>${html}</section>`;

  const methodLabel = {
    card: "Card",
    us_bank_account: "US bank account",
    link: "Link · saved payment",
    upi_qr: "UPI QR",
    upi_app: "UPI intent",
    upi_vpa: "Legacy UPI ID (iOS exception)",
    netbanking: "Netbanking",
    cod: "Cash on delivery",
  };
  function choice(f, options) {
    const val = values()[f.key] || "";
    return `<label class="field" for="${f.key}"><span>${esc(f.label)}</span><select id="${f.key}" name="${f.key}" aria-label="${esc(f.label)}"><option value="">Select…</option>${options.map((o) => `<option value="${esc(o.id)}" ${o.id === val ? "selected" : ""} ${o.disabled ? "disabled" : ""}>${esc(o.label)}</option>`).join("")}</select></label>`;
  }
  function payment() {
    const selected = values()[state.method_control.key] || "";
    const methods = state.payment_order || state.methods;
    let html =
      state.payment_ui === "select"
        ? choice(
            state.method_control,
            methods.map((m) => ({ id: m, label: methodLabel[m] })),
          )
        : `<div id="${state.method_control.key}" role="radiogroup" aria-label="Payment method" class="method-${state.payment_ui}"><input type="hidden" name="${state.method_control.key}" value="${selected}">${methods.map((m) => `<button type="button" role="radio" data-value="${m}" data-method="${m}" aria-checked="${selected === m}">${methodLabel[m]}</button>`).join("")}</div>`;
    if (state.family === "stripe")
      html +=
        '<p class="muted">Local Payment Element approximation. Browser wallets are not configured for this test session.</p>';
    if (selected === "us_bank_account")
      html +=
        "<p>Connect a US test bank account through user authorisation. No account credentials are requested here.</p>";
    if (selected === "card")
      html += `<div class="card-element"><span class="muted">Test payment information · isolated local simulation</span><div class="grid">${fields(state.payment_fields)}</div></div>`;
    if (selected === "upi_app")
      html += `<p>Continue on this mobile device with an installed test wallet. External app launch is represented by a handoff.</p>${input(state.app_control)}`;
    if (selected === "upi_vpa")
      html += `<p>iOS Collect exception simulation. Not offered on Android or desktop.</p>${input(state.vpa_control)}`;
    if (selected === "netbanking") html += input(state.bank_control);
    if (selected === "cod")
      html +=
        "<p>Cash on delivery · available for the supplied serviceable PIN. No online payment will be collected.</p>";
    if (selected === "link")
      html += state.link_authenticated
        ? choice(
            state.saved_control,
            state.cards.map((c) => ({
              ...c,
              disabled: c.expired,
              label: c.label + (c.expired ? " · Expired" : ""),
            })),
          )
        : "<p>Sign in from Contact to use Link.</p>";
    if (selected === "upi_qr")
      html += state.qr_url
        ? `<div class="qr-box"><img alt="Synthetic payment QR code" src="${state.qr_url}" width="${state.qr_size}" height="${state.qr_size}"><p>${esc(state.qr_notice)}</p><div class="row">${button("Enlarge displayed QR", "qr_enlarge", "secondary")}${button("Request full-resolution QR", "qr_fullsize", "secondary")}${button("Regenerate QR", "qr_refresh", "secondary")}${button("Request user intervention", "help", "secondary")}</div></div>`
        : button("Show QR code", "show_qr", "secondary");
    return html;
  }
  function linkLogin() {
    const email = state.fields.find((f) =>
      f.label.toLowerCase().includes("email"),
    );
    return `<section class="link-wallet"><strong>link · LOCAL SIMULATION</strong><p>US test merchant · USD · Link is unavailable in India.</p>${state.link_authenticated ? `<p>Signed in as ${esc(values()[email?.key])}</p>${button("Use a different account", "signout", "secondary")}` : state.link_status === "signup" ? `<p>No saved account. Account creation requires explicit consent.</p>${input(state.consent_control)}${group("Payment information to save", fields(state.payment_fields))}${button("Create synthetic account", "register")}${button("Continue without Link", "manual_card", "secondary")}` : state.link_status === "declined" ? "<p>Ordinary card checkout selected.</p>" : `${email ? input(email) : ""}${button("Continue with Link", "recognize")}${button("Use ordinary card checkout", "manual_card", "secondary")}`}</section>`;
  }
  function details() {
    const fs = state.fields,
      groups = [...new Set(fs.map((f) => f.section))];
    if (state.family === "railway") {
      const passengers = groups.filter((g) => g.startsWith("Passenger"));
      const table = `<div class="table-scroll"><table class="passenger-table"><caption>Passenger particulars · browser workflow approximation</caption><thead><tr><th>Traveller</th><th>Name</th><th>Age</th><th>Berth preference</th><th>Gender</th><th>Nationality</th></tr></thead><tbody>${passengers
        .map(
          (g) =>
            `<tr><th>${g}</th>${fs
              .filter((f) => f.section === g)
              .map((f) => `<td>${input(f)}</td>`)
              .join("")}</tr>`,
        )
        .join("")}</tbody></table></div>`;
      return `<div class="journey-strip"><b>DEMO 042 · SAMPLE EXPRESS</b><span>SMC → DMT · 14 Nov · 3A · General quota</span></div><p>Destination: DMT · Demo Terminal. Boarding may differ from journey origin.</p>${button("Use saved first passenger", "saved_passenger", "secondary")}${table}${group("Reservation preferences", fields(fs.filter((f) => !f.section.startsWith("Passenger"))))}<aside class="ad-panel">FICTIONAL TRAVEL NOTICE · No real booking or passenger identifiers.</aside>`;
    }
    if (state.family === "passport")
      return `<div class="application-card"><span>SAVED APPLICATION · ${state.variant === "legacy" ? "HISTORICAL REFERENCE" : "REFRESHED WEB APPROXIMATION"}</span><h2>${esc(state.application_summary.reference)}</h2><p>${esc(state.application_summary.name)} · No real documents required</p></div>${groups
        .filter((g) =>
          fs.some(
            (f) =>
              f.section === g &&
              (!f.when ||
                Object.entries(f.when).every(([k, v]) => values()[k] === v)),
          ),
        )
        .map((g) =>
          group(
            g,
            `<div class="${state.variant === "legacy" ? "legacy-form" : "grid"}">${fields(fs.filter((f) => f.section === g))}</div>`,
          ),
        )
        .join("")}`;
    if (state.family === "echallan")
      return group(
        "Find a synthetic notice",
        `<p>Select challan, vehicle or driving licence lookup. DEMO identifiers only.</p>${fields(fs)}`,
      );
    if (
      state.family === "shopify" &&
      state.layout === "express" &&
      !state.accelerated_authenticated
    )
      return group(
        "Shop Pay-style accelerated checkout",
        `<p>Authenticate your saved checkout session before reviewing delivery and payment.</p>${button("Authenticate accelerated checkout", "accelerated_login")}`,
      );
    let html = state.family === "link" && state.link_enabled ? linkLogin() : "";
    html += groups
      .map((section) => {
        let subset = fs.filter(
          (f) =>
            f.section === section &&
            !(
              state.family === "link" &&
              state.link_enabled &&
              f.label.toLowerCase().includes("email")
            ),
        );
        if (state.family === "generic" && state.variant === "address-book")
          subset = subset.filter((f) =>
            state.merchant_stage === "address"
              ? f.section !== "Options"
              : f.section === "Options",
          );
        if (!subset.length) return "";
        const content = `<div class="${state.variant === "compact" ? "compact-form" : "grid"}">${fields(subset)}</div>`;
        const title =
          {
            contact: "Contact",
            delivery: "Delivery",
            billing: "Billing address",
            shipping: "Delivery options & merchant extras",
          }[section] || section;
        if (
          (state.layout === "express" || state.link_authenticated) &&
          ["delivery", "billing"].includes(section)
        )
          return `<details class="panel rollup" ${expandedSummaries.has(title + " · Review saved details") ? "open" : ""}><summary>${title} · Review saved details</summary>${content}</details>`;
        if (state.family === "shopify" && section === "shipping")
          return group(
            title,
            `<iframe class="merchant-extension-frame" sandbox="allow-scripts" title="Merchant options sandbox" src="${base}/extension"></iframe>`,
          );
        if (state.shadow)
          return group(
            title,
            `<merchant-extension data-content="${esc(content)}"></merchant-extension><p>Generic shadow DOM stress test; unrelated to Shopify runtime.</p>`,
          );
        return group(title, content);
      })
      .join("");
    if (state.family === "generic" && state.variant === "address-book")
      html =
        '<p class="notice">Saved address · review the prefilled PIN before continuing.</p>' +
        html;
    if (
      state.family === "shopify" &&
      ["one-page", "express"].includes(state.layout)
    )
      html += group("Payment", payment());
    return html;
  }
  function providerPayment() {
    const content = payment() + button("Prepare selected payment", "pay");
    if (state.family === "razor")
      return `<dialog open class="razor-modal" aria-label="Standard checkout"><header><b>Northstar Store</b>${button("Dismiss payment gateway", "dismiss", "secondary")}</header><p>Order DEMO-ORDER · ₹1,200 · Contact prefilled from checkout</p><dl class="provider-contact">${Object.entries(
        state.provider_contact || {},
      )
        .map(([k, v]) => `<div><dt>${k}</dt><dd>${esc(v)}</dd></div>`)
        .join(
          "",
        )}</dl><nav class="provider-menu">Cards · UPI · Netbanking</nav>${content}<p>Callback result is verified by the local merchant server.</p></dialog>`;
    return group(
      state.family === "cashfree"
        ? "River Market · payment session"
        : "Payment details",
      content,
    );
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
    if (stage === "details" || stage === "shipping") {
      const single =
        state.family === "shopify" &&
        ["one-page", "express"].includes(state.layout);
      const locked =
        state.family === "shopify" &&
        state.layout === "express" &&
        !state.accelerated_authenticated;
      const application =
        state.family === "passport" &&
        state.variant === "refreshed" &&
        state.passport_step === "application";
      const address =
        state.family === "generic" &&
        state.variant === "address-book" &&
        state.merchant_stage === "address";
      return (
        details() +
        (locked
          ? ""
          : `<div class="footer-action">${button(single ? "Prepare selected payment" : application ? "Choose appointment" : address ? "Continue with this address" : state.family === "echallan" ? "Find challans" : state.layout === "three-page" ? (stage === "details" ? "Continue to shipping" : "Continue to payment") : "Review details", single ? "pay" : application ? "application_next" : address ? "address_next" : "continue")}</div>`)
      );
    }
    if (stage === "verification")
      return group(
        "Payment transaction verification",
        `<p>Verify the pending transaction before starting another payment.</p>${button("Check transaction status", "check_status")}`,
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
          )}</tbody></table>${button("Open transaction verification", "open_verification", "secondary")}`,
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
    if (stage === "payment") {
      if (["razor", "cashfree"].includes(state.family)) {
        if (!state.gateway_open)
          return group(
            "Complete your order",
            `<p>Delivery details saved. Continue to the provider payment session.</p>${button("Launch payment gateway", "launch")}`,
          );
        if (parts[3] === "provider" || state.family === "razor")
          return providerPayment();
        if (state.variant === "inline")
          return `<iframe class="payment-frame" title="Cashfree inline checkout" src="${base}/provider"></iframe>`;
        return group(
          "Provider session launched",
          `<a class="primary" href="${base}/provider">Launch payment gateway</a><p>Return here after the provider response.</p>`,
        );
      }
      if (
        ((state.family === "stripe" && state.variant === "payment-element") ||
          (state.family === "link" && state.variant === "embedded")) &&
        parts[3] !== "component"
      )
        return `<iframe class="payment-frame" title="Isolated Payment Element" src="${base}/component"></iframe>`;
      return group(
        "Choose payment",
        payment() + button("Prepare selected payment", "pay"),
      );
    }
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
      sub = [
        "challenge",
        "component",
        "gateway",
        "provider",
        "verification",
      ].includes(part);
    document.body.className = `family-${family} variant-${state.variant} ${state.variant === "legacy" ? "legacy" : ""} ${sub ? "subpage" : ""}`;
    if (sub) {
      let content =
        part === "challenge"
          ? state.stage === "auth"
            ? authControls()
            : button("Return to checkout", "back")
          : part === "gateway" && state.stage === "gateway"
            ? group(
                "Demo bank gateway",
                button("Start authentication", "gateway"),
              )
            : body();
      root.innerHTML = `<div class="simulation-banner">CHECKOUTBENCH · FICTIONAL ${esc(part.toUpperCase())} · NO REAL PAYMENTS</div><main id="workflow" class="submain"><div role="alert" class="error">${esc(state.error || "")}</div>${content}</main>`;
      bind();
      return;
    }
    if (state.family === "stripe" && state.variant === "embedded") {
      root.innerHTML = `<div class="simulation-banner">CHECKOUTBENCH · FICTIONAL EMBEDDED CHECKOUT</div><header class="brand-header">PAPER & FORM · Merchant storefront</header><main id="workflow" class="embedded-shell"><aside><h1>Studio essentials</h1><p>₹1,200 · Local merchant order</p></aside><iframe title="Stripe-style embedded checkout" src="${base}/provider"></iframe></main>`;
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
    root.innerHTML = `<div class="simulation-banner">CHECKOUTBENCH · FICTIONAL BENCHMARK SIMULATION · SYNTHETIC DATA ONLY · NO REAL PAYMENTS</div><header class="brand-header"><a href="#" class="brand">${esc(name)}</a><span>Secure local simulation <span aria-hidden="true">◇</span></span></header><div class="shell"><aside class="order-summary"><div class="eyebrow">${["passport", "echallan"].includes(family) ? "SERVICE OVERVIEW" : family === "railway" ? "JOURNEY SUMMARY" : "YOUR ORDER"}</div><div class="product-art" aria-hidden="true"><svg viewBox="0 0 160 140"><path d="M40 95 55 35 110 35 125 95 95 120 65 120Z"/><circle cx="82" cy="63" r="19"/><path d="M52 110h60"/></svg></div><h2>${esc(m?.product || { link: "Studio essentials", railway: "Sample Express · DEMO 042", passport: "Appointment service", echallan: "Synthetic traffic notice" }[family] || "Everyday essentials")}</h2><p>${esc(m?.tagline || "Original interface · documented workflow inspiration")}</p><div class="order-total"><span>${family === "railway" ? "Current fare" : "Total"}</span><b>${state.market?.startsWith("US") ? "$48.00" : "₹" + (family === "railway" ? state.fare : m?.price || 1200).toLocaleString("en-IN")}</b></div><p class="muted">${family === "link" ? "US test merchant · USD · card-funded Link simulation. Link is distinct from UPI." : "All prices are fictional. No real payment will be attempted."}</p><ol class="stage-list">${(state.family === "shopify" ? (state.layout === "three-page" ? ["Information", "Shipping", "Payment"] : ["Contact · Delivery · Payment"]) : ["Details", "Review", "Payment", "Confirmation"]).map((t) => `<li>${t}</li>`).join("")}</ol></aside><main id="workflow"><nav class="breadcrumbs">${state.layout === "three-page" ? "Information › Shipping › Payment" : state.variant === "legacy" ? "Train selected | Passenger details | Journey review | Payment" : `Checkout / ${esc(state.stage.replaceAll("_", " "))}`}</nav><div role="alert" class="error">${esc(state.error || "")}</div>${body()}<datalist id="address-suggestions"><option value="14B Maple Residency, Test Road"><option value="27 Sample House, Example Lane"><option value="8C Fictional Apartments, Demo Road"></datalist><footer class="checkout-footer">Fictional ${family} workflow · No affiliation with any payment provider or government service.</footer></main></div>`;
    root.querySelectorAll("merchant-extension").forEach((e) => {
      e.attachShadow({ mode: "open" }).innerHTML =
        `<style>:host{display:block}label{display:block;margin:12px 0;font:14px system-ui}input,select{padding:12px;border:1px solid #bbb;border-radius:6px;max-width:100%;box-sizing:border-box}input:not([type=checkbox]){width:100%}</style>` +
        e.dataset.content;
    });
    bind();
  }
  window.addEventListener("message", (e) => {
    const frame = root.querySelector(".merchant-extension-frame");
    if (!frame || e.source !== frame.contentWindow) return;
    if (e.data?.type === "merchant-extension-size") {
      frame.style.height =
        Math.min(1400, Math.max(100, Number(e.data.height) + 25)) + "px";
      return;
    }
    if (e.data?.type !== "merchant-extension-change") return;
    const allowed = new Set(
      state.fields.filter((f) => f.section === "shipping").map((f) => f.key),
    );
    revision++;
    for (const [k, v] of Object.entries(e.data.values || {}))
      if (allowed.has(k)) local[k] = String(v).slice(0, 300);
  });
  function bind() {
    root.querySelectorAll("details.rollup").forEach((e) =>
      e.addEventListener("toggle", () => {
        const label = e.querySelector("summary").textContent;
        if (e.open) expandedSummaries.add(label);
        else expandedSummaries.delete(label);
      }),
    );
    root
      .querySelectorAll(".merchant-extension-frame")
      .forEach((frame) =>
        frame.addEventListener("load", () =>
          frame.contentWindow.postMessage(
            { type: "merchant-extension-context", values: values() },
            "*",
          ),
        ),
      );
    root.querySelectorAll("[data-method]").forEach((e) =>
      e.addEventListener("click", () => {
        revision++;
        local = { ...collect(), [state.method_control.key]: e.dataset.method };
        render();
      }),
    );
    const all = [root, ...root.querySelectorAll("merchant-extension")].map(
      (e) => e.shadowRoot || e,
    );
    all.forEach((el) =>
      el.querySelectorAll("input,select,textarea").forEach((e) =>
        e.addEventListener("change", () => {
          revision++;
          local = collect();
          if (
            e.type === "radio" ||
            e.type === "checkbox" ||
            e.tagName === "SELECT"
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
      const observedRevision = revision;
      const next = await fetch(base + "/state").then((r) => r.json());
      if (busy || observedRevision !== revision) return;
      if (
        state &&
        (state.auth_surface === "iframe" ||
          (state.family === "stripe" && state.variant === "embedded")) &&
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
