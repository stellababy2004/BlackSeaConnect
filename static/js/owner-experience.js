(function () {
  "use strict";

  const pageLanguage = (document.documentElement.lang || "en").toLowerCase().split("-")[0];
  const supportedLanguage = ["en", "fr", "bg", "ru"].includes(pageLanguage) ? pageLanguage : "en";
  const statusLabels = {
    en: { NEW: "New", SCHEDULED: "Scheduled", IN_PROGRESS: "In progress", WAITING: "Waiting", COMPLETED: "Completed", CANCELLED: "Cancelled", URGENT: "Urgent", HIGH: "High", NORMAL: "Normal", LOW: "Low" },
    fr: { NEW: "Nouveau", SCHEDULED: "Planifié", IN_PROGRESS: "En cours", WAITING: "En attente", COMPLETED: "Terminé", CANCELLED: "Annulé", URGENT: "Urgent", HIGH: "Élevée", NORMAL: "Normale", LOW: "Faible" },
    bg: { NEW: "Нова", SCHEDULED: "Планирана", IN_PROGRESS: "В процес", WAITING: "В изчакване", COMPLETED: "Завършена", CANCELLED: "Отменена", URGENT: "Спешен", HIGH: "Висок", NORMAL: "Нормален", LOW: "Нисък" },
    ru: { NEW: "Новая", SCHEDULED: "Запланирована", IN_PROGRESS: "В работе", WAITING: "В ожидании", COMPLETED: "Завершена", CANCELLED: "Отменена", URGENT: "Срочный", HIGH: "Высокий", NORMAL: "Обычный", LOW: "Низкий" }
  };
  const loadingLabels = {
    en: "Saving…",
    fr: "Enregistrement…",
    bg: "Запазване…",
    ru: "Сохранение…"
  };

  document.querySelectorAll("[data-owner-status]").forEach(function (badge) {
    const normalized = (badge.dataset.ownerStatus || "").trim().toUpperCase().replace(/[\s-]+/g, "_");
    const label = statusLabels[supportedLanguage][normalized];
    if (!label) return;
    badge.textContent = label;
    badge.classList.add("owner-premium-badge", "owner-premium-badge--" + normalized.toLowerCase().replace(/_/g, "-"));
    badge.setAttribute("aria-label", label);
  });

  document.querySelectorAll("[data-owner-datetime]").forEach(function (element) {
    const rawValue = element.dataset.ownerDatetime || element.textContent.trim();
    if (!rawValue) return;
    const normalizedValue = /^\d{4}-\d{2}-\d{2} /.test(rawValue) ? rawValue.replace(" ", "T") : rawValue;
    const parsed = new Date(normalizedValue);
    if (Number.isNaN(parsed.getTime())) return;
    element.textContent = new Intl.DateTimeFormat(supportedLanguage, {
      dateStyle: "medium",
      timeStyle: rawValue.includes(":") ? "short" : undefined
    }).format(parsed);
    if (element.tagName === "TIME") element.dateTime = rawValue;
  });

  document.querySelectorAll("form[data-owner-submit-state]").forEach(function (form) {
    form.addEventListener("submit", function () {
      if (!form.checkValidity()) return;
      const button = form.querySelector('button[type="submit"]');
      if (!button || button.disabled) return;
      button.dataset.idleLabel = button.textContent;
      button.textContent = loadingLabels[supportedLanguage];
      button.disabled = true;
      button.classList.add("is-loading");
      button.setAttribute("aria-busy", "true");
    });
  });

  const propertyPage = document.querySelector(".owner-property-detail-page");
  if (propertyPage) {
    const tabOrder = ["overview", "property", "calendar", "operations", "knowledge", "equipment", "integrations"];
    const tabButtons = Array.from(propertyPage.querySelectorAll("[data-property-workspace-tab]"));
    const tabSections = Array.from(propertyPage.querySelectorAll("[data-property-tab-section]"));
    const propertyMain = propertyPage.querySelector("main.owner-property-detail-shell");
    const sourceGrid = propertyPage.querySelector("[data-property-tab-source]");
    const panels = {};

    if (propertyMain && tabButtons.length && tabSections.length) {
      const panelContainer = document.createElement("div");
      panelContainer.className = "owner-property-workspace-panels";
      tabOrder.forEach(function (tabId) {
        const panel = document.createElement("section");
        panel.className = "owner-property-workspace-panel";
        panel.id = "property-panel-" + tabId;
        panel.setAttribute("role", "tabpanel");
        panel.setAttribute("aria-labelledby", "property-tab-" + tabId);
        panel.hidden = tabId !== "overview";
        panels[tabId] = panel;
        panelContainer.appendChild(panel);
      });
      tabSections.forEach(function (section) {
        const target = panels[section.dataset.propertyTabSection];
        if (target) target.appendChild(section);
      });
      const setupSummary = Array.from(propertyMain.children).find(function (child) {
        return child.matches && child.matches("[data-owner-property-setup]");
      });
      if (setupSummary) {
        setupSummary.after(panelContainer);
      } else {
        propertyMain.prepend(panelContainer);
      }
      sourceGrid?.remove();

      const activateTab = function (tabId, updateHash) {
        if (!panels[tabId]) tabId = "overview";
        tabButtons.forEach(function (button) {
          const active = button.dataset.propertyWorkspaceTab === tabId;
          button.classList.toggle("is-active", active);
          button.setAttribute("aria-selected", active ? "true" : "false");
          button.tabIndex = active ? 0 : -1;
        });
        Object.keys(panels).forEach(function (panelId) {
          panels[panelId].hidden = panelId !== tabId;
        });
        if (updateHash) {
          window.history.replaceState(null, "", "#property-" + tabId);
        }
        const activeButton = tabButtons.find(function (button) {
          return button.dataset.propertyWorkspaceTab === tabId;
        });
        activeButton?.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
      };

      tabButtons.forEach(function (button, index) {
        button.addEventListener("click", function () {
          activateTab(button.dataset.propertyWorkspaceTab, true);
        });
        button.addEventListener("keydown", function (event) {
          if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
          event.preventDefault();
          let nextIndex = index;
          if (event.key === "ArrowLeft") nextIndex = (index - 1 + tabButtons.length) % tabButtons.length;
          if (event.key === "ArrowRight") nextIndex = (index + 1) % tabButtons.length;
          if (event.key === "Home") nextIndex = 0;
          if (event.key === "End") nextIndex = tabButtons.length - 1;
          tabButtons[nextIndex].focus();
          activateTab(tabButtons[nextIndex].dataset.propertyWorkspaceTab, true);
        });
      });

      const hashTab = window.location.hash.replace("#property-", "");
      activateTab(tabOrder.includes(hashTab) ? hashTab : "overview", false);
      propertyPage.classList.add("has-workspace-tabs");
      propertyPage._activatePropertyTab = activateTab;
    }

    const editToggle = propertyPage.querySelector("[data-property-edit-toggle]");
    if (editToggle) {
      editToggle.addEventListener("click", function () {
        const editing = propertyPage.classList.toggle("is-editing");
        editToggle.textContent = editing ? "Close editor" : "Edit profile";
        if (editing) {
          propertyPage._activatePropertyTab?.("property", true);
          propertyPage.querySelector("#property-panel-property")?.scrollIntoView({
            behavior: "smooth",
            block: "start"
          });
        }
      });
    }

    propertyPage.querySelectorAll(".owner-property-knowledge-section").forEach(function (section, index) {
      const heading = section.querySelector(":scope > h3");
      if (!heading) return;
      heading.tabIndex = 0;
      heading.setAttribute("role", "button");
      heading.setAttribute("aria-expanded", index === 0 ? "true" : "false");
      if (index === 0) section.classList.add("is-open");
      const toggle = function () {
        const open = section.classList.toggle("is-open");
        heading.setAttribute("aria-expanded", open ? "true" : "false");
      };
      heading.addEventListener("click", toggle);
      heading.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          toggle();
        }
      });
    });

    propertyPage.querySelectorAll(".owner-property-knowledge-card").forEach(function (card) {
      const title = card.querySelector(":scope > h4");
      if (!title) return;
      title.tabIndex = 0;
      title.setAttribute("role", "button");
      title.setAttribute("aria-expanded", "false");
      const toggle = function () {
        const open = card.classList.toggle("is-open");
        title.setAttribute("aria-expanded", open ? "true" : "false");
      };
      title.addEventListener("click", toggle);
      title.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          toggle();
        }
      });
    });
  }

  const calendarPage = document.querySelector(".calendar-page");
  if (!calendarPage) return;

  const eventTypeSelect = calendarPage.querySelector("[data-event-type-select]");
  calendarPage.querySelectorAll("[data-event-type]").forEach(function (button) {
    button.addEventListener("click", function () {
      if (!eventTypeSelect) return;
      eventTypeSelect.value = button.dataset.eventType;
      calendarPage.querySelectorAll("[data-event-type]").forEach(function (item) {
        item.classList.toggle("is-active", item === button);
      });
    });
  });

  const startInput = calendarPage.querySelector('input[name="start_datetime"]');
  const endInput = calendarPage.querySelector('input[name="end_datetime"]');
  const localInputValue = function (date) {
    const offset = date.getTimezoneOffset();
    return new Date(date.getTime() - offset * 60000).toISOString().slice(0, 16);
  };
  const atHour = function (date, hour) {
    const value = new Date(date);
    value.setHours(hour, 0, 0, 0);
    return value;
  };

  calendarPage.querySelectorAll("[data-calendar-range]").forEach(function (button) {
    button.addEventListener("click", function () {
      if (!startInput || !endInput) return;
      const now = new Date();
      let start = atHour(now, 9);
      let end = atHour(now, 18);
      if (button.dataset.calendarRange === "weekend") {
        const daysToSaturday = (6 - now.getDay() + 7) % 7;
        start.setDate(start.getDate() + daysToSaturday);
        end = atHour(start, 18);
        end.setDate(end.getDate() + 1);
      } else if (button.dataset.calendarRange === "week") {
        end = atHour(start, 18);
        end.setDate(end.getDate() + 7);
      }
      startInput.value = localInputValue(start);
      endInput.value = localInputValue(end);
      startInput.dispatchEvent(new Event("change", { bubbles: true }));
    });
  });

  const eventCards = Array.from(calendarPage.querySelectorAll("[data-calendar-event]"));
  if (!eventCards.length) return;
  const miniCalendar = document.createElement("div");
  miniCalendar.className = "calendar-interactive-strip";
  miniCalendar.setAttribute("aria-label", "Interactive date filter");
  const today = new Date();
  for (let offset = 0; offset < 10; offset += 1) {
    const day = new Date(today);
    day.setDate(today.getDate() + offset);
    const key = localInputValue(day).slice(0, 10);
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.filterDate = key;
    button.innerHTML = "<span>" + day.toLocaleDateString(undefined, { weekday: "short" }) +
      "</span><strong>" + day.getDate() + "</strong>";
    button.addEventListener("click", function () {
      const active = button.classList.toggle("is-active");
      miniCalendar.querySelectorAll("button").forEach(function (item) {
        if (item !== button) item.classList.remove("is-active");
      });
      eventCards.forEach(function (card) {
        card.hidden = active && card.dataset.eventDate !== key;
      });
    });
    miniCalendar.appendChild(button);
  }
  calendarPage.querySelector(".calendar-grid")?.before(miniCalendar);
})();
