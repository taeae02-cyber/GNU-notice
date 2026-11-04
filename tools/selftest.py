# -*- coding: utf-8 -*-
"""인터넷 없이 수집기 전체 흐름을 점검하는 자가 테스트.
실행: python tools/selftest.py
학교 서버 대신 미리 만들어 둔 가짜 HTML 을 먹여서 파싱 → 분류 → 저장까지 도는지 확인.
"""
import sys
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gnu import fetch, parse, store, config  # noqa: E402
from gnu.classify import classify, tag_campus  # noqa: E402
from gnu.dday import find_deadline  # noqa: E402
from gnu.schedule import parse_schedule  # noqa: E402

LIST_HTML = """
<html><body>
<div class="bbs_list">
<p class="total">전체 <strong>2,651</strong>건 1/266페이지</p>
<form name="frm" action="/main/na/ntt/selectNttList.do" method="post">
<input type="hidden" name="mi" value="1126"/><input type="hidden" name="bbsId" value="1028"/>
<input type="hidden" name="currPage" value="1"/>
<select name="pageUnit"><option value="10" selected>10건</option><option value="20">20건</option>
<option value="30">30건</option><option value="40">40건</option><option value="50">50건</option></select>
</form>
<table class="bbs_table"><caption>공지 목록</caption>
<thead><tr><th>번호</th><th>제목</th><th>부서</th><th>등록일</th></tr></thead>
<tbody>
<tr><td>2651</td><td class="subject"><a href="/main/na/ntt/selectNttInfo.do?mi=1126&amp;bbsId=1028&amp;nttSn=9140443">[홍보]「2026년 진주시 기후변화·탄소중립 우수사례 공모전」참여 안내</a> <span class="new">새로운 글</span></td><td>진주시탄소중립지원센터</td><td>2026.11.02</td></tr>
<tr><td>2650</td><td class="subject"><a href="javascript:void(0)" onclick="fn_view('9139601'); return false;">2026년 취업활동사례 수기 공모전 안내</a><span class="new">새로운 글</span></td><td>진로취업지원실</td><td>2026.11.02</td></tr>
<tr><td>2649</td><td class="subject"><a href="#" data-ntt-sn="9134921">[국립대학육성사업] 2026 GNU 개척리더스 창업아이디어 해커톤 경진대회 모집 안내</a></td><td>창업지원단 기업가정신센터</td><td>2026.11.02</td></tr>
<tr><td>2648</td><td class="subject"><a href="/main/na/ntt/selectNttInfo.do?mi=1126&amp;bbsId=1028&amp;nttSn=9100001">2026학년도 2학기 국가장학금 2차 신청 안내 (~11.20)</a></td><td>장학과</td><td>2026.11.01</td></tr>
<tr><td>2647</td><td class="subject"><a href="/main/na/ntt/selectNttInfo.do?mi=1126&amp;bbsId=1028&amp;nttSn=9100002">칠암캠퍼스 셔틀버스 운행시간 변경 안내</a></td><td>총무과</td><td>2026.10.30</td></tr>
</tbody></table>
<div class="paging"><a href="?mi=1126&amp;bbsId=1028&amp;currPage=2">2</a></div>
</div></body></html>
"""

DETAIL_HTML = """
<html><body>
<header><div class="gnb">메뉴 메뉴 메뉴</div></header>
<div class="bbs_view">
<h3 class="bbs_tit">[국립대학육성사업] 2026 GNU 개척리더스 창업아이디어 해커톤 경진대회 모집 안내</h3>
<table class="bbs_info"><tbody>
<tr><th>등록일</th><td>2026.11.02</td><th>부서</th><td>창업지원단 기업가정신센터</td></tr>
<tr><th>조회수</th><td>1,284</td><th>연락처</th><td>055-772-4697</td></tr>
<tr><th>첨부파일</th><td><a href="/common/nttFileDownload.do?fileKey=abc123">붙임1. 운영계획.hwp (다운로드 : 12회)</a>
<a href="/common/nttFileDownload.do?fileKey=def456">붙임2. 참가신청서.hwp (다운로드 : 30회)</a></td></tr>
</tbody></table>
<div class="bbs_content">
<p>창업지원단 기업가정신센터에서는 교내 학생을 대상으로 창업아이디어를 평가받을 수 있는 기회를 제공하기 위하여 해커톤 경진대회를 운영합니다.</p>
<p>1. 참가대상: 경상국립대 학부생 (3~5인 팀)<br/>2. 접수기간: ~'26. 11. 11.(수) 오전 09:00<br/>3. 해커톤: '26. 12. 4.(금) ~ 12. 5.(토), 가좌캠퍼스</p>
<p>4. 제출: 신청서를 260425@gnu.ac.kr 로 제출</p>
</div>
<div class="bbs_nav"><p>다음글 경상국립대학교 학사학위복 디자인 공모 안내</p><p>이전글 생활관 추가 모집</p></div>
</div>
<footer>경상국립대학교 footer</footer>
</body></html>
"""

SCHEDULE_HTML = """
<html><body><div class="schedule"><h3>2026년 학사일정</h3>
<select name="schdulYear"><option value="2025">2025</option><option value="2026" selected>2026</option><option value="2027">2027</option></select>
<ul>
<li><span class="date">11.03(화) ~ 11.07(토)</span><span class="tit">2학기 수강 포기(취소) 신청</span></li>
<li><span class="date">11.17 ~ 11.21</span><span class="tit">2학기 등록금 분납 4차 납부</span></li>
<li><span class="date">12.15</span><span class="tit">2학기 종강</span></li>
<li><span class="date">2026.12.22(월) ~ 2027.01.09(금)</span><span class="tit">동계 계절학기</span></li>
</ul></div></body></html>
"""


def main():
    ok = True
    board = config.BOARDS[0]
    rows, pager = parse.parse_list(LIST_HTML, board["url"])
    print(f"[목록] {len(rows)}건, 페이지 파라미터={pager['page_param']}, 크기 파라미터={pager['size_param']}, 전체={pager['total']}")
    for r in rows:
        print("   ", r["ntt_sn"], r["date"], r["dept"], "|", r["title"][:35], "|", (r["detail_url"] or "")[-30:])
    if len(rows) != 5 or any(r["ntt_sn"] is None for r in rows):
        print("  !! 목록 파싱 실패"); ok = False
    if pager["page_param"] != "currPage" or pager["size_param"] != "pageUnit":
        print("  !! 페이지 파라미터 감지 실패"); ok = False

    det = parse.parse_detail(DETAIL_HTML, rows[2]["detail_url"])
    print(f"[상세] 날짜={det['date']} 부서={det['dept']} 조회={det['views']} 연락처={det['contact']} 첨부={len(det['attachments'])}")
    print("   본문:", det["body"][:80].replace("\n", " / "))
    if det["views"] != 1284 or len(det["attachments"]) != 2 or "해커톤" not in det["body"] or "다음글" in det["body"]:
        print("  !! 상세 파싱 실패"); ok = False

    cat, why = classify(rows[2]["title"], rows[2]["dept"], det["body"], board)
    dl = find_deadline(rows[2]["title"], det["body"], "2026-11-02")
    camp = tag_campus(rows[2]["title"], rows[2]["dept"], det["body"])
    print(f"[분류] {cat} ({why}) / 마감={dl[0]} ({dl[1]}) / 캠퍼스={camp}")
    if cat != "취업·창업" or dl[0] != "2026-11-11" or "가좌" not in camp:
        print("  !! 분류/마감 실패"); ok = False

    for r in rows:
        c, w = classify(r["title"], r["dept"], "", board)
        print(f"   - {r['title'][:30]:<32} → {c:<8} ({w})")

    items = parse_schedule(SCHEDULE_HTML, 2026)
    print(f"[학사일정] {len(items)}건")
    for it in items:
        print("   ", it["start"], "~", it["end"], it["title"])
    if len(items) != 4 or items[-1]["end"] != "2027-01-09":
        print("  !! 학사일정 파싱 실패"); ok = False

    print("\n자가 테스트", "통과 ✔" if ok else "실패 ✘ — 이 출력을 그대로 보내주세요")
    return 0 if ok else 1


if __name__ == "__main__":
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
