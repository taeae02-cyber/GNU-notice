# -*- coding: utf-8 -*-
"""제목/본문에서 마감일(신청·접수 기한)을 추출.

예) "(~11.2)", "~'26. 11. 11.(수) 09:00", "11/11까지", "접수기간: 2026. 11. 2.(월) ~ 11. 11.(수)"
100% 는 불가능하므로 못 찾으면 None 을 돌려주고 억지로 추측하지 않음.
"""
import re
from datetime import date, timedelta

# 연도(2자리/4자리, 앞에 ' 가능) 는 선택, 월·일은 필수. 뒤에 영문이 바로 오면(1.2MB) 제외.
TOKEN = re.compile(
    r"(?:['’‘]?(?P<y>\d{4}|\d{2})\s*[.\-/년]\s*)?"
    r"(?P<m>\d{1,2})\s*[.\-/월]\s*(?P<d>\d{1,2})\s*(?:일)?\.?"
    r"(?![A-Za-z\d])"
)
TILDE = r"[~∼〜–]|부터"
DEADLINE_WORDS = ("마감", "기한", "까지", "접수", "신청", "모집", "제출", "등록", "설문", "응모", "참가", "참여",
                  "투표", "예약", "until", "due", "deadline")
PREFER_WORDS = ("접수", "신청", "모집", "제출", "마감", "기한", "등록")
# 이런 말 근처의 날짜는 '행사 일정'이지 마감이 아님 (단, 접수/신청 같은 말이 같이 있으면 인정)
NEG_WORDS = ("운영", "행사", "일시", "개강", "종강", "수업", "시험", "고사", "발표회", "공연", "개최",
             "지급", "입사일", "교육일", "일정:", "기간 중", "점검", "휴무", "휴관", "방학")


def _to_date(y, m, d, posted):
    no_year = y is None
    try:
        if y is None:
            y = posted.year
        elif y < 100:
            y += 2000
        dt = date(y, m, d)
    except (ValueError, TypeError):
        return None
    # 연도가 없고, 게시일보다 60일 이상 과거면 다음 해로 (12월 게시 → 1월 마감)
    if no_year and dt < posted - timedelta(days=60):
        try:
            dt = date(dt.year + 1, m, d)
        except ValueError:
            return None
    if dt > posted + timedelta(days=400) or dt < posted - timedelta(days=120):
        return None
    return dt


def _tokens(text):
    out = []
    for m in TOKEN.finditer(text):
        y = int(m.group("y")) if m.group("y") else None
        mo, d = int(m.group("m")), int(m.group("d"))
        if not (1 <= mo <= 12 and 1 <= d <= 31):
            continue
        out.append({"start": m.start(), "end": m.end(), "y": y, "m": mo, "d": d, "text": m.group(0)})
    return out


def _candidates(text, posted, require_keyword):
    """문장에서 마감일 후보 [(date, score, snippet)] 추출."""
    cands = []
    toks = _tokens(text)
    for i, t in enumerate(toks):
        before = text[max(0, t["start"] - 25):t["start"]]
        after = text[t["end"]:t["end"] + 12]
        score = 0
        prefer = any(w in before for w in PREFER_WORDS)
        negative = any(w in before for w in NEG_WORDS)
        if negative and not prefer:
            continue
        # A ~ B 범위의 B 인가?  (앞 토큰과 ~ 로 연결) → 키워드가 있어야 마감으로 인정
        is_range_end = False
        if i > 0:
            between = text[toks[i - 1]["end"]:t["start"]]
            if len(between) <= 16 and "\n" not in between and re.search(TILDE, between):
                is_range_end = True
                before = text[max(0, toks[i - 1]["start"] - 25):toks[i - 1]["start"]]
                prefer = any(w in before for w in PREFER_WORDS)
                if any(w in before for w in NEG_WORDS) and not prefer:
                    continue
                score += 2 if any(w in before for w in DEADLINE_WORDS) else 0
        # "~ B" (시작 생략) → 마감일 가능성 높음
        if not is_range_end and re.search(r"(?:" + TILDE + r")\s*$", before):
            is_range_end = True
            score += 3
        # "B 까지"
        if re.match(r"\s*(?:\([^)]{1,4}\))?\s*(?:\d{1,2}:\d{2})?\s*(?:오전|오후)?\s*\d{0,2}:?\d{0,2}\s*(까지|限)", after):
            score += 3
        # 앞에 마감 관련 단어
        for w in DEADLINE_WORDS:
            if w in before:
                score += 2 if w in PREFER_WORDS else 1
        # 범위의 시작(A ~) 은 제외
        if i + 1 < len(toks):
            between = text[t["end"]:toks[i + 1]["start"]]
            if len(between) <= 16 and "\n" not in between and re.search(TILDE, between):
                continue
        if require_keyword and score == 0:
            continue
        dt = _to_date(t["y"], t["m"], t["d"], posted)
        if dt is None:
            continue
        snippet = text[max(0, t["start"] - 20):t["end"] + 8].replace("\n", " ").strip()
        cands.append((dt, score, snippet))
    return cands


def find_deadline(title, body, posted_str):
    """(deadline 'YYYY-MM-DD' | None, source 'title'|'body'|None, snippet)"""
    posted = None
    if posted_str:
        try:
            posted = date.fromisoformat(posted_str)
        except ValueError:
            posted = None
    posted = posted or date.today()

    # 1) 제목: 키워드 없어도 "~날짜" 나 "까지" 면 인정, 그 외엔 키워드 필요
    cands = _candidates(title or "", posted, require_keyword=True)
    if cands:
        cands.sort(key=lambda c: (-c[1], c[0]))
        dt, _, snip = cands[0]
        return dt.isoformat(), "title", snip

    # 2) 본문: 접수/신청/마감 키워드 근처만
    text = (body or "")[:4000]
    cands = _candidates(text, posted, require_keyword=True)
    if cands:
        # 점수 높은 순, 같으면 본문에서 먼저 나온 것
        best = max(range(len(cands)), key=lambda i: (cands[i][1], -i))
        dt, _, snip = cands[best]
        return dt.isoformat(), "body", snip
    return None, None, None
