(function () {
  const STORAGE_KEY = "blacksea-language";
  const DEFAULT_LANG = "bg";
  const PAGE_NAMESPACE_BY_PATH = {
    "/": "home",
    "/services": "services",
    "/partners": "partners",
    "/pilot-access": "pilot",
    "/demo/operations": "demo",
    "/guest/a-302": "guest"
  };
  const warnedKeys = new Set();

  function getPageNamespace() {
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
    const buttons = document.querySelectorAll("[data-lang-switch]");

    function applyLanguage(lang) {
      const activeLang = translations[lang] ? lang : defaultLang;
      const dictionary = translations[activeLang] || translations[defaultLang] || {};
      const nodes = document.querySelectorAll("[data-i18n]");
      const attrNodes = document.querySelectorAll("[data-i18n-attr]");

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

      document.documentElement.lang = activeLang;

      try {
        localStorage.setItem(STORAGE_KEY, activeLang);
      } catch (error) {
        void error;
      }

      buttons.forEach((button) => {
        const isActive = button.getAttribute("data-lang-switch") === activeLang;
        button.classList.toggle("is-active", isActive);
        button.setAttribute("aria-pressed", isActive ? "true" : "false");
      });

      window.dispatchEvent(new CustomEvent("blacksea:languagechange", {
        detail: { lang: activeLang }
      }));
    }

    buttons.forEach((button) => {
      button.addEventListener("click", function () {
        applyLanguage(this.getAttribute("data-lang-switch"));
      });
    });

    let storedLanguage = defaultLang;
    try {
      storedLanguage = localStorage.getItem(STORAGE_KEY) || defaultLang;
    } catch (error) {
      void error;
    }

    applyLanguage(storedLanguage);
  }

  window.BlackSeaI18n = window.BlackSeaI18n || { init };

  if (window.BlackSeaI18N) {
    init(window.BlackSeaI18N);
  }
}());
