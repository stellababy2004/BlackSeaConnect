(function () {
  "use strict";
  var preferenceKey = "blacksea_analytics_consent";
  var allowedEvents = new Set([
    "pilot_request_submitted", "owner_registration_completed", "service_request_submitted",
    "professional_application_submitted", "partner_application_submitted"
  ]);

  function preference() {
    try { return window.localStorage.getItem(preferenceKey); } catch (_) { return null; }
  }
  function savePreference(value) {
    try { window.localStorage.setItem(preferenceKey, value); } catch (_) { /* Storage may be unavailable. */ }
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
    if (privacySignal() || window.__blackSeaAnalyticsLoaded) return;
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
    var current = preference();
if (current === "accepted") configureAndLoad(root);
    else if (!current) root.hidden = false;
    root.querySelector("[data-analytics-accept]").addEventListener("click", function () { savePreference("accepted"); root.hidden = true; configureAndLoad(root); fireEvent(root, root.dataset.event, JSON.parse(root.dataset.eventParams || "{}")); });
    root.querySelector("[data-analytics-reject]").addEventListener("click", function () { savePreference("rejected"); root.hidden = true; });
    if (current === "accepted") fireEvent(root, root.dataset.event, JSON.parse(root.dataset.eventParams || "{}"));
    window.BlackSeaAnalytics = { track: function (name, params) { fireEvent(root, name, params || {}); } };
  }
  document.addEventListener("DOMContentLoaded", init, { once: true });
}());

