/* Shared UI behaviour: flashes, PWA installation, service worker updates. */
(function () {
  'use strict';

  document.addEventListener('click', function (event) {
    var close = event.target.closest('.flash-close');
    if (close) {
      var flash = close.closest('.flash');
      if (flash) flash.remove();
    }

    var destructive = event.target.closest('[data-confirm]');
    if (destructive && destructive.tagName === 'FORM') {
      if (!window.confirm(destructive.dataset.confirm || 'Are you sure?')) {
        event.preventDefault();
      }
    }
  });

  if ('serviceWorker' in navigator && (location.protocol === 'https:' || ['localhost', '127.0.0.1'].includes(location.hostname))) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('/sw.js', { scope: '/' }).then(function (registration) {
        var installButton = document.getElementById('install-button');

        function setUpdateReady() {
          if (installButton) {
            installButton.textContent = 'Update app';
            installButton.hidden = false;
            installButton.dataset.update = 'true';
          }
        }

        if (registration.waiting) setUpdateReady();
        registration.addEventListener('updatefound', function () {
          var installing = registration.installing;
          if (!installing) return;
          installing.addEventListener('statechange', function () {
            if (installing.state === 'installed' && navigator.serviceWorker.controller) setUpdateReady();
          });
        });

        if (installButton) {
          var deferredPrompt = null;
          window.addEventListener('beforeinstallprompt', function (event) {
            event.preventDefault();
            deferredPrompt = event;
            installButton.hidden = false;
          });
          window.addEventListener('appinstalled', function () {
            installButton.hidden = true;
            deferredPrompt = null;
          });

          installButton.addEventListener('click', async function () {
            if (installButton.dataset.update === 'true' && registration.waiting) {
              registration.waiting.postMessage({ type: 'SKIP_WAITING' });
              window.location.reload();
              return;
            }
            if (deferredPrompt) {
              deferredPrompt.prompt();
              await deferredPrompt.userChoice;
              deferredPrompt = null;
              installButton.hidden = true;
            }
          });
        }
      }).catch(function (error) {
        console.warn('Service worker registration failed:', error);
      });
    });
  }
})();
