/* Chart.js rendering for the statistics page. */
(function () {
  'use strict';

  var data = window.IRON_OATH_STATS;
  if (!data || !window.Chart) return;

  Chart.defaults.color = '#a89e8c';
  Chart.defaults.borderColor = 'rgba(201,162,77,0.16)';
  Chart.defaults.font.family = 'Segoe UI, Roboto, Helvetica, Arial, sans-serif';

  function chart(id, config) {
    var canvas = document.getElementById(id);
    if (canvas) new Chart(canvas, config);
  }

  var lineOptions = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: { legend: { labels: { color: '#e8dfcd' } } },
    scales: {
      x: { ticks: { color: '#a89e8c', maxRotation: 45 }, grid: { color: 'rgba(255,255,255,0.04)' } },
      y: { beginAtZero: true, ticks: { color: '#a89e8c' }, grid: { color: 'rgba(201,162,77,0.12)' } }
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
            borderColor: '#c9a24d',
            backgroundColor: 'rgba(201,162,77,0.18)',
            tension: 0.25,
            yAxisID: 'y'
          },
          {
            label: 'Estimated 1RM (Epley)',
            data: data.e1rm.map(function (point) { return point.value; }),
            borderColor: '#a72a39',
            backgroundColor: 'rgba(167,42,57,0.12)',
            tension: 0.25,
            yAxisID: 'y1'
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#e8dfcd' } }, tooltip: { callbacks: { label: function (context) { return context.dataset.label + ': ' + context.parsed.y + ' kg'; } } } },
        scales: {
          x: { ticks: { color: '#a89e8c' } },
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
        datasets: [{ label: 'Volume (kg)', data: data.volume_by_week.map(function (point) { return point.volume; }), backgroundColor: 'rgba(125,31,43,0.75)', borderColor: '#c9a24d', borderWidth: 1 }]
      },
      options: lineOptions
    });
  }

  if (data.volume_by_muscle.length) {
    chart('muscle-volume-chart', {
      type: 'bar',
      data: {
        labels: data.volume_by_muscle.map(function (point) { return point.label; }),
        datasets: [{ label: 'Volume (kg)', data: data.volume_by_muscle.map(function (point) { return point.volume; }), backgroundColor: 'rgba(201,162,77,0.6)', borderColor: '#ecdc7e', borderWidth: 1 }]
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
          { label: 'Completed', data: data.consistency.completed, backgroundColor: 'rgba(111,155,98,0.75)' },
          { label: 'Planned', data: data.consistency.planned, backgroundColor: 'rgba(201,162,77,0.5)' }
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
        datasets: [{ label: 'Volume (kg)', data: data.volume_by_exercise.slice(0, 12).map(function (point) { return point.volume; }), backgroundColor: 'rgba(167,42,57,0.7)' }]
      },
      options: Object.assign({}, lineOptions, { indexAxis: 'y' })
    });
  }

  if (data.volume_by_workout.length) {
    chart('workout-volume-chart', {
      type: 'line',
      data: {
        labels: data.volume_by_workout.map(function (point) { return point.date; }),
        datasets: [{ label: 'Session volume (kg)', data: data.volume_by_workout.map(function (point) { return point.volume; }), borderColor: '#6f9b62', backgroundColor: 'rgba(111,155,98,0.15)', fill: true, tension: 0.2 }]
      },
      options: lineOptions
    });
  }
})();
