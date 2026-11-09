# -*- coding: utf-8 -*-
"""
푸시 알림 발송기 — 수집(crawl.py) 직후 GitHub Actions 에서 실행.

흐름
  1. debug/new_ids.json (이번 수집에서 새로 생긴 글) 읽기
  2. 푸시 서버(Cloudflare Worker) /export 에서 구독자 목록 + 서명 키 받기
  3. 구독자마다 조건(키워드, 내 학과 새 글)에 맞는 글을 골라 Web Push 로 보냄
  4. 사라진 구독(404/410)은 서버에서 지우도록 /remove 호출

환경변수 (GitHub 저장소 Settings → Secrets)
  PUSH_SERVER  푸시 서버 주소  예: https://gnu-push.xxx.workers.dev
  PUSH_TOKEN   서버 TOKEN 과 같은 값

직접 시험: python tools/push_send.py --dry   (보내지 않고 누가 뭘 받을지만 출력)
"""
import argparse
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import requests  # noqa: E402

from gnu import config, store  # noqa: E402
from gnu.webpush import send  # noqa: E402

MAX_PER_SUB = 4            # 한 사람에게 한 번에 보낼 개별 알림 최대 개수 (넘치면 묶음 알림 1개)
TTL = 6 * 3600             # 폰이 꺼져 있어도 6시간까지는 기다렸다 전달


def load_new_notices(ids_path=None):
    ids_path = ids_path or (ROOT / "debug" / "new_ids.json")
    if not ids_path.exists():
        return []
    ids = set(json.loads(ids_path.read_text(encoding="utf-8")))
    if not ids:
        return []
    data = json.loads((store.DATA / "notices.json").read_text(encoding="utf-8"))
    items = data.get("notices", data) if isinstance(data, dict) else data
    return [n for n in items if n["id"] in ids]


def matches(sub, n):
    """구독 조건에 맞으면 이유 문자열, 아니면 None."""
    hay = (n.get("title", "") + " " + (n.get("dept") or "") + " " + (n.get("unit") or "")).lower()
    for k in sub.get("keywords") or []:
        k = str(k).strip().lower()
        if k and k in hay:
            return f"키워드 '{k}'"
    dept = sub.get("dept")
    if sub.get("deptNew", True) and dept and dept.get("unit"):
        if n.get("scope") == "학과" and n.get("unit") == dept["unit"]:
            return f"{dept.get('name') or dept['unit']} 새 글"
        if dept.get("scope") == "단과대" and n.get("scope") == "단과대" and n.get("unit") == dept["unit"]:
            return f"{dept.get('name') or dept['unit']} 새 글"
    return None


def dday_text(n):
    dl = n.get("deadline")
    if not dl:
        return ""
    try:
        y, m, d = map(int, dl.split("-"))
        days = (date(y, m, d) - date.today()).days
    except Exception:
        return ""
    if days < 0:
        return ""
    return f" · 마감 {m}.{d:02d} (D-{days})" if days else f" · 오늘 마감"


def payload_for(n):
    cat = n.get("category") or "공지"
    where = n.get("dept") or n.get("unit") or n.get("board") or ""
    return {
        "title": f"[{cat}] {n['title']}",
        "body": f"{where}{dday_text(n)}",
        "url": f"{config.SITE_URL}#/n/{n['id']}",
        "tag": "gnu-" + n["id"],
    }


def summary_payload(items, reason_count):
    return {
        "title": f"GNU 공지 — 새 공지 {len(items)}건",
        "body": " / ".join(i["title"][:28] for i in items[:3]) + (" …" if len(items) > 3 else ""),
        "url": f"{config.SITE_URL}#/tab/%EB%82%B4%20%ED%82%A4%EC%9B%8C%EB%93%9C",
        "tag": "gnu-summary",
    }


def dedupe(items):
    """같은 공지가 여러 게시판에 올라온 경우 하나만."""
    seen, out = set(), []
    for n in items:
        k = (n.get("dup_key") or n.get("title")) + "|" + (n.get("deadline") or "")
        if k in seen:
            continue
        seen.add(k)
        out.append(n)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="보내지 않고 대상만 출력")
    ap.add_argument("--ids", help="새 글 id 목록 파일 (기본 debug/new_ids.json)")
    args = ap.parse_args()

    server = (os.environ.get("PUSH_SERVER") or "").rstrip("/")
    token = os.environ.get("PUSH_TOKEN") or ""
    if not server or not token:
        print("PUSH_SERVER / PUSH_TOKEN 이 없어 푸시 발송을 건너뜀")
        return 0

    new = load_new_notices(Path(args.ids) if args.ids else None)
    if not new:
        print("새 글 없음 → 발송 없음")
        return 0
    new.sort(key=lambda n: (n.get("date") or "", n.get("first_seen") or ""), reverse=True)

    r = requests.get(server + "/export", headers={"Authorization": "Bearer " + token}, timeout=20)
    if r.status_code != 200:
        print(f"구독 목록을 못 받음: HTTP {r.status_code} {r.text[:200]}")
        return 1
    ex = r.json()
    subs, priv = ex.get("subs", []), ex.get("privateKey")
    print(f"새 글 {len(new)}건, 구독자 {len(subs)}명")
    if not subs or not priv:
        return 0

    sent = failed = 0
    dead = []
    for sub in subs:
        hits = []
        for n in new:
            why = matches(sub, n)
            if why:
                hits.append((n, why))
        if not hits:
            continue
        items = dedupe([h[0] for h in hits])
        payloads = [payload_for(n) for n in items] if len(items) <= MAX_PER_SUB else [summary_payload(items, len(hits))]
        label = (sub.get("dept") or {}).get("name") or "학과 없음"
        print(f"- 구독자({label}, 키워드 {len(sub.get('keywords') or [])}개): {len(items)}건 → 알림 {len(payloads)}개")
        if args.dry:
            for p in payloads:
                print("    ", p["title"], "|", p["body"])
            continue
        for p in payloads:
            try:
                code = send(sub["subscription"], p, priv, config.SITE_URL, ttl=TTL)
            except Exception as e:
                failed += 1
                print("    발송 오류:", str(e)[:120])
                continue
            if code in (200, 201, 202):
                sent += 1
            elif code in (404, 410):
                dead.append(sub["subscription"]["endpoint"])
                print("    구독이 사라짐 (브라우저에서 알림을 껐거나 앱 삭제) → 정리")
                break
            else:
                failed += 1
                print(f"    발송 실패: HTTP {code}")
            time.sleep(0.05)

    if dead and not args.dry:
        try:
            requests.post(server + "/remove", headers={"Authorization": "Bearer " + token}, json={"endpoints": dead}, timeout=20)
        except Exception as e:
            print("죽은 구독 정리 실패:", e)
    print(f"발송 {sent}건, 실패 {failed}건, 정리 {len(dead)}건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
