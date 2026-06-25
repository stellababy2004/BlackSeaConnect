(function () {
  const DEFAULT_LANG = "bg";
  const FALLBACK_LANG = "en";
  const SUPPORTED_LANGS = new Set(["bg", "en", "fr", "ru"]);
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
    "/owners/register": "ownersRegister",
    "/owners/login": "ownersLogin",
    "/owners/dashboard": "ownersDashboard",
    "/owners/request-service": "ownersRequestService",
    "/admin/service-requests": "adminServiceRequests"
  };
  const LANGUAGE_CONTROL_SELECTOR = "[data-lang-switch], [data-lang]";
  const warnedKeys = new Set();
  const DEBUG_I18N = /^(localhost|127\.0\.0\.1)$/.test(window.location.hostname);

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
      return SUPPORTED_LANGS.has(candidate) ? candidate : "";
    } catch (error) {
      void error;
      return "";
    }
  }

  function getInitialLanguage() {
    const fromUrl = getLanguageFromUrl();
    return fromUrl || DEFAULT_LANG;
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

  function buildLanguageUrl(lang) {
    try {
      const url = new URL(window.location.href);
      url.searchParams.set("lang", lang);
      return `${url.pathname}${url.search}${url.hash}`;
    } catch (error) {
      void error;
      return window.location.href;
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

  function toPrefixedKey(section, name) {
    return section + name.charAt(0).toUpperCase() + name.slice(1);
  }

  function getNamespaceTranslation(dictionary, namespace, key) {
    if (!dictionary || !namespace || !key) {
      return undefined;
    }

    const scoped = dictionary[namespace];
    if (!scoped || typeof scoped !== "object") {
      return undefined;
    }

    if (Object.prototype.hasOwnProperty.call(scoped, key)) {
      return scoped[key];
    }

    return resolvePath(scoped, key);
  }

  function getTranslation(lang, key, pageNamespace) {
    const translations = window.BlackSeaI18N || {};
    const dictionary = translations[lang] || translations[FALLBACK_LANG] || translations[DEFAULT_LANG] || {};
    const fallbackDictionary = translations[FALLBACK_LANG] || translations[DEFAULT_LANG] || {};
    let value;

    if (!key) {
      value = null;
    } else {
      if (
        pageNamespace &&
        dictionary[pageNamespace] &&
        typeof dictionary[pageNamespace] === "object"
      ) {
        if (Object.prototype.hasOwnProperty.call(dictionary[pageNamespace], key)) {
          value = dictionary[pageNamespace][key];
        } else {
          const pagePathValue = resolvePath(dictionary[pageNamespace], key);
          if (pagePathValue !== undefined) {
            value = pagePathValue;
          }
        }
      }

      if (value === undefined) {
        value = getNamespaceTranslation(dictionary, "common", key);
      }

      if (value === undefined && pageNamespace && pageNamespace.startsWith("owners")) {
        value = getNamespaceTranslation(dictionary, "owners", key);
      }

      if (value === undefined && Object.prototype.hasOwnProperty.call(dictionary, key)) {
        value = dictionary[key];
      }

      if (value === undefined) {
        const directPathValue = resolvePath(dictionary, key);
        if (directPathValue !== undefined) {
          value = directPathValue;
        }
      }

      if (value === undefined && key.includes(".")) {
        const [section, ...rest] = key.split(".");
        const nestedKey = rest.join(".");
        const prefixedKey = toPrefixedKey(section, nestedKey);

        if (
          dictionary[section] &&
          Object.prototype.hasOwnProperty.call(dictionary[section], nestedKey)
        ) {
          value = dictionary[section][nestedKey];
        } else if (
          dictionary[section] &&
          Object.prototype.hasOwnProperty.call(dictionary[section], prefixedKey)
        ) {
          value = dictionary[section][prefixedKey];
        }
      }

      if (value === undefined && Object.prototype.hasOwnProperty.call(fallbackDictionary, key)) {
        value = fallbackDictionary[key];
      }

      if (value === undefined) {
        const fallbackPathValue = resolvePath(fallbackDictionary, key);
        if (fallbackPathValue !== undefined) {
          value = fallbackPathValue;
        }
      }

      if (
        value === undefined &&
        pageNamespace &&
        fallbackDictionary[pageNamespace] &&
        typeof fallbackDictionary[pageNamespace] === "object"
      ) {
        if (Object.prototype.hasOwnProperty.call(fallbackDictionary[pageNamespace], key)) {
          value = fallbackDictionary[pageNamespace][key];
        } else {
          const fallbackPagePathValue = resolvePath(fallbackDictionary[pageNamespace], key);
          if (fallbackPagePathValue !== undefined) {
            value = fallbackPagePathValue;
          }
        }
      }

      if (value === undefined) {
        value = getNamespaceTranslation(fallbackDictionary, "common", key);
      }

      if (value === undefined && pageNamespace && pageNamespace.startsWith("owners")) {
        value = getNamespaceTranslation(fallbackDictionary, "owners", key);
      }

      if (value === undefined && key.includes(".")) {
        const [section, ...rest] = key.split(".");
        const nestedKey = rest.join(".");
        const prefixedKey = toPrefixedKey(section, nestedKey);

        if (
          fallbackDictionary[section] &&
          Object.prototype.hasOwnProperty.call(fallbackDictionary[section], nestedKey)
        ) {
          value = fallbackDictionary[section][nestedKey];
        } else if (
          fallbackDictionary[section] &&
          Object.prototype.hasOwnProperty.call(fallbackDictionary[section], prefixedKey)
        ) {
          value = fallbackDictionary[section][prefixedKey];
        }

        if (value === undefined) {
          value = getNamespaceTranslation(dictionary, "common", nestedKey);
        }

        if (value === undefined) {
          value = getNamespaceTranslation(fallbackDictionary, "common", nestedKey);
        }
      }

      if (value === undefined) {
        warnMissing(key, lang);
        value = null;
      }
    }
    if (DEBUG_I18N && window.console && typeof window.console.log === "function") {
      window.console.log({
        lang,
        namespace: pageNamespace,
        key,
        value
      });
    }
    return value;
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
      const dictionary = translations[activeLang] || translations[FALLBACK_LANG] || translations[defaultLang] || {};
      const nodes = document.querySelectorAll("[data-i18n]:not([data-i18n-html])");
      const htmlNodes = document.querySelectorAll("[data-i18n-html]");
      const attrNodes = document.querySelectorAll("[data-i18n-attr]");
      const titleNode = document.querySelector("title[data-i18n]");

      nodes.forEach((node) => {
        const key = node.getAttribute("data-i18n");
        const value = getTranslation(activeLang, key, pageNamespace);
        if (value !== undefined && value !== null) {
          node.textContent = value;
          if (node.tagName === "OPTION") {
            node.label = value;
          }
        }
      });

      htmlNodes.forEach((node) => {
        const key = node.getAttribute("data-i18n-html");
        const value = getTranslation(activeLang, key, pageNamespace);
        if (value !== undefined && value !== null) {
          node.innerHTML = value;
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

          const value = getTranslation(activeLang, key, pageNamespace);
          if (value !== undefined && value !== null) {
            node.setAttribute(attr, value);
          }
        });
      });

      if (titleNode) {
        const titleKey = titleNode.getAttribute("data-i18n");
        const titleValue = getTranslation(activeLang, titleKey, pageNamespace);
        if (titleValue !== undefined && titleValue !== null) {
          titleNode.textContent = titleValue;
        }
      }

      document.documentElement.lang = activeLang;

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

      if (normalizeLanguage(document.documentElement.lang) === selectedLanguage) {
        return;
      }

      if (control.tagName === "A") {
        event.preventDefault();
      }

      window.location.assign(buildLanguageUrl(selectedLanguage));
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

      let initialLanguage = getInitialLanguage();
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



