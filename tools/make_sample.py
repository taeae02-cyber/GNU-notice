# -*- coding: utf-8 -*-
"""사이트 미리보기용 예시 데이터 생성 (실제 수집 전에 화면을 확인할 때).
실행: python tools/make_sample.py
실제 수집(python crawl.py)을 돌리면 덮어써짐.
"""
import sys
import json
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from gnu import store, config  # noqa: E402
from gnu.classify import classify, tag_campus  # noqa: E402
from gnu.dday import find_deadline  # noqa: E402

today = date.today()


def d(n):
    return (today + timedelta(days=n)).isoformat()


def k(n):
    return (today + timedelta(days=n)).strftime("%Y. %m. %d.")


BOARD = {b["id"]: b for b in config.BOARDS}
DEPT_BOARD = {"id": "dept-ee", "name": "전기공학과 공지", "scope": "학과", "unit": "전기공학과",
              "college": "IT공과대학", "url": "https://www.gnu.ac.kr/", "default_category": None}

SAMPLES = [
    # (board_id, title, dept, posted_offset, views, body, attachments)
    ("main-janghak", "2026학년도 2학기 국가장학금 2차 신청 안내", "장학과", -2, 1842,
     f"한국장학재단 국가장학금 2차 신청 기간을 안내합니다.\n\n1. 신청기간: {k(-2)}(화) ~ {k(1)}(금) 18:00\n2. 신청방법: 한국장학재단 홈페이지 또는 앱\n3. 유의사항: 기한 내 미신청 시 2학기 국가장학금 지급 불가\n문의: 장학과 055-772-1234",
     [{"name": "국가장학금 2차 신청 안내문.pdf", "url": "https://www.gnu.ac.kr/common/nttFileDownload.do?fileKey=sample1"}]),
    ("main-notice", "2027학년도 1학기 교환학생 파견 모집 (일본·미국·독일 등 32개교)", "국제교류본부", -3, 1284,
     f"2027학년도 1학기 교환학생 파견 프로그램 참가 학생을 모집합니다.\n\n1. 모집 대상: 2학기 이상 이수한 재학생\n2. 파견 기간: 2027. 3. ~ 2027. 8.\n3. 지원 자격: 직전 학기 성적 3.0 이상, 어학 성적(JLPT N2, TOEFL 80 등)\n4. 접수기간: {k(-2)} ~ {k(5)}(일) 23:59\n5. 접수방법: 국제교류본부 온라인 신청 후 서류 제출\n문의: 국제교류본부 055-772-0000",
     [{"name": "2027-1 교환학생 모집요강.pdf", "url": "https://www.gnu.ac.kr/common/nttFileDownload.do?fileKey=sample2"},
      {"name": "파견대학 목록 및 지원자격.hwp", "url": "https://www.gnu.ac.kr/common/nttFileDownload.do?fileKey=sample3"}]),
    ("main-haksa", "2026학년도 2학기 수강 포기(취소) 신청 안내", "교무과", -1, 2210,
     f"2학기 수강 포기 신청을 아래와 같이 실시합니다.\n\n- 신청기간: {k(0)}(수) 10:00 ~ {k(4)}(일) 17:00\n- 신청방법: 통합정보시스템 → 수업 → 수강포기신청\n- 유의사항: 포기 후 학점 복구 불가, 최소 이수학점 확인 필수", []),
    ("main-haksa", "2026학년도 동계 계절학기 수강신청 안내", "교무과", -5, 980,
     f"동계 계절학기 수강신청 안내\n\n1. 수강신청 기간: {k(20)}(월) 10:00 ~ {k(24)}(금) 17:00\n2. 개설과목: 첨부파일 참조\n3. 등록금 납부: {k(27)} ~ {k(29)}",
     [{"name": "동계 계절학기 개설과목.xlsx", "url": "https://www.gnu.ac.kr/common/nttFileDownload.do?fileKey=sample4"}]),
    ("main-notice", "[국립대학육성사업] 2026 GNU 개척리더스 창업아이디어 해커톤 경진대회 모집 안내", "창업지원단 기업가정신센터", -2, 611,
     f"창업지원단 기업가정신센터에서는 교내 학생을 대상으로 창업아이디어를 평가받을 수 있는 기회를 제공하기 위하여 해커톤 경진대회를 운영합니다.\n\n1. 참가대상: 경상국립대 학부생 (3~5인 팀, 8팀 내외)\n2. 접수기간: ~{k(7)}(수) 오전 09:00\n3. 사전교육(ZOOM): {k(21)}, {k(26)} 19:00~21:00\n4. 해커톤: {k(30)}(금) 11:20 ~ {k(31)}(토) 11:50, 가좌캠퍼스\n5. 제출: 신청서를 260425@gnu.ac.kr 로 제출\n문의: 055-772-4697",
     [{"name": "붙임1. 해커톤 운영계획.hwp", "url": "https://www.gnu.ac.kr/common/nttFileDownload.do?fileKey=sample5"},
      {"name": "붙임2. 참가신청서.hwp", "url": "https://www.gnu.ac.kr/common/nttFileDownload.do?fileKey=sample6"}]),
    ("main-notice", "2026년 취업활동사례 수기 공모전 안내", "진로취업지원실", -2, 402,
     f"취업에 성공한 재학생·졸업생의 취업활동 사례를 공모합니다.\n- 접수: ~{k(12)}\n- 시상: 최우수 1, 우수 3, 장려 5", []),
    ("main-notice", "칠암캠퍼스 셔틀버스 운행시간 변경 안내", "총무과", -4, 3301,
     "동절기 셔틀버스 운행시간을 변경합니다.\n- 적용일: 11월 10일부터\n- 가좌 → 칠암 첫차 08:00, 막차 21:30\n- 칠암 → 가좌 첫차 08:20, 막차 21:50\n운행시간표는 첨부파일을 확인하세요.",
     [{"name": "동절기 셔틀 시간표.pdf", "url": "https://www.gnu.ac.kr/common/nttFileDownload.do?fileKey=sample7"}]),
    ("main-notice", "중앙도서관 시험기간 24시간 열람실 운영 안내", "도서관", -6, 1520,
     f"기말고사 기간 24시간 열람실을 운영합니다.\n- 운영기간: {k(35)} ~ {k(49)}\n- 장소: 중앙도서관 1층 제1열람실 (가좌), 칠암도서관 2층 열람실", []),
    ("main-event", "2026 GNU 취업 콘서트 - 삼성전자 현직자 특강", "진로취업지원실", -1, 733,
     f"삼성전자 현직자가 들려주는 반도체 직무 이야기\n- 일시: {k(9)}(금) 14:00\n- 장소: GNU컨벤션센터 대강당\n- 신청: {k(6)}까지 학생역량관리시스템", []),
    ("main-event", "2026 진주학연구센터 제7회 정기학술대회 개최", "진주학연구센터", -3, 210,
     f"진주학연구센터 정기학술대회를 개최합니다.\n- 일시: {k(15)}(금) 13:00\n- 장소: 인문대학 세미나실", []),
    ("main-external", "[홍보]「2026년 진주시 기후변화·탄소중립 우수사례 공모전」참여 안내", "진주시탄소중립지원센터", -2, 98,
     f"진주시 탄소중립 우수사례 공모전\n- 접수기간: ~{k(25)}\n- 대상: 진주시민 누구나", []),
    ("main-external", "서울미래인재재단 대표 캐릭터 공모전", "서울미래인재재단", -2, 45,
     f"대표 캐릭터 공모 - 접수 {k(-10)} ~ {k(18)}", []),
    ("main-notice", "2026학년도 2학기 학생생활관 동계방학 입사 신청 안내", "학생생활관", -3, 2777,
     f"동계방학 생활관 입사 신청\n- 신청기간: {k(2)}(금) 10:00 ~ {k(8)}(목) 17:00\n- 대상: 가좌·칠암 생활관 재사생 및 신규 희망자\n- 입사일: {k(40)}", []),
    ("main-janghak", "2026학년도 2학기 교내 성적우수장학금 지급 안내", "장학과", -8, 1100,
     "2학기 성적우수장학금이 11월 15일 지급됩니다. 계좌 미등록자는 통합정보시스템에서 계좌를 등록하세요.", []),
    ("main-janghak", "2027학년도 1학기 등록금 분납 신청 안내", "재무과", -9, 540,
     f"등록금 분납 신청 기간: {k(60)} ~ {k(66)}\n분납 횟수: 4회", []),
    ("main-notice", "GNU 공식 앱 서비스 점검 안내", "정보전산원", -1, 320,
     f"시스템 점검으로 {k(3)} 02:00~06:00 서비스가 중단됩니다.", []),
    ("main-notice", "2026 GNU 개척리더스 창업서포터즈(3기) 프로그램 모집", "창업지원단 기업가정신센터", -2, 150,
     f"창업서포터즈 3기 모집 - 접수 ~{k(-1)} 18:00 (마감)", []),
    ("main-haksa", "2027학년도 1학기 복수전공·부전공 신청 안내", "교무과", -12, 1330,
     f"복수전공/부전공 신청기간: {k(-3)} ~ {k(-1)} 18:00", []),
    ("main-chaeyong", "2026학년도 2학기 교내 근로장학생 추가 모집", "학생과", -4, 870,
     f"근로장학생 추가 모집 - 접수: ~{k(5)}", []),
    ("main-haksa", "2026학년도 2학기 기말고사 일정 및 이러닝 시험 안내", "교무과", -2, 1950,
     f"기말고사: {k(37)} ~ {k(43)}\n이러닝 과목 시험: {k(30)} 10:00 ~ {k(36)} 23:59 (LMS)", []),
    ("main-notice", "JLPT·TOEIC 응시료 지원 사업 안내 (어학교육원)", "국제어학원", -5, 690,
     f"어학시험 응시료 지원 신청 - {k(-4)} ~ {k(10)}", []),
    ("main-notice", "2026 GNU 가을 축제 '개척제' 프로그램 안내", "학생과", -14, 4210,
     "가을 축제 프로그램 안내 (10/28 ~ 10/30, 가좌캠퍼스 대운동장)", []),
    ("main-notice", "통영캠퍼스 학생식당 운영시간 변경", "총무과", -7, 180,
     "통영캠퍼스 학생식당 저녁 운영이 11월부터 18:30까지로 변경됩니다.", []),
    ("main-external", "2026 경남 청년정책 아이디어 공모전", "경상남도", -6, 77,
     f"경남 청년정책 공모 - 접수 ~{k(14)}", []),
    ("main-janghak", "2027년도 관정재단 장학생 신청 안내", "장학과", -3, 2100,
     f"관정이종환교육재단 2027년도 장학생 선발\n- 신청기간: ~{k(5)} 18:00\n- 대상: 2학년 이상, 직전학기 3.5 이상", []),
    ("main-haksa", "★중요★ 2027학년도 1학기 전공 배정 계획 공고", "교무과", -1, 1500,
     f"자율전공 학생 전공 배정 신청: {k(3)} ~ {k(9)}", []),
]

DEPT_SAMPLES = [
    ("전기공학과 2026학년도 졸업작품 발표회 참가 신청", "전기공학과", -2, 240,
     f"졸업작품 발표회 참가 신청\n- 신청: ~{k(7)}\n- 발표회: {k(21)} 13:00, 공학관 301호", []),
    ("2027학년도 1학기 전기공학과 전공 교과목 개설 수요조사", "전기공학과", -4, 310,
     f"수요조사 설문: {k(-3)} ~ {k(3)}", []),
    ("전기기사 필기 대비 특강 (학과 주관) 수강생 모집", "전기공학과", -1, 520,
     f"특강 기간: {k(10)} ~ {k(24)} 매주 화·목 18:00\n신청: ~{k(6)} 학과사무실", []),
    ("2026학년도 2학기 전기공학과 학생회 간담회 안내", "전기공학과 학생회", -9, 130,
     f"간담회 일시: {k(-5)} 18:00", []),
    ("[교외장학금] 2027년도 관정재단 장학생 신청 안내(~11/9 18시)", "전기공학과", -2, 90,
     f"관정이종환교육재단 2027년도 장학생 선발 안내입니다. 학과 사무실로 서류 제출.\n- 신청기간: ~{k(5)} 18:00", []),
]


def main():
    index = {}
    seq = 9000000
    for bid, title, dept, off, views, body, atts in SAMPLES:
        board = BOARD[bid]
        seq += 1
        posted = d(off)
        nid = store.make_id(bid, seq, title, posted)
        cat, why = classify(title, dept, body, board)
        dl, src, snip = find_deadline(title, body, posted)
        n = {
            "id": nid, "board_id": bid, "board": board["name"], "scope": board["scope"],
            "unit": None, "college": None, "title": title, "dept": dept, "date": posted, "views": views,
            "url": f"https://www.gnu.ac.kr/main/na/ntt/selectNttInfo.do?mi=1126&bbsId=1028&nttSn={seq}",
            "category": cat, "category_reason": why, "campus": tag_campus(title, dept, body),
            "deadline": dl, "deadline_source": src, "deadline_text": snip,
            "has_attachments": bool(atts), "first_seen": store.now_iso(), "fetched_at": store.now_iso(),
        }
        index[nid] = n
        store.save_body(nid, {"id": nid, "title": title, "body": body, "attachments": atts,
                              "contact": "055-772-0000", "schedule": None, "author": None,
                              "fetched_at": store.now_iso()})
    for title, dept, off, views, body, atts in DEPT_SAMPLES:
        seq += 1
        posted = d(off)
        nid = store.make_id(DEPT_BOARD["id"], seq, title, posted)
        cat, why = classify(title, dept, body, DEPT_BOARD)
        dl, src, snip = find_deadline(title, body, posted)
        n = {
            "id": nid, "board_id": DEPT_BOARD["id"], "board": DEPT_BOARD["name"], "scope": "학과",
            "unit": "전기공학과", "college": "IT공과대학", "title": title, "dept": dept, "date": posted,
            "views": views, "url": "https://www.gnu.ac.kr/",
            "category": cat, "category_reason": why, "campus": tag_campus(title, dept, body),
            "deadline": dl, "deadline_source": src, "deadline_text": snip,
            "has_attachments": bool(atts), "first_seen": store.now_iso(), "fetched_at": store.now_iso(),
        }
        index[nid] = n
        store.save_body(nid, {"id": nid, "title": title, "body": body, "attachments": atts,
                              "contact": "055-772-1700", "schedule": None, "author": None,
                              "fetched_at": store.now_iso()})

    status = {b["id"]: {"name": b["name"], "ok": True, "new": 0, "updated": 0, "errors": 0, "listed": 0}
              for b in config.BOARDS}
    status["dept-ee"] = {"name": "전기공학과 공지", "ok": True, "new": 0, "updated": 0, "errors": 0, "listed": 0}
    total = store.save_index(index, status)
    meta = json.loads((store.DATA / "meta.json").read_text(encoding="utf-8"))
    meta["sample"] = True
    (store.DATA / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    store.save_departments(config.BOARDS + [DEPT_BOARD])

    sched = [
        {"start": d(-1), "end": d(3), "title": "2학기 수강 포기(취소) 신청"},
        {"start": d(13), "end": d(17), "title": "2학기 등록금 분납 4차 납부"},
        {"start": d(20), "end": d(24), "title": "동계 계절학기 수강신청"},
        {"start": d(37), "end": d(43), "title": "2학기 기말고사"},
        {"start": d(44), "end": d(44), "title": "2학기 종강"},
        {"start": d(48), "end": d(66), "title": "동계 계절학기 수업"},
        {"start": d(75), "end": d(79), "title": "2027학년도 1학기 수강신청"},
        {"start": d(-20), "end": d(-16), "title": "2학기 중간고사"},
    ]
    sched.sort(key=lambda x: x["start"])
    for i, it in enumerate(sched):
        it["target"] = "대학원" if i == 1 else "학부"
    store.save_schedule(sched)
    from gnu.calendar_feed import save_calendars
    save_calendars(index, sched, config.BOARDS + [DEPT_BOARD])
    print(f"예시 데이터 {total}건 + 학사일정 {len(sched)}건 생성 → docs/data/")


if __name__ == "__main__":
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
