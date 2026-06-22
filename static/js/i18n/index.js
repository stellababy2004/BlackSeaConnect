/* Auto-generated i18n bundle merger */
(function () {
  function isPlainObject(value) {
    return !!value && Object.prototype.toString.call(value) === '[object Object]';
  }

  function deepMerge(target, source) {
    if (!isPlainObject(target) || !isPlainObject(source)) {
      return target;
    }

    Object.keys(source).forEach(function (key) {
      var sourceValue = source[key];
      if (isPlainObject(sourceValue)) {
        if (!isPlainObject(target[key])) {
          target[key] = {};
        }
        deepMerge(target[key], sourceValue);
      } else {
        target[key] = sourceValue;
      }
    });

    return target;
  }

  window.BlackSeaI18N = window.BlackSeaI18N || {};
  window.BlackSeaI18NModules = window.BlackSeaI18NModules || {};

  Object.keys(window.BlackSeaI18NModules).forEach(function (moduleName) {
    deepMerge(window.BlackSeaI18N, window.BlackSeaI18NModules[moduleName]);
  });
})();
