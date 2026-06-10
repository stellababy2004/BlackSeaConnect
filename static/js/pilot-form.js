document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("[data-pilot-form]");
  const response = document.querySelector("[data-pilot-response]");

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

    if (submitButton) {
      submitButton.disabled = true;
      submitButton.dataset.originalText = submitButton.textContent;
      submitButton.textContent = "Sending request...";
    }

    if (response) {
      response.textContent = "Preparing your pilot request...";
    }

    try {
      const res = await fetch("/api/pilot-request", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
      });

      const data = await res.json();

      if (!res.ok || !data.ok) {
        throw new Error(data.error || "Request failed");
      }

      if (response) {
        response.textContent = "Request received. We’ll reply within 1 business day.";
      }

      form.reset();

      document.querySelectorAll("[data-pilot-select]").forEach((select) => {
        const placeholder = select.querySelector("[data-pilot-select-placeholder]");
        const valueEl = select.querySelector("[data-pilot-select-value]");
        const input = select.querySelector("[data-pilot-select-input]");
        if (placeholder) placeholder.style.display = "inline";
        if (valueEl) {
          valueEl.textContent = "";
          valueEl.hidden = true;
        }
        if (input) input.value = "";
      });
    } catch (error) {
      if (response) {
        response.textContent = "The request could not be sent. Please try again or email blackseaconnect@orange.fr.";
      }
    } finally {
      if (submitButton) {
        submitButton.disabled = false;
        submitButton.textContent = submitButton.dataset.originalText || "Send pilot request";
      }
    }
  });

  document.querySelectorAll("[data-pilot-select]").forEach((select) => {
    const trigger = select.querySelector("[data-pilot-select-trigger]");
    const panel = select.querySelector("[data-pilot-select-panel]");
    const valueEl = select.querySelector("[data-pilot-select-value]");
    const placeholder = select.querySelector("[data-pilot-select-placeholder]");
    const input = select.querySelector("[data-pilot-select-input]");
    const options = select.querySelectorAll("[data-pilot-select-option]");

    if (!trigger || !panel || !input) return;

    trigger.addEventListener("click", () => {
      const isOpen = trigger.getAttribute("aria-expanded") === "true";
      trigger.setAttribute("aria-expanded", String(!isOpen));
      panel.hidden = isOpen;
    });

    options.forEach((option) => {
      option.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        const selectedText = option.textContent.trim();
        input.value = selectedText;

        if (valueEl) {
          valueEl.textContent = selectedText;
          valueEl.hidden = false;
        }

        if (placeholder) {
          placeholder.style.display = "none";
        }

        trigger.setAttribute("aria-expanded", "false");
        panel.hidden = true;
      });
    });

    document.addEventListener("click", (event) => {
      if (!select.contains(event.target)) {
        trigger.setAttribute("aria-expanded", "false");
        panel.hidden = true;
      }
    });
  });
});


