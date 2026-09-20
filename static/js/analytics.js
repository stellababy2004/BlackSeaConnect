(function () {
  "use strict";
  var preferenceKey = "blacksea_analytics_consent";
  var consentLifetime = 180 * 24 * 60 * 60 * 1000;
  var consentExpiresAt = 0;
  var allowedEvents = new Set([
    "pilot_request_submitted", "owner_registration_completed", "service_request_submitted",
    "professional_application_submitted", "partner_application_submitted"
  ]);

  function preference() {
    consentExpiresAt = 0;
    try {
      var saved = JSON.parse(window.localStorage.getItem(preferenceKey));
      if (!saved || (saved.value !== "accepted" && saved.value !== "rejected") ||
          !Number.isFinite(saved.expiresAt) || saved.expiresAt <= Date.now() ||
          saved.expiresAt > Date.now() + consentLifetime) return null;
      consentExpiresAt = saved.expiresAt;
      return saved.value;
    } catch (_) { return null; }
  }
  function savePreference(value) {
    try {
      window.localStorage.setItem(preferenceKey, JSON.stringify({
        value: value, expiresAt: Date.now() + consentLifetime
      }));
      return true;
    } catch (_) { return false; }
  }
  function privacySignal() {
    return navigator.globalPrivacyControl === true || navigator.doNotTrack === "1" || window.doNotTrack === "1";
  }
  function loadScript(src) {
    var script = document.createElement("script");
    script.async = true;
    script.src = src;
    document.head.appendChild(script);
  }
  function configureAndLoad(root) {
    if (preference() !== "accepted" || privacySignal() || window.__blackSeaAnalyticsLoaded) return;
    window.__blackSeaAnalyticsLoaded = true;
    var ga4 = root.dataset.ga4MeasurementId || "";
    var clarity = root.dataset.clarityProjectId || "";
    if (ga4) {
      window.dataLayer = window.dataLayer || [];
      window.gtag = function () { window.dataLayer.push(arguments); };
      window.gtag("consent", "default", { analytics_storage: "granted", ad_storage: "denied", ad_user_data: "denied", ad_personalization: "denied" });
      window.gtag("js", new Date());
      window.gtag("config", ga4, { send_page_view: true, allow_google_signals: false });
      loadScript("https://www.googletagmanager.com/gtag/js?id=" + encodeURIComponent(ga4));
    }
    if (clarity) {
      window.clarity = window.clarity || function () { (window.clarity.q = window.clarity.q || []).push(arguments); };
      window.clarity("consentv2", { analytics_Storage: "granted", ad_Storage: "denied" });
      loadScript("https://www.clarity.ms/tag/" + encodeURIComponent(clarity));
    }
  }
  function fireEvent(root, name, params) {
    if (!allowedEvents.has(name) || preference() !== "accepted" || privacySignal()) return;
    var key = "blacksea_analytics_event:" + name + ":" + location.pathname;
    try { if (window.sessionStorage.getItem(key)) return; window.sessionStorage.setItem(key, "1"); } catch (_) { /* Best-effort duplicate protection. */ }
    var safe = { language: document.documentElement.lang || "bg", route_category: "public" };
    if (params && params.form_type) safe.form_type = String(params.form_type).slice(0, 40);
    if (typeof window.gtag === "function") window.gtag("event", name, safe);
    if (typeof window.clarity === "function") window.clarity("event", name);
  }
  function init() {
    var root = document.querySelector("[data-analytics-consent]");
    if (!root) return;
    var accept = root.querySelector("[data-analytics-accept]");
    var reject = root.querySelector("[data-analytics-reject]");
    var settings = document.querySelector("[data-analytics-settings]");
    if (!accept || !reject || !settings) return;
    var expiryTimer;

    function showSettings() {
      root.hidden = false;
      settings.hidden = true;
      settings.setAttribute("aria-expanded", "true");
      accept.focus();
    }
    function hideSettings() {
      root.hidden = true;
      settings.hidden = false;
      settings.setAttribute("aria-expanded", "false");
      settings.focus();
    }
    function stopAnalytics() {
      if (!window.__blackSeaAnalyticsLoaded) return;
      window["ga-disable-" + root.dataset.ga4MeasurementId] = true;
      if (typeof window.gtag === "function") {
        window.gtag("consent", "update", { analytics_storage: "denied", ad_storage: "denied",
          ad_user_data: "denied", ad_personalization: "denied" });
      }
      if (typeof window.clarity === "function") {
        window.clarity("consentv2", { analytics_Storage: "denied", ad_Storage: "denied" });
      }
      // A fresh document removes SDKs, including their automatic tracking hooks.
      window.location.reload();
    }
    function refreshConsent() {
      window.clearTimeout(expiryTimer);
      var current = preference();
      if (current !== "accepted" || privacySignal()) stopAnalytics();
      if (!current) {
        root.hidden = false;
        settings.hidden = true;
      } else {
        settings.hidden = false;
      }
      settings.setAttribute("aria-expanded", String(!root.hidden));
      if (consentExpiresAt) {
        // Browser timers cannot represent the entire 180-day period at once.
        expiryTimer = window.setTimeout(refreshConsent, Math.min(consentExpiresAt - Date.now(), 2147483647));
      }
      return current;
    }
    function trackPageEvent() {
      var params;
      try { params = JSON.parse(root.dataset.eventParams || "{}"); } catch (_) { params = {}; }
      fireEvent(root, root.dataset.event, params);
    }
    settings.addEventListener("click", showSettings);
    accept.addEventListener("click", function () {
      if (!savePreference("accepted")) return; // Fail closed when consent cannot be saved.
      hideSettings();
      refreshConsent();
      configureAndLoad(root);
      trackPageEvent();
    });
    reject.addEventListener("click", function () {
      if (!savePreference("rejected")) {
        // Removal also prevents an old acceptance surviving the reload.
        try { window.localStorage.removeItem(preferenceKey); } catch (_) { return; }
      }
      hideSettings();
      refreshConsent();
    });
    window.addEventListener("storage", function (event) {
      if (event.key === preferenceKey || event.key === null) refreshConsent();
    });
    document.addEventListener("visibilitychange", refreshConsent);
    window.addEventListener("pageshow", refreshConsent);
    if (refreshConsent() === "accepted") {
      configureAndLoad(root);
      trackPageEvent();
    }
    window.BlackSeaAnalytics = {
      track: function (name, params) { fireEvent(root, name, params || {}); },
      openSettings: showSettings
    };
  }
  document.addEventListener("DOMContentLoaded", init, { once: true });
}());

