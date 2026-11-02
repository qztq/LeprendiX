/**
 * sw.js - Service Worker für 100% Offline-Betrieb der LeprendiX Companion App.
 * Ermöglicht den Betrieb auf Tablets im Wartezimmer ohne bestehende WLAN-Verbindung zum Haupt-PC.
 */

const CACHE_NAME = 'leprendix-companion-v1.4';
const STATIC_ASSETS = [
  './',
  './index.html',
  './manifest.json',
  './logo.png',
  './favicon.ico',
  './css/style.css',
  './js/app.js',
  './js/austria_plz.js',
  './js/contracts.js',
  './js/signature.js',
  './res/contracts_index.json',
  './res/dsgvo_datenverarbeitung.json',
  './res/behandlungsvertrag.json',
  './res/telemedizin_einwilligung.json'
];

// Installation: Alle Kern-Dateien in den Cache laden
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    }).then(() => self.skipWaiting())
  );
});

// Aktivierung: Alte Caches aufräumen
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch-Handler: Cache-First für statische App-Dateien, Netzwerk-Only für APIs
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // API-Routen (Sync, Upload, Verify) NIEMALS cachen
  if (url.pathname.includes('/upload') ||
      url.pathname.includes('/sync_batch') ||
      url.pathname.includes('/verify') ||
      url.pathname.includes('/pong') ||
      url.pathname.includes('/status')) {
    return; // Normaler Netzwerkanruf
  }

  // Für statische Dateien: Cache-First mit Fallback auf Netzwerk
  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      if (cachedResponse) {
        // Im Hintergrund nach Aktualisierungen suchen (Stale-While-Revalidate)
        fetch(event.request).then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, networkResponse));
          }
        }).catch(() => {});
        return cachedResponse;
      }

      // Wenn nicht im Cache, aus Netzwerk laden
      return fetch(event.request).then((networkResponse) => {
        if (!networkResponse || networkResponse.status !== 200 || networkResponse.type !== 'basic') {
          return networkResponse;
        }
        const responseToCache = networkResponse.clone();
        caches.open(CACHE_NAME).then((cache) => {
          cache.put(event.request, responseToCache);
        });
        return networkResponse;
      }).catch(() => {
        // Offline-Fallback auf index.html falls Navigation fehlschlägt
        if (event.request.mode === 'navigate') {
          return caches.match('./index.html');
        }
      });
    })
  );
});
