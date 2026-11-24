/* Program builder: renders and serialises the complete week/day/set plan. */
(function () {
  'use strict';

  var form = document.getElementById('program-form');
  var root = document.getElementById('builder-app');
  if (!form || !root) return;

  var hidden = document.getElementById('program-payload');
  var editingWeek = root.dataset.editingWeek === '1';
  var state = JSON.parse(hidden.value || '{}');
  state.weeks = Array.isArray(state.weeks) ? state.weeks : [];

  var DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function defaultSet(number) {
    return { set_number: number, target_reps: 8, target_weight_kg: null, target_rpe: null, rest_seconds: 90, notes: '' };
  }

  function defaultExercise() {
    return {
      exercise_name: '',
      muscle_group: '',
      is_bodyweight: false,
      notes: '',
      progression_notes: '',
      sets: [defaultSet(1), defaultSet(2), defaultSet(3)]
    };
  }

  function defaultWeek(number) {
    return { week_number: number, title: 'Week ' + number, notes: '', days: [] };
  }

  function clone(value) { return JSON.parse(JSON.stringify(value)); }

  function ensureWeeks(count) {
    while (state.weeks.length < count) state.weeks.push(clone(state.weeks[0] || defaultWeek(1)));
    if (state.weeks.length > count) state.weeks = state.weeks.slice(0, count);
    state.weeks.forEach(function (week, index) { week.week_number = index + 1; });
    state.duration_weeks = count;
  }

  function renderSet(set, setIndex) {
    return '<div class="set-row" data-set="' + setIndex + '">' +
      '<span class="set-number-badge">' + (setIndex + 1) + '</span>' +
      '<input type="number" min="1" max="100" value="' + escapeHtml(set.target_reps) + '" data-field="target_reps" aria-label="Target reps" placeholder="Reps">' +
      '<input type="number" step="0.5" min="0" value="' + escapeHtml(set.target_weight_kg == null ? '' : set.target_weight_kg) + '" data-field="target_weight_kg" aria-label="Target weight kg" placeholder="kg">' +
      '<input type="number" step="0.5" min="1" max="10" value="' + escapeHtml(set.target_rpe == null ? '' : set.target_rpe) + '" data-field="target_rpe" aria-label="Target RPE" placeholder="RPE">' +
      '<input type="text" class="set-notes-input" value="' + escapeHtml(set.notes || '') + '" data-field="notes" aria-label="Set notes" placeholder="Set note">' +
      '<button type="button" class="button button-danger button-small" data-action="remove-set" title="Remove set">×</button>' +
      '</div>';
  }

  function renderExercise(assignment, exerciseIndex) {
    var setsHtml = (assignment.sets || []).map(function (set, index) {
      return renderSet(set, index);
    }).join('');
    return '<div class="assignment-editor" data-exercise="' + exerciseIndex + '">' +
      '<div class="form-row">' +
        '<div class="field"><label>Exercise name <span class="required">*</span></label>' +
          '<input type="text" data-field="exercise_name" value="' + escapeHtml(assignment.exercise_name || '') + '" required placeholder="e.g. Barbell Bench Press" aria-label="Exercise name"></div>' +
        '<div class="field"><label>Muscle group <span class="muted">(optional)</span></label>' +
          '<input type="text" data-field="muscle_group" value="' + escapeHtml(assignment.muscle_group || '') + '" placeholder="e.g. Chest"></div>' +
      '</div>' +
      '<div class="form-row" style="margin-top:10px">' +
        '<div class="field"><label>Exercise notes</label><input type="text" data-field="notes" value="' + escapeHtml(assignment.notes || '') + '" placeholder="Form cue"></div>' +
        '<div class="field"><label>Progression</label><input type="text" data-field="progression_notes" value="' + escapeHtml(assignment.progression_notes || '') + '" placeholder="+2.5kg next week"></div>' +
      '</div>' +
      '<label class="checkbox-field" style="margin-top:8px"><input type="checkbox" data-field="is_bodyweight"' + (assignment.is_bodyweight ? ' checked' : '') + '> Bodyweight exercise</label>' +
      '<div class="set-rows">' + setsHtml + '</div>' +
      '<div class="button-row" style="margin-top:8px">' +
        '<button type="button" class="button button-ghost button-small" data-action="add-set">＋ Add set</button>' +
        '<button type="button" class="button button-danger button-small" data-action="remove-exercise">Remove exercise</button>' +
      '</div>' +
    '</div>';
  }

  function renderDay(day, weekIndex, dayIndex) {
    var assignments = (day.exercises || []).map(function (assignment, index) {
      return renderExercise(assignment, index);
    }).join('');
    return '<div class="day-editor" data-day="' + dayIndex + '">' +
      '<div class="day-editor-head">' +
        '<div class="field" style="width:150px"><label>Day</label><select data-field="day_of_week">' +
          DAY_NAMES.map(function (name, index) {
            return '<option value="' + index + '"' + (day.day_of_week === index ? ' selected' : '') + '>' + name + '</option>';
          }).join('') +
        '</select></div>' +
        '<div class="field" style="flex:1"><label>Session name</label><input type="text" data-field="label" value="' + escapeHtml(day.label || '') + '" placeholder="e.g. Legs"></div>' +
        '<label class="checkbox-field"><input type="checkbox" data-field="is_rest"' + (day.is_rest ? ' checked' : '') + '> Rest day</label>' +
        '<button type="button" class="button button-danger button-small" data-action="remove-day">Remove</button>' +
      '</div>' +
      '<div class="field" style="margin-top:10px"><label>Day notes</label><input type="text" data-field="notes" value="' + escapeHtml(day.notes || '') + '" placeholder="Optional session notes"></div>' +
      '<div class="assignments">' + assignments + '</div>' +
      '<button type="button" class="button button-ghost button-small" data-action="add-exercise" style="margin-top:10px">＋ Add exercise</button>' +
    '</div>';
  }

  function renderWeek(week, index) {
    var days = (week.days || []).map(function (day, dayIndex) {
      return renderDay(day, index, dayIndex);
    }).join('');
    return '<section class="week-editor" data-week="' + index + '">' +
      '<div class="week-editor-head">' +
        '<div><h3>Week ' + (index + 1) + '</h3><span class="muted">' + escapeHtml(week.title || '') + '</span></div>' +
        '<div class="button-row">' +
          '<button type="button" class="button button-ghost button-small" data-action="copy-week">Copy to all weeks</button>' +
          (editingWeek ? '' : '<button type="button" class="button button-danger button-small" data-action="remove-week">Remove week</button>') +
        '</div>' +
      '</div>' +
      '<div class="form-row"><div class="field"><label>Week title</label><input type="text" data-field="title" value="' + escapeHtml(week.title || '') + '"></div>' +
      '<div class="field"><label>Week notes</label><input type="text" data-field="notes" value="' + escapeHtml(week.notes || '') + '" placeholder="Deload, intensity, etc."></div></div>' +
      '<div class="days">' + days + '</div>' +
      '<button type="button" class="button button-ghost button-small" data-action="add-day" style="margin-top:10px">＋ Add training day</button>' +
    '</section>';
  }

  function render() {
    root.innerHTML = state.weeks.map(renderWeek).join('');
    syncHidden();
  }

  function syncHidden() {
    hidden.value = JSON.stringify(state);
  }

  function readFormFields() {
    ['name', 'description', 'start_date', 'duration'].forEach(function (id) {
      var element = document.getElementById(id === 'name' ? 'name' : id === 'description' ? 'description' : id === 'start_date' ? 'start_date' : 'duration');
      if (!element) return;
      if (id === 'name') state.name = element.value;
      if (id === 'description') state.description = element.value;
      if (id === 'start_date') state.start_date = element.value;
      if (id === 'duration') ensureWeeks(parseInt(element.value, 10) || 8);
    });
  }

  function updateStateFromDom() {
    readFormFields();
    Array.prototype.forEach.call(root.querySelectorAll('[data-week]'), function (weekEl) {
      var week = state.weeks[parseInt(weekEl.dataset.week, 10)];
      if (!week) return;
      week.title = weekEl.querySelector('[data-field="title"]').value;
      week.notes = weekEl.querySelector('[data-field="notes"]').value;
      Array.prototype.forEach.call(weekEl.querySelectorAll('[data-day]'), function (dayEl) {
        var day = week.days[parseInt(dayEl.dataset.day, 10)];
        if (!day) return;
        day.day_of_week = parseInt(dayEl.querySelector('[data-field="day_of_week"]').value, 10);
        day.label = dayEl.querySelector('[data-field="label"]').value;
        day.is_rest = dayEl.querySelector('[data-field="is_rest"]').checked;
        day.notes = dayEl.querySelector('[data-field="notes"]').value;
        Array.prototype.forEach.call(dayEl.querySelectorAll('[data-exercise]'), function (exEl) {
          var assignment = day.exercises[parseInt(exEl.dataset.exercise, 10)];
          if (!assignment) return;
          assignment.exercise_name = exEl.querySelector('[data-field="exercise_name"]').value;
          assignment.muscle_group = exEl.querySelector('[data-field="muscle_group"]').value;
          assignment.is_bodyweight = exEl.querySelector('[data-field="is_bodyweight"]').checked;
          assignment.notes = exEl.querySelector('[data-field="notes"]').value;
          assignment.progression_notes = exEl.querySelector('[data-field="progression_notes"]').value;
          Array.prototype.forEach.call(exEl.querySelectorAll('[data-set]'), function (setEl) {
            var set = assignment.sets[parseInt(setEl.dataset.set, 10)];
            if (!set) return;
            set.target_reps = parseInt(setEl.querySelector('[data-field="target_reps"]').value, 10) || 1;
            var weight = setEl.querySelector('[data-field="target_weight_kg"]').value;
            set.target_weight_kg = weight === '' ? null : parseFloat(weight);
            var rpe = setEl.querySelector('[data-field="target_rpe"]').value;
            set.target_rpe = rpe === '' ? null : parseFloat(rpe);
            set.notes = setEl.querySelector('[data-field="notes"]').value;
          });
        });
      });
    });
    syncHidden();
  }

  function validateExerciseNames() {
    var valid = true;
    Array.prototype.forEach.call(root.querySelectorAll('[data-exercise]'), function (exEl) {
      var input = exEl.querySelector('[data-field="exercise_name"]');
      if (!input) return;
      var empty = !input.value.trim();
      input.classList.toggle('invalid', empty);
      if (empty) valid = false;
    });
    if (!valid) alert('Enter a name for each exercise, or remove the empty exercise.');
    return valid;
  }

  root.addEventListener('click', function (event) {
    var button = event.target.closest('[data-action]');
    if (!button) return;
    event.preventDefault();
    updateStateFromDom();
    var weekEl = button.closest('[data-week]');
    var dayEl = button.closest('[data-day]');
    var exEl = button.closest('[data-exercise]');
    var setEl = button.closest('[data-set]');
    var week = weekEl ? state.weeks[parseInt(weekEl.dataset.week, 10)] : null;
    var day = dayEl && week ? week.days[parseInt(dayEl.dataset.day, 10)] : null;
    var assignment = exEl && day ? day.exercises[parseInt(exEl.dataset.exercise, 10)] : null;

    switch (button.dataset.action) {
      case 'add-week':
        ensureWeeks(state.weeks.length + 1);
        render();
        break;
      case 'remove-week':
        if (state.weeks.length > 1) { state.weeks.splice(parseInt(weekEl.dataset.week, 10), 1); ensureWeeks(state.weeks.length); render(); }
        break;
      case 'copy-week':
        for (var i = 0; i < state.weeks.length; i += 1) {
          if (i !== parseInt(weekEl.dataset.week, 10)) state.weeks[i] = clone(week);
        }
        render();
        break;
      case 'add-day':
        var used = week.days.map(function (d) { return d.day_of_week; });
        var nextDay = DAY_NAMES.findIndex(function (_, i) { return used.indexOf(i) === -1; });
        if (nextDay < 0) { alert('All seven days are already configured.'); return; }
        week.days.push({ day_of_week: nextDay, label: DAY_NAMES[nextDay], is_rest: false, notes: '', exercises: [] });
        render();
        break;
      case 'remove-day':
        week.days.splice(parseInt(dayEl.dataset.day, 10), 1);
        render();
        break;
      case 'add-exercise':
        day.exercises.push(defaultExercise());
        render();
        break;
      case 'remove-exercise':
        day.exercises.splice(parseInt(exEl.dataset.exercise, 10), 1);
        render();
        break;
      case 'add-set':
        assignment.sets.push(defaultSet(assignment.sets.length + 1));
        render();
        break;
      case 'remove-set':
        assignment.sets.splice(parseInt(setEl.dataset.set, 10), 1);
        render();
        break;
      default:
        break;
    }
  });

  form.addEventListener('input', updateStateFromDom);
  form.addEventListener('change', updateStateFromDom);
  form.addEventListener('submit', function (event) {
    updateStateFromDom();
    var name = document.getElementById('name');
    if (name && !name.value.trim()) {
      event.preventDefault();
      alert('Please give your program a name.');
      name.focus();
      return false;
    }
    if (!validateExerciseNames()) {
      event.preventDefault();
      return false;
    }
  });

  var copyTemplate = document.getElementById('copy-template');
  if (copyTemplate) {
    copyTemplate.addEventListener('click', function () {
      updateStateFromDom();
      var template = clone(state.weeks[0]);
      state.weeks.forEach(function (week, index) {
        if (index > 0) state.weeks[index] = clone(template);
      });
      render();
    });
  }

  var addWeek = document.getElementById('add-week');
  if (addWeek) {
    addWeek.addEventListener('click', function () {
      updateStateFromDom();
      ensureWeeks(state.weeks.length + 1);
      var duration = document.getElementById('duration');
      if (duration) duration.value = String(state.weeks.length);
      render();
    });
  }

  if (!state.weeks.length) state.weeks.push(defaultWeek(1));
  render();
})();
