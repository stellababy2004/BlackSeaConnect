(function () {
  const STORAGE_KEY = "blacksea-language";
  const STORAGE_KEY_ALIAS = "blackseaLang";
  const DEFAULT_LANG = "bg";
  const PAGE_NAMESPACE_BY_PATH = {
    "/": "home",
    "/services": "services",
    "/partners": "partners",
    "/pilot-access": "pilot",
    "/demo/operations": "demo",
    "/guest/a-302": "guest",
    "/professionals": "professionals",
    "/professionals/apply": "professionalsApply",
    "/network": "network",
    "/request-service": "requestService",
    "/admin/service-requests": "adminServiceRequests"
  };
  const LANGUAGE_CONTROL_SELECTOR = "[data-lang-switch], [data-lang]";
  const warnedKeys = new Set();

  function normalizeLanguage(lang) {
    if (!lang) {
      return "";
    }

    return String(lang).trim().toLowerCase();
  }

  function getLanguageFromUrl() {
    try {
      const params = new URLSearchParams(window.location.search);
      const candidate = normalizeLanguage(params.get("lang"));
      return candidate;
    } catch (error) {
      void error;
      return "";
    }
  }

  function getStoredLanguage() {
    try {
      return normalizeLanguage(localStorage.getItem(STORAGE_KEY) || localStorage.getItem(STORAGE_KEY_ALIAS));
    } catch (error) {
      void error;
      return "";
    }
  }

  function setLanguageInUrl(lang) {
    try {
      const url = new URL(window.location.href);
      url.searchParams.set("lang", lang);
      window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
    } catch (error) {
      void error;
    }
  }

  function getLanguageFromControl(control) {
    if (!control) {
      return "";
    }

    const explicit = normalizeLanguage(control.getAttribute("data-lang-switch") || control.getAttribute("data-lang"));
    if (explicit) {
      return explicit;
    }

    if (control.tagName === "A") {
      try {
        const href = control.getAttribute("href") || "";
        const url = new URL(href, window.location.href);
        return normalizeLanguage(url.searchParams.get("lang"));
      } catch (error) {
        void error;
      }
    }

    return "";
  }

  function getLanguageControls() {
    return document.querySelectorAll(LANGUAGE_CONTROL_SELECTOR);
  }

  function syncLanguageControls(activeLang) {
    getLanguageControls().forEach((control) => {
      const controlLang = getLanguageFromControl(control);
      const isActive = controlLang === activeLang;
      control.classList.toggle("is-active", isActive);
      control.setAttribute("aria-pressed", isActive ? "true" : "false");

      if (control.tagName === "A" && controlLang) {
        try {
          const url = new URL(control.getAttribute("href") || window.location.href, window.location.href);
          url.searchParams.set("lang", controlLang);
          control.setAttribute("href", `${url.pathname}${url.search}${url.hash}`);
        } catch (error) {
          void error;
        }
      }
    });
  }

  function getPageNamespace() {
    if (window.location.pathname.startsWith("/network/")) {
      return "network";
    }
    if (window.location.pathname.startsWith("/admin/service-requests/")) {
      return "adminServiceRequests";
    }
    return PAGE_NAMESPACE_BY_PATH[window.location.pathname] || "home";
  }

  function resolvePath(dictionary, keyPath) {
    if (!dictionary || !keyPath) {
      return undefined;
    }

    return keyPath.split(".").reduce((value, segment) => {
      if (value && Object.prototype.hasOwnProperty.call(value, segment)) {
        return value[segment];
      }
      return undefined;
    }, dictionary);
  }

  function resolveTranslation(dictionary, key, pageNamespace) {
    if (!key) {
      return undefined;
    }

    const namespacedKey = key.includes(".") ? key : `${pageNamespace}.${key}`;
    return resolvePath(dictionary, namespacedKey) || resolvePath(dictionary, key);
  }

  function warnMissing(key, lang) {
    const warningKey = `${lang}:${key}`;
    if (warnedKeys.has(warningKey)) {
      return;
    }

    warnedKeys.add(warningKey);
    const isLocalhost = /^(localhost|127\.0\.0\.1)$/.test(window.location.hostname);
    if (isLocalhost && window.console && typeof window.console.warn === "function") {
      window.console.warn(`[BlackSeaI18N] Missing translation for "${key}" in "${lang}".`);
    }
  }

  function init(config) {
    if (!config) {
      return;
    }

    const translations = config;
    const defaultLang = DEFAULT_LANG;
    const pageNamespace = getPageNamespace();
    function applyLanguage(lang, options) {
      const settings = options || {};
      const activeLang = translations[lang] ? lang : defaultLang;
      const dictionary = translations[activeLang] || translations[defaultLang] || {};
      const nodes = document.querySelectorAll("[data-i18n]");
      const attrNodes = document.querySelectorAll("[data-i18n-attr]");
      const titleNode = document.querySelector("title[data-i18n]");

      nodes.forEach((node) => {
        const key = node.getAttribute("data-i18n");
        const value = resolveTranslation(dictionary, key, pageNamespace);
        if (value !== undefined && value !== null) {
          node.textContent = value;
        } else {
          warnMissing(key, activeLang);
        }
      });

      attrNodes.forEach((node) => {
        const mappings = node.getAttribute("data-i18n-attr").split(",");
        mappings.forEach((mapping) => {
          const parts = mapping.split(":");
          const attr = parts[0] && parts[0].trim();
          const key = parts[1] && parts[1].trim();
          if (!attr || !key) {
            return;
          }

          const value = resolveTranslation(dictionary, key, pageNamespace);
          if (value !== undefined && value !== null) {
            node.setAttribute(attr, value);
          } else {
            warnMissing(key, activeLang);
          }
        });
      });

      if (titleNode) {
        const titleKey = titleNode.getAttribute("data-i18n");
        const titleValue = resolveTranslation(dictionary, titleKey, pageNamespace);
        if (titleValue !== undefined && titleValue !== null) {
          titleNode.textContent = titleValue;
        } else {
          warnMissing(titleKey, activeLang);
        }
      }

      document.documentElement.lang = activeLang;

      try {
        localStorage.setItem(STORAGE_KEY, activeLang);
        localStorage.setItem(STORAGE_KEY_ALIAS, activeLang);
      } catch (error) {
        void error;
      }

      if (settings.syncUrl !== false) {
        setLanguageInUrl(activeLang);
      }

      syncLanguageControls(activeLang);

      window.dispatchEvent(new CustomEvent("blacksea:languagechange", {
        detail: { lang: activeLang }
      }));
    }

    function handleLanguageControlClick(event) {
      const control = event.currentTarget || event.target.closest(LANGUAGE_CONTROL_SELECTOR);
      if (!control) {
        return;
      }

      const selectedLanguage = getLanguageFromControl(control);
      if (!selectedLanguage) {
        return;
      }

      if (window.console && typeof window.console.log === "function") {
        window.console.log("language click", selectedLanguage);
      }

      if (control.tagName === "A") {
        event.preventDefault();
      }

      applyLanguage(selectedLanguage, { syncUrl: true });
    }

    function bindLanguageControls() {
      getLanguageControls().forEach((control) => {
        if (control.dataset.blackseaLangBound === "1") {
          return;
        }

        control.dataset.blackseaLangBound = "1";
        control.addEventListener("click", handleLanguageControlClick);
      });
    }

    document.addEventListener("click", function (event) {
      const control = event.target.closest(LANGUAGE_CONTROL_SELECTOR);
      if (!control) {
        return;
      }

      if (control.dataset.blackseaLangBound === "1") {
        return;
      }

      handleLanguageControlClick.call(control, event);
    });

    function boot() {
      bindLanguageControls();

      const urlLanguage = getLanguageFromUrl();
      let initialLanguage = urlLanguage;
      if (!initialLanguage) {
        initialLanguage = getStoredLanguage();
      }
      if (!translations[initialLanguage]) {
        initialLanguage = defaultLang;
      }

      applyLanguage(initialLanguage, { syncUrl: false });
    }

    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", boot, { once: true });
    } else {
      boot();
    }
  }

  window.BlackSeaI18n = window.BlackSeaI18n || { init };

  if (window.BlackSeaI18N) {
    init(window.BlackSeaI18N);
  }
}());
