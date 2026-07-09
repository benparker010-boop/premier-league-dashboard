/* Kit Tracker service worker.
   Deliberately minimal: it exists mainly to make the app installable and to
   cache the static shell (CSS/JS/icons) for fast loads. It NEVER caches
   navigations or /api responses, so scan data and page state are always live
   — offline support is out of scope by design. Bump CACHE to invalidate. */
const CACHE = "kit-tracker-v1";
const ASSETS = [
  "/static/css/style.css",
  "/static/js/scanner.js",
  "/static/manifest.webmanifest",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
  "/static/icons/apple-touch-icon.png",
  "/static/icons/favicon-32.png",
];

self.addEventListener("install", function (event) {
  event.waitUntil(
    caches.open(CACHE)
      .then(function (cache) { return cache.addAll(ASSETS); })
      .then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches.keys()
      .then(function (keys) {
        return Promise.all(
          keys.filter(function (k) { return k !== CACHE; })
              .map(function (k) { return caches.delete(k); })
        );
      })
      .then(function () { return self.clients.claim(); })
  );
});

self.addEventListener("fetch", function (event) {
  var req = event.request;
  if (req.method !== "GET") return; // never intercept scans / form posts
  var url = new URL(req.url);
  if (url.origin !== self.location.origin) return; // let the CDN handle itself
  // Cache-first only for our own static assets; everything else hits network.
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(req).then(function (cached) {
        return cached || fetch(req).then(function (resp) {
          if (resp && resp.status === 200) {
            var copy = resp.clone();
            caches.open(CACHE).then(function (c) { c.put(req, copy); });
          }
          return resp;
        });
      })
    );
  }
});
