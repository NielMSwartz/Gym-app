/* IndexedDB-backed offline workout queue with idempotent server sync. */
(function () {
  'use strict';

  var DB_NAME = 'iron-oath-offline';
  var DB_VERSION = 1;
  var STORE = 'pending_workouts';
  var dbPromise = null;

  function openDb() {
    if (dbPromise) return dbPromise;
    dbPromise = new Promise(function (resolve, reject) {
      if (!('indexedDB' in window)) {
        reject(new Error('IndexedDB is not available'));
        return;
      }
      var request = indexedDB.open(DB_NAME, DB_VERSION);
      request.onupgradeneeded = function () {
        var db = request.result;
        if (!db.objectStoreNames.contains(STORE)) {
          db.createObjectStore(STORE, { keyPath: 'client_uuid' });
        }
      };
      request.onsuccess = function () { resolve(request.result); };
      request.onerror = function () { reject(request.error); };
    });
    return dbPromise;
  }

  function tx(mode, handler) {
    return openDb().then(function (db) {
      return new Promise(function (resolve, reject) {
        var transaction = db.transaction(STORE, mode);
        var store = transaction.objectStore(STORE);
        var request = handler(store);
        transaction.oncomplete = function () { resolve(request ? request.result : null); };
        transaction.onerror = function () { reject(transaction.error); };
      });
    });
  }

  function savePending(payload, status) {
    var record = Object.assign({}, payload, {
      sync_status: status || 'pending',
      queued_at: new Date().toISOString()
    });
    return tx('readwrite', function (store) { return store.put(record); }).then(function () {
      updateIndicator();
      return record;
    });
  }

  function allPending() {
    return tx('readonly', function (store) { return store.getAll(); });
  }

  function removePending(clientUuid) {
    return tx('readwrite', function (store) { return store.delete(clientUuid); }).then(updateIndicator);
  }

  function updateIndicator() {
    var pill = document.getElementById('sync-indicator');
    if (!pill) return;
    allPending().then(function (items) {
      var conflicts = items.filter(function (item) { return item.sync_status === 'conflict'; }).length;
      if (conflicts) {
        pill.textContent = conflicts + ' sync conflict' + (conflicts === 1 ? '' : 's');
        pill.className = 'sync-pill conflict';
      } else if (items.length) {
        pill.textContent = items.length + ' pending sync';
        pill.className = 'sync-pill pending';
      } else {
        pill.hidden = true;
        pill.className = 'sync-pill';
      }
    }).catch(function () { /* indicator is best-effort */ });
  }

  async function flushQueue() {
    if (!navigator.onLine) return { flushed: 0, conflicts: 0 };
    var items;
    try {
      items = await allPending();
    } catch (error) {
      console.warn('Could not read offline queue:', error);
      return { flushed: 0, conflicts: 0 };
    }
    var flushed = 0;
    var conflicts = 0;
    for (var index = 0; index < items.length; index += 1) {
      var item = items[index];
      var payload = Object.assign({}, item, { base_updated_at: item.base_updated_at || item.updated_at });
      delete payload.sync_status;
      delete payload.queued_at;
      try {
        var response = await fetch('/api/sync/workouts', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        var result = await response.json();
        if (response.ok && result.status === 'applied') {
          await removePending(item.client_uuid);
          flushed += 1;
        } else if (response.status === 409) {
          item.sync_status = 'conflict';
          item.conflict_message = result.message || 'Server record is newer.';
          await savePending(item, 'conflict');
          conflicts += 1;
        } else {
          break;
        }
      } catch (error) {
        break;
      }
    }
    updateIndicator();
    if (flushed) window.dispatchEvent(new CustomEvent('iron-oath:synced', { detail: { count: flushed } }));
    return { flushed: flushed, conflicts: conflicts };
  }

  function updateNetwork() {
    var banner = document.getElementById('offline-banner');
    if (banner) banner.hidden = navigator.onLine;
    if (navigator.onLine) flushQueue();
    else updateIndicator();
  }

  window.addEventListener('online', updateNetwork);
  window.addEventListener('offline', updateNetwork);
  document.addEventListener('DOMContentLoaded', function () {
    updateNetwork();
    updateIndicator();
  });

  window.IronOathOffline = {
    savePending: savePending,
    allPending: allPending,
    removePending: removePending,
    flushQueue: flushQueue,
    updateIndicator: updateIndicator
  };
})();
