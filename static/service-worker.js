"use strict";

const CACHE_VERSION = "bsc-pwa-v4";
const SHELL_CACHE = `${CACHE_VERSION}-shell`;
const PAGE_CACHE = `${CACHE_VERSION}-pages`;
const ASSET_CACHE = `${CACHE_VERSION}-assets`;
const OFFLINE_URL = "/offline";
const SHELL_ASSETS = [
  OFFLINE_URL, "/static/site.webmanifest", "/static/css/styles.css", "/static/css/pwa.css", "/static/js/pwa.js",
  "/static/js/pwa-storage.js", "/static/js/pwa-operations.js",
  "/static/favicon-16x16.png", "/static/favicon-32x32.png", "/static/favicon-192x192.png",
  "/static/favicon-512x512.png", "/static/apple-touch-icon.png"
];
const NEVER_CACHE_PREFIXES = [
  "/api/", "/auth/", "/admin", "/enterprise", "/health", "/operations/", "/organizations",
  "/webhooks", "/workspace", "/static/uploads/", "/owners/finance/", "/professionals/stripe/"
];
const NEVER_CACHE_MARKERS = [
  "login", "logout", "magic", "token", "session", "stripe", "payment", "checkout", "upload",
  "attachment", "evidence", "media", "download"
];
const OFFLINE_PAGE_PATTERNS = [
  /^\/$/, /^\/demo(?:\/|$)/,
  /^\/professionals(?:\/dashboard|\/tasks(?:\/[^/]+)?)\/?$/,
  /^\/owners\/dashboard\/?$/
];

const isNeverCacheUrl = (url) => {
  const path = url.pathname.toLowerCase();
  return NEVER_CACHE_PREFIXES.some((prefix) => path === prefix || path.startsWith(prefix))
    || NEVER_CACHE_MARKERS.some((marker) => path.includes(marker));
};
const isCacheablePage = (url) => OFFLINE_PAGE_PATTERNS.some((pattern) => pattern.test(url.pathname));
const isSafeResponse = (response, expectedType) => {
  if (!response || !response.ok || response.type === "opaque") return false;
  const contentType = (response.headers.get("Content-Type") || "").toLowerCase();
  if (contentType.includes("application/json")) return false;
  if ((response.headers.get("Cache-Control") || "").toLowerCase().includes("no-store")) return false;
  return expectedType === "document" ? contentType.includes("text/html") : true;
};

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(SHELL_CACHE).then((cache) => cache.addAll(SHELL_ASSETS)));
});
self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys()
    .then((keys) => Promise.all(keys.filter((key) => !key.startsWith(CACHE_VERSION)).map((key) => caches.delete(key))))
    .then(() => self.clients.claim()));
});
self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") self.skipWaiting();
  if (event.data && event.data.type === "CLEAR_PRIVATE_CACHES") {
    event.waitUntil(Promise.all([caches.delete(PAGE_CACHE), clearOfflineDatabase()]));
  }
});

const OFFLINE_DB_NAME = "blacksea-professional-offline";
const OFFLINE_DB_VERSION = 1;
const OFFLINE_STORES = ["tasks", "mutations", "uploads", "conflicts", "drafts"];

const openOfflineDatabase = () => new Promise((resolve, reject) => {
  const request = indexedDB.open(OFFLINE_DB_NAME, OFFLINE_DB_VERSION);
  request.onupgradeneeded = () => {
    const database = request.result;
    if (!database.objectStoreNames.contains("tasks")) database.createObjectStore("tasks", {keyPath: "id"});
    if (!database.objectStoreNames.contains("mutations")) database.createObjectStore("mutations", {keyPath: "id"});
    if (!database.objectStoreNames.contains("uploads")) database.createObjectStore("uploads", {keyPath: "id"});
    if (!database.objectStoreNames.contains("conflicts")) database.createObjectStore("conflicts", {keyPath: "id"});
    if (!database.objectStoreNames.contains("drafts")) database.createObjectStore("drafts", {keyPath: "taskId"});
  };
  request.onsuccess = () => resolve(request.result);
  request.onerror = () => reject(request.error);
});

const databaseRequest = (request) => new Promise((resolve, reject) => {
  request.onsuccess = () => resolve(request.result);
  request.onerror = () => reject(request.error);
});

const databaseOperation = async (storeName, mode, operation) => {
  const database = await openOfflineDatabase();
  const transaction = database.transaction(storeName, mode);
  const result = await operation(transaction.objectStore(storeName));
  await new Promise((resolve, reject) => {
    transaction.oncomplete = resolve;
    transaction.onerror = () => reject(transaction.error);
    transaction.onabort = () => reject(transaction.error);
  });
  database.close();
  return result;
};

const clearOfflineDatabase = async () => {
  try {
    const database = await openOfflineDatabase();
    const names = OFFLINE_STORES.filter((name) => database.objectStoreNames.contains(name));
    if (!names.length) return database.close();
    const transaction = database.transaction(names, "readwrite");
    names.forEach((name) => transaction.objectStore(name).clear());
    await new Promise((resolve, reject) => {
      transaction.oncomplete = resolve;
      transaction.onerror = () => reject(transaction.error);
      transaction.onabort = () => reject(transaction.error);
    });
    database.close();
  } catch (_error) {
    // A foreground login/logout cleanup retries when the database is available.
  }
};

const notifyClients = async (message) => {
  const clients = await self.clients.matchAll({type: "window", includeUncontrolled: true});
  clients.forEach((client) => client.postMessage(message));
};

const backgroundSyncQueue = async () => {
  let mutations;
  try {
    mutations = await databaseOperation("mutations", "readonly", (store) => databaseRequest(store.getAll()));
  } catch (_error) {
    return;
  }
  mutations.sort((left, right) => String(left.createdAt).localeCompare(String(right.createdAt)) || String(left.id).localeCompare(String(right.id)));
  const taskVersions = new Map();
  let completed = 0;
  let retryNeeded = false;
  for (const mutation of mutations) {
    if (mutation.status === "conflict" || (mutation.nextAttemptAt && mutation.nextAttemptAt > Date.now())) continue;
    const data = new FormData();
    Object.entries(mutation.payload || {}).forEach(([key, value]) => {
      (Array.isArray(value) ? value : [value]).forEach((entry) => data.append(key, entry));
    });
    for (const uploadId of mutation.uploadIds || []) {
      const upload = await databaseOperation("uploads", "readonly", (store) => databaseRequest(store.get(uploadId)));
      if (upload?.blob) data.append(upload.field, upload.blob, upload.name);
    }
    try {
      const response = await fetch(mutation.url, {
        method: mutation.method || "POST",
        body: data,
        credentials: "same-origin",
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          "X-Idempotency-Key": mutation.idempotencyKey,
          "X-Task-Version": taskVersions.get(mutation.taskId) || mutation.baseVersion || "",
          ...(mutation.conflictResolution ? {"X-Conflict-Resolution": mutation.conflictResolution} : {}),
        },
      });
      if (response.status === 401 || response.status === 403 || (response.redirected && /\/professionals\/login(?:\?|$)/.test(response.url))) {
        await notifyClients({type: "BSC_SYNC_COMPLETE", state: "sync-failed", reason: "authorization"});
        return;
      }
      const result = await response.json().catch(() => ({}));
      if (response.status === 409 && result.conflict) {
        const conflict = {id: mutation.id, mutationId: mutation.id, taskId: mutation.taskId, localPayload: mutation.payload, serverState: result.server_state, serverVersion: result.server_version, createdAt: new Date().toISOString()};
        await databaseOperation("conflicts", "readwrite", (store) => databaseRequest(store.put(conflict)));
        await databaseOperation("mutations", "readwrite", (store) => databaseRequest(store.put({...mutation, status: "conflict", conflictId: conflict.id})));
        continue;
      }
      if (!response.ok || !result.ok) throw new Error(result.error || `http_${response.status}`);
      if (result.server_version) taskVersions.set(mutation.taskId, result.server_version);
      for (const uploadId of mutation.uploadIds || []) await databaseOperation("uploads", "readwrite", (store) => databaseRequest(store.delete(uploadId)));
      await databaseOperation("mutations", "readwrite", (store) => databaseRequest(store.delete(mutation.id)));
      if (mutation.payload?.task_action === "complete") await databaseOperation("drafts", "readwrite", (store) => databaseRequest(store.delete(mutation.taskId)));
      completed += 1;
    } catch (error) {
      const retryCount = Number(mutation.retryCount || 0) + 1;
      const nextAttemptAt = Date.now() + Math.min(5 * 60 * 1000, 1000 * (2 ** Math.max(0, retryCount - 1)));
      await databaseOperation("mutations", "readwrite", (store) => databaseRequest(store.put({...mutation, status: "failed", retryCount, nextAttemptAt, lastError: error?.message || "sync_failed"})));
      retryNeeded = true;
    }
  }
  if (retryNeeded && self.registration.sync) {
    try { await self.registration.sync.register("blacksea-professional-sync"); } catch (_error) {}
  }
  await notifyClients({type: "BSC_SYNC_COMPLETE", state: "synchronized", completed});
};

self.addEventListener("sync", (event) => {
  if (event.tag === "blacksea-professional-sync") event.waitUntil(backgroundSyncQueue());
});
self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin || isNeverCacheUrl(url)) return;

  if (request.mode === "navigate") {
    event.respondWith((async () => {
      try {
        const response = await fetch(request);
        if (isCacheablePage(url) && isSafeResponse(response, "document")) {
          const cache = await caches.open(PAGE_CACHE);
          await cache.put(request, response.clone());
        }
        return response;
      } catch (_error) {
        if (isCacheablePage(url)) {
          const cached = await caches.match(request);
          if (cached) return cached;
        }
        return (await caches.match(OFFLINE_URL)) || Response.error();
      }
    })());
    return;
  }

  if (url.pathname.startsWith("/static/")) {
    event.respondWith((async () => {
      const cached = await caches.match(request);
      if (cached) return cached;
      const response = await fetch(request);
      if (isSafeResponse(response, "asset")) {
        const cache = await caches.open(ASSET_CACHE);
        await cache.put(request, response.clone());
      }
      return response;
    })());
  }
});
