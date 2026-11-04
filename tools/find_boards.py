# -*- coding: utf-8 -*-
"""모든 단과대·학과 홈페이지를 돌면서 '공지사항' 게시판 주소를 자동으로 찾아 boards.json 에 추가.

실행:  python tools/find_boards.py            (전체, 3~5분)
       python tools/find_boards.py --only 전기   (이름에 '전기'가 들어간 곳만)
       python tools/find_boards.py --dry       (boards.json 은 건드리지 않고 결과만 출력)

결과:  boards.json 에 학과/단과대 게시판 추가
       setup/find_boards_report.txt 에 찾은 것/못 찾은 것 정리
       못 찾은 사이트의 HTML 은 debug/sites/ 에 저장 (파서 보완용)
"""
import sys
import re
import json
import argparse
import logging
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from gnu import fetch  # noqa: E402
from gnu.parse import clean  # noqa: E402

SEED = ROOT / "tools" / "departments_seed.json"
BOARDS_FILE = ROOT / "boards.json"
REPORT = ROOT / "setup" / "find_boards_report.txt"
DEBUG_DIR = ROOT / "debug" / "sites"

log = logging.getLogger("find")

# 이런 말이 들어간 게시판은 공지가 아님 (단, 이름에 '공지'가 있으면 예외)
SKIP_WORDS = ["자유", "포토", "사진", "갤러리", "Gallary", "Gallery", "자료실", "서식", "양식", "FAQ", "질문", "Q&A", "졸업작품",
              "매뉴얼", "앨범", "동문", "동창", "교수", "세미나", "예약", "뉴스레터", "링크", "채용", "홍보관", "브로슈어", "동영상",
              "출판", "추천도서", "교과과정", "시간표", "입학", "강의", "졸업생", "수우지", "음악회", "학생회", "취업"]
HARD_SKIP = ["대학원"]          # 대학원 게시판은 학부생 대상이 아니므로 제외
NOTICE_WORDS = ["공지", "소식", "알림", "notice", "Notice", "NOTICE", "news", "News", "NEWS"]
GENERIC_PARENTS = ["정보광장", "열린광장", "열린마당", "정보마당", "커뮤니티", "게시판", "학과활동", "대학생활", "자연대광장",
                   "학생광장", "학사과정", "재학생게시판", "학부게시판", "학과게시판", "소통광장", "알림마당", "알림광장", "학부"]

META_REFRESH = re.compile(r'http-equiv\s*=\s*["\']?refresh["\']?[^>]*content\s*=\s*["\'][^"\']*url\s*=\s*([^"\'>\s]+)', re.I)
JS_REDIRECT = re.compile(r'(?:location\.href|location\.replace|window\.location)\s*[=(]\s*["\']([^"\']+)["\']', re.I)
FRAME_SRC = re.compile(r'<(?:frame|iframe)[^>]+src\s*=\s*["\']([^"\']+)["\']', re.I)


def land(url, hops=3):
    """주소를 열고, meta refresh / JS / frame 리다이렉트를 따라가 최종 (html, url) 반환."""
    html, final = fetch.get(url)
    for _ in range(hops):
        if not html:
            return None, final
        nxt = None
        m = META_REFRESH.search(html) or JS_REDIRECT.search(html)
        if m:
            nxt = m.group(1)
        else:
            # 본문이 거의 없고 frame 만 있는 경우
            if len(clean(BeautifulSoup(html, "html.parser").get_text(" "))) < 200:
                f = FRAME_SRC.search(html)
                if f:
                    nxt = f.group(1)
        if not nxt:
            break
        nxt = urljoin(final, nxt.strip())
        if nxt == final:
            break
        html, final = fetch.get(nxt)
    return html, final


def menu_label(a):
    """링크의 부모 메뉴 이름 (li > a 구조에서 상위 li 의 첫 링크/텍스트)."""
    li = a.find_parent("li")
    parent_li = li.find_parent("li") if li else None
    if parent_li:
        first = parent_li.find(["a", "span", "button", "p", "strong"])
        if first:
            return clean(first.get_text())[:40]
    return ""


def find_boards_on(html, page_url):
    """페이지에서 게시판 목록 주소들을 찾음 → [{labels:[(label,parent),...], url, bbsId}]
    같은 게시판(bbsId)을 가리키는 메뉴가 여러 개면 이름을 전부 모음 (상위 메뉴 링크 = 첫 하위 게시판인 경우가 많음)."""
    soup = BeautifulSoup(html, "html.parser")
    boards = {}
    order = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "selectNttList.do" not in href:
            continue
        url = urljoin(page_url, href)
        q = parse_qs(urlparse(url).query)
        bbs = (q.get("bbsId") or [None])[0]
        if not bbs:
            continue
        label = clean(a.get_text())[:40]
        parent = menu_label(a)
        if bbs not in boards:
            boards[bbs] = {"labels": [], "url": url, "bbsId": bbs}
            order.append(bbs)
        if label and (label, parent) not in boards[bbs]["labels"]:
            boards[bbs]["labels"].append((label, parent))
    found = [boards[b] for b in order]
    # 메뉴에서 못 찾았으면 NOTICE 위젯의 글 링크에서 게시판 추정
    if not found:
        seen = set()
        for a in soup.find_all("a", href=True):
            if "selectNttInfo.do" in a["href"]:
                url = urljoin(page_url, a["href"])
                p = urlparse(url)
                q = parse_qs(p.query)
                bbs = (q.get("bbsId") or [None])[0]
                mi = (q.get("mi") or [None])[0]
                if bbs and bbs not in seen:
                    path = p.path.replace("selectNttInfo.do", "selectNttList.do")
                    list_url = f"{p.scheme}://{p.netloc}{path}?mi={mi}&bbsId={bbs}" if mi else f"{p.scheme}://{p.netloc}{path}?bbsId={bbs}"
                    found.append({"labels": [("공지사항", "")], "url": list_url, "bbsId": bbs})
                    seen.add(bbs)
    return found


def _score(board):
    labels = [l for l, _ in board["labels"]]
    parents = [p for _, p in board["labels"]]
    joined = " ".join(labels)
    if any(w in joined for w in HARD_SKIP):
        return 0, ""
    # 상위 메뉴가 전부 '대학원' 류이면 대학원 게시판
    if parents and all(any(w in p for w in HARD_SKIP) for p in parents if p) and any(p for p in parents):
        return 0, ""
    has_notice = any(w in joined for w in NOTICE_WORDS)
    has_skip = any(w in joined for w in SKIP_WORDS)
    if has_notice and not has_skip:
        return 10, "공지"
    if has_notice and has_skip and "공지" in joined:
        return 8, "공지+자료"
    if has_skip:
        return 0, ""
    if any(l in GENERIC_PARENTS for l in labels):
        return 5, "광장"
    return 0, ""


def choose(found):
    """찾은 게시판 중 수집할 것 고르기 → [{label, url, bbsId}] (최대 4개)"""
    scored = []
    for b in found:
        sc, why = _score(b)
        if sc <= 0:
            continue
        labels = [l for l, _ in b["labels"]]
        label = next((l for l in labels if "공지" in l), None) or next((l for l in labels if any(w in l for w in NOTICE_WORDS)), labels[0])
        scored.append((sc, {"label": label, "url": b["url"], "bbsId": b["bbsId"]}))
    scored.sort(key=lambda x: -x[0])
    return [b for _, b in scored[:4]]


def site_code(url):
    p = urlparse(url)
    seg = [s for s in p.path.split("/") if s]
    if p.netloc.startswith("www.gnu.ac.kr") and seg:
        return seg[0]
    return p.netloc.split(".")[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="이름에 이 글자가 들어간 학과/단과대만")
    ap.add_argument("--dry", action="store_true", help="boards.json 수정 없이 결과만")
    ap.add_argument("--no-college", action="store_true", help="단과대 홈페이지는 건너뜀")
    ap.add_argument("--keep", action="store_true", help="기존 학과 게시판을 지우지 않고 새것만 추가 (기본은 다시 찾기)")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=[logging.StreamHandler(sys.stdout)])
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(exist_ok=True)

    seed = json.loads(SEED.read_text(encoding="utf-8"))
    data = json.loads(BOARDS_FILE.read_text(encoding="utf-8"))
    boards = data["boards"]
    if not args.keep and not args.only:
        # 본부 게시판(main-*)만 남기고 학과/단과대 게시판은 처음부터 다시 찾음
        data["boards"] = boards = [b for b in boards if b["id"].startswith("main-")]
    existing_urls = {b["url"] for b in boards}
    existing_ids = {b["id"] for b in boards}

    targets = []  # (scope, unit, college, url)
    for col in seed["colleges"]:
        if not args.no_college:
            targets.append(("단과대", col["name"], None, col["url"]))
        for d in col["departments"]:
            targets.append(("학과", d["name"], col["name"], d["url"]))
    if args.only:
        targets = [t for t in targets if args.only in t[1]]

    # 같은 사이트를 쓰는 학과(수의예과/수의학과 등)는 한 번만
    by_site = {}
    for scope, unit, college, url in targets:
        key = url.rstrip("/").lower()
        if key in by_site:
            by_site[key]["units"].append(unit)
            continue
        by_site[key] = {"scope": scope, "unit": unit, "college": college, "url": url, "units": [unit]}

    report = []
    added = 0
    total = len(by_site)
    for i, (key, t) in enumerate(by_site.items(), 1):
        label = t["unit"] if len(t["units"]) == 1 else "/".join(t["units"])
        log.info("[%d/%d] %s  %s", i, total, label, t["url"])
        html, final = land(t["url"])
        if not html:
            report.append(f"✘ {label}: 접속 실패 ({t['url']})")
            continue
        found = find_boards_on(html, final)
        picks = choose(found)
        if not picks:
            code = site_code(final)
            (DEBUG_DIR / f"{code}.html").write_text(html, encoding="utf-8")
            kind = "다른 게시판 시스템(지원 예정)" if "selectNttList" not in html else "공지 메뉴 못 찾음"
            report.append(f"✘ {label}: {kind} → debug/sites/{code}.html 저장 ({final})")
            continue
        code = site_code(final)
        for b in picks:
            bid = re.sub(r"[^a-z0-9]+", "-", f"{code}-{b['bbsId']}".lower())
            if b["url"] in existing_urls or bid in existing_ids:
                continue
            lab = (b["label"] or "").strip()
            if lab.startswith(t["unit"]):
                lab = lab[len(t["unit"]):].strip()
            name = f"{t['unit']} {lab}" if lab and lab != t["unit"] else f"{t['unit']} 공지"
            boards.append({
                "id": bid, "name": name, "scope": t["scope"], "unit": t["unit"], "college": t["college"],
                "url": b["url"], "default_category": None,
                "aliases": t["units"][1:] if len(t["units"]) > 1 else [],
            })
            existing_urls.add(b["url"]); existing_ids.add(bid)
            added += 1
            report.append(f"✔ {label}: {name} ({b['url']})")

    if not args.dry:
        BOARDS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT.write_text("\n".join(report), encoding="utf-8")
    ok = sum(1 for r in report if r.startswith("✔"))
    bad = sum(1 for r in report if r.startswith("✘"))
    print(f"\n찾은 게시판 {ok}개 (새로 추가 {added}), 못 찾은 사이트 {bad}개")
    print(f"자세한 목록: setup/find_boards_report.txt")
    if not args.dry:
        print("이제 run.bat (python crawl.py) 를 다시 실행하면 학과 공지도 함께 수집돼요.")
    return 0


if __name__ == "__main__":
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
