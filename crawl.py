# -*- coding: utf-8 -*-
"""
경상국립대 공지 수집기.

실행:  python crawl.py
옵션:
  --pages N      게시판당 가져올 목록 페이지 수 (기본 1). 처음 한 번은 --pages 3 정도 추천
  --size N       한 페이지에 보여줄 글 수 (사이트가 지원하면 10/20/30/40/50)
  --board ID     특정 게시판만 (config.BOARDS 의 id)
  --no-detail    상세 페이지(본문·첨부)는 건너뛰고 목록만
  --no-schedule  학사일정 수집 안 함
  --debug        받은 HTML 을 debug/ 폴더에 저장 (파싱이 이상할 때)
"""
import sys
import argparse
import logging
from datetime import timedelta
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from gnu import config, fetch, parse, store  # noqa: E402
from gnu.classify import classify, tag_campus  # noqa: E402
from gnu.dday import find_deadline  # noqa: E402
from gnu.schedule import crawl_schedule  # noqa: E402
from gnu import ocr, images as imgstore  # noqa: E402
from gnu.calendar_feed import save_calendars  # noqa: E402

LOG_FILE = ROOT / "crawl.log"
DEBUG_DIR = ROOT / "debug"
VIEWS_REFRESH_DAYS = 5
VIEWS_REFRESH_MAX = 10
RUN_STARTED = None
BACKFILL = {"left": 400}   # 한 번 실행에서 본문을 뒤늦게 보충할 최대 글 수
DEBUG_SAVES = {"nosn": 0, "body": 0}
NEW_IDS = []               # 이번 실행에서 새로 생긴 글 (푸시 알림 발송용)


def setup_logging():
    fmt = "%(asctime)s %(levelname)s %(message)s"
    logging.basicConfig(level=logging.INFO, format=fmt, datefmt="%H:%M:%S",
                        handlers=[logging.StreamHandler(sys.stdout),
                                  logging.FileHandler(LOG_FILE, encoding="utf-8")])
    logging.getLogger("urllib3").setLevel(logging.WARNING)


log = logging.getLogger("gnu")


def fetch_detail(row, board, notice_id, debug, first):
    """상세 페이지를 받아 본문/첨부/메타를 돌려줌. 실패하면 None."""
    if not row.get("detail_url"):
        return None
    html, final_url = fetch.get(row["detail_url"])
    if not html:
        return None
    if debug and first:
        (DEBUG_DIR / f"{board['id']}_detail.html").write_text(html, encoding="utf-8")
    try:
        det = parse.parse_detail(html, final_url)
    except Exception as e:  # 파싱 실패해도 전체가 멈추지 않게
        log.exception("상세 파싱 실패 %s: %s", notice_id, e)
        return None
    if det.get("body_suspicious") and DEBUG_SAVES["body"] < 6:
        DEBUG_DIR.mkdir(exist_ok=True)
        (DEBUG_DIR / f"body_{notice_id}.html").write_text(html, encoding="utf-8")
        DEBUG_SAVES["body"] += 1
        log.warning("본문 대신 페이지 메뉴가 잡힘: %s → debug/body_%s.html 저장", notice_id, notice_id)
    return det


def crawl_board(board, index, args, status):
    bid = board["id"]
    log.info("=== [%s] %s", bid, board["name"])
    new_count, updated, errors = 0, 0, 0
    first_detail = True

    first_url = board["url"]
    if args.size and "listCo=" not in first_url and "/na/ntt/" in first_url:
        first_url += f"&listCo={args.size}"   # 경상국립대 게시판 공통 파라미터 (무시돼도 무해)
    html, final_url = fetch.get(first_url)
    if not html:
        log.error("[%s] 목록 페이지를 가져오지 못함", bid)
        status[bid] = {"name": board["name"], "ok": False, "error": "목록 요청 실패"}
        return
    if args.debug:
        (DEBUG_DIR / f"{bid}_list.html").write_text(html, encoding="utf-8")
    st = parse.page_status(html)
    if st == "login":
        log.info("[%s] 로그인이 필요한 게시판 → 수집 목록에서 제외", bid)
        store.disable_board(bid, "로그인 필요")
        status[bid] = {"name": board["name"], "ok": False, "error": "로그인 필요 (제외됨)"}
        return
    rows, pager = parse.parse_list(html, board["url"])
    if not rows:
        if st == "empty":
            log.info("[%s] 글이 없는 게시판", bid)
            status[bid] = {"name": board["name"], "ok": True, "new": 0, "updated": 0, "errors": 0, "listed": 0}
            return
        # 파싱 실패 → 자동으로 HTML 저장 (디버그용)
        DEBUG_DIR.mkdir(exist_ok=True)
        (DEBUG_DIR / f"{bid}_list.html").write_text(html, encoding="utf-8")
        log.error("[%s] 목록에서 글을 하나도 못 찾음. debug/%s_list.html 저장함", bid, bid)
        status[bid] = {"name": board["name"], "ok": False, "error": "목록 파싱 실패"}
        return
    log.info("[%s] 1페이지 %d건 (페이지 파라미터=%s, 크기 파라미터=%s, 전체=%s)",
             bid, len(rows), pager.get("page_param"), pager.get("size_param"), pager.get("total"))
    no_sn = sum(1 for r in rows if not r.get("ntt_sn"))
    if no_sn >= max(1, len(rows) // 2) and DEBUG_SAVES["nosn"] < 6:
        DEBUG_DIR.mkdir(exist_ok=True)
        (DEBUG_DIR / f"{bid}_list_nosn.html").write_text(html, encoding="utf-8")
        DEBUG_SAVES["nosn"] += 1
        log.warning("[%s] 글 번호를 못 읽은 행 %d/%d → debug/%s_list_nosn.html 저장", bid, no_sn, len(rows), bid)

    # 페이지 크기 변경(첫 요청에서 안 먹혔을 때) / 추가 페이지
    if args.size and pager.get("size_param") and len(rows) < args.size and (pager.get("total") or 0) > len(rows) and "listCo=" not in first_url:
        url1 = parse.build_list_url(board["url"], pager, page=1, size=args.size)
        h, _ = fetch.get(url1)
        if h:
            r2, _ = parse.parse_list(h, board["url"])
            if len(r2) >= len(rows):
                rows = r2
    for page in range(2, args.pages + 1):
        if not pager.get("page_param"):
            log.info("[%s] 페이지 파라미터를 몰라서 2페이지부터는 생략", bid)
            break
        urlp = parse.build_list_url(board["url"], pager, page=page, size=args.size)
        h, _ = fetch.get(urlp)
        if not h:
            break
        more, _ = parse.parse_list(h, board["url"])
        if not more:
            break
        known = {r["ntt_sn"] for r in rows if r["ntt_sn"]}
        more = [r for r in more if not (r["ntt_sn"] and r["ntt_sn"] in known)]
        if not more:
            break
        rows.extend(more)

    # 글 처리
    old_cutoff = (store.today_kst() - timedelta(days=store.RETENTION_DAYS)).isoformat()
    skipped_old = 0
    for row in rows:
        nid = store.make_id(bid, row.get("ntt_sn"), row["title"], row.get("date"))
        existing = index.get(nid)
        if not existing and row.get("date") and row["date"] < old_cutoff:
            # 보관 기간(1년)보다 오래된 글: 저장해도 바로 지워지므로 본문을 받지 않음
            skipped_old += 1
            continue
        if not existing and row.get("ntt_sn"):
            # 예전(번호를 못 읽던 때)에 제목+날짜로 저장된 글이면 새 id 로 옮김
            old_id = store.make_id(bid, None, row["title"], row.get("date"))
            old = index.pop(old_id, None)
            if old:
                old["id"] = nid
                old["url"] = row.get("detail_url") or old.get("url")
                index[nid] = old
                existing = old
        if existing:
            changed = False
            if row.get("views") is not None and row["views"] != existing.get("views"):
                existing["views"] = row["views"]
                changed = True
            if not existing.get("title") and row["title"]:
                existing["title"] = row["title"]
                changed = True
            # 본문이 없거나(또는 그림뿐인데 아직 그림을 안 받아둔 글) 상세 주소가 생겼으면 보충 (한 번에 한도만큼)
            if (not args.no_detail and row.get("detail_url") and BACKFILL["left"] > 0
                    and _needs_body(nid)):
                BACKFILL["left"] -= 1
                det = fetch_detail(row, board, nid, args.debug, first_detail)
                first_detail = False
                if det:
                    existing["url"] = row["detail_url"]
                    _apply_detail(existing, det, board)
                    changed = True
            if changed:
                existing["fetched_at"] = store.now_iso()
                updated += 1
            continue

        notice = {
            "id": nid,
            "board_id": bid,
            "board": board["name"],
            "scope": board["scope"],
            "unit": board.get("unit"),
            "college": board.get("college"),
            "title": row["title"],
            "dept": row.get("dept") or "",
            "date": row.get("date"),
            "views": row.get("views"),
            "url": row.get("detail_url") or board["url"],
            "category": None, "category_reason": None,
            "campus": ["공통"],
            "deadline": None, "deadline_source": None, "deadline_text": None,
            "has_attachments": False,
            "first_seen": store.now_iso(),
            "fetched_at": store.now_iso(),
        }
        det = None
        if not args.no_detail:
            det = fetch_detail(row, board, nid, args.debug, first_detail)
            first_detail = False
            if det is None and row.get("detail_url"):
                errors += 1
        if det:
            _apply_detail(notice, det, board)
        else:
            body_text = ""
            notice["category"], notice["category_reason"] = classify(notice["title"], notice["dept"], body_text, board)
            notice["campus"] = tag_campus(notice["title"], notice["dept"], body_text)
            dl, src, snip = find_deadline(notice["title"], body_text, notice["date"])
            notice["deadline"], notice["deadline_source"], notice["deadline_text"] = dl, src, snip
        index[nid] = notice
        new_count += 1
        NEW_IDS.append(nid)
        log.info("[%s] 새 글: %s → %s", bid, notice["title"][:40], notice["category"])

    # 최근 글 조회수 갱신 (목록에 조회수가 없는 게시판만)
    if not args.no_detail and rows and rows[0].get("views") is None:
        _refresh_views(board, index, args)

    status[bid] = {"name": board["name"], "ok": True, "new": new_count, "updated": updated,
                   "errors": errors, "listed": len(rows)}
    log.info("[%s] 새 글 %d, 갱신 %d, 오류 %d%s", bid, new_count, updated, errors,
             f", 1년 넘은 글 {skipped_old}건 건너뜀" if skipped_old else "")


def _needs_body(nid):
    b = store.load_body(nid)
    if b is None:
        return True
    body = (b.get("body") or "").strip()
    # 예전 버전으로 받은 글: 본문이 거의 없고 이미지 정보도 없거나, 본문 자리에 사이트 메뉴가 들어갔으면 다시 받아봄
    if "images" not in b and len(body) < 40:
        return True
    # 이미지가 있는데 아직 우리 저장소에 복사해 두지 않은 글 (예전 버전으로 받은 글)
    if any(isinstance(i, dict) and "local" not in i for i in (b.get("images") or [])):
        return True
    return any(m in body for m in parse.CHROME_MARKS)


def _apply_detail(notice, det, board):
    body = det.get("body") or ""
    images = det.get("images") or []
    ocr_text = ""
    pil_list = []
    if images:
        images, pil_list = imgstore.fetch_and_store(notice["id"], images)
    if pil_list and len(body.replace("[이미지]", "").strip()) < 80:
        # 글자는 검색용으로만 읽어 둠 (화면에는 그림을 보여주고 글자는 접어 둠)
        ocr_text = ocr.read_pil(pil_list)
        if ocr_text:
            body = (body + "\n\n[이미지 글자 자동 인식 — 오타가 있을 수 있어요]\n" + ocr_text).strip()
    if det.get("date") and not notice.get("date"):
        notice["date"] = det["date"]
    if det.get("dept") and not notice.get("dept"):
        notice["dept"] = det["dept"]
    elif det.get("author") and not notice.get("dept"):
        notice["dept"] = det["author"]
    if det.get("views") is not None:
        notice["views"] = det["views"]
    notice["has_attachments"] = bool(det.get("attachments"))
    notice["category"], notice["category_reason"] = classify(notice["title"], notice["dept"], body, board)
    notice["campus"] = tag_campus(notice["title"], notice["dept"], body)
    dl, src, snip = find_deadline(notice["title"], body, notice["date"])
    notice["deadline"], notice["deadline_source"], notice["deadline_text"] = dl, src, snip
    store.save_body(notice["id"], {
        "id": notice["id"],
        "title": notice["title"],
        "body": body,
        "images": images,
        "ocr": bool(ocr_text),
        "attachments": det.get("attachments") or [],
        "contact": det.get("contact"),
        "schedule": det.get("schedule"),
        "author": det.get("author"),
        "fetched_at": store.now_iso(),
    })
    notice["fetched_at"] = store.now_iso()


def _refresh_views(board, index, args):
    from datetime import date, timedelta
    cutoff = (date.today() - timedelta(days=VIEWS_REFRESH_DAYS)).isoformat()
    targets = [n for n in index.values()
               if n["board_id"] == board["id"] and (n.get("date") or "") >= cutoff and n.get("url")
               and not (RUN_STARTED and (n.get("fetched_at") or "") >= RUN_STARTED)]  # 이번 실행에서 받은 글은 제외
    targets.sort(key=lambda n: n.get("date") or "", reverse=True)
    for n in targets[:VIEWS_REFRESH_MAX]:
        html, final_url = fetch.get(n["url"])
        if not html:
            continue
        try:
            det = parse.parse_detail(html, final_url)
        except Exception:
            continue
        if det.get("views") is not None:
            n["views"] = det["views"]


def main():
    ap = argparse.ArgumentParser(description="경상국립대 공지 수집기")
    ap.add_argument("--pages", type=int, default=1)
    ap.add_argument("--size", type=int, default=None)
    ap.add_argument("--board", default=None)
    ap.add_argument("--no-detail", action="store_true")
    ap.add_argument("--no-schedule", action="store_true")
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--backfill", type=int, default=400, help="본문 없는 옛 글을 한 번에 보충할 최대 개수")
    ap.add_argument("--reclassify", action="store_true", help="수집 없이, 저장된 글 전체를 현재 규칙으로 다시 분류")
    args = ap.parse_args()
    BACKFILL["left"] = args.backfill

    setup_logging()
    global RUN_STARTED
    RUN_STARTED = store.now_iso()
    if args.debug:
        DEBUG_DIR.mkdir(exist_ok=True)

    boards = [b for b in config.BOARDS if not args.board or b["id"] == args.board]
    if not boards:
        log.error("게시판을 찾을 수 없음: %s", args.board)
        return 1

    index = store.load_index()
    log.info("기존 글 %d건 불러옴", len(index))
    status = {}
    if args.reclassify:
        by_id = {b["id"]: b for b in config.BOARDS}
        changed = 0
        for n in index.values():
            board = by_id.get(n["board_id"], {"name": n["board"], "default_category": None})
            body_obj = store.load_body(n["id"]) or {}
            body = body_obj.get("body") or ""
            cat, why = classify(n["title"], n.get("dept"), body, board)
            dl, src, snip = find_deadline(n["title"], body, n.get("date"))
            if cat != n.get("category") or dl != n.get("deadline"):
                changed += 1
            n["category"], n["category_reason"] = cat, why
            n["deadline"], n["deadline_source"], n["deadline_text"] = dl, src, snip
            n["campus"] = tag_campus(n["title"], n.get("dept"), body)
        total = store.save_index(index, {})
        try:
            import json as _json
            sched_items = _json.loads((store.DATA / "schedule.json").read_text(encoding="utf-8")).get("items", [])
        except Exception:
            sched_items = []
        save_calendars(index, sched_items, config.BOARDS)
        print(f"다시 분류 완료: {total}건 중 {changed}건 바뀜")
        return 0
    for board in boards:
        try:
            crawl_board(board, index, args, status)
        except Exception as e:
            log.exception("[%s] 처리 중 오류: %s", board["id"], e)
            status[board["id"]] = {"name": board["name"], "ok": False, "error": str(e)[:200]}

    total = store.save_index(index, status)
    store.save_departments(config.BOARDS)
    try:
        n_img = imgstore.prune(set(index.keys()))
        if n_img:
            log.info("주인 없는 이미지 %d개 정리", n_img)
    except Exception as e:
        log.warning("이미지 정리 실패: %s", e)
    try:
        DEBUG_DIR.mkdir(exist_ok=True)
        import json as _json
        (DEBUG_DIR / "new_ids.json").write_text(_json.dumps([i for i in NEW_IDS if i in index], ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        log.warning("새 글 목록 저장 실패: %s", e)

    sched_items = None
    if not args.no_schedule:
        try:
            DEBUG_DIR.mkdir(exist_ok=True)
            sched_items = crawl_schedule(DEBUG_DIR)
            store.save_schedule(sched_items)
            log.info("학사일정 %d건 저장", len(sched_items))
        except Exception as e:
            log.exception("학사일정 수집 오류: %s", e)
    if sched_items is None:
        try:
            import json as _json
            sched_items = _json.loads((store.DATA / "schedule.json").read_text(encoding="utf-8")).get("items", [])
        except Exception:
            sched_items = []
    try:
        n_cal = save_calendars(index, sched_items, config.BOARDS)
        log.info("캘린더 구독 파일 생성: 학사일정 + 학과별 %d개", n_cal)
    except Exception as e:
        log.exception("캘린더 파일 생성 오류: %s", e)

    # 요약
    print("\n==== 요약 ====")
    for bid, s in status.items():
        if s.get("ok"):
            print(f"  {s['name']:<14} 목록 {s['listed']:>3}건 / 새 글 {s['new']:>3} / 갱신 {s['updated']:>3} / 오류 {s['errors']}")
        else:
            print(f"  {s['name']:<14} 실패: {s.get('error')}")
    print(f"  저장된 글 총 {total}건 → docs/data/notices.json")
    failed = [s for s in status.values() if not s.get("ok")]
    if failed:
        print("  * 실패한 게시판이 있어요. debug/ 폴더의 HTML 파일을 보내주시면 파서를 고칠 수 있어요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
