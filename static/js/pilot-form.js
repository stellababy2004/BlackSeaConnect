(function () {
  const DEFAULT_TO = "blackseaconnect@orange.fr";
  const DEFAULT_SUBJECT = "BlackSea Connect pilot access request";
  const LINE_BREAK = "\n";
  const SELECTOR = "[data-pilot-select]";
  const selectInstances = new Set();
  let documentListenerBound = false;
  let languageListenerBound = false;

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

  function getSelectOptionKey(option) {
    return (
      option.getAttribute("data-value-key") ||
      option.getAttribute("data-i18n") ||
      (option.dataset && option.dataset.value) ||
      option.textContent.trim()
    );
  }

  function getSelectOptionText(option) {
    return (option.textContent || "").trim();
  }

  function closeSelect(wrapper, focusTrigger) {
    const trigger = wrapper.querySelector("[data-pilot-select-trigger]");
    const panel = wrapper.querySelector("[data-pilot-select-panel]");
    if (!trigger || !panel) {
      return;
    }

    wrapper.classList.remove("is-open");
    trigger.setAttribute("aria-expanded", "false");
    panel.hidden = true;

    if (focusTrigger) {
      trigger.focus();
    }
  }

  function updateSelectState(wrapper) {
    const trigger = wrapper.querySelector("[data-pilot-select-trigger]");
    const panel = wrapper.querySelector("[data-pilot-select-panel]");
    const input = wrapper.querySelector("[data-pilot-select-input]");
    const placeholder = wrapper.querySelector("[data-pilot-select-placeholder]");
    const valueNode = wrapper.querySelector("[data-pilot-select-value]");
    const options = Array.from(wrapper.querySelectorAll("[data-pilot-select-option]"));
    const selectedKey = wrapper.getAttribute("data-selected-key") || "";
    const selectedOption = options.find((option) => getSelectOptionKey(option) === selectedKey);

    if (!trigger || !panel || !input || !placeholder || !valueNode) {
      return;
    }

    options.forEach((option) => {
      const isSelected = getSelectOptionKey(option) === selectedKey;
      option.classList.toggle("is-selected", isSelected);
      option.setAttribute("aria-selected", isSelected ? "true" : "false");
    });

    if (selectedOption) {
      const selectedText = getSelectOptionText(selectedOption);
      input.value = selectedText;
      placeholder.hidden = true;
      valueNode.hidden = false;
      valueNode.textContent = selectedText;
      trigger.classList.add("is-selected");
      trigger.setAttribute("aria-label", selectedText);
    } else {
      input.value = "";
      placeholder.hidden = false;
      valueNode.hidden = true;
      valueNode.textContent = "";
      trigger.classList.remove("is-selected");
      trigger.removeAttribute("aria-label");
    }

    panel.hidden = !wrapper.classList.contains("is-open");
  }

  function focusOption(wrapper, index) {
    const options = Array.from(wrapper.querySelectorAll("[data-pilot-select-option]"));
    if (!options.length) {
      return;
    }

    const nextIndex = Math.max(0, Math.min(index, options.length - 1));
    options[nextIndex].focus();
  }

  function openSelect(wrapper, focusIndex) {
    const trigger = wrapper.querySelector("[data-pilot-select-trigger]");
    const panel = wrapper.querySelector("[data-pilot-select-panel]");
    if (!trigger || !panel) {
      return;
    }

    selectInstances.forEach((openWrapper) => {
      if (openWrapper !== wrapper) {
        closeSelect(openWrapper, false);
      }
    });

    wrapper.classList.add("is-open");
    trigger.setAttribute("aria-expanded", "true");
    panel.hidden = false;
    updateSelectState(wrapper);

    if (typeof focusIndex === "number") {
      focusOption(wrapper, focusIndex);
    }
  }

  function toggleSelect(wrapper) {
    if (wrapper.classList.contains("is-open")) {
      closeSelect(wrapper, true);
      return;
    }

    openSelect(wrapper);
  }

  function selectOption(wrapper, option) {
    wrapper.setAttribute("data-selected-key", getSelectOptionKey(option));
    updateSelectState(wrapper);
    closeSelect(wrapper, true);
  }

  function moveFocus(wrapper, currentOption, direction) {
    const options = Array.from(wrapper.querySelectorAll("[data-pilot-select-option]"));
    const currentIndex = options.indexOf(currentOption);
    if (currentIndex === -1) {
      return;
    }

    const nextIndex = Math.max(0, Math.min(options.length - 1, currentIndex + direction));
    options[nextIndex].focus();
  }

  function attachCustomSelect(wrapper) {
    if (wrapper.dataset.pilotSelectBound === "true") {
      return;
    }

    const trigger = wrapper.querySelector("[data-pilot-select-trigger]");
    const panel = wrapper.querySelector("[data-pilot-select-panel]");
    const options = Array.from(wrapper.querySelectorAll("[data-pilot-select-option]"));

    if (!trigger || !panel || !options.length) {
      return;
    }

    wrapper.dataset.pilotSelectBound = "true";
    selectInstances.add(wrapper);

    trigger.setAttribute("aria-haspopup", "listbox");
    trigger.setAttribute("aria-expanded", "false");
    panel.hidden = true;

    trigger.addEventListener("click", function () {
      toggleSelect(wrapper);
    });

    trigger.addEventListener("keydown", function (event) {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        openSelect(wrapper, 0);
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        openSelect(wrapper, options.length - 1);
      } else if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        toggleSelect(wrapper);
      } else if (event.key === "Escape") {
        event.preventDefault();
        closeSelect(wrapper, true);
      }
    });

    options.forEach((option, index) => {
      option.addEventListener("click", function () {
        selectOption(wrapper, option);
      });

      option.addEventListener("keydown", function (event) {
        if (event.key === "ArrowDown") {
          event.preventDefault();
          moveFocus(wrapper, option, 1);
        } else if (event.key === "ArrowUp") {
          event.preventDefault();
          moveFocus(wrapper, option, -1);
        } else if (event.key === "Home") {
          event.preventDefault();
          focusOption(wrapper, 0);
        } else if (event.key === "End") {
          event.preventDefault();
          focusOption(wrapper, options.length - 1);
        } else if (event.key === "Escape") {
          event.preventDefault();
          closeSelect(wrapper, true);
        }
      });

      option.setAttribute("tabindex", "0");
      option.setAttribute("role", "option");
      option.setAttribute("aria-selected", index === 0 ? "false" : "false");
    });

    updateSelectState(wrapper);
  }

  function initCustomSelects() {
    document.querySelectorAll(SELECTOR).forEach(attachCustomSelect);
  }

  function refreshCustomSelects() {
    selectInstances.forEach((wrapper) => {
      updateSelectState(wrapper);
    });
  }

  function bindDocumentListeners() {
    if (!documentListenerBound) {
      document.addEventListener("click", function (event) {
        selectInstances.forEach((wrapper) => {
          if (wrapper.classList.contains("is-open") && !wrapper.contains(event.target)) {
            closeSelect(wrapper, false);
          }
        });
      });

      document.addEventListener("keydown", function (event) {
        if (event.key !== "Escape") {
          return;
        }

        selectInstances.forEach((wrapper) => {
          if (wrapper.classList.contains("is-open")) {
            closeSelect(wrapper, true);
          }
        });
      });

      documentListenerBound = true;
    }

    if (!languageListenerBound) {
      window.addEventListener("blacksea:languagechange", function () {
        refreshCustomSelects();
      });

      languageListenerBound = true;
    }
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
    bindDocumentListeners();
    document.querySelectorAll("form[data-pilot-form]").forEach(attach);
    initCustomSelects();
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
