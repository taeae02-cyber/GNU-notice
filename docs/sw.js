/* GNU 공지 서비스 워커: 화면 파일은 캐시, 데이터는 항상 네트워크 우선 */
const SHELL = "gnu-shell-v2";
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

// ===== 푸시 알림 (서버가 보낸 메시지를 알림으로 표시) =====
self.addEventListener("push", e => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (_) { d = { body: e.data ? e.data.text() : "" }; }
  const title = d.title || "GNU 공지";
  const opts = {
    body: d.body || "",
    icon: "./icons/icon-192.png",
    badge: "./icons/icon-192.png",
    tag: d.tag || undefined,
    data: { url: d.url || "./" },
  };
  e.waitUntil(self.registration.showNotification(title, opts));
});
self.addEventListener("notificationclick", e => {
  e.notification.close();
  const target = new URL((e.notification.data && e.notification.data.url) || "./", self.location.href).href;
  e.waitUntil(clients.matchAll({ type: "window", includeUncontrolled: true }).then(list => {
    const base = target.split("#")[0];
    for (const c of list) {
      if (c.url.split("#")[0] === base && "focus" in c) {
        if ("navigate" in c) c.navigate(target).catch(() => {});
        return c.focus();
      }
    }
    return clients.openWindow(target);
  }));
});
// 브라우저가 구독 주소를 바꾸면 다음에 사이트를 열 때 다시 등록됨 (app.js의 pushSyncNow)
