# GNU 공지 — 경상국립대 공지 모아보기

흩어진 학교 공지를 한 곳에 모으고, 카테고리·학과·캠퍼스로 거르고, 마감 D-day를 붙이고,
내 키워드에 맞는 새 글을 알려주는 사이트.

```
boards.json          수집할 게시판 목록 (여기에 학과 게시판 추가)
crawl.py             수집기 (python crawl.py)
gnu/                 수집기 내부 코드 (config: 분류 규칙 / parse: HTML 해석 / dday: 마감일 / schedule: 학사일정)
docs/                사이트 (GitHub Pages 가 이 폴더를 보여줌)
docs/data/           수집 결과 JSON (사이트가 읽음)
tools/selftest.py    인터넷 없이 수집기 점검
tools/make_sample.py 예시 데이터 (화면 미리보기용)
tools/find_boards.py 모든 학과·단과대 공지 게시판 자동 찾기
tools/add_board.py   게시판 하나 추가
.github/workflows/   GitHub 에서 1시간마다 자동 수집
run.bat / preview.bat / selftest.bat / find_boards.bat   윈도우용 더블클릭 실행
```

## 1. 내 컴퓨터에서 돌려보기

1. Python 설치 (python.org, 설치 시 **Add python.exe to PATH** 체크)
2. `selftest.bat` 더블클릭 → 마지막 줄에 `자가 테스트 통과 ✔` 가 나오면 준비 끝
3. `run.bat` 더블클릭 → 학교 게시판을 돌면서 공지를 받아옴 (처음엔 1~3분)
   - 명령창에서 직접: `python crawl.py --pages 3` (처음 한 번은 과거 글까지 넉넉히)
4. `preview.bat` 더블클릭 → 브라우저에서 사이트 확인

실패한 게시판이 있으면 `debug/` 폴더에 HTML 이 저장돼요. 그 파일을 보내주면 파서를 고칠 수 있어요.

## 2. 학과·단과대 게시판 전부 추가

`find_boards.bat` 더블클릭 (또는 `python tools/find_boards.py`)
→ 18개 단과대 + 112개 학과 홈페이지를 돌면서 공지사항 게시판 주소를 찾아 `boards.json` 에 넣어요 (3~5분).
결과는 `setup/find_boards_report.txt` 에 ✔/✘ 로 정리되고, ✘(못 찾은 사이트)의 HTML 은 `debug/sites/` 에 저장돼요.
그 다음 `run.bat` 를 다시 실행하면 학과 공지까지 수집돼요.

학과 목록은 `tools/departments_seed.json` (2026.3.1 기준 학교 홈페이지 단과대학 안내). 학과가 바뀌면 여기 고치고 다시 실행.

하나만 추가할 때:
```
python tools/add_board.py "게시판주소" --name "전기공학과 공지" --scope 학과 --unit 전기공학과 --college IT공과대학
```

## 3. GitHub 에 올려서 자동으로 돌리기

1. GitHub 에서 새 저장소 `gnu-notice` (Public) 생성
2. 이 폴더 전체를 올림 (GitHub Desktop 또는 웹에서 업로드)
3. 저장소 **Settings → Pages → Source: Deploy from a branch → Branch: main, 폴더: /docs → Save**
4. 저장소 **Settings → Actions → General → Workflow permissions → Read and write permissions → Save**
5. **Actions** 탭 → "공지 수집" → **Run workflow** 로 한 번 수동 실행
6. 몇 분 뒤 `https://<아이디>.github.io/gnu-notice/` 에서 확인

그 뒤로는 매시 7분에 자동으로 수집돼요. (GitHub 사정으로 몇 분 늦을 수 있음)

> GitHub 서버(해외)에서 학교 사이트 접속이 막혀 있으면 Actions 가 실패해요.
> 그럴 땐 내 컴퓨터의 작업 스케줄러로 `run.bat` 를 1시간마다 돌리는 방법으로 바꿉니다.

## 4. 분류 신고 연결

`docs/app.js` 맨 위 `CONFIG.reportIssueUrl` 에 `https://github.com/<아이디>/gnu-notice/issues/new` 를 넣으면
"분류 신고" 버튼이 GitHub 이슈로 연결돼요.

## 5. 자주 묻는 것

- **수집 주기 바꾸기**: `.github/workflows/crawl.yml` 의 `cron` 줄 (`"7 * * * *"` = 매시 7분)
- **분류 규칙 고치기**: `gnu/config.py` 의 `RULES` — 단어를 추가/삭제한 뒤 `python crawl.py --reclassify` 로 저장된 글 전체를 다시 분류
- **로그인이 필요한 게시판**은 자동으로 `boards.json` 에 `"disabled": true` 가 붙고 건너뛰어요
- **마감일이 틀리게 잡힘**: `gnu/dday.py` 의 `NEG_WORDS`(행사 날짜로 보는 단어) / `DEADLINE_WORDS`(마감으로 보는 단어)
- **글 보관 기간**: `gnu/store.py` 의 `RETENTION_DAYS` (기본 365일)
