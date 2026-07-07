/* תעבורה – חטיבת עפר · Service Worker
 *
 * IMPORTANT: this SW only caches the app SHELL (its own static files).
 * It NEVER touches cross-origin requests (Supabase, Anthropic, CDNs),
 * so cloud data, real-time sync and multi-device updates behave EXACTLY
 * as before — every data request always goes live to the network.
 */
const CACHE = 'tavura-v1';
const SHELL = ['./', './index.html', './manifest.json', './icon.svg',
               './icon-192.png', './icon-512.png', './icon-512-maskable.png'];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE)
      .then(c => c.addAll(SHELL))
      .then(() => self.skipWaiting())
      .catch(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const req = e.request;

  // Only handle GET; leave POST/PUT/etc. (Supabase writes, AI calls) untouched.
  if (req.method !== 'GET') return;

  const url = new URL(req.url);

  // Only handle our OWN origin. Cross-origin (Supabase, Anthropic, CDN,
  // WhatsApp, realtime websockets) is passed straight through to the network
  // so cloud sync is never intercepted or served from a stale cache.
  if (url.origin !== self.location.origin) return;

  // App navigations: network-first so users get the freshest app, with an
  // offline fallback to the cached shell.
  if (req.mode === 'navigate') {
    e.respondWith(
      fetch(req).catch(() => caches.match('./index.html'))
    );
    return;
  }

  // Same-origin static assets: cache-first (fast, offline-capable),
  // refreshing the cache copy in the background.
  e.respondWith(
    caches.match(req).then(hit => {
      const net = fetch(req).then(res => {
        if (res && res.status === 200) {
          const copy = res.clone();
          caches.open(CACHE).then(c => c.put(req, copy)).catch(() => {});
        }
        return res;
      }).catch(() => hit);
      return hit || net;
    })
  );
});
