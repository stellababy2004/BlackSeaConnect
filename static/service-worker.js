"use strict";

const CACHE_VERSION = "bsc-pwa-v1";
const SHELL_CACHE = `${CACHE_VERSION}-shell`;
const PAGE_CACHE = `${CACHE_VERSION}-pages`;
const ASSET_CACHE = `${CACHE_VERSION}-assets`;
const OFFLINE_URL = "/offline";
const SHELL_ASSETS = [
  OFFLINE_URL, "/static/site.webmanifest", "/static/css/styles.css", "/static/css/pwa.css", "/static/js/pwa.js",
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
  if (event.data && event.data.type === "CLEAR_PRIVATE_CACHES") caches.delete(PAGE_CACHE);
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
