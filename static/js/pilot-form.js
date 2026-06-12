document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("[data-pilot-form]");
  const response = document.querySelector("[data-pilot-response]");
  const selects = Array.from(document.querySelectorAll("[data-pilot-select]"));
  let activeSelect = null;

  const closeSelect = (select) => {
    if (!select) return;

    const trigger = select.querySelector("[data-pilot-select-trigger]");
    const panel = select.querySelector("[data-pilot-select-panel]");
    if (!trigger || !panel) return;

    select.classList.remove("is-open");
    trigger.setAttribute("aria-expanded", "false");
    panel.hidden = true;

    if (activeSelect === select) {
      activeSelect = null;
    }
  };

  const openSelect = (select) => {
    if (!select) return;

    if (activeSelect && activeSelect !== select) {
      closeSelect(activeSelect);
    }

    const trigger = select.querySelector("[data-pilot-select-trigger]");
    const panel = select.querySelector("[data-pilot-select-panel]");
    if (!trigger || !panel) return;

    select.classList.add("is-open");
    trigger.setAttribute("aria-expanded", "true");
    panel.hidden = false;
    activeSelect = select;
  };

  selects.forEach((select) => {
    const trigger = select.querySelector("[data-pilot-select-trigger]");
    const panel = select.querySelector("[data-pilot-select-panel]");
    const valueEl = select.querySelector("[data-pilot-select-value]");
    const placeholder = select.querySelector("[data-pilot-select-placeholder]");
    const input = select.querySelector("[data-pilot-select-input]");
    const options = select.querySelectorAll("[data-pilot-select-option]");

    if (!trigger || !panel || !input) return;

    trigger.addEventListener("click", (event) => {
      event.preventDefault();

      const isOpen = select.classList.contains("is-open");
      if (isOpen) {
        closeSelect(select);
      } else {
        openSelect(select);
      }
    });

    options.forEach((option) => {
      option.addEventListener("click", (event) => {
        event.preventDefault();

        const selectedText = option.textContent.trim();
        const selectedValue = option.dataset.value || selectedText;

        input.value = selectedValue;

        if (placeholder) placeholder.hidden = true;
        if (valueEl) {
          valueEl.textContent = selectedText;
          valueEl.hidden = false;
        }

        closeSelect(select);
      });
    });
  });

  document.addEventListener("click", (event) => {
    if (!activeSelect) return;
    if (activeSelect.contains(event.target)) return;
    closeSelect(activeSelect);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || !activeSelect) return;
    const trigger = activeSelect.querySelector("[data-pilot-select-trigger]");
    closeSelect(activeSelect);
    if (trigger) trigger.focus();
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

