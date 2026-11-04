# -*- coding: utf-8 -*-
"""게시판 추가 도우미.

사용법 (프로젝트 폴더에서):
  python tools/add_board.py "목록페이지주소" --name "전기공학과 공지" --scope 학과 --unit 전기공학과 --college IT공과대학

목록페이지주소: 학과 홈페이지 → 공지사항 메뉴 → 주소창 복사
  (예: https://www.gnu.ac.kr/ee/na/ntt/selectNttList.do?mi=1234&bbsId=5678)
"""
import sys
import json
import re
import argparse
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent.parent
BOARDS_FILE = ROOT / "boards.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--name", required=True, help="게시판 이름 (예: 전기공학과 공지)")
    ap.add_argument("--scope", default="학과", choices=["전체", "단과대", "학과"])
    ap.add_argument("--unit", default=None, help="학과/단과대 이름 (예: 전기공학과)")
    ap.add_argument("--college", default=None, help="학과일 때 소속 단과대 (예: IT공과대학)")
    ap.add_argument("--id", default=None, help="식별자 (생략하면 자동)")
    args = ap.parse_args()

    p = urlparse(args.url)
    q = parse_qs(p.query)
    if "selectNttList.do" not in p.path or "bbsId" not in q:
        print("! 주소가 게시판 목록 주소 같지 않아요. selectNttList.do?mi=..&bbsId=.. 형태여야 해요.")
        print("  그래도 추가하려면 boards.json 을 직접 편집하세요.")
        return 1
    seg = [s for s in p.path.split("/") if s]
    site_code = seg[0] if seg else "x"
    bid = args.id or re.sub(r"[^a-z0-9]+", "-", f"{site_code}-{q['bbsId'][0]}".lower())

    data = json.loads(BOARDS_FILE.read_text(encoding="utf-8"))
    boards = data["boards"]
    if any(b["id"] == bid for b in boards):
        print(f"! 이미 같은 id({bid})의 게시판이 있어요.")
        return 1
    if any(b["url"] == args.url for b in boards):
        print("! 이미 같은 주소의 게시판이 있어요.")
        return 1
    boards.append({
        "id": bid, "name": args.name, "scope": args.scope, "unit": args.unit, "college": args.college,
        "url": args.url, "default_category": None,
    })
    BOARDS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"추가됨: [{bid}] {args.name} ({args.scope}{' / ' + args.unit if args.unit else ''})")
    print("이제 python crawl.py --board", bid, "로 먼저 테스트해 보세요.")
    return 0


if __name__ == "__main__":
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
