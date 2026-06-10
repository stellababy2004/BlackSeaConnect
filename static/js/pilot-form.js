document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("[data-pilot-form]");
  const response = document.querySelector("[data-pilot-response]");

  if (!form) return;

  form.addEventListener("submit", (event) => {
    event.preventDefault();

    const formData = new FormData(form);

    const name = formData.get("name") || "";
    const email = formData.get("email") || "";
    const propertyType = formData.get("property_type") || "";
    const location = formData.get("location") || "";
    const apartmentCount = formData.get("apartment_count") || "";
    const needs = formData.get("needs") || "";

    const subject = "BlackSea Connect Pilot Request";

    const body = `
Name: ${name}

Email: ${email}

Property Type: ${propertyType}

Region: ${location}

Property Count: ${apartmentCount}

Operational Needs:
${needs}
    `.trim();

    const mailto = `mailto:blackseaconnect@orange.fr?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;

    window.location.href = mailto;

    if (response) {
      response.textContent =
        "Pilot request prepared successfully.";
    }

    form.reset();
  });
});(function () {
  function initPilotSelect() {
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
        option.addEventListener("click", () => {
          input.value = option.textContent.trim();

          if (valueEl) {
            valueEl.textContent = option.textContent.trim();
            valueEl.hidden = false;
          }

          if (placeholder) {
            placeholder.hidden = true;
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
  }

  document.addEventListener("DOMContentLoaded", initPilotSelect);
})();
