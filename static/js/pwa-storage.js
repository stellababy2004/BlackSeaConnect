(() => {
  "use strict";

  const DB_NAME = "blacksea-professional-offline";
  const DB_VERSION = 1;
  const STORE_NAMES = ["tasks", "mutations", "uploads", "conflicts", "drafts"];
  let databasePromise;

  const requestResult = (request) => new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });

  const open = () => {
    if (databasePromise) return databasePromise;
    databasePromise = new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);
      request.onupgradeneeded = () => {
        const database = request.result;
        if (!database.objectStoreNames.contains("tasks")) database.createObjectStore("tasks", {keyPath: "id"});
        if (!database.objectStoreNames.contains("mutations")) {
          const store = database.createObjectStore("mutations", {keyPath: "id"});
          store.createIndex("createdAt", "createdAt", {unique: false});
          store.createIndex("taskId", "taskId", {unique: false});
          store.createIndex("status", "status", {unique: false});
        }
        if (!database.objectStoreNames.contains("uploads")) {
          const store = database.createObjectStore("uploads", {keyPath: "id"});
          store.createIndex("mutationId", "mutationId", {unique: false});
        }
        if (!database.objectStoreNames.contains("conflicts")) database.createObjectStore("conflicts", {keyPath: "id"});
        if (!database.objectStoreNames.contains("drafts")) database.createObjectStore("drafts", {keyPath: "taskId"});
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
      request.onblocked = () => reject(new Error("IndexedDB upgrade blocked"));
    });
    return databasePromise;
  };

  const withStore = async (storeName, mode, operation) => {
    const database = await open();
    const transaction = database.transaction(storeName, mode);
    const result = await operation(transaction.objectStore(storeName));
    await new Promise((resolve, reject) => {
      transaction.oncomplete = resolve;
      transaction.onerror = () => reject(transaction.error);
      transaction.onabort = () => reject(transaction.error || new Error("IndexedDB transaction aborted"));
    });
    return result;
  };

  const put = (storeName, value) => withStore(storeName, "readwrite", (store) => requestResult(store.put(value)));
  const get = (storeName, key) => withStore(storeName, "readonly", (store) => requestResult(store.get(key)));
  const remove = (storeName, key) => withStore(storeName, "readwrite", (store) => requestResult(store.delete(key)));
  const getAll = (storeName) => withStore(storeName, "readonly", (store) => requestResult(store.getAll()));

  const clearAll = async () => {
    const database = await open();
    const transaction = database.transaction(STORE_NAMES, "readwrite");
    STORE_NAMES.forEach((name) => transaction.objectStore(name).clear());
    await new Promise((resolve, reject) => {
      transaction.oncomplete = resolve;
      transaction.onerror = () => reject(transaction.error);
      transaction.onabort = () => reject(transaction.error || new Error("IndexedDB cleanup aborted"));
    });
  };

  const listMutations = async () => {
    const records = await getAll("mutations");
    return records.sort((left, right) => String(left.createdAt).localeCompare(String(right.createdAt)) || String(left.id).localeCompare(String(right.id)));
  };

  const api = {
    DB_NAME,
    DB_VERSION,
    open,
    putTask: (value) => put("tasks", value),
    getTask: (key) => get("tasks", key),
    putMutation: (value) => put("mutations", value),
    getMutation: (key) => get("mutations", key),
    removeMutation: (key) => remove("mutations", key),
    listMutations,
    putUpload: (value) => put("uploads", value),
    getUpload: (key) => get("uploads", key),
    removeUpload: (key) => remove("uploads", key),
    listUploads: () => getAll("uploads"),
    putConflict: (value) => put("conflicts", value),
    removeConflict: (key) => remove("conflicts", key),
    listConflicts: () => getAll("conflicts"),
    putDraft: (value) => put("drafts", value),
    getDraft: (taskId) => get("drafts", taskId),
    removeDraft: (taskId) => remove("drafts", taskId),
    clearAll,
  };

  globalThis.BlackSeaOfflineStore = api;
})();
