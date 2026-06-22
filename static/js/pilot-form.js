document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("[data-pilot-form]");
  const response = document.querySelector("[data-pilot-response]");
  const selects = Array.from(document.querySelectorAll("[data-pilot-select]"));
  let activeSelect = null;

  const getI18n = (key, fallback) => {
    const lang = (document.documentElement.lang || new URLSearchParams(window.location.search).get("lang") || "bg").toLowerCase();
    const dictionaries = window.BlackSeaI18N || {};
    const dictionary = dictionaries[lang] || dictionaries.bg || {};
    return dictionary[key] || fallback || "";
  };

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

    const getValue = (...names) => {
      for (const name of names) {
        const value = formData.get(name);
        if (typeof value === "string") {
          const trimmed = value.trim();
          if (trimmed) return trimmed;
        }
      }
      return "";
    };

    const payload = {
      name: getValue("name"),
      email: getValue("email"),
      property_type: getValue("property_type"),
      apartment_count: getValue("apartment_count"),
      city: getValue("city", "location", "region"),
      concierge_needs: getValue("concierge_needs", "needs"),
      current_language: document.documentElement.lang || "",
      location: getValue("location", "city", "region"),
      needs: getValue("needs", "concierge_needs"),
    };

    if (submitButton) submitButton.disabled = true;
    if (response) response.textContent = getI18n("pilotFormSending", "Sending request...");

    try {
      const res = await fetch("/api/pilot-request", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
      });

      const data = await res.json();

      if (!res.ok || !data.ok) throw new Error(data.error || "Request failed");

      if (response) response.textContent = getI18n("pilotFormSuccess", "Request received. We will contact you shortly.");
      form.reset();
    } catch (error) {
      if (response) response.textContent = getI18n("pilotFormError", "The request could not be sent. Please email concierge@blackseaconnect.com.");
    } finally {
      if (submitButton) submitButton.disabled = false;
    }
  });
});
