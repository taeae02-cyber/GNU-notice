# -*- coding: utf-8 -*-
"""학사일정 페이지 수집. 구조를 모르는 상태에서도 '날짜(범위) + 제목' 쌍을 최대한 찾아냄."""
import re
import logging
from datetime import date

from bs4 import BeautifulSoup

from . import config, fetch
from .parse import clean

log = logging.getLogger("gnu.schedule")

# 11.03 ~ 11.07 / 2026.11.03~2026.11.07 / 11.03(월) ~ 11.07(금) / 11월 3일 ~ 11월 7일
D = r"(?:(\d{4})\s*[.\-/년]\s*)?(\d{1,2})\s*[.\-/월]\s*(\d{1,2})\s*일?\.?\s*(?:\([^)]{1,3}\))?"
RANGE_RE = re.compile(D + r"\s*[~∼〜–\-]\s*" + D)
SINGLE_RE = re.compile(D)
YEAR_RE = re.compile(r"(20\d{2})\s*년")


def _mk(y, m, d, default_year):
    try:
        return date(int(y) if y else default_year, int(m), int(d))
    except (ValueError, TypeError):
        return None


def _extract(text, default_year):
    """텍스트 한 줄 → (start, end, title) 또는 None"""
    text = clean(text.replace("\n", " "))
    if len(text) > 160 or len(text) < 4:
        return None
    m = RANGE_RE.search(text)
    if m:
        y1, m1, d1, y2, m2, d2 = m.groups()
        s = _mk(y1, m1, d1, default_year)
        e = _mk(y2, m2, d2, (int(y1) if y1 else default_year))
        if s and e and e < s:
            e = _mk(y2, m2, d2, s.year + 1)
        title = (text[:m.start()] + " " + text[m.end():]).strip(" :-–~·|")
        if s and e and title:
            return s, e, clean(title)
        return None
    m = SINGLE_RE.search(text)
    if m:
        y, mo, d = m.groups()
        s = _mk(y, mo, d, default_year)
        title = (text[:m.start()] + " " + text[m.end():]).strip(" :-–~·|")
        if s and title and not re.fullmatch(r"[\d\s.()월일요]*", title):
            return s, s, clean(title)
    return None


def _year_param(soup):
    """연도 선택 select 가 있으면 (name, [연도들]) 반환."""
    for sel in soup.find_all("select"):
        vals = [o.get("value", "").strip() for o in sel.find_all("option")]
        years = [v for v in vals if re.fullmatch(r"20\d{2}", v)]
        if len(years) >= 2 and sel.get("name"):
            return sel.get("name"), years
    return None, []


MONTH_HEAD_RE = re.compile(r"^\s*20\d{2}\s*년\s*\d{1,2}\s*월\s*")
TARGET_RE = re.compile(r"^\s*\[(학부|대학원|전체|공통)\]\s*")


def parse_schedule(html, default_year, year_fixed=False):
    soup = BeautifulSoup(html, "html.parser")
    for el in soup.select("script, style, header, footer, nav, [class*='gnb'], [class*='lnb'], [id*='header'], [id*='footer']"):
        el.decompose()
    # 페이지에 표시된 연도 (요청한 연도가 확실하면 그걸 씀)
    m = YEAR_RE.search(soup.get_text(" "))
    year = default_year if year_fixed else (int(m.group(1)) if m else default_year)

    items, seen = [], set()
    # 작은 요소부터: li, tr, dd, p, div(짧은 것)
    for el in soup.find_all(["li", "tr", "dd", "p", "div", "span"]):
        txt = el.get_text(" ")
        if len(clean(txt)) > 160:
            continue
        # 날짜가 3개 이상 들어 있으면 여러 항목을 감싼 상자이므로 건너뜀 (안쪽 요소에서 잡힘)
        if len(SINGLE_RE.findall(txt)) > 2:
            continue
        got = _extract(txt, year)
        if not got:
            continue
        s, e, title = got
        title = MONTH_HEAD_RE.sub("", title)          # "2026년 01월 " 같은 월 머리글 제거
        target = None
        tm = TARGET_RE.match(title)
        if tm:
            target = tm.group(1)
            title = TARGET_RE.sub("", title)
        title = clean(title)
        if not title:
            continue
        key = (s.isoformat(), e.isoformat(), title, target)
        if key in seen:
            continue
        seen.add(key)
        item = {"start": s.isoformat(), "end": e.isoformat(), "title": title}
        if target:
            item["target"] = target
        items.append(item)
    return items


def _fetch_year_html(year, sch_type=""):
    """학사일정은 페이지에 바로 안 들어 있고, 폼을 POST 하면 JSON 문자열(HTML)이 돌아옴.
    sch_type: "" = 전체, "ND" = 학부 (학교 페이지의 구분 버튼과 같은 값)"""
    import json as _json
    data = {"schdulSeq": "", "schdulLevel": "Y", "fromDate": "", "toDate": "", "date": "", "weekNum": "",
            "chkNP": "", "srchDate": "", "schType": sch_type, "schColor": "", "menuId": "", "srchYear": str(year)}
    for mi in ("1127", "1084"):
        text, _ = fetch.post(f"{config.SITE}/main/ps/schdul/selectSchdulList.do?mi={mi}", data=data)
        if not text:
            continue
        html = text
        try:
            parsed = _json.loads(text)
            if isinstance(parsed, str):
                html = parsed
            elif isinstance(parsed, dict):
                html = next((v for v in parsed.values() if isinstance(v, str) and len(v) > 50), text)
        except ValueError:
            pass
        if isinstance(html, str) and len(html) > 50:
            return html
    return None


def crawl_schedule(debug_dir=None):
    """학사일정 수집 → 리스트. 올해 + 내년."""
    today = date.today()
    items = []
    for y in (today.year, today.year + 1):
        html = _fetch_year_html(y)
        if not html:
            log.warning("학사일정 %d년: 응답 없음", y)
            continue
        got = parse_schedule(html, y, year_fixed=True)
        log.info("학사일정 %d년: %d건", y, len(got))
        if debug_dir:
            (debug_dir / f"schedule_{y}.html").write_text(html, encoding="utf-8")
        for it in got:
            it.setdefault("target", "학부")
        items.extend(got)
    if not items:
        # 예전 방식(정적 페이지)도 한 번 시도
        html, _ = fetch.get(config.SCHEDULE_URL)
        if html:
            if debug_dir:
                (debug_dir / "schedule.html").write_text(html, encoding="utf-8")
            items = parse_schedule(html, today.year)
    out, seen = [], set()
    for it in items:
        key = (it["start"], it["end"], it["title"], it.get("target"))
        if key not in seen:
            seen.add(key)
            out.append(it)
    out.sort(key=lambda x: (x["start"], x["end"], x.get("target") or ""))
    return out
