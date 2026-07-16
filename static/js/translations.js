/* Compatibility shim for Node-based translation tests */
(function () {
  if (typeof window === "undefined") {
    return;
  }

  if (typeof window.document === "undefined") {
    window.document = {
      documentElement: { lang: "bg" },
      querySelectorAll: function () { return []; },
      querySelector: function () { return null; },
      addEventListener: function () {},
      write: function () {}
    };
  }

  if (typeof window.location === "undefined") {
    window.location = { search: "" };
  }

  if (typeof window.setTimeout === "undefined") {
    window.setTimeout = function (fn) {
      if (typeof fn === "function") {
        fn();
      }
      return 0;
    };
  }

  if (typeof window.clearTimeout === "undefined") {
    window.clearTimeout = function () {};
  }

  if (typeof globalThis !== "undefined") {
    if (typeof globalThis.document === "undefined") {
      globalThis.document = window.document;
    }
    if (typeof globalThis.location === "undefined") {
      globalThis.location = window.location;
    }
    if (typeof globalThis.setTimeout === "undefined") {
      globalThis.setTimeout = window.setTimeout;
    }
    if (typeof globalThis.clearTimeout === "undefined") {
      globalThis.clearTimeout = window.clearTimeout;
    }
  }

  window.BlackSeaI18NModules = window.BlackSeaI18NModules || {};
  var base = '/static/js/i18n/';
  var moduleFiles = [
    'common.js',
    'home.js',
    'services.js',
    'demo.js',
    'pilot.js',
    'guest.js',
    'owners.js',
    'owners-landing.js',
    'owners-dashboard.js',
    'owners-login.js',
    'owners-register.js',
    'owners-request-service.js',
    'partners.js',
    'professionals.js',
    'network.js',
    'request-service.js',
    'admin.js',
    'admin-shell.js',
    'professionals-apply.js',
    'index.js'
  ];

  if (typeof document !== 'undefined' && typeof document.write === 'function') {
    document.write(moduleFiles.map(function (file) {
      return '<script src="' + base + file + '"></script>';
    }).join(''));
  }
})();
