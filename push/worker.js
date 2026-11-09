/*
 * GNU 공지 — 푸시 알림 서버 (Cloudflare Worker)
 *
 * 하는 일
 *   1. 사이트에서 "푸시 알림 받기"를 켠 사람의 구독 정보(브라우저가 준 주소)와 조건(키워드·학과)을 보관
 *   2. 푸시 서명용 키(VAPID)를 처음 한 번 만들어 보관
 *   3. GitHub 수집기가 1시간마다 /export 로 구독 목록을 가져가서, 조건에 맞는 새 공지를 푸시로 보냄
 *
 * 필요한 설정 (Cloudflare 대시보드 → 이 Worker → Settings)
 *   - Bindings → KV namespace: 변수 이름 SUBS
 *   - Variables and Secrets → Secret: 이름 TOKEN (GitHub 비밀값 PUSH_TOKEN 과 같은 값)
 */

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    const cors = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type,Authorization",
    };
    const json = (o, status = 200) => new Response(JSON.stringify(o), { status, headers: { ...cors, "Content-Type": "application/json; charset=utf-8" } });
    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });

    try {
      if (!env.SUBS) return json({ error: "KV 바인딩(SUBS)이 없어요. Settings → Bindings 에서 추가하세요." }, 500);

      // 사이트가 구독할 때 쓰는 공개키
      if (url.pathname === "/vapid") {
        const k = await getKeys(env);
        return json({ publicKey: k.publicKey });
      }

      // 구독 등록/갱신 (키워드·학과가 바뀔 때마다 사이트가 다시 보냄)
      if (url.pathname === "/subscribe" && req.method === "POST") {
        const b = await req.json();
        const sub = b && b.subscription;
        if (!sub || typeof sub.endpoint !== "string" || !sub.endpoint.startsWith("https://")) return json({ error: "bad subscription" }, 400);
        const id = await sha256(sub.endpoint);
        const rec = {
          subscription: { endpoint: sub.endpoint, keys: sub.keys || {}, expirationTime: sub.expirationTime || null },
          keywords: Array.isArray(b.keywords) ? b.keywords.slice(0, 30).map(k => String(k).slice(0, 30)) : [],
          dept: b.dept && typeof b.dept === "object" ? { name: str(b.dept.name), unit: str(b.dept.unit), college: str(b.dept.college), scope: str(b.dept.scope) } : null,
          deptNew: b.deptNew !== false,
          ua: str(b.ua),
          updated: Date.now(),
        };
        await env.SUBS.put("sub:" + id, JSON.stringify(rec));
        return json({ ok: true });
      }

      // 구독 해제
      if (url.pathname === "/unsubscribe" && req.method === "POST") {
        const b = await req.json();
        if (b && typeof b.endpoint === "string") await env.SUBS.delete("sub:" + await sha256(b.endpoint));
        return json({ ok: true });
      }

      // 수집기가 가져가는 전체 목록 (토큰 필요)
      if (url.pathname === "/export") {
        if (!authed(req, env)) return json({ error: "unauthorized" }, 401);
        const keys = await getKeys(env);
        const subs = [];
        let cursor = undefined;
        do {
          const page = await env.SUBS.list({ prefix: "sub:", cursor });
          for (const k of page.keys) {
            const v = await env.SUBS.get(k.name);
            if (v) subs.push(JSON.parse(v));
          }
          cursor = page.list_complete ? undefined : page.cursor;
        } while (cursor);
        return json({ publicKey: keys.publicKey, privateKey: keys.privateKey, subs });
      }

      // 수집기가 "죽은 구독"(브라우저가 알림을 끈 경우 등)을 지워 달라고 보냄 (토큰 필요)
      if (url.pathname === "/remove" && req.method === "POST") {
        if (!authed(req, env)) return json({ error: "unauthorized" }, 401);
        const b = await req.json();
        let n = 0;
        for (const ep of Array.isArray(b.endpoints) ? b.endpoints : []) {
          if (typeof ep === "string") { await env.SUBS.delete("sub:" + await sha256(ep)); n++; }
        }
        return json({ ok: true, removed: n });
      }

      // 상태 확인 (브라우저로 열어보면 이게 보임)
      if (url.pathname === "/" || url.pathname === "/health") {
        const page = await env.SUBS.list({ prefix: "sub:", limit: 1000 });
        return json({ ok: true, service: "GNU 공지 푸시 서버", subscribers: page.keys.length + (page.list_complete ? "" : "+"), token: env.TOKEN ? "설정됨" : "없음 (Settings → Variables and Secrets 에 TOKEN 추가 필요)" });
      }
      return json({ error: "not found" }, 404);
    } catch (e) {
      return json({ error: String(e && e.message || e) }, 500);
    }
  },
};

function str(v) { return v == null ? null : String(v).slice(0, 100); }

function authed(req, env) {
  const h = req.headers.get("Authorization") || "";
  return !!env.TOKEN && h === "Bearer " + env.TOKEN;
}

async function sha256(text) {
  const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(d)].map(b => b.toString(16).padStart(2, "0")).join("");
}

function b64url(bytes) {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

// VAPID 키: 처음 요청 때 한 번 만들어 KV에 보관 (공개키는 사이트가, 비밀키는 수집기가 씀)
async function getKeys(env) {
  const saved = await env.SUBS.get("vapid");
  if (saved) return JSON.parse(saved);
  const kp = await crypto.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, true, ["sign", "verify"]);
  const pub = new Uint8Array(await crypto.subtle.exportKey("raw", kp.publicKey));   // 65바이트 (0x04 + X + Y)
  const jwk = await crypto.subtle.exportKey("jwk", kp.privateKey);                   // d = 비밀 스칼라 (base64url)
  const keys = { publicKey: b64url(pub), privateKey: jwk.d, created: new Date().toISOString() };
  await env.SUBS.put("vapid", JSON.stringify(keys));
  return keys;
}
