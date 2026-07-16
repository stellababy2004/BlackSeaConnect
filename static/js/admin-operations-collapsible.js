(() => {
  const sections = new Map([
    ["Чеклист", ["operations-checklist", "Чеклист"]],
    ["Финанси", ["operations-finance", "Финанси"]],
    ["Отчет за завършване", ["completion-report", "Отчет"]],
    ["Карта на възлагането", ["assigned-professional", "Професионалист"]],
    ["Свързана резервация", ["linked-reservation", "Резервация"]],
    ["Контекст на имота", ["property-context", "Имот"]],
    ["Свързани заявки", ["related-requests", "Свързани заявки"]],
    ["Вътрешни бележки", ["internal-notes", "Вътрешни бележки"]],
    ["Хронология", ["operations-timeline", "Хронология"]]
  ]);

  const normalize = value => String(value || "").replace(/\s+/g, " ").trim();

  const setExpanded = (panel, expanded) => {
    panel.classList.toggle("is-collapsed", !expanded);
    const button = panel.querySelector(":scope > .admin-operations-collapse-header .admin-operations-collapse-toggle");
    if (!button) return;
    button.setAttribute("aria-expanded", String(expanded));
    const state = button.querySelector(".admin-operations-collapse-toggle__state");
    if (state) state.textContent = expanded ? "Скрий" : "Покажи";
  };

  const enhancePanel = (panel, id, label) => {
    if (panel.dataset.bscCollapsible === "true") return;
    const eyebrow = panel.querySelector(":scope > .eyebrow");
    const title = panel.querySelector(":scope > .admin-operations-section-title");
    if (!eyebrow || !title) return;

    panel.dataset.bscCollapsible = "true";
    panel.id = panel.id || id;

    const header = document.createElement("div");
    header.className = "admin-operations-collapse-header";

    const heading = document.createElement("div");
    heading.className = "admin-operations-collapse-heading";

    eyebrow.before(header);
    heading.append(eyebrow, title);
    header.append(heading);

    const button = document.createElement("button");
    button.type = "button";
    button.className = "admin-operations-collapse-toggle";
    button.setAttribute("aria-controls", panel.id + "-body");
    button.innerHTML = `<span class="admin-operations-collapse-toggle__icon" aria-hidden="true">▼</span><span>${label}</span><span class="admin-operations-collapse-toggle__state">Покажи</span>`;
    header.append(button);

    const body = document.createElement("div");
    body.className = "admin-operations-collapse-body";
    body.id = panel.id + "-body";

    while (header.nextSibling) {
      body.append(header.nextSibling);
    }

    panel.append(body);

    button.addEventListener("click", () => {
      setExpanded(panel, panel.classList.contains("is-collapsed"));
    });

    setExpanded(panel, false);
  };

  document.querySelectorAll(".admin-operations-detail-panel").forEach(panel => {
    const eyebrow = panel.querySelector(":scope > .eyebrow");
    if (!eyebrow) return;
    const config = sections.get(normalize(eyebrow.textContent));
    if (!config) return;
    enhancePanel(panel, config[0], config[1]);
  });

  const evidence = document.getElementById("evidence");
  if (evidence && evidence.dataset.bscCollapsible !== "true") {
    const eyebrow = evidence.querySelector(":scope > .eyebrow");
    if (eyebrow) eyebrow.textContent = "Файлове";
    enhancePanel(evidence, "evidence", "Файлове");
  }

  const openTarget = () => {
    const id = window.location.hash.replace(/^#/, "");
    if (!id) return;
    const target = document.getElementById(id);
    if (!target) return;
    const panel = target.matches("[data-bsc-collapsible]") ? target : target.closest("[data-bsc-collapsible]");
    if (!panel) return;
    setExpanded(panel, true);
    requestAnimationFrame(() => panel.scrollIntoView({ behavior: "smooth", block: "start" }));
  };

  if (evidence && evidence.querySelector(".admin-evidence__message")) {
    setExpanded(evidence, true);
  }

  window.addEventListener("hashchange", openTarget);
  openTarget();

  // BSC_SMART_EMPTY_STATES_V1
  const reservationPanel = document.getElementById("linked-reservation");

  if (reservationPanel) {
    const reservationEmpty = reservationPanel.querySelector(".admin-operations-empty");

    if (reservationEmpty && !reservationPanel.querySelector(".bsc-empty-state-actions")) {
      const actions = document.createElement("div");
      actions.className = "bsc-empty-state-actions";

      const calendarLink = document.createElement("a");
      calendarLink.className = "bsc-empty-state-action";
      calendarLink.href = "/admin/calendar";
      calendarLink.textContent = "Отвори календара";

      actions.append(calendarLink);
      reservationEmpty.insertAdjacentElement("afterend", actions);
    }
  }

  const relatedRequestsPanel = document.getElementById("related-requests");

  if (relatedRequestsPanel) {
    const hasRequestsTable = Boolean(
      relatedRequestsPanel.querySelector(".admin-operations-table")
    );
    const hasEmptyMessage = Boolean(
      relatedRequestsPanel.querySelector(".admin-operations-empty")
    );

    if (!hasRequestsTable && hasEmptyMessage) {
      relatedRequestsPanel.classList.add("bsc-smart-hidden");
    }
  }

  // BSC_FINANCE_CALCULATOR_V1
  const financePanel = document.getElementById("operations-finance");

  if (financePanel) {
    const quoteInput = financePanel.querySelector("[data-finance-quote]");
    const feeTypeInput = financePanel.querySelector("[data-finance-fee-type]");
    const feeInput = financePanel.querySelector("[data-finance-fee]");
    const currencyInput = financePanel.querySelector("[data-finance-currency]");
    const professionalOutput = financePanel.querySelector("[data-finance-professional-total]");
    const platformOutput = financePanel.querySelector("[data-finance-platform-fee]");
    const ownerOutput = financePanel.querySelector("[data-finance-owner-total]");
    const feeHint = financePanel.querySelector("[data-finance-fee-hint]");

    const numberValue = input => {
      const parsed = Number.parseFloat(input?.value || "0");
      return Number.isFinite(parsed) && parsed >= 0 ? parsed : 0;
    };

    const refreshFinance = () => {
      const quote = numberValue(quoteInput);
      const feeValue = numberValue(feeInput);
      const feeType = feeTypeInput?.value || "FIXED";
      const currency = currencyInput?.value || "EUR";
      const fee = feeType === "PERCENT" ? quote * feeValue / 100 : feeValue;
      const ownerTotal = quote + fee;

      professionalOutput.textContent = `${quote.toFixed(2)} ${currency}`;
      platformOutput.textContent = `${fee.toFixed(2)} ${currency}`;
      ownerOutput.textContent = `${ownerTotal.toFixed(2)} ${currency}`;
      feeHint.textContent = feeType === "PERCENT"
        ? `Комисиона ${feeValue.toFixed(2)}% върху офертата.`
        : "Фиксирана комисиона към офертата.";
    };

    [quoteInput, feeTypeInput, feeInput, currencyInput].forEach(input => {
      input?.addEventListener("input", refreshFinance);
      input?.addEventListener("change", refreshFinance);
    });

    refreshFinance();
  }
})();
