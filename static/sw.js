const CACHE_NAME = 'ngenoai-shell-v1';
const APP_SHELL = [
  '/',
  '/static/style.css',
  '/static/app.js',
  '/static/manifest.json',
  '/static/icons/ngenoai-192.png',
  '/static/icons/ngenoai-512.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((key) => key.startsWith('ngenoai-shell-') && key !== CACHE_NAME)
          .map((key) => caches.delete(key))
    ))
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin) return;

  // Never cache API results, authentication responses, profile data, or uploads.
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/static/uploads/')) return;

  if (request.mode === 'navigate') {
    event.respondWith(fetch(request).then((response) => {
      if (response && response.ok) {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put('/', copy));
      }
      return response;
    }).catch(async () => {
      const cached = await caches.match('/');
      if (cached) return cached;
      return new Response('<!doctype html><html lang="en"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NgenoAI offline</title><body style="font-family:Arial,sans-serif;padding:2rem;max-width:36rem;margin:auto"><h1>NgenoAI 🇳🇦</h1><h2>You are offline</h2><p>The app shell may open, but AI tutoring, login, saving progress, translation and image generation need an internet connection.</p><p>Reconnect and refresh to continue learning.</p></body></html>', {headers: {'Content-Type': 'text/html; charset=utf-8'}});
    }));
    return;
  }

  if (url.pathname.startsWith('/static/')) {
    event.respondWith(caches.match(request).then((cached) => cached || fetch(request).then((response) => {
      if (response && response.ok) {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
      }
      return response;
    })));
  }
});
