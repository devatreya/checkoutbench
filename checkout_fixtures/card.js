const card = {};
document.querySelectorAll("input").forEach((el) =>
  el.addEventListener("input", () => {
    if (el.id === "cardNumber")
      el.value = el.value
        .replace(/\D/g, "")
        .slice(0, 16)
        .replace(/(.{4})/g, "$1 ")
        .trim();
    card[el.id] = el.value;
    parent.postMessage({ type: "test-card", card }, location.origin);
  }),
);
