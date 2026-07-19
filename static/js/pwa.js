(() => {
  "use strict";
  if (!("serviceWorker" in navigator)) return;

  const labels = {
    online: "Online",
    offline: "You are offline.",
    reconnecting: "Reconnecting…",
    "back-online": "Back online",
    "sync-pending": "Sync pending",
    synchronizing: "Synchronizing",
    synchronized: "Synchronized",
    "sync-failed": "Sync failed",
  };
  let backOnlineTimer;
  const status = document.createElement("div");
  status.className = "pwa-status";
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  status.tabIndex = -1;

  const update = document.createElement("div");
  update.className = "pwa-update";
  update.hidden = true;
  update.setAttribute("role", "status");
  update.setAttribute("aria-live", "polite");
  update.innerHTML = "<span>New version available</span><button type=\"button\">Refresh</button>";

  const setNetworkState = (state, detail = {}) => {
    clearTimeout(backOnlineTimer);
    status.dataset.state = state;
    status.textContent = state === "synchronizing" && detail.total
      ? `${labels[state]} ${detail.completed || 0}/${detail.total}`
      : state === "sync-pending" && detail.pending
        ? `${labels[state]} (${detail.pending})`
        : labels[state] || labels.online;
    document.documentElement.classList.toggle("pwa-offline", state === "offline");
  };

  const showUpdate = (worker) => {
    if (!worker) return;
    update.hidden = false;
    update.querySelector("button").onclick = () => {
      update.querySelector("button").disabled = true;
      worker.postMessage({type: "SKIP_WAITING"});
    };
  };

  const checkConnection = async () => {
    if (!navigator.onLine) return setNetworkState("offline");
    setNetworkState("reconnecting");
    try {
      const response = await fetch("/health/live", {cache: "no-store", credentials: "omit", headers: {"X-PWA-Network-Check": "1"}});
      if (!response.ok) throw new Error("network check failed");
      setNetworkState("back-online");
      backOnlineTimer = window.setTimeout(() => setNetworkState("online"), 2200);
    } catch (_error) {
      setNetworkState("offline");
    }
  };

  document.addEventListener("submit", (event) => {
    if (navigator.onLine) return;
    if (event.target.matches("form[action*='/professionals/tasks/']")) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    setNetworkState("offline");
    status.focus();
  }, true);

  document.addEventListener("click", (event) => {
    const logoutLink = event.target.closest("a[href*='logout']");
    if (logoutLink && navigator.serviceWorker.controller) {
      navigator.serviceWorker.controller.postMessage({type: "CLEAR_PRIVATE_CACHES"});
    }
    if (logoutLink) globalThis.BlackSeaOfflineStore?.clearAll().catch(() => {});
  }, true);

  document.addEventListener("DOMContentLoaded", () => {
    document.body.append(status, update);
    setNetworkState(navigator.onLine ? "online" : "offline");
  });
  window.addEventListener("offline", () => setNetworkState("offline"));
  window.addEventListener("online", checkConnection);
  window.addEventListener("bsc:offline-sync-state", (event) => setNetworkState(event.detail.state, event.detail));
  navigator.serviceWorker.addEventListener("controllerchange", () => window.location.reload());

  navigator.serviceWorker.register("/service-worker.js", {scope: "/"}).then((registration) => {
    if (window.location.pathname.endsWith("/login") && navigator.serviceWorker.controller) {
      navigator.serviceWorker.controller.postMessage({type: "CLEAR_PRIVATE_CACHES"});
    }
    if (registration.waiting) showUpdate(registration.waiting);
    registration.addEventListener("updatefound", () => {
      const installing = registration.installing;
      if (!installing) return;
      installing.addEventListener("statechange", () => {
        if (installing.state === "installed" && navigator.serviceWorker.controller) showUpdate(installing);
      });
    });
  }).catch(() => {});

  globalThis.BlackSeaPWA = {setState: setNetworkState, checkConnection};
})();
