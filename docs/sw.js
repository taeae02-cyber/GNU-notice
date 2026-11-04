/* GNU 공지 서비스 워커: 화면 파일은 캐시, 데이터는 항상 네트워크 우선 */
const SHELL = "gnu-shell-v1";
const SHELL_FILES = ["./", "./index.html", "./style.css", "./app.js", "./manifest.webmanifest", "./icons/icon-192.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(SHELL).then(c => c.addAll(SHELL_FILES)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== SHELL).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  if (url.pathname.includes("/data/")) {
    // 데이터: 네트워크 우선, 실패하면 캐시
    e.respondWith(fetch(e.request).then(r => { const copy = r.clone(); caches.open("gnu-data").then(c => c.put(e.request, copy)); return r; })
      .catch(() => caches.match(e.request)));
    return;
  }
  // 화면 파일: 네트워크 우선(업데이트 바로 반영), 실패하면 캐시
  e.respondWith(fetch(e.request).then(r => { const copy = r.clone(); caches.open(SHELL).then(c => c.put(e.request, copy)); return r; })
    .catch(() => caches.match(e.request)));
});
