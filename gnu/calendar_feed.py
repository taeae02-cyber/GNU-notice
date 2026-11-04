# -*- coding: utf-8 -*-
"""캘린더 구독용 .ics 파일 생성.

docs/calendar/schedule.ics        학사일정(학부)
docs/calendar/schedule-all.ics    학사일정(학부+대학원)
docs/calendar/all.ics             전체 공지 마감일
docs/calendar/u/<코드>.ics        학과/단과대별: 전체 공지 + 내 단과대 + 내 학과 마감일 + 학사일정(학부)
docs/calendar/index.json          학과 이름 → 파일 이름

구글/애플 캘린더에서 이 주소를 '구독'하면 새 마감이 자동으로 들어감.
"""
import json
import hashlib
from datetime import date, datetime, timedelta, timezone

from .store import DOCS, KST

CAL_DIR = DOCS / "calendar"
WINDOW_PAST = 30      # 며칠 전 마감까지 포함
WINDOW_FUTURE = 400


def _esc(text):
    return (text or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line):
    """ICS 는 한 줄 75바이트 제한 → 접기"""
    out, cur = [], ""
    for ch in line:
        if len((cur + ch).encode("utf-8")) > 72:
            out.append(cur)
            cur = " " + ch
        else:
            cur += ch
    out.append(cur)
    return "\r\n".join(out)


def _event(uid, start, end, summary, description, url=None):
    s = date.fromisoformat(start)
    e = date.fromisoformat(end or start) + timedelta(days=1)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VEVENT", f"UID:{uid}@gnu-notice", f"DTSTAMP:{stamp}",
             f"DTSTART;VALUE=DATE:{s.strftime('%Y%m%d')}", f"DTEND;VALUE=DATE:{e.strftime('%Y%m%d')}",
             f"SUMMARY:{_esc(summary)}"]
    if description:
        lines.append(f"DESCRIPTION:{_esc(description)}")
    if url:
        lines.append(f"URL:{url}")
    lines.append("END:VEVENT")
    return "\r\n".join(_fold(ln) for ln in lines)


def _write(path, text):
    # 윈도우에서 \n → \r\n 자동 변환되면 \r\r\n 이 되므로 바이트로 그대로 씀
    path.write_bytes(text.encode("utf-8"))


def _calendar(name, events):
    head = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//GNU 공지//KO", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
            f"X-WR-CALNAME:{_esc(name)}", "X-WR-TIMEZONE:Asia/Seoul",
            "REFRESH-INTERVAL;VALUE=DURATION:PT1H", "X-PUBLISHED-TTL:PT1H"]
    return "\r\n".join(head) + "\r\n" + "\r\n".join(events) + "\r\nEND:VCALENDAR\r\n"


def _in_window(day):
    try:
        d = date.fromisoformat(day)
    except (TypeError, ValueError):
        return False
    today = datetime.now(KST).date()
    return today - timedelta(days=WINDOW_PAST) <= d <= today + timedelta(days=WINDOW_FUTURE)


def _sched_events(items, include_grad):
    out = []
    for it in items:
        if not include_grad and it.get("target") == "대학원":
            continue
        if not _in_window(it["end"]):
            continue
        uid = "sch-" + hashlib.md5(f"{it['start']}|{it['end']}|{it['title']}".encode("utf-8")).hexdigest()[:12]
        out.append(_event(uid, it["start"], it["end"], "[학사] " + it["title"], "경상국립대 학사일정"))
    return out


def _deadline_events(notices):
    out = []
    for n in notices:
        if not n.get("deadline") or not _in_window(n["deadline"]):
            continue
        desc = f"{n.get('dept') or n.get('board') or ''} · {n.get('category') or ''}"
        out.append(_event("dl-" + n["id"], n["deadline"], n["deadline"], "[마감] " + n["title"], desc, n.get("url")))
    return out


def unit_code(name):
    return hashlib.md5(name.encode("utf-8")).hexdigest()[:8]


def save_calendars(index, schedule_items, boards):
    CAL_DIR.mkdir(parents=True, exist_ok=True)
    (CAL_DIR / "u").mkdir(exist_ok=True)
    notices = list(index.values())
    sched_u = _sched_events(schedule_items, include_grad=False)
    _write(CAL_DIR / "schedule.ics", _calendar("경상국립대 학사일정(학부)", sched_u))
    _write(CAL_DIR / "schedule-all.ics", _calendar("경상국립대 학사일정(전체)", _sched_events(schedule_items, include_grad=True)))
    all_dl = _deadline_events([n for n in notices if n.get("scope") == "전체"])
    _write(CAL_DIR / "all.ics", _calendar("GNU 공지 — 전체 공지 마감", all_dl + sched_u))

    units = {}
    for b in boards:
        if b.get("scope") in ("학과", "단과대") and b.get("unit"):
            units[b["unit"]] = {"scope": b["scope"], "college": b.get("college")}
            for alias in b.get("aliases") or []:
                units[alias] = {"scope": b["scope"], "college": b.get("college"), "unit": b["unit"]}
    index_json = {}
    for name, info in units.items():
        real = info.get("unit", name)
        mine = [n for n in notices if n.get("scope") == "전체"
                or (n.get("scope") == "학과" and n.get("unit") == real)
                or (n.get("scope") == "단과대" and (n.get("unit") == real or (info.get("college") and n.get("unit") == info["college"])))]
        code = unit_code(name)
        _write(CAL_DIR / "u" / f"{code}.ics", _calendar(f"GNU 공지 — {name} 마감·학사일정", _deadline_events(mine) + sched_u))
        index_json[name] = f"calendar/u/{code}.ics"
    (CAL_DIR / "index.json").write_text(json.dumps(
        {"schedule": "calendar/schedule.ics", "schedule_all": "calendar/schedule-all.ics", "all": "calendar/all.ics",
         "units": index_json}, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(index_json)
