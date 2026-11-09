# -*- coding: utf-8 -*-
"""수집 결과 저장. 사이트(docs/)가 읽는 JSON 파일들을 만든다.

docs/data/notices.json      목록 (본문 제외, 가벼움)
docs/data/body/<id>.json    본문·첨부파일 (글을 눌렀을 때만 읽음)
docs/data/schedule.json     학사일정
docs/data/departments.json  학과/단과대 목록 (학과 검색용)
docs/data/meta.json         마지막 갱신 시각, 게시판 상태
"""
import json
import hashlib
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
DATA = DOCS / "data"
BODY_DIR = DATA / "body"
KST = timezone(timedelta(hours=9))

INDEX_FIELDS = ["id", "board_id", "board", "scope", "unit", "college", "title", "dept", "date", "views",
                "url", "category", "category_reason", "campus", "deadline", "deadline_source",
                "deadline_text", "has_attachments", "first_seen", "fetched_at", "dup_key", "flags"]
SEARCH_SNIPPET = 500
RETENTION_DAYS = 365


def now_iso():
    return datetime.now(KST).replace(microsecond=0).isoformat()


def make_id(board_id, ntt_sn, title, date_str):
    if ntt_sn:
        return f"{board_id}-{ntt_sn}"
    h = hashlib.sha1(f"{board_id}|{title}|{date_str}".encode("utf-8")).hexdigest()[:10]
    return f"{board_id}-h{h}"


def _is_sample():
    f = DATA / "meta.json"
    if not f.exists():
        return False
    try:
        return bool(json.loads(f.read_text(encoding="utf-8")).get("sample"))
    except json.JSONDecodeError:
        return False


def load_index():
    f = DATA / "notices.json"
    if not f.exists():
        return {}
    if _is_sample():
        # 예시 데이터는 실제 수집 시작할 때 전부 버림
        for bf in BODY_DIR.glob("*.json"):
            bf.unlink()
        return {}
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {n["id"]: n for n in data.get("notices", [])}


def load_body(notice_id):
    f = BODY_DIR / f"{notice_id}.json"
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def save_body(notice_id, body_obj):
    BODY_DIR.mkdir(parents=True, exist_ok=True)
    (BODY_DIR / f"{notice_id}.json").write_text(
        json.dumps(body_obj, ensure_ascii=False, indent=None), encoding="utf-8")


def today_kst():
    return datetime.now(KST).date()


def _drop_stale_hash_entries(index):
    """예전 버전이 번호 없이 저장한 글(id 끝이 -h…)과 같은 글(게시판·제목·날짜 동일)이 번호로 다시 들어왔으면 옛것을 지움."""
    import re
    norm = lambda t: re.sub(r"\s+", "", t or "")
    real = {}
    for n in index.values():
        if not re.search(r"-h[0-9a-f]{10}$", n["id"]):
            real[(n["board_id"], norm(n.get("title")), n.get("date"))] = n["id"]
    removed = 0
    for nid in list(index.keys()):
        if re.search(r"-h[0-9a-f]{10}$", nid):
            n = index[nid]
            if (n["board_id"], norm(n.get("title")), n.get("date")) in real:
                bf = BODY_DIR / f"{nid}.json"
                if bf.exists():
                    bf.unlink()
                _remove_images(nid)
                del index[nid]
                removed += 1
    return removed


def _remove_images(nid):
    img_dir = DATA / "img"
    if img_dir.exists():
        for f in img_dir.glob(f"{nid}-*.jpg"):
            try:
                f.unlink()
            except OSError:
                pass


def _drop_orphans(index):
    """boards.json 에서 사라진 게시판의 글 삭제 (find_boards 다시 돌려 게시판이 바뀐 경우)."""
    f = ROOT / "boards.json"
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        ids = {b["id"] for b in data.get("boards", [])}
    except (OSError, json.JSONDecodeError, KeyError):
        return 0
    if not ids:
        return 0
    removed = 0
    for nid in list(index.keys()):
        if index[nid].get("board_id") not in ids:
            bf = BODY_DIR / f"{nid}.json"
            if bf.exists():
                bf.unlink()
            _remove_images(nid)
            del index[nid]
            removed += 1
    return removed


def save_index(index, boards_status):
    from .classify import dup_key, title_flags
    DATA.mkdir(parents=True, exist_ok=True)
    _drop_stale_hash_entries(index)
    _drop_orphans(index)
    cutoff = (today_kst() - timedelta(days=RETENTION_DAYS)).isoformat()
    notices = []
    search = {}
    for n in index.values():
        if n.get("date") and n["date"] < cutoff:
            bf = BODY_DIR / f"{n['id']}.json"
            if bf.exists():
                bf.unlink()
            _remove_images(n["id"])
            continue
        n["dup_key"] = dup_key(n.get("title"))
        n["flags"] = title_flags(n.get("title"))
        notices.append({k: n.get(k) for k in INDEX_FIELDS})
        body = load_body(n["id"])
        if body and body.get("body"):
            search[n["id"]] = body["body"][:SEARCH_SNIPPET]
    notices.sort(key=lambda n: ((n.get("date") or ""), n.get("first_seen") or "", n["id"]), reverse=True)
    payload = {"generated_at": now_iso(), "count": len(notices), "notices": notices}
    (DATA / "notices.json").write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                                       encoding="utf-8")
    (DATA / "search.json").write_text(json.dumps(search, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    meta = {"generated_at": now_iso(), "count": len(notices), "boards": boards_status}
    (DATA / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(notices)


def save_schedule(items):
    DATA.mkdir(parents=True, exist_ok=True)
    payload = {"generated_at": now_iso(), "count": len(items), "items": items}
    (DATA / "schedule.json").write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                                        encoding="utf-8")


def save_departments(boards):
    """학과 검색용 목록. 게시판이 연결된 학과/단과대만 들어감."""
    DATA.mkdir(parents=True, exist_ok=True)
    units = {}
    for b in boards:
        if b.get("scope") in ("학과", "단과대") and b.get("unit"):
            units[b["unit"]] = {"name": b["unit"], "unit": b["unit"], "scope": b["scope"], "college": b.get("college")}
            for alias in b.get("aliases") or []:   # 같은 홈페이지를 쓰는 다른 학과 이름
                units[alias] = {"name": alias, "unit": b["unit"], "scope": b["scope"], "college": b.get("college")}
    payload = {"generated_at": now_iso(), "units": sorted(units.values(), key=lambda u: u["name"])}
    (DATA / "departments.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def disable_board(board_id, reason):
    """boards.json 에서 게시판을 비활성화 (로그인 필요 등). 다시 켜려면 disabled 를 지우면 됨."""
    f = ROOT / "boards.json"
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    for b in data.get("boards", []):
        if b.get("id") == board_id:
            b["disabled"] = True
            b["disabled_reason"] = reason
    f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
