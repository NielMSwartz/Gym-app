/* Active workout interactions: fast set editing, offline queue, rest timer. */
(function () {
  'use strict';

  var root = document.getElementById('workout-root');
  if (!root) return;

  var workoutId = root.dataset.workoutId;
  var statusBox = document.getElementById('workout-status');
  var basePayload = null;
  var debounceHandle = null;

  function showStatus(message, kind) {
    if (!statusBox) return;
    statusBox.textContent = message;
    statusBox.className = 'flash flash-' + (kind || 'info');
    statusBox.hidden = false;
  }

  function valueOf(row, field) {
    var input = row.querySelector('[data-field="' + field + '"]');
    if (!input) return null;
    if (input.type === 'checkbox') return input.checked;
    if (input.value === '') return null;
    if (input.type === 'number') return parseFloat(input.value);
    return input.value;
  }

  function fallbackPayload() {
    return {
      client_uuid: root.dataset.clientUuid,
      program_name: root.dataset.programName,
      week_number: root.dataset.weekNumber ? parseInt(root.dataset.weekNumber, 10) : null,
      training_day_name: root.dataset.dayName,
      started_at: root.dataset.startedAt,
      status: root.dataset.status,
      notes: document.getElementById('workout-notes') ? document.getElementById('workout-notes').value : '',
      exercises: []
    };
  }

  async function ensurePayload() {
    if (basePayload) return basePayload;
    try {
      var response = await fetch(root.dataset.payloadUrl, { headers: { 'Accept': 'application/json' } });
      if (response.ok) {
        basePayload = await response.json();
        basePayload.base_updated_at = basePayload.updated_at;
        return basePayload;
      }
    } catch (error) { /* offline fallback */ }
    basePayload = fallbackPayload();
    return basePayload;
  }

  async function currentPayload() {
    var payload = JSON.parse(JSON.stringify(await ensurePayload()));
    payload.notes = document.getElementById('workout-notes') ? document.getElementById('workout-notes').value : '';
    payload.status = root.dataset.status;
    root.querySelectorAll('[data-we-id]').forEach(function (weEl) {
      var exercise = payload.exercises.find(function (item) { return String(item.id) === weEl.dataset.weId; });
      if (!exercise) return;
      weEl.querySelectorAll('[data-set-id]').forEach(function (row) {
        var set = exercise.sets.find(function (item) { return String(item.id) === row.dataset.setId; });
        if (!set) return;
        set.actual_reps = valueOf(row, 'actual_reps');
        set.actual_weight_kg = valueOf(row, 'actual_weight_kg');
        set.rpe = valueOf(row, 'rpe');
        set.rir = valueOf(row, 'rir');
        set.is_completed = valueOf(row, 'is_completed') === true;
        set.notes = valueOf(row, 'notes') || '';
      });
    });
    return payload;
  }

  function queueOffline() {
    if (!window.IronOathOffline) return;
    currentPayload().then(function (payload) {
      return window.IronOathOffline.savePending(payload, 'pending');
    }).then(function () {
      showStatus('Saved on this device · pending sync. Reconnect to send it to Neon.', 'warning');
    }).catch(function (error) {
      showStatus('Could not save offline: ' + error.message, 'error');
    });
  }

  async function pushSet(row) {
    if (!navigator.onLine) {
      queueOffline();
      return;
    }
    var setId = row.dataset.setId;
    var body = {
      actual_reps: valueOf(row, 'actual_reps'),
      actual_weight_kg: valueOf(row, 'actual_weight_kg'),
      rpe: valueOf(row, 'rpe'),
      rir: valueOf(row, 'rir'),
      notes: valueOf(row, 'notes') || '',
      is_completed: valueOf(row, 'is_completed') === true
    };
    row.classList.toggle('completed-set', body.is_completed);
    try {
      var response = await fetch('/workouts/' + workoutId + '/sets/' + setId, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      if (!response.ok) throw new Error('save failed');
      showStatus('Set saved to Neon.', 'success');
    } catch (error) {
      queueOffline();
    }
  }

  document.addEventListener('change', function (event) {
    var row = event.target.closest('[data-set-id]');
    if (row) pushSet(row);
  });

  document.addEventListener('input', function (event) {
    if (!event.target.closest('[data-set-id]') || navigator.onLine) return;
    clearTimeout(debounceHandle);
    debounceHandle = setTimeout(queueOffline, 800);
  });

  root.addEventListener('click', async function (event) {
    var button = event.target.closest('[data-action]');
    if (!button) return;
    var weEl = button.closest('[data-we-id]');
    var setRow = button.closest('[data-set-id]');
    var url;

    if (button.dataset.action === 'add-set' && weEl) {
      url = '/workouts/' + workoutId + '/sets';
    } else if (button.dataset.action === 'delete-set' && setRow) {
      url = '/workouts/' + workoutId + '/sets/' + setRow.dataset.setId + '/delete';
    } else if (button.dataset.action === 'remove-exercise' && weEl) {
      if (!window.confirm('Remove this exercise from the current workout?')) return;
      url = '/workouts/' + workoutId + '/exercises/' + weEl.dataset.weId + '/delete';
    } else {
      return;
    }

    try {
      var response = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' } });
      if (!response.ok) throw new Error('request failed');
      window.location.reload();
    } catch (error) {
      showStatus('Could not update this workout. Your latest edits are still on screen.', 'error');
    }
  });

  var copyButton = document.getElementById('copy-previous');
  if (copyButton) {
    copyButton.addEventListener('click', async function () {
      try {
        var response = await fetch('/workouts/' + workoutId + '/copy-previous', { method: 'POST' });
        var result = await response.json();
        window.location.reload();
      } catch (error) {
        showStatus('Could not copy previous values.', 'error');
      }
    });
  }

  var saveNotes = document.getElementById('save-notes');
  if (saveNotes) {
    saveNotes.addEventListener('click', async function () {
      var notes = document.getElementById('workout-notes').value;
      if (!navigator.onLine) { queueOffline(); return; }
      try {
        await fetch('/workouts/' + workoutId + '/notes', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ notes: notes })
        });
        showStatus('Notes saved.', 'success');
      } catch (error) { queueOffline(); }
    });
  }

  var saveOffline = document.getElementById('save-offline');
  if (saveOffline) {
    saveOffline.addEventListener('click', function () {
      if (navigator.onLine) {
        showStatus('You are online — set edits save to Neon automatically.', 'info');
        return;
      }
      queueOffline();
    });
  }

  var complete = document.getElementById('complete-workout');
  if (complete) {
    complete.addEventListener('click', async function () {
      if (!navigator.onLine) {
        queueOffline();
        showStatus('You are offline. The workout is queued for sync; complete it once reconnected.', 'warning');
        return;
      }
      if (!window.confirm('Mark this workout complete? Personal records will be recalculated.')) return;
      try {
        var response = await fetch('/workouts/' + workoutId + '/complete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ notes: document.getElementById('workout-notes').value })
        });
        var result = await response.json();
        if (result.redirect) window.location.href = result.redirect;
      } catch (error) {
        showStatus('Could not complete the workout. Please try again.', 'error');
      }
    });
  }

  window.addEventListener('iron-oath:synced', function () {
    showStatus('Pending workout edits synchronised with Neon.', 'success');
  });

  // Rest timer
  var restRemaining = parseInt(document.querySelector('meta[name="rest-seconds"]')?.content || '90', 10);
  var timerDisplay = document.getElementById('rest-timer');
  var timerHandle = null;
  function paintTimer() {
    if (!timerDisplay) return;
    var minutes = String(Math.floor(restRemaining / 60)).padStart(2, '0');
    var seconds = String(restRemaining % 60).padStart(2, '0');
    timerDisplay.textContent = minutes + ':' + seconds;
  }
  paintTimer();
  var startRest = document.getElementById('start-rest');
  if (startRest) {
    startRest.addEventListener('click', function () {
      clearInterval(timerHandle);
      timerHandle = setInterval(function () {
        restRemaining = Math.max(0, restRemaining - 1);
        paintTimer();
        if (restRemaining === 0) clearInterval(timerHandle);
      }, 1000);
    });
  }
  var resetRest = document.getElementById('reset-rest');
  if (resetRest) {
    resetRest.addEventListener('click', function () {
      clearInterval(timerHandle);
      restRemaining = 90;
      paintTimer();
    });
  }
})();
