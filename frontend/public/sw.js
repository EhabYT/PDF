/* Public shell only. Never cache API responses, cookies or private documents. */
const CACHE = 'omnifix-shell-v2';
const SHELL = ['/offline.html', '/manifest.webmanifest', '/icons/icon-192.png', '/icons/icon-512.png'];
self.addEventListener('install', event => { event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL)).then(() => self.skipWaiting())); });
self.addEventListener('activate', event => { event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/') || url.pathname.startsWith('/storage/') || event.request.headers.has('Authorization')) return;
  if (event.request.mode === 'navigate') {
    event.respondWith(fetch(event.request).then(response => { if (response.ok && !response.headers.get('set-cookie')) { const copy = response.clone(); caches.open(CACHE).then(cache => cache.put(event.request, copy)); } return response; }).catch(async () => (await caches.match(event.request)) || (await caches.match('/offline.html'))));
    return;
  }
  if (url.pathname.startsWith('/_next/static/') || url.pathname.startsWith('/icons/') || SHELL.includes(url.pathname)) {
    event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request).then(response => { if (response.ok && !response.headers.get('set-cookie')) { const copy = response.clone(); caches.open(CACHE).then(cache => cache.put(event.request, copy)); } return response; })));
  }
});
