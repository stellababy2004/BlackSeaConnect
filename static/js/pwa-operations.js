(() => {
  "use strict";

  const store = globalThis.BlackSeaOfflineStore;
  if (!store || !("indexedDB" in globalThis)) return;
  if (!globalThis.location?.pathname?.startsWith("/professionals/")) return;

  const SYNC_TAG = "blacksea-professional-sync";
  const MAX_BACKOFF_MS = 5 * 60 * 1000;
  let synchronizing = false;
  let taskConfig = null;
  let retryTimer;

  const uuid = () => globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}-${Math.random().toString(16).slice(2)}`;
  const backoffDelay = (retryCount) => Math.min(MAX_BACKOFF_MS, 1000 * (2 ** Math.max(0, retryCount - 1)));
  const setState = (state, detail = {}) => globalThis.dispatchEvent(new CustomEvent("bsc:offline-sync-state", {detail: {state, ...detail}}));
  const taskMain = () => document.querySelector(".professional-task-shell");

  const announce = (message, error = false) => {
    const main = taskMain();
    if (!main) return;
    let alert = main.querySelector("[data-offline-live-alert]");
    if (!alert) {
      alert = document.createElement("div");
      alert.dataset.offlineLiveAlert = "";
      alert.setAttribute("role", "status");
      main.prepend(alert);
    }
    alert.className = `professional-alert ${error ? "professional-alert--error" : "professional-alert--success"}`;
    alert.textContent = message;
  };

  const readTaskConfig = () => {
    const element = document.getElementById("pwa-task-config");
    if (!element) return null;
    try { return JSON.parse(element.textContent); } catch (_error) { return null; }
  };

  const persistVisibleTasks = async () => {
    document.querySelectorAll("a.professional-task-card[href*='/professionals/tasks/']").forEach((card) => {
      const path = new URL(card.href, location.origin).pathname;
      const id = decodeURIComponent(path.split("/").filter(Boolean).pop() || "");
      if (id) store.putTask({id, url: card.href, summary: card.textContent.trim(), cachedAt: new Date().toISOString()}).catch(() => {});
    });
    if (taskConfig?.taskId) {
      await store.putTask({...taskConfig.task, id: taskConfig.taskId, version: taskConfig.version, checklist: taskConfig.checklist, attachments: taskConfig.attachments, ownerContact: taskConfig.ownerContact, propertyInformation: taskConfig.propertyInformation, completionReport: taskConfig.completionReport, url: location.href, cachedAt: new Date().toISOString()});
    }
  };

  const formPayload = (form) => {
    const payload = {};
    new FormData(form).forEach((value, key) => {
      if (value instanceof File) return;
      if (payload[key] === undefined) payload[key] = value;
      else if (Array.isArray(payload[key])) payload[key].push(value);
      else payload[key] = [payload[key], value];
    });
    return payload;
  };

  const persistUploads = async (form, mutationId) => {
    const uploadIds = [];
    for (const input of form.querySelectorAll('input[type="file"]')) {
      for (const file of Array.from(input.files || [])) {
        const id = uuid();
        await store.putUpload({id, mutationId, field: input.name, name: file.name, type: file.type, lastModified: file.lastModified, size: file.size, blob: file, status: "pending", createdAt: new Date().toISOString()});
        uploadIds.push(id);
      }
    }
    return uploadIds;
  };

  const buildFormData = async (mutation) => {
    const data = new FormData();
    Object.entries(mutation.payload || {}).forEach(([key, value]) => {
      (Array.isArray(value) ? value : [value]).forEach((entry) => data.append(key, entry));
    });
    for (const uploadId of mutation.uploadIds || []) {
      const upload = await store.getUpload(uploadId);
      if (upload?.blob) data.append(upload.field, upload.blob, upload.name);
    }
    return data;
  };

  const refreshPendingUi = async (stateOverride = "") => {
    const mutations = await store.listMutations();
    const active = mutations.filter((item) => item.status !== "discarded");
    document.querySelectorAll("[data-pwa-pending-count]").forEach((element) => { element.textContent = String(active.length); });
    let badge = document.querySelector("[data-pwa-global-pending]");
    if (active.length && taskMain()) {
      if (!badge) {
        badge = document.createElement("span");
        badge.className = "professional-badge pwa-pending-badge";
        badge.dataset.pwaGlobalPending = "";
        taskMain().prepend(badge);
      }
      badge.innerHTML = `<span data-pwa-pending-count>${active.length}</span> ${taskConfig?.labels?.pending || "Pending"}`;
    } else if (badge) badge.remove();

    const evidenceForm = document.querySelector("[data-evidence-form]");
    if (evidenceForm) {
      let list = evidenceForm.querySelector("[data-pwa-queued-uploads]");
      const uploads = await store.listUploads();
      if (uploads.length && !list) {
        list = document.createElement("div");
        list.className = "pwa-queued-uploads";
        list.dataset.pwaQueuedUploads = "";
        evidenceForm.append(list);
      }
      if (list) {
        list.replaceChildren(...uploads.map((upload) => {
          const row = document.createElement("div");
          row.className = "professional-list-item";
          row.textContent = `${upload.name} · ${taskConfig?.labels?.pending || "Pending upload"}`;
          return row;
        }));
        if (!uploads.length) list.remove();
      }
    }
    const state = stateOverride || (!navigator.onLine ? (active.length ? "sync-pending" : "offline") : (active.length ? "sync-pending" : "synchronized"));
    setState(state, {pending: active.length});
  };

  const updateChecklistUi = (form) => {
    const button = form.querySelector(".professional-check-toggle");
    if (!button) return;
    button.disabled = true;
    button.setAttribute("aria-pressed", "true");
    const mark = form.querySelector(".professional-check-mark");
    if (mark) { mark.classList.add("professional-check-mark--done"); mark.textContent = "✓"; }
    const badge = form.querySelector(".professional-badge");
    if (badge) badge.textContent = taskConfig?.labels?.pending || "Pending";
    const buttons = Array.from(document.querySelectorAll(".professional-check-toggle"));
    const checked = buttons.filter((item) => item.getAttribute("aria-pressed") === "true").length;
    const progress = buttons.length ? Math.round((checked / buttons.length) * 100) : 0;
    const bar = document.querySelector("[data-check-progress-bar]");
    const count = document.querySelector("[data-check-progress-count]");
    if (bar) bar.style.width = `${progress}%`;
    if (count) count.textContent = `${checked}/${buttons.length}`;
  };

  const NEXT_ACTION = {accept: "on_the_way", on_the_way: "arrived", arrived: "start", start: "pause", pause: "resume", resume: "pause"};
  const ensureCompletionForm = () => {
    let form = document.querySelector("[data-pwa-completion-form]");
    if (form) return form;
    const panel = document.getElementById("completion-report");
    if (!panel || !taskConfig?.taskId) return null;
    form = document.createElement("form");
    form.className = "professional-form";
    form.method = "post";
    form.action = `/professionals/tasks/${encodeURIComponent(taskConfig.taskId)}${location.search}`;
    form.dataset.pwaCompletionForm = "";
    const fields = [
      ["completed_work", taskConfig.labels?.completedWork || "Completed work", "textarea", true],
      ["materials_used", taskConfig.labels?.materialsUsed || "Materials used", "textarea", false],
      ["time_spent_minutes", taskConfig.labels?.timeSpent || "Time spent", "number", false],
      ["recommendations", taskConfig.labels?.recommendations || "Recommendations", "textarea", false],
      ["follow_up_needed", taskConfig.labels?.followUpNeeded || "Follow-up needed", "textarea", false],
      ["completion_notes", taskConfig.labels?.completionNotes || "Completion notes", "textarea", true],
    ];
    const hidden = document.createElement("input");
    hidden.type = "hidden";
    hidden.name = "task_action";
    hidden.value = "complete";
    form.append(hidden);
    fields.forEach(([name, labelText, kind, required]) => {
      const label = document.createElement("label");
      const span = document.createElement("span");
      span.textContent = labelText;
      const field = document.createElement(kind === "textarea" ? "textarea" : "input");
      field.name = name;
      field.required = required;
      if (kind === "number") { field.type = "number"; field.min = "0"; }
      label.append(span, field);
      form.append(label);
    });
    const submit = document.createElement("button");
    submit.className = "button button--primary";
    submit.type = "submit";
    submit.textContent = taskConfig.labels?.complete || "Complete work";
    form.append(submit);
    panel.append(form);
    setupDraft();
    return form;
  };
  const updateStatusUi = (action) => {
    const next = NEXT_ACTION[action];
    if (!next) return;
    document.querySelectorAll('form[action*="/professionals/tasks/"]').forEach((form) => {
      const actionInput = form.querySelector('input[name="task_action"]');
      if (!actionInput || actionInput.value !== action) return;
      actionInput.value = next;
      const button = form.querySelector('[type="submit"]');
      if (button) button.textContent = taskConfig?.labels?.[next] || next.replaceAll("_", " ");
    });
    const completionForm = ["start", "resume"].includes(action) ? ensureCompletionForm() : document.querySelector("[data-pwa-completion-form]");
    const blockedMessage = document.querySelector("[data-pwa-completion-blocked]");
    if (completionForm && ["start", "resume"].includes(action)) {
      completionForm.hidden = false;
      if (blockedMessage) blockedMessage.hidden = true;
    } else if (completionForm && action === "pause") {
      completionForm.hidden = true;
      if (blockedMessage) blockedMessage.hidden = false;
    }
  };

  const applyOptimisticUi = (form, mutation) => {
    const action = mutation.payload.task_action;
    if (action === "checklist") updateChecklistUi(form);
    else if (["accept", "on_the_way", "arrived", "start", "pause", "resume"].includes(action)) updateStatusUi(action);
    form.dataset.pwaQueued = "true";
    announce(taskConfig?.labels?.queued || "Saved offline. Sync pending.");
  };

  const registerBackgroundSync = async () => {
    try {
      const registration = await navigator.serviceWorker?.ready;
      if (registration?.sync) await registration.sync.register(SYNC_TAG);
    } catch (_error) {
      // Foreground online handling remains active when Background Sync is unavailable.
    }
  };

  const scheduleForegroundRetry = (delay) => {
    clearTimeout(retryTimer);
    retryTimer = globalThis.setTimeout(() => syncQueue(), delay);
  };

  const markRetry = async (mutation, message) => {
    const retryCount = Number(mutation.retryCount || 0) + 1;
    const delay = backoffDelay(retryCount);
    await store.putMutation({...mutation, status: "failed", retryCount, lastError: message, nextAttemptAt: Date.now() + delay});
    scheduleForegroundRetry(delay);
    await registerBackgroundSync();
  };

  const removeMutationAndUploads = async (mutation) => {
    await Promise.all((mutation.uploadIds || []).map((id) => store.removeUpload(id)));
    await store.removeMutation(mutation.id);
  };

  const isAuthorizationFailure = (response) => response.status === 401 || response.status === 403 || (response.redirected && /\/professionals\/login(?:\?|$)/.test(response.url));

  const syncQueue = async ({force = false, interactiveMutationId = ""} = {}) => {
    if (synchronizing || !navigator.onLine) return;
    synchronizing = true;
    const mutations = await store.listMutations();
    const taskVersions = new Map();
    let completed = 0;
    let syncFailed = false;
    setState("synchronizing", {completed, total: mutations.length});
    try {
      for (const mutation of mutations) {
        if (!force && mutation.nextAttemptAt && mutation.nextAttemptAt > Date.now()) continue;
        if (mutation.status === "conflict") continue;
        const version = taskVersions.get(mutation.taskId) || mutation.baseVersion || "";
        try {
          const response = await fetch(mutation.url, {
            method: mutation.method || "POST",
            body: await buildFormData(mutation),
            credentials: "same-origin",
            headers: {
              "X-Requested-With": "XMLHttpRequest",
              "X-Idempotency-Key": mutation.idempotencyKey,
              "X-Task-Version": version,
              ...(mutation.conflictResolution ? {"X-Conflict-Resolution": mutation.conflictResolution} : {}),
            },
          });
          if (isAuthorizationFailure(response)) {
            await markRetry(mutation, "authorization_required");
            syncFailed = true;
            break;
          }
          const result = await response.json().catch(() => ({}));
          if (response.status === 409 && result.conflict) {
            const conflict = {id: mutation.id, mutationId: mutation.id, taskId: mutation.taskId, localPayload: mutation.payload, serverState: result.server_state, serverVersion: result.server_version, createdAt: new Date().toISOString()};
            await store.putConflict(conflict);
            await store.putMutation({...mutation, status: "conflict", conflictId: conflict.id});
            renderConflict(conflict);
            continue;
          }
          if (!response.ok || !result.ok) {
            await markRetry(mutation, result.error || `http_${response.status}`);
            syncFailed = true;
            continue;
          }
          if (result.server_version) taskVersions.set(mutation.taskId, result.server_version);
          await removeMutationAndUploads(mutation);
          if (mutation.payload?.task_action === "complete") await store.removeDraft(mutation.taskId);
          completed += 1;
          setState("synchronizing", {completed, total: mutations.length});
          if (interactiveMutationId === mutation.id && result.redirect && navigator.onLine && mutation.payload?.task_action !== "checklist") location.assign(result.redirect);
        } catch (error) {
          await markRetry(mutation, error?.message || "network_error");
          syncFailed = true;
        }
      }
    } finally {
      synchronizing = false;
      await refreshPendingUi(syncFailed ? "sync-failed" : "");
    }
  };

  const renderConflict = (conflict) => {
    if (!taskMain() || document.querySelector(`[data-pwa-conflict="${CSS.escape(conflict.id)}"]`)) return;
    const card = document.createElement("section");
    card.className = "professional-alert professional-alert--error pwa-conflict-card";
    card.dataset.pwaConflict = conflict.id;
    card.innerHTML = `<strong>${taskConfig?.labels?.conflict || "This task changed on the server."}</strong><div class="professional-actions"><button class="button button--primary" data-resolution="keep-local">${taskConfig?.labels?.keepLocal || "Keep local"}</button><button class="button button--secondary" data-resolution="keep-server">${taskConfig?.labels?.keepServer || "Keep server"}</button><button class="button button--ghost" data-resolution="retry">${taskConfig?.labels?.retry || "Retry"}</button></div>`;
    card.addEventListener("click", async (event) => {
      const resolution = event.target.closest("[data-resolution]")?.dataset.resolution;
      if (!resolution) return;
      const mutation = await store.getMutation(conflict.mutationId);
      if (!mutation) return card.remove();
      if (resolution === "keep-server") await removeMutationAndUploads(mutation);
      else await store.putMutation({...mutation, status: "pending", nextAttemptAt: 0, baseVersion: conflict.serverVersion, conflictResolution: resolution === "keep-local" ? "keep-local" : ""});
      await store.removeConflict(conflict.id);
      card.remove();
      await refreshPendingUi();
      if (resolution !== "keep-server") syncQueue({force: true});
    });
    taskMain().prepend(card);
  };

  const enqueueForm = async (form) => {
    const id = uuid();
    const mutation = {
      id,
      timestamp: new Date().toISOString(),
      createdAt: new Date().toISOString(),
      retryCount: 0,
      payload: formPayload(form),
      taskId: taskConfig?.taskId || decodeURIComponent(new URL(form.action, location.origin).pathname.split("/").filter(Boolean).pop() || ""),
      idempotencyKey: id,
      baseVersion: taskConfig?.version || "",
      method: "POST",
      url: form.action,
      status: "pending",
      nextAttemptAt: 0,
      uploadIds: [],
    };
    mutation.uploadIds = await persistUploads(form, id);
    await store.putMutation(mutation);
    applyOptimisticUi(form, mutation);
    await refreshPendingUi();
    await registerBackgroundSync();
    if (navigator.onLine) syncQueue({force: true, interactiveMutationId: id});
  };

  const isQueueableForm = (form) => {
    if (!(form instanceof HTMLFormElement) || (form.method || "get").toLowerCase() !== "post") return false;
    const path = new URL(form.action, location.origin).pathname;
    return /^\/professionals\/tasks\/[^/]+\/?$/.test(path) && Boolean(form.querySelector('input[name="task_action"]'));
  };

  const setupDraft = async () => {
    if (!taskConfig?.taskId) return;
    const form = document.querySelector('#completion-report form');
    if (!form) return;
    const saved = await store.getDraft(taskConfig.taskId);
    if (saved?.payload) Object.entries(saved.payload).forEach(([key, value]) => { const field = form.elements.namedItem(key); if (field) field.value = value; });
    form.addEventListener("input", () => store.putDraft({taskId: taskConfig.taskId, payload: formPayload(form), updatedAt: new Date().toISOString()}).catch(() => {}));
  };

  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (!isQueueableForm(form)) return;
    if (navigator.onLine) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if (!form.reportValidity()) return;
    enqueueForm(form).catch(() => announce("Unable to save this action offline.", true));
  }, true);

  document.addEventListener("click", (event) => {
    if (!event.target.closest("a[href*='/professionals/logout']")) return;
    store.clearAll().catch(() => {});
  }, true);

  globalThis.addEventListener("online", () => syncQueue({force: true}));
  navigator.serviceWorker?.addEventListener("message", (event) => {
    if (event.data?.type === "BSC_SYNC_REQUEST") syncQueue({force: true});
    if (event.data?.type === "BSC_SYNC_COMPLETE") refreshPendingUi(event.data.state === "sync-failed" ? "sync-failed" : "");
  });

  const initialize = async () => {
    taskConfig = readTaskConfig();
    if (location.pathname.endsWith("/professionals/login")) {
      await store.clearAll();
      await refreshPendingUi();
      return;
    }
    await persistVisibleTasks();
    await setupDraft();
    for (const conflict of await store.listConflicts()) renderConflict(conflict);
    await refreshPendingUi();
    if (navigator.onLine) syncQueue();
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => initialize().catch(() => {}));
  else initialize().catch(() => {});

  globalThis.BlackSeaOfflineOperations = {backoffDelay, enqueueForm, syncQueue, refreshPendingUi, registerBackgroundSync};
})();
