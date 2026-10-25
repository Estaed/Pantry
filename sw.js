/* Pantry service worker: the app opens offline, and an online launch always gets the newest files.
   Every same-origin GET goes to the network first (revalidating past the HTTP cache, so a GitHub Pages deploy
   shows on the next launch) and falls back to the cache when offline or after 3 s without an answer.
   Install stores the shell below plus every feature in app/registry.js, so a new feature needs no edit here.
   CACHE is 'pantry-v' + CHANGELOG.md's newest version, set on every release; activate drops the older caches. */
const CACHE = 'pantry-v0.5.0';   // CHANGELOG.md's newest version
importScripts('app/registry.js');

const SHELL = [
  'index.html', 'manifest.json', 'tokens.css', 'app/base.css', 'app/registry.js', 'app/core.js',
  'fonts/archivo.css', 'fonts/Archivo-latin.woff2', 'fonts/Archivo-latin-ext.woff2', 'fonts/Manrope.woff2',
  'icons/icon-192.png', 'icons/icon-512.png',
];
const WAIT_MS = 3000;

self.addEventListener('install', event => {
  self.skipWaiting();
  const files = SHELL.concat(self.PANTRY_FEATURES || []);
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(files.map(f => new Request(f, { cache: 'reload' })))));
});

self.addEventListener('activate', event => {
  event.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k.startsWith('pantry-') && k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET' || new URL(request.url).origin !== self.location.origin) return;

  let saved = Promise.resolve();
  const network = fetch(request.mode === 'navigate' ? request.url : request, { cache: 'no-cache' }).then(response => {
    if (response.ok && response.type === 'basic') {
      const copy = response.clone();
      saved = caches.open(CACHE).then(cache => cache.put(request, copy));
    }
    return response;
  });
  const cached = () => caches.match(request)
    .then(hit => hit || (request.mode === 'navigate' ? caches.match('index.html') : undefined));
  const slow = new Promise(resolve => setTimeout(resolve, WAIT_MS)).then(() => cached().then(hit => hit || network));

  event.respondWith(Promise.race([network, slow]).catch(() => cached().then(hit => hit || Response.error())));
  event.waitUntil(network.then(() => saved, () => undefined));
});
