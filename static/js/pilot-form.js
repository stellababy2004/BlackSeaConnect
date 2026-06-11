document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("[data-pilot-form]");
  const response = document.querySelector("[data-pilot-response]");

  document.querySelectorAll("[data-pilot-select]").forEach((select) => {
    const trigger = select.querySelector("[data-pilot-select-trigger]");
    const panel = select.querySelector("[data-pilot-select-panel]");
    const valueEl = select.querySelector("[data-pilot-select-value]");
    const placeholder = select.querySelector("[data-pilot-select-placeholder]");
    const input = select.querySelector("[data-pilot-select-input]");
    const options = select.querySelectorAll("[data-pilot-select-option]");

    if (!trigger || !panel || !input) return;

    const close = () => {
      trigger.setAttribute("aria-expanded", "false");
      panel.hidden = true;
    };

    trigger.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const open = trigger.getAttribute("aria-expanded") === "true";
      trigger.setAttribute("aria-expanded", String(!open));
      panel.hidden = open;
    });

    options.forEach((option) => {
      option.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();

        const selectedText = option.textContent.trim();
        input.value = selectedText;

        if (placeholder) placeholder.style.display = "none";
        if (valueEl) {
          valueEl.textContent = selectedText;
          valueEl.hidden = false;
          valueEl.style.display = "inline";
        }

        close();
      });
    });

    document.addEventListener("click", close);
  });

  if (!form) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const submitButton = form.querySelector('button[type="submit"]');
    const formData = new FormData(form);

    const payload = {
      name: String(formData.get("name") || "").trim(),
      email: String(formData.get("email") || "").trim(),
      property_type: String(formData.get("property_type") || "").trim(),
      location: String(formData.get("location") || "").trim(),
      apartment_count: String(formData.get("apartment_count") || "").trim(),
      needs: String(formData.get("needs") || "").trim(),
    };

    if (submitButton) submitButton.disabled = true;
    if (response) response.textContent = "Sending request...";

    try {
      const res = await fetch("/api/pilot-request", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
      });

      const data = await res.json();

      if (!res.ok || !data.ok) throw new Error(data.error || "Request failed");

      if (response) response.textContent = "Request received. We’ll reply within 1 business day.";
      form.reset();
    } catch (error) {
      if (response) response.textContent = "The request could not be sent. Please email concierge@blackseaconnect.com.";
    } finally {
      if (submitButton) submitButton.disabled = false;
    }
  });
});

