/* GNU 공지 — 사이트 동작 (프레임워크 없이 순수 JS) */
(function () {
  "use strict";

  // ===== 설정 (저장소 만든 뒤 채우기) =====
  const CONFIG = {
    reportIssueUrl: "https://github.com/taeae02-cyber/GNU-notice/issues/new",
    reportMail: "",
  };

  const CATEGORIES = ["수강·학사", "장학·등록금", "취업·창업", "국제·교환", "생활·시설", "행사·특강", "외부기관"];
  const CAMPUSES = ["가좌", "칠암", "통영", "내동", "창원", "공통"];
  const PAGE = 60;
  const $ = (s, el) => (el || document).querySelector(s);
  const $$ = (s, el) => Array.from((el || document).querySelectorAll(s));

  // ===== 상태 =====
  const state = {
    notices: [], schedule: [], departments: [], meta: {}, search: null,
    tab: "전체", q: "", sort: "new", hideExpired: false, bodySearch: false, limit: PAGE,
    campuses: new Set(CAMPUSES),
    myDept: load("myDept", null),
    scopeOn: Object.assign({ all: true, college: true, dept: true, others: false }, load("scopeOn", {})),
    keywords: load("keywords", []),
    notify: load("notify", false),
    read: new Set(load("read", [])),
    marks: new Set(load("marks", [])),
    lastVisit: load("lastVisit", null),
    reports: load("reports", []),
    onboarded: load("onboarded", false),
    theme: load("theme", "system"),
    showGrad: load("showGrad", false),
    calMonth: null, calSel: null, calAllDl: load("calAllDl", false), feeds: null,
  };
  const today = startOfDay(new Date());
  let deferredInstall = null;

  function load(k, d) { try { const v = localStorage.getItem("gnu." + k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } }
  function save(k, v) { try { localStorage.setItem("gnu." + k, JSON.stringify(v)); } catch (e) { /* 저장 못 해도 동작 */ } }
  function startOfDay(d) { return new Date(d.getFullYear(), d.getMonth(), d.getDate()); }
  function parseDate(s) { if (!s) return null; const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); }
  function daysUntil(s) { const d = parseDate(s); if (!d) return null; return Math.round((d - today) / 86400000); }
  function fmtDate(s, withYear) { const d = parseDate(s); if (!d) return ""; const md = `${d.getMonth() + 1}.${String(d.getDate()).padStart(2, "0")}`; return withYear ? `${d.getFullYear()}.${md}` : md; }
  function ymd(s) { return (s || "").replace(/-/g, ""); }
  function addDays(s, n) { const d = parseDate(s); d.setDate(d.getDate() + n); return `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, "0")}${String(d.getDate()).padStart(2, "0")}`; }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
  function linkify(text) { return esc(text).replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>'); }
  function ddInfo(deadline) {
    const n = daysUntil(deadline);
    if (n === null) return { cls: "none", label: "", n: null };
    if (n < 0) return { cls: "past", label: "마감", n };
    if (n === 0) return { cls: "red", label: "D-day", n };
    if (n <= 3) return { cls: "red", label: "D-" + n, n };
    if (n <= 7) return { cls: "amber", label: "D-" + n, n };
    return { cls: "", label: "D-" + n, n };
  }
  function matchKeywords(n) {
    if (!state.keywords.length) return [];
    const hay = (n.title + " " + (n.dept || "") + " " + (n.unit || "")).toLowerCase();
    return state.keywords.filter(k => hay.includes(k.toLowerCase()));
  }
  function isNew(n) {
    if (!state.lastVisit || !n.first_seen) return false;
    const a = new Date(n.first_seen), b = new Date(state.lastVisit);
    return !isNaN(a) && !isNaN(b) && a > b;
  }
  function myUnit() {
    if (!state.myDept) return null;
    const u = state.departments.find(d => d.name === state.myDept);
    return { name: state.myDept, unit: u && u.unit ? u.unit : state.myDept, college: u ? u.college : null, scope: u ? u.scope : "학과" };
  }

  // 초성 검색
  const CHO = ["ㄱ", "ㄲ", "ㄴ", "ㄷ", "ㄸ", "ㄹ", "ㅁ", "ㅂ", "ㅃ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅉ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"];
  function chosung(str) {
    let out = "";
    for (const ch of str) {
      const c = ch.charCodeAt(0);
      if (c >= 0xac00 && c <= 0xd7a3) out += CHO[Math.floor((c - 0xac00) / 588)];
      else out += ch;
    }
    return out;
  }
  function isChosungQuery(q) { return /^[ㄱ-ㅎ]+$/.test(q); }

  // ===== 테마 =====
  function applyTheme() {
    const dark = state.theme === "dark" || (state.theme === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.dataset.theme = dark ? "dark" : "";
    $("#btn-theme").title = "테마: " + ({ system: "시스템 설정", light: "밝게", dark: "어둡게" })[state.theme];
  }

  // ===== 데이터 로드 =====
  async function loadData() {
    const bust = "?v=" + Math.floor(Date.now() / 300000);
    const [nz, sc, dp, mt] = await Promise.all([
      fetch("data/notices.json" + bust).then(r => r.json()).catch(() => ({ notices: [] })),
      fetch("data/schedule.json" + bust).then(r => r.json()).catch(() => ({ items: [] })),
      fetch("data/departments.json" + bust).then(r => r.json()).catch(() => ({ units: [] })),
      fetch("data/meta.json" + bust).then(r => r.json()).catch(() => ({})),
    ]);
    state.notices = nz.notices || [];
    state.schedule = sc.items || [];
    state.departments = dp.units || [];
    state.meta = mt || {};
  }
  async function loadSearchIndex() {
    if (state.search) return;
    try { state.search = await fetch("data/search.json?v=" + Math.floor(Date.now() / 300000)).then(r => r.json()); }
    catch (e) { state.search = {}; }
  }

  // ===== 탭 =====
  function renderTabs() {
    const counts = {};
    for (const n of filtered({ ignoreTab: true })) counts[n.category] = (counts[n.category] || 0) + 1;
    const kwCount = state.notices.filter(n => matchKeywords(n).length).length;
    const tabs = ["전체", ...CATEGORIES];
    $("#tabs").innerHTML = tabs.map(t => {
      const c = t === "전체" ? Object.values(counts).reduce((a, b) => a + b, 0) : (counts[t] || 0);
      return `<button data-tab="${esc(t)}" class="${state.tab === t ? "on" : ""}">${esc(t)}<span class="cnt">${c}</span></button>`;
    }).join("") +
      `<span class="spacer"></span>` +
      `<button data-tab="북마크" class="${state.tab === "북마크" ? "on" : ""}">★ 북마크<span class="cnt">${state.marks.size}</span></button>` +
      `<button data-tab="내 달력" class="${state.tab === "내 달력" ? "on" : ""}">📅 내 달력</button>` +
      `<button data-tab="내 키워드" class="${state.tab === "내 키워드" ? "on" : ""}">내 키워드<span class="cnt">${kwCount}</span></button>` +
      `<button data-tab="학사일정" class="${state.tab === "학사일정" ? "on" : ""}">학사일정</button>`;
  }

  // ===== 툴바 =====
  function renderToolbar() {
    const me = myUnit();
    const chips = $("#scope-chips");
    const chip = (key, label, extra) => `<button class="chip ${state.scopeOn[key] ? "on" : ""}" data-scope="${key}"><span class="ck"></span>${esc(label)}${extra || ""}</button>`;
    if (me) {
      $("#dept-input").placeholder = "다른 학과로 바꾸기";
      chips.innerHTML = chip("all", "전체 공지") + (me.college ? chip("college", me.college) : "") +
        chip("dept", me.name, '<span class="x" data-clear-dept title="학과 해제">✕</span>') + chip("others", "다른 학과·단과대");
    } else {
      $("#dept-input").placeholder = "내 학과 검색 — 예: 전기, 간호, 컴퓨터";
      chips.innerHTML = chip("all", "전체 공지") + chip("college", "단과대 공지") + chip("dept", "학과 공지");
    }
    $("#campus-chips").innerHTML = '<span class="lbl">캠퍼스</span>' + CAMPUSES.map(c =>
      `<button class="chip ${state.campuses.has(c) ? "on" : ""}" data-campus="${c}"><span class="ck"></span>${c}</button>`).join("");
    $("#sort").value = state.sort;
    $("#hide-expired").checked = state.hideExpired;
    $("#body-search").checked = state.bodySearch;
    $("#onboard").hidden = !!(state.myDept || state.onboarded || !state.departments.length);
    const g = state.meta.generated_at;
    $("#updated").textContent = g ? "마지막 갱신 " + g.replace("T", " ").slice(0, 16) : "";
    $("#sample-banner").hidden = !state.meta.sample;
    renderStatusBanner();
    const newKw = state.notices.filter(n => matchKeywords(n).length && isNew(n)).length;
    const b = $("#kw-badge");
    b.hidden = newKw === 0; b.textContent = newKw;
  }

  // ===== 수집 상태 =====
  function boardStatus() {
    const boards = Object.values(state.meta.boards || {});
    const bad = boards.filter(b => !b.ok);
    return { total: boards.length, bad, ok: boards.length - bad.length };
  }
  function renderStatusBanner() {
    const st = boardStatus();
    const el = $("#status-banner");
    if (!st.total || st.bad.length === 0 || st.bad.length / st.total < 0.3) { el.hidden = true; return; }
    el.hidden = false;
    el.innerHTML = `마지막 수집 때 게시판 ${st.bad.length}곳을 못 가져왔어요 (학교 서버 상태일 수 있어요). <a href="#" id="link-status-2">자세히</a>`;
  }
  function openStatus() {
    const st = boardStatus();
    const boards = Object.entries(state.meta.boards || {});
    const g = state.meta.generated_at ? state.meta.generated_at.replace("T", " ").slice(0, 16) : "-";
    $("#status-body").innerHTML = `
      <p class="hint">마지막 수집 ${g} · 저장된 공지 ${(state.meta.count || 0).toLocaleString()}건</p>
      <div class="status-sum"><span><b>${st.ok}</b>정상</span><span class="${st.bad.length ? "bad" : ""}"><b>${st.bad.length}</b>실패</span><span><b>${st.total}</b>게시판</span></div>
      <div class="status-list">${boards.sort((a, b) => (a[1].ok === b[1].ok) ? 0 : (a[1].ok ? 1 : -1)).map(([id, b]) =>
        `<div><span>${esc(b.name)}</span><span class="${b.ok ? "ok" : "bad"}">${b.ok ? `정상 · ${b.listed || 0}건` : esc(b.error || "실패")}</span></div>`).join("") || '<div class="ok">아직 수집 기록이 없어요.</div>'}</div>`;
    $("#status-panel").hidden = false;
  }

  // ===== 학과 자동완성 =====
  let suggestIndex = -1;
  function deptMatches(q) {
    q = q.trim().toLowerCase();
    if (!q) return [];
    const cho = isChosungQuery(q);
    const starts = [], contains = [];
    for (const d of state.departments) {
      const name = d.name.toLowerCase();
      const key = cho ? chosung(name) : name;
      if (key.startsWith(q)) starts.push(d);
      else if (key.includes(q) || (!cho && (d.college || "").toLowerCase().includes(q))) contains.push(d);
    }
    return starts.concat(contains).slice(0, 8);
  }
  function renderSuggest(q) {
    const ul = $("#dept-suggest");
    const items = deptMatches(q);
    suggestIndex = -1;
    if (!q.trim()) { ul.hidden = true; return; }
    if (!items.length) { ul.innerHTML = '<li class="none">연결된 학과 중에 없어요. 다른 이름으로 검색해 보세요.</li>'; ul.hidden = false; return; }
    const cho = isChosungQuery(q.trim());
    const re = cho ? null : new RegExp(q.trim().replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "i");
    ul.innerHTML = items.map((d, i) => {
      const name = re ? esc(d.name).replace(re, m => `<mark>${m}</mark>`) : esc(d.name);
      const sub = d.scope === "단과대" ? "단과대" : (d.college || "학과");
      return `<li data-name="${esc(d.name)}" data-i="${i}"><b>${name}</b><small>${esc(sub)}</small></li>`;
    }).join("");
    ul.hidden = false;
  }
  function moveSuggest(dir) {
    const lis = $$("#dept-suggest li[data-name]");
    if (!lis.length) return;
    suggestIndex = (suggestIndex + dir + lis.length) % lis.length;
    lis.forEach((li, i) => li.classList.toggle("active", i === suggestIndex));
    lis[suggestIndex].scrollIntoView({ block: "nearest" });
  }
  function pickDept(name) {
    state.myDept = name; save("myDept", name);
    state.onboarded = true; save("onboarded", true);
    state.scopeOn = { all: true, college: true, dept: true, others: false }; save("scopeOn", state.scopeOn);
    $("#dept-input").value = ""; $("#dept-suggest").hidden = true;
    refresh();
  }

  // ===== 필터링 =====
  function filtered(opt) {
    opt = opt || {};
    const q = state.q.trim().toLowerCase();
    const cho = q && isChosungQuery(q);
    const me = myUnit();
    return state.notices.filter(n => {
      if (!opt.ignoreTab) {
        if (state.tab === "내 키워드") { if (!matchKeywords(n).length) return false; }
        else if (state.tab === "북마크") { if (!state.marks.has(n.id)) return false; }
        else if (state.tab !== "전체" && n.category !== state.tab) return false;
      }
      if (state.tab !== "북마크") {
        if (n.scope === "전체") { if (!state.scopeOn.all) return false; }
        else if (me) {
          const mine = (n.scope === "학과" && n.unit === me.unit) || (me.scope === "단과대" && n.scope === "단과대" && n.unit === me.unit);
          const myCollege = n.scope === "단과대" && me.college && n.unit === me.college;
          if (mine) { if (!state.scopeOn.dept) return false; }
          else if (myCollege) { if (!state.scopeOn.college) return false; }
          else if (!state.scopeOn.others) return false;
        } else {
          if (n.scope === "단과대" && !state.scopeOn.college) return false;
          if (n.scope === "학과" && !state.scopeOn.dept) return false;
        }
        if (!(n.campus || ["공통"]).some(c => state.campuses.has(c))) return false;
        if (state.hideExpired && n.deadline && daysUntil(n.deadline) < 0) return false;
      }
      if (q) {
        const hay = (n.title + " " + (n.dept || "") + " " + (n.category || "") + " " + (n.unit || "")).toLowerCase();
        let hit = cho ? chosung(hay).includes(q) : hay.includes(q);
        if (!hit && state.bodySearch && state.search && state.search[n.id]) {
          const body = state.search[n.id].toLowerCase();
          hit = cho ? chosung(body).includes(q) : body.includes(q);
        }
        if (!hit) return false;
      }
      return true;
    });
  }

  // 같은 공지(제목이 같고 날짜가 3주 이내)가 여러 게시판에 올라온 경우 하나로 묶음
  function grouped(list) {
    const rank = n => (n.scope === "전체" ? 0 : n.scope === "단과대" ? 1 : 2);
    const byKey = new Map();
    for (const n of list) {
      const k = n.dup_key || n.title;
      if (!byKey.has(k)) byKey.set(k, []);
      byKey.get(k).push(n);
    }
    const out = [];
    for (const arr of byKey.values()) {
      if (arr.length === 1) { out.push(Object.assign({}, arr[0], { dups: [] })); continue; }
      arr.sort((a, b) => (a.date || "").localeCompare(b.date || ""));
      let cluster = [arr[0]];
      const flush = () => {
        cluster.sort((a, b) => rank(a) - rank(b) || (a.date || "").localeCompare(b.date || "") || (b.views || 0) - (a.views || 0));
        const head = Object.assign({}, cluster[0], { dups: cluster.slice(1) });
        out.push(head);
      };
      for (let i = 1; i < arr.length; i++) {
        const prev = parseDate(cluster[cluster.length - 1].date), cur = parseDate(arr[i].date);
        if (prev && cur && (cur - prev) / 86400000 <= 21) cluster.push(arr[i]);
        else { flush(); cluster = [arr[i]]; }
      }
      flush();
    }
    return out;
  }

  function sorted(list) {
    if (state.sort === "dday") {
      return list.slice().sort((a, b) => {
        const da = a.deadline ? daysUntil(a.deadline) : null, db = b.deadline ? daysUntil(b.deadline) : null;
        const ra = da === null ? 2 : (da < 0 ? 1 : 0), rb = db === null ? 2 : (db < 0 ? 1 : 0);
        if (ra !== rb) return ra - rb;
        if (ra === 0) return da - db;
        return (b.date || "").localeCompare(a.date || "");
      });
    }
    if (state.sort === "views") return list.slice().sort((a, b) => (b.views || 0) - (a.views || 0) || (b.date || "").localeCompare(a.date || ""));
    return list.slice().sort((a, b) => (b.date || "").localeCompare(a.date || "") || (b.first_seen || "").localeCompare(a.first_seen || ""));
  }

  function groupLabel(n) {
    if (state.sort === "dday") {
      const d = n.deadline ? daysUntil(n.deadline) : null;
      if (d === null) return "마감일 없음";
      if (d < 0) return "지난 마감";
      if (d <= 3) return "3일 이내 마감";
      if (d <= 7) return "일주일 이내 마감";
      if (d <= 30) return "한 달 이내 마감";
      return "그 이후";
    }
    if (state.sort === "views") return "";
    const d = daysUntil(n.date);
    if (d === null) return "날짜 없음";
    if (d === 0) return "오늘";
    if (d === -1) return "어제";
    if (d >= -6) return "이번 주";
    if (d >= -13) return "지난주";
    if (d >= -30) return "이번 달";
    return "그 이전";
  }

  // ===== 목록 =====
  function keywordSchedHtml() {
    if (state.tab !== "내 키워드" || !state.keywords.length) return "";
    const hits = schedVisible().filter(s => daysUntil(s.end) >= 0 && state.keywords.some(k => s.title.toLowerCase().includes(k.toLowerCase())));
    if (!hits.length) return "";
    return `<li class="group-head">키워드에 걸린 학사일정</li>` + hits.slice(0, 6).map(s => {
      const n = daysUntil(s.start);
      const dd = n <= 0 ? { cls: "red", label: "진행중" } : ddInfo(s.start);
      const range = s.start === s.end ? fmtDate(s.start) : `${fmtDate(s.start)} ~ ${fmtDate(s.end)}`;
      return `<li class="row sched-like"><span class="dd ${dd.cls}">${dd.label}</span><div class="row-main"><div class="title">${esc(s.title)}</div><div class="meta"><span class="cat">학사일정</span>·<span>${range}</span></div></div><a class="cal-btn" href="${gcalUrl(s.title, s.start, s.end, "경상국립대 학사일정")}" target="_blank" rel="noopener">캘린더 추가</a></li>`;
    }).join("");
  }
  function renderList() {
    const all = sorted(grouped(filtered()));
    const me = myUnit();
    const scopeText = state.tab === "북마크" ? "내 북마크" : (me ? `${me.name} 기준` : "전체 학과");
    const sortText = { new: "최신순", dday: "마감 임박순", views: "많이 본 순" }[state.sort];
    $("#list-head").innerHTML = `<span>${all.length}건 · ${esc(scopeText)}</span><span>${state.tab === "내 키워드" ? "키워드: " + esc(state.keywords.join(", ") || "없음") : sortText}</span>`;
    const shown = all.slice(0, state.limit);
    let lastGroup = null, html = "";
    for (const n of shown) {
      const g = groupLabel(n);
      if (g && g !== lastGroup) { html += `<li class="group-head">${esc(g)}</li>`; lastGroup = g; }
      html += rowHtml(n);
    }
    const schedHtml = keywordSchedHtml();
    $("#list").innerHTML = schedHtml + html;
    const empty = $("#empty");
    empty.hidden = all.length > 0 || !!schedHtml;
    if (!all.length) {
      empty.innerHTML = state.tab === "북마크" ? "아직 북마크한 공지가 없어요.<br>목록에서 ★ 를 누르면 여기에 모여요."
        : state.tab === "내 키워드" ? "키워드에 맞는 공지가 없어요.<br>오른쪽 위 '내 키워드'에서 단어를 등록해 보세요."
        : state.q ? `"${esc(state.q)}" 에 맞는 공지가 없어요.${state.bodySearch ? "" : "<br>검색창 옆 '본문'을 켜면 내용까지 찾아요."}`
        : "조건에 맞는 공지가 없어요.<br>위 칩에서 범위를 넓혀 보세요.";
    }
    $("#more-wrap").hidden = all.length <= state.limit;
    if (all.length > state.limit) $("#more").textContent = `더 보기 (${all.length - state.limit}건 남음)`;
    renderSchedStrip();
  }
  function rowHtml(n) {
    const dd = ddInfo(n.deadline);
    const kws = matchKeywords(n);
    const scope = n.scope === "전체" ? "" : `<span class="scope-dept">${esc(n.unit || n.scope)}</span>`;
    const flags = (n.flags || []).map(f => `<span class="flag ${f === "중요" ? "imp" : "chg"}">${f}</span>`).join("");
    const dup = n.dups && n.dups.length ? `·<span class="dup" title="${esc(n.dups.map(d => d.unit || d.board).join(", "))}">+${n.dups.length} 게시판</span>` : "";
    return `<li class="row ${state.read.has(n.id) ? "read" : ""}" data-id="${esc(n.id)}">
      <span class="dd ${dd.cls}" title="${esc(n.deadline_text || "")}">${dd.label}</span>
      <div class="row-main">
        <div class="title">${isNew(n) ? '<span class="new" title="새 글"></span>' : ""}${flags}${esc(n.title)}${kws.length ? `<span class="kw">${esc(kws[0])}</span>` : ""}</div>
        <div class="meta"><span class="cat">${esc(n.category)}</span>·<span>${esc(n.dept || n.board)}</span>${scope ? "·" + scope : ""}·<span>${fmtDate(n.date)}</span>${n.views != null ? `·<span>조회 ${n.views.toLocaleString()}</span>` : ""}${n.has_attachments ? '·<span class="clip"></span>' : ""}${dup}</div>
      </div>
      <button class="star ${state.marks.has(n.id) ? "on" : ""}" data-mark="${esc(n.id)}" title="북마크" aria-label="북마크">${state.marks.has(n.id) ? "★" : "☆"}</button>
      <svg class="ico arrow" viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6"/></svg></li>`;
  }

  function renderSchedStrip() {
    const strip = $("#sched-strip");
    const show = (state.tab === "전체" || state.tab === "수강·학사") && !state.q;
    if (!show || !state.schedule.length) { strip.hidden = true; return; }
    const upcoming = schedVisible().filter(s => daysUntil(s.end) >= 0).sort((a, b) => a.start.localeCompare(b.start)).slice(0, 4);
    if (!upcoming.length) { strip.hidden = true; return; }
    strip.hidden = false;
    strip.innerHTML = `<div class="sh"><span>다가오는 학사일정</span><a href="#/tab/학사일정">전체 보기 →</a></div>
      <div class="sched-items">${upcoming.map(s => {
        const n = daysUntil(s.start);
        const dd = n <= 0 ? { cls: "red", label: "진행중" } : ddInfo(s.start);
        const range = s.start === s.end ? fmtDate(s.start) : `${fmtDate(s.start)} ~ ${fmtDate(s.end)}`;
        return `<div class="sched-item"><span class="dd ${dd.cls}">${dd.label}</span><div><div class="st">${esc(s.title)}</div><div class="sd">${range}</div></div></div>`;
      }).join("")}</div>`;
  }

  // ===== 학사일정 =====
  function schedVisible() {
    return state.schedule.filter(s => state.showGrad || s.target !== "대학원");
  }
  function renderSchedule() {
    const el = $("#view-schedule");
    if (!state.schedule.length) { el.innerHTML = '<p class="empty">학사일정 데이터가 아직 없어요.</p>'; return; }
    const hasGrad = state.schedule.some(s => s.target === "대학원");
    const byMonth = {};
    for (const s of schedVisible()) { const k = s.start.slice(0, 7); (byMonth[k] = byMonth[k] || []).push(s); }
    const months = Object.keys(byMonth).sort();
    const cur = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}`;
    el.innerHTML = `<div class="sched-opts"><button class="btn" id="sched-sub">📡 캘린더 앱에 구독</button>${hasGrad ? `<label class="switch" style="margin-left:12px"><input type="checkbox" id="show-grad" ${state.showGrad ? "checked" : ""}><span>대학원 일정도 보기</span></label>` : ""}</div>` + months.map(m => {
      const [y, mo] = m.split("-");
      return `<section class="sched-month" ${m < cur ? 'data-past="1"' : ""}><h3>${y}년 ${Number(mo)}월</h3>${byMonth[m].map((s, i) => {
        const ds = daysUntil(s.start), de = daysUntil(s.end);
        const cls = de < 0 ? "past" : (ds <= 0 ? "today" : "");
        const range = s.start === s.end ? fmtDate(s.start) : `${fmtDate(s.start)} ~ ${fmtDate(s.end)}`;
        const dd = de < 0 ? "" : (ds <= 0 ? '<span class="dd red">진행중</span>' : `<span class="dd ${ddInfo(s.start).cls}">${ddInfo(s.start).label}</span>`);
        const kw = state.keywords.find(k => s.title.toLowerCase().includes(k.toLowerCase()));
        return `<div class="sched-row ${cls}"><span class="sd">${range}</span><span>${esc(s.title)}${s.target === "대학원" ? ' <span class="tag">대학원</span>' : ""}${kw ? ` <span class="kw">${esc(kw)}</span>` : ""}</span>${dd}<a class="cal-btn" href="${gcalUrl(s.title, s.start, s.end, "경상국립대 학사일정")}" target="_blank" rel="noopener">캘린더 추가</a></div>`;
      }).join("")}</section>`;
    }).join("");
    const sg = $("#show-grad");
    if (sg) sg.addEventListener("change", e => { state.showGrad = e.target.checked; save("showGrad", state.showGrad); renderSchedule(); });
    const sb = $("#sched-sub");
    if (sb) sb.addEventListener("click", openSubscribe);
    const curEl = $(`.sched-month:not([data-past])`, el);
    if (curEl) setTimeout(() => curEl.scrollIntoView({ block: "start", behavior: "instant" }), 0);
  }

  // ===== 내 달력 =====
  function calEvents() {
    const ev = [];
    for (const s of schedVisible()) ev.push({ kind: "sch", start: s.start, end: s.end, title: s.title, href: "#/tab/학사일정" });
    const me = myUnit();
    const seen = new Set();
    for (const n of state.notices) {
      if (!n.deadline) continue;
      const marked = state.marks.has(n.id);
      if (!marked && !state.calAllDl) continue;
      if (!marked && state.calAllDl) {
        // 내 범위(전체 + 내 단과대 + 내 학과)의 마감만
        if (!(n.scope === "전체" || (me && ((n.scope === "학과" && n.unit === me.unit) || (n.scope === "단과대" && (n.unit === me.college || n.unit === me.unit)))))) continue;
        const k = (n.dup_key || n.title) + n.deadline;
        if (seen.has(k)) continue;
        seen.add(k);
      }
      ev.push({ kind: marked ? "mark" : "dl", start: n.deadline, end: n.deadline, title: n.title, href: "#/n/" + encodeURIComponent(n.id), scope: n.scope, unit: n.unit });
    }
    return ev;
  }
  function renderCalendar() {
    const el = $("#view-calendar");
    if (!state.calMonth) state.calMonth = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}`;
    const [Y, M] = state.calMonth.split("-").map(Number);
    const first = new Date(Y, M - 1, 1);
    const startDow = first.getDay();
    const daysIn = new Date(Y, M, 0).getDate();
    const events = calEvents();
    const byDay = {};
    for (const e of events) {
      let d = parseDate(e.start); const end = parseDate(e.end);
      let i = 0;
      while (d <= end && i < 120) {
        const k = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
        (byDay[k] = byDay[k] || []).push(Object.assign({ cont: i > 0 }, e));
        d = new Date(d.getFullYear(), d.getMonth(), d.getDate() + 1); i++;
      }
    }
    const cells = [];
    const prevDays = new Date(Y, M - 1, 0).getDate();
    for (let i = 0; i < 42; i++) {
      const dayNum = i - startDow + 1;
      let y = Y, m = M, d = dayNum, out = false;
      if (dayNum < 1) { out = true; m = M - 1; d = prevDays + dayNum; if (m < 1) { m = 12; y--; } }
      else if (dayNum > daysIn) { out = true; m = M + 1; d = dayNum - daysIn; if (m > 12) { m = 1; y++; } }
      const key = `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
      const evs = byDay[key] || [];
      const isToday = key === `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
      cells.push(`<div class="cal-cell ${out ? "out" : ""} ${isToday ? "today" : ""} ${state.calSel === key ? "sel" : ""}" data-day="${key}">
        <span class="dn">${d}</span>
        ${evs.slice(0, 3).map(e => `<a class="cal-ev ${e.kind} ${e.cont ? "cont" : ""}" href="${e.href}" title="${esc(e.title)}">${esc(e.title)}</a>`).join("")}
        ${evs.length > 3 ? `<div class="cal-more">+${evs.length - 3}</div>` : ""}
        <div class="dots">${evs.slice(0, 6).map(e => `<i class="${e.kind}"></i>`).join("")}</div>
      </div>`);
      if (i >= 34 && dayNum >= daysIn && (i + 1) % 7 === 0) break;
    }
    const me = myUnit();
    el.innerHTML = `<div class="cal-head">
        <button class="btn" data-cal="-1">◀</button><h2>${Y}년 ${M}월</h2><button class="btn" data-cal="1">▶</button>
        <button class="btn" data-cal="0">오늘</button>
        <div class="legend"><span><i class="sch"></i>학사일정</span><span><i class="mark"></i>북마크한 일정</span>
          <label class="switch" title="${me ? `전체 공지 + ${me.college && me.college !== me.unit ? me.college + " + " : ""}${me.unit} 공지의 마감일을 모두 표시` : "전체 공지의 마감일을 모두 표시"}"><input type="checkbox" id="cal-all" ${state.calAllDl ? "checked" : ""}><span><i class="dl" style="display:inline-block;width:10px;height:10px;border-radius:3px;background:var(--accent);opacity:.55;margin-right:4px"></i>${me ? me.name + "의 일정" : "전체 공지 일정"}</span></label>
          <button class="btn" id="cal-sub">📡 캘린더 앱에 구독</button></div>
      </div>
      <div class="cal-grid">${["일", "월", "화", "수", "목", "금", "토"].map(d => `<div class="cal-dow">${d}</div>`).join("")}${cells.join("")}</div>
      <div id="cal-day"></div>`;
    renderCalDay();
  }
  function renderCalDay() {
    const box = $("#cal-day");
    if (!box) return;
    if (!state.calSel) { box.innerHTML = '<p class="hint" style="text-align:center;margin-top:10px">날짜를 누르면 그날 일정이 아래에 나와요. 공지에 ★를 누르면 그 공지의 마감일이 달력에 들어와요.</p>'; return; }
    const evs = calEvents().filter(e => e.start <= state.calSel && state.calSel <= e.end);
    const d = parseDate(state.calSel);
    box.innerHTML = `<div class="cal-day-list"><h3>${d.getMonth() + 1}월 ${d.getDate()}일 (${["일", "월", "화", "수", "목", "금", "토"][d.getDay()]})</h3>
      ${evs.length ? evs.map(e => `<a class="row sched-like" href="${e.href}" style="text-decoration:none;color:inherit"><span class="dd ${e.kind === "sch" ? "" : (ddInfo(e.end).cls)}">${e.kind === "sch" ? "학사" : ddInfo(e.end).label}</span><div class="row-main"><div class="title">${esc(e.title)}</div><div class="meta"><span class="cat">${e.kind === "sch" ? "학사일정" : (e.kind === "mark" ? "북마크한 공지" : (e.scope === "전체" || !e.unit ? "전체 공지" : esc(e.unit) + " 공지"))}</span>·<span>${e.start === e.end ? fmtDate(e.start) : fmtDate(e.start) + " ~ " + fmtDate(e.end)}</span></div></div></a>`).join("")
        : '<p class="empty">이 날은 일정이 없어요.</p>'}</div>`;
  }
  async function openSubscribe() {
    if (!state.feeds) {
      try { state.feeds = await fetch("calendar/index.json?v=" + Math.floor(Date.now() / 300000)).then(r => r.json()); }
      catch (e) { state.feeds = null; }
    }
    const list = $("#sub-list");
    if (!state.feeds) { list.innerHTML = '<p class="hint">구독 파일이 아직 없어요. 수집기를 한 번 실행하면 만들어져요.</p>'; $("#sub-panel").hidden = false; return; }
    const base = new URL(".", location.href).href;
    const me = myUnit();
    const items = [];
    if (me && state.feeds.units && state.feeds.units[me.name]) items.push({ name: `${me.name}의 일정 (학사일정 + 전체·단과대·${me.name} 공지 마감일)`, path: state.feeds.units[me.name] });
    items.push({ name: "학사일정만 (학부)", path: state.feeds.schedule });
    items.push({ name: "전체 공지 일정 (학사일정 + 전체 공지 마감일)", path: state.feeds.all });
    list.innerHTML = items.map(it => {
      const url = base + it.path;
      const webcal = url.replace(/^https?:/, "webcal:");
      return `<div class="sub-item"><b>${esc(it.name)}</b><button class="btn" data-copy="${esc(url)}">주소 복사</button><a class="btn" href="${esc(webcal)}">애플 캘린더로 열기</a></div>`;
    }).join("") + (location.protocol === "file:" || /localhost|127\.0\.0\.1/.test(location.host) ? '<p class="hint small">지금은 PC 미리보기라 주소가 내 컴퓨터용이에요. GitHub에 올린 뒤 그 주소에서 구독해야 캘린더 앱이 읽을 수 있어요.</p>' : "");
    $$("[data-copy]", list).forEach(b => b.addEventListener("click", () => { navigator.clipboard && navigator.clipboard.writeText(b.dataset.copy).then(() => { b.textContent = "복사됨 ✓"; setTimeout(() => b.textContent = "주소 복사", 1500); }).catch(() => {}); }));
    $("#sub-panel").hidden = false;
  }

  // ===== 캘린더 =====
  function gcalUrl(title, start, end, details, url) {
    const dates = `${ymd(start)}/${addDays(end || start, 1)}`;
    const p = new URLSearchParams({ action: "TEMPLATE", text: title, dates, details: (details || "") + (url ? "\n" + url : "") });
    return "https://calendar.google.com/calendar/render?" + p.toString();
  }
  function downloadIcs(title, start, end, details, url) {
    const uid = Math.random().toString(36).slice(2) + "@gnu-notice";
    const stamp = new Date().toISOString().replace(/[-:]/g, "").slice(0, 15) + "Z";
    const ics = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//GNU 공지//KO", "BEGIN:VEVENT", `UID:${uid}`, `DTSTAMP:${stamp}`,
      `DTSTART;VALUE=DATE:${ymd(start)}`, `DTEND;VALUE=DATE:${addDays(end || start, 1)}`,
      `SUMMARY:${title.replace(/[\n,;]/g, " ")}`, `DESCRIPTION:${((details || "") + (url ? " " + url : "")).replace(/[\n]/g, " ")}`,
      "END:VEVENT", "END:VCALENDAR"].join("\r\n");
    const blob = new Blob([ics], { type: "text/calendar" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = "gnu-notice.ics"; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  // ===== 상세 =====
  async function renderDetail(id) {
    const n = state.notices.find(x => x.id === id);
    const el = $("#view-detail");
    if (!n) { el.innerHTML = '<p class="empty">글을 찾을 수 없어요. <a href="#/">목록으로</a></p>'; return; }
    state.read.add(id); save("read", Array.from(state.read).slice(-2000));
    const dd = ddInfo(n.deadline);
    const campus = (n.campus || []).join("·");
    const scopeLabel = n.scope === "전체" ? "전체 공지" : `${n.unit || ""} 공지`;
    const marked = state.marks.has(id);
    // 같은 공지가 올라온 다른 게시판
    const sameKey = n.dup_key || n.title;
    const siblings = state.notices.filter(x => x.id !== id && (x.dup_key || x.title) === sameKey && x.date && n.date && Math.abs((parseDate(x.date) - parseDate(n.date)) / 86400000) <= 21);
    el.innerHTML = `<article class="detail">
      <div class="detail-bar">
        <a href="#/">← 목록으로</a>
        <div class="acts">
          <button class="btn" data-act="mark">${marked ? "★ 북마크됨" : "☆ 북마크"}</button>
          <button class="btn" data-act="keyword">🔔 키워드</button>
          <button class="btn" data-act="report">분류 신고</button>
          <a class="btn" href="${esc(n.url)}" target="_blank" rel="noopener">학교 홈페이지 ↗</a>
        </div>
      </div>
      <div class="detail-body">
        <div class="tags"><span class="tag cat">${esc(n.category)}</span><span class="tag">${esc(scopeLabel)}</span><span class="tag">${esc(campus)}</span><span class="tag">${esc(n.board)}</span>${(n.flags || []).map(f => `<span class="tag ${f === "중요" ? "cat" : ""}">${f}</span>`).join("")}</div>
        <h1>${esc(n.title)}</h1>
        <div class="dmeta"><span>${esc(n.dept || "")}</span><span id="d-contact"></span><span>등록 ${fmtDate(n.date, true)}</span>${n.views != null ? `<span>조회 ${n.views.toLocaleString()}</span>` : ""}</div>
      </div>
      ${n.deadline ? `<div class="ddbox ${dd.cls}"><b>${dd.label}</b><span>마감 ${fmtDate(n.deadline, true)}</span><span class="src">${n.deadline_source === "title" ? "제목에서 자동 추출" : "본문에서 자동 추출"}${n.deadline_text ? " · “" + esc(n.deadline_text) + "”" : ""}</span>
        <span class="cal"><a class="btn" href="${gcalUrl("[마감] " + n.title, n.deadline, n.deadline, n.dept || "", n.url)}" target="_blank" rel="noopener">구글 캘린더</a><button class="btn" data-act="ics">.ics 저장</button></span></div>` : ""}
      ${siblings.length ? `<div class="dup-list">같은 공지가 올라온 곳: ${siblings.map(s => `<a href="#/n/${encodeURIComponent(s.id)}">${esc(s.unit || s.board)}</a>`).join("")}</div>` : ""}
      <div class="content loading" id="d-body">본문 불러오는 중…</div>
      <div id="d-attach"></div>
    </article>`;
    try {
      const b = await fetch(`data/body/${encodeURIComponent(id)}.json`).then(r => { if (!r.ok) throw new Error(); return r.json(); });
      const body = $("#d-body");
      body.classList.remove("loading");
      const imgs = (b.images || []).map(i => `<figure class="bimg"><img src="${esc(i.src)}" alt="${esc(i.alt || "공지 이미지")}" loading="lazy"><figcaption>${i.alt ? esc(i.alt) + " · " : ""}<a href="${esc(i.src)}" target="_blank" rel="noopener">원본 크기로 보기</a></figcaption></figure>`).join("");
      const text = (b.body || "").replace(/^\[이미지\][^\n]*\n?/gm, "").trim();
      let html = "";
      if (imgs && !text) html += '<p class="hint" style="margin:0 0 10px">본문이 이미지로 올라온 공지예요.</p>';
      html += imgs;
      if (text) html += (imgs ? '<div class="btext">' : "") + linkify(text).replace(/\[이미지 글자 자동 인식 — 오타가 있을 수 있어요\]/, '<span class="ocr-label">이미지 글자 자동 인식 — 오타가 있을 수 있어요</span>') + (imgs ? "</div>" : "");
      if (!html) html = '<span class="hint">본문을 가져오지 못했어요. 학교 홈페이지에서 확인해 주세요.</span>';
      body.innerHTML = html;
      if (b.contact) $("#d-contact").textContent = b.contact;
      if (b.attachments && b.attachments.length) {
        $("#d-attach").innerHTML = `<div class="attach"><h4>첨부파일 ${b.attachments.length}</h4>${b.attachments.map(a => {
          const ext = (a.name.match(/\.([a-z0-9]{2,5})$/i) || [, "file"])[1].toUpperCase();
          return `<a href="${esc(a.url)}" target="_blank" rel="noopener"><span class="ext">${esc(ext)}</span>${esc(a.name)}</a>`;
        }).join("")}<p class="hint">클릭하면 학교 서버에서 바로 내려받아요.</p></div>`;
      }
    } catch (e) {
      const body = $("#d-body");
      body.classList.remove("loading");
      body.innerHTML = '<span class="hint">본문이 아직 수집되지 않았어요. 학교 홈페이지에서 확인해 주세요.</span>';
    }
    $$('[data-act]', el).forEach(btn => btn.addEventListener("click", () => {
      const act = btn.dataset.act;
      if (act === "keyword") openKeywords(suggestKeyword(n));
      if (act === "report") openReport(n);
      if (act === "ics") downloadIcs("[마감] " + n.title, n.deadline, n.deadline, n.dept || "", n.url);
      if (act === "mark") { toggleMark(id); btn.textContent = state.marks.has(id) ? "★ 북마크됨" : "☆ 북마크"; }
    }));
  }
  function toggleMark(id) {
    state.marks.has(id) ? state.marks.delete(id) : state.marks.add(id);
    save("marks", Array.from(state.marks));
  }
  function suggestKeyword(n) {
    if (n.unit) return n.unit;
    const words = ["장학", "교환학생", "수강", "생활관", "셔틀", "채용", "공모전", "특강", "등록금", "졸업", "계절학기"];
    return words.find(w => n.title.includes(w)) || "";
  }

  // ===== 키워드 =====
  function openKeywords(prefill) {
    renderKeywords();
    $("#kw-input").value = prefill || "";
    $("#kw-notify").checked = !!state.notify;
    $("#kw-panel").hidden = false;
    setTimeout(() => $("#kw-input").focus(), 0);
  }
  function renderKeywords() {
    $("#kw-list").innerHTML = state.keywords.length
      ? state.keywords.map(k => `<span class="chip kw-chip">${esc(k)}<button data-rm="${esc(k)}" title="삭제">✕</button></span>`).join("")
      : '<span class="hint">아직 등록한 키워드가 없어요.</span>';
  }
  function addKeyword() {
    const v = $("#kw-input").value.trim();
    if (!v) return;
    if (!state.keywords.includes(v)) { state.keywords.push(v); save("keywords", state.keywords); }
    $("#kw-input").value = "";
    renderKeywords(); refresh();
  }

  // ===== 분류 신고 =====
  let reportTarget = null;
  function openReport(n) {
    reportTarget = n;
    $("#report-title").textContent = `“${n.title}” — 지금은 [${n.category}]로 분류돼 있어요.`;
    $("#report-cat").innerHTML = CATEGORIES.concat(["기타"]).filter(c => c !== n.category).map(c => `<option>${esc(c)}</option>`).join("");
    $("#report-note").value = "";
    $("#report-done").hidden = true;
    $("#report-panel").hidden = false;
  }
  function sendReport() {
    if (!reportTarget) return;
    const rep = { id: reportTarget.id, title: reportTarget.title, from: reportTarget.category, to: $("#report-cat").value, note: $("#report-note").value.trim(), at: new Date().toISOString() };
    state.reports.push(rep); save("reports", state.reports.slice(-200));
    const text = `[분류 신고] ${rep.title}\n- 글 ID: ${rep.id}\n- 현재: ${rep.from} → 제안: ${rep.to}\n- 메모: ${rep.note || "(없음)"}\n- 원문: ${reportTarget.url}`;
    const done = $("#report-done");
    if (CONFIG.reportIssueUrl) {
      window.open(`${CONFIG.reportIssueUrl}?title=${encodeURIComponent("[분류] " + rep.title)}&body=${encodeURIComponent(text)}`, "_blank");
      done.textContent = "GitHub 이슈 작성 창을 열었어요. 등록하면 반영돼요.";
    } else if (CONFIG.reportMail) {
      location.href = `mailto:${CONFIG.reportMail}?subject=${encodeURIComponent("[분류 신고] " + rep.title)}&body=${encodeURIComponent(text)}`;
      done.textContent = "메일 앱을 열었어요.";
    } else {
      navigator.clipboard && navigator.clipboard.writeText(text).catch(() => {});
      done.textContent = "신고 내용을 복사했어요. (신고 서버는 다음 단계에서 연결돼요)";
    }
    done.hidden = false;
  }

  // ===== 브라우저 알림 =====
  function notifyNew() {
    if (!state.notify || !("Notification" in window) || Notification.permission !== "granted") return;
    const hits = state.notices.filter(n => matchKeywords(n).length && isNew(n));
    if (!hits.length) return;
    const t = hits.length === 1 ? hits[0].title : `${hits[0].title} 외 ${hits.length - 1}건`;
    try { new Notification("GNU 공지 — 키워드 새 글", { body: t }); } catch (e) { /* 무시 */ }
  }

  // ===== 라우팅 =====
  function refresh() { state.limit = PAGE; renderToolbar(); renderTabs(); renderList(); }
  function route() {
    const h = location.hash || "#/";
    const mDetail = h.match(/^#\/n\/(.+)$/);
    const mTab = h.match(/^#\/tab\/(.+)$/);
    $("#view-list").hidden = true; $("#view-detail").hidden = true; $("#view-schedule").hidden = true; $("#view-calendar").hidden = true;
    $("#toolbar").hidden = !!mDetail; $("#onboard").hidden = true;
    if (mDetail) {
      $("#view-detail").hidden = false;
      renderDetail(decodeURIComponent(mDetail[1]));
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }
    if (mTab) state.tab = decodeURIComponent(mTab[1]);
    state.limit = PAGE;
    renderToolbar(); renderTabs();
    if (state.tab === "학사일정") { $("#view-schedule").hidden = false; $("#toolbar").hidden = true; $("#onboard").hidden = true; renderSchedule(); }
    else if (state.tab === "내 달력") { $("#view-calendar").hidden = false; $("#toolbar").hidden = true; $("#onboard").hidden = true; renderCalendar(); }
    else { $("#view-list").hidden = false; renderList(); }
  }

  // ===== 이벤트 =====
  function bind() {
    $("#tabs").addEventListener("click", e => {
      const b = e.target.closest("button[data-tab]"); if (!b) return;
      state.tab = b.dataset.tab; location.hash = "#/tab/" + encodeURIComponent(state.tab);
    });
    $("#list").addEventListener("click", e => {
      const star = e.target.closest("[data-mark]");
      if (star) { e.stopPropagation(); toggleMark(star.dataset.mark); star.classList.toggle("on"); star.textContent = star.classList.contains("on") ? "★" : "☆"; renderTabs(); if (state.tab === "북마크") renderList(); return; }
      const li = e.target.closest("li[data-id]"); if (!li) return;
      location.hash = "#/n/" + encodeURIComponent(li.dataset.id);
    });
    $("#more").addEventListener("click", () => { state.limit += PAGE; renderList(); });
    let qt;
    $("#q").addEventListener("input", e => {
      clearTimeout(qt);
      qt = setTimeout(async () => {
        state.q = e.target.value; state.limit = PAGE;
        if (state.bodySearch) await loadSearchIndex();
        if (location.hash.startsWith("#/n/")) location.hash = "#/"; else { renderTabs(); renderList(); }
      }, 120);
    });
    $("#body-search").addEventListener("change", async e => {
      state.bodySearch = e.target.checked;
      if (state.bodySearch) await loadSearchIndex();
      renderTabs(); renderList();
    });
    $("#btn-theme").addEventListener("click", () => {
      state.theme = { system: "light", light: "dark", dark: "system" }[state.theme] || "system";
      save("theme", state.theme); applyTheme();
    });
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", applyTheme);
    $("#onboard-skip").addEventListener("click", () => { state.onboarded = true; save("onboarded", true); $("#onboard").hidden = true; });
    $("#tb-more").addEventListener("click", e => { const open = $("#toolbar").classList.toggle("open"); e.target.textContent = open ? "캠퍼스 · 정렬 옵션 ▴" : "캠퍼스 · 정렬 옵션 ▾"; e.target.setAttribute("aria-expanded", open); });

    const di = $("#dept-input");
    di.addEventListener("input", () => renderSuggest(di.value));
    di.addEventListener("focus", () => { if (di.value.trim()) renderSuggest(di.value); });
    di.addEventListener("keydown", e => {
      if (e.key === "ArrowDown") { e.preventDefault(); moveSuggest(1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); moveSuggest(-1); }
      else if (e.key === "Enter") {
        e.preventDefault();
        const lis = $$("#dept-suggest li[data-name]");
        const pick = suggestIndex >= 0 ? lis[suggestIndex] : lis[0];
        if (pick) pickDept(pick.dataset.name);
      } else if (e.key === "Escape") { $("#dept-suggest").hidden = true; }
    });
    $("#dept-suggest").addEventListener("mousedown", e => {
      const li = e.target.closest("li[data-name]"); if (!li) return;
      e.preventDefault(); pickDept(li.dataset.name);
    });
    document.addEventListener("click", e => { if (!e.target.closest(".dept-wrap")) $("#dept-suggest").hidden = true; });

    $("#scope-chips").addEventListener("click", e => {
      if (e.target.closest("[data-clear-dept]")) {
        e.stopPropagation();
        state.myDept = null; save("myDept", null);
        state.scopeOn = { all: true, college: true, dept: true, others: false }; save("scopeOn", state.scopeOn);
        refresh(); return;
      }
      const b = e.target.closest("[data-scope]"); if (!b) return;
      state.scopeOn[b.dataset.scope] = !state.scopeOn[b.dataset.scope]; save("scopeOn", state.scopeOn);
      refresh();
    });
    $("#campus-chips").addEventListener("click", e => {
      const b = e.target.closest("[data-campus]"); if (!b) return;
      const c = b.dataset.campus;
      state.campuses.has(c) ? state.campuses.delete(c) : state.campuses.add(c);
      refresh();
    });
    $("#sort").addEventListener("change", e => { state.sort = e.target.value; state.limit = PAGE; renderList(); });
    $("#hide-expired").addEventListener("change", e => { state.hideExpired = e.target.checked; refresh(); });

    $("#btn-keywords").addEventListener("click", () => openKeywords(""));
    $("#kw-add-btn").addEventListener("click", addKeyword);
    $("#kw-input").addEventListener("keydown", e => { if (e.key === "Enter") addKeyword(); });
    $("#kw-list").addEventListener("click", e => {
      const b = e.target.closest("[data-rm]"); if (!b) return;
      state.keywords = state.keywords.filter(k => k !== b.dataset.rm); save("keywords", state.keywords);
      renderKeywords(); refresh();
    });
    $("#kw-notify").addEventListener("change", async e => {
      if (e.target.checked && "Notification" in window && Notification.permission !== "granted") {
        const p = await Notification.requestPermission();
        if (p !== "granted") { e.target.checked = false; return; }
      }
      state.notify = e.target.checked; save("notify", state.notify);
    });
    $("#report-send").addEventListener("click", sendReport);
    $("#view-calendar").addEventListener("click", e => {
      const nav = e.target.closest("[data-cal]");
      if (nav) {
        const n = Number(nav.dataset.cal);
        if (n === 0) { state.calMonth = null; state.calSel = null; }
        else { const [y, m] = state.calMonth.split("-").map(Number); const d = new Date(y, m - 1 + n, 1); state.calMonth = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`; }
        renderCalendar(); return;
      }
      if (e.target.id === "cal-sub") { openSubscribe(); return; }
      if (e.target.closest("a.cal-ev")) return;  // 링크는 그대로 이동
      const cell = e.target.closest(".cal-cell");
      if (cell) { state.calSel = state.calSel === cell.dataset.day ? null : cell.dataset.day; renderCalendar(); }
    });
    $("#view-calendar").addEventListener("change", e => {
      if (e.target.id === "cal-all") { state.calAllDl = e.target.checked; save("calAllDl", state.calAllDl); renderCalendar(); }
    });
    $("#link-status").addEventListener("click", e => { e.preventDefault(); openStatus(); });
    document.addEventListener("click", e => { if (e.target.id === "link-status-2") { e.preventDefault(); openStatus(); } });
    $("#link-pwa").addEventListener("click", e => { e.preventDefault(); $("#pwa-install").hidden = !deferredInstall; $("#pwa-panel").hidden = false; });
    $("#pwa-install").addEventListener("click", async () => { if (!deferredInstall) return; deferredInstall.prompt(); await deferredInstall.userChoice; deferredInstall = null; $("#pwa-panel").hidden = true; });
    window.addEventListener("beforeinstallprompt", e => { e.preventDefault(); deferredInstall = e; });
    $$("[data-close]").forEach(b => b.addEventListener("click", () => { b.closest(".modal").hidden = true; }));
    $$(".modal").forEach(m => m.addEventListener("click", e => { if (e.target === m) m.hidden = true; }));
    document.addEventListener("keydown", e => { if (e.key === "Escape") $$(".modal").forEach(m => m.hidden = true); });
    window.addEventListener("hashchange", route);
  }

  // ===== 시작 =====
  (async function init() {
    applyTheme();
    bind();
    await loadData();
    route();
    notifyNew();
    if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
    const nowIso = new Date().toISOString();
    window.addEventListener("pagehide", () => save("lastVisit", nowIso));
    setTimeout(() => save("lastVisit", nowIso), 60000);
  })();
})();
