# -*- coding: utf-8 -*-
"""카테고리 분류 + 캠퍼스 태그. 규칙은 config.RULES / config.CAMPUSES 에 있음."""
import re
from . import config


def _hits(text, words):
    if not text:
        return []
    low = text.lower()
    return [w for w in words if w.lower() in low]


def classify(title, dept, body, board):
    """(category, reason) 반환. reason 은 왜 그렇게 분류했는지 짧은 설명."""
    forced = board.get("force_category")
    if forced:
        return forced, f"게시판:{board['name']}"

    title = title or ""
    dept = dept or ""
    body_head = (body or "")[:600]
    scores = {}
    reasons = {}
    for cat in config.CATEGORIES:
        rule = config.RULES.get(cat, {})
        s = 0
        why = []
        d = _hits(dept, rule.get("dept", []))
        if d:
            s += 3 * len(d)
            why.append("부서:" + ",".join(d[:2]))
        t = _hits(title, rule.get("title", []))
        if t:
            s += 2 * len(t)
            why.append("제목:" + ",".join(t[:3]))
        b = _hits(body_head, rule.get("body", []))
        if b:
            s += 1 * len(b)
            why.append("본문:" + ",".join(b[:2]))
        if s:
            scores[cat] = s
            reasons[cat] = " / ".join(why)

    default = board.get("default_category")
    if default and default in config.CATEGORIES:
        # 게시판 기본값은 가산점 2 (제목 키워드 하나와 같은 무게)
        scores[default] = scores.get(default, 0) + 2
        reasons[default] = (reasons.get(default, "") + f" / 게시판:{board['name']}").strip(" /")

    if not scores:
        return config.FALLBACK_CATEGORY, "규칙에 해당 없음"
    best = max(scores.items(), key=lambda kv: (kv[1], -config.CATEGORIES.index(kv[0])))
    return best[0], reasons[best[0]]


def tag_campus(title, dept, body):
    text = " ".join([title or "", dept or "", (body or "")[:300]])
    found = []
    for campus, words in config.CAMPUSES.items():
        for w in words:
            if w in text:
                found.append(campus)
                break
    return found or ["공통"]


# ---------------------------------------------------------------------------
# 중복 판단용 키, 중요/변경 표시
# ---------------------------------------------------------------------------
_LEAD_TAG = re.compile(r"^(\s*(\[[^\]]{0,30}\]|【[^】]{0,30}】|★[^★]{0,8}★|★+|☆+|"
                       r"\((중요|필독|긴급|재공지|기간\s*연장|연장|수정|변경|경상국립대|구\.?\s*경남과기대[^)]*|칠암|가좌)\)))+")
_TAIL_PAREN = re.compile(r"(\s*\([^)]*\))+\s*$")
_DEADLINE_PAREN = re.compile(r"\(\s*[~∼〜][^)]*\)")
_NONWORD = re.compile(r"[^0-9a-z가-힣]+")
IMPORTANT_RE = re.compile(r"필독|★|☆|\[중요\]|\(중요\)|중요\]|긴급|필수|반드시|\[필수")
CHANGED_RE = re.compile(r"기간\s*연장|연장\s*안내|변경\s*안내|수정\s*공지|재공지|재안내|정정\s*공지|일정\s*변경|\(수정\)|\[수정\]|\(변경\)|\[변경\]")


def dup_key(title):
    """같은 공지가 여러 게시판에 올라온 걸 묶기 위한 키. 앞의 [태그], 뒤의 (괄호), (~마감) 을 떼고 글자만 남김."""
    t = (title or "").strip()
    t = _LEAD_TAG.sub("", t)
    t = _DEADLINE_PAREN.sub("", t)
    t = _TAIL_PAREN.sub("", t)
    t = _NONWORD.sub("", t.lower())
    return t[:80]


def title_flags(title):
    flags = []
    if IMPORTANT_RE.search(title or ""):
        flags.append("중요")
    if CHANGED_RE.search(title or ""):
        flags.append("변경")
    return flags
