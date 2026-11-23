/* Chart.js rendering for the statistics page. */
(function () {
  'use strict';

  var data = window.GYM_LOGBOOK_STATS;
  if (!data || !window.Chart) return;

  Chart.defaults.color = '#a2aab8';
  Chart.defaults.borderColor = 'rgba(255,255,255,0.08)';
  Chart.defaults.font.family = 'Segoe UI, Roboto, Helvetica, Arial, sans-serif';

  function chart(id, config) {
    var canvas = document.getElementById(id);
    if (canvas) new Chart(canvas, config);
  }

  var lineOptions = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: { legend: { labels: { color: '#eef1f5' } } },
    scales: {
      x: { ticks: { color: '#a2aab8', maxRotation: 45 }, grid: { color: 'rgba(255,255,255,0.04)' } },
      y: { beginAtZero: true, ticks: { color: '#a2aab8' }, grid: { color: 'rgba(255,255,255,0.06)' } }
    }
  };

  if (data.strength && data.strength.length) {
    chart('strength-chart', {
      type: 'line',
      data: {
        labels: data.strength.map(function (point) { return point.date; }),
        datasets: [
          {
            label: 'Load lifted (kg)',
            data: data.strength.map(function (point) { return point.weight; }),
            borderColor: '#9aa4b2',
            backgroundColor: 'rgba(154,164,178,0.16)',
            tension: 0.25,
            yAxisID: 'y'
          },
          {
            label: 'Estimated 1RM (Epley)',
            data: data.e1rm.map(function (point) { return point.value; }),
            borderColor: '#d53246',
            backgroundColor: 'rgba(213,50,70,0.14)',
            tension: 0.25,
            yAxisID: 'y1'
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#eef1f5' } }, tooltip: { callbacks: { label: function (context) { return context.dataset.label + ': ' + context.parsed.y + ' kg'; } } } },
        scales: {
          x: { ticks: { color: '#a2aab8' } },
          y: { type: 'linear', position: 'left', beginAtZero: true, title: { display: true, text: 'Load (kg)' } },
          y1: { type: 'linear', position: 'right', beginAtZero: true, grid: { drawOnChartArea: false }, title: { display: true, text: 'E1RM estimate (kg)' } }
        }
      }
    });
  }

  if (data.volume_by_week.length) {
    chart('weekly-volume-chart', {
      type: 'bar',
      data: {
        labels: data.volume_by_week.map(function (point) { return point.week; }),
        datasets: [{ label: 'Volume (kg)', data: data.volume_by_week.map(function (point) { return point.volume; }), backgroundColor: 'rgba(180,35,52,0.75)', borderColor: '#d53246', borderWidth: 1 }]
      },
      options: lineOptions
    });
  }

  if (data.volume_by_muscle.length) {
    chart('muscle-volume-chart', {
      type: 'bar',
      data: {
        labels: data.volume_by_muscle.map(function (point) { return point.label; }),
        datasets: [{ label: 'Volume (kg)', data: data.volume_by_muscle.map(function (point) { return point.volume; }), backgroundColor: 'rgba(154,164,178,0.55)', borderColor: '#cfd6e0', borderWidth: 1 }]
      },
      options: Object.assign({}, lineOptions, { indexAxis: 'y' })
    });
  }

  if (data.consistency) {
    chart('consistency-chart', {
      type: 'bar',
      data: {
        labels: data.consistency.labels,
        datasets: [
          { label: 'Completed', data: data.consistency.completed, backgroundColor: 'rgba(180,35,52,0.8)' },
          { label: 'Planned', data: data.consistency.planned, backgroundColor: 'rgba(154,164,178,0.4)' }
        ]
      },
      options: lineOptions
    });
  }

  if (data.volume_by_exercise.length) {
    chart('exercise-volume-chart', {
      type: 'bar',
      data: {
        labels: data.volume_by_exercise.slice(0, 12).map(function (point) { return point.label; }),
        datasets: [{ label: 'Volume (kg)', data: data.volume_by_exercise.slice(0, 12).map(function (point) { return point.volume; }), backgroundColor: 'rgba(213,50,70,0.72)' }]
      },
      options: Object.assign({}, lineOptions, { indexAxis: 'y' })
    });
  }

  if (data.volume_by_workout.length) {
    chart('workout-volume-chart', {
      type: 'line',
      data: {
        labels: data.volume_by_workout.map(function (point) { return point.date; }),
        datasets: [{ label: 'Session volume (kg)', data: data.volume_by_workout.map(function (point) { return point.volume; }), borderColor: '#d53246', backgroundColor: 'rgba(180,35,52,0.16)', fill: true, tension: 0.2 }]
      },
      options: lineOptions
    });
  }
})();
