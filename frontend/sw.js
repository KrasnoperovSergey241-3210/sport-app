const cacheName = 'sport-pulse-shell-__CACHE_VERSION__'
const shell = /* SHELL_FILES */ []

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(cacheName).then((cache) => cache.addAll(shell)))
})

self.addEventListener('activate', (event) => {
  event.waitUntil(Promise.all([
    self.clients.claim(),
    caches.keys().then((names) => Promise.all(names.filter((name) => name.startsWith('sport-pulse-shell-') && name !== cacheName).map((name) => caches.delete(name)))),
  ]))
})

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url)
  if (event.request.method !== 'GET' || url.origin !== location.origin || url.pathname.startsWith('/api/')) return
  if (event.request.mode === 'navigate') {
    event.respondWith(fetch(event.request).catch(() => caches.open(cacheName).then((cache) => cache.match('/index.html'))))
  } else if (shell.includes(url.pathname)) {
    event.respondWith(caches.open(cacheName).then(async (cache) => (await cache.match(url.pathname)) || fetch(event.request)))
  }
})
