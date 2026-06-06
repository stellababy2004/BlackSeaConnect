(function () {
  const STORAGE_KEY = "blacksea-language";

  function init(config) {
    if (!config || !config.translations) {
      return;
    }

    const translations = config.translations;
    const defaultLang = config.defaultLang || "bg";
    const nodes = document.querySelectorAll("[data-i18n]");
    const attrNodes = document.querySelectorAll("[data-i18n-attr]");
    const buttons = document.querySelectorAll("[data-lang-switch]");

    function applyLanguage(lang) {
      const activeLang = translations[lang] ? lang : defaultLang;
      const dictionary = translations[activeLang] || translations[defaultLang] || {};

      nodes.forEach((node) => {
        const key = node.getAttribute("data-i18n");
        if (dictionary[key]) {
          node.textContent = dictionary[key];
        }
      });

      attrNodes.forEach((node) => {
        const mappings = node.getAttribute("data-i18n-attr").split(",");
        mappings.forEach((mapping) => {
          const parts = mapping.split(":");
          const attr = parts[0] && parts[0].trim();
          const key = parts[1] && parts[1].trim();
          if (attr && key && dictionary[key]) {
            node.setAttribute(attr, dictionary[key]);
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

  if (window.BLACKSEA_I18N) {
    init(window.BLACKSEA_I18N);
  }
}());
