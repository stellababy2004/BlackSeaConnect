(function () {
  const DEFAULT_TO = "blackseaconnect@orange.fr";
  const DEFAULT_SUBJECT = "BlackSea Connect pilot access request";
  const LINE_BREAK = "\n";

  function getFieldLabel(field) {
    const label = field.closest("label");
    if (!label) {
      return field.name || field.id || "Field";
    }

    const labelNode = label.querySelector("span, label");
    const text = labelNode ? labelNode.textContent : label.textContent;
    return (text || field.name || field.id || "Field").trim();
  }

  function getFieldValue(field) {
    if (field.tagName === "SELECT") {
      const selected = field.options[field.selectedIndex];
      return selected ? selected.textContent.trim() : "";
    }

    if (field.type === "checkbox") {
      return field.checked ? "Yes" : "No";
    }

    return (field.value || "").trim();
  }

  function buildMailto(form) {
    const to = form.getAttribute("data-pilot-to") || DEFAULT_TO;
    const subject = form.getAttribute("data-pilot-subject") || DEFAULT_SUBJECT;
    const fields = Array.from(form.querySelectorAll("input, select, textarea"))
      .filter((field) => field.name && !field.disabled);
    const lines = fields
      .map((field) => {
        const value = getFieldValue(field);
        const label = getFieldLabel(field);
        return value ? `${label}: ${value}` : null;
      })
      .filter(Boolean);

    const bodyPrefix = form.getAttribute("data-pilot-body-prefix");
    const bodySuffix = form.getAttribute("data-pilot-body-suffix");
    const bodyParts = [];

    if (bodyPrefix) {
      bodyParts.push(bodyPrefix);
    }

    bodyParts.push(...lines);

    if (bodySuffix) {
      bodyParts.push("");
      bodyParts.push(bodySuffix);
    }

    const body = encodeURIComponent(bodyParts.join(LINE_BREAK));
    return `mailto:${to}?subject=${encodeURIComponent(subject)}&body=${body}`;
  }

  function getResponseNode(form) {
    return (
      form.querySelector("[data-pilot-response]") ||
      form.querySelector("[data-pilot-success]") ||
      null
    );
  }

  function submitForm(form) {
    const response = getResponseNode(form);
    const successMessage = response && response.textContent.trim()
      ? response.textContent.trim()
      : "Ще се отвори вашият email клиент с подготвена заявка.";

    if (response) {
      response.textContent = successMessage;
    }

    const mailto = buildMailto(form);
    window.location.href = mailto;
  }

  function attach(form) {
    if (form.dataset.pilotBound === "true") {
      return;
    }

    form.dataset.pilotBound = "true";
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      submitForm(form);
    });
  }

  function init() {
    document.querySelectorAll("form[data-pilot-form]").forEach(attach);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }

  window.BlackSeaPilotForm = {
    init: init,
    attach: attach,
    submitForm: submitForm
  };
}());
